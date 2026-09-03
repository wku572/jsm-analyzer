import streamlit as st
from chromadb.utils import embedding_functions

from utils.supabase_db import (
    save_ticket_embeddings,
    match_ticket_embeddings,
    get_ticket_embeddings_count,
)


DEFAULT_ESCALATION_LEVEL = "L1 – Support"


@st.cache_resource
def _get_embedding_function():
    return embedding_functions.DefaultEmbeddingFunction()


def _embed(texts):
    embed_fn = _get_embedding_function()
    vectors = embed_fn(texts)
    return [[float(x) for x in vector] for vector in vectors]


def tickets_from_dataframe(df):
    if df is None or df.empty:
        return []

    resolved_df = df[df.get("Status Category") == "Resolved"].copy()

    tickets = []
    for _, row in resolved_df.iterrows():
        issue_key = str(row.get("Key", "")).strip()
        if not issue_key:
            continue

        resolution_text = str(row.get("Last Comment", "")).strip()
        if not resolution_text:
            resolution_text = str(row.get("Description", "")).strip()

        escalation_level = str(row.get("Escalation Level", "")).strip()
        if not escalation_level or escalation_level.lower() == "none":
            escalation_level = DEFAULT_ESCALATION_LEVEL

        tickets.append({
            "id": issue_key,
            "summary": str(row.get("Summary", "")).strip(),
            "resolution": resolution_text,
            "escalation_level": escalation_level,
        })

    return tickets


def build_ticket_index(tickets):
    if not tickets:
        return 0

    documents = [f"{t['summary']}\nResolution: {t['resolution']}" for t in tickets]
    embeddings = _embed(documents)

    rows = [
        {
            "ticket_id": t["id"],
            "escalation_level": t["escalation_level"],
            "document": document,
            "embedding": embedding,
        }
        for t, document, embedding in zip(tickets, documents, embeddings)
    ]

    save_ticket_embeddings(rows)
    return len(rows)


def retrieve_similar_tickets(query, n_results=5):
    if not str(query).strip():
        return []

    query_embedding = _embed([query])[0]
    matches = match_ticket_embeddings(query_embedding, match_count=n_results)

    return [
        {
            "text": match["document"],
            "escalation_level": match["escalation_level"],
            "ticket_id": match["ticket_id"],
        }
        for match in matches
    ]


def get_index_stats():
    return {"count": get_ticket_embeddings_count()}
