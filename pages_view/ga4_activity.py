import io
import pandas as pd
import streamlit as st

from utils.supabase_db import (
    save_ga4_activity_records,
    load_ga4_activity_records,
    calculate_ga4_weekday_baseline,
    load_ga4_property_map,
    save_ga4_property_mapping,
    delete_ga4_property_mapping,
)
from utils.ga4_client import fetch_ga4_daily_active_users


WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _to_ga4_records(df):
    if df is None or df.empty:
        return []

    working = df.copy()
    working.columns = [str(col).strip().lower().replace(" ", "_") for col in working.columns]

    required = [
        "organization",
        "activity_date",
        "weekday",
        "active_users",
    ]

    for col in required:
        if col not in working.columns:
            working[col] = ""

    if "source" not in working.columns:
        working["source"] = "GA4"
    if "hour" not in working.columns:
        working["hour"] = pd.NA
    if "excluded" not in working.columns:
        working["excluded"] = False
    if "notes" not in working.columns:
        working["notes"] = ""

    return working[
        ["organization", "activity_date", "weekday", "hour", "active_users", "source", "excluded", "notes"]
    ].to_dict(orient="records")


def _parse_ga4_report_workbook(uploaded_file, organization):
    raw_df = pd.read_excel(uploaded_file, header=None)

    if raw_df.empty:
        return []

    raw_df = raw_df.fillna("")

    start_date = None
    end_date = None
    header_row_idx = None

    for idx, row in raw_df.iterrows():
        first_cell = str(row.iloc[0]).strip()
        if first_cell.startswith("# Start date:"):
            start_text = first_cell.split(":", 1)[1].strip()
            start_date = pd.to_datetime(start_text, format="%Y%m%d", errors="coerce")
        elif first_cell.startswith("# End date:"):
            end_text = first_cell.split(":", 1)[1].strip()
            end_date = pd.to_datetime(end_text, format="%Y%m%d", errors="coerce")
        elif first_cell == "Nth day":
            header_row_idx = idx

    if header_row_idx is None or start_date is None:
        return []

    data_rows = raw_df.iloc[header_row_idx + 1 :].copy()
    data_rows.columns = ["nth_day", "active_30d", "active_7d", "active_1d"]

    records = []
    for _, row in data_rows.iterrows():
        nth_day_raw = str(row["nth_day"]).strip()
        if not nth_day_raw:
            continue

        try:
            offset = int(nth_day_raw)
        except ValueError:
            continue

        activity_date = (start_date + pd.Timedelta(days=offset)).date()
        active_users = pd.to_numeric(row["active_1d"], errors="coerce")
        if pd.isna(active_users):
            continue

        seven_day = pd.to_numeric(row["active_7d"], errors="coerce")
        thirty_day = pd.to_numeric(row["active_30d"], errors="coerce")

        notes = []
        if pd.notna(seven_day):
            notes.append(f"7d={int(seven_day)}")
        if pd.notna(thirty_day):
            notes.append(f"30d={int(thirty_day)}")
        if pd.notna(end_date):
            notes.append(f"report_end={end_date.date().isoformat()}")

        records.append({
            "organization": organization,
            "activity_date": activity_date.isoformat(),
            "weekday": activity_date.strftime("%A"),
            "hour": pd.NA,
            "active_users": float(active_users),
            "source": "GA4 Workbook",
            "excluded": False,
            "notes": " | ".join(notes),
        })

    return records


def _records_to_preview_df(records):
    if not records:
        return pd.DataFrame()

    preview_df = pd.DataFrame(records).copy()

    if "activity_date" in preview_df.columns:
        preview_df["activity_date"] = pd.to_datetime(preview_df["activity_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return preview_df


def _organizations_from_filtered_df(filtered_df):
    if filtered_df is None or filtered_df.empty or "Organizations" not in filtered_df.columns:
        return []

    values = (
        filtered_df["Organizations"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    values = values[values.ne("")]

    return sorted(values.unique().tolist())


def _render_live_sync_tab(organizations):
    st.subheader("Property Mappings")
    st.caption("Each organization syncs from its own GA4 property.")

    property_map = load_ga4_property_map()

    if property_map:
        mapping_df = pd.DataFrame(
            [
                {"Organization": org, "GA4 Property ID": property_id}
                for org, property_id in sorted(property_map.items())
            ]
        )
        st.dataframe(mapping_df, width="stretch", hide_index=True)
    else:
        st.info("No organizations are mapped to a GA4 property yet. Add one below.")

    with st.expander("Add / Update Mapping", expanded=not property_map):
        with st.form("ga4_property_mapping_form", clear_on_submit=True):
            if organizations:
                mapping_org = st.selectbox(
                    "Organization",
                    organizations,
                    key="ga4_mapping_org_select"
                )
            else:
                mapping_org = st.text_input(
                    "Organization",
                    key="ga4_mapping_org_text"
                )

            mapping_property_id = st.text_input(
                "GA4 Property ID",
                placeholder="e.g. 123456789"
            )

            mapping_submitted = st.form_submit_button("Save Mapping")

        if mapping_submitted:
            if not str(mapping_org).strip() or not mapping_property_id.strip():
                st.warning("Both organization and property ID are required.")
            else:
                try:
                    save_ga4_property_mapping(mapping_org, mapping_property_id)
                    st.success(f"Mapped {mapping_org} to GA4 property {mapping_property_id}.")
                    st.rerun()
                except RuntimeError as exc:
                    st.warning(str(exc))
                except Exception as exc:
                    st.error("Failed to save the property mapping.")
                    st.exception(exc)

    if property_map:
        with st.expander("Remove a Mapping"):
            remove_org = st.selectbox(
                "Organization to unmap",
                sorted(property_map.keys()),
                key="ga4_remove_mapping_org"
            )

            if st.button("Remove Mapping", key="ga4_remove_mapping_button"):
                try:
                    delete_ga4_property_mapping(remove_org)
                    st.success(f"Removed the GA4 mapping for {remove_org}.")
                    st.rerun()
                except Exception as exc:
                    st.error("Failed to remove the property mapping.")
                    st.exception(exc)

    st.divider()
    st.subheader("Sync from GA4")
    st.caption("Pulls the last 90 days of daily active users directly from GA4 and upserts them into GA4 activity.")

    if not property_map:
        st.info("Map at least one organization to a GA4 property above to enable syncing.")
        return

    sync_org = st.selectbox(
        "Organization to sync",
        sorted(property_map.keys()),
        key="ga4_sync_org"
    )

    if st.button("Sync from GA4", type="primary", key="ga4_sync_button"):
        try:
            property_id = property_map[sync_org]
            rows = fetch_ga4_daily_active_users(property_id)

            if not rows:
                st.info(f"GA4 returned no activity rows for {sync_org} in the last 90 days.")
            else:
                synced_at = pd.Timestamp.now(tz="UTC").isoformat()
                records = []

                for row in rows:
                    activity_date = row["activity_date"]
                    records.append({
                        "organization": sync_org,
                        "activity_date": activity_date.isoformat(),
                        "weekday": activity_date.strftime("%A"),
                        "hour": pd.NA,
                        "active_users": row["active_users"],
                        "source": "GA4 API",
                        "excluded": False,
                        "notes": f"Synced from GA4 property {property_id} at {synced_at}",
                    })

                save_ga4_activity_records(records)
                st.success(f"Synced {len(records)} days of GA4 activity for {sync_org}.")
                st.rerun()
        except RuntimeError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error("Failed to sync GA4 data.")
            st.exception(exc)


def _render_manual_entry_tab():
    st.subheader("Add Activity")
    with st.form("ga4_manual_entry", clear_on_submit=True):
        organization = st.text_input("Organization")
        activity_date = st.date_input("Activity Date")
        weekday = st.selectbox(
            "Weekday",
            WEEKDAYS,
            index=pd.Timestamp(activity_date).weekday(),
        )
        hour = st.number_input("Hour of Day", min_value=0, max_value=23, value=0, step=1)
        active_users = st.number_input("Active Users", min_value=0.0, step=1.0, value=0.0)
        source = st.text_input("Source", value="GA4")
        excluded = st.checkbox("Exclude from baseline", value=False)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Activity")

    if submitted:
        if not organization.strip():
            st.warning("Organization is required.")
        else:
            try:
                save_ga4_activity_records(
                    [{
                        "organization": organization.strip(),
                        "activity_date": activity_date.isoformat(),
                        "weekday": weekday,
                        "hour": hour,
                        "active_users": active_users,
                        "source": source.strip() or "GA4",
                        "excluded": excluded,
                        "notes": notes,
                    }]
                )
                st.success("GA4 activity saved successfully.")
                st.rerun()
            except RuntimeError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error("Failed to save GA4 activity.")
                st.exception(exc)


def _render_bulk_import_tab():
    st.subheader("Bulk Import")
    upload_org = st.text_input(
        "Organization for uploaded file",
        placeholder="e.g. Coop Bank / Wegagen Bank ...",
        key="ga4_upload_org"
    )
    upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

    if upload is not None:
        try:
            file_name = upload.name.lower()
            records = []
            if file_name.endswith((".xlsx", ".xls")):
                if not upload_org.strip():
                    st.warning("Please enter the organization name for this GA4 workbook before importing.")
                else:
                    records = _parse_ga4_report_workbook(upload, upload_org.strip())
            else:
                imported = pd.read_csv(upload)
                records = _to_ga4_records(imported)
                if upload_org.strip() and records:
                    for record in records:
                        record["organization"] = upload_org.strip()

            if records:
                st.caption(f"Parsed rows: {len(records)}")
                preview_df = _records_to_preview_df(records)
                st.dataframe(preview_df.head(5), width="stretch", hide_index=True)

                if st.button("Import Parsed Rows", type="primary", key="ga4_import_parsed_rows"):
                    try:
                        save_ga4_activity_records(records)
                        st.success(f"Imported {len(records)} GA4 rows.")
                        st.rerun()
                    except RuntimeError as exc:
                        st.warning(str(exc))
                    except Exception as exc:
                        st.error("Failed to import GA4 CSV.")
                        st.exception(exc)
            else:
                st.warning("The uploaded file did not contain any usable rows.")
        except Exception as exc:
            st.error("Failed to import GA4 CSV.")
            st.exception(exc)

    activity_df = load_ga4_activity_records()

    if activity_df is not None and not activity_df.empty:
        st.caption(
            f"Stored rows: {len(activity_df)} | Organizations: {activity_df['organization'].nunique()}"
        )
    else:
        st.caption("No GA4 activity table data is available yet. Create the table or add records to enable baseline previews.")


def render(filtered_df=None):
    st.title("GA4 Activity Baseline")

    st.info(
        "Phase 2 stores historical GA4 activity so the Incident Impact page can recommend a same-weekday baseline for single-day incidents."
    )

    organizations = _organizations_from_filtered_df(filtered_df)

    live_tab, manual_tab, bulk_tab = st.tabs(["Live GA4 Sync", "Manual Entry", "Bulk Import"])

    with live_tab:
        _render_live_sync_tab(organizations)

    with manual_tab:
        _render_manual_entry_tab()

    with bulk_tab:
        _render_bulk_import_tab()

    st.divider()
    st.subheader("Baseline Preview")

    baseline_org = st.text_input("Organization for baseline preview", key="ga4_preview_org")
    baseline_weekday = st.selectbox(
        "Weekday for preview",
        WEEKDAYS,
        key="ga4_preview_weekday"
    )

    if baseline_org.strip():
        baseline = calculate_ga4_weekday_baseline(baseline_org, baseline_weekday)
        if baseline is None:
            st.info("No GA4 baseline found for the selected organization and weekday.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Expected Active Users", baseline["expected_users"])
                st.metric("Records Used", baseline["lookback_used"])
            with c2:
                st.caption(f"Baseline Type: {baseline['baseline_type']}")

            records = baseline["records"].copy()
            display_cols = [col for col in ["activity_date", "weekday", "hour", "active_users", "source", "excluded"] if col in records.columns]
            st.dataframe(records[display_cols], width="stretch", hide_index=True)

    st.divider()
    st.subheader("Stored GA4 Activity")

    search = st.text_input("Search activity")
    activity_df = load_ga4_activity_records()

    if activity_df is None or activity_df.empty:
        st.info("No GA4 activity has been stored yet, or the GA4 table has not been created.")
        return

    view = activity_df.copy()
    if search.strip():
        mask = pd.Series([False] * len(view), index=view.index)
        for col in ["organization", "weekday", "source", "notes"]:
            if col in view.columns:
                mask = mask | view[col].fillna("").astype(str).str.contains(search, case=False, na=False)
        view = view[mask]

    if view.empty:
        st.info("No GA4 rows matched your search.")
        return

    for col in view.columns:
        if col == "activity_date":
            view[col] = pd.to_datetime(view[col], errors="coerce").dt.strftime("%Y-%m-%d")

    st.dataframe(
        view.sort_values("activity_date", ascending=False),
        width="stretch",
        hide_index=True
    )
