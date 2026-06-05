"""Collect — paste target URLs, validate, and queue a scraping run."""
import streamlit as st

import app_state
import ui_helpers
import ui_theme
from thread_manager import ScraperWorker
from environment_config import get_chromium_environment
from scraper import ExecutionWindowController, AnomalyDetector

app_state.init_session_state()

st.markdown("## 📥 Collect")
st.caption("Paste LinkedIn profile URLs, one per line. Invalid lines are flagged before queuing.")

active = st.session_state.get("collection_active", False)

if active:
    st.info("⏳ A collection is running. Inputs are frozen — see the Live Monitor.")
    if st.button("📡 Open Live Monitor", type="primary"):
        st.switch_page("pages/3_live_monitor.py")

col_input, col_meta = st.columns([4, 1])
with col_input:
    text = st.text_area(
        "Target URLs",
        value=st.session_state.bulk_urls,
        height=240,
        placeholder="https://www.linkedin.com/in/username\nhttps://www.linkedin.com/in/another-user",
        disabled=active,
        label_visibility="collapsed",
    )
st.session_state.bulk_urls = text

valid, invalid = ui_helpers.split_url_validation(text)

with col_meta:
    st.metric("Valid", len(valid))
    st.metric("Invalid", len(invalid))

if invalid:
    with st.expander(f"⚠️ {len(invalid)} invalid line(s)"):
        for line in invalid[:20]:
            st.text(line[:80])

with st.expander("ℹ️ Tips"):
    st.markdown(
        "- One URL per line.\n"
        "- Must contain `linkedin.com/in/`.\n"
        "- Duplicates already in the database are skipped automatically."
    )

st.divider()

queue_disabled = active or not valid
if st.button("🚀 Queue for Scraping", type="primary", use_container_width=True, disabled=queue_disabled):
    worker = ScraperWorker()
    worker.spawn(
        valid,
        env=get_chromium_environment(),
        window_controller=ExecutionWindowController(),
        anomaly_detector=AnomalyDetector(),
    )
    st.session_state.scraper_worker = worker
    app_state.start_collection(len(valid))
    st.switch_page("pages/3_live_monitor.py")

if not valid and not active:
    ui_theme.render_empty_state("Nothing queued yet", "Paste valid LinkedIn profile URLs above to enable queuing.")
