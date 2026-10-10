-- Restaurant order system schema v2. Tenancy: owner_id + RLS.
-- v2: profiles.restaurant_slug for plus-address routing on shared inbox.
-- v2.1: menu_items.category, seeded per default dish.
-- Run in Supabase SQL editor on a fresh project, then also run db/002_unrouted_emails.sql.
-- Already ran an older version? Use db/003_menu_category.sql (and the slug ALTER at the bottom if v1).

create extension if not exists "pgcrypto";

-- ───────── profiles ─────────
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  login_email text not null,
  customer_email text,                 -- tester's default ordering email; may equal login_email; NOT unique, NOT a routing key
  restaurant_name text default 'My Restaurant',
  -- Routing label. Order address = mealdesk.orders+<slug>@gmail.com (built in backend, not stored).
  -- Random so it cannot be guessed. Regenerate to retire a leaked address.
  restaurant_slug text not null unique
    default substr(md5(random()::text), 1, 8)
    check (restaurant_slug ~ '^[a-z0-9]{8}$'),
  created_at timestamptz not null default now()
);

-- ───────── menu ─────────
create table public.menu_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  description text,
  category text not null default 'Mains'               -- free text, shown as a group label in the dashboard
    check (char_length(category) between 1 and 40),
  price_paise integer not null check (price_paise >= 0),   -- Razorpay uses paise
  is_available boolean not null default true,
  created_at timestamptz not null default now(),
  unique (owner_id, name)
);

create table public.inventory (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  menu_item_id uuid not null references public.menu_items(id) on delete cascade,
  quantity integer not null default 0 check (quantity >= 0),
  updated_at timestamptz not null default now(),
  unique (menu_item_id)
);

-- ───────── customers ─────────
create table public.customers (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  email text not null,
  name text,
  created_at timestamptz not null default now(),
  unique (owner_id, email)
);

-- ───────── emails (idempotency on Gmail message id) ─────────
create table public.emails (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  gmail_message_id text not null,
  gmail_thread_id text,
  direction text not null check (direction in ('inbound','outbound')),
  from_email text,
  to_email text,
  subject text,
  body text,                           -- untrusted content
  status text not null default 'received'
    check (status in ('received','processing','processed','failed')),
  created_at timestamptz not null default now(),
  unique (owner_id, gmail_message_id)
);

-- ───────── orders ─────────
create table public.orders (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  customer_id uuid not null references public.customers(id),
  source_email_id uuid references public.emails(id),
  status text not null default 'PENDING'
    check (status in ('PENDING','PAID','CANCELLED','REFUNDED')),
  total_paise integer not null default 0 check (total_paise >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  order_id uuid not null references public.orders(id) on delete cascade,
  menu_item_id uuid not null references public.menu_items(id),
  quantity integer not null check (quantity > 0),
  unit_price_paise integer not null check (unit_price_paise >= 0)  -- snapshot price
);

-- ───────── payments ─────────
create table public.payments (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  order_id uuid not null references public.orders(id) on delete cascade,
  razorpay_payment_link_id text,
  razorpay_payment_id text unique,     -- webhook idempotency
  amount_paise integer not null,
  status text not null default 'CREATED'
    check (status in ('CREATED','PAID','FAILED','REFUNDED')),
  created_at timestamptz not null default now()
);

-- ───────── agent logs + approvals ─────────
create table public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  email_id uuid references public.emails(id),
  tool_calls jsonb not null default '[]',
  final_output text,
  status text not null default 'running'
    check (status in ('running','done','failed','awaiting_approval')),
  created_at timestamptz not null default now()
);

create table public.approvals (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  agent_run_id uuid references public.agent_runs(id) on delete cascade,
  action text not null,                -- e.g. cancel_order, refund
  payload jsonb not null default '{}',
  status text not null default 'pending'
    check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now()
);

-- ───────── indexes ─────────
create index on public.menu_items (owner_id);
create index on public.orders (owner_id, status, created_at desc);
create index on public.order_items (order_id);
create index on public.emails (owner_id, status);
create index on public.payments (order_id);
create index on public.agent_runs (owner_id, created_at desc);
create index on public.approvals (owner_id, status);

-- ───────── RLS: each user sees only own rows ─────────
alter table public.profiles enable row level security;
create policy "own profile" on public.profiles
  for all using (id = auth.uid()) with check (id = auth.uid());

do $$
declare t text;
begin
  foreach t in array array[
    'menu_items','inventory','customers','emails','orders',
    'order_items','payments','agent_runs','approvals'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy "owner access" on public.%I for all
       using (owner_id = auth.uid()) with check (owner_id = auth.uid())', t);
  end loop;
end $$;

-- ───────── signup trigger: profile + default menu ─────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, login_email, customer_email)
  values (new.id, new.email, new.email);

  with items as (
    insert into public.menu_items (owner_id, name, description, category, price_paise)
    values
      (new.id, 'Margherita Pizza', 'Classic cheese and tomato', 'Mains',    24900),
      (new.id, 'Paneer Burger',    'Grilled paneer patty',      'Mains',    14900),
      (new.id, 'Veg Biryani',      'Fragrant basmati rice',     'Mains',    19900),
      (new.id, 'Masala Fries',     'Spiced crispy fries',       'Starters',  9900),
      (new.id, 'Cold Coffee',      'Chilled and creamy',        'Drinks',    9000)
    returning id
  )
  insert into public.inventory (owner_id, menu_item_id, quantity)
  select new.id, id, 50 from items;

  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ───────── MIGRATION: only if v1 already ran ─────────
-- Do NOT run this on a fresh v2 install (column already exists).
-- Volatile default is evaluated per row, so existing users each get a different slug.
--
-- alter table public.profiles
--   add column restaurant_slug text not null unique
--   default substr(md5(random()::text), 1, 8)
--   check (restaurant_slug ~ '^[a-z0-9]{8}$');