"""Tests for genre_categories — classify_genre, classify_genres, augment_with_categories."""
from __future__ import annotations

import pytest

from agent_hub.agents.music_recommender.genre_categories import (
    ALL_CATEGORIES,
    augment_with_categories,
    classify_genre,
    classify_genres,
)


# ---------------------------------------------------------------------------
# classify_genre — known genres
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("genre,expected", [
    # Rap / Hip-Hop
    ("rap", "Rap / Hip-Hop"),
    ("hip hop", "Rap / Hip-Hop"),
    ("trap", "Rap / Hip-Hop"),
    ("drill", "Rap / Hip-Hop"),
    ("lo-fi", "Rap / Hip-Hop"),
    # EDM / Electronic
    ("house", "EDM / Electronic"),
    ("techno", "EDM / Electronic"),
    ("dubstep", "EDM / Electronic"),
    ("synthwave", "EDM / Electronic"),
    ("ambient", "EDM / Electronic"),
    ("indietronica", "EDM / Electronic"),
    # R&B / Soul
    ("r&b", "R&B / Soul"),
    ("soul", "R&B / Soul"),
    ("funk", "R&B / Soul"),
    ("neo soul", "R&B / Soul"),
    # Jazz / Blues
    ("jazz", "Jazz / Blues"),
    ("blues", "Jazz / Blues"),
    ("smooth jazz", "Jazz / Blues"),
    # Classical
    ("classical", "Classical"),
    ("orchestral", "Classical"),
    ("opera", "Classical"),
    # Latin
    ("reggaeton", "Latin"),
    ("salsa", "Latin"),
    ("latin", "Latin"),
    ("flamenco", "Latin"),
    # Country
    ("country", "Country"),
    ("bluegrass", "Country"),
    ("americana", "Country"),
    # Rock
    ("rock", "Rock"),
    ("metal", "Rock"),
    ("punk", "Rock"),
    ("indie rock", "Rock"),
    ("alternative", "Rock"),
    ("new wave", "Rock"),
    # Pop
    ("pop", "Pop"),
    ("dance pop", "Pop"),
    ("k-pop", "Pop"),
    ("dream pop", "Pop"),
    # Overrides
    ("indie", "Rock"),
    ("folk", "Other / World"),
    ("reggae", "Other / World"),
    ("singer-songwriter", "Other / World"),
    # Catch-all
    ("bleep bloop mystery", "Other / World"),
    ("", "Other / World"),
])
def test_classify_genre(genre: str, expected: str) -> None:
    assert classify_genre(genre) == expected


# ---------------------------------------------------------------------------
# classify_genres — deduplication and ordering
# ---------------------------------------------------------------------------

def test_classify_genres_deduplicates() -> None:
    genres = ["indie rock", "classic rock", "hard rock"]
    cats = classify_genres(genres)
    assert cats == ["Rock"]


def test_classify_genres_multiple_categories() -> None:
    genres = ["rap", "pop", "indie rock"]
    cats = classify_genres(genres)
    assert "Rock" in cats
    assert "Pop" in cats
    assert "Rap / Hip-Hop" in cats
    assert len(cats) == 3


def test_classify_genres_respects_display_order() -> None:
    genres = ["pop", "rap", "rock"]
    cats = classify_genres(genres)
    indices = [ALL_CATEGORIES.index(c) for c in cats]
    assert indices == sorted(indices)


def test_classify_genres_empty() -> None:
    assert classify_genres([]) == []


def test_classify_genres_all_catch_all() -> None:
    genres = ["completely unknown genre xyz", "another mystery"]
    cats = classify_genres(genres)
    assert cats == ["Other / World"]


# ---------------------------------------------------------------------------
# augment_with_categories
# ---------------------------------------------------------------------------

def test_augment_preserves_original_genres() -> None:
    genres = ["indie rock", "alternative"]
    augmented = augment_with_categories(genres)
    assert "indie rock" in augmented
    assert "alternative" in augmented


def test_augment_adds_category_names_lowercase() -> None:
    genres = ["indie rock", "rap"]
    augmented = augment_with_categories(genres)
    assert "rock" in augmented
    assert "rap / hip-hop" in augmented


def test_augment_empty() -> None:
    assert augment_with_categories([]) == []


def test_augment_no_duplicates_in_categories() -> None:
    genres = ["indie rock", "classic rock", "alternative rock"]
    augmented = augment_with_categories(genres)
    # Should only have "rock" once as a category (lowercase)
    cat_entries = [g for g in augmented if g == "rock"]
    assert len(cat_entries) == 1


# ---------------------------------------------------------------------------
# ALL_CATEGORIES completeness
# ---------------------------------------------------------------------------

def test_all_categories_has_ten() -> None:
    assert len(ALL_CATEGORIES) == 10


def test_catch_all_is_last() -> None:
    assert ALL_CATEGORIES[-1] == "Other / World"
