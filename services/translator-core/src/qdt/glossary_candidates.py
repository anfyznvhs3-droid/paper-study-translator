"""Mine reusable glossary candidates and term-consistency conflicts from a
translation map.

Failure mode this absorbs: batch agent translation renders the same domain term
or repeated table cell inconsistently across batches, so the document loses term
consistency (e.g. ``disposition`` -> 처분 판정 / 처리 판정, ``access control`` ->
접근 통제 / 접근 관리). Rather than hard-coding a fix for specific terms, this
turns the error into a reusable signal:

* ``extract_candidates`` pulls the agent's own term -> translation decisions from
  short, term-like entries. The result is a domain-neutral glossary-candidate
  set that can enrich the domain glossary, which is already fed to the agent
  prompt — so future runs become consistent without forcing anything.
* ``find_cell_conflicts`` flags entries whose source is identical up to
  case/whitespace/punctuation but whose translation differs (the same table cell
  translated two ways). These become audit review items.

This is report-only: it never rewrites a translation, so it is safe by default
and needs no kill switch.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_SENTENCE_END = re.compile(r"[.!?]\s")
_WORDISH = re.compile(r"[A-Za-z][A-Za-z0-9/&+.-]*")


def normalize_source(text: str) -> str:
    """Collapse whitespace, drop trailing punctuation and case for matching."""
    collapsed = " ".join(text.split()).strip().casefold()
    return collapsed.rstrip(".:;,").strip()


def is_term_like(source: str) -> bool:
    """True for short, header/cell/term-like English strings (not sentences)."""
    s = source.strip()
    if not s or not _LATIN.search(s):
        return False
    if _SENTENCE_END.search(s):  # contains a sentence break -> prose
        return False
    tokens = s.split()
    if not (1 <= len(tokens) <= 4):
        return False
    # Exclude bare identifiers / codes (kept verbatim, not glossary terms).
    if re.fullmatch(r"[A-Z0-9][A-Z0-9/\-]*", s):
        return False
    return True


def extract_candidates(rows: list[dict]) -> dict[str, Counter]:
    """term (normalized English) -> Counter of observed Korean translations."""
    candidates: dict[str, Counter] = {}
    for row in rows:
        source = str(row.get("source", "")).strip()
        translation = str(row.get("translation", "")).strip()
        if not is_term_like(source):
            continue
        if not _HANGUL.search(translation):  # untranslated / preserved -> skip
            continue
        if source.casefold() == translation.casefold():
            continue
        candidates.setdefault(normalize_source(source), Counter())[translation] += 1
    return candidates


def find_cell_conflicts(rows: list[dict]) -> list[dict]:
    """Sources identical up to case/space/punctuation but translated differently."""
    by_norm: dict[str, dict] = {}
    for row in rows:
        source = str(row.get("source", "")).strip()
        translation = str(row.get("translation", "")).strip()
        if not source:
            continue
        key = normalize_source(source)
        entry = by_norm.setdefault(key, {"sources": set(), "translations": Counter()})
        entry["sources"].add(source)
        entry["translations"][translation] += 1

    conflicts: list[dict] = []
    for key, entry in by_norm.items():
        distinct = [t for t in entry["translations"] if t.strip()]
        if len(distinct) > 1:
            ranked = entry["translations"].most_common()
            conflicts.append(
                {
                    "source": sorted(entry["sources"])[0],
                    "variants": [t for t, _ in ranked],
                    "suggested": ranked[0][0],
                }
            )
    return conflicts


def find_term_drift(rows: list[dict]) -> list[dict]:
    """Single-word English terms whose canonical Korean is missing from some of
    their occurrences across the document — i.e. the term drifted to a different
    translation in another sentence/cell (e.g. ``control`` -> 관리 here, 통제 there).

    Heuristic and report-only: it can't word-align, so it reports the term, the
    canonical Korean (most common standalone rendering), and the occurrences that
    do not contain it, as review candidates — not assertions.
    """
    candidates = extract_candidates(rows)
    single = {
        term: counter.most_common(1)[0][0]
        for term, counter in candidates.items()
        if len(term.split()) == 1
    }
    drift: list[dict] = []
    for term, canonical in single.items():
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        missing: list[str] = []
        occurrences = 0
        for row in rows:
            source = str(row.get("source", ""))
            if not pattern.search(source):
                continue
            occurrences += 1
            translation = str(row.get("translation", "")).strip()
            if not _HANGUL.search(translation):  # preserved/untranslated, ignore
                continue
            if canonical not in translation:
                missing.append(translation)
        if occurrences >= 2 and missing:
            drift.append(
                {
                    "term": term,
                    "canonical": canonical,
                    "occurrences": occurrences,
                    "inconsistent": len(missing),
                    "examples": missing[:3],
                }
            )
    drift.sort(key=lambda d: d["inconsistent"], reverse=True)
    return drift


@dataclass
class GlossaryReport:
    candidates: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    term_drift: list[dict] = field(default_factory=list)


def build_report(rows: list[dict]) -> GlossaryReport:
    """Build the glossary-candidate + conflict report for one translation map."""
    candidate_index = extract_candidates(rows)
    candidates: list[dict] = []
    for term, counter in sorted(candidate_index.items()):
        ranked = counter.most_common()
        candidates.append(
            {
                "term": term,
                "suggested": ranked[0][0],
                "variants": [t for t, _ in ranked],
                "ambiguous": len(ranked) > 1,
            }
        )
    return GlossaryReport(
        candidates=candidates,
        conflicts=find_cell_conflicts(rows),
        term_drift=find_term_drift(rows),
    )
