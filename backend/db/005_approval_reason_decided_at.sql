-- Migration 005. Run once in the Supabase SQL editor. Safe on existing data.
-- D10 (user's decision): store the approval reason and the decision time in real columns.

-- DECISION PROBLEM (D10): where do the approval reason and the decision time live?
-- Options: (a) two real columns, (b) keys inside the payload JSON.
-- Chosen: (a). Reason: the database can sort and filter on them, and the names are visible in the schema.
-- Cost: one migration. Both columns are nullable so old rows stay valid.
alter table public.approvals  -- change the approvals table
  add column if not exists reason text;  -- why the agent asked, shown to the owner, null on old rows

alter table public.approvals  -- change the approvals table
  add column if not exists decided_at timestamptz;  -- when the owner approved or rejected, null while pending