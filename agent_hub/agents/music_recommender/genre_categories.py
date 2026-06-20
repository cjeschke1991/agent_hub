"""Genre category mapping for the Music Recommender.

Maps Spotify's granular genre strings (e.g. "indie rock", "vapor twitch") into
10 broad categories (e.g. "Rock", "EDM / Electronic").

Public API
----------
classify_genre(genre)   -> str          single genre → category name
classify_genres(genres) -> list[str]    list of genres → deduplicated sorted categories
augment_with_categories(genres) -> list[str]
                                        original genres + category names (for scoring)
ALL_CATEGORIES          : list[str]     all 10 category names in display order
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

ALL_CATEGORIES: list[str] = [
    "Rock",
    "Pop",
    "Rap / Hip-Hop",
    "EDM / Electronic",
    "R&B / Soul",
    "Country",
    "Jazz / Blues",
    "Classical",
    "Latin",
    "Other / World",
]

# Priority-ordered keyword rules.
# Each entry: (category_name, [keywords]).
# The FIRST matching rule wins.  Order matters — more specific rules first.
_RULES: list[tuple[str, list[str]]] = [
    ("Rap / Hip-Hop", [
        "rap", "hip hop", "hip-hop", "trap", "drill", "grime",
        "cloud rap", "mumble", "phonk", "crunk", "hyphy",
    ]),
    ("EDM / Electronic", [
        "edm", "house", "techno", "trance", "dubstep", "drum and bass",
        "dnb", "electro", "electronica", "ambient", "idm", "downtempo",
        "synthwave", "chillwave", "vaporwave", "garage", "breakbeat",
        "jungle", "hardstyle", "bassline", "dancehall", "club",
    ]),
    ("R&B / Soul", [
        "r&b", "soul", "funk", "motown", "gospel", "neo soul",
        "quiet storm", "new jack swing",
    ]),
    ("Jazz / Blues", [
        "jazz", "blues", "swing", "bebop", "bossa nova", "samba jazz",
        "smooth jazz", "soul jazz", "cool jazz", "free jazz",
    ]),
    ("Classical", [
        "classical", "orchestral", "opera", "baroque", "chamber",
        "symphony", "concerto", "choral", "neoclassical",
    ]),
    ("Latin", [
        "latin", "reggaeton", "salsa", "samba", "cumbia", "merengue",
        "bachata", "tango", "flamenco", "mariachi", "vallenato",
        "norteño", "corridos",
    ]),
    ("Country", [
        "country", "bluegrass", "americana", "outlaw", "honky",
        "cowboy", "western", "country pop", "country rock",
    ]),
    ("Rock", [
        "rock", "metal", "punk", "grunge", "hardcore", "emo",
        "alternative", "indie rock", "classic rock", "progressive",
        "psychedelic", "shoegaze", "post-rock", "post rock",
        "new wave", "glam", "surf", "garage rock",
    ]),
    ("Pop", [
        "pop", "dance", "disco", "bubblegum", "teen pop",
        "art pop", "power pop",
    ]),
    # "Other / World" is the catch-all — no keywords needed
]

# Curated overrides for ambiguous genres that don't parse cleanly by keyword.
# Checked BEFORE rules.  Keys are lowercase normalized genre strings.
_OVERRIDES: dict[str, str] = {
    # Genuinely ambiguous: need explicit assignment
    "indie": "Rock",
    "alternative": "Rock",
    "folk": "Other / World",
    "singer-songwriter": "Other / World",
    "acoustic": "Other / World",
    "soul": "R&B / Soul",
    "funk": "R&B / Soul",
    "gospel": "R&B / Soul",
    "reggae": "Other / World",
    "ska": "Other / World",
    "dub": "Other / World",
    "afrobeats": "Other / World",
    "afropop": "Other / World",
    "world": "Other / World",
    "k-pop": "Pop",
    "j-pop": "Pop",
    "c-pop": "Pop",
    "mandopop": "Pop",
    "cantopop": "Pop",
    "dream pop": "Pop",
    "indietronica": "EDM / Electronic",
    "chillhop": "Rap / Hip-Hop",
    "lo-fi": "Rap / Hip-Hop",
    "lo fi": "Rap / Hip-Hop",
    "lofi": "Rap / Hip-Hop",
    "r&b": "R&B / Soul",
    "rnb": "R&B / Soul",
    "blues": "Jazz / Blues",
    "bossa nova": "Jazz / Blues",
    "new age": "Classical",
    "ambient": "EDM / Electronic",
    "instrumental": "Other / World",
    "soundtrack": "Other / World",
    "score": "Classical",
    "broadway": "Other / World",
    "musical": "Other / World",
    "comedy": "Other / World",
    "christian": "Other / World",
    "worship": "Other / World",
    "celtic": "Other / World",
    "medieval": "Classical",
    "flamenco": "Latin",
}

_CATCH_ALL = "Other / World"


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------

def _normalize(genre: str) -> str:
    return " ".join(genre.lower().split())


def classify_genre(genre: str) -> str:
    """Map a single raw genre string to a category name."""
    norm = _normalize(genre)

    # 1. Exact override match
    if norm in _OVERRIDES:
        return _OVERRIDES[norm]

    # 2. Partial override match (e.g. "indie pop" contains "indie" override key — skip;
    #    overrides are exact-only to avoid false positives)

    # 3. Keyword rules in priority order
    for category, keywords in _RULES:
        for kw in keywords:
            if kw in norm:
                return category

    return _CATCH_ALL


def classify_genres(genres: list[str]) -> list[str]:
    """Return deduplicated, sorted category names for a list of raw genres."""
    seen: set[str] = set()
    result: list[str] = []
    for g in genres:
        cat = classify_genre(g)
        if cat not in seen:
            seen.add(cat)
            result.append(cat)
    # Preserve ALL_CATEGORIES display order
    result.sort(key=lambda c: ALL_CATEGORIES.index(c) if c in ALL_CATEGORIES else 99)
    return result


def augment_with_categories(genres: list[str]) -> list[str]:
    """Return original genres + their category names (for scoring overlap).

    The category names are appended as extra genre tags so that the existing
    Jaccard overlap scorer naturally picks up category-level similarity
    without any changes to scoring weights or logic.
    """
    cats = classify_genres(genres)
    # Add as lowercase to match the rest of the genre pipeline
    return list(genres) + [c.lower() for c in cats]
