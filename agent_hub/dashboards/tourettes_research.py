"""Tourette's Research dashboard.

Sub-tabs:
  • Influential People   — top 10 most influential people with TS
  • Tips & Strategies    — curated tips organised by category
"""
from __future__ import annotations

import streamlit as st

from agent_hub.agents.tourettes_research.people import PEOPLE
from agent_hub.agents.tourettes_research.tips import CATEGORIES

# ── colour palette for the gradient initials avatar ──────────────────────────
_AVATAR_COLORS = [
    "#6C63FF", "#FF6584", "#43AA8B", "#F8961E",
    "#577590", "#90BE6D", "#F9C74F", "#F94144",
    "#277DA1", "#4D908E",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Influential People sub-tab
# ─────────────────────────────────────────────────────────────────────────────

def _render_person_card(person: dict, idx: int) -> None:
    rank = idx + 1
    with st.expander(f"#{rank} — {person['name']}  ·  {person['field']}", expanded=(idx == 0)):
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


def _render_people_tab() -> None:
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
        key="ts_people_search",
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

    for person in filtered:
        orig_idx = PEOPLE.index(person)
        _render_person_card(person, orig_idx)

    st.markdown("---")
    st.caption(
        "Know someone who should be on this list? "
        "Dynamic entry management is coming — stay tuned."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tips & Strategies sub-tab
# ─────────────────────────────────────────────────────────────────────────────

def _tip_card_html(tip: dict, color: str) -> str:
    title = tip["title"]
    body = tip["body"]
    return (
        f'<div style="'
        f'border-left:4px solid {color};'
        f'background:#fafafa;'
        f'padding:0.75rem 1rem;'
        f'margin-bottom:0.75rem;'
        f'border-radius:0 6px 6px 0;'
        f'">'
        f'<div style="font-weight:600;font-size:0.95rem;margin-bottom:0.3rem;">'
        f'{title}'
        f'</div>'
        f'<div style="font-size:0.88rem;color:#444;line-height:1.5;">'
        f'{body}'
        f'</div>'
        f'</div>'
    )


def _render_tips_tab() -> None:
    st.markdown(
        "Practical, evidence-informed tips for people living with Tourette syndrome, "
        "organised by life area. Expand any category to read the tips."
    )

    # Search box filters across all tips
    search = st.text_input(
        "Search tips",
        placeholder="e.g. sleep, school, medication, anxiety …",
        key="ts_tips_search",
    )
    query = search.strip().lower()

    st.markdown("---")

    # Category selector pills (radio with horizontal layout)
    all_label = "All Categories"
    cat_options = [all_label] + [f"{c['icon']} {c['label']}" for c in CATEGORIES]
    selected = st.radio(
        "Filter by category",
        options=cat_options,
        horizontal=True,
        key="ts_tips_category",
        label_visibility="collapsed",
    )

    st.markdown("")

    total_shown = 0

    for cat in CATEGORIES:
        pill_label = f"{cat['icon']} {cat['label']}"
        if selected != all_label and selected != pill_label:
            continue

        # Filter tips within this category by search query
        if query:
            matching_tips = [
                t for t in cat["tips"]
                if query in t["title"].lower() or query in t["body"].lower()
            ]
        else:
            matching_tips = cat["tips"]

        if not matching_tips:
            continue

        total_shown += len(matching_tips)

        # Category header
        st.markdown(
            f'<div style="'
            f'display:flex;align-items:center;gap:0.5rem;'
            f'margin-bottom:0.25rem;'
            f'">'
            f'<span style="font-size:1.5rem;">{cat["icon"]}</span>'
            f'<span style="font-size:1.1rem;font-weight:700;color:{cat["color"]};">'
            f'{cat["label"]}'
            f'</span>'
            f'</div>'
            f'<div style="font-size:0.85rem;color:#666;margin-bottom:0.75rem;">'
            f'{cat["intro"]}'
            f'</div>',
            unsafe_allow_html=True,
        )

        for tip in matching_tips:
            st.markdown(_tip_card_html(tip, cat["color"]), unsafe_allow_html=True)

        st.markdown("---")

    if total_shown == 0:
        st.warning("No tips match your search. Try a different keyword.")
    else:
        st.caption(f"{total_shown} tip{'s' if total_shown != 1 else ''} shown")


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.subheader("Tourette's Research")

    tab_people, tab_tips = st.tabs([
        "🏆 Influential People",
        "💡 Tips & Strategies",
    ])

    with tab_people:
        _render_people_tab()

    with tab_tips:
        _render_tips_tab()
