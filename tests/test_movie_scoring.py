from agent_hub.agents.movie_recommender.scoring import composite_score
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


def test_composite_score_prefers_genre_and_cast_overlap():
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
    weak = _movie(
        3,
        "Random Comedy",
        genres=["Comedy"],
        director="Someone Else",
        cast=["Unknown"],
        keywords=["romcom"],
        rating=5.0,
        year=2010,
    )

    weights = MovieRecommenderWeights()
    strong_score = composite_score(candidate, liked, [], 1970, 1990, weights)
    weak_score = composite_score(weak, liked, [], 1970, 2020, weights)

    assert strong_score.total > weak_score.total
    assert strong_score.genre > weak_score.genre
    assert strong_score.cast_director > weak_score.cast_director
