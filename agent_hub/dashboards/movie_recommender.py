from __future__ import annotations

import streamlit as st

from agent_hub.agents.movie_recommender.logic import (
    MovieValidationError,
    RecommendFilters,
    RecommendationError,
    add_movie,
    add_to_wishlist,
    ensure_db,
    get_tmdb_genres,
    list_disliked,
    list_liked,
    list_wishlist,
    recommend,
    remove_from_wishlist,
    remove_movie,
    search_tmdb,
    tmdb_configured,
)
from agent_hub.agents.movie_recommender.omdb import omdb_configured
from agent_hub.agents.movie_recommender.tmdb import TmdbConfigError
from agent_hub.core.config import load_config


def _init_session_state() -> None:
    defaults = {
        "movie_search_query": "",
        "movie_search_results": [],
        "movie_recommendations": [],
        "movie_recommendations_loading": False,
        "movie_pending_filters": None,
        "movie_kids_only": False,
        "movie_year_min": 1980,
        "movie_year_max": 2026,
        "movie_rec_count": 10,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _setup_instructions() -> None:
    st.info(
        "TMDB API key required for search, genres, and recommendations. "
        "OMDb alone is not enough — you need **both** keys for full functionality.\n\n"
        "1. Get a free TMDB key at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)\n"
        "2. Add to a `.env` file in the project root (recommended):\n"
        "   `TMDB_API_KEY=your-key` and `OMDB_API_KEY=your-key`\n"
        "3. Restart Streamlit (`agent_hub`) from the same environment"
    )


def _render_api_status() -> None:
    tmdb_ok = tmdb_configured()
    omdb_ok = omdb_configured()
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.markdown(f"**TMDB:** {'✅ configured' if tmdb_ok else '❌ missing (required)'}")
    with status_col2:
        st.markdown(f"**OMDb:** {'✅ configured' if omdb_ok else '⚪ optional (Rotten Tomatoes)'}")


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


def _add_wishlist_action(tmdb_id: int, title: str) -> None:
    try:
        add_to_wishlist(tmdb_id)
        st.success(f"Added {title} to wishlist.")
        st.rerun()
    except TmdbConfigError as exc:
        st.error(str(exc))


def _render_wishlist_list(movies) -> None:
    if not movies:
        st.caption("Your wishlist is empty. Add movies from Search or Recommendations.")
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
            for label, value in movie.to_details().metadata_display().items():
                st.caption(f"{label}: {value}")
        with cols[2]:
            if st.button("Remove", key=f"movie_wishlist_remove_{movie.tmdb_id}"):
                remove_from_wishlist(movie.tmdb_id)
                st.rerun()


def _render_search() -> None:
    st.caption("Search TMDB and mark movies as liked, disliked, or add them to your wishlist.")
    query = st.text_input("Search TMDB", key="movie_search_query")
    if st.button("Search", use_container_width=True):
        if not query.strip():
            st.warning("Enter a movie title to search.")
        else:
            try:
                st.session_state.movie_search_results = search_tmdb(query)
            except TmdbConfigError as exc:
                st.error(str(exc))

    liked_ids = {movie.tmdb_id for movie in list_liked()}
    disliked_ids = {movie.tmdb_id for movie in list_disliked()}
    wishlist_ids = {movie.tmdb_id for movie in list_wishlist()}

    for result in st.session_state.movie_search_results:
        cols = st.columns([1, 3, 1, 1, 1])
        with cols[0]:
            if result.poster_url:
                st.image(result.poster_url, width=60)
        with cols[1]:
            year = result.year or "—"
            st.markdown(f"**{result.title}** ({year})")
            if result.overview:
                st.caption(result.overview[:140] + ("…" if len(result.overview) > 140 else ""))
        with cols[2]:
            if st.button(
                "Like",
                key=f"movie_like_{result.tmdb_id}",
                type="primary" if result.tmdb_id in liked_ids else "secondary",
            ):
                try:
                    add_movie(result.tmdb_id, "like")
                    st.success(f"Added {result.title} to likes.")
                    st.rerun()
                except TmdbConfigError as exc:
                    st.error(str(exc))
        with cols[3]:
            if st.button(
                "Dislike",
                key=f"movie_dislike_{result.tmdb_id}",
                type="primary" if result.tmdb_id in disliked_ids else "secondary",
            ):
                try:
                    add_movie(result.tmdb_id, "dislike")
                    st.success(f"Added {result.title} to dislikes.")
                    st.rerun()
                except TmdbConfigError as exc:
                    st.error(str(exc))
        with cols[4]:
            if st.button(
                "Add to wishlist",
                key=f"movie_wishlist_search_{result.tmdb_id}",
                type="primary" if result.tmdb_id in wishlist_ids else "secondary",
            ):
                _add_wishlist_action(result.tmdb_id, result.title)


def _recommendations_loading_css() -> None:
    st.markdown(
        """
        <style>
        .st-key-movie_get_recs button {
            background-color: #2563eb !important;
            border-color: #2563eb !important;
            color: #ffffff !important;
        }
        .st-key-movie_get_recs button:disabled {
            background-color: #2563eb !important;
            border-color: #2563eb !important;
            color: #ffffff !important;
            opacity: 0.95 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_add_movies() -> None:
    _render_search()


def _render_my_taste(config) -> None:
    st.subheader("My Taste Profile")
    st.caption("Movies you've marked as liked or disliked to personalize recommendations.")
    _render_taste_list("Liked", list_liked(config), "like")
    st.divider()
    _render_taste_list("Disliked", list_disliked(config), "dislike")


def _render_wishlist(config) -> None:
    st.subheader("Wishlist")
    st.caption("Movies you want to watch.")
    _render_wishlist_list(list_wishlist(config))


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

    selected_genres: list[str] = []
    if not tmdb_configured():
        st.caption("Genre filter unavailable until TMDB API key is configured.")
    elif genre_options:
        selected_genres = st.multiselect(
            "Genres (leave empty for any genre)",
            options=sorted(genre_options),
            default=[],
        )
    else:
        st.caption("Could not load genres from TMDB. Check your API key and try restarting the app.")
    count = st.slider("Number of recommendations", min_value=1, max_value=20, value=st.session_state.movie_rec_count)
    st.session_state.movie_rec_count = count

    kids_only = st.toggle(
        "Kids movies only",
        value=st.session_state.movie_kids_only,
        help="When on, only Family and Animation films are recommended.",
    )
    st.session_state.movie_kids_only = kids_only

    recommend_disabled = (
        not liked or not tmdb_configured() or st.session_state.movie_recommendations_loading
    )
    if not liked:
        st.caption("Add at least one liked movie in the **Add Movies** tab to get recommendations.")

    if st.session_state.movie_recommendations_loading:
        _recommendations_loading_css()

    if st.button(
        "Get recommendations",
        key="movie_get_recs",
        use_container_width=True,
        disabled=recommend_disabled,
    ):
        st.session_state.movie_recommendations_loading = True
        st.session_state.movie_pending_filters = RecommendFilters(
            year_min=year_min,
            year_max=year_max,
            genre_names=selected_genres,
            count=count,
            kids_only=kids_only,
        )
        st.rerun()

    if st.session_state.movie_recommendations_loading and st.session_state.movie_pending_filters:
        pending = st.session_state.movie_pending_filters
        try:
            with st.spinner("Getting recommendations..."):
                st.session_state.movie_recommendations = recommend(pending)
        except (TmdbConfigError, RecommendationError, MovieValidationError) as exc:
            st.error(str(exc))
            st.session_state.movie_recommendations = []
        st.session_state.movie_recommendations_loading = False
        st.session_state.movie_pending_filters = None
        st.rerun()

    if not st.session_state.movie_recommendations:
        st.caption("No recommendations yet.")
        return

    wishlist_ids = {movie.tmdb_id for movie in list_wishlist()}

    for index, item in enumerate(st.session_state.movie_recommendations, start=1):
        cols = st.columns([1, 5])
        with cols[0]:
            if item.movie.poster_url:
                st.image(item.movie.poster_url, use_container_width=True)
        with cols[1]:
            year = item.movie.year or "—"
            st.markdown(f"**#{index} {item.movie.title}** ({year}) — **Score: {item.score.total}**")
            st.info(item.reason)
            for label, value in item.movie.metadata_display().items():
                st.markdown(f"**{label}:** {value}")
            breakdown = " · ".join(
                f"{label}: {value:.0f}" for label, value in item.score.as_labels().items()
            )
            st.write(breakdown)
            if item.movie.overview:
                st.write(item.movie.overview)
            if st.button(
                "Add to wishlist",
                key=f"movie_wishlist_rec_{item.movie.tmdb_id}",
                type="primary" if item.movie.tmdb_id in wishlist_ids else "secondary",
            ):
                _add_wishlist_action(item.movie.tmdb_id, item.movie.title)


def render() -> None:
    ensure_db()
    _init_session_state()
    config = load_config()

    st.subheader("Movie Recommender")
    st.caption("Build a taste profile from likes and dislikes, then get ranked TMDB recommendations.")
    _render_api_status()

    if not tmdb_configured():
        _setup_instructions()
    elif not omdb_configured():
        st.caption(
            "Tip: set `OMDB_API_KEY` so recommendations use Rotten Tomatoes scores in ranking and display "
            "(free key at omdbapi.com/apikey.aspx)."
        )

    sub_tabs = st.tabs(["Recommendations", "Add Movies", "My Taste", "Wishlist"])
    with sub_tabs[0]:
        _render_recommendations()
    with sub_tabs[1]:
        _render_add_movies()
    with sub_tabs[2]:
        _render_my_taste(config)
    with sub_tabs[3]:
        _render_wishlist(config)
