-- Enable Row Level Security across every table this app touches, so
-- access is enforced by Postgres itself and not solely by the Streamlit
-- app's own role checks (which is all that stood between any bug there
-- and the whole database, since every DB client used to authenticate
-- with the service_role key, which bypasses RLS entirely).
--
-- Run this whole file once in the Supabase SQL editor. It's idempotent -
-- safe to re-run. It has zero effect on the currently-deployed app until
-- the app's Supabase client also switches from the service_role key to
-- the anon key (see utils/db_client.py) - until then the app still
-- authenticates as service_role, which bypasses RLS, so this migration
-- can be applied ahead of that code deploy with no risk of an outage.
--
-- Roles referenced below come from public.user_roles.role and mirror the
-- checks in utils/auth.py: support_admin, admin, engineer_pm, slt_viewer.


-- ---------------------------------------------------------------------------
-- Helper functions
-- ---------------------------------------------------------------------------

-- Resolves the calling user's app role from user_roles, keyed by the email
-- claim on their Supabase Auth JWT. security definer so it can read
-- user_roles even under that table's own restrictive RLS policy below.
create or replace function public.current_app_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.user_roles where email = auth.jwt() ->> 'email'
$$;

create or replace function public.has_role(roles text[])
returns boolean
language sql
stable
as $$
  select coalesce(public.current_app_role() = any(roles), false)
$$;


-- ---------------------------------------------------------------------------
-- user_roles - each user may read only their own role row. No app code
-- ever writes to this table (roles are managed by hand in the console),
-- so there is deliberately no insert/update/delete policy for anon or
-- authenticated - only the service_role (or the console) can change it.
-- ---------------------------------------------------------------------------

alter table public.user_roles enable row level security;
grant select on public.user_roles to authenticated;

drop policy if exists user_roles_select_own on public.user_roles;
create policy user_roles_select_own
on public.user_roles for select
to authenticated
using (email = auth.jwt() ->> 'email');


-- ---------------------------------------------------------------------------
-- audit_logs - written before login succeeds (LOGIN_FAILED) as well as
-- after, so anon needs a narrow insert/select allowance limited to
-- LOGIN_FAILED rows (used by the login rate limiter). Authenticated users
-- may only insert rows under their own identity - never on someone
-- else's behalf. Only support_admin/admin can browse the full log.
-- ---------------------------------------------------------------------------

alter table public.audit_logs enable row level security;
grant select, insert on public.audit_logs to anon;
grant select, insert on public.audit_logs to authenticated;

drop policy if exists audit_logs_insert_login_failed_anon on public.audit_logs;
create policy audit_logs_insert_login_failed_anon
on public.audit_logs for insert
to anon
with check (action = 'LOGIN_FAILED');

drop policy if exists audit_logs_select_login_failed_anon on public.audit_logs;
create policy audit_logs_select_login_failed_anon
on public.audit_logs for select
to anon
using (action = 'LOGIN_FAILED');

drop policy if exists audit_logs_insert_own on public.audit_logs;
create policy audit_logs_insert_own
on public.audit_logs for insert
to authenticated
with check (username = auth.jwt() ->> 'email');

drop policy if exists audit_logs_select_admin on public.audit_logs;
create policy audit_logs_select_admin
on public.audit_logs for select
to authenticated
using (public.has_role(array['support_admin', 'admin']));


-- ---------------------------------------------------------------------------
-- current_snapshot - backs the public dashboard, so it is intentionally
-- readable by anon. Only support_admin/admin may refresh/clear it.
-- ---------------------------------------------------------------------------

alter table public.current_snapshot enable row level security;
grant select on public.current_snapshot to anon;
grant select, insert, update, delete on public.current_snapshot to authenticated;

drop policy if exists current_snapshot_select_all on public.current_snapshot;
create policy current_snapshot_select_all
on public.current_snapshot for select
to anon, authenticated
using (true);

drop policy if exists current_snapshot_write_admin on public.current_snapshot;
create policy current_snapshot_write_admin
on public.current_snapshot for insert
to authenticated
with check (public.has_role(array['support_admin', 'admin']));

drop policy if exists current_snapshot_update_admin on public.current_snapshot;
create policy current_snapshot_update_admin
on public.current_snapshot for update
to authenticated
using (public.has_role(array['support_admin', 'admin']))
with check (public.has_role(array['support_admin', 'admin']));

drop policy if exists current_snapshot_delete_admin on public.current_snapshot;
create policy current_snapshot_delete_admin
on public.current_snapshot for delete
to authenticated
using (public.has_role(array['support_admin', 'admin']));


-- ---------------------------------------------------------------------------
-- historical_snapshots - viewable by any logged-in user; only
-- support_admin/admin write it (alongside a Jira refresh).
-- ---------------------------------------------------------------------------

alter table public.historical_snapshots enable row level security;
grant select, insert on public.historical_snapshots to authenticated;

drop policy if exists historical_snapshots_select_authenticated on public.historical_snapshots;
create policy historical_snapshots_select_authenticated
on public.historical_snapshots for select
to authenticated
using (true);

drop policy if exists historical_snapshots_insert_admin on public.historical_snapshots;
create policy historical_snapshots_insert_admin
on public.historical_snapshots for insert
to authenticated
with check (public.has_role(array['support_admin', 'admin']));


-- ---------------------------------------------------------------------------
-- incident_impact_assessments - the whole feature (view and write) is
-- restricted to the support_admin role only, matching
-- can_manage_incidents() in utils/auth.py.
-- ---------------------------------------------------------------------------

alter table public.incident_impact_assessments enable row level security;
grant select, insert, update, delete on public.incident_impact_assessments to authenticated;

drop policy if exists incident_impact_select_authenticated on public.incident_impact_assessments;
drop policy if exists incident_impact_select_support_admin on public.incident_impact_assessments;
create policy incident_impact_select_support_admin
on public.incident_impact_assessments for select
to authenticated
using (public.has_role(array['support_admin']));

drop policy if exists incident_impact_insert_managers on public.incident_impact_assessments;
create policy incident_impact_insert_managers
on public.incident_impact_assessments for insert
to authenticated
with check (public.has_role(array['support_admin']));

drop policy if exists incident_impact_update_managers on public.incident_impact_assessments;
create policy incident_impact_update_managers
on public.incident_impact_assessments for update
to authenticated
using (public.has_role(array['support_admin']))
with check (public.has_role(array['support_admin']));

drop policy if exists incident_impact_delete_managers on public.incident_impact_assessments;
create policy incident_impact_delete_managers
on public.incident_impact_assessments for delete
to authenticated
using (public.has_role(array['support_admin']));


-- ---------------------------------------------------------------------------
-- ga4_activity - same shape as incident_impact_assessments, restricted to
-- support_admin only. Writes use upsert, so the update policy needs a
-- matching with check for the ON CONFLICT DO UPDATE path.
-- ---------------------------------------------------------------------------

alter table public.ga4_activity enable row level security;
grant select, insert, update, delete on public.ga4_activity to authenticated;

drop policy if exists ga4_activity_select_authenticated on public.ga4_activity;
drop policy if exists ga4_activity_select_support_admin on public.ga4_activity;
create policy ga4_activity_select_support_admin
on public.ga4_activity for select
to authenticated
using (public.has_role(array['support_admin']));

drop policy if exists ga4_activity_insert_managers on public.ga4_activity;
create policy ga4_activity_insert_managers
on public.ga4_activity for insert
to authenticated
with check (public.has_role(array['support_admin']));

drop policy if exists ga4_activity_update_managers on public.ga4_activity;
create policy ga4_activity_update_managers
on public.ga4_activity for update
to authenticated
using (public.has_role(array['support_admin']))
with check (public.has_role(array['support_admin']));

drop policy if exists ga4_activity_delete_managers on public.ga4_activity;
create policy ga4_activity_delete_managers
on public.ga4_activity for delete
to authenticated
using (public.has_role(array['support_admin']));


-- ---------------------------------------------------------------------------
-- ga4_property_map - also upserted (on_conflict on organization), also
-- restricted to support_admin only.
-- ---------------------------------------------------------------------------

alter table public.ga4_property_map enable row level security;
grant select, insert, update, delete on public.ga4_property_map to authenticated;

drop policy if exists ga4_map_select_authenticated on public.ga4_property_map;
drop policy if exists ga4_map_select_support_admin on public.ga4_property_map;
create policy ga4_map_select_support_admin
on public.ga4_property_map for select
to authenticated
using (public.has_role(array['support_admin']));

drop policy if exists ga4_map_insert_managers on public.ga4_property_map;
create policy ga4_map_insert_managers
on public.ga4_property_map for insert
to authenticated
with check (public.has_role(array['support_admin']));

drop policy if exists ga4_map_update_managers on public.ga4_property_map;
create policy ga4_map_update_managers
on public.ga4_property_map for update
to authenticated
using (public.has_role(array['support_admin']))
with check (public.has_role(array['support_admin']));

drop policy if exists ga4_map_delete_managers on public.ga4_property_map;
create policy ga4_map_delete_managers
on public.ga4_property_map for delete
to authenticated
using (public.has_role(array['support_admin']));


-- ---------------------------------------------------------------------------
-- ticket_embeddings - backs the Support Triage RAG index, which the app
-- restricts entirely to support_admin/admin (is_support_admin()).
-- ---------------------------------------------------------------------------

alter table public.ticket_embeddings enable row level security;
grant select, insert, update, delete on public.ticket_embeddings to authenticated;

drop policy if exists ticket_embeddings_all_support_admin on public.ticket_embeddings;
create policy ticket_embeddings_all_support_admin
on public.ticket_embeddings for all
to authenticated
using (public.has_role(array['support_admin', 'admin']))
with check (public.has_role(array['support_admin', 'admin']));
