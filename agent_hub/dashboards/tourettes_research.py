"""Tourette's Research dashboard.

Displays the top 10 most influential people with Tourette syndrome,
with a summary of each person's influence and their top 3 motivational facts.
"""
from __future__ import annotations

import streamlit as st

from agent_hub.agents.tourettes_research.people import PEOPLE

# ── colour palette for the gradient initials avatar ──────────────────────────
_AVATAR_COLORS = [
    "#6C63FF", "#FF6584", "#43AA8B", "#F8961E",
    "#577590", "#90BE6D", "#F9C74F", "#F94144",
    "#277DA1", "#4D908E",
]


def _initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else parts[0][:2].upper()


def _avatar_html(name: str, idx: int) -> str:
    color = _AVATAR_COLORS[idx % len(_AVATAR_COLORS)]
    initials = _initials(name)
    return (
        f'<div style="'
        f'width:64px;height:64px;border-radius:50%;background:{color};'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:1.4rem;font-weight:700;color:white;'
        f'flex-shrink:0;margin-right:1rem;'
        f'">{initials}</div>'
    )


def _render_person_card(person: dict, idx: int) -> None:
    rank = idx + 1
    with st.expander(f"#{rank} — {person['name']}  ·  {person['field']}", expanded=(idx == 0)):
        # Header row: avatar + summary
        col_a, col_b = st.columns([1, 5])
        with col_a:
            st.markdown(_avatar_html(person["name"], idx), unsafe_allow_html=True)
        with col_b:
            st.markdown(
                f"**Born:** {person['born']}  \n"
                f"**Field:** {person['field']}"
            )

        st.markdown("---")
        st.markdown("#### Why They Are Influential")
        st.markdown(person["summary"])

        st.markdown("#### Top 3 Motivational Facts")
        for i, fact in enumerate(person["motivational"], start=1):
            st.markdown(
                f'<div style="'
                f'background:#f0f4ff;border-left:4px solid #6C63FF;'
                f'padding:0.6rem 0.8rem;margin-bottom:0.6rem;border-radius:4px;'
                f'">'
                f'<strong>{i}.</strong> {fact}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.caption(f"Source: {person['source']}")


def render() -> None:
    st.subheader("Tourette's Research")
    st.markdown(
        "A curated look at the **top 10 most influential people** who have lived with "
        "Tourette syndrome — athletes, entertainers, educators, and historical figures "
        "who shaped their fields and changed perceptions of TS."
    )

    st.info(
        "Content is curated and fact-checked. "
        "Dynamic entry management (add/edit/remove people) is planned for a future update.",
        icon="ℹ️",
    )

    st.markdown("---")

    search = st.text_input(
        "Filter by name or field",
        placeholder="e.g. athlete, musician, actor …",
        key="ts_search",
    )
    query = search.strip().lower()

    filtered = [
        p for p in PEOPLE
        if not query
        or query in p["name"].lower()
        or query in p["field"].lower()
        or query in p["summary"].lower()
    ]

    if not filtered:
        st.warning("No entries match your search.")
        return

    st.caption(f"Showing {len(filtered)} of {len(PEOPLE)} entries")

    for idx, person in enumerate(filtered):
        # Use original index for consistent avatar colours regardless of filter
        orig_idx = PEOPLE.index(person)
        _render_person_card(person, orig_idx)

    st.markdown("---")
    st.caption(
        "Know someone who should be on this list? "
        "Dynamic entry management is coming — stay tuned."
    )
