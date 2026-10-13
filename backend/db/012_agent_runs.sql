-- Migration 012: agent_runs, one row per agent run on a mail (D51, option a). Run once in the Supabase SQL editor.

-- DECISION PROBLEM (D51, chosen by the user): where does the run log live for the Agent Activity page?
-- Options: (a) a new table agent_runs, (b) extra columns on emails, (c) a log file only.
-- Chosen: a. Reason: the page reads real data, and evals can use the same rows later.
-- Cost: one more table. steps is jsonb, so its shape is checked in Python, not by the database.
-- PRIVACY RULE: steps holds tool names and short results only. Never store mail bodies or subjects here (same rule as worker.py logs).

-- STEP 0. An older agent_runs table (from the first schema, columns tool_calls and final_output) already exists and is empty.
-- This block drops it ONLY when it has the old shape AND no rows. A new-shape table is never touched, so re-running this file is safe.
do $$  -- run a small block of procedural code
begin  -- start of the block
  if exists (  -- is the table the OLD shape?
    select 1 from information_schema.columns  -- look at the column list
    where table_schema = 'public' and table_name = 'agent_runs' and column_name = 'tool_calls'  -- only the old table has tool_calls
  ) then  -- old shape found
    if exists (select 1 from public.agent_runs) then  -- old rows would be lost
      raise exception 'old agent_runs has rows, migrate them by hand first';  -- stop, never delete data silently
    end if;  -- end of the row check
    alter table public.approvals drop constraint if exists approvals_agent_run_id_fkey;  -- approvals.agent_run_id pointed at the old table. The old table is empty, so every agent_run_id is null and no link is lost. Re-added at the bottom.
    drop table public.agent_runs;  -- empty and old, safe to drop. No cascade on purpose: if something ELSE depends on it, this errors and nothing is lost
  end if;  -- end of the shape check
end;  -- end of the block
$$;  -- end of the block

create table if not exists public.agent_runs (  -- create the table only if it does not exist yet
  id uuid primary key default gen_random_uuid(),  -- run id
  owner_id uuid not null references public.profiles(id) on delete cascade,  -- restaurant that owns the run, same pattern as emails
  email_id uuid not null references public.emails(id) on delete cascade,  -- the mail this run worked on
  order_id uuid references public.orders(id) on delete set null,  -- the order the run created, null when none was created
  status text not null default 'RUNNING'  -- where the run is now
    check (status in ('RUNNING', 'SUCCESS', 'WAITING_APPROVAL', 'FAILED')),  -- RUNNING is new, the other three match the UI type AgentRunStatus
  model_calls integer not null default 0 check (model_calls >= 0),  -- how many LLM calls the run used (ModelCallLimit watches this)
  tokens integer not null default 0 check (tokens >= 0),  -- total tokens used, for the cost view
  steps jsonb not null default '[]'::jsonb  -- list of {tool, summary, ok}, matches the UI type AgentStep
    check (jsonb_typeof(steps) = 'array'),  -- must be a list
  error text,  -- short failure reason, null when fine. No mail text here.
  started_at timestamptz not null default now(),  -- when the run began
  finished_at timestamptz  -- when it ended, null while RUNNING
);

create index if not exists agent_runs_owner_started_idx  -- speeds up the dashboard list
  on public.agent_runs (owner_id, started_at desc);  -- newest first per restaurant

create index if not exists agent_runs_email_idx  -- speeds up "runs for this mail" and retries
  on public.agent_runs (email_id);  -- lookup by mail

alter table public.agent_runs enable row level security;  -- same as every other table: RLS on

-- DECISION PROBLEM (small, assumed): what happens to an approval when its agent run row is deleted?
-- Options: (1) set approvals.agent_run_id to null, (2) delete the approval too, (3) block the delete.
-- Chosen: 1. Reason: an owner decision must outlive the run log. Cost: the link from approval to run is lost after a delete.
alter table public.approvals drop constraint if exists approvals_agent_run_id_fkey;  -- so the file can be run again
alter table public.approvals  -- put the link back, now pointing at the new table
  add constraint approvals_agent_run_id_fkey  -- same name as before
  foreign key (agent_run_id) references public.agent_runs(id) on delete set null;  -- see the decision above

drop policy if exists "owner access" on public.agent_runs;  -- so the file can be run again without a "policy already exists" error

create policy "owner access"  -- same pattern as emails: owner_id = auth.uid()
  on public.agent_runs  -- this table
  for all  -- select, insert, update, delete
  using (owner_id = auth.uid());  -- a logged-in user sees only their own rows. The backend uses the service role and filters by owner_id itself.