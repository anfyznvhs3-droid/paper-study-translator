"""Deterministic candidate-term detection (task T2.2).

Pure functions for extracting potential terms from text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TermCandidate:
    source: str
    signal: str


_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")


def find_acronyms(text: str) -> list[str]:
    """Find uppercase runs of 2+ chars, dedup preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _ACRONYM_RE.finditer(text):
        word = match.group()
        if word not in seen:
            seen.add(word)
            result.append(word)
    return result


def find_residual_english(text: str, min_len: int = 4) -> list[str]:
    """Find Latin words of min_len+ chars, case-insensitive dedup, first-seen form preserved."""
    pattern = re.compile(rf"[A-Za-z]{{{min_len},}}")
    seen_lower: set[str] = set()
    result: list[str] = []
    for match in pattern.finditer(text):
        word = match.group()
        lower = word.lower()
        if lower not in seen_lower:
            seen_lower.add(lower)
            result.append(word)
    return result


def detect_candidates(text: str, confirmed: set[str] = frozenset()) -> list[TermCandidate]:
    """Detect candidate terms: acronyms first, then residual English, excluding confirmed."""
    if not text:
        return []

    confirmed_lower = {c.lower() for c in confirmed}

    acronyms = find_acronyms(text)
    acronym_lower = {a.lower() for a in acronyms}

    residuals = find_residual_english(text)

    result: list[TermCandidate] = []
    for a in acronyms:
        if a.lower() not in confirmed_lower:
            result.append(TermCandidate(source=a, signal="acronym"))

    for r in residuals:
        if r.lower() not in acronym_lower and r.lower() not in confirmed_lower:
            result.append(TermCandidate(source=r, signal="residual_english"))

    return result
