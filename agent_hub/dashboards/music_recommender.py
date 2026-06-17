from __future__ import annotations

import streamlit as st

from agent_hub.agents.music_recommender.logic import (
    MusicRecommendFilters,
    MusicRecommendationError,
    MusicValidationError,
    add_artist,
    add_artist_to_wishlist,
    add_song,
    add_song_to_wishlist,
    ensure_db,
    get_spotify_genres,
    list_artist_top_tracks,
    list_disliked_artists,
    list_disliked_songs,
    list_liked_artists,
    list_liked_songs,
    list_wishlist_artists,
    list_wishlist_songs,
    recommend,
    refresh_artist_top_tracks,
    remove_artist,
    remove_artist_from_wishlist,
    remove_song,
    remove_song_from_wishlist,
    search_artists_query,
    search_songs,
)
from agent_hub.agents.music_recommender.spotify import (
    SpotifyConfigError,
    SpotifyError,
    is_spotify_catalog_id,
    spotify_configured,
    spotify_web_api_available,
)
from agent_hub.core.config import load_config


def _init_session_state() -> None:
    defaults: dict = {
        "music_track_query": "",
        "music_track_results": [],
        "music_artist_query": "",
        "music_artist_results": [],
        "music_song_recs": [],
        "music_artist_recs": [],
        "music_recs_loading": False,
        "music_pending_filters": None,
        "music_year_range": (1980, 2026),
        "music_song_count": 10,
        "music_artist_count": 10,
        "music_energy_range": (0.0, 1.0),
        "music_valence_range": (0.0, 1.0),
        "music_include_energy": True,
        "music_include_valence": True,
        "music_include_year": True,
        "music_recs_status": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.music_recs_loading and not st.session_state.music_pending_filters:
        st.session_state.music_recs_loading = False


def _setup_instructions() -> None:
    st.info(
        "Spotify credentials are required for search and recommendations.\n\n"
        "1. Create a free app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)\n"
        "2. Copy the **Client ID** and **Client Secret**\n"
        "3. Add to a `.env` file in the project root:\n"
        "   `SPOTIFY_CLIENT_ID=your-id`\n"
        "   `SPOTIFY_CLIENT_SECRET=your-secret`\n"
        "4. Restart Streamlit"
    )


def _render_api_status() -> None:
    ok = spotify_configured()
    st.markdown(f"**Spotify:** {'✅ configured' if ok else '❌ missing (required)'}")


def _loading_css() -> None:
    st.markdown(
        """
        <style>
        .st-key-music_get_recs button {
            background-color: #2563eb !important;
            border-color: #2563eb !important;
            color: #ffffff !important;
        }
        .st-key-music_get_recs button:disabled {
            opacity: 0.45 !important;
            cursor: not-allowed !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _add_song_wishlist(spotify_id: str, title: str) -> None:
    try:
        add_song_to_wishlist(spotify_id)
        st.success(f"Added '{title}' to song wishlist.")
        st.rerun()
    except SpotifyConfigError as exc:
        st.error(str(exc))


def _add_artist_wishlist(spotify_id: str, name: str) -> None:
    try:
        add_artist_to_wishlist(spotify_id)
        st.success(f"Added {name} to artist wishlist.")
        st.rerun()
    except SpotifyConfigError as exc:
        st.error(str(exc))


def _render_song_row(
    result,
    liked_ids: set[str],
    disliked_ids: set[str],
    wishlist_ids: set[str],
    key_prefix: str,
) -> None:
    cols = st.columns([1, 3, 1, 1, 1])
    with cols[0]:
        if result.image_url:
            st.image(result.image_url, width=60)
    with cols[1]:
        year = result.year or "—"
        st.markdown(f"**{result.title}** — {result.artist} ({year})")
        if result.album:
            st.caption(result.album)
    with cols[2]:
        if st.button(
            "Like",
            key=f"{key_prefix}_like_{result.spotify_id}",
            type="primary" if result.spotify_id in liked_ids else "secondary",
        ):
            try:
                add_song(result.spotify_id, "like")
                st.success(f"Liked '{result.title}'.")
                st.rerun()
            except SpotifyConfigError as exc:
                st.error(str(exc))
    with cols[3]:
        if st.button(
            "Dislike",
            key=f"{key_prefix}_dislike_{result.spotify_id}",
            type="primary" if result.spotify_id in disliked_ids else "secondary",
        ):
            try:
                add_song(result.spotify_id, "dislike")
                st.success(f"Disliked '{result.title}'.")
                st.rerun()
            except SpotifyConfigError as exc:
                st.error(str(exc))
    with cols[4]:
        if st.button(
            "Wishlist",
            key=f"{key_prefix}_wl_{result.spotify_id}",
            type="primary" if result.spotify_id in wishlist_ids else "secondary",
        ):
            _add_song_wishlist(result.spotify_id, result.title)


def _render_artist_row(
    result,
    liked_ids: set[str],
    disliked_ids: set[str],
    wishlist_ids: set[str],
    key_prefix: str,
) -> None:
    cols = st.columns([1, 3, 1, 1, 1])
    with cols[0]:
        if result.image_url:
            st.image(result.image_url, width=60)
    with cols[1]:
        st.markdown(f"**{result.name}**")
        genres = ", ".join(result.genres[:3]) if result.genres else "—"
        st.caption(genres)
    with cols[2]:
        if st.button(
            "Like",
            key=f"{key_prefix}_like_{result.spotify_id}",
            type="primary" if result.spotify_id in liked_ids else "secondary",
        ):
            try:
                add_artist(result.spotify_id, "like")
                st.success(f"Liked {result.name}.")
                st.rerun()
            except SpotifyConfigError as exc:
                st.error(str(exc))
    with cols[3]:
        if st.button(
            "Dislike",
            key=f"{key_prefix}_dislike_{result.spotify_id}",
            type="primary" if result.spotify_id in disliked_ids else "secondary",
        ):
            try:
                add_artist(result.spotify_id, "dislike")
                st.success(f"Disliked {result.name}.")
                st.rerun()
            except SpotifyConfigError as exc:
                st.error(str(exc))
    with cols[4]:
        if st.button(
            "Wishlist",
            key=f"{key_prefix}_wl_{result.spotify_id}",
            type="primary" if result.spotify_id in wishlist_ids else "secondary",
        ):
            _add_artist_wishlist(result.spotify_id, result.name)


def _render_add_music() -> None:
    liked_song_ids = {s.spotify_id for s in list_liked_songs()}
    disliked_song_ids = {s.spotify_id for s in list_disliked_songs()}
    wishlist_song_ids = {s.spotify_id for s in list_wishlist_songs()}
    liked_artist_ids = {a.spotify_id for a in list_liked_artists()}
    disliked_artist_ids = {a.spotify_id for a in list_disliked_artists()}
    wishlist_artist_ids = {a.spotify_id for a in list_wishlist_artists()}

    st.subheader("Search Songs")
    st.caption("Search Spotify for tracks, then like, dislike, or add to your wishlist.")
    track_query = st.text_input("Song search", key="music_track_query")
    if st.button("Search Songs", use_container_width=True, key="music_search_songs_btn"):
        if not track_query.strip():
            st.warning("Enter a song title or artist name to search.")
        else:
            try:
                st.session_state.music_track_results = search_songs(track_query)
            except SpotifyConfigError as exc:
                st.error(str(exc))

    for result in st.session_state.music_track_results:
        _render_song_row(result, liked_song_ids, disliked_song_ids, wishlist_song_ids, "search_song")

    st.divider()

    st.subheader("Search Artists")
    st.caption("Search Spotify for artists, then like, dislike, or add to your wishlist.")
    artist_query = st.text_input("Artist search", key="music_artist_query")
    if st.button("Search Artists", use_container_width=True, key="music_search_artists_btn"):
        if not artist_query.strip():
            st.warning("Enter an artist name to search.")
        else:
            try:
                st.session_state.music_artist_results = search_artists_query(artist_query)
            except SpotifyConfigError as exc:
                st.error(str(exc))

    for result in st.session_state.music_artist_results:
        _render_artist_row(result, liked_artist_ids, disliked_artist_ids, wishlist_artist_ids, "search_artist")


_TASTE_VISIBLE_ITEMS = 8
_TASTE_SONG_ROW_PX = 78
_TASTE_ARTIST_ROW_PX = 72


def _taste_list_height(*, songs: bool) -> int:
    row_px = _TASTE_SONG_ROW_PX if songs else _TASTE_ARTIST_ROW_PX
    return _TASTE_VISIBLE_ITEMS * row_px


def _render_taste_song_list(title: str, songs, sentiment: str) -> None:
    st.markdown(f"**{title}**")
    if not songs:
        st.caption("None yet.")
        return
    for song in songs:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if song.image_url:
                st.image(song.image_url, width=60)
        with cols[1]:
            year = song.year or "—"
            st.markdown(f"**{song.title}** — {song.artist} ({year})")
            genres = ", ".join(song.genres[:3]) if song.genres else "—"
            st.caption(genres)
        with cols[2]:
            if st.button("Remove", key=f"music_remove_song_{sentiment}_{song.spotify_id}"):
                remove_song(song.spotify_id)
                st.rerun()


def _render_taste_artist_list(title: str, artists, sentiment: str, config) -> None:
    st.markdown(f"**{title}**")
    if not artists:
        st.caption("None yet.")
        return
    for artist in artists:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if artist.image_url:
                st.image(artist.image_url, width=60)
        with cols[1]:
            if sentiment == "like":
                with st.expander(artist.name, expanded=False):
                    top_tracks = list_artist_top_tracks(artist.spotify_id, config=config)
                    if not top_tracks:
                        st.caption("No top tracks stored yet.")
                        if is_spotify_catalog_id(artist.spotify_id) and st.button(
                            "Fetch top tracks",
                            key=f"music_fetch_top_tracks_{artist.spotify_id}",
                        ):
                            refresh_artist_top_tracks(artist.spotify_id, config=config)
                            st.rerun()
                    else:
                        for track in top_tracks:
                            year = track.year or "—"
                            st.markdown(f"**{track.rank}. {track.title}** ({year})")
                            if track.album:
                                st.caption(track.album)
            else:
                st.markdown(f"**{artist.name}**")
            genres = ", ".join(artist.genres[:3]) if artist.genres else "—"
            st.caption(genres)
        with cols[2]:
            if st.button("Remove", key=f"music_remove_artist_{sentiment}_{artist.spotify_id}"):
                remove_artist(artist.spotify_id, config=config)
                st.rerun()


def _render_my_taste(config) -> None:
    st.subheader("My Taste Profile")
    st.caption("Songs and artists you've liked or disliked to personalize recommendations.")

    st.markdown("**Songs**")
    with st.container(height=_taste_list_height(songs=True)):
        col1, col2 = st.columns(2)
        with col1:
            _render_taste_song_list("Liked Songs", list_liked_songs(config), "like")
        with col2:
            _render_taste_song_list("Disliked Songs", list_disliked_songs(config), "dislike")

    st.divider()

    st.markdown("**Artists**")
    with st.container(height=_taste_list_height(songs=False)):
        col3, col4 = st.columns(2)
        with col3:
            _render_taste_artist_list("Liked Artists", list_liked_artists(config), "like", config)
        with col4:
            _render_taste_artist_list("Disliked Artists", list_disliked_artists(config), "dislike", config)


def _render_wishlist(config) -> None:
    st.subheader("Wishlist")
    st.caption("Songs and artists you want to listen to.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Songs**")
        songs = list_wishlist_songs(config)
        if not songs:
            st.caption("No songs wishlisted yet.")
        for song in songs:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                if song.image_url:
                    st.image(song.image_url, width=60)
            with cols[1]:
                year = song.year or "—"
                st.markdown(f"**{song.title}** — {song.artist} ({year})")
                if song.genres:
                    st.caption(", ".join(song.genres[:3]))
                af = {}
                if song.energy is not None:
                    af["Energy"] = f"{song.energy:.0%}"
                if song.valence is not None:
                    af["Mood"] = f"{song.valence:.0%}"
                if song.tempo is not None:
                    af["BPM"] = f"{song.tempo:.0f}"
                if af:
                    st.caption(" · ".join(f"{k}: {v}" for k, v in af.items()))
            with cols[2]:
                if st.button("Remove", key=f"music_wl_rm_song_{song.spotify_id}"):
                    remove_song_from_wishlist(song.spotify_id)
                    st.rerun()

    with col2:
        st.markdown("**Artists**")
        artists = list_wishlist_artists(config)
        if not artists:
            st.caption("No artists wishlisted yet.")
        for artist in artists:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                if artist.image_url:
                    st.image(artist.image_url, width=60)
            with cols[1]:
                st.markdown(f"**{artist.name}**")
                if artist.genres:
                    st.caption(", ".join(artist.genres[:3]))
                if artist.followers:
                    st.caption(f"{artist.followers:,} followers")
            with cols[2]:
                if st.button("Remove", key=f"music_wl_rm_artist_{artist.spotify_id}"):
                    remove_artist_from_wishlist(artist.spotify_id)
                    st.rerun()


def _render_recommendations() -> None:
    st.subheader("Recommendations")

    liked_songs = list_liked_songs()
    liked_artists = list_liked_artists()
    has_taste = bool(liked_songs or liked_artists)

    year_col, year_toggle_col = st.columns([5, 1])
    with year_toggle_col:
        include_year = st.toggle(
            "Include",
            key="music_include_year",
            help="When off, release year is ignored for filtering and scoring.",
        )
    with year_col:
        year_min, year_max = st.slider(
            "Release years",
            min_value=1950,
            max_value=2030,
            key="music_year_range",
            disabled=not include_year,
        )

    genre_options: list[str] = []
    if spotify_configured():
        try:
            genre_options = get_spotify_genres()
        except SpotifyConfigError as exc:
            st.error(str(exc))

    selected_genres: list[str] = []
    if not spotify_configured():
        st.caption("Genre filter unavailable until Spotify credentials are configured.")
    elif genre_options:
        selected_genres = st.multiselect(
            "Genres (leave empty for any genre)",
            options=sorted(genre_options),
            default=[],
        )
    else:
        st.caption(
            "Could not load genres from Spotify. Check your credentials and try restarting the app."
        )

    energy_col, energy_toggle_col = st.columns([5, 1])
    with energy_toggle_col:
        include_energy = st.toggle(
            "Include",
            key="music_include_energy",
            help="When off, energy is ignored for Spotify filters and scoring.",
        )
    with energy_col:
        energy_min, energy_max = st.slider(
            "Energy (0 = chill, 1 = intense)",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            key="music_energy_range",
            disabled=not include_energy,
        )

    valence_col, valence_toggle_col = st.columns([5, 1])
    with valence_toggle_col:
        include_valence = st.toggle(
            "Include",
            key="music_include_valence",
            help="When off, mood is ignored for Spotify filters and scoring.",
        )
    with valence_col:
        valence_min, valence_max = st.slider(
            "Mood (0 = melancholic, 1 = upbeat)",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            key="music_valence_range",
            disabled=not include_valence,
        )

    col_song_count, col_artist_count = st.columns(2)
    with col_song_count:
        song_count = st.slider(
            "Songs to recommend",
            min_value=1,
            max_value=20,
            key="music_song_count",
        )
    with col_artist_count:
        artist_count = st.slider(
            "Artists to recommend",
            min_value=1,
            max_value=20,
            key="music_artist_count",
        )

    recommend_disabled = not has_taste or not spotify_configured() or st.session_state.music_recs_loading

    if recommend_disabled and not st.session_state.music_recs_loading:
        if not has_taste:
            st.warning(
                "Add at least one liked song or artist in the **Add Music** tab before getting recommendations."
            )
        elif not spotify_configured():
            st.warning("Spotify credentials are required for recommendations.")

    if st.session_state.music_recs_loading:
        _loading_css()

    if st.button(
        "Get recommendations",
        key="music_get_recs",
        use_container_width=True,
        disabled=recommend_disabled,
    ):
        st.session_state.music_recs_status = None
        st.session_state.music_recs_loading = True
        st.session_state.music_pending_filters = MusicRecommendFilters(
            year_min=year_min,
            year_max=year_max,
            genre_names=selected_genres or None,
            song_count=song_count,
            artist_count=artist_count,
            energy_min=energy_min,
            energy_max=energy_max,
            valence_min=valence_min,
            valence_max=valence_max,
            include_energy=include_energy,
            include_valence=include_valence,
            include_year=include_year,
        )
        st.rerun()

    if st.session_state.music_recs_loading and st.session_state.music_pending_filters:
        pending = st.session_state.music_pending_filters
        try:
            with st.spinner("Getting recommendations…"):
                songs, artists = recommend(pending)
            st.session_state.music_song_recs = songs
            st.session_state.music_artist_recs = artists
            if not songs and not artists:
                if selected_genres:
                    st.session_state.music_recs_status = (
                        "warning",
                        "No songs matched your filters. Embed-based discovery does not include "
                        "genre tags — clear the **Genres** filter and try again.",
                    )
                elif not spotify_web_api_available():
                    st.session_state.music_recs_status = (
                        "warning",
                        "No recommendations found. Spotify's Web API is blocked for this developer "
                        "account, so results come from public embed pages. Add liked songs with "
                        "real Spotify IDs (via search or playlist import) for best results.",
                    )
                else:
                    st.session_state.music_recs_status = (
                        "warning",
                        "No songs or artists matched your filters. Try widening the year range, "
                        "clearing genre filters, or adding more liked music.",
                    )
            else:
                st.session_state.music_recs_status = None
        except (SpotifyConfigError, MusicRecommendationError, MusicValidationError, SpotifyError) as exc:
            st.session_state.music_recs_status = ("error", str(exc))
            st.session_state.music_song_recs = []
            st.session_state.music_artist_recs = []
        except Exception as exc:
            st.session_state.music_recs_status = (
                "error",
                f"Unexpected error while fetching recommendations: {exc}",
            )
            st.session_state.music_song_recs = []
            st.session_state.music_artist_recs = []
        finally:
            st.session_state.music_recs_loading = False
            st.session_state.music_pending_filters = None
        st.rerun()

    status = st.session_state.music_recs_status
    if status:
        kind, message = status
        if kind == "error":
            st.error(message)
        elif kind == "warning":
            st.warning(message)
        else:
            st.info(message)

    song_recs = st.session_state.music_song_recs
    artist_recs = st.session_state.music_artist_recs

    if not song_recs and not artist_recs:
        if not status:
            st.caption("No recommendations yet — click **Get recommendations** above.")
        return

    wishlist_song_ids = {s.spotify_id for s in list_wishlist_songs()}
    wishlist_artist_ids = {a.spotify_id for a in list_wishlist_artists()}
    liked_song_ids = {s.spotify_id for s in list_liked_songs()}
    disliked_song_ids = {s.spotify_id for s in list_disliked_songs()}
    liked_artist_ids = {a.spotify_id for a in list_liked_artists()}
    disliked_artist_ids = {a.spotify_id for a in list_disliked_artists()}

    _ZONE_BADGE: dict[str, str] = {
        "safe": "🟢 Safe",
        "stretch": "🟡 Stretch",
        "wild_card": "🔴 Wild Card",
    }

    if song_recs:
        st.markdown("### Songs")
        for idx, item in enumerate(song_recs, start=1):
            cols = st.columns([1, 5])
            with cols[0]:
                if item.track.image_url:
                    st.image(item.track.image_url, use_container_width=True)
            with cols[1]:
                year = item.track.year or "—"
                zone_label = _ZONE_BADGE.get(getattr(item, "zone", "safe"), "🟢 Safe")
                st.markdown(
                    f"**#{idx} {item.track.title}** — {item.track.artist} ({year}) "
                    f"— **Score: {item.score.total}** &nbsp; `{zone_label}`"
                )
                st.info(item.reason)
                genres = ", ".join(item.track.genres[:4]) if item.track.genres else "—"
                st.markdown(f"**Genres:** {genres}")
                af = item.track.audio_features_display()
                if af:
                    st.markdown("  ".join(f"**{k}:** {v}" for k, v in af.items()))
                breakdown = " · ".join(
                    f"{k}: {v:.0f}" for k, v in item.score.as_labels().items()
                )
                st.caption(breakdown)
                like_col, dislike_col, wl_col = st.columns([1, 1, 1])
                with like_col:
                    if st.button(
                        "Like",
                        key=f"music_rec_song_like_{item.track.spotify_id}",
                        type="primary" if item.track.spotify_id in liked_song_ids else "secondary",
                    ):
                        try:
                            add_song(item.track.spotify_id, "like")
                            st.success(f"Liked '{item.track.title}'.")
                            st.rerun()
                        except SpotifyConfigError as exc:
                            st.error(str(exc))
                with dislike_col:
                    if st.button(
                        "Dislike",
                        key=f"music_rec_song_dislike_{item.track.spotify_id}",
                        type="primary" if item.track.spotify_id in disliked_song_ids else "secondary",
                    ):
                        try:
                            add_song(item.track.spotify_id, "dislike")
                            st.success(f"Disliked '{item.track.title}'.")
                            st.rerun()
                        except SpotifyConfigError as exc:
                            st.error(str(exc))
                with wl_col:
                    if st.button(
                        "Add to wishlist",
                        key=f"music_rec_song_wl_{item.track.spotify_id}",
                        type="primary" if item.track.spotify_id in wishlist_song_ids else "secondary",
                    ):
                        _add_song_wishlist(item.track.spotify_id, item.track.title)

    if artist_recs:
        st.markdown("### Artists")
        for idx, item in enumerate(artist_recs, start=1):
            cols = st.columns([1, 5])
            with cols[0]:
                if item.artist.image_url:
                    st.image(item.artist.image_url, use_container_width=True)
            with cols[1]:
                st.markdown(
                    f"**#{idx} {item.artist.name}** — **Score: {item.score.total}**"
                )
                st.info(item.reason)
                genres = ", ".join(item.artist.genres[:4]) if item.artist.genres else "—"
                st.markdown(f"**Genres:** {genres}")
                if item.artist.followers:
                    st.markdown(f"**Followers:** {item.artist.followers:,}")
                breakdown = " · ".join(
                    f"{k}: {v:.0f}" for k, v in item.score.as_labels().items()
                )
                st.caption(breakdown)
                like_col, dislike_col, wl_col = st.columns([1, 1, 1])
                with like_col:
                    if st.button(
                        "Like",
                        key=f"music_rec_artist_like_{item.artist.spotify_id}",
                        type="primary" if item.artist.spotify_id in liked_artist_ids else "secondary",
                    ):
                        try:
                            add_artist(item.artist.spotify_id, "like")
                            st.success(f"Liked {item.artist.name}.")
                            st.rerun()
                        except SpotifyConfigError as exc:
                            st.error(str(exc))
                with dislike_col:
                    if st.button(
                        "Dislike",
                        key=f"music_rec_artist_dislike_{item.artist.spotify_id}",
                        type="primary" if item.artist.spotify_id in disliked_artist_ids else "secondary",
                    ):
                        try:
                            add_artist(item.artist.spotify_id, "dislike")
                            st.success(f"Disliked {item.artist.name}.")
                            st.rerun()
                        except SpotifyConfigError as exc:
                            st.error(str(exc))
                with wl_col:
                    if st.button(
                        "Add to wishlist",
                        key=f"music_rec_artist_wl_{item.artist.spotify_id}",
                        type="primary" if item.artist.spotify_id in wishlist_artist_ids else "secondary",
                    ):
                        _add_artist_wishlist(item.artist.spotify_id, item.artist.name)


def render() -> None:
    ensure_db()
    _init_session_state()
    config = load_config()

    st.subheader("Music Recommender")
    st.caption("Build a taste profile from liked songs and artists, then get Spotify-powered recommendations.")
    _render_api_status()

    if not spotify_configured():
        _setup_instructions()
        return

    sub_tabs = st.tabs(["Recommendations", "Add Music", "My Taste", "Wishlist"])
    with sub_tabs[0]:
        _render_recommendations()
    with sub_tabs[1]:
        _render_add_music()
    with sub_tabs[2]:
        _render_my_taste(config)
    with sub_tabs[3]:
        _render_wishlist(config)
