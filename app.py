import streamlit as st

from agent_hub.dashboards import daily_briefing, pinball_tracker, placeholder

st.set_page_config(page_title="AI Agent Hub", page_icon="🤖", layout="wide")

TABS = [
    ("Daily Briefing", "daily_briefing"),
    ("Screenshot Organizer", "screenshot_organizer"),
    ("Gmail / Calendar Assistant", "gmail_calendar"),
    ("PRI Tracker", "pri_tracker"),
    ("Pinball Tracker", "pinball_tracker"),
    ("File Search", "file_search"),
    ("Finance Summaries", "finance_summaries"),
]

ENABLED_TABS = {
    "daily_briefing": daily_briefing.render,
    "pinball_tracker": pinball_tracker.render,
}

PLACEHOLDER_COPY = {
    "screenshot_organizer": "Organize screenshots into folders with tags and quick previews.",
    "gmail_calendar": "Assistant for inbox triage and calendar-aware daily planning.",
    "pri_tracker": "Track Programmable Real Estate Investment metrics and milestones.",
    "file_search": "Fast local file search with agent-assisted ranking.",
    "finance_summaries": "Daily and monthly finance rollups from your data sources.",
}

st.title("AI Agent Hub")
st.caption("Streamlit control surface for local agents, Raycast shortcuts, and scheduled jobs.")

tab_labels = [label for label, _ in TABS]
tabs = st.tabs(tab_labels)

for tab, (label, key) in zip(tabs, TABS):
    with tab:
        render = ENABLED_TABS.get(key)
        if render:
            render()
        else:
            placeholder.render(label, PLACEHOLDER_COPY.get(key, "Coming soon."))
