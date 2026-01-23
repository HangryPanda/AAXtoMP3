"""
Title matching utilities for robust ASIN extraction from filenames.

Based on analysis of actual file naming patterns:
- Downloads: ASIN_Title-AAX_XX_XXX.aaxc or ISBN_Title-AAX_XX_XXX.aaxc
- Converted: Title.m4b (no ASIN, organized by author folders)
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass
class TitleMatchResult:
    """Result of a title match operation."""
    matched: bool
    asin: str | None
    confidence: float  # 0.0 to 1.0
    match_method: str  # "asin_prefix", "isbn_prefix", "metadata_tag", "title_exact", "title_fuzzy"
    normalized_title: str
    original_title: str


# Regex patterns based on observed file naming conventions
ASIN_PREFIX_PATTERN = re.compile(r'^(B[A-Z0-9]{9})_(.+?)(?:-AAX_\d{2}_\d+)?(?:\.aaxc?)?$', re.IGNORECASE)
ISBN_PREFIX_PATTERN = re.compile(r'^(\d{10})_(.+?)(?:-AAX_\d{2}_\d+)?(?:\.aaxc?)?$')
AUDIO_SPEC_SUFFIX = re.compile(r'-AAX_\d{2}_\d+$')

# Series/book number patterns to strip for matching
SERIES_PATTERNS = [
    re.compile(r',?\s*Book\s+\d+\s*$', re.IGNORECASE),
    re.compile(r',?\s*Volume\s+\d+\s*$', re.IGNORECASE),
    re.compile(r',?\s*Part\s+\d+\s*$', re.IGNORECASE),
    re.compile(r',?\s*#\d+\s*$'),
    re.compile(r'\s*\(\s*Book\s+\d+\s*\)\s*$', re.IGNORECASE),
    re.compile(r'\s*\[\s*Book\s+\d+\s*\]\s*$', re.IGNORECASE),
    # Series name suffix like "The Stormlight Archive, Book 2"
    re.compile(r',\s*[^,]+,\s*Book\s+\d+\s*$', re.IGNORECASE),
]

# Common subtitle/edition patterns
EDITION_PATTERNS = [
    re.compile(r'\s*\(Unabridged\)\s*$', re.IGNORECASE),
    re.compile(r'\s*\[Unabridged\]\s*$', re.IGNORECASE),
    re.compile(r'\s*\(Full[- ]Cast Edition\)\s*$', re.IGNORECASE),
    re.compile(r'\s*\[Dramatized Adaptation\]\s*$', re.IGNORECASE),
    re.compile(r'\s*\(Dramatized\)\s*$', re.IGNORECASE),
]

# Characters to normalize
PUNCTUATION_MAP = {
    ':': ' ',
    ';': ' ',
    '—': ' ',
    '–': ' ',
    '"': '',
    '"': '',
    '"': '',
    "'": '',
    ''': '',
    ''': '',
    '…': '',
    '&': 'and',
}


def extract_asin_from_filename(filename: str) -> tuple[str | None, str | None]:
    """
    Extract ASIN/ISBN and title from a download filename.

    Returns:
        Tuple of (asin_or_isbn, extracted_title) or (None, None) if no match.
    """
    # Remove path if present
    name = Path(filename).stem if '/' in filename or '\\' in filename else filename

    # Remove extension if present
    for ext in ['.aaxc', '.aax', '.m4b', '.m4a', '.mp3']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]

    # Try ASIN pattern (B + 9 alphanumeric)
    match = ASIN_PREFIX_PATTERN.match(name)
    if match:
        asin = match.group(1).upper()
        title = match.group(2)
        # Remove audio spec suffix if present
        title = AUDIO_SPEC_SUFFIX.sub('', title)
        return asin, title

    # Try ISBN pattern (10 digits)
    match = ISBN_PREFIX_PATTERN.match(name)
    if match:
        isbn = match.group(1)
        title = match.group(2)
        title = AUDIO_SPEC_SUFFIX.sub('', title)
        return isbn, title

    return None, None


def normalize_title(title: str) -> str:
    """
    Normalize a title for comparison.

    Handles:
    - Case normalization
    - Unicode normalization
    - Punctuation removal/replacement
    - Series/book number stripping
    - Edition text removal
    - Whitespace normalization
    """
    if not title:
        return ""

    # Unicode normalize (handle accents, etc.)
    normalized = unicodedata.normalize('NFKD', title)

    # Lowercase
    normalized = normalized.lower()

    # Replace punctuation
    for char, replacement in PUNCTUATION_MAP.items():
        normalized = normalized.replace(char, replacement)

    # Remove edition patterns
    for pattern in EDITION_PATTERNS:
        normalized = pattern.sub('', normalized)

    # Remove series/book number patterns
    for pattern in SERIES_PATTERNS:
        normalized = pattern.sub('', normalized)

    # Remove remaining punctuation except spaces and alphanumeric
    normalized = re.sub(r'[^\w\s]', ' ', normalized)

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized.strip()


def extract_title_from_path(filepath: str) -> str:
    """
    Extract title from a converted file path.

    Handles paths like:
    - /Audiobook/Author Name/Book Title/Book Title.m4b
    - /Author Name/Book Title.m4b
    - Book Title.m4b
    """
    path = Path(filepath)

    # Get stem (filename without extension)
    title = path.stem

    return title


def similarity_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1, s2).ratio()


def match_title_to_books(
    title: str,
    books: list[dict[str, Any]],
    threshold: float = 0.85
) -> TitleMatchResult | None:
    """
    Match a title against a list of books.

    Args:
        title: The title to match (from filename or metadata)
        books: List of book dicts with 'asin' and 'title' keys
        threshold: Minimum similarity ratio for fuzzy match (0.0-1.0)

    Returns:
        TitleMatchResult if match found, None otherwise.
    """
    if not title or not books:
        return None

    normalized_input = normalize_title(title)

    best_match = None
    best_score = 0.0

    for book in books:
        book_title = book.get('title', '')
        book_asin = book.get('asin', '')

        if not book_title:
            continue

        normalized_book = normalize_title(book_title)

        # Exact match (after normalization)
        if normalized_input == normalized_book:
            return TitleMatchResult(
                matched=True,
                asin=book_asin,
                confidence=1.0,
                match_method="title_exact",
                normalized_title=normalized_input,
                original_title=title,
            )

        # Fuzzy match
        score = similarity_ratio(normalized_input, normalized_book)

        # Also try matching with the input as a substring or vice versa
        if normalized_input in normalized_book or normalized_book in normalized_input:
            # Boost score for substring matches
            substring_score = max(len(normalized_input), len(normalized_book)) / max(len(normalized_input), len(normalized_book), 1)
            score = max(score, substring_score * 0.95)

        if score > best_score:
            best_score = score
            best_match = book

    if best_match and best_score >= threshold:
        return TitleMatchResult(
            matched=True,
            asin=best_match.get('asin'),
            confidence=best_score,
            match_method="title_fuzzy",
            normalized_title=normalized_input,
            original_title=title,
        )

    return None


def match_m4b_to_asin(
    m4b_path: str,
    books: list[dict[str, Any]],
    metadata_asin: str | None = None,
    threshold: float = 0.85
) -> TitleMatchResult:
    """
    Attempt to match an M4B file to an ASIN using multiple strategies.

    Strategy order:
    1. Metadata ASIN tag (if provided and valid)
    2. ASIN/ISBN prefix in filename (rare for M4B but possible)
    3. Title matching against book database

    Args:
        m4b_path: Path to the M4B file
        books: List of book dicts with 'asin' and 'title' keys
        metadata_asin: ASIN extracted from file metadata tags (if any)
        threshold: Minimum similarity for fuzzy title matching

    Returns:
        TitleMatchResult with match details.
    """
    title = extract_title_from_path(m4b_path)
    normalized = normalize_title(title)

    # Strategy 1: Use metadata ASIN if valid
    if metadata_asin and re.match(r'^B[A-Z0-9]{9}$', metadata_asin, re.IGNORECASE):
        return TitleMatchResult(
            matched=True,
            asin=metadata_asin.upper(),
            confidence=1.0,
            match_method="metadata_tag",
            normalized_title=normalized,
            original_title=title,
        )

    # Strategy 2: Try to extract ASIN from filename
    asin, extracted_title = extract_asin_from_filename(m4b_path)
    if asin:
        return TitleMatchResult(
            matched=True,
            asin=asin,
            confidence=0.99,
            match_method="asin_prefix" if asin.startswith('B') else "isbn_prefix",
            normalized_title=normalize_title(extracted_title or title),
            original_title=title,
        )

    # Strategy 3: Title matching
    match_result = match_title_to_books(title, books, threshold)
    if match_result:
        return match_result

    # No match found
    return TitleMatchResult(
        matched=False,
        asin=None,
        confidence=0.0,
        match_method="none",
        normalized_title=normalized,
        original_title=title,
    )


def build_title_index(books: list[dict[str, Any]]) -> dict[str, str]:
    """
    Build a normalized title -> ASIN index for fast lookups.

    Args:
        books: List of book dicts with 'asin' and 'title' keys

    Returns:
        Dict mapping normalized titles to ASINs.
    """
    index = {}
    for book in books:
        title = book.get('title', '')
        asin = book.get('asin', '')
        if title and asin:
            normalized = normalize_title(title)
            if normalized not in index:  # Don't overwrite if duplicate titles
                index[normalized] = asin
    return index


def quick_lookup(title: str, title_index: dict[str, str]) -> str | None:
    """
    Quick exact-match lookup using pre-built index.

    Args:
        title: Title to look up
        title_index: Dict from build_title_index()

    Returns:
        ASIN if found, None otherwise.
    """
    normalized = normalize_title(title)
    return title_index.get(normalized)
