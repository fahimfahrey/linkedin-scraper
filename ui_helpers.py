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
