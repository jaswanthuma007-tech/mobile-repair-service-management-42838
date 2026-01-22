# Supabase schema + RLS fix for Customer Booking flow

This repo’s frontend/backend expect the `repairs` table to use:

- `device_type` (TEXT NOT NULL)
- `issue_description` (TEXT NOT NULL)
- `customer_user_id` (UUID NOT NULL) with RLS owner check: `customer_user_id = auth.uid()`

Your current error:

> null value in column "issue" of relation "repairs" violates not-null constraint

means the database still has an old NOT NULL column (`issue`) that the app no longer writes to.

---

## 1) Apply schema changes (run in Supabase SQL editor)

> Run each statement one-by-one if your environment prefers it.

### 1.1 Add/ensure new columns exist and are NOT NULL

```sql
alter table public.repairs
  add column if not exists device_type text;

alter table public.repairs
  add column if not exists issue_description text;
```

If you already have old columns like `device` or `issue`, backfill the new columns before enforcing NOT NULL:

```sql
update public.repairs
set device_type = coalesce(device_type, device)
where device_type is null;

update public.repairs
set issue_description = coalesce(issue_description, issue)
where issue_description is null;
```

Now enforce NOT NULL:

```sql
alter table public.repairs
  alter column device_type set not null;

alter table public.repairs
  alter column issue_description set not null;
```

### 1.2 Remove (or relax) the old `issue` column constraint

Preferred: drop the legacy column (only if you’re sure nothing else uses it):

```sql
alter table public.repairs
  drop column if exists issue;
```

Alternative: if you cannot drop it yet, at minimum remove NOT NULL so inserts don’t fail:

```sql
alter table public.repairs
  alter column issue drop not null;
```

---

## 2) Fix RLS policies (customer_user_id = auth.uid())

Enable RLS:

```sql
alter table public.repairs enable row level security;
```

Drop old policies if they exist (names may differ; adjust as needed):

```sql
drop policy if exists "Customers can insert own repairs" on public.repairs;
drop policy if exists "Customers can view own repairs" on public.repairs;
drop policy if exists "Customers can update own repairs" on public.repairs;
```

Create policies:

```sql
create policy "Customers can insert own repairs"
on public.repairs
for insert
to authenticated
with check (customer_user_id = auth.uid());
```

```sql
create policy "Customers can view own repairs"
on public.repairs
for select
to authenticated
using (customer_user_id = auth.uid());
```

Optional (only if you want customers to edit their booking fields):

```sql
create policy "Customers can update own repairs"
on public.repairs
for update
to authenticated
using (customer_user_id = auth.uid())
with check (customer_user_id = auth.uid());
```

---

## 3) Reload PostgREST schema cache (required)

```sql
notify pgrst, 'reload schema';
```

---

## 4) Verification checklist

1. Login as customer
2. Create booking (Book Repair page or Customer dashboard)
3. Confirm row exists in `public.repairs`:
   - `customer_user_id` == your auth user id
   - `device_type` is non-empty
   - `issue_description` is non-empty
4. “Your Repairs” list loads without errors
5. Realtime updates still arrive (status changes propagate)

If you still see insert errors after schema change:
- Confirm the insert payload uses `device_type` + `issue_description` only
- Confirm RLS insert policy uses **WITH CHECK (customer_user_id = auth.uid())**
- Confirm PostgREST schema reload was executed
