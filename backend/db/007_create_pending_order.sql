-- Migration 007. Run once in the Supabase SQL editor. Needs migration 006 applied first (same permission pattern).
-- Creates create_pending_order(): writes an order and its lines in one transaction, with the total computed from DB prices.
-- The backend calls it with rpc. The agent's create_order tool will call it later. The LLM never supplies a price or a total.

-- DECISION PROBLEM (D22, chosen by the user): an order needs rows in two tables, orders and order_items.
-- Options: (a) one Postgres function, (b) two inserts in Python with a cleanup delete.
-- Chosen: (a). Reason: all-or-nothing, and prices are read inside the database, so the total cannot be faked from outside.
-- Cost: logic lives in SQL, so it is tested and changed in the database.
-- Order creation only CHECKS stock. Stock is deducted at payment, in mark_order_paid().
-- A dish with no inventory row means "stock not tracked": never counted as short.

create or replace function public.create_pending_order(  -- create the function, or replace an older version
  p_owner_id uuid,  -- restaurant that owns the order, from the mail slug, never from mail text
  p_customer_id uuid,  -- customer row of this restaurant
  p_source_email_id uuid,  -- the mail that caused the order, may be null
  p_items jsonb  -- list like [{"menu_item_id": "...", "quantity": 2}]
) returns jsonb  -- returns {"order_id": ..., "total_paise": ...}
language plpgsql  -- the procedural language of Postgres
set search_path = public  -- fixed search path, so no other schema can shadow our tables
as $$
declare  -- variables used below
  v_lines jsonb;  -- the items merged to one row per dish
  v_bad text;  -- names or ids that failed a check
  v_total bigint;  -- total in paise, bigint so a huge value is caught before it overflows
  v_order_id uuid;  -- id of the new order
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
    select (e->>'menu_item_id')::uuid as id, sum((e->>'quantity')::integer) as qty
    from jsonb_array_elements(p_items) e
    group by 1
  ) s;

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

  select string_agg(l.id::text, ', ') into v_bad  -- dishes that do not exist for this owner
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)
  left join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id  -- another restaurant's dish counts as not found
  where m.id is null;
  if v_bad is not null then  -- at least one missing dish
    raise exception 'item_not_found: %', v_bad;  -- the text after the colon lists the ids
  end if;  -- end of the check

  select string_agg(m.name, ', ') into v_bad  -- dishes that are hidden from the agent
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id
  where not m.is_available;
  if v_bad is not null then  -- at least one unavailable dish
    raise exception 'item_unavailable: %', v_bad;  -- the text after the colon lists the names
  end if;  -- end of the check

  select string_agg(m.name || ' (have ' || i.quantity || ', want ' || l.qty || ')', ', ') into v_bad  -- dishes with too little stock
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id
  join public.inventory i on i.menu_item_id = l.id and i.owner_id = p_owner_id  -- inner join: dishes without a stock row are skipped
  where i.quantity < l.qty;
  if v_bad is not null then  -- at least one dish is short
    raise exception 'insufficient_stock: %', v_bad;  -- the text after the colon says how much is left
  end if;  -- end of the check

  select sum(m.price_paise::bigint * l.qty) into v_total  -- total from DB prices only
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id;
  if v_total > 2147483647 then  -- orders.total_paise is an integer
    raise exception 'total_too_large';  -- stop before the insert fails with an overflow
  end if;  -- end of the check

  insert into public.orders (owner_id, customer_id, source_email_id, status, total_paise)  -- create the order
  values (p_owner_id, p_customer_id, p_source_email_id, 'PENDING', v_total::integer)  -- always starts PENDING
  returning id into v_order_id;  -- keep its id

  insert into public.order_items (owner_id, order_id, menu_item_id, quantity, unit_price_paise)  -- create the lines
  select p_owner_id, v_order_id, l.id, l.qty, m.price_paise  -- price snapshot copied from the menu
  from jsonb_to_recordset(v_lines) as l(id uuid, qty integer)
  join public.menu_items m on m.id = l.id and m.owner_id = p_owner_id;

  return jsonb_build_object('order_id', v_order_id, 'total_paise', v_total::integer);  -- what the caller needs
end;  -- end of the function body
$$;  -- end of the function

-- SECURITY: same lock-down as mark_order_paid. Only the backend key may call this function.
revoke all on function public.create_pending_order(uuid, uuid, uuid, jsonb) from public, anon, authenticated;  -- nobody by default
grant execute on function public.create_pending_order(uuid, uuid, uuid, jsonb) to service_role;  -- only the backend key can call it