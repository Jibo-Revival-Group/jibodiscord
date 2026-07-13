"""Parse define-word commands ported from OpenJibo DefineCommandParser."""

from __future__ import annotations

import re

from jibo.normalize import normalize_transcript

_PREFIX_PATTERNS = (
    "what is the definition of",
    "what s the definition of",
    "define the word",
    "define",
)

_WHAT_DOES_MEAN = re.compile(r"^what does (?P<word>.+) mean$", re.I)


def _clean_word(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    cleaned = value.strip().rstrip("?!.,")
    if not cleaned or not any(char.isalpha() for char in cleaned):
        return None
    return cleaned


def is_define_request(transcript: str) -> bool:
    return try_parse_define_word(transcript) is not None or _matches_define_without_word(transcript)


def _matches_define_without_word(transcript: str) -> bool:
    normalized = normalize_transcript(transcript)
    if not normalized:
        return False
    return normalized in _PREFIX_PATTERNS


def try_parse_define_word(transcript: str) -> str | None:
    normalized = normalize_transcript(transcript)
    if not normalized:
        return None

    for prefix in _PREFIX_PATTERNS:
        if normalized == prefix:
            return None
        prefix_with_space = f"{prefix} "
        if normalized.startswith(prefix_with_space):
            return _clean_word(normalized[len(prefix_with_space) :])

    match = _WHAT_DOES_MEAN.match(normalized)
    if match:
        return _clean_word(match.group("word"))
    return None
