from __future__ import annotations

from agent_hub.agents.movie_recommender.scoring import ScoreBreakdown
from agent_hub.agents.movie_recommender.tmdb import MovieDetails


def _format_list(items: list[str], limit: int = 2) -> str:
    items = items[:limit]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{items[0]} and {items[1]}"


def _liked_genres(liked: list[MovieDetails]) -> set[str]:
    genres: set[str] = set()
    for movie in liked:
        genres.update(movie.genres)
    return genres


def _best_liked_match(candidate: MovieDetails, liked: list[MovieDetails]) -> MovieDetails | None:
    best: MovieDetails | None = None
    best_score = 0
    candidate_genres = set(candidate.genres)
    candidate_cast = {name.lower() for name in candidate.cast}
    for movie in liked:
        score = len(candidate_genres & set(movie.genres)) * 2
        if (
            candidate.director
            and movie.director
            and candidate.director.lower() == movie.director.lower()
        ):
            score += 3
        score += len(candidate_cast & {name.lower() for name in movie.cast})
        if score > best_score:
            best_score = score
            best = movie
    return best if best_score > 0 else None


def _shared_cast(candidate: MovieDetails, liked: list[MovieDetails]) -> list[str]:
    liked_cast = {name.lower(): name for movie in liked for name in movie.cast}
    shared: list[str] = []
    for name in candidate.cast:
        canonical = liked_cast.get(name.lower())
        if canonical and canonical not in shared:
            shared.append(canonical)
    return shared


def _shared_keywords(candidate: MovieDetails, liked: list[MovieDetails]) -> list[str]:
    liked_keywords = {keyword.lower(): keyword for movie in liked for keyword in movie.keywords}
    shared: list[str] = []
    for keyword in candidate.keywords:
        canonical = liked_keywords.get(keyword.lower())
        if canonical and canonical not in shared:
            shared.append(canonical)
    return shared


def _director_liked_before(candidate: MovieDetails, liked: list[MovieDetails]) -> bool:
    if not candidate.director:
        return False
    return any(
        movie.director and movie.director.lower() == candidate.director.lower()
        for movie in liked
    )


def recommendation_reason(
    candidate: MovieDetails,
    liked: list[MovieDetails],
    disliked: list[MovieDetails],
    score: ScoreBreakdown,
) -> str:
    if not liked:
        return "Add liked movies to personalize recommendations."

    shared_genres = sorted(set(candidate.genres) & _liked_genres(liked))
    similar = _best_liked_match(candidate, liked)
    shared_people = _shared_cast(candidate, liked)
    shared_topics = _shared_keywords(candidate, liked)
    disliked_genres = {genre for movie in disliked for genre in movie.genres}

    parts: list[str] = []

    if shared_genres and score.genre >= 40:
        parts.append(f"it matches your taste for {_format_list(shared_genres)}")

    if similar and similar.title != candidate.title:
        parts.append(f"it's similar to {similar.title}")

    if candidate.director and _director_liked_before(candidate, liked) and score.cast_director >= 30:
        parts.append(f"it comes from director {candidate.director}, whose work you've liked")

    if shared_people and score.cast_director >= 25:
        parts.append(f"it features {_format_list(shared_people)}, whom you've enjoyed before")

    if shared_topics and score.keywords >= 20:
        parts.append(f"it shares {_format_list(shared_topics, limit=1)} themes with your favorites")

    if score.rating >= 70 and candidate.scoring_rating() is not None:
        if candidate.rotten_tomatoes_score:
            parts.append(f"its Rotten Tomatoes score ({candidate.rotten_tomatoes_score}) fits your taste")
        else:
            parts.append("its rating fits the quality level of your liked films")

    if score.year >= 70 and candidate.year is not None:
        parts.append(f"its {candidate.year} release sits in the era you tend to favor")

    if disliked_genres and not (set(candidate.genres) & disliked_genres):
        parts.append("it avoids the genres you've disliked")

    if not parts:
        return "This pick aligns with patterns across the movies you've liked."

    lead = parts[0]
    if len(parts) == 1:
        return f"You'll likely enjoy this because {lead}."
    return f"You'll likely enjoy this because {lead}, and {parts[1]}."
