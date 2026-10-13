-- Migration 008. Run once in the Supabase SQL editor, after 007.
-- Implements D25 (duplicate link guard), D26 (24 h expiry) and D30 (expired order).

-- CHECK FIRST: run this query alone. It must return zero rows.
-- If it returns rows, test data has two payments for one order; delete the extras, then continue.
-- select order_id, count(*) from public.payments group by order_id having count(*) > 1;

-- DECISION PROBLEM (D30): what happens to an order whose payment link expired?
-- Options: (a) new status EXPIRED, (b) reuse CANCELLED.
-- Chosen: (a). Reason: the dashboard can tell "customer never paid" from "someone cancelled it".
-- Cost: the status check must be rebuilt, because the old list has no EXPIRED.
alter table public.orders drop constraint if exists orders_status_check;  -- remove the old status list (Postgres default name)
alter table public.orders add constraint orders_status_check  -- add the new status list under the same name
  check (status in ('PENDING','PAID','CANCELLED','REFUNDED','EXPIRED'));  -- same four values plus EXPIRED

-- DECISION PROBLEM (D25): where does the database stop a second link for one order?
-- Options: (a) unique on payments.order_id, (b) unique on the link id only.
-- Chosen: (a), plus (b) below. Reason: D30 says one link per order, ever, so one payments row per order.
-- Cost: refunds must update the same row (status REFUNDED), not insert a second row.
alter table public.payments add constraint payments_order_id_key unique (order_id);  -- at most one payments row per order

-- The link id must also be unique. Postgres allows many NULLs, so rows without a link yet are fine.
alter table public.payments add constraint payments_link_id_key unique (razorpay_payment_link_id);  -- same link cannot sit on two rows

-- DECISION PROBLEM (D26): where is the link expiry time kept?
-- Options: (a) a column on payments, (b) compute "created_at + 24 h" in code.
-- Chosen: (a). Reason: Razorpay's real expire_by is stored, and a later expiry sweep can query it.
-- Cost: one more column to fill when the link is created.
alter table public.payments  -- change the payments table
  add column if not exists payment_link_expires_at timestamptz;  -- Razorpay expire_by as a timestamp; null until a link exists

-- Speeds up the later expiry sweep: find unpaid links past their time.
create index if not exists payments_expiry_idx  -- index name
  on public.payments (payment_link_expires_at)  -- column to search by
  where status = 'CREATED';  -- only unpaid rows; keeps the index small