import streamlit as st
from utils.logger import write_audit_log
from utils.auth import get_user_role


def safe_render(page_name, render_func, data):
    try:
        render_func(data)

    except Exception as e:
        user_email = st.session_state.get("user_email", "")

        write_audit_log(
            user_email,
            get_user_role(),
            "PAGE_RENDER_ERROR",
            f"page={page_name}, error={str(e)}"
        )

        st.error(f"{page_name} failed to load.")
        with st.expander("Show error details"):
            st.exception(e)