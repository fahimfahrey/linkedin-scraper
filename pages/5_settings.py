"""Settings — session/auth management and environment readout."""
import asyncio
import json
from pathlib import Path

import streamlit as st

import app_state
import ui_helpers
import ui_theme
from session_manager import SessionManager
from environment_config import get_chromium_environment

app_state.init_session_state()

st.markdown("## ⚙️ Settings")

# --- Session / Auth ---
st.markdown("#### Authentication")

is_valid, status_msg, expiry = ui_helpers.validate_session_file(app_state.SESSION_FILE)

sc1, sc2 = st.columns([2, 1])
with sc1:
    if is_valid:
        ui_theme.render_badge("Session valid & active", "valid")
    else:
        ui_theme.render_badge(status_msg, "invalid")
    if expiry:
        st.caption(expiry)
    path = Path(app_state.SESSION_FILE)
    if path.exists():
        st.caption(f"📁 {path.stat().st_size / 1024:.1f} KB — {path.resolve()}")
with sc2:
    if st.button("🔄 Re-check", use_container_width=True):
        st.session_state.session_validated = False
        st.rerun()

if st.button("🚀 Launch Interactive Login", type="primary", use_container_width=True):
    with st.spinner("Launching browser auth…"):
        try:
            manager = SessionManager(app_state.SESSION_FILE)
            success = asyncio.run(manager.interactive_login())
            if success:
                st.success("✅ Auth successful — session cached.")
                st.session_state.session_validated = False
            else:
                st.error("❌ Auth failed")
        except Exception as exc:
            st.error(f"Error: {str(exc)[:120]}")

st.divider()

# --- Environment readout (read-only) ---
st.markdown("#### Environment")
env = get_chromium_environment()
env_cols = st.columns(2)
keys = list(env.items())
mid = (len(keys) + 1) // 2
for col, chunk in zip(env_cols, (keys[:mid], keys[mid:])):
    with col:
        for key, value in chunk:
            st.markdown(f"**{key}**")
            st.caption(value or "—")

win_path = Path("execution_window.json")
if win_path.exists():
    st.markdown("#### Execution window")
    try:
        st.json(json.loads(win_path.read_text()))
    except Exception:
        st.caption("Unreadable execution_window.json")
