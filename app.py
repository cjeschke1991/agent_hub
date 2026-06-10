import streamlit as st

from agent_hub.dashboards import daily_briefing, placeholder

st.set_page_config(page_title="AI Agent Hub", page_icon="🤖", layout="wide")

TABS = [
    ("Daily Briefing", "daily_briefing", True),
    ("Screenshot Organizer", "screenshot_organizer", False),
    ("Gmail / Calendar Assistant", "gmail_calendar", False),
    ("PRI Tracker", "pri_tracker", False),
    ("Pinball Tracker", "pinball_tracker", False),
    ("File Search", "file_search", False),
    ("Finance Summaries", "finance_summaries", False),
]

PLACEHOLDER_COPY = {
    "screenshot_organizer": "Organize screenshots into folders with tags and quick previews.",
    "gmail_calendar": "Assistant for inbox triage and calendar-aware daily planning.",
    "pri_tracker": "Track Programmable Real Estate Investment metrics and milestones.",
    "pinball_tracker": "Log machines, scores, and maintenance for your pinball collection.",
    "file_search": "Fast local file search with agent-assisted ranking.",
    "finance_summaries": "Daily and monthly finance rollups from your data sources.",
}

st.title("AI Agent Hub")
st.caption("Streamlit control surface for local agents, Raycast shortcuts, and scheduled jobs.")

tab_labels = [label for label, _, _ in TABS]
tabs = st.tabs(tab_labels)

for tab, (label, key, enabled) in zip(tabs, TABS):
    with tab:
        if enabled and key == "daily_briefing":
            daily_briefing.render()
        else:
            placeholder.render(label, PLACEHOLDER_COPY.get(key, "Coming soon."))
