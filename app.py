import streamlit as st
import logging
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import asyncio
from typing import Optional

# Import local modules
from database import get_profiles_df, init_db
from session_manager import SessionManager
import ui_helpers
import export_helpers

# === Config ===
st.set_page_config(
    page_title="LinkedIn Lead Scraper Control Center",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = "linkedin_profiles.db"
SESSION_FILE = "session.json"

# === Initialize db ===
init_db(DB_PATH)

# === Session State init ===
if "session_validated" not in st.session_state:
    st.session_state.session_validated = False
if "validation_timestamp" not in st.session_state:
    st.session_state.validation_timestamp = None
if "validation_status" not in st.session_state:
    st.session_state.validation_status = None
if "bulk_urls" not in st.session_state:
    st.session_state.bulk_urls = ""
if "last_queue_time" not in st.session_state:
    st.session_state.last_queue_time = None


@st.cache_data(ttl=600)
def load_profile_data(db_path: str):
    """Load profile data from SQLite."""
    try:
        df = get_profiles_df(db_path)
    except Exception as e:
        logger.error(f"Failed to load profiles: {e}")
        return pd.DataFrame()
    return df


# === SIDEBAR ===
with st.sidebar:
    ui_helpers.display_validation_sidebar(SESSION_FILE)
    st.sidebar.divider()

    st.sidebar.markdown("### 🚀 Authentication")
    if st.sidebar.button("Launch Interactive Login", key="auth_button", use_container_width=True):
        st.session_state.auth_triggered = True
        with st.spinner("Launching browser auth..."):
            try:
                manager = SessionManager(SESSION_FILE)
                success = asyncio.run(manager.interactive_login())
                if success:
                    st.sidebar.success("✅ Auth successful!")
                    st.session_state.session_validated = False  # Trigger revalidation
                else:
                    st.sidebar.error("❌ Auth failed")
            except Exception as e:
                st.sidebar.error(f"Error: {str(e)[:100]}")


# === MAIN CONTENT ===
st.markdown("## 📊 LinkedIn Lead Acquisition Dashboard")

tab1, tab2 = st.tabs(["📥 Input & Auth", "📈 Analytics"])

# --- TAB 1: INPUT & AUTH ---
with tab1:
    st.markdown("### Bulk Target URL Input")

    col1, col2 = st.columns([4, 1])
    with col1:
        bulk_urls_input = st.text_area(
            "Paste LinkedIn profile URLs (one per line)",
            value=st.session_state.bulk_urls,
            height=200,
            placeholder="https://www.linkedin.com/in/username\nhttps://www.linkedin.com/in/another-user",
            help="URLs will be parsed and queued for scraping",
        )

    with col2:
        st.markdown("**Count**")
        url_count = len([u for u in bulk_urls_input.strip().split("\n") if u.strip()])
        st.metric("URLs", url_count)

    st.session_state.bulk_urls = bulk_urls_input

    # Validation feedback
    if bulk_urls_input.strip():
        urls = [u.strip() for u in bulk_urls_input.strip().split("\n") if u.strip()]
        valid_urls = [u for u in urls if "linkedin.com/in/" in u]
        invalid_urls = [u for u in urls if "linkedin.com/in/" not in u]

        if invalid_urls:
            st.warning(
                f"⚠️ {len(invalid_urls)} invalid URLs detected:\n"
                + "\n".join([f"  • {u[:60]}" for u in invalid_urls[:5]])
            )

        if st.button("🚀 Queue for Scraping", use_container_width=True, key="queue_urls"):
            st.info(f"✅ Queued {len(valid_urls)} profiles for scraping")
            st.session_state.last_queue_time = datetime.now()

    st.divider()
    st.markdown("### Manual Authentication")
    st.write("Use the button in the sidebar to launch interactive browser auth.")
    st.info("Session will be cached and reused for all subsequent requests.")


# --- TAB 2: ANALYTICS ---
with tab2:
    st.markdown("### 📊 Dashboard Metrics & Data")

    df_profiles = load_profile_data(DB_PATH)

    if not df_profiles.empty:
        ui_helpers.display_dashboard_metrics(df_profiles)
        st.divider()

        st.markdown("### 👥 Profile Repository")

        # Add filters
        col1, col2 = st.columns([2, 1])
        with col1:
            company_filter = st.multiselect(
                "Filter by Company",
                options=sorted(df_profiles["current_company"].dropna().unique()),
                default=[],
            )

        with col2:
            limit = st.number_input("Rows to display", min_value=5, max_value=500, value=50)

        # Prepare and filter dataframe
        df_display = ui_helpers.prepare_profiles_dataframe(df_profiles)

        if company_filter:
            # Filter based on original dataframe's company column
            mask = df_profiles.loc[df_display.index, "current_company"].isin(company_filter)
            df_display = df_display[mask]

        df_display = df_display.head(limit)

        # Responsive dataframe display
        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            hide_index=True,
        )

        st.caption(f"Showing {len(df_display)} of {len(df_profiles)} profiles")

        # Export section
        st.divider()
        st.markdown("### 📥 Export Data")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            csv_data = export_helpers.export_profiles_to_csv(df_profiles)
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=export_helpers.generate_export_filename("csv"),
                mime="text/csv",
                key="download_csv",
            )

        with col2:
            excel_data = export_helpers.export_profiles_to_excel(df_profiles)
            st.download_button(
                label="📊 Download Excel",
                data=excel_data,
                file_name=export_helpers.generate_export_filename("xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel",
            )

        with col3:
            st.caption(f"Total profiles available: {len(df_profiles)}")

    else:
        st.info("No profiles collected yet. Queue URLs in the Input tab to begin.")
