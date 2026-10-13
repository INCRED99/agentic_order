-- Migration 011: one order per source mail (D47, option a). Run once in the Supabase SQL editor. Needs 007 applied first.
-- Part 1 adds a unique index. Part 2 replaces create_pending_order() so a second call for the same mail returns the FIRST order.

-- DECISION PROBLEM (D47, chosen by the user): ToolRetry or a crash can call create_pending_order twice for one mail.
-- Options: (a) unique key on orders(owner_id, source_email_id), (b) check first in Python, (c) no guard.
-- Chosen: a. Reason: the database decides, so there is no race gap, same claim idea as D32 and D39.
-- Cost: one mail means one order forever. A second order needs a second mail. Orders made by hand (no source mail) are not affected.

-- PART 1. The index. It fails if two orders already share the same source mail. Test orders made by hand have a null source mail, which is allowed.
create unique index if not exists orders_owner_source_email_key  -- create the index only if it does not exist yet
  on public.orders (owner_id, source_email_id)  -- one row per restaurant and mail
  where source_email_id is not null;  -- orders without a source mail are not limited

-- PART 2. Same function as 007, plus the lock and the lookup marked NEW below.
create or replace function public.create_pending_order(  -- create the function, or replace the 007 version
  p_owner_id uuid,  -- restaurant that owns the order, from the mail slug, never from mail text
  p_customer_id uuid,  -- customer row of this restaurant
  p_source_email_id uuid,  -- the mail that caused the order, may be null
  p_items jsonb  -- list like [{"menu_item_id": "...", "quantity": 2}]
) returns jsonb  -- returns {"order_id": ..., "total_paise": ..., "already_existed": true or false}
language plpgsql  -- the procedural language of Postgres
set search_path = public  -- fixed search path, so no other schema can shadow our tables
as $$
declare  -- variables used below
  v_lines jsonb;  -- the items merged to one row per dish
  v_bad text;  -- names or ids that failed a check
  v_total bigint;  -- total in paise, bigint so a huge value is caught before it overflows
  v_order_id uuid;  -- id of the new order, or of the existing one (NEW use)
  v_existing_total integer;  -- NEW: total of an order that already exists for this mail
begin  -- start of the function body, everything below is one transaction
  if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then  -- must be a non-empty list
    raise exception 'invalid_items';  -- stop, the caller maps this to a clear message
  end if;  -- end of the check
  if jsonb_array_length(p_items) > 50 then  -- sanity cap on lines
    raise exception 'too_many_lines';  -- stop
  end if;  -- end of the check

  if exists (  -- look for any malformed element
    select 1 from jsonb_array_elements(p_items) e  -- every element of the list
    where jsonb_typeof(e) is distinct from 'object'  -- must be an object
       or jsonb_typeof(e->'menu_item_id') is distinct from 'string'  -- id must be text
       or lower(coalesce(e->>'menu_item_id', '')) !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'  -- and look like a uuid
       or jsonb_typeof(e->'quantity') is distinct from 'number'  -- quantity must be a number
       or coalesce(e->>'quantity', '') !~ '^[0-9]{1,4}$'  -- whole number with at most 4 digits, so no decimals, no negatives
  ) then  -- at least one bad element
    raise exception 'invalid_items';  -- stop
  end if;  -- end of the check

  select jsonb_agg(jsonb_build_object('id', s.id, 'qty', s.qty))  -- merge repeated dishes into one line
  into v_lines  -- keep the merged list
  from (  -- one row per dish with the summed quantity
    select (e->>'menu_item_id')::uuid as id, sum((e->>'quantity')::integer) as qty  -- dish id and total quantity
    from jsonb_array_elements(p_items) e  -- every element of the list
    group by 1  -- one row per dish
  ) s;  -- end of the merge

  if exists (select 1 from jsonb_to_recordset(v_lines) as l(id uuid, qty integer) where l.qty < 1) then  -- zero is not an order
    raise exception 'invalid_items';  -- stop
  end if;  -- end of the check
  if exists (select 1 from jsonb_to_recordset(v_lines) as l(id uuid, qty integer) where l.qty > 1000) then  -- sanity cap per dish
    raise exception 'quantity_too_large';  -- stop
  end if;  -- end of the check

  if not exists (select 1 from public.customers where id = p_customer_id and owner_id = p_owner_id) then  -- customer must belong to this restaurant
    raise exception 'customer_not_found';  -- stop
  end if;  -- end of the check
  if p_source_email_id is not null and not exists (select 1 from public.emails where id = p_source_email_id and owner_id = p_owner_id) then  -- mail must belong to this restaurant
    raise exception 'email_not_found';  -- stop
  end if;  -- end of the check

  -- NEW (D47): one order per mail. Placed BEFORE the stock checks, so a retry gets the first order even if stock changed since.
  if p_source_email_id is not null then  -- only mails that caused the order
    perform pg_advisory_xact_lock(hashtextextended(p_source_email_id::text, 0));  -- two calls for the same mail wait for each other, the lock frees itself at the end of the transaction
    select o.id, o.total_paise into v_order_id, v_existing_total  -- look for an order made from this mail
    from public.orders o  -- the orders table
    where o.owner_id = p_owner_id and o.source_email_id = p_source_email_id  -- same restaurant, same mail
    limit 1;  -- at most one, the unique index guarantees it
    if v_order_id is not null then  -- an order already exists
      return jsonb_build_object('order_id', v_order_id, 'total_paise', v_existing_total, 'already_existed', true);  -- hand back the FIRST order, create nothing
    end if;  -- end of the check
  end if;  -- end of the new block

  select string_agg(l.id::text, ', ') into v_bad  -- dishes that do not exist for this owner
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)  -- the merged lines
  left join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id  -- another restaurant's dish counts as not found
  where m.id is null;  -- no match
  if v_bad is not null then  -- at least one missing dish
    raise exception 'item_not_found: %', v_bad;  -- the text after the colon lists the ids
  end if;  -- end of the check

  select string_agg(m.name, ', ') into v_bad  -- dishes that are hidden from the agent
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)  -- the merged lines
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id  -- the dish rows
  where not m.is_available;  -- hidden dishes
  if v_bad is not null then  -- at least one unavailable dish
    raise exception 'item_unavailable: %', v_bad;  -- the text after the colon lists the names
  end if;  -- end of the check

  select string_agg(m.name || ' (have ' || i.quantity || ', want ' || l.qty || ')', ', ') into v_bad  -- dishes with too little stock
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)  -- the merged lines
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id  -- the dish rows
  join public.inventory i on i.menu_item_id = l.id and i.owner_id = p_owner_id  -- inner join: dishes without a stock row are skipped
  where i.quantity < l.qty;  -- not enough left
  if v_bad is not null then  -- at least one dish is short
    raise exception 'insufficient_stock: %', v_bad;  -- the text after the colon says how much is left
  end if;  -- end of the check

  select sum(m.price_paise::bigint * l.qty) into v_total  -- total from DB prices only
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)  -- the merged lines
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id;  -- the dish rows
  if v_total > 2147483647 then  -- orders.total_paise is an integer
    raise exception 'total_too_large';  -- stop before the insert fails with an overflow
  end if;  -- end of the check

  insert into public.orders (owner_id, customer_id, source_email_id, status, total_paise)  -- create the order
  values (p_owner_id, p_customer_id, p_source_email_id, 'PENDING', v_total::integer)  -- always starts PENDING
  returning id into v_order_id;  -- keep its id

  insert into public.order_items (owner_id, order_id, menu_item_id, quantity, unit_price_paise)  -- create the lines
  select p_owner_id, v_order_id, l.id, l.qty, m.price_paise  -- price snapshot copied from the menu
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)  -- the merged lines
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id;  -- the dish rows

  return jsonb_build_object('order_id', v_order_id, 'total_paise', v_total::integer, 'already_existed', false);  -- what the caller needs, plus the new flag
end;  -- end of the function body
$$;  -- end of the function

-- SECURITY: same lock-down as 007. Re-applied so nothing depends on how replace treats permissions.
revoke all on function public.create_pending_order(uuid, uuid, uuid, jsonb) from public, anon, authenticated;  -- nobody by default
grant execute on function public.create_pending_order(uuid, uuid, uuid, jsonb) to service_role;  -- only the backend key can call it