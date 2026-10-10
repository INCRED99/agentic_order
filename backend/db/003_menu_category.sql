-- Run once in the Supabase SQL editor if you already ran an older schema.sql.
-- Fresh installs do not need this file, the new schema.sql already has it.

alter table public.menu_items  -- change the existing menu table
  add column category text not null default 'Mains'  -- every existing dish becomes 'Mains' first
    check (char_length(category) between 1 and 40);  -- keep labels short and non-empty

update public.menu_items  -- fix the two default dishes that are not mains
  set category = case name  -- pick a label by dish name
    when 'Masala Fries' then 'Starters'  -- starter dish
    when 'Cold Coffee' then 'Drinks'  -- drink
    else category  -- everything else keeps its current label
  end;  -- end of the case expression

create or replace function public.handle_new_user()  -- replace the signup trigger function so new users get categories
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, login_email, customer_email)  -- profile row for the new user
  values (new.id, new.email, new.email);  -- both emails start equal

  with items as (  -- default menu, inserted in one statement
    insert into public.menu_items (owner_id, name, description, category, price_paise)
    values
      (new.id, 'Margherita Pizza', 'Classic cheese and tomato', 'Mains',    24900),
      (new.id, 'Paneer Burger',    'Grilled paneer patty',      'Mains',    14900),
      (new.id, 'Veg Biryani',      'Fragrant basmati rice',     'Mains',    19900),
      (new.id, 'Masala Fries',     'Spiced crispy fries',       'Starters',  9900),
      (new.id, 'Cold Coffee',      'Chilled and creamy',        'Drinks',    9000)
    returning id  -- hand the new ids to the inventory insert
  )
  insert into public.inventory (owner_id, menu_item_id, quantity)  -- stock row for each dish
  select new.id, id, 50 from items;  -- starting stock 50 for the default dishes

  return new;  -- required by Postgres for AFTER INSERT triggers
end $$;