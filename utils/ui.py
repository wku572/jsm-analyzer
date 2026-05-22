import streamlit as st
from datetime import datetime
import pytz
from pathlib import Path


LOCAL_TZ = "Africa/Addis_Ababa"

PRIMARY = "#02404f"
ACCENT = "#eb7d23"
LOGO_PATH = Path("assets/kifiya-logo.png")


def inject_css():
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=Raleway:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Raleway', sans-serif;
}}

.stApp {{
    background: #ffffff;
}}

header[data-testid="stHeader"],
.stDeployButton,
div[data-testid="stToolbar"] {{
    display: block !important;
}}



.main .block-container {{
    padding-top: 0.4rem;
    padding-bottom: 1rem;
    padding-left: 1.4rem;
    padding-right: 1.4rem;
    max-width: 1550px;
}}

h1, h2, h3, h4 {{
    font-family: 'Montserrat', sans-serif;
    color: {PRIMARY};
}}

.kifiya-title {{
    font-family: 'Montserrat', sans-serif;
    color: {PRIMARY};
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
}}

.kifiya-subtitle {{
    color: #64748b;
    font-size: 13px;
    margin-top: 4px;
}}

.refresh-card {{
    background: {PRIMARY};
    color: white;
    padding: 14px 18px;
    border-radius: 18px;
    text-align: right;
    box-shadow: 0 10px 22px rgba(2,64,79,0.20);
}}

.refresh-label {{
    color: #cbd5e1;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

.refresh-time {{
    color: white;
    font-size: 17px;
    font-weight: 800;
    margin-top: 4px;
    font-family: 'Montserrat', sans-serif;
}}

.kpi-card {{
    padding: 18px;
    border-radius: 18px;
    background: #ffffff;
    border-top: 5px solid {ACCENT};
    border-left: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    box-shadow: 0 8px 24px rgba(15,23,42,0.06);
    margin-bottom: 12px;
}}

.kpi-title {{
    font-size: 12px;
    color: #64748b;
    font-weight: 800;
    text-transform: uppercase;
}}

.kpi-value {{
    font-size: 34px;
    font-weight: 800;
    color: {PRIMARY};
    margin-top: 6px;
    font-family: 'Montserrat', sans-serif;
}}

.kpi-note {{
    font-size: 11px;
    color: #94a3b8;
    margin-top: 6px;
}}

section[data-testid="stSidebar"] {{
    
    border-right: 1px solid #dbe5e8;
    color: {PRIMARY};

}}

section[data-testid="stSidebar"] > div:first-child {{
    padding-top: 1rem;
    
}}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    background: {PRIMARY};
    color: white;
    font-family: 'Montserrat', sans-serif;
    font-weight: 800;
}}

div[role="radiogroup"] label {{
    padding: 7px 9px;
    border-radius: 10px;
    margin-bottom: 2px;
    color: white;
}}

div[role="radiogroup"] label:hover {{
    background: {ACCENT} !important;
    color: white !important;
}}

div[data-testid="stExpander"] details {{
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    background: #ffffff;
}}

div[data-testid="stExpander"] summary {{
    font-weight: 700;
    color: {PRIMARY};
}}

button[kind="primary"] {{
    background: {ACCENT} !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}}

.footer {{
    margin-top: 42px;
    padding-top: 18px;
    border-top: 1px solid #cbd5e1;
    text-align: center;
    color: #64748b;
    font-size: 12px;
}}
</style>
        """,
        unsafe_allow_html=True
    )


def header():
    tz = pytz.timezone(LOCAL_TZ)
    refreshed = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    left, right = st.columns([6, 1.2])

    with left:
        logo_col, title_col = st.columns([1, 6])

        with logo_col:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=110)
            else:
                st.markdown("### K")

        with title_col:
            st.markdown('<div class="kifiya-title">JSM Analyzer</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="kifiya-subtitle">Kifiya Jira Service Management Analytics Platform</div>',
                unsafe_allow_html=True
            )

    with right:
        st.markdown(
            f"""
<div class="refresh-card">
    <div class="refresh-label">Last Refreshed</div>
    <div class="refresh-time">{refreshed}</div>
</div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")


def footer():
    st.markdown(
        """
<div class="footer">
    © 2026 Kifiya Financial Technology • JSM Analytics Platform
</div>
        """,
        unsafe_allow_html=True
    )


def kpi_card(title, value, note="", icon="📌"):
    st.markdown(
        f"""
<div class="kpi-card">
    <div class="kpi-title">{icon} {title}</div>
    <div class="kpi-value">{value}</div>
    <div class="kpi-note">{note}</div>
</div>
        """,
        unsafe_allow_html=True
    )