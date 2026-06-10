import streamlit as st


def render(title: str, description: str) -> None:
    st.subheader(title)
    st.info(description)
    st.markdown("This tab is a placeholder for a future agent dashboard.")
