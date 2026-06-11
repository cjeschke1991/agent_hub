from agent_hub.agents.movie_recommender.logic import (
    add_to_wishlist,
    list_wishlist,
    remove_from_wishlist,
)
from agent_hub.agents.movie_recommender.tmdb import MovieDetails
from agent_hub.core.config import HubConfig, TmdbConfig


def test_wishlist_add_list_remove(hub_config, monkeypatch):
    config = HubConfig(
        data_dir=hub_config.data_dir,
        tmdb=TmdbConfig(api_key="test-key"),
    )

    def fake_details(tmdb_id: int, config=None):
        return MovieDetails(
            tmdb_id=tmdb_id,
            title=f"Movie {tmdb_id}",
            year=2020,
            genres=["Drama"],
            director="Director",
            cast=["Actor"],
            keywords=[],
            rating=7.5,
            runtime=100,
            poster_url=None,
            overview="Overview",
        )

    monkeypatch.setattr("agent_hub.agents.movie_recommender.logic.get_movie_details", fake_details)

    add_to_wishlist(99, config=config)
    movies = list_wishlist(config)
    assert len(movies) == 1
    assert movies[0].tmdb_id == 99
    assert movies[0].title == "Movie 99"

    remove_from_wishlist(99, config=config)
    assert list_wishlist(config) == []
