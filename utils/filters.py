import streamlit as st


def apply_filters(df):

    with st.expander("🎛️ Filters & Search", expanded=False):

        search_text = st.text_input(
            "Search tickets",
            placeholder="🔍 Search by key, summary, assignee, reporter, organization...",
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            selected_status = st.multiselect(
                "Status",
                ["In Progress", "Pending", "Resolved"],
                default=["In Progress", "Pending", "Resolved"]
            )

        with c2:
            selected_priority = st.multiselect(
                "Priority",
                sorted(df["Priority"].dropna().unique()),
                default=list(sorted(df["Priority"].dropna().unique()))
            )

        with c3:
            selected_assignee = st.multiselect(
                "Assignee",
                sorted(df["Assignee"].dropna().unique()),
                default=list(sorted(df["Assignee"].dropna().unique()))
            )

        with c4:
            selected_org = st.multiselect(
                "Organization",
                sorted(df["Organizations"].dropna().unique()),
                default=list(sorted(df["Organizations"].dropna().unique()))
            )

    filtered_df = df.copy()

    if selected_status:
        filtered_df = filtered_df[filtered_df["Status Category"].isin(selected_status)]

    if selected_priority:
        filtered_df = filtered_df[filtered_df["Priority"].isin(selected_priority)]

    if selected_assignee:
        filtered_df = filtered_df[filtered_df["Assignee"].isin(selected_assignee)]

    if selected_org:
        filtered_df = filtered_df[filtered_df["Organizations"].isin(selected_org)]

    if search_text.strip():
        search_text = search_text.lower().strip()

        searchable_columns = [
            "Key", "Summary", "Assignee", "Reporter",
            "Priority", "Status", "Status Category", "Organizations"
        ]

        mask = False

        for col in searchable_columns:
            if col in filtered_df.columns:
                mask = mask | filtered_df[col].astype(str).str.lower().str.contains(search_text, na=False)

        filtered_df = filtered_df[mask]

    return filtered_df