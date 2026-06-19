import streamlit as st

from agent_hub.dashboards import daily_briefing, gmail_assistant, movie_recommender, music_recommender, pinball_tracker, placeholder

st.set_page_config(page_title="AI Agent Hub", page_icon="🤖", layout="wide")

TABS = [
    ("Daily Briefing", "daily_briefing"),
    ("Screenshot Organizer", "screenshot_organizer"),
    ("Gmail Assistant", "gmail_assistant"),
    ("PRI Tracker", "pri_tracker"),
    ("Pinball Tracker", "pinball_tracker"),
    ("Movie Recommender", "movie_recommender"),
    ("Music Recommender", "music_recommender"),
    ("File Search", "file_search"),
    ("Finance Summaries", "finance_summaries"),
    ("Health & Fitness", "health_fitness"),
]

ENABLED_TABS = {
    "daily_briefing": daily_briefing.render,
    "gmail_assistant": gmail_assistant.render,
    "pinball_tracker": pinball_tracker.render,
    "movie_recommender": movie_recommender.render,
    "music_recommender": music_recommender.render,
}

PLACEHOLDER_COPY = {
    "screenshot_organizer": "Organize screenshots into folders with tags and quick previews.",
    "gmail_assistant": "Assistant for AI-powered inbox triage and email management.",
    "pri_tracker": "Track Programmable Real Estate Investment metrics and milestones.",
    "file_search": "Fast local file search with agent-assisted ranking.",
    "finance_summaries": "Daily and monthly finance rollups from your data sources.",
    "health_fitness": "Track workouts, nutrition, sleep, and health trends in one place.",
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
