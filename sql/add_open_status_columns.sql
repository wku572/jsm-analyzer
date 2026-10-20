-- Adds the new Open-status columns to historical_snapshots after Jira's
-- workflow statuses changed (Canceled/Closed/Resolved -> Resolved; In
-- Progress/Waiting for customer/support/approval -> Open).
--
-- Additive only - nothing here touches or recomputes existing rows. The
-- pre-existing columns (pending, active_backlog, overdue_1_month,
-- overdue_2_months, high_priority_open, unassigned_open) keep their true
-- historical values up to the cutover; the app writes 0 to them in every
-- row from the cutover forward instead of silently feeding them a
-- different, incompatible meaning. historical_intelligence.py reads the
-- old columns before the cutover and the new ones after.
--
-- Safe to re-run - every statement is idempotent.

alter table public.historical_snapshots
    add column if not exists open_total integer not null default 0,
    add column if not exists waiting_for_customer integer not null default 0,
    add column if not exists waiting_for_support integer not null default 0,
    add column if not exists waiting_for_approval integer not null default 0,
    add column if not exists open_overdue_1_month integer not null default 0,
    add column if not exists open_overdue_2_months integer not null default 0,
    add column if not exists open_high_priority integer not null default 0,
    add column if not exists open_unassigned integer not null default 0;
