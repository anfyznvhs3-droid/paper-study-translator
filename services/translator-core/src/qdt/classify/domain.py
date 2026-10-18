"""Keyword-based domain proposal (task T2.1a).

Pure function for proposing a domain based on keyword matches.
"""

from __future__ import annotations

import re


def propose_domain(text: str, domain_keywords: dict[str, list[str]]) -> str | None:
    """Propose the best-matching domain based on keyword hits.

    Score = number of a domain's keywords present (whole-word, case-insensitive) in text.
    Highest score wins; ties break to first-inserted domain; zero -> None.
    """
    if not text:
        return None

    best_slug: str | None = None
    best_score = 0

    for slug, keywords in domain_keywords.items():
        score = 0
        for keyword in keywords:
            pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
            if pattern.search(text):
                score += 1
        if score > best_score:
            best_score = score
            best_slug = slug

    return best_slug if best_score > 0 else None
