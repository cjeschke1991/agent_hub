"""
Backfill Spotify genres for all liked artists and songs.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_hub.agents.music_recommender.logic import (  # noqa: E402
    backfill_taste_genres,
    list_liked_artists,
    list_liked_songs,
)


def main() -> None:
    print("Backfilling genres for liked artists and songs…")
    artists_updated, songs_updated = backfill_taste_genres()
    artists = list_liked_artists()
    songs = list_liked_songs()
    artists_with = sum(1 for artist in artists if artist.genres)
    songs_with = sum(1 for song in songs if song.genres)
    print(f"Artists updated: {artists_updated}")
    print(f"Songs updated: {songs_updated}")
    print(f"Artists with genres: {artists_with}/{len(artists)}")
    print(f"Songs with genres: {songs_with}/{len(songs)}")


if __name__ == "__main__":
    main()
