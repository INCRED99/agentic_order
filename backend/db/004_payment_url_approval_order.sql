-- Migration 004. Run once in the Supabase SQL editor. Safe on existing data.
-- D4 (user's decision): store the Razorpay payment link URL on the payment row.
-- D5 (user's decision): link each approval to the order it is about.

-- DECISION PROBLEM (D4): where does the clickable payment link URL come from?
-- Options: (a) store it in payments, (b) ask Razorpay every time.
-- Chosen: (a). Reason: one read, no outside call, the dashboard keeps working if Razorpay is slow.
-- Cost: one more column to fill when the link is created.
alter table public.payments  -- change the payments table
  add column if not exists payment_link_url text;  -- Razorpay short_url, null until a link exists

-- DECISION PROBLEM (D5): how does an approval point to its order?
-- Options: (a) a real column with a foreign key, (b) order_id inside the payload JSON.
-- Chosen: (a). Reason: the database checks the link, and the join and index are fast.
-- Cost: one migration. The column is nullable because some approvals may not be about an order.
alter table public.approvals  -- change the approvals table
  add column if not exists order_id uuid references public.orders(id) on delete cascade;  -- deleting an order removes its approvals

create index if not exists approvals_order_id_idx on public.approvals (order_id);  -- speeds up "does this order have a pending approval"