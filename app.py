"""LinkedIn Lead Scraper — Streamlit control center (navigation entry point).

This file is intentionally thin: it sets page config, injects theme, initializes
shared session state, renders the pinned sidebar, and dispatches to the page
selected via st.navigation. Page logic lives under pages/.
"""
import logging

import streamlit as st

from database import init_db
import app_state
import ui_theme
import ui_helpers

logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="LinkedIn Lead Scraper Control Center",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_theme.inject_theme()
init_db(app_state.DB_PATH)
app_state.init_session_state()

# --- Navigation ---
pages = {
    "Overview": [
        st.Page("pages/1_dashboard.py", title="Dashboard", icon="📊", default=True),
    ],
    "Operate": [
        st.Page("pages/2_collect.py", title="Collect", icon="📥"),
        st.Page("pages/3_live_monitor.py", title="Live Monitor", icon="📡"),
    ],
    "Manage": [
        st.Page("pages/4_data.py", title="Data", icon="🗂️"),
        st.Page("pages/5_settings.py", title="Settings", icon="⚙️"),
    ],
}

nav = st.navigation(pages)

# --- Pinned sidebar status (below native nav) ---
with st.sidebar:
    ui_helpers.render_sidebar_session(app_state.SESSION_FILE)
    if st.session_state.get("collection_active"):
        ui_theme.render_badge("Collection running", "live")

nav.run()
