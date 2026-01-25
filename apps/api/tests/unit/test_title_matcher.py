"""Unit tests for title matching utilities used by repair."""

from __future__ import annotations

from services.title_matcher import (
    build_title_index,
    extract_asin_from_filename,
    match_m4b_to_asin,
    normalize_title,
    quick_lookup,
)


def test_extract_asin_from_filename_asin_prefix() -> None:
    asin, title = extract_asin_from_filename("B012345678_My Book-AAX_64_22050.aaxc")
    assert asin == "B012345678"
    assert "My Book" in (title or "")


def test_match_m4b_to_asin_prefers_metadata_asin() -> None:
    result = match_m4b_to_asin(
        "/converted/Some Title.m4b",
        books=[{"asin": "B012345678", "title": "Some Title"}],
        metadata_asin="b012345678",
    )
    assert result.matched is True
    assert result.asin == "B012345678"
    assert result.match_method == "metadata_tag"


def test_match_m4b_to_asin_filename_prefix() -> None:
    result = match_m4b_to_asin(
        "/converted/B012345678_Some Title.m4b",
        books=[{"asin": "B999999999", "title": "Other"}],
        metadata_asin=None,
    )
    assert result.matched is True
    assert result.asin == "B012345678"
    assert result.match_method in {"asin_prefix", "isbn_prefix"}


def test_match_m4b_to_asin_title_normalization_strips_series_suffix() -> None:
    books = [{"asin": "B012345678", "title": "The Stormlight Archive"}]
    result = match_m4b_to_asin(
        "/converted/The Stormlight Archive, Book 2.m4b",
        books=books,
        metadata_asin=None,
        threshold=0.5,
    )
    assert result.matched is True
    assert result.asin == "B012345678"
    assert normalize_title("The Stormlight Archive, Book 2") == normalize_title("The Stormlight Archive")


def test_build_title_index_and_quick_lookup_does_not_overwrite_duplicates() -> None:
    books = [
        {"asin": "B001", "title": "Same Title"},
        {"asin": "B002", "title": "Same Title"},
        {"asin": "B003", "title": "Other"},
    ]
    idx = build_title_index(books)
    assert quick_lookup("Same Title", idx) == "B001"
    assert quick_lookup("Other", idx) == "B003"

