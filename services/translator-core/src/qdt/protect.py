"""Global protected-span detector (task T2.8).

Pure function for finding spans that must NEVER be translated:
URLs, DOIs, emails, citation markers.
"""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"https?://\S+"),
    re.compile(r"\b10\.\d{4,}/\S+"),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    re.compile(r"\[\d+(?:[-,]\s*\d+)*\]"),
]


def find_protected_spans(text: str) -> list[str]:
    """Find protected spans (URL/DOI/email/citation) in order, deduped (first seen)."""
    if not text:
        return []

    seen: set[str] = set()
    result: list[str] = []

    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            span = match.group()
            if span not in seen:
                seen.add(span)
                result.append(span)

    result.sort(key=lambda s: text.index(s))
    return result
