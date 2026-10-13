-- Migration 006. Run once in the Supabase SQL editor. Needs migrations 004 and 005 applied first.
-- Creates mark_order_paid(): one all-or-nothing step that marks an order PAID and deducts stock.
-- The backend calls it with rpc after the Razorpay webhook has been verified.

-- DECISION PROBLEM: marking PAID and deducting stock are two writes. A crash between them would leave money taken but stock unchanged.
-- Options: (1) two calls from Python, (2) one Postgres function, so both writes live in one transaction.
-- Chosen: option 2. Reason: money needs all-or-nothing, and a function runs as a single transaction.
-- Cost: logic lives in SQL, so it is tested and changed in the database, not in Python.

-- DECISION PROBLEM (D20, assumed by me, not yet confirmed): what happens when a paid order has a dish that is out of stock?
-- Options: (a) mark PAID, deduct nothing, create an approval so the owner decides (refund or substitute),
--          (b) mark PAID, deduct the dishes that are in stock, approval only for the short ones.
-- Chosen: (a). Reason: stock for one order is either fully deducted or not touched, so the numbers stay simple to reason about.
-- Cost: stock is not reduced for such an order until the owner resolves the approval.
-- A dish with no inventory row means "stock not tracked". It is never counted as short and never deducted.

create or replace function public.mark_order_paid(  -- create the function, or replace an older version
  p_owner_id uuid,  -- restaurant that owns the order, taken from the order lookup, never from the webhook body
  p_order_id uuid,  -- order that was paid
  p_payment_link_id text,  -- Razorpay payment link id, used to find the payment row
  p_payment_id text,  -- Razorpay payment id, unique, this is the idempotency key
  p_amount_paise integer  -- amount Razorpay says was paid
) returns text  -- returns paid, paid_out_of_stock or already_paid
language plpgsql  -- the procedural language of Postgres
set search_path = public  -- fixed search path, so no other schema can shadow our tables
as $$
declare  -- variables used below
  v_order public.orders%rowtype;  -- the locked order row
  v_short text;  -- names of dishes that are short, null when all are in stock
begin  -- start of the function body, everything below is one transaction
  select * into v_order  -- load the order
  from public.orders  -- from the orders table
  where id = p_order_id and owner_id = p_owner_id  -- it must belong to this owner
  for update;  -- lock the row, so a second webhook for the same order waits here

  if not found then  -- no such order for this owner
    raise exception 'order_not_found';  -- stop, the caller maps this to a clear error
  end if;  -- end of the check

  if v_order.status = 'PAID' then  -- the order was already paid by an earlier call
    return 'already_paid';  -- idempotent: a repeated webhook changes nothing
  end if;  -- end of the check

  if v_order.status <> 'PENDING' then  -- for example CANCELLED or REFUNDED
    raise exception 'order_not_pending';  -- stop. How to handle money for such orders is decided in the webhook step
  end if;  -- end of the check

  if v_order.total_paise <> p_amount_paise then  -- paid amount differs from the order total
    raise exception 'amount_mismatch';  -- safety net, the webhook code also checks this first
  end if;  -- end of the check

  update public.payments  -- record the payment on the row created with the link
  set razorpay_payment_id = p_payment_id, status = 'PAID'  -- unique payment id and the new status
  where order_id = p_order_id and owner_id = p_owner_id and razorpay_payment_link_id = p_payment_link_id;  -- the right row
  if not found then  -- no row was created with the link
    insert into public.payments (owner_id, order_id, razorpay_payment_link_id, razorpay_payment_id, amount_paise, status)  -- create it now
    values (p_owner_id, p_order_id, p_payment_link_id, p_payment_id, p_amount_paise, 'PAID');  -- paid right away
  end if;  -- end of the check

  update public.orders  -- mark the order paid
  set status = 'PAID', updated_at = now()  -- new status and time
  where id = p_order_id;  -- this order

  perform 1  -- lock the stock rows of this order, the result is not needed
  from public.inventory  -- stock table
  where owner_id = p_owner_id  -- this owner only
    and menu_item_id in (select menu_item_id from public.order_items where order_id = p_order_id)  -- dishes in this order
  order by menu_item_id  -- always lock in the same order, so two orders cannot deadlock each other
  for update;  -- lock them until this transaction ends

  select string_agg(m.name, ', ') into v_short  -- collect the names of short dishes
  from (  -- total quantity per dish, in case a dish appears on two lines
    select menu_item_id, sum(quantity) as qty from public.order_items where order_id = p_order_id group by menu_item_id
  ) a
  join public.inventory i on i.menu_item_id = a.menu_item_id and i.owner_id = p_owner_id  -- inner join: dishes without a stock row are skipped
  join public.menu_items m on m.id = a.menu_item_id  -- the dish name
  where i.quantity < a.qty;  -- not enough stock

  if v_short is not null then  -- at least one dish is short
    insert into public.approvals (owner_id, order_id, action, reason, payload, status)  -- ask the owner to decide
    values (  -- the new approval
      p_owner_id,  -- owner
      p_order_id,  -- the order
      'substitute_item',  -- known action name in the UI, the reason text says refund or substitute
      'Paid, but out of stock: ' || v_short || '. Refund or substitute.',  -- text shown on the Approvals page
      '{}'::jsonb,  -- no extra data yet
      'pending'  -- waiting for the owner
    );
    return 'paid_out_of_stock';  -- order is PAID, stock untouched
  end if;  -- end of the short branch

  update public.inventory i  -- deduct stock for every tracked dish
  set quantity = i.quantity - a.qty, updated_at = now()  -- new quantity and time
  from (  -- total quantity per dish
    select menu_item_id, sum(quantity)::integer as qty from public.order_items where order_id = p_order_id group by menu_item_id
  ) a
  where i.menu_item_id = a.menu_item_id and i.owner_id = p_owner_id;  -- match by dish and owner

  return 'paid';  -- order PAID and stock deducted
end;  -- end of the function body
$$;  -- end of the function

-- SECURITY: functions in the public schema can be called by browsers through the Supabase API.
-- Without the lines below, any signed-in user could call this function and mark their own order as paid for free.
revoke all on function public.mark_order_paid(uuid, uuid, text, text, integer) from public, anon, authenticated;  -- nobody by default
grant execute on function public.mark_order_paid(uuid, uuid, text, text, integer) to service_role;  -- only the backend key can call it