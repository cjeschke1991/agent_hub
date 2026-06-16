import json

import typer

from agent_hub.agents.music_recommender.logic import (
    MusicRecommendFilters,
    MusicRecommendationError,
    MusicValidationError,
    add_artist,
    add_song,
    list_liked_artists,
    list_liked_songs,
    list_wishlist_artists,
    list_wishlist_songs,
    recommend,
    remove_artist,
    remove_song,
)
from agent_hub.agents.music_recommender.spotify import SpotifyConfigError, spotify_configured
from agent_hub.core.music_db import init_db

app = typer.Typer(help="Music Recommender taste profile and recommendations.")


@app.command("init-db")
def init_db_cmd() -> None:
    path = init_db()
    typer.echo(f"Music database ready: {path}")


@app.command("search-songs")
def search_songs_cmd(query: str) -> None:
    from agent_hub.agents.music_recommender.spotify import search_tracks

    try:
        results = search_tracks(query)
    except SpotifyConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for r in results:
        year = r.year or "—"
        typer.echo(f"{r.spotify_id}\t{r.title} — {r.artist} ({year})")


@app.command("search-artists")
def search_artists_cmd(query: str) -> None:
    from agent_hub.agents.music_recommender.spotify import search_artists

    try:
        results = search_artists(query)
    except SpotifyConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for r in results:
        genres = ", ".join(r.genres[:3]) or "—"
        typer.echo(f"{r.spotify_id}\t{r.name} — {genres}")


@app.command("add-song")
def add_song_cmd(
    spotify_id: str,
    like: bool = typer.Option(True, "--like/--dislike"),
) -> None:
    try:
        song = add_song(spotify_id, "like" if like else "dislike")
    except SpotifyConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Saved '{song.title}' by {song.artist} as {song.sentiment}.")


@app.command("add-artist")
def add_artist_cmd(
    spotify_id: str,
    like: bool = typer.Option(True, "--like/--dislike"),
) -> None:
    try:
        artist = add_artist(spotify_id, "like" if like else "dislike")
    except SpotifyConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Saved '{artist.name}' as {artist.sentiment}.")


@app.command("remove-song")
def remove_song_cmd(spotify_id: str) -> None:
    remove_song(spotify_id)
    typer.echo(f"Removed song {spotify_id}.")


@app.command("remove-artist")
def remove_artist_cmd(spotify_id: str) -> None:
    remove_artist(spotify_id)
    typer.echo(f"Removed artist {spotify_id}.")


@app.command("recommend")
def recommend_cmd(
    year_min: int = typer.Option(1980, "--year-min"),
    year_max: int = typer.Option(2026, "--year-max"),
    genres: str = typer.Option("", "--genres", help="Comma-separated genre names."),
    song_count: int = typer.Option(10, "--song-count"),
    artist_count: int = typer.Option(10, "--artist-count"),
) -> None:
    genre_names = [p.strip() for p in genres.split(",") if p.strip()]
    filters = MusicRecommendFilters(
        year_min=year_min,
        year_max=year_max,
        genre_names=genre_names or None,
        song_count=song_count,
        artist_count=artist_count,
    )
    try:
        songs, artists = recommend(filters)
    except (SpotifyConfigError, MusicRecommendationError, MusicValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    payload = {
        "songs": [
            {
                "spotify_id": item.track.spotify_id,
                "title": item.track.title,
                "artist": item.track.artist,
                "year": item.track.year,
                "score": item.score.total,
                "reason": item.reason,
            }
            for item in songs
        ],
        "artists": [
            {
                "spotify_id": item.artist.spotify_id,
                "name": item.artist.name,
                "genres": item.artist.genres[:3],
                "score": item.score.total,
                "reason": item.reason,
            }
            for item in artists
        ],
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command("status")
def status_cmd() -> None:
    typer.echo(
        json.dumps(
            {
                "spotify_configured": spotify_configured(),
                "liked_songs": len(list_liked_songs()),
                "liked_artists": len(list_liked_artists()),
                "wishlist_songs": len(list_wishlist_songs()),
                "wishlist_artists": len(list_wishlist_artists()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
