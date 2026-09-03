# JSM Analyzer

Kifiya Jira Service Management Analytics Platform — a Streamlit app for
analyzing Jira Service Management (`KSC` project) tickets. Data is pulled
live from Jira and persisted in Supabase; a public, no-login dashboard shows
high-level KPIs, while authenticated internal users get the full analytics
suite plus GA4-baselined incident impact assessment and an AI support triage
agent.

## Features

- **Executive Overview / Executive Intelligence / Historical Intelligence** —
  KPI dashboards and trend narratives over the loaded ticket set.
- **Status & Queue Health, Aging Analysis, Assignee Workload, Organization
  Analysis, Priority Analysis, Label / Category Analysis, Issue Type
  Analysis, Resolution Time Analysis, Trend Analysis** — standard cut-by-X
  breakdowns of the ticket data.
- **Incident Impact Assessment** — a 4-step wizard (Select Ticket → Review
  Baseline → Enter Impact → Save) that estimates customer impact % against a
  GA4-derived expected-users baseline, and separately classifies each
  incident's Priority/Severity from an Impact × Urgency matrix — with an
  optional push of the computed Priority back to the real Jira ticket.
- **GA4 Activity Baseline** — per-organization daily active-user history,
  either synced live from the GA4 Data API, entered manually, or bulk
  imported from a GA4 workbook export; feeds the Incident Impact baseline.
- **Support Triage Agent** — RAG-based L1/escalation triage assistant over
  resolved `KSC` tickets, using Claude. See [below](#support-triage-agent).
- **Raw Data** — paginated, filtered ticket export (Excel).
- **Public dashboard** — a no-login operational summary shown to anyone who
  hasn't authenticated.

Every tab is role-gated (`support_admin`, `engineer_pm`, `slt_viewer`) via
`utils/auth.py`; see [Roles](#roles--permissions) below.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure secrets

Create `.streamlit/secrets.toml` (gitignored — never commit this file).
**Bare keys must come before any `[section]` header** — in TOML, everything
after a `[section]` heading belongs to that section until the next one, so a
bare key placed after an existing section silently becomes nested inside it
instead of top-level.

```toml
# Jira (read + the one write path: pushing a computed Priority back to a ticket)
JIRA_BASE_URL = "https://<your-domain>.atlassian.net"
JIRA_EMAIL = "you@yourcompany.com"
JIRA_API_TOKEN = "..."

# Claude API, used by the Support Triage Agent
ANTHROPIC_API_KEY = "sk-ant-..."

[supabase]
url = "https://<project-ref>.supabase.co"
service_role_key = "..."

# One block per app user. Roles: support_admin, engineer_pm, slt_viewer
[auth.users.<username>]
password_hash = "<bcrypt hash>"
role = "support_admin"

# GA4 Data API service account, used by the GA4 Activity Baseline live sync.
# Only required if you use "Sync from GA4" rather than manual/bulk import.
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

### 3. Set up the Supabase schema

#### Core tables

These back the base app (snapshot loading, audit logging, user roles) and
are expected to already exist before you set up any of the features below:

```sql
create table if not exists public.current_snapshot (
    id bigint generated always as identity primary key,
    data jsonb not null,
    updated_at timestamptz default now()
);

create table if not exists public.historical_snapshots (
    id bigint generated always as identity primary key,
    snapshot_timestamp timestamptz default now(),
    total_tickets integer,
    in_progress integer,
    pending integer,
    resolved integer,
    active_backlog integer,
    overdue_1_month integer,
    overdue_2_months integer,
    high_priority_open integer,
    unassigned_open integer,
    organization_summary jsonb,
    assignee_summary jsonb,
    issue_type_summary jsonb
);

create table if not exists public.user_roles (
    id bigint generated always as identity primary key,
    email text not null unique,
    role text not null,
    created_at timestamptz default now()
);

create table if not exists public.audit_logs (
    id bigint generated always as identity primary key,
    created_at timestamptz default now(),
    username text,
    role text,
    action text,
    details text
);
```

#### Feature migrations

Run the following in the Supabase SQL editor for the features added since:

```sql
-- GA4 activity baseline
create table if not exists public.ga4_activity (
    id bigint generated always as identity primary key,
    organization text not null,
    activity_date date not null,
    weekday text not null,
    hour integer,
    active_users numeric not null default 0,
    source text not null default 'GA4',
    excluded boolean not null default false,
    notes text,
    created_at timestamptz not null default now()
);
create index if not exists idx_ga4_activity_org_weekday_date
on public.ga4_activity (organization, weekday, activity_date);
create index if not exists idx_ga4_activity_excluded
on public.ga4_activity (excluded);
create unique index if not exists uq_ga4_activity_org_date_source
on public.ga4_activity (organization, activity_date, source);

-- Organization -> GA4 property ID mapping, used by "Sync from GA4"
create table if not exists public.ga4_property_map (
    organization text primary key,
    property_id text not null,
    updated_at timestamptz not null default now()
);

-- Incident impact assessments
create table if not exists public.incident_impact_assessments (
    id bigint generated always as identity primary key,
    issue_key text not null,
    summary text,
    organization text,
    priority text,
    status text,
    labels text,
    assignee text,
    reporter text,
    incident_start timestamptz,
    incident_end timestamptz,
    duration_hours numeric,
    duration_type text,
    expected_users integer,
    affected_users integer,
    impact_percentage numeric,
    suggested_severity text,
    affected_user_source text,
    remarks text,
    baseline_type text default 'Manual Phase 1',
    created_by text,
    created_at timestamptz default now(),
    impact_level text,
    urgency_level text,
    computed_priority text,
    computed_severity text,
    jira_priority_pushed boolean not null default false,
    jira_priority_pushed_at timestamptz
);

-- Support Triage Agent's ticket index (pgvector)
create extension if not exists vector;

create table if not exists public.ticket_embeddings (
    ticket_id text primary key,
    escalation_level text not null,
    document text not null,
    embedding vector(384) not null,
    updated_at timestamptz not null default now()
);

create or replace function match_ticket_embeddings (
    query_embedding vector(384),
    match_count int default 5
)
returns table (
    ticket_id text,
    escalation_level text,
    document text,
    similarity float
)
language sql stable
as $$
    select
        ticket_id,
        escalation_level,
        document,
        1 - (embedding <=> query_embedding) as similarity
    from public.ticket_embeddings
    order by embedding <=> query_embedding
    limit match_count;
$$;
```

### 4. Run the app

```bash
streamlit run app.py
```

Log in as `support_admin`, use **Load Jira Data** to fetch and cache the
initial ticket snapshot, then the rest of the tabs become usable.

## Roles & permissions

| Capability | support_admin | engineer_pm | slt_viewer |
|---|---|---|---|
| View public dashboard (no login) | ✅ | ✅ | ✅ |
| View standard analysis tabs | ✅ | ✅ | ✅ |
| Assignee Workload, Raw Data, export | ✅ | ✅ | ❌ |
| Refresh/clear Jira data | ✅ | ❌ | ❌ |
| Support Triage tab + index refresh | ✅ | ❌ | ❌ |
| Push computed Priority to Jira | ✅ | ❌ | ❌ |

See `utils/auth.py` for the exact gating functions.

## Support Triage Agent

The **Support Triage** tab (`support_admin` only) helps the L1 support team
decide whether a new ticket can be resolved at L1 or should be escalated to
L2+, using retrieval-augmented generation over resolved `KSC` tickets:

1. Resolved tickets are pulled from Jira and embedded locally (Chroma's
   bundled `all-MiniLM-L6-v2` model, no paid embedding API), then stored in
   Supabase Postgres via the `pgvector` extension (`ticket_embeddings`
   table) — same database as the rest of the app, so the index survives
   redeploys and isn't tied to one server's local disk.
2. When you paste a new ticket's description, the most similar past tickets
   are retrieved via the `match_ticket_embeddings` Postgres function (cosine
   similarity over `pgvector`).
3. The new ticket + similar past tickets are sent to Claude
   (`claude-haiku-4-5-20251001`) with a triage system prompt, which returns
   either `L1_RESOLVABLE` (with a drafted reply) or `ESCALATE` (with a
   drafted escalation summary for L2+).
4. 👍 / 👎 feedback on each triage result is logged locally to
   `data/support_triage_feedback.csv` (ticket text, decision, confidence,
   the drafted response, thumbs, timestamp, and the reviewing user's email).
   This is local-disk storage, unlike the rest of the app's Supabase-backed
   persistence — it won't survive a redeploy or be shared across multiple
   app instances. Good enough for now; revisit if this needs to be durable
   or centrally reviewable later.

### Building the ticket index

The index starts empty. As a `support_admin`, open **Support Triage** and
click **"Refresh ticket index"** — this pulls resolved `KSC` tickets via the
existing Jira integration (`jira_client.fetch_jira_issues`), embeds them
locally, and upserts them into `ticket_embeddings`. Re-run this whenever you
want the index to reflect newly-resolved tickets; there's no
scheduled/automatic rebuild.
