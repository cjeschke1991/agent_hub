"""
Populate liked artists from liked songs.

For each unique artist in liked songs:
  - Real Spotify songs: resolve artist_id via fetch_track_details_from_embed if missing
  - Pandora songs: create synthetic artist ID from artist name hash
Then insert any not-yet-liked artists into taste_artists with sentiment='like'.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

# Make sure the package root is on the path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_hub.agents.music_recommender.logic import (
    _upsert_taste_artist,
    is_collaboration_artist_name,
    list_liked_artists,
    list_liked_songs,
    refresh_artist_top_tracks,
)
from agent_hub.agents.music_recommender.spotify import (
    ArtistDetails,
    SpotifyError,
    fetch_artist_details_from_embed,
    fetch_track_details_from_embed,
    is_spotify_catalog_id,
)


def pandora_artist_id(artist_name: str) -> str:
    digest = hashlib.sha1(artist_name.lower().encode()).hexdigest()[:16]
    return f"pandora-artist-{digest}"


def main() -> None:
    print("Loading liked songs…")
    liked_songs = list_liked_songs()
    print(f"  Found {len(liked_songs)} liked songs")

    print("Loading existing liked artists…")
    existing_artists = list_liked_artists()
    existing_ids = {a.spotify_id for a in existing_artists}
    print(f"  Found {len(existing_ids)} existing liked artists")

    # Build deduped {artist_id: artist_name} map
    artist_map: dict[str, str] = {}

    for song in liked_songs:
        # Case 1: artist_id already populated
        if song.artist_id and song.artist_id.strip():
            artist_map[song.artist_id] = song.artist
            continue

        # Case 2: real Spotify track ID — fetch artist_id from embed
        if is_spotify_catalog_id(song.spotify_id):
            try:
                track = fetch_track_details_from_embed(song.spotify_id)
                if track.artist_id:
                    artist_map[track.artist_id] = track.artist
                    continue
            except SpotifyError as exc:
                print(f"  [warn] Could not fetch embed for {song.spotify_id}: {exc}")
            # Fallback: use artist name as key if we couldn't get artist_id
            if song.artist and song.artist.strip():
                aid = pandora_artist_id(song.artist)
                artist_map[aid] = song.artist
            continue

        # Case 3: pandora-* track — derive artist_id from artist name
        if song.artist and song.artist.strip():
            aid = pandora_artist_id(song.artist)
            artist_map[aid] = song.artist

    print(f"\nUnique artists found across liked songs: {len(artist_map)}")

    added = 0
    skipped = 0
    errors = 0

    for artist_id, artist_name in artist_map.items():
        if is_collaboration_artist_name(artist_name):
            skipped += 1
            continue
        if artist_id in existing_ids:
            skipped += 1
            continue

        # Build ArtistDetails — fetch from embed for real Spotify IDs
        if is_spotify_catalog_id(artist_id):
            try:
                details = fetch_artist_details_from_embed(artist_id)
                time.sleep(0.3)  # be polite to Spotify's embed endpoints
            except SpotifyError as exc:
                print(f"  [warn] Could not fetch artist embed for {artist_id} ({artist_name}): {exc}")
                # Fall back to minimal details
                details = ArtistDetails(
                    spotify_id=artist_id,
                    name=artist_name,
                    genres=[],
                    popularity=0,
                    followers=0,
                    image_url=None,
                )
        else:
            # Pandora synthetic artist — minimal details
            details = ArtistDetails(
                spotify_id=artist_id,
                name=artist_name,
                genres=[],
                popularity=0,
                followers=0,
                image_url=None,
            )

        try:
            _upsert_taste_artist(details, "like")
            existing_ids.add(artist_id)
            if is_spotify_catalog_id(artist_id):
                try:
                    refresh_artist_top_tracks(artist_id)
                except Exception as exc:
                    print(f"  [warn] Could not fetch top tracks for {artist_name}: {exc}")
            added += 1
            print(f"  + Added: {artist_name} ({artist_id})")
        except Exception as exc:
            errors += 1
            print(f"  [error] Failed to insert {artist_name} ({artist_id}): {exc}")

    # Final verification
    final_artists = list_liked_artists()

    print("\n" + "=" * 50)
    print(f"Artists added:   {added}")
    print(f"Artists skipped (already existed): {skipped}")
    print(f"Errors:          {errors}")
    print(f"Total liked artists after: {len(final_artists)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
