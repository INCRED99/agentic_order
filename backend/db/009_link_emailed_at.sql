-- Migration 009: claim flag for the payment link mail (D39, option a).

-- DECISION PROBLEM (D39, chosen by the user): how to stop a double send of the link mail.
-- Options: (a) DB flag claimed with one update, (b) search the Gmail Sent folder, (c) no guard.
-- Chosen: a. Reason: one atomic update says who won, same claim-first idea as D32.
-- Cost: if SMTP fails after the claim, the sender must reset the flag (payment_mail.py does this).

alter table public.payments  -- change the payments table
  add column if not exists link_emailed_at timestamptz;  -- null = link mail not claimed yet, set = one sender already claimed it

comment on column public.payments.link_emailed_at is  -- documentation stored inside the database
  'When a sender claimed the job of emailing the payment link. Null means not claimed. Reset to null if SMTP fails.';  -- the text