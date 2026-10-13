-- Migration 010: expiry sweep as one Postgres function (D30, D42 option a).

-- DECISION PROBLEM (D42, chosen by the user): who runs the expiry sweep.
-- Options: (a) SQL function called by the worker, (b) pg_cron inside Supabase, (c) Python select-then-update loop.
-- Chosen: a. Reason: one statement, safe against a webhook arriving at the same moment, no new moving part.
-- Cost: if the worker is down, the sweep stops. pg_cron can call this same function later (V2).

create or replace function public.expire_unpaid_orders()  -- create the function, or replace an older version
returns integer  -- returns how many orders were expired, useful for logs
language plpgsql  -- procedural language, needed for get diagnostics
set search_path = public  -- fixed search path, so a function name cannot be hijacked
as $$
declare
  v_count integer;  -- number of rows changed by the update below
begin
  update public.orders o  -- change orders...
     set status = 'EXPIRED',  -- ...to EXPIRED (allowed since 008)
         updated_at = now()  -- set explicitly, we do not know if a trigger does it
    from public.payments p  -- ...that have a payment row (one per order, unique since 008)
   where p.order_id = o.id  -- join payment to its order
     and p.owner_id = o.owner_id  -- same owner, tenant guard
     and o.status = 'PENDING'  -- ONLY unpaid orders. mark_order_paid locks the order row; if it wins, this check fails and we skip
     and p.status = 'CREATED'  -- the link was never paid, failed or refunded
     and p.payment_link_expires_at is not null  -- an order with no link has no expiry (D28 gap, see note below)
     and p.payment_link_expires_at < now();  -- the 24 hour link time (D26) has passed
  get diagnostics v_count = row_count;  -- how many orders the update changed
  return v_count;  -- give the number back to the caller
end;
$$;

-- NOTE (known gap): an order that stayed PENDING without any link (Razorpay failed, D28) has no expiry date, so this sweep ignores it.
-- Fix later: also expire PENDING orders with no link that are older than 24 hours.

revoke all on function public.expire_unpaid_orders() from public;  -- nobody by default
revoke all on function public.expire_unpaid_orders() from anon;  -- not the anonymous browser role
revoke all on function public.expire_unpaid_orders() from authenticated;  -- not a logged-in browser user
grant execute on function public.expire_unpaid_orders() to service_role;  -- only our backend (same pattern as 006 and 007)