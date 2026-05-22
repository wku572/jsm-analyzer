import streamlit as st


JIRA_BASE_URL = "https://kifiyaprod.atlassian.net/browse/"


def render(filtered_df):

    st.subheader("📄 Raw Ticket Data")

    preferred_columns = [
        "Issue Type", "Key", "Summary", "Assignee", "Reporter",
        "Priority", "Status", "Status Category", "Resolution", "Resolved Date",
        "Created", "Updated", "Due date", "Organizations",
        "Year", "Month", "Ticket Age",
        "Ticket Age Duration", "Overdue"
    ]

    available_columns = [
        col for col in preferred_columns
        if col in filtered_df.columns
    ]

    data = filtered_df[available_columns].copy()

    data.insert(
        loc=data.columns.get_loc("Key") + 1,
        column="Ticket Link",
        value=data["Key"].apply(lambda key: f"{JIRA_BASE_URL}{key}")
    )

    total_rows = len(data)

    col1, col2, col3 = st.columns(3)

    with col1:
        page_size = st.selectbox(
            "Rows per page",
            [10, 25, 50, 100, 200],
            index=2
        )

    total_pages = max((total_rows - 1) // page_size + 1, 1)

    with col2:
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1
        )

    with col3:
        st.metric("Total Rows", total_rows)

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size

    st.caption(
        f"Showing rows {start_idx + 1} to {min(end_idx, total_rows)} of {total_rows}"
    )

    st.dataframe(
        data.iloc[start_idx:end_idx],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ticket Link": st.column_config.LinkColumn(
                "Open Ticket",
                display_text="Open"
            )
        }
    )