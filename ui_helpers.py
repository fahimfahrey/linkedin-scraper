"""Helper functions for Streamlit UI components."""
import json
import logging
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


def validate_session_file(session_file: str = "session.json") -> Tuple[bool, str, Optional[str]]:
    """Validate session.json file structure and content.

    Returns:
        Tuple of (is_valid: bool, status_message: str, expiry_info: Optional[str])
    """
    session_path = Path(session_file)

    # Check file exists
    if not session_path.exists():
        return False, "❌ Session file not found", None

    # Check file size
    file_size = session_path.stat().st_size
    if file_size == 0:
        return False, "❌ Session file empty", None

    # Validate JSON structure
    try:
        with open(session_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"❌ Invalid JSON: {str(e)[:50]}", None

    # Check required keys
    required_keys = ["cookies", "origins"]
    if not all(key in data for key in required_keys):
        missing = [k for k in required_keys if k not in data]
        return False, f"❌ Missing keys: {', '.join(missing)}", None

    # Check cookies present
    if not data.get("cookies"):
        return False, "❌ No auth cookies found", None

    # Success - calculate cookie expiry if available
    expiry_info = None
    if data.get("cookies"):
        expirations = []
        for cookie in data["cookies"]:
            if "expires" in cookie:
                expirations.append(cookie["expires"])
        if expirations:
            earliest = min(expirations)
            expiry_info = f"Expires: {datetime.fromtimestamp(earliest).strftime('%Y-%m-%d %H:%M:%S')}"

    return True, "🟢 Session valid & active", expiry_info


def calculate_profile_metrics(df: pd.DataFrame) -> dict:
    """Calculate dashboard metrics from profile dataframe.

    Returns:
        Dict with keys: total_count, new_today, avg_experience_years
    """
    if df.empty:
        return {
            "total_count": 0,
            "new_today": 0,
            "avg_experience_years": 0,
        }

    # Total profiles
    total_count = len(df)

    # New profiles today
    df_copy = df.copy()
    df_copy["collected_at"] = pd.to_datetime(df_copy["collected_at"])
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = len(df_copy[df_copy["collected_at"] >= today])

    # Average experience years (parsed from experience_json)
    avg_exp = 0
    try:
        exp_years = []
        for exp_json_str in df_copy["experience_json"].dropna():
            if exp_json_str:
                exp_data = json.loads(exp_json_str)
                if isinstance(exp_data, list) and len(exp_data) > 0:
                    exp_years.append(len(exp_data))
        if exp_years:
            avg_exp = sum(exp_years) / len(exp_years)
    except Exception as e:
        logger.warning(f"Failed to calculate avg experience: {e}")

    return {
        "total_count": total_count,
        "new_today": new_today,
        "avg_experience_years": round(avg_exp, 1),
    }


def display_dashboard_metrics(df: pd.DataFrame) -> None:
    """Display dashboard metric cards."""
    import streamlit as st

    metrics = calculate_profile_metrics(df)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Total Profiles",
            metrics["total_count"],
            delta=None,
            help="Unique LinkedIn profiles in database",
        )

    with col2:
        st.metric(
            "New Today",
            metrics["new_today"],
            delta=None,
            help="Profiles collected in last 24 hours",
        )

    with col3:
        st.metric(
            "Avg Experience (yrs)",
            metrics["avg_experience_years"],
            delta=None,
            help="Average number of jobs per profile",
        )


def display_validation_sidebar(session_file: str = "session.json") -> None:
    """Render sidebar validation UI."""
    import streamlit as st

    st.sidebar.markdown("## 🔐 System Operations")

    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.sidebar.markdown("**Session Status**")
    with col2:
        if st.sidebar.button("🔄 Refresh", key="refresh_validation"):
            st.session_state.session_validated = False
            st.rerun()

    # Validate on demand or cache if recently validated
    if (
        not st.session_state.get("session_validated", False)
        or st.session_state.get("validation_timestamp") is None
    ):
        is_valid, status_msg, expiry_info = validate_session_file(session_file)
        st.session_state.session_validated = is_valid
        st.session_state.validation_status = status_msg
        st.session_state.validation_expiry = expiry_info
        st.session_state.validation_timestamp = datetime.now()

    # Display status badge
    status_container = st.sidebar.container()
    status_container.markdown(st.session_state.get("validation_status", "⚠️ Unknown status"))

    if st.session_state.get("validation_expiry"):
        st.sidebar.caption(st.session_state.validation_expiry)

    # File size indicator
    session_path = Path(session_file)
    if session_path.exists():
        size_kb = session_path.stat().st_size / 1024
        st.sidebar.caption(f"📁 {size_kb:.1f} KB")


def prepare_profiles_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare dataframe for display: parse JSON fields, derive preview columns.

    Uses vectorized operations per pandas-pro best practices.
    """
    if df.empty:
        return df.copy()

    # Make explicit copy to avoid SettingWithCopyWarning
    df_display = df.copy()

    # Convert collected_at to datetime
    df_display["collected_at"] = pd.to_datetime(df_display["collected_at"])

    # Parse experience_json: count jobs
    def count_jobs(exp_json_str):
        if pd.isna(exp_json_str) or not exp_json_str:
            return 0
        try:
            data = json.loads(exp_json_str)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    # Parse education_json: count degrees
    def count_degrees(edu_json_str):
        if pd.isna(edu_json_str) or not edu_json_str:
            return 0
        try:
            data = json.loads(edu_json_str)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    # Vectorized: extract parsed counts
    df_display["Jobs"] = df_display["experience_json"].apply(count_jobs)
    df_display["Degrees"] = df_display["education_json"].apply(count_degrees)

    # Select display columns in order
    display_cols = [
        "full_name",
        "headline",
        "location",
        "current_company",
        "Jobs",
        "Degrees",
        "collected_at",
    ]
    df_display = df_display[display_cols].copy()

    # Rename for display
    df_display.columns = [
        "Name",
        "Headline",
        "Location",
        "Company",
        "Jobs",
        "Degrees",
        "Collected",
    ]

    # Format timestamp
    df_display["Collected"] = df_display["Collected"].dt.strftime("%Y-%m-%d %H:%M")

    return df_display.sort_values("Collected", ascending=False)


# --- URL validation -------------------------------------------------------

def split_url_validation(text: str) -> Tuple[list, list]:
    """Split pasted text into (valid, invalid) LinkedIn profile URLs.

    A line is valid when it contains "linkedin.com/in/". Blank lines ignored.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    valid = [u for u in lines if "linkedin.com/in/" in u]
    invalid = [u for u in lines if "linkedin.com/in/" not in u]
    return valid, invalid


# --- Data shaping for the Data page ---------------------------------------

def _count_json(value) -> int:
    if pd.isna(value) or not value:
        return 0
    try:
        data = json.loads(value)
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def prepare_profiles_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a display table that keeps linkedin_url (for LinkColumn) + counts.

    Distinct from prepare_profiles_dataframe (which drops the URL). Used by the
    Data page with st.dataframe column_config.
    """
    if df.empty:
        return pd.DataFrame(
            columns=["Name", "Headline", "Location", "Company", "Jobs", "Degrees", "Profile", "Collected"]
        )

    out = pd.DataFrame()
    out["Name"] = df["full_name"]
    out["Headline"] = df["headline"]
    out["Location"] = df["location"]
    out["Company"] = df["current_company"]
    out["Jobs"] = df["experience_json"].apply(_count_json)
    out["Degrees"] = df["education_json"].apply(_count_json)
    out["Profile"] = df["linkedin_url"]
    out["Collected"] = pd.to_datetime(df["collected_at"])
    return out.sort_values("Collected", ascending=False)


def filter_profiles(df: pd.DataFrame, companies: list, search: str) -> pd.DataFrame:
    """Filter raw profile df by company list and free-text search (name/headline)."""
    if df.empty:
        return df
    out = df
    if companies:
        out = out[out["current_company"].isin(companies)]
    term = (search or "").strip().lower()
    if term:
        name = out["full_name"].fillna("").str.lower()
        head = out["headline"].fillna("").str.lower()
        out = out[name.str.contains(term) | head.str.contains(term)]
    return out


def top_companies(df: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    """Return top-n companies by profile count as a DataFrame (index=company)."""
    if df.empty or "current_company" not in df:
        return pd.DataFrame({"Profiles": []})
    counts = df["current_company"].dropna().value_counts().head(n)
    return counts.rename("Profiles").to_frame()


def collection_timeline(df: pd.DataFrame) -> pd.DataFrame:
    """Return profiles-collected-per-day as a DataFrame (index=date)."""
    if df.empty:
        return pd.DataFrame({"Profiles": []})
    dates = pd.to_datetime(df["collected_at"]).dt.date
    counts = dates.value_counts().sort_index()
    out = counts.rename("Profiles").to_frame()
    out.index = pd.to_datetime(out.index)
    out.index.name = "Date"
    return out


# --- Shared render components ----------------------------------------------

def render_sidebar_session(session_file: str = "session.json") -> None:
    """Render pinned session-status badge + auth shortcut in the sidebar.

    Replaces the old display_validation_sidebar layout; works under st.navigation.
    """
    import streamlit as st
    import ui_theme

    st.sidebar.divider()
    st.sidebar.markdown("**Session**")

    if not st.session_state.get("session_validated", False) or st.session_state.get("validation_timestamp") is None:
        is_valid, status_msg, expiry_info = validate_session_file(session_file)
        st.session_state.session_validated = is_valid
        st.session_state.validation_status = status_msg
        st.session_state.validation_expiry = expiry_info
        st.session_state.validation_timestamp = datetime.now()

    if st.session_state.get("session_validated"):
        ui_theme.render_badge("Session active", "valid")
    else:
        ui_theme.render_badge("No valid session", "invalid")

    if st.session_state.get("validation_expiry"):
        st.sidebar.caption(st.session_state.validation_expiry)

    path = Path(session_file)
    if path.exists():
        st.sidebar.caption(f"📁 {path.stat().st_size / 1024:.1f} KB")

    if st.sidebar.button("🔄 Re-check session", use_container_width=True, key="recheck_session"):
        st.session_state.session_validated = False
        st.rerun()


def render_profile_detail(profile: dict) -> None:
    """Render a single profile's full detail (used inside st.dialog)."""
    import streamlit as st

    st.subheader(profile.get("full_name") or "Unknown")
    if profile.get("headline"):
        st.caption(profile["headline"])

    meta_cols = st.columns(2)
    with meta_cols[0]:
        st.markdown(f"**Location:** {profile.get('location') or '—'}")
    with meta_cols[1]:
        st.markdown(f"**Company:** {profile.get('current_company') or '—'}")

    url = profile.get("linkedin_url")
    if url:
        st.markdown(f"🔗 [Open LinkedIn profile]({url})")

    if profile.get("about_text"):
        st.markdown("**About**")
        st.write(profile["about_text"])

    _render_json_section("Experience", profile.get("experience_json"))
    _render_json_section("Education", profile.get("education_json"))


def _render_json_section(title: str, raw) -> None:
    import streamlit as st

    if not raw:
        return
    try:
        items = json.loads(raw)
    except Exception:
        return
    if not isinstance(items, list) or not items:
        return

    st.markdown(f"**{title}**")
    for item in items:
        if isinstance(item, dict):
            primary = item.get("title") or item.get("degree") or item.get("school") or ""
            secondary = item.get("company") or item.get("school") or item.get("field") or ""
            line = " — ".join([p for p in (primary, secondary) if p]) or json.dumps(item)
            st.markdown(f"- {line}")
        else:
            st.markdown(f"- {item}")
