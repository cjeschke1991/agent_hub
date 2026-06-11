from __future__ import annotations

import streamlit as st

from agent_hub.agents.movie_recommender.logic import (
    MovieValidationError,
    RecommendFilters,
    RecommendationError,
    add_movie,
    ensure_db,
    get_tmdb_genres,
    list_disliked,
    list_liked,
    recommend,
    remove_movie,
    search_tmdb,
    tmdb_configured,
)
from agent_hub.agents.movie_recommender.tmdb import TmdbConfigError
from agent_hub.core.config import load_config


def _init_session_state() -> None:
    defaults = {
        "movie_search_query": "",
        "movie_search_results": [],
        "movie_recommendations": [],
        "movie_year_min": 1980,
        "movie_year_max": 2026,
        "movie_rec_count": 10,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _setup_instructions() -> None:
    st.info(
        "TMDB API key required for search and recommendations. "
        "Get a free key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api), "
        "then set `TMDB_API_KEY` in your environment or add `tmdb.api_key` to `config.yaml`."
    )


def _render_taste_list(title: str, movies, sentiment: str) -> None:
    st.markdown(f"**{title}**")
    if not movies:
        st.caption("None yet.")
        return
    for movie in movies:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if movie.poster_url:
                st.image(movie.poster_url, width=60)
        with cols[1]:
            year = movie.year or "—"
            genres = ", ".join(movie.genres[:3]) if movie.genres else "—"
            st.markdown(f"**{movie.title}** ({year})")
            st.caption(genres)
        with cols[2]:
            if st.button("Remove", key=f"movie_remove_{sentiment}_{movie.tmdb_id}"):
                remove_movie(movie.tmdb_id)
                st.rerun()


def _render_search() -> None:
    st.subheader("Add Movies")
    query = st.text_input("Search TMDB", key="movie_search_query")
    if st.button("Search", use_container_width=True):
        if not query.strip():
            st.warning("Enter a movie title to search.")
        else:
            try:
                st.session_state.movie_search_results = search_tmdb(query)
            except TmdbConfigError as exc:
                st.error(str(exc))

    for result in st.session_state.movie_search_results:
        cols = st.columns([1, 4, 1, 1])
        with cols[0]:
            if result.poster_url:
                st.image(result.poster_url, width=60)
        with cols[1]:
            year = result.year or "—"
            st.markdown(f"**{result.title}** ({year})")
            if result.overview:
                st.caption(result.overview[:140] + ("…" if len(result.overview) > 140 else ""))
        with cols[2]:
            if st.button("Like", key=f"movie_like_{result.tmdb_id}"):
                try:
                    add_movie(result.tmdb_id, "like")
                    st.success(f"Added {result.title} to likes.")
                    st.rerun()
                except TmdbConfigError as exc:
                    st.error(str(exc))
        with cols[3]:
            if st.button("Dislike", key=f"movie_dislike_{result.tmdb_id}"):
                try:
                    add_movie(result.tmdb_id, "dislike")
                    st.success(f"Added {result.title} to dislikes.")
                    st.rerun()
                except TmdbConfigError as exc:
                    st.error(str(exc))


def _render_recommendations() -> None:
    st.subheader("Recommendations")
    liked = list_liked()
    genre_options: list[str] = []
    if tmdb_configured():
        try:
            genre_options = [genre["name"] for genre in get_tmdb_genres()]
        except TmdbConfigError as exc:
            st.error(str(exc))

    year_min, year_max = st.slider(
        "Release years",
        min_value=1950,
        max_value=2030,
        value=(st.session_state.movie_year_min, st.session_state.movie_year_max),
    )
    st.session_state.movie_year_min = year_min
    st.session_state.movie_year_max = year_max

    selected_genres = st.multiselect(
        "Genres (leave empty for any genre)",
        options=sorted(genre_options),
        default=[],
    )
    count = st.slider("Number of recommendations", min_value=1, max_value=20, value=st.session_state.movie_rec_count)
    st.session_state.movie_rec_count = count

    recommend_disabled = not liked or not tmdb_configured()
    if not liked:
        st.caption("Add at least one liked movie to get recommendations.")

    if st.button("Get recommendations", use_container_width=True, disabled=recommend_disabled):
        filters = RecommendFilters(
            year_min=year_min,
            year_max=year_max,
            genre_names=selected_genres,
            count=count,
        )
        try:
            st.session_state.movie_recommendations = recommend(filters)
        except (TmdbConfigError, RecommendationError, MovieValidationError) as exc:
            st.error(str(exc))
            st.session_state.movie_recommendations = []

    if not st.session_state.movie_recommendations:
        st.caption("No recommendations yet.")
        return

    for index, item in enumerate(st.session_state.movie_recommendations, start=1):
        cols = st.columns([1, 5])
        with cols[0]:
            if item.movie.poster_url:
                st.image(item.movie.poster_url, use_container_width=True)
        with cols[1]:
            year = item.movie.year or "—"
            genres = ", ".join(item.movie.genres) if item.movie.genres else "—"
            st.markdown(f"**#{index} {item.movie.title}** ({year}) — **Score: {item.score.total}**")
            st.caption(genres)
            breakdown = " · ".join(
                f"{label}: {value:.0f}" for label, value in item.score.as_labels().items()
            )
            st.write(breakdown)
            if item.movie.overview:
                st.write(item.movie.overview)


def render() -> None:
    ensure_db()
    _init_session_state()
    config = load_config()

    st.subheader("Movie Recommender")
    st.caption("Build a taste profile from likes and dislikes, then get ranked TMDB recommendations.")

    if not tmdb_configured():
        _setup_instructions()

    left_col, right_col = st.columns([1, 1])
    with left_col:
        _render_search()
        st.divider()
        _render_taste_list("Liked", list_liked(config), "like")
        st.divider()
        _render_taste_list("Disliked", list_disliked(config), "dislike")

    with right_col:
        _render_recommendations()
