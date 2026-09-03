# JSM Analyzer

Kifiya Jira Service Management Analytics Platform — a Streamlit app for
analyzing Jira Service Management (`KSC` project) tickets, backed by
Supabase.

## Support Triage Agent

The **Support Triage** tab (visible to `support_admin` users only) helps the
L1 support team decide whether a new ticket can be resolved at L1 or should
be escalated to L2+, using retrieval-augmented generation over resolved
`KSC` tickets:

1. Resolved tickets are pulled from Jira and embedded locally (Chroma's
   bundled `all-MiniLM-L6-v2` model, no paid embedding API), then stored in
   Supabase Postgres via the `pgvector` extension (`ticket_embeddings`
   table) — same database as the rest of the app, so the index survives
   redeploys and isn't tied to one server's local disk.
2. When you paste a new ticket's description, the most similar past tickets
   are retrieved via a `match_ticket_embeddings` Postgres function (cosine
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

### Setup

Add to `.streamlit/secrets.toml` (alongside the existing `JIRA_*` and
`[supabase]` secrets, as **top-level keys** — not nested under a `[section]`
that appears earlier in the file, since anything after a `[section]` header
in TOML belongs to that section until the next header):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Run this once in the Supabase SQL editor to enable `pgvector` and create the
ticket index table + similarity-search function:

```sql
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

Install dependencies (already in `requirements.txt`):

```bash
pip install -r requirements.txt
```

### Building the ticket index

The index starts empty. As a `support_admin`, open **Support Triage** and
click **"Refresh ticket index"** — this pulls resolved `KSC` tickets via the
existing Jira integration (`jira_client.fetch_jira_issues`), embeds them
locally, and upserts them into `ticket_embeddings`. Re-run this whenever you
want the index to reflect newly-resolved tickets; there's no
scheduled/automatic rebuild.
