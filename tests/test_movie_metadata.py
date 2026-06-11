from agent_hub.agents.movie_recommender.tmdb import MovieDetails


def test_metadata_display_includes_genre_director_cast_and_rt():
    movie = MovieDetails(
        tmdb_id=1,
        title="Alien",
        year=1979,
        genres=["Sci-Fi", "Horror"],
        director="Ridley Scott",
        cast=["Sigourney Weaver", "Tom Skerritt", "John Hurt", "Extra"],
        keywords=[],
        rating=8.5,
        runtime=117,
        poster_url=None,
        overview="",
        imdb_id="tt0078748",
        rotten_tomatoes_score="93%",
    )

    metadata = movie.metadata_display()
    assert metadata["Genre"] == "Sci-Fi, Horror"
    assert metadata["Director"] == "Ridley Scott"
    assert metadata["Lead actors"] == "Sigourney Weaver, Tom Skerritt, John Hurt"
    assert metadata["Rotten Tomatoes"] == "93%"
