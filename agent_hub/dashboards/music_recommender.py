from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

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
    resolve_display_genres,
    resolve_track_genres,
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
    liked_artist_ids = {a.spotify_id for a in list_liked_artists() if a.spotify_id}
    disliked_artist_ids = {a.spotify_id for a in list_disliked_artists() if a.spotify_id}
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


def _format_genres(genres: list[str]) -> str:
    return ", ".join(genres) if genres else "—"


def _sort_letter(label: str) -> str:
    stripped = label.strip()
    if not stripped:
        return "#"
    first = stripped[0].upper()
    return first if first.isalpha() else "#"


def _group_by_letter(items, label_fn):
    groups: list[tuple[str, list]] = []
    current_letter: str | None = None
    for item in items:
        letter = _sort_letter(label_fn(item))
        if letter != current_letter:
            current_letter = letter
            groups.append((letter, []))
        groups[-1][1].append(item)
    return groups


def _render_letter_index_css() -> None:
    st.markdown(
        """
        <style>
        .music-letter-header {
            padding: 0.15rem 0.5rem;
            margin: 0.5rem 0 0.35rem;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.55;
        }
        .music-letter-spy-bar {
            position: sticky;
            top: 0;
            z-index: 10;
            padding: 0.35rem 0.65rem;
            margin: 0 0 0.5rem;
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            border-bottom: 1px solid rgba(49, 51, 63, 0.15);
        }
        [data-theme="light"] .music-letter-spy-bar {
            background: rgba(255, 255, 255, 0.97);
            color: #31333F;
        }
        [data-theme="dark"] .music-letter-spy-bar {
            background: rgba(38, 39, 48, 0.97);
            color: #FAFAFA;
            border-bottom-color: rgba(250, 250, 250, 0.15);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_letter_header(letter: str, scope_id: str) -> None:
    st.markdown(
        f'<div class="music-letter-header" id="music-letter-{scope_id}-{letter}" '
        f'data-letter="{html.escape(letter)}">{html.escape(letter)}</div>',
        unsafe_allow_html=True,
    )


def _render_letter_scroll_spy(scope_id: str) -> None:
    components.html(
        f"""
        <script>
        (() => {{
            const doc = window.parent.document;
            const scope = {scope_id!r};
            const barClass = "music-letter-spy-bar-" + scope;
            if (doc.querySelector("." + barClass)) return;

            const headers = [...doc.querySelectorAll('[id^="music-letter-' + scope + '-"]')];
            if (!headers.length) return;

            let scrollEl = headers[0].parentElement;
            while (scrollEl && scrollEl !== doc.body) {{
                const style = window.parent.getComputedStyle(scrollEl);
                if (/(auto|scroll)/.test(style.overflowY)) break;
                scrollEl = scrollEl.parentElement;
            }}
            if (!scrollEl) return;

            const letterFrom = (el) => el.dataset.letter || el.textContent.trim();

            const bar = doc.createElement("div");
            bar.className = "music-letter-spy-bar " + barClass;
            bar.textContent = letterFrom(headers[0]);
            scrollEl.insertBefore(bar, scrollEl.firstChild);

            const update = () => {{
                const rootTop = scrollEl.getBoundingClientRect().top + 4;
                let active = headers[0];
                for (const header of headers) {{
                    if (header.getBoundingClientRect().top <= rootTop) {{
                        active = header;
                    }}
                }}
                bar.textContent = letterFrom(active);
            }};

            scrollEl.addEventListener("scroll", update, {{ passive: true }});
            window.parent.addEventListener("resize", update, {{ passive: true }});
            update();
        }})();
        </script>
        """,
        height=0,
    )


def _render_genres_caption(genres: list[str]) -> None:
    st.caption(f"Genres: {_format_genres(genres)}")


def _render_remove_pending_css() -> None:
    st.markdown(
        """
        <style>
        .music-remove-pending {
            background-color: #dc3545 !important;
            color: #ffffff !important;
            border: 1px solid #b02a37 !important;
            border-radius: 0.5rem;
            padding: 0.375rem 0.75rem;
            width: 100%;
            font-size: 1rem;
            line-height: 1.4;
            cursor: not-allowed;
            opacity: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_remove_button(
    *,
    button_key: str,
    item_kind: str,
    item_id: str,
    sentiment: str,
    config=None,
) -> None:
    pending = st.session_state.get("music_pending_removal")
    is_pending = sentiment == "like" and pending == (item_kind, item_id)

    if is_pending:
        _render_remove_pending_css()
        st.markdown(
            '<button class="music-remove-pending" disabled aria-label="Removing">Remove</button>',
            unsafe_allow_html=True,
        )
    elif st.button("Remove", key=button_key):
        if sentiment == "like":
            st.session_state["music_pending_removal"] = (item_kind, item_id)
            st.rerun()
        elif item_kind == "song":
            remove_song(item_id)
            st.rerun()
        else:
            remove_artist(item_id, config=config)
            st.rerun()


def _finalize_pending_taste_removal(item_kind: str, item_ids: set[str], config=None) -> None:
    pending = st.session_state.get("music_pending_removal")
    if not pending or pending[0] != item_kind or pending[1] not in item_ids:
        return
    if not st.session_state.get("music_pending_removal_ack"):
        st.session_state["music_pending_removal_ack"] = True
        st.rerun()
    if item_kind == "song":
        remove_song(pending[1])
    else:
        remove_artist(pending[1], config=config)
    st.session_state.pop("music_pending_removal", None)
    st.session_state.pop("music_pending_removal_ack", None)
    st.rerun()


def _render_rec_names_css() -> None:
    st.markdown(
        """
        <style>
        .music-rec-name { font-size: 1.35em; font-weight: 600; line-height: 1.4; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_section_title_css() -> None:
    st.markdown(
        """
        <style>
        .music-taste-section-title {
            text-align: center;
            font-size: 1.5em;
            font-weight: 700;
            margin: 0.25rem 0 0.75rem;
            line-height: 1.3;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_column_title_css() -> None:
    st.markdown(
        """
        <style>
        .music-taste-column-title {
            text-align: center;
            font-weight: 700;
            margin: 0 0 0.5rem;
            line-height: 1.3;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_column_title(label: str) -> None:
    st.markdown(
        f'<p class="music-taste-column-title">{html.escape(label)}</p>',
        unsafe_allow_html=True,
    )


def _render_taste_section_title(label: str, *, font_size: str = "1.5em") -> None:
    _render_taste_section_title_css()
    st.markdown(
        f'<p class="music-taste-section-title" style="font-size: {font_size};">'
        f"{html.escape(label)}</p>",
        unsafe_allow_html=True,
    )


def _render_taste_song_stacked_css() -> None:
    st.markdown(
        """
        <style>
        .music-taste-song-artist { font-size: 0.85em; line-height: 1.3; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_song_list(
    title: str,
    songs,
    sentiment: str,
    *,
    stacked_artist: bool = False,
    show_letter_index: bool = False,
    show_title: bool = True,
) -> None:
    if show_title:
        st.markdown(f"**{title}**")
    if not songs:
        st.caption("None yet.")
        return
    if stacked_artist:
        _render_taste_song_stacked_css()
    if show_letter_index:
        _render_letter_index_css()
    scope_id = f"song-{sentiment}"
    song_groups = (
        _group_by_letter(songs, lambda song: song.title)
        if show_letter_index
        else [(None, songs)]
    )
    for letter, group_songs in song_groups:
        if letter is not None:
            _render_letter_header(letter, scope_id)
        for song in group_songs:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                if song.image_url:
                    st.image(song.image_url, width=60)
            with cols[1]:
                year = song.year or "—"
                if stacked_artist:
                    st.markdown(
                        f"**{html.escape(song.title)}**<br>"
                        f'<span class="music-taste-song-artist">'
                        f"{html.escape(song.artist)} ({year})</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{song.title}** — {song.artist} ({year})")
                _render_genres_caption(song.genres)
            with cols[2]:
                _render_taste_remove_button(
                    button_key=f"music_remove_song_{sentiment}_{song.spotify_id}",
                    item_kind="song",
                    item_id=song.spotify_id,
                    sentiment=sentiment,
                )
    if show_letter_index:
        _render_letter_scroll_spy(scope_id)
    _finalize_pending_taste_removal("song", {song.spotify_id for song in songs})


def _render_taste_artist_list(
    title: str,
    artists,
    sentiment: str,
    config,
    *,
    show_letter_index: bool = False,
    show_title: bool = True,
) -> None:
    if show_title:
        st.markdown(f"**{title}**")
    if not artists:
        st.caption("None yet.")
        return
    if show_letter_index:
        _render_letter_index_css()
    scope_id = f"artist-{sentiment}"
    artist_groups = (
        _group_by_letter(artists, lambda artist: artist.name)
        if show_letter_index
        else [(None, artists)]
    )
    for letter, group_artists in artist_groups:
        if letter is not None:
            _render_letter_header(letter, scope_id)
        for artist in group_artists:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                if artist.image_url:
                    st.image(artist.image_url, width=60)
            with cols[1]:
                if sentiment == "like":
                    with st.expander(artist.name, expanded=False):
                        top_tracks = list_artist_top_tracks(artist.pandora_id, config=config)
                        if not top_tracks:
                            st.caption("No top tracks stored yet.")
                            if artist.spotify_id and st.button(
                                "Fetch top tracks",
                                key=f"music_fetch_top_tracks_{artist.pandora_id}",
                            ):
                                refresh_artist_top_tracks(artist.pandora_id, config=config)
                                st.rerun()
                        else:
                            for track in top_tracks:
                                year = track.year or "—"
                                st.markdown(f"**{track.rank}. {track.title}** ({year})")
                                if track.album:
                                    st.caption(track.album)
                else:
                    st.markdown(f"**{artist.name}**")
                _render_genres_caption(artist.genres)
            with cols[2]:
                _render_taste_remove_button(
                    button_key=f"music_remove_artist_{sentiment}_{artist.pandora_id}",
                    item_kind="artist",
                    item_id=artist.pandora_id,
                    sentiment=sentiment,
                    config=config,
                )
    if show_letter_index:
        _render_letter_scroll_spy(scope_id)
    _finalize_pending_taste_removal("artist", {artist.pandora_id for artist in artists}, config=config)


def _render_my_taste(config) -> None:
    st.subheader("My Taste Profile")
    st.caption("Songs and artists you've liked or disliked to personalize recommendations.")

    _render_taste_column_title_css()
    _render_taste_section_title("Songs", font_size="calc(1.5em + 4pt)")
    col1, col2 = st.columns(2)
    with col1:
        _render_taste_column_title("Liked Songs")
        with st.container(height=_taste_list_height(songs=True)):
            _render_taste_song_list(
                "Liked Songs",
                list_liked_songs(config),
                "like",
                stacked_artist=True,
                show_letter_index=True,
                show_title=False,
            )
    with col2:
        _render_taste_column_title("Disliked Songs")
        with st.container(height=_taste_list_height(songs=True)):
            _render_taste_song_list(
                "Disliked Songs",
                list_disliked_songs(config),
                "dislike",
                show_title=False,
            )

    st.divider()

    _render_taste_section_title("Artists")
    col3, col4 = st.columns(2)
    with col3:
        _render_taste_column_title("Liked Artists")
        with st.container(height=_taste_list_height(songs=False)):
            _render_taste_artist_list(
                "Liked Artists",
                list_liked_artists(config),
                "like",
                config,
                show_letter_index=True,
                show_title=False,
            )
    with col4:
        _render_taste_column_title("Disliked Artists")
        with st.container(height=_taste_list_height(songs=False)):
            _render_taste_artist_list(
                "Disliked Artists",
                list_disliked_artists(config),
                "dislike",
                config,
                show_title=False,
            )


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
        if not spotify_web_api_available():
            st.caption(
                "Spotify's genre API is unavailable for this developer account — "
                "showing standard genres and tags from your taste profile."
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
                        "No recommendations found. Results come from Spotify embed pages when the "
                        "Web API is blocked. If you recently ran recommendations, wait a minute and "
                        "try again (Spotify may rate-limit embed requests). Liked artists with linked "
                        "Spotify IDs work best.",
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
    liked_artist_ids = {a.spotify_id for a in list_liked_artists() if a.spotify_id}
    disliked_artist_ids = {a.spotify_id for a in list_disliked_artists() if a.spotify_id}

    liked_artists_for_genres = list_liked_artists()
    genre_cache: dict[str, list[str]] = {}

    if song_recs or artist_recs:
        _render_rec_names_css()

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
                    f'<span class="music-rec-name">#{idx} {html.escape(item.track.title)}</span> '
                    f'— <span class="music-rec-name">{html.escape(item.track.artist)}</span> '
                    f"({year}) — <strong>Score: {item.score.total}</strong> &nbsp; "
                    f"<code>{zone_label}</code>",
                    unsafe_allow_html=True,
                )
                st.info(item.reason)
                _render_genres_caption(
                    resolve_track_genres(
                        item.track,
                        genre_cache=genre_cache,
                        liked_artists=liked_artists_for_genres,
                    )
                )
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
                    f'<span class="music-rec-name">#{idx} {html.escape(item.artist.name)}</span> '
                    f"— <strong>Score: {item.score.total}</strong>",
                    unsafe_allow_html=True,
                )
                st.info(item.reason)
                _render_genres_caption(
                    resolve_display_genres(
                        item.artist.spotify_id,
                        item.artist.name,
                        existing_genres=item.artist.genres,
                        genre_cache=genre_cache,
                        liked_artists=liked_artists_for_genres,
                    )
                )
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
