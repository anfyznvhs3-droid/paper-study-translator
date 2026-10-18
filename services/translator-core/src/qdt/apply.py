"""Machine-mode glossary apply layer (task T2.3).

Pure function for applying confirmed glossary terms to text,
with rejected-term guardrail.
"""

from __future__ import annotations

import re


def apply_glossary(
    text: str,
    glossary: dict[str, str],
    rejected: set[str] = frozenset(),
) -> str:
    """Apply glossary replacements to text.

    - Case-insensitive whole-word matching.
    - Terms in `rejected` (case-insensitive) are NEVER replaced.
    - Empty glossary returns text unchanged.
    """
    if not glossary:
        return text

    rejected_lower = {r.lower() for r in rejected}
    result = text

    for source, target in glossary.items():
        if source.lower() in rejected_lower:
            continue
        pattern = re.compile(rf"\b{re.escape(source)}\b", re.IGNORECASE)
        result = pattern.sub(target, result)

    return result
