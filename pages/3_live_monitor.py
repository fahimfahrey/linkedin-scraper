"""Live Monitor — real-time collection progress via auto-refreshing fragment."""
import streamlit as st

import app_state
import ui_theme

app_state.init_session_state()

st.markdown("## 📡 Live Monitor")


@st.fragment(run_every=2 if st.session_state.get("collection_active") else None)
def monitor_panel():
    app_state.drain_worker_messages()

    active = st.session_state.get("collection_active", False)
    collected = len(st.session_state.get("collected_profiles", []))
    total = st.session_state.get("queue_total", 0)

    # Progress + metrics
    if total:
        st.progress(min(collected / total, 1.0), text=f"{collected} / {total} profiles")

    m1, m2, m3 = st.columns(3)
    m1.metric("Collected", collected)
    m2.metric("Remaining", max(total - collected, 0))
    m3.metric("Elapsed", f"{app_state.elapsed_seconds():.0f}s")

    worker = st.session_state.get("scraper_worker")
    if active and worker is not None:
        ui_theme.render_badge("Running" if worker.is_alive() else "Stopping", "live" if worker.is_alive() else "warning")
        if st.button("⏹️ Cancel collection", key="cancel_collection"):
            worker.terminate()
            st.session_state.collection_active = False
            st.rerun()

    # Warnings
    warning = st.session_state.get("current_warning")
    if warning is not None:
        if warning.severity == "critical":
            st.error(f"⚠️ {warning.message}")
        elif warning.severity == "warning":
            st.warning(f"⚠️ {warning.message}")
        else:
            st.info(f"ℹ️ {warning.message}")

    st.divider()
    st.markdown("#### Recent activity")
    log = st.session_state.get("status_log", [])
    if log:
        with st.status(f"{len(log)} updates", state="running" if active else "complete", expanded=True):
            for entry in log[-15:]:
                st.write(entry)
    else:
        st.caption("No activity yet…")

    # Completion summary
    completion = st.session_state.get("last_completion")
    if not active and completion is not None:
        if completion.success:
            st.success(
                f"✅ Done: {completion.profiles_collected}/{completion.total_queued} profiles collected."
            )
        else:
            st.error(f"❌ Failed: {completion.error_type}")

    # When a run finishes mid-fragment, do a full rerun once to drop the timer.
    if not active and st.session_state.get("_monitor_was_active"):
        st.session_state._monitor_was_active = False
        st.rerun()
    if active:
        st.session_state._monitor_was_active = True


if not st.session_state.get("collection_active") and not st.session_state.get("collected_profiles"):
    ui_theme.render_empty_state(
        "No active collection",
        "Queue URLs on the Collect page to see live progress here.",
    )
    if st.button("📥 Go to Collect", type="primary"):
        st.switch_page("pages/2_collect.py")
else:
    monitor_panel()
