import streamlit as st
import logging
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import asyncio
import threading
import time
from typing import Optional

# Import local modules
from database import get_profiles_df, init_db
from session_manager import SessionManager
from thread_manager import ScraperWorker
from environment_config import get_chromium_environment
from scraper import ExecutionWindowController, AnomalyDetector
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

# Thread control state
if "scraper_worker" not in st.session_state:
    st.session_state.scraper_worker = None
if "collection_active" not in st.session_state:
    st.session_state.collection_active = False
if "collected_profiles" not in st.session_state:
    st.session_state.collected_profiles = []
if "status_log" not in st.session_state:
    st.session_state.status_log = []
if "thread_lock" not in st.session_state:
    st.session_state.thread_lock = threading.Lock()
if "current_warning" not in st.session_state:
    st.session_state.current_warning = None
if "last_message_check" not in st.session_state:
    st.session_state.last_message_check = 0.0


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


# === Message Consumer Loop ===
if st.session_state.scraper_worker and st.session_state.collection_active:
    # Non-blocking message pull with rerun trigger
    if time.time() - st.session_state.last_message_check > 0.1:
        message = st.session_state.scraper_worker.get_next_message(timeout=0.05)
        if message:
            from queue_protocol import StatusUpdate, ProfilePayload, OperationWarning, ExecutionComplete

            if isinstance(message, StatusUpdate):
                # Log status updates
                log_entry = f"[{message.status}] {message.profile_url} ({message.elapsed_sec:.1f}s)"
                st.session_state.status_log.append(log_entry)
                # Keep only last 50
                if len(st.session_state.status_log) > 50:
                    st.session_state.status_log = st.session_state.status_log[-50:]

            elif isinstance(message, ProfilePayload):
                # Add profile to collected list (thread-safe)
                with st.session_state.thread_lock:
                    st.session_state.collected_profiles.append(message.profile_data)

            elif isinstance(message, OperationWarning):
                # Store warning for UI display
                st.session_state.current_warning = message

            elif isinstance(message, ExecutionComplete):
                # Mark collection as complete
                st.session_state.collection_active = False
                if message.success:
                    logger.info(f"Collection complete: {message.profiles_collected}/{message.total_queued}")
                else:
                    logger.error(f"Collection failed: {message.error_type} - {message.details}")

        st.session_state.last_message_check = time.time()

        # Trigger rerun to refresh UI
        time.sleep(0.01)
        st.rerun()


# === MAIN CONTENT ===
st.markdown("## 📊 LinkedIn Lead Acquisition Dashboard")

# Show collection status if active
if st.session_state.collection_active:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("⏳ Collection in progress. Inputs frozen.")
    with col2:
        if st.button("⏹️ Cancel", key="cancel_scrape"):
            if st.session_state.scraper_worker:
                st.session_state.scraper_worker.terminate()
            st.session_state.collection_active = False
            st.success("Collection cancelled")
            st.rerun()

tab1, tab2, tab3 = st.tabs(["📥 Input & Auth", "📈 Analytics", "📊 Live Status"])

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
            disabled=st.session_state.collection_active,
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

        if st.button("🚀 Queue for Scraping", use_container_width=True, key="queue_urls",
                     disabled=st.session_state.collection_active):
            # Spawn worker thread
            worker = ScraperWorker()
            worker.spawn(
                valid_urls,
                env=get_chromium_environment(),
                window_controller=ExecutionWindowController(),
                anomaly_detector=AnomalyDetector(),
            )
            st.session_state.scraper_worker = worker
            st.session_state.collection_active = True
            st.session_state.collected_profiles = []
            st.session_state.status_log = []
            st.session_state.current_warning = None
            st.info(f"✅ Queued {len(valid_urls)} profiles for scraping. Collection starting...")
            st.session_state.last_queue_time = datetime.now()
            st.rerun()

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


# --- TAB 3: LIVE STATUS ---
with tab3:
    st.markdown("### 📊 Live Collection Status")

    if st.session_state.collection_active:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Profiles Collected", len(st.session_state.collected_profiles))

        with col2:
            st.metric("Status Updates", len(st.session_state.status_log))

        with col3:
            if st.session_state.scraper_worker:
                st.metric("Worker Active", "🟢 Running" if st.session_state.scraper_worker.is_alive() else "🟡 Stopping")

        st.divider()

        # Display warnings if any
        if st.session_state.current_warning:
            warning = st.session_state.current_warning
            if warning.severity == "critical":
                st.error(f"⚠️ {warning.message}")
            elif warning.severity == "warning":
                st.warning(f"⚠️ {warning.message}")
            else:
                st.info(f"ℹ️ {warning.message}")

        st.divider()

        # Recent activity log
        st.markdown("### Recent Activity")
        if st.session_state.status_log:
            for log in st.session_state.status_log[-15:]:
                st.caption(log)
        else:
            st.caption("No activity yet...")

    else:
        st.info("No active collection. Queue URLs in the Input tab to start.")
