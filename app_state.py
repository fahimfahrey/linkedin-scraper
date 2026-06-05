"""Shared session-state init and worker message-drain for the Streamlit app.

Extracted from the old monolithic app.py so every page can initialize state and
consume worker messages without duplicating logic.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)

DB_PATH = "linkedin_profiles.db"
SESSION_FILE = "session.json"

# Max messages drained per fragment tick (keeps a single rerun bounded).
_DRAIN_BATCH = 100

_DEFAULTS = {
    "session_validated": False,
    "validation_timestamp": None,
    "validation_status": None,
    "validation_expiry": None,
    "bulk_urls": "",
    "last_queue_time": None,
    "scraper_worker": None,
    "collection_active": False,
    "collected_profiles": [],
    "status_log": [],
    "current_warning": None,
    "queue_total": 0,
    "collection_start": None,
    "last_completion": None,
}


def init_session_state() -> None:
    """Initialize all session-state keys with safe defaults (idempotent)."""
    for key, value in _DEFAULTS.items():
        # Use list/dict-safe defaults via copy for mutables.
        if isinstance(value, list):
            st.session_state.setdefault(key, list(value))
        else:
            st.session_state.setdefault(key, value)

    if "thread_lock" not in st.session_state:
        st.session_state.thread_lock = threading.Lock()


def start_collection(total: int) -> None:
    """Reset live-collection state when a new batch is queued."""
    st.session_state.collection_active = True
    st.session_state.collected_profiles = []
    st.session_state.status_log = []
    st.session_state.current_warning = None
    st.session_state.queue_total = total
    st.session_state.collection_start = datetime.now()
    st.session_state.last_completion = None
    st.session_state.last_queue_time = datetime.now()


def drain_worker_messages() -> None:
    """Pull all currently-available worker messages and fold them into state.

    Non-blocking: drains up to _DRAIN_BATCH messages then returns. Safe to call
    from a fragment on every tick.
    """
    worker = st.session_state.get("scraper_worker")
    if worker is None:
        return

    from queue_protocol import (
        StatusUpdate,
        ProfilePayload,
        OperationWarning,
        ExecutionComplete,
    )

    for _ in range(_DRAIN_BATCH):
        message = worker.get_next_message(timeout=0.01)
        if message is None:
            break

        if isinstance(message, StatusUpdate):
            entry = f"[{message.status}] {message.profile_url} ({message.elapsed_sec:.1f}s)"
            st.session_state.status_log.append(entry)
            if len(st.session_state.status_log) > 100:
                st.session_state.status_log = st.session_state.status_log[-100:]

        elif isinstance(message, ProfilePayload):
            with st.session_state.thread_lock:
                st.session_state.collected_profiles.append(message.profile_data)

        elif isinstance(message, OperationWarning):
            st.session_state.current_warning = message

        elif isinstance(message, ExecutionComplete):
            st.session_state.collection_active = False
            st.session_state.last_completion = message
            if message.success:
                logger.info(
                    "Collection complete: %s/%s",
                    message.profiles_collected,
                    message.total_queued,
                )
            else:
                logger.error(
                    "Collection failed: %s - %s",
                    message.error_type,
                    message.details,
                )


@st.cache_data(ttl=600)
def load_profiles(db_path: str):
    """Load profiles from SQLite (cached). Returns empty DataFrame on failure."""
    import pandas as pd
    from database import get_profiles_df

    try:
        return get_profiles_df(db_path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load profiles: %s", exc)
        return pd.DataFrame()


def elapsed_seconds() -> float:
    """Seconds since the active collection started (0 if none)."""
    start = st.session_state.get("collection_start")
    if start is None:
        return 0.0
    return (datetime.now() - start).total_seconds()
