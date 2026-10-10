-- Run once in the Supabase SQL editor, after schema.sql v2.
-- Stores inbox mail that belongs to no restaurant, so it is never handled or answered twice.

create table public.unrouted_emails (  -- new table, no owner because no restaurant matched
  message_id text primary key,  -- the Message-ID header; the primary key blocks duplicate handling
  from_email text,  -- sender address, used for the once-per-day reply limit
  subject text,  -- trimmed subject, for debugging only
  reason text not null  -- why it was not routed
    check (reason in ('no_slug', 'unknown_slug', 'own_address')),  -- the only allowed reasons
  replied boolean not null default false,  -- true when we sent an "unknown address" reply
  created_at timestamptz not null default now()  -- when we first saw it, used for 24-hour limits
);

create index on public.unrouted_emails (from_email, created_at desc);  -- speeds up the per-sender limit check

alter table public.unrouted_emails enable row level security;  -- turn RLS on
-- No policy on purpose: with RLS on and no policy, browser users see nothing.
-- The backend uses the service role, which bypasses RLS, so it can still read and write.