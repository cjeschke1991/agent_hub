import json

import typer

from agent_hub.agents.movie_recommender.logic import (
    RecommendFilters,
    RecommendationError,
    add_movie,
    list_disliked,
    list_liked,
    recommend,
    remove_movie,
    search_tmdb,
    tmdb_configured,
)
from agent_hub.agents.movie_recommender.tmdb import TmdbConfigError
from agent_hub.core.movie_db import init_db

app = typer.Typer(help="Movie Recommender taste profile and recommendations.")


@app.command("init-db")
def init_db_cmd() -> None:
    path = init_db()
    typer.echo(f"Movie database ready: {path}")


@app.command("search")
def search_cmd(query: str) -> None:
    try:
        results = search_tmdb(query)
    except TmdbConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for result in results:
        year = result.year or "—"
        typer.echo(f"{result.tmdb_id}\t{result.title} ({year})")


@app.command("add")
def add_cmd(
    tmdb_id: int,
    like: bool = typer.Option(True, "--like/--dislike", help="Mark as liked or disliked."),
) -> None:
    try:
        movie = add_movie(tmdb_id, "like" if like else "dislike")
    except TmdbConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Saved {movie.title} as {movie.sentiment}.")


@app.command("remove")
def remove_cmd(tmdb_id: int) -> None:
    remove_movie(tmdb_id)
    typer.echo(f"Removed TMDB id {tmdb_id}.")


@app.command("list")
def list_cmd(liked: bool = typer.Option(True, "--liked/--disliked")) -> None:
    movies = list_liked() if liked else list_disliked()
    for movie in movies:
        year = movie.year or "—"
        typer.echo(f"{movie.tmdb_id}\t{movie.title} ({year})")


@app.command("recommend")
def recommend_cmd(
    year_min: int = typer.Option(1980, "--year-min"),
    year_max: int = typer.Option(2026, "--year-max"),
    genres: str = typer.Option("", "--genres", help="Comma-separated genre names."),
    count: int = typer.Option(10, "--count"),
) -> None:
    genre_names = [part.strip() for part in genres.split(",") if part.strip()]
    filters = RecommendFilters(
        year_min=year_min,
        year_max=year_max,
        genre_names=genre_names,
        count=count,
    )
    try:
        results = recommend(filters)
    except (TmdbConfigError, RecommendationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    payload = [
        {
            "tmdb_id": item.movie.tmdb_id,
            "title": item.movie.title,
            "year": item.movie.year,
            "score": item.score.total,
            "breakdown": item.score.as_labels(),
        }
        for item in results
    ]
    typer.echo(json.dumps(payload, indent=2))


@app.command("status")
def status_cmd() -> None:
    typer.echo(
        json.dumps(
            {
                "tmdb_configured": tmdb_configured(),
                "liked_count": len(list_liked()),
                "disliked_count": len(list_disliked()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
