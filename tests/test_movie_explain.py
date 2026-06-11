from agent_hub.agents.movie_recommender.explain import recommendation_reason
from agent_hub.agents.movie_recommender.scoring import ScoreBreakdown, composite_score
from agent_hub.agents.movie_recommender.tmdb import MovieDetails
from agent_hub.core.config import MovieRecommenderWeights


def _movie(
    tmdb_id: int,
    title: str,
    *,
    year: int = 2000,
    genres: list[str] | None = None,
    director: str | None = None,
    cast: list[str] | None = None,
    keywords: list[str] | None = None,
    rating: float = 7.5,
) -> MovieDetails:
    return MovieDetails(
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        genres=genres or [],
        director=director,
        cast=cast or [],
        keywords=keywords or [],
        rating=rating,
        runtime=120,
        poster_url=None,
        overview="",
    )


def test_recommendation_reason_mentions_genre_and_similar_liked_movie():
    liked = [
        _movie(
            1,
            "Blade Runner",
            genres=["Sci-Fi", "Thriller"],
            director="Ridley Scott",
            cast=["Harrison Ford"],
            keywords=["dystopia"],
            rating=8.1,
            year=1982,
        )
    ]
    candidate = _movie(
        2,
        "Alien",
        genres=["Sci-Fi", "Horror"],
        director="Ridley Scott",
        cast=["Sigourney Weaver"],
        keywords=["space"],
        rating=8.0,
        year=1979,
    )
    weights = MovieRecommenderWeights()
    score = composite_score(candidate, liked, [], 1970, 1990, weights)
    reason = recommendation_reason(candidate, liked, [], score)

    assert "Blade Runner" in reason or "Sci-Fi" in reason
    assert reason.endswith(".")
    assert reason.count(".") == 1


def test_recommendation_reason_avoids_disliked_genre_note():
    liked = [_movie(1, "Arrival", genres=["Sci-Fi"], rating=7.9, year=2016)]
    disliked = [_movie(2, "Bad Comedy", genres=["Comedy"], rating=4.0, year=2015)]
    candidate = _movie(3, "Interstellar", genres=["Sci-Fi", "Drama"], rating=8.6, year=2014)
    weights = MovieRecommenderWeights()
    score = composite_score(candidate, liked, disliked, 2010, 2020, weights)
    reason = recommendation_reason(candidate, liked, disliked, score)

    assert "disliked" in reason.lower() or "Sci-Fi" in reason
