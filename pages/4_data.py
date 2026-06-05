"""Data — explore, filter, drill into, and export collected profiles."""
import streamlit as st

import app_state
import ui_helpers
import ui_theme
import export_helpers

app_state.init_session_state()

st.markdown("## 🗂️ Data")

df = app_state.load_profiles(app_state.DB_PATH)

if df.empty:
    ui_theme.render_empty_state(
        "No profiles to show",
        "Collected profiles will appear here once a run completes.",
    )
    if st.button("📥 Go to Collect", type="primary"):
        st.switch_page("pages/2_collect.py")
    st.stop()

ui_helpers.display_dashboard_metrics(df)
st.divider()

# --- Filters ---
f1, f2, f3 = st.columns([2, 2, 1])
with f1:
    companies = st.multiselect(
        "Company", options=sorted(df["current_company"].dropna().unique()), default=[]
    )
with f2:
    search = st.text_input("Search name / headline", placeholder="e.g. engineer")
with f3:
    limit = st.number_input("Rows", min_value=5, max_value=500, value=50, step=5)

filtered = ui_helpers.filter_profiles(df, companies, search)
table = ui_helpers.prepare_profiles_table(filtered).head(limit)


@st.dialog("Profile detail", width="large")
def _detail(profile: dict):
    ui_helpers.render_profile_detail(profile)


event = st.dataframe(
    table,
    use_container_width=True,
    height=460,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Profile": st.column_config.LinkColumn("Profile", display_text="Open ↗"),
        "Jobs": st.column_config.ProgressColumn(
            "Jobs", min_value=0, max_value=max(int(table["Jobs"].max() or 1), 1), format="%d"
        ),
        "Degrees": st.column_config.ProgressColumn(
            "Degrees", min_value=0, max_value=max(int(table["Degrees"].max() or 1), 1), format="%d"
        ),
        "Collected": st.column_config.DatetimeColumn("Collected", format="YYYY-MM-DD HH:mm"),
    },
)

st.caption(f"Showing {len(table)} of {len(df)} profiles")

# Row selection → detail dialog (map table row back to raw record by URL).
rows = event.selection.rows if event and event.selection else []
if rows:
    selected_url = table.iloc[rows[0]]["Profile"]
    match = df[df["linkedin_url"] == selected_url]
    if not match.empty:
        _detail(match.iloc[0].to_dict())

# --- Export ---
st.divider()
st.markdown("#### Export")
e1, e2, e3 = st.columns([1, 1, 2])
with e1:
    st.download_button(
        "📄 CSV",
        data=export_helpers.export_profiles_to_csv(filtered),
        file_name=export_helpers.generate_export_filename("csv"),
        mime="text/csv",
        use_container_width=True,
    )
with e2:
    st.download_button(
        "📊 Excel",
        data=export_helpers.export_profiles_to_excel(filtered),
        file_name=export_helpers.generate_export_filename("xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with e3:
    st.caption(f"Export reflects current filters: {len(filtered)} profiles.")
