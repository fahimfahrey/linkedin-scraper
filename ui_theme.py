"""Light CSS theming and reusable HTML snippets for the Streamlit UI.

Kept intentionally small: native theme tokens live in .streamlit/config.toml.
This module adds only cosmetic polish (cards, badge pills, spacing) — no layout
hacks or overrides of Streamlit internals.
"""
from __future__ import annotations

import streamlit as st

PRIMARY = "#0A66C2"

_CSS = """
<style>
/* Tighten top padding so headers sit higher */
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

/* Metric cards: subtle border + shadow */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E3E8EF;
    border-radius: 0.6rem;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05);
}
div[data-testid="stMetricLabel"] p { color: #5B6B7B; font-weight: 600; }

/* Badge pills */
.ui-badge {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.2;
}
.ui-badge-valid   { background: #E6F4EA; color: #137333; }
.ui-badge-invalid { background: #FCE8E6; color: #C5221F; }
.ui-badge-live    { background: #E8F0FE; color: #0A66C2; }
.ui-badge-idle    { background: #EEF1F4; color: #5B6B7B; }
.ui-badge-warning { background: #FEF7E0; color: #B06000; }

/* Empty-state card */
.ui-empty {
    border: 1px dashed #CDD5DF;
    border-radius: 0.7rem;
    padding: 2.2rem 1.5rem;
    text-align: center;
    background: #FBFCFE;
    color: #5B6B7B;
}
.ui-empty h4 { margin: 0 0 0.4rem 0; color: #1D2226; }
.ui-empty p  { margin: 0; font-size: 0.9rem; }

/* Info card (generic) */
.ui-card {
    border: 1px solid #E3E8EF;
    border-radius: 0.6rem;
    padding: 1rem 1.2rem;
    background: #FFFFFF;
}
</style>
"""

_BADGE_CLASS = {
    "valid": "ui-badge-valid",
    "invalid": "ui-badge-invalid",
    "live": "ui-badge-live",
    "idle": "ui-badge-idle",
    "warning": "ui-badge-warning",
}


def inject_theme() -> None:
    """Inject the cosmetic CSS once per page render."""
    st.markdown(_CSS, unsafe_allow_html=True)


def badge(label: str, kind: str = "idle") -> str:
    """Return an HTML badge-pill string. `kind` in valid/invalid/live/idle/warning."""
    cls = _BADGE_CLASS.get(kind, "ui-badge-idle")
    return f'<span class="ui-badge {cls}">{label}</span>'


def render_badge(label: str, kind: str = "idle") -> None:
    """Render a badge pill inline."""
    st.markdown(badge(label, kind), unsafe_allow_html=True)


def render_empty_state(title: str, body: str = "") -> None:
    """Render a friendly empty-state card."""
    st.markdown(
        f'<div class="ui-empty"><h4>{title}</h4><p>{body}</p></div>',
        unsafe_allow_html=True,
    )
