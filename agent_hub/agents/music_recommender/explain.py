from __future__ import annotations

from agent_hub.agents.music_recommender.scoring import ArtistScoreBreakdown, SongScoreBreakdown


def _fmt(items: list[str], limit: int = 2) -> str:
    items = [i for i in items[:limit] if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{items[0]} and {items[1]}"


def song_reason(
    candidate_title: str,
    candidate_artist: str,
    candidate_genres: list[str],
    candidate_energy: float | None,
    candidate_valence: float | None,
    candidate_year: int | None,
    score: SongScoreBreakdown,
    liked_genres: set[str],
    disliked_genres: set[str],
    liked_artist_names: set[str],
    candidate_artist_in_liked: bool,
) -> str:
    parts: list[str] = []
    shared_genres = sorted(set(g for g in candidate_genres if g.lower() in liked_genres))

    if candidate_artist_in_liked and score.artist_affinity >= 80:
        parts.append(f"it's by {candidate_artist}, an artist you've liked")
    elif score.artist_affinity >= 50:
        parts.append(f"{candidate_artist} is closely related to artists you enjoy")

    if shared_genres and score.genre >= 30:
        parts.append(f"it matches your taste for {_fmt(shared_genres)}")

    if score.audio_features >= 60:
        descriptors: list[str] = []
        if candidate_energy is not None:
            if candidate_energy >= 0.7:
                descriptors.append("high-energy")
            elif candidate_energy <= 0.4:
                descriptors.append("mellow")
        if candidate_valence is not None:
            if candidate_valence >= 0.7:
                descriptors.append("upbeat")
            elif candidate_valence <= 0.3:
                descriptors.append("melancholic")
        if descriptors:
            parts.append(f"its {' and '.join(descriptors)} vibe fits your taste")

    if score.year >= 70 and candidate_year:
        parts.append(f"its {candidate_year} release sits in the era you tend to favor")

    if not (set(g.lower() for g in candidate_genres) & disliked_genres) and disliked_genres:
        parts.append("it avoids the genres you've disliked")

    if not parts:
        return "This pick aligns with patterns across the music you've liked."

    lead = parts[0]
    if len(parts) == 1:
        return f"You'll likely enjoy this because {lead}."
    return f"You'll likely enjoy this because {lead}, and {parts[1]}."


def artist_reason(
    candidate_name: str,
    candidate_genres: list[str],
    candidate_popularity: int,
    score: ArtistScoreBreakdown,
    liked_genres: set[str],
    liked_artist_names: set[str],
    related_liked_count: int,
) -> str:
    parts: list[str] = []
    shared_genres = sorted(set(g for g in candidate_genres if g.lower() in liked_genres))

    if related_liked_count >= 2 and score.related_artists >= 60:
        parts.append(f"they're closely related to {related_liked_count} artists you already like")
    elif related_liked_count == 1 and score.related_artists >= 30:
        parts.append("they're related to an artist you already like")

    if shared_genres and score.genre >= 30:
        parts.append(f"they make {_fmt(shared_genres)} music you enjoy")

    if score.popularity >= 70 and candidate_popularity >= 70:
        parts.append("they're highly regarded in their genre")

    if not parts:
        return "This artist aligns with your taste profile."

    lead = parts[0]
    if len(parts) == 1:
        return f"You'll likely enjoy {candidate_name} because {lead}."
    return f"You'll likely enjoy {candidate_name} because {lead}, and {parts[1]}."
