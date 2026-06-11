from agent_hub.agents.movie_recommender.logic import (
    RecommendFilters,
    add_movie,
    is_kids_movie,
    list_disliked,
    list_liked,
    recommend,
)
from agent_hub.agents.movie_recommender.tmdb import MovieDetails
from agent_hub.core.config import HubConfig, TmdbConfig


def _details(tmdb_id: int, title: str, *, year: int = 2000, genres: list[str] | None = None) -> MovieDetails:
    return MovieDetails(
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        genres=genres or ["Sci-Fi"],
        director="Director",
        cast=["Actor One"],
        keywords=["future"],
        rating=8.0,
        runtime=120,
        poster_url=None,
        overview="Overview",
    )


def test_add_movie_upserts_sentiment(hub_config, monkeypatch):
    config = HubConfig(
        data_dir=hub_config.data_dir,
        tmdb=TmdbConfig(api_key="test-key"),
    )

    def fake_details(tmdb_id: int, config=None):
        return _details(tmdb_id, f"Movie {tmdb_id}")

    monkeypatch.setattr("agent_hub.agents.movie_recommender.logic.get_movie_details", fake_details)

    add_movie(42, "like", config=config)
    add_movie(42, "dislike", config=config)

    assert list_liked(config) == []
    disliked = list_disliked(config)
    assert len(disliked) == 1
    assert disliked[0].tmdb_id == 42
    assert disliked[0].sentiment == "dislike"


def test_recommend_excludes_existing_taste_and_ranks(hub_config, monkeypatch):
    config = HubConfig(
        data_dir=hub_config.data_dir,
        tmdb=TmdbConfig(api_key="test-key"),
    )

    catalog = {
        1: _details(1, "Liked Seed", year=1982, genres=["Sci-Fi"]),
        2: _details(2, "Best Match", year=1984, genres=["Sci-Fi", "Thriller"]),
        3: _details(3, "Also Good", year=1985, genres=["Sci-Fi"]),
        4: _details(4, "Disliked", year=1983, genres=["Comedy"]),
    }

    monkeypatch.setattr(
        "agent_hub.agents.movie_recommender.logic.get_movie_details",
        lambda tmdb_id, config=None: catalog[tmdb_id],
    )
    monkeypatch.setattr(
        "agent_hub.agents.movie_recommender.logic.discover_movie_ids",
        lambda year_min, year_max, genre_ids=None, page=1, config=None: [2, 3, 1, 4],
    )
    monkeypatch.setattr(
        "agent_hub.agents.movie_recommender.logic.get_similar_ids",
        lambda tmdb_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.movie_recommender.logic.get_recommendation_ids",
        lambda tmdb_id, config=None: [],
    )
    monkeypatch.setattr(
        "agent_hub.agents.movie_recommender.logic.list_genres",
        lambda config=None: [],
    )

    add_movie(1, "like", config=config)
    add_movie(4, "dislike", config=config)

    results = recommend(
        RecommendFilters(year_min=1980, year_max=1990, genre_names=[], count=2),
        config=config,
    )

    assert len(results) == 2
    assert {item.movie.tmdb_id for item in results} == {2, 3}
    assert results[0].score.total >= results[1].score.total
    assert results[0].reason
    assert results[0].reason.endswith(".")


def test_kids_only_filters_non_family_animation(hub_config):
    assert is_kids_movie(_details(1, "Toy Story", genres=["Animation", "Family"]))
    assert not is_kids_movie(_details(2, "Die Hard", genres=["Action", "Thriller"]))

