from __future__ import annotations

import html
from collections import Counter
from typing import Any

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
    SpotifyWebApiUnavailableError,
    is_spotify_catalog_id,
    spotify_configured,
    spotify_web_api_available,
)
from agent_hub.agents.music_recommender.genre_categories import classify_genres
from agent_hub.agents.music_recommender.music_scores import (
    artist_score_key,
    load_song_score,
    load_artist_score,
    save_song_score,
    save_artist_score,
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
        _result_genres = getattr(result, "genres", None) or []
        if _result_genres:
            _render_genres_caption(_result_genres)
            _render_categories_caption(_result_genres)
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
    _render_music_score_widget(
        result.spotify_id,
        "song",
        key_prefix=f"{key_prefix}_score",
        title=result.title,
        artist=result.artist,
        genres=getattr(result, "genres", None) or [],
    )


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
        if result.genres:
            _render_genres_caption(result.genres)
            _render_categories_caption(result.genres)
        else:
            st.caption("—")
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
    _render_music_score_widget(
        result.spotify_id,
        "artist",
        key_prefix=f"{key_prefix}_score",
        name=result.name,
        genres=result.genres,
    )


def _render_add_music() -> None:
    liked_song_ids = {s.spotify_id for s in list_liked_songs()}
    disliked_song_ids = {s.spotify_id for s in list_disliked_songs()}
    wishlist_song_ids = {s.spotify_id for s in list_wishlist_songs()}
    liked_artist_ids = {a.spotify_id for a in list_liked_artists() if a.spotify_id}
    disliked_artist_ids = {a.spotify_id for a in list_disliked_artists() if a.spotify_id}
    wishlist_artist_ids = {a.spotify_id for a in list_wishlist_artists()}

    if spotify_configured() and not spotify_web_api_available():
        st.info(
            "Spotify text search is unavailable for this developer account. "
            "Paste a Spotify track or artist link/ID in the search box below."
        )

    st.subheader("Search Songs")
    st.caption(
        "Search Spotify for tracks, or paste a track link/ID "
        "(e.g. open.spotify.com/track/…)."
    )
    track_query = st.text_input("Song search", key="music_track_query")
    if st.button("Search Songs", use_container_width=True, key="music_search_songs_btn"):
        if not track_query.strip():
            st.warning("Enter a song title or artist name to search.")
        else:
            try:
                st.session_state.music_track_results = search_songs(track_query)
            except SpotifyConfigError as exc:
                st.error(str(exc))
            except SpotifyWebApiUnavailableError as exc:
                st.error(str(exc))
                st.session_state.music_track_results = []
            except SpotifyError as exc:
                st.error(str(exc))
                st.session_state.music_track_results = []

    for result in st.session_state.music_track_results:
        _render_song_row(result, liked_song_ids, disliked_song_ids, wishlist_song_ids, "search_song")

    st.divider()

    st.subheader("Search Artists")
    st.caption(
        "Search Spotify for artists, or paste an artist link/ID "
        "(e.g. open.spotify.com/artist/…)."
    )
    artist_query = st.text_input("Artist search", key="music_artist_query")
    if st.button("Search Artists", use_container_width=True, key="music_search_artists_btn"):
        if not artist_query.strip():
            st.warning("Enter an artist name to search.")
        else:
            try:
                st.session_state.music_artist_results = search_artists_query(artist_query)
            except SpotifyConfigError as exc:
                st.error(str(exc))
            except SpotifyWebApiUnavailableError as exc:
                st.error(str(exc))
                st.session_state.music_artist_results = []
            except SpotifyError as exc:
                st.error(str(exc))
                st.session_state.music_artist_results = []

    for result in st.session_state.music_artist_results:
        _render_artist_row(result, liked_artist_ids, disliked_artist_ids, wishlist_artist_ids, "search_artist")


_TASTE_VISIBLE_ITEMS = 10
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


def _render_categories_caption(genres: list[str]) -> None:
    """Derive and display genre categories from a raw genre list."""
    cats = classify_genres(genres)
    if cats:
        st.caption(f"Categories: {', '.join(cats)}")


def _score_display_color(score: int) -> str:
    """Red (0) → yellow (5) → green (10) gradient."""
    score = max(0, min(10, int(score)))
    if score <= 5:
        t = score / 5.0
        r = round(139 + (255 - 139) * t)
        g = round(0 + (200 - 0) * t)
        b = 0
    else:
        t = (score - 5) / 5.0
        r = round(255 + (0 - 255) * t)
        g = round(200 + (100 - 200) * t)
        b = 0
    return f"#{r:02x}{g:02x}{b:02x}"


def _render_score_badge(score: int) -> None:
    color = _score_display_color(score)
    st.markdown(
        f'<div class="music-score-badge" style="color:{color};">{score}'
        f'<span class="music-score-badge-denom">/10</span></div>',
        unsafe_allow_html=True,
    )


def _render_taste_score_badge_css() -> None:
    st.markdown(
        """
        <style>
        .music-score-badge {
            text-align: right;
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1;
            margin-top: 0.15rem;
            white-space: nowrap;
        }
        .music-score-badge-denom {
            font-size: 1.1rem;
            font-weight: 600;
            opacity: 0.85;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_music_score_widget(
    spotify_id: str,
    item_type: str,  # "song" | "artist"
    *,
    key_prefix: str = "music",
    label_hint: str = "Rate 0-10",
    title: str = "",
    artist: str = "",
    name: str = "",
    genres: list[str] | None = None,
    ai_score: float | None = None,
) -> None:
    """0-10 selectbox with auto-save and red flash confirmation."""
    if not spotify_id:
        return
    saved_key = f"{key_prefix}_score_saved_{item_type}_{spotify_id}"
    select_key = f"{key_prefix}_score_select_{item_type}_{spotify_id}"

    current = (
        load_song_score(spotify_id) if item_type == "song" else load_artist_score(spotify_id)
    )
    options = ["—"] + [str(i) for i in range(11)]
    current_index = (current + 1) if current is not None else 0

    score_col, label_col = st.columns([2, 3])
    with score_col:
        chosen = st.selectbox(
            "Rate (0-10)",
            options=options,
            index=current_index,
            key=select_key,
            label_visibility="collapsed",
        )
    with label_col:
        if st.session_state.get(saved_key):
            display_score = current if current is not None else int(chosen)
            st.markdown(
                f'<span style="color:#dc3545;font-weight:600;">✓ {display_score}/10 saved</span>',
                unsafe_allow_html=True,
            )
            st.session_state[saved_key] = False
        else:
            st.caption(label_hint)

    if chosen != "—":
        new_score = int(chosen)
        if new_score != current:
            if item_type == "song":
                save_song_score(
                    spotify_id,
                    new_score,
                    title=title,
                    artist=artist,
                    genres=genres,
                    ai_score=ai_score,
                )
            else:
                save_artist_score(
                    spotify_id,
                    new_score,
                    name=name,
                    genres=genres,
                    ai_score=ai_score,
                )
            st.session_state[saved_key] = True
            st.rerun()


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


def _aggregate_top_genres(
    liked_songs: list[Any],
    liked_artists: list[Any],
    *,
    limit: int = 10,
) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for item in liked_songs:
        for genre in item.genres:
            normalized = genre.strip().lower()
            if not normalized:
                continue
            counts[normalized] += 1
            display.setdefault(normalized, genre.strip())
    for item in liked_artists:
        for genre in item.genres:
            normalized = genre.strip().lower()
            if not normalized:
                continue
            counts[normalized] += 1
            display.setdefault(normalized, genre.strip())
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [display[key] for key, _ in ranked[:limit]]


def _render_taste_hero_css() -> None:
    st.markdown(
        """
        <style>
        .music-taste-hero {
            padding: 1.1rem 1.25rem;
            margin: 0 0 1.25rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(49, 51, 63, 0.12);
        }
        [data-theme="light"] .music-taste-hero {
            background: linear-gradient(135deg, rgba(29, 185, 84, 0.12) 0%, rgba(30, 144, 255, 0.08) 100%);
        }
        [data-theme="dark"] .music-taste-hero {
            background: linear-gradient(135deg, rgba(29, 185, 84, 0.18) 0%, rgba(30, 144, 255, 0.12) 100%);
            border-color: rgba(250, 250, 250, 0.12);
        }
        .music-taste-hero-title {
            font-size: 1.35rem;
            font-weight: 700;
            margin: 0 0 0.75rem;
            line-height: 1.3;
        }
        .music-taste-stat-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.85rem;
        }
        .music-taste-stat {
            display: inline-flex;
            align-items: baseline;
            gap: 0.35rem;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .music-taste-stat small {
            font-size: 0.78rem;
            font-weight: 600;
            opacity: 0.85;
        }
        .music-taste-stat-liked {
            background: rgba(29, 185, 84, 0.18);
            color: #128043;
        }
        [data-theme="dark"] .music-taste-stat-liked {
            color: #6de89a;
        }
        .music-taste-stat-disliked {
            background: rgba(220, 53, 69, 0.14);
            color: #a52834;
        }
        [data-theme="dark"] .music-taste-stat-disliked {
            color: #f28b99;
        }
        .music-taste-genre-label {
            display: block;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            opacity: 0.65;
            margin-bottom: 0.45rem;
        }
        .music-taste-genre-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }
        .music-taste-genre-pill {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 600;
            line-height: 1.3;
        }
        [data-theme="light"] .music-taste-genre-pill {
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid rgba(49, 51, 63, 0.12);
            color: #31333F;
        }
        [data-theme="dark"] .music-taste-genre-pill {
            background: rgba(38, 39, 48, 0.85);
            border: 1px solid rgba(250, 250, 250, 0.12);
            color: #FAFAFA;
        }
        .music-taste-genre-empty {
            font-size: 0.85rem;
            opacity: 0.65;
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_hero(
    liked_songs: list[Any],
    disliked_songs: list[Any],
    liked_artists: list[Any],
    disliked_artists: list[Any],
) -> None:
    _render_taste_hero_css()
    top_genres = _aggregate_top_genres(liked_songs, liked_artists)
    stats = [
        ("liked", len(liked_songs), "liked songs"),
        ("liked", len(liked_artists), "liked artists"),
        ("disliked", len(disliked_songs), "disliked songs"),
        ("disliked", len(disliked_artists), "disliked artists"),
    ]
    stat_html = "".join(
        f'<span class="music-taste-stat music-taste-stat-{kind}">'
        f"{count} <small>{html.escape(label)}</small></span>"
        for kind, count, label in stats
    )
    if top_genres:
        genre_html = (
            '<div class="music-taste-genre-pills">'
            + "".join(
                f'<span class="music-taste-genre-pill">{html.escape(genre)}</span>'
                for genre in top_genres
            )
            + "</div>"
        )
    else:
        genre_html = (
            '<p class="music-taste-genre-empty">'
            "Genres will appear as your library grows."
            "</p>"
        )
    st.markdown(
        f"""
        <div class="music-taste-hero">
            <div class="music-taste-hero-title">Your Taste Profile</div>
            <div class="music-taste-stat-row">{stat_html}</div>
            <span class="music-taste-genre-label">Top genres</span>
            {genre_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_panel_css() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.music-taste-panel-marker-liked) {
            background: rgba(29, 185, 84, 0.06);
            border-left: 3px solid #1db954;
            border-radius: 0.5rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.music-taste-panel-marker-disliked) {
            background: rgba(220, 53, 69, 0.05);
            border-left: 3px solid #dc3545;
            border-radius: 0.5rem;
        }
        [data-theme="dark"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.music-taste-panel-marker-liked) {
            background: rgba(29, 185, 84, 0.1);
        }
        [data-theme="dark"] div[data-testid="stVerticalBlockBorderWrapper"]:has(.music-taste-panel-marker-disliked) {
            background: rgba(220, 53, 69, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_taste_panel_marker(sentiment: str) -> None:
    marker_class = (
        "music-taste-panel-marker-liked"
        if sentiment == "like"
        else "music-taste-panel-marker-disliked"
    )
    st.markdown(
        f'<div class="{marker_class}" style="display:none" aria-hidden="true"></div>',
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
    _render_taste_score_badge_css()
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
                title_col, score_col = st.columns([5, 1])
                with title_col:
                    if stacked_artist:
                        st.markdown(
                            f"**{html.escape(song.title)}**<br>"
                            f'<span class="music-taste-song-artist">'
                            f"{html.escape(song.artist)} ({year})</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"**{song.title}** — {song.artist} ({year})")
                with score_col:
                    song_score = load_song_score(song.spotify_id)
                    if song_score is not None:
                        _render_score_badge(song_score)
                _render_genres_caption(song.genres)
                _render_categories_caption(song.genres)
                _render_music_score_widget(
                    song.spotify_id,
                    "song",
                    key_prefix=f"taste_{sentiment}_song",
                    title=song.title,
                    artist=song.artist,
                    genres=song.genres,
                )
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
    _render_taste_score_badge_css()
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
                score_id = artist_score_key(artist.spotify_id, pandora_id=artist.pandora_id)
                artist_score = load_artist_score(score_id) if score_id else None
                name_col, score_col = st.columns([5, 1])
                with name_col:
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
                with score_col:
                    if artist_score is not None:
                        _render_score_badge(artist_score)
                _render_genres_caption(artist.genres)
                _render_categories_caption(artist.genres)
                _render_music_score_widget(
                    score_id,
                    "artist",
                    key_prefix=f"taste_{sentiment}_artist",
                    name=artist.name,
                    genres=artist.genres,
                )
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


def _render_taste_songs_tab(liked_songs, disliked_songs) -> None:
    _render_taste_section_title("Songs", font_size="calc(1.5em + 4pt)")
    col1, col2 = st.columns(2)
    with col1:
        _render_taste_column_title("Liked Songs")
        with st.container(height=_taste_list_height(songs=True)):
            _render_taste_panel_marker("like")
            _render_taste_song_list(
                "Liked Songs",
                liked_songs,
                "like",
                stacked_artist=True,
                show_letter_index=True,
                show_title=False,
            )
    with col2:
        _render_taste_column_title("Disliked Songs")
        with st.container(height=_taste_list_height(songs=True)):
            _render_taste_panel_marker("dislike")
            _render_taste_song_list(
                "Disliked Songs",
                disliked_songs,
                "dislike",
                show_title=False,
            )


def _render_taste_artists_tab(liked_artists, disliked_artists, config) -> None:
    _render_taste_section_title("Artists")
    col1, col2 = st.columns(2)
    with col1:
        _render_taste_column_title("Liked Artists")
        with st.container(height=_taste_list_height(songs=False)):
            _render_taste_panel_marker("like")
            _render_taste_artist_list(
                "Liked Artists",
                liked_artists,
                "like",
                config,
                show_letter_index=True,
                show_title=False,
            )
    with col2:
        _render_taste_column_title("Disliked Artists")
        with st.container(height=_taste_list_height(songs=False)):
            _render_taste_panel_marker("dislike")
            _render_taste_artist_list(
                "Disliked Artists",
                disliked_artists,
                "dislike",
                config,
                show_title=False,
            )


def _render_my_taste(config) -> None:
    liked_songs = list_liked_songs(config)
    disliked_songs = list_disliked_songs(config)
    liked_artists = list_liked_artists(config)
    disliked_artists = list_disliked_artists(config)

    _render_taste_panel_css()
    _render_taste_column_title_css()
    _render_taste_hero(liked_songs, disliked_songs, liked_artists, disliked_artists)
    st.caption("Songs and artists you've liked or disliked to personalize recommendations.")

    tab_songs, tab_artists = st.tabs(
        [
            f"Songs ({len(liked_songs) + len(disliked_songs)})",
            f"Artists ({len(liked_artists) + len(disliked_artists)})",
        ]
    )
    with tab_songs:
        _render_taste_songs_tab(liked_songs, disliked_songs)
    with tab_artists:
        _render_taste_artists_tab(liked_artists, disliked_artists, config)


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
                _render_music_score_widget(
                    song.spotify_id,
                    "song",
                    key_prefix="wishlist_song",
                    title=song.title,
                    artist=song.artist,
                    genres=song.genres,
                )
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
                _render_music_score_widget(
                    artist.spotify_id,
                    "artist",
                    key_prefix="wishlist_artist",
                    name=artist.name,
                    genres=artist.genres,
                )
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
        except OSError as exc:
            st.session_state.music_recs_status = (
                "error",
                "Spotify connection was interrupted while fetching recommendations. "
                "Wait a minute and try again.",
            )
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
                track_genres = resolve_track_genres(
                    item.track,
                    genre_cache=genre_cache,
                    liked_artists=liked_artists_for_genres,
                )
                _render_genres_caption(track_genres)
                _render_categories_caption(track_genres)
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
                _render_music_score_widget(
                    item.track.spotify_id,
                    "song",
                    key_prefix="rec_song",
                    label_hint="Rate this recommendation",
                    title=item.track.title,
                    artist=item.track.artist,
                    genres=item.track.genres,
                    ai_score=item.score.total,
                )

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
                artist_genres = resolve_display_genres(
                    item.artist.spotify_id,
                    item.artist.name,
                    existing_genres=item.artist.genres,
                    genre_cache=genre_cache,
                    liked_artists=liked_artists_for_genres,
                )
                _render_genres_caption(artist_genres)
                _render_categories_caption(artist_genres)
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
                _render_music_score_widget(
                    item.artist.spotify_id,
                    "artist",
                    key_prefix="rec_artist",
                    label_hint="Rate this recommendation",
                    name=item.artist.name,
                    genres=item.artist.genres,
                    ai_score=item.score.total,
                )


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
