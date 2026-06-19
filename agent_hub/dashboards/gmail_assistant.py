from __future__ import annotations

import os
from typing import Any

import streamlit as st

from agent_hub.agents.gmail_assistant.analysis_cache import (
    analysis_cache_count,
    clear_analysis_cache,
)
from agent_hub.agents.gmail_assistant.auth import (
    get_gmail_service,
    gmail_credentials_configured,
    revoke_gmail_token,
)
from agent_hub.agents.gmail_assistant.llm import CATEGORIES, EmailResult
from agent_hub.agents.gmail_assistant.logic import (
    clear_inbox_snapshot,
    delete_email_and_learn,
    keep_email_and_learn,
    load_and_analyze_inbox,
    load_inbox_snapshot,
    rebuild_inbox_from_cache,
)
from agent_hub.agents.gmail_assistant.prefs import (
    GmailPrefs,
    load_prefs,
    record_low_value,
    record_protected,
    record_vip,
    save_prefs,
)
from agent_hub.core.config import load_config

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
<style>
.gmail-card {
    background: #1a1a2e;
    border: 1px solid #2d2d44;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.gmail-card:hover { border-color: #5a5af0; }

.gmail-subject {
    font-size: 1.05rem;
    font-weight: 600;
    color: #e8e8f0;
    margin-bottom: 2px;
}
.gmail-meta {
    font-size: 0.78rem;
    color: #888;
    margin-bottom: 6px;
}
.gmail-summary {
    font-size: 0.88rem;
    color: #bbb;
    line-height: 1.5;
}
.gmail-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 6px;
}
.badge-high   { background:#3d1a1a; color:#f87171; }
.badge-med    { background:#2d2508; color:#facc15; }
.badge-low    { background:#1a2a1a; color:#4ade80; }
.badge-cat    { background:#1e1e3a; color:#818cf8; }
.badge-delete { background:#3d1a1a; color:#f87171; }
.badge-action { background:#1a2a3a; color:#38bdf8; }
.badge-deadline { background:#2a1a3a; color:#c084fc; }
.badge-urgency { background:#1a1a1a; color:#aaa; font-weight:400; }

.gmail-section-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #e0e0f0;
    margin-top: 8px;
    margin-bottom: 12px;
}
.gmail-hero {
    background: linear-gradient(135deg, #1a1a3e 0%, #0d0d24 100%);
    border: 1px solid #3a3a5c;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
}
.gmail-hero-stat {
    text-align: center;
}
.gmail-hero-stat .value {
    font-size: 2rem;
    font-weight: 800;
    color: #818cf8;
}
.gmail-hero-stat .label {
    font-size: 0.78rem;
    color: #888;
    margin-top: 2px;
}
.gmail-delete-pending,
.gmail-action-pending {
    background: #7f1d1d !important;
    color: #fca5a5 !important;
    border: 1px solid #ef4444 !important;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 0.75rem;
    cursor: default;
    white-space: nowrap;
}
</style>
"""

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    config = load_config()

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        st.warning(
            "**OPENAI_API_KEY** not set — add it to your `.env` file to enable AI analysis.",
            icon="⚠️",
        )

    if not gmail_credentials_configured(config):
        _render_setup_guide()
        return

    _render_main(config)


# ---------------------------------------------------------------------------
# Setup / onboarding
# ---------------------------------------------------------------------------

def _render_setup_guide() -> None:
    st.markdown("## Gmail Assistant — Setup Required")
    st.info(
        "To use the Gmail Assistant you need a Google Cloud OAuth credentials file "
        "(`client_secret.json`). Follow the steps below, then restart the app.",
        icon="ℹ️",
    )
    with st.expander("Setup instructions", expanded=True):
        st.markdown(
            """
1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Gmail API** for the project.
3. Under **APIs & Services → Credentials**, create an **OAuth 2.0 Client ID** (Desktop app).
4. Download the JSON file (e.g. `client_secret.json`).
5. Add the path to your `.env` file:
   ```
   GMAIL_CREDENTIALS_PATH=/path/to/client_secret.json
   ```
6. Also add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...
   ```
7. Restart the app and come back to this tab — it will prompt you to sign in with Google.
"""
        )


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

def _render_main(config) -> None:
    if "gmail_summary" not in st.session_state:
        # Try snapshot first (exact last fetch), then rebuild from analysis cache
        # so the user sees their emails instantly without hitting Gmail.
        snapshot = load_inbox_snapshot(config)
        if snapshot is None:
            snapshot = rebuild_inbox_from_cache(config)
        if snapshot is not None:
            st.session_state["gmail_summary"] = snapshot

    tab_inbox, tab_suggested, tab_categories, tab_prefs = st.tabs(
        ["📥 Inbox", "🗑️ Suggested Deletes", "📂 Categories", "⚙️ Preferences"]
    )

    with tab_inbox:
        _render_inbox_tab(config)

    with tab_suggested:
        _render_suggested_deletes_tab(config)

    with tab_categories:
        _render_categories_tab(config)

    with tab_prefs:
        _render_prefs_tab(config)


# ---------------------------------------------------------------------------
# Inbox tab
# ---------------------------------------------------------------------------

def _render_inbox_tab(config) -> None:
    st.markdown('<div class="gmail-section-title">Your Inbox</div>', unsafe_allow_html=True)

    col_fetch, col_clear, col_revoke = st.columns([2, 1, 1])
    with col_fetch:
        fetch_clicked = st.button("Fetch & Analyze Inbox", type="primary")
    with col_clear:
        cache_count = analysis_cache_count(config)
        if st.button(
            "Clear Analysis Cache",
            help=(
                "Delete saved AI analyses on disk. Your last inbox view stays until you fetch again. "
                "The next fetch will re-run AI on every email."
            ),
        ):
            removed = clear_analysis_cache(config)
            st.session_state.pop("gmail_summary", None)
            clear_inbox_snapshot(config)
            st.success(
                f"Cleared {removed} cached analysis(es). "
                "Click **Fetch & Analyze Inbox** for fresh results."
            )
            st.rerun()
        elif cache_count:
            st.caption(f"{cache_count} AI analyses on disk")
    with col_revoke:
        if st.button("Sign out of Google", help="Delete stored OAuth token"):
            revoke_gmail_token(config)
            st.session_state.pop("gmail_summary", None)
            clear_inbox_snapshot(config)
            st.success("Signed out. Click 'Fetch & Analyze' to sign in again.")
            st.rerun()

    if fetch_clicked:
        with st.spinner("Fetching inbox from Gmail…"):
            try:
                service = get_gmail_service(config)
                summary = load_and_analyze_inbox(service, config=config)
                st.session_state["gmail_summary"] = summary
                st.session_state["gmail_service"] = service
            except Exception as exc:
                st.error(f"Failed to load inbox: {exc}")
                return

    summary = st.session_state.get("gmail_summary")
    if summary is None:
        st.caption("Click **Fetch & Analyze Inbox** to load your emails.")
        return

    if summary.priority:
        st.markdown('<div class="gmail-section-title">Priority — Must Read Today</div>', unsafe_allow_html=True)
        for result in summary.priority:
            _render_email_card(result, config, compact=True, key_prefix="priority")
        st.divider()

    # Hero stats
    n_total = len(summary.results)
    n_delete = len(summary.suggested_deletes)
    avg_imp = (
        sum(r.importance for r in summary.results) / n_total if n_total else 0
    )
    cache_note = ""
    if summary.cached_count or summary.analyzed_count:
        cache_note = (
            f"<div class='gmail-hero-stat'>"
            f"<div class='value'>{summary.cached_count}</div>"
            f"<div class='label'>From cache</div></div>"
            f"<div class='gmail-hero-stat'>"
            f"<div class='value'>{summary.analyzed_count}</div>"
            f"<div class='label'>Newly analyzed</div></div>"
        )
    st.markdown(
        f"""
        <div class="gmail-hero">
          <div style="display:flex; gap:40px; justify-content:center;">
            <div class="gmail-hero-stat"><div class="value">{n_total}</div><div class="label">Emails analyzed</div></div>
            <div class="gmail-hero-stat"><div class="value">{n_delete}</div><div class="label">Suggested deletes</div></div>
            <div class="gmail-hero-stat"><div class="value">{avg_imp:.1f}</div><div class="label">Avg importance</div></div>
            {cache_note}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filter bar
    col_cat, col_imp = st.columns(2)
    with col_cat:
        filter_cats = st.multiselect(
            "Filter by category", CATEGORIES, key="gmail_filter_cats"
        )
    with col_imp:
        min_imp = st.slider("Minimum importance", 0, 10, 0, key="gmail_filter_imp")

    results = summary.results
    if filter_cats:
        results = [r for r in results if r.category in filter_cats]
    if min_imp > 0:
        results = [r for r in results if r.importance >= min_imp]

    if not results:
        st.info("No emails match the current filters.")
        return

    for result in results:
        _render_email_card(result, config, key_prefix="inbox")


# ---------------------------------------------------------------------------
# Suggested deletes tab
# ---------------------------------------------------------------------------

def _render_suggested_deletes_tab(config) -> None:
    st.markdown(
        '<div class="gmail-section-title">Suggested Deletes</div>', unsafe_allow_html=True
    )
    summary = st.session_state.get("gmail_summary")
    if summary is None:
        st.caption("Fetch your inbox first (go to the **Inbox** tab).")
        return

    deletes = summary.suggested_deletes
    if not deletes:
        st.success("No emails are suggested for deletion right now.")
        return

    st.caption(
        f"{len(deletes)} email(s) flagged by the AI as safe to delete. "
        "Review and confirm below."
    )

    # Bulk delete
    if st.button(f"Delete all {len(deletes)} suggested emails", type="primary"):
        service = st.session_state.get("gmail_service")
        if service:
            with st.spinner("Deleting…"):
                errors = 0
                for r in deletes:
                    try:
                        delete_email_and_learn(service, r, config=config)
                    except Exception:
                        errors += 1
            # Refresh
            with st.spinner("Refreshing inbox…"):
                try:
                    summary2 = load_and_analyze_inbox(service, config=config)
                    st.session_state["gmail_summary"] = summary2
                except Exception:
                    st.session_state.pop("gmail_summary", None)
            msg = f"Deleted {len(deletes) - errors} email(s)."
            if errors:
                msg += f" {errors} failed."
            st.success(msg)
            st.rerun()

    for result in deletes:
        _render_email_card(result, config, show_delete_reason=True, key_prefix="suggested")


# ---------------------------------------------------------------------------
# Categories tab
# ---------------------------------------------------------------------------

def _render_categories_tab(config) -> None:
    st.markdown('<div class="gmail-section-title">By Category</div>', unsafe_allow_html=True)
    summary = st.session_state.get("gmail_summary")
    if summary is None:
        st.caption("Fetch your inbox first (go to the **Inbox** tab).")
        return

    for cat in CATEGORIES:
        emails = summary.by_category.get(cat, [])
        if not emails:
            continue
        with st.expander(f"{cat}  ({len(emails)})", expanded=False):
            for result in emails:
                _render_email_card(result, config, key_prefix=f"cat_{cat}")


# ---------------------------------------------------------------------------
# Preferences tab
# ---------------------------------------------------------------------------

def _render_prefs_tab(config) -> None:
    st.markdown('<div class="gmail-section-title">Preferences</div>', unsafe_allow_html=True)
    st.caption(
        "Teach the assistant which senders matter most, which to ignore, and which keywords signal urgency."
    )

    prefs = load_prefs(config)

    with st.form("gmail_prefs_form"):
        vip_senders_raw = st.text_area(
            "VIP senders (always high importance, never delete)",
            value="\n".join(prefs.vip_senders),
            height=80,
        )
        keep_senders_raw = st.text_area(
            "Protected senders (never delete)",
            value="\n".join(prefs.keep_senders),
            height=80,
        )
        delete_senders_raw = st.text_area(
            "Low-value senders (safe to delete)",
            value="\n".join(prefs.delete_senders),
            height=80,
        )
        boost_keywords_raw = st.text_area(
            "Important keywords (boost urgency, one per line)",
            value="\n".join(prefs.boost_keywords),
            height=80,
        )
        delete_subjects_raw = st.text_area(
            "Delete if subject contains (one keyword per line)",
            value="\n".join(prefs.delete_subjects),
            height=80,
        )
        notes = st.text_area(
            "Additional preference notes (free text)",
            value=prefs.notes,
            height=80,
        )
        saved = st.form_submit_button("Save preferences")

    if saved:
        new_prefs = GmailPrefs(
            vip_senders=[s.strip().lower() for s in vip_senders_raw.splitlines() if s.strip()],
            keep_senders=[s.strip().lower() for s in keep_senders_raw.splitlines() if s.strip()],
            delete_senders=[s.strip().lower() for s in delete_senders_raw.splitlines() if s.strip()],
            boost_keywords=[s.strip() for s in boost_keywords_raw.splitlines() if s.strip()],
            delete_subjects=[s.strip() for s in delete_subjects_raw.splitlines() if s.strip()],
            notes=notes.strip(),
            sender_reputation=prefs.sender_reputation,
        )
        save_prefs(new_prefs, config)
        st.success("Preferences saved! They will be used on the next inbox fetch.")


# ---------------------------------------------------------------------------
# Email card
# ---------------------------------------------------------------------------

def _pending_action(
    *,
    pending_key: str,
    pending_label: str,
    button_label: str,
    button_key: str,
    action,
    success_toast: str,
    config,
    result: EmailResult,
) -> None:
    """Render a button that turns red while a preference action runs."""
    is_pending = st.session_state.get(pending_key, False)

    if is_pending:
        st.markdown(
            f'<button class="gmail-action-pending" disabled>{pending_label}</button>',
            unsafe_allow_html=True,
        )
        try:
            action(result.sender, config=config)
            st.toast(success_toast)
        except Exception as exc:
            st.error(str(exc))
        finally:
            st.session_state.pop(pending_key, None)
            st.rerun()
    elif st.button(button_label, key=button_key):
        st.session_state[pending_key] = True
        st.rerun()


def _importance_badge(score: int) -> str:
    if score >= 7:
        cls = "badge-high"
        label = f"⚡ {score}"
    elif score >= 4:
        cls = "badge-med"
        label = f"● {score}"
    else:
        cls = "badge-low"
        label = f"○ {score}"
    return f'<span class="gmail-badge {cls}">{label}</span>'


def _render_email_card(
    result: EmailResult,
    config,
    show_delete_reason: bool = False,
    compact: bool = False,
    *,
    key_prefix: str = "card",
) -> None:
    pending_key = f"gmail_pending_delete_{result.msg_id}"
    is_pending = st.session_state.get(pending_key, False)
    del_key = f"{key_prefix}_del_{result.msg_id}"
    keep_key = f"{key_prefix}_keep_{result.msg_id}"

    badge_imp = _importance_badge(result.importance)
    badge_cat = f'<span class="gmail-badge badge-cat">{result.category}</span>'
    badge_action = (
        '<span class="gmail-badge badge-action">Action needed</span>'
        if result.requires_action
        else ""
    )
    badge_deadline = (
        f'<span class="gmail-badge badge-deadline">Due: {result.deadline}</span>'
        if result.deadline
        else ""
    )

    delete_hint = ""
    if show_delete_reason and result.delete_reason:
        delete_hint = f'<span class="gmail-badge badge-delete">🗑 {result.delete_reason}</span>'

    urgency_line = ""
    if result.urgency_reason:
        urgency_line = f'<div class="gmail-badge badge-urgency">{result.urgency_reason}</div>'

    with st.container():
        st.markdown(
            f"""
            <div class="gmail-card">
              <div class="gmail-subject">{result.subject}</div>
              <div class="gmail-meta">From: {result.sender} &nbsp;·&nbsp; {result.date}</div>
              <div style="margin-bottom:6px;">{badge_imp}{badge_cat}{badge_action}{badge_deadline}{delete_hint}</div>
              <div class="gmail-summary">{result.summary}</div>
              {urgency_line}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if compact:
            return

        col_vip, col_prot, col_low, col_del, col_keep = st.columns(5)

        with col_vip:
            _pending_action(
                pending_key=f"gmail_pending_vip_{result.msg_id}",
                pending_label="Adding VIP…",
                button_label="VIP Sender",
                button_key=f"{key_prefix}_vip_{result.msg_id}",
                action=record_vip,
                success_toast=f"Added {result.sender} to VIP senders.",
                config=config,
                result=result,
            )

        with col_prot:
            _pending_action(
                pending_key=f"gmail_pending_prot_{result.msg_id}",
                pending_label="Protecting…",
                button_label="Protected Sender",
                button_key=f"{key_prefix}_prot_{result.msg_id}",
                action=record_protected,
                success_toast=f"Added {result.sender} to protected senders.",
                config=config,
                result=result,
            )

        with col_low:
            _pending_action(
                pending_key=f"gmail_pending_low_{result.msg_id}",
                pending_label="Marking low-value…",
                button_label="Low-Value Sender",
                button_key=f"{key_prefix}_low_{result.msg_id}",
                action=record_low_value,
                success_toast=f"Added {result.sender} to low-value senders.",
                config=config,
                result=result,
            )

        with col_del:
            if is_pending:
                st.markdown(
                    '<button class="gmail-action-pending" disabled>Deleting…</button>',
                    unsafe_allow_html=True,
                )
            elif st.button("🗑 Delete", key=del_key):
                service = st.session_state.get("gmail_service")
                if service:
                    st.session_state[pending_key] = True
                    st.rerun()

        with col_keep:
            if st.button("Keep ✓", key=keep_key):
                keep_email_and_learn(result, config=config)
                st.toast(f"Marked to keep emails from {result.sender}.")

        if is_pending:
            service = st.session_state.get("gmail_service")
            if service:
                try:
                    delete_email_and_learn(service, result, config=config)
                    st.toast("Email moved to trash.")
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")
                finally:
                    st.session_state.pop(pending_key, None)
                    # Remove from summary
                    summary = st.session_state.get("gmail_summary")
                    if summary:
                        summary.results = [r for r in summary.results if r.msg_id != result.msg_id]
                        summary.suggested_deletes = [
                            r for r in summary.suggested_deletes if r.msg_id != result.msg_id
                        ]
                        for cat in summary.by_category:
                            summary.by_category[cat] = [
                                r for r in summary.by_category[cat] if r.msg_id != result.msg_id
                            ]
                    st.rerun()
