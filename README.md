# JSM Analyzer

JSM Analyzer is a cloud-based operational intelligence platform for Jira Service Management (JSM).

It provides real-time operational dashboards, executive insights, historical analytics, workload monitoring, queue health analysis, and ticket intelligence.

---

## Features

- Real-time Jira analytics
- Executive operational dashboards
- Historical intelligence
- Queue health monitoring
- Aging & backlog analysis
- Assignee workload tracking
- Organization-level insights
- Resolution time analytics
- Role-based authentication
- Excel export
- Cloud deployment support

---

## Architecture

```text
Jira API
   ↓
Streamlit Cloud
   ↓
Supabase Database
   ↓
Operational Dashboards
```

---

## Tech Stack

- Streamlit
- Python
- Plotly
- Pandas
- Supabase PostgreSQL
- Jira REST API
- Docker

---

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Deployment

- GitHub
- Streamlit Community Cloud
- Supabase

---

## User Roles

| Role | Access |
|---|---|
| Support Admin | Full access |
| Engineer / PM | Operational analytics |
| SLT Viewer | Executive dashboards |

---

## Author

SIntayehu Feleke (Santa)

Operational Intelligence Platform for Jira Service Management.
