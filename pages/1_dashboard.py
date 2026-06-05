"""Dashboard — overview KPIs, trends, and recent activity."""
import streamlit as st

import app_state
import ui_helpers
import ui_theme

app_state.init_session_state()

st.markdown("## 📊 Dashboard")
st.caption("Overview of your LinkedIn lead acquisition.")

df = app_state.load_profiles(app_state.DB_PATH)
metrics = ui_helpers.calculate_profile_metrics(df)

# --- KPI cards ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Profiles", metrics["total_count"], help="Unique profiles in database")
c2.metric("New Today", metrics["new_today"], help="Collected since midnight")
c3.metric("Avg Jobs / Profile", metrics["avg_experience_years"], help="Average experience entries")
with c4:
    st.markdown("**Collection**")
    if st.session_state.get("collection_active"):
        ui_theme.render_badge("Live", "live")
    else:
        ui_theme.render_badge("Idle", "idle")

st.divider()

if df.empty:
    ui_theme.render_empty_state(
        "No profiles yet",
        "Queue some LinkedIn URLs on the Collect page to start building your dataset.",
    )
    if st.button("📥 Go to Collect", type="primary"):
        st.switch_page("pages/2_collect.py")
else:
    left, right = st.columns(2)
    with left:
        st.markdown("#### Collection over time")
        st.line_chart(ui_helpers.collection_timeline(df), height=240)
    with right:
        st.markdown("#### Top companies")
        st.bar_chart(ui_helpers.top_companies(df, 8), height=240, horizontal=True)

    st.divider()
    st.markdown("#### Recent profiles")
    recent = ui_helpers.prepare_profiles_dataframe(df).head(5)
    st.dataframe(recent, use_container_width=True, hide_index=True)

    if st.button("🗂️ View all data"):
        st.switch_page("pages/4_data.py")
