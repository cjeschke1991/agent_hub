from dataclasses import dataclass, field

from agent_hub.dashboards.music_recommender import _aggregate_top_genres


@dataclass
class _GenreItem:
    genres: list[str] = field(default_factory=list)


def test_aggregate_top_genres_orders_by_frequency():
    songs = [
        _GenreItem(genres=["Rock", "Indie"]),
        _GenreItem(genres=["rock"]),
        _GenreItem(genres=["Pop"]),
    ]
    artists = [
        _GenreItem(genres=["Rock"]),
        _GenreItem(genres=["Jam Band"]),
    ]

    assert _aggregate_top_genres(songs, artists, limit=3) == ["Rock", "Indie", "Jam Band"]


def test_aggregate_top_genres_skips_empty_and_respects_limit():
    songs = [_GenreItem(genres=["", "  ", "EDM"])]
    artists = [_GenreItem(genres=["edm", "House"])]

    assert _aggregate_top_genres(songs, artists, limit=2) == ["EDM", "House"]
