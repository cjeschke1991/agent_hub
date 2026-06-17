"""
Backfill top 5 Spotify tracks for all liked artists.

For artists with real Spotify IDs, fetches directly. For Pandora/synthetic IDs,
resolves a catalog artist ID from liked songs (embed metadata) when possible.
"""
from __future__ import annotations

import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_hub.agents.music_recommender.logic import (  # noqa: E402
    TasteArtist,
    TasteSong,
    list_artist_top_tracks,
    list_liked_artists,
    list_liked_songs,
    refresh_artist_top_tracks_from_catalog,
    resolve_catalog_id_from_sibling_artists,
    resolve_manual_catalog_artist_id,
)
from agent_hub.agents.music_recommender.spotify import (  # noqa: E402
    SpotifyError,
    fetch_track_details_from_embed,
    is_spotify_catalog_id,
)

_MUSICBRAINZ_USER_AGENT = "agent-hub/1.0 (music-recommender-backfill)"


def _clean_artist_lookup_name(name: str) -> str:
    cleaned = re.sub(r"\s+explicit$", "", name, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.endswith("(Dance)"):
        cleaned = cleaned[: -len("(Dance)")].strip()
    for token in ("Junge Junge",):
        if token.lower() in cleaned.lower():
            return token
    return cleaned.replace("'", "ʻ") if "Kamakawiwo" in cleaned else cleaned.replace("'", "")


def resolve_catalog_artist_id_via_musicbrainz(name: str) -> str | None:
    """Resolve a Spotify artist ID via MusicBrainz URL relations."""
    import json
    import urllib.error
    import urllib.request
    from urllib.parse import quote

    lookup_name = _clean_artist_lookup_name(name)
    if not lookup_name:
        return None

    search_url = (
        "https://musicbrainz.org/ws/2/artist/"
        f'?query=artist:{quote(f"\"{lookup_name}\"")}&fmt=json&limit=5'
    )
    request = urllib.request.Request(search_url, headers={"User-Agent": _MUSICBRAINZ_USER_AGENT})
    try:
        payload = json.loads(urllib.request.urlopen(request, timeout=20).read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    artists = payload.get("artists") or []
    if not artists:
        return None

    target = _normalize_artist_name(lookup_name)
    mbid = None
    for artist in artists:
        if _normalize_artist_name(str(artist.get("name") or "")) == target:
            mbid = str(artist["id"])
            break
    if mbid is None:
        mbid = str(artists[0]["id"])

    time.sleep(1.1)
    detail_url = f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=url-rels&fmt=json"
    detail_request = urllib.request.Request(detail_url, headers={"User-Agent": _MUSICBRAINZ_USER_AGENT})
    try:
        detail = json.loads(urllib.request.urlopen(detail_request, timeout=20).read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    for relation in detail.get("relations") or []:
        resource = str((relation.get("url") or {}).get("resource") or "")
        match = re.search(r"open\.spotify\.com/artist/([A-Za-z0-9]+)", resource)
        if match:
            return match.group(1)
    return None


def _normalize_artist_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.lower().strip())
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized


def _register_name(mapping: dict[str, set[str]], name: str, catalog_id: str) -> None:
    for key in {_normalize_artist_name(name), name.lower().strip()}:
        if key:
            mapping[key].add(catalog_id)


def build_catalog_id_map(liked_songs: list[TasteSong], *, delay: float = 0.2) -> dict[str, set[str]]:
    """Map artist name variants to real Spotify artist IDs using liked song embeds."""
    mapping: dict[str, set[str]] = defaultdict(set)
    catalog_songs = [song for song in liked_songs if is_spotify_catalog_id(song.spotify_id)]
    print(f"Building artist ID map from {len(catalog_songs)} liked songs with Spotify track IDs…")

    for i, song in enumerate(catalog_songs, start=1):
        if song.artist_id and is_spotify_catalog_id(song.artist_id):
            _register_name(mapping, song.artist, song.artist_id)
            continue
        try:
            details = fetch_track_details_from_embed(song.spotify_id)
        except SpotifyError as exc:
            print(f"  [{i}/{len(catalog_songs)}] skip {song.title}: {exc}")
            continue
        if details.artist_id:
            _register_name(mapping, details.artist, details.artist_id)
            _register_name(mapping, song.artist, details.artist_id)
        time.sleep(delay)

    print(f"  Resolved {len(mapping)} artist name variants")
    return mapping


def resolve_catalog_artist_id(
    artist: TasteArtist,
    liked_songs: list[TasteSong],
    catalog_map: dict[str, set[str]],
) -> tuple[str | None, str]:
    if artist.spotify_id and is_spotify_catalog_id(artist.spotify_id):
        return artist.spotify_id, "stored"

    sibling_id = resolve_catalog_id_from_sibling_artists(artist, list_liked_artists())
    if sibling_id:
        return sibling_id, "sibling"

    keys = [_normalize_artist_name(artist.name), artist.name.lower().strip()]
    for key in keys:
        ids = catalog_map.get(key)
        if ids:
            return sorted(ids)[0], "liked-song"

    normalized_target = _normalize_artist_name(artist.name)
    for song in liked_songs:
        if not is_spotify_catalog_id(song.spotify_id):
            continue
        song_artist = song.artist.lower().strip()
        song_normalized = _normalize_artist_name(song.artist)
        if (
            normalized_target == song_normalized
            or normalized_target in song_normalized
            or song_normalized in normalized_target
            or artist.name.lower().strip() in song_artist
            or song_artist in artist.name.lower().strip()
        ):
            ids = catalog_map.get(song_normalized) or catalog_map.get(song_artist)
            if ids:
                return sorted(ids)[0], "liked-song"

    catalog_id = resolve_catalog_artist_id_via_musicbrainz(artist.name)
    if catalog_id:
        return catalog_id, "musicbrainz"
    manual_id = resolve_manual_catalog_artist_id(artist.name)
    if manual_id:
        return manual_id, "manual"
    return None, "unresolved"


def main() -> None:
    liked_songs = list_liked_songs()
    artists = list_liked_artists()
    print(f"Found {len(artists)} liked artists")

    catalog_map = build_catalog_id_map(liked_songs)

    ok = 0
    empty = 0
    unresolved = 0
    failed = 0
    unresolved_names: list[str] = []

    for i, artist in enumerate(artists, start=1):
        if artist.spotify_id and list_artist_top_tracks(artist.pandora_id):
            print(f"[{i}/{len(artists)}] {artist.name}: already linked")
            ok += 1
            continue

        catalog_id, source = resolve_catalog_artist_id(artist, liked_songs, catalog_map)
        if not catalog_id:
            unresolved += 1
            unresolved_names.append(artist.name)
            print(f"[{i}/{len(artists)}] {artist.name}: no Spotify artist ID found")
            continue

        print(f"[{i}/{len(artists)}] {artist.name} ({source}: {catalog_id})…", end=" ", flush=True)
        try:
            tracks = refresh_artist_top_tracks_from_catalog(artist.pandora_id, catalog_id)
            if tracks:
                print(f"OK ({len(tracks)} tracks)")
                ok += 1
            else:
                print("no tracks returned")
                empty += 1
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed += 1
        time.sleep(0.3)

    stored = sum(1 for artist in artists if list_artist_top_tracks(artist.pandora_id))
    print()
    print(f"Done: {ok} with tracks, {empty} empty, {failed} failed, {unresolved} unresolved")
    print(f"Artists with stored top tracks in DB: {stored}/{len(artists)}")
    if unresolved_names:
        print()
        print("Could not resolve Spotify artist IDs for:")
        for name in unresolved_names:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
