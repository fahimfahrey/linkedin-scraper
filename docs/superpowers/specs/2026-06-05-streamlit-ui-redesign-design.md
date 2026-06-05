# Streamlit UI/UX Full Redesign — Design Spec

**Date:** 2026-06-05
**Status:** Approved (design), pending implementation plan
**Scope:** Full redesign of the LinkedIn Lead Scraper control center UI, staying Streamlit-native (light theming, minimal custom CSS).

## Goal

Transform the current single-page, 3-tab `app.py` into a focused multipage Streamlit
application with a coherent information architecture, native theming, real-time live
monitoring via fragments, and richer data exploration — without leaving the Streamlit
framework or relying on heavy custom CSS.

Decisions captured from brainstorming:

- **Depth:** Full redesign (rethink IA, add views/components).
- **Style:** Keep Streamlit-native — native theme via `config.toml`, light CSS only.
- **Priority areas:** All four — Analytics/data, Live monitoring, Input & auth, Global shell.
- **Architecture:** Native multipage app (`st.navigation` / `st.Page`).

Target Streamlit version: **1.58.0** (confirmed installed). All required native features
available: `st.navigation`/`st.Page`, `st.fragment(run_every=)`, `st.status`,
`st.dialog`, `st.dataframe` `column_config`, native theming, `st.switch_page`.

## Architecture & File Layout

```
app.py                 # thin entry: theme inject, st.navigation, shared state init (~40 lines)
.streamlit/config.toml # native theme tokens
app_state.py           # NEW: session-state init + worker message-drain helpers
ui_theme.py            # NEW: CSS injection helper + reusable HTML snippets (cards, badges)
ui_helpers.py          # KEEP + grow: shared render components, metric calc, df prep, states
export_helpers.py      # KEEP unchanged
database.py            # KEEP unchanged
pages/
  1_dashboard.py       # KPI overview, charts, recent activity
  2_collect.py         # URL input, validation, queue → spawn worker
  3_live_monitor.py    # real-time progress (fragment auto-refresh)
  4_data.py            # profile table + filters + export + detail dialog
  5_settings.py        # auth/session status, interactive login, config readout
```

Rules:

- `app.py` shrinks from 334 lines to a thin entry point. Each page is focused and
  independently testable.
- Shared session-state init and the worker message-drain loop move out of `app.py`
  into `app_state.py`, called from the entry point / pages as needed.
- `st.navigation` sidebar groups:
  - **Overview** → Dashboard
  - **Operate** → Collect, Live Monitor
  - **Manage** → Data, Settings
- Session-status badge + "Launch Interactive Login" shortcut stay pinned in the sidebar
  (custom, rendered below the native nav).

## Data Model (existing, unchanged)

Table `linkedin_profiles`:
`id, linkedin_url, full_name, headline, location, current_company, about_text,
experience_json, education_json, collected_at`.

Implications:

- `linkedin_url` → `st.column_config.LinkColumn` in the data table.
- No profile-picture column exists → **no avatar/ImageColumn** (explicitly out of scope).
- `about_text`, `experience_json`, `education_json` → rendered in the profile detail dialog.

## Per-Page UX

### Dashboard (landing)

- Four KPI metric cards: Total Profiles, New Today, Avg Jobs/Profile, Active Collection
  (live/idle badge).
- "Collection over time" line chart — profiles grouped by collect-date (`st.line_chart`).
- "Top companies" bar chart — top 8 by count (`st.bar_chart`).
- Recent 5 profiles mini-list.
- Primary CTA button → Collect page (`st.switch_page`).

### Collect

- URL textarea + live count metric.
- Validation split: green "N valid" / red "M invalid", invalid lines listed in an expander.
- Inputs disabled while a collection is active (guard preserved).
- "Queue for Scraping" spawns the worker, then `st.switch_page` to Live Monitor.
- Paste-help / sample expander.

### Live Monitor

- `@st.fragment(run_every=2)` panel — auto-refreshes only the monitor, every 2 seconds.
  Replaces the current fragile `time.sleep` + `st.rerun` polling loop (app.py:99-136).
- Progress bar (collected / total) + three metrics: Collected, Remaining, Elapsed.
- `st.status` activity stream (last 15 entries), severity-colored warnings
  (critical/warning/info).
- Cancel button (terminates worker, clears active flag).
- Idle state → empty-state card pointing to Collect.

### Data

- Filter row: company multiselect + free-text search (name/headline) + row-limit input.
- `st.dataframe` with `column_config`:
  - `LinkColumn` on `linkedin_url`.
  - `ProgressColumn` (or numeric) for Jobs / Degrees counts.
  - Formatted `collected_at`.
- Row selection → `@st.dialog("Profile")` detail view: name, headline, location, company,
  LinkedIn link, about text, parsed experience list, parsed education list.
- Export toolbar: CSV + Excel download buttons (existing `export_helpers`).

### Settings

- Session-status card: valid/invalid badge, expiry, file size, Refresh button.
- "Launch Interactive Login" (existing `SessionManager.interactive_login`).
- Read-only config readout: chromium path, execution window.

## Theme

`.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#0A66C2"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F3F6F9"
textColor = "#1D2226"
font = "sans serif"
baseRadius = "0.6rem"
```

`ui_theme.py` provides a single `inject_theme()` that adds light CSS only for:

- Metric-card borders / subtle shadow.
- Badge pills: valid / invalid / live / idle.
- Section spacing.

No layout hacks, no overriding Streamlit internals beyond cosmetics.

## Live Monitor Mechanics

- Worker message-drain logic extracted to `app_state.drain_worker_messages()`
  (parses `StatusUpdate`, `ProfilePayload`, `OperationWarning`, `ExecutionComplete`).
- The Live Monitor panel is wrapped in `@st.fragment(run_every=2)`; it drains messages
  and re-renders only itself. When `collection_active` is false, the fragment renders the
  idle state and does not schedule further refreshes.
- This removes the brittle global `time.sleep(0.01)` + `st.rerun()` loop, so inputs on
  other pages are not interrupted by the refresh cycle.

## States (apply to every page)

- **Empty:** No profiles / no active collection → friendly card with a CTA, not a bare
  `st.info`.
- **Loading:** `st.spinner` / `st.status` around auth launch and DB load.
- **Error:** DB load or session-validation failures surface via `st.error` with a short
  cause. No silent failures.

## Testing

- **Unit (no Streamlit runtime):** metric calculation, dataframe prep, validation split,
  badge rendering helpers. Extend existing `tests/`.
- **Smoke (`streamlit.testing.v1.AppTest`):** each page renders without exception and key
  widgets are present.
- All existing tests must stay green.

## Out of Scope

- Avatar / profile-image columns (no source data).
- Framework change away from Streamlit.
- Dark mode (chose native light theme).
- New scraping/backend functionality — this is a UI/UX redesign only.

## Migration Notes

- Behavior of worker spawning, session validation, export, and DB access is preserved;
  only their presentation and the page they live on changes.
- `app.py` becomes the navigation entry point; the current monolithic body is split into
  `pages/` and `app_state.py`.
