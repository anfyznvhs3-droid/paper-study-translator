"""Core service layer assembling WIKI pieces (task T2.7a).

Composes DomainMemoryStore with apply_glossary and detect_candidates.
"""

from __future__ import annotations

from pathlib import Path

from qdt.apply import apply_glossary
from qdt.detect import TermCandidate, detect_candidates
from qdt.memory import DomainMemoryStore


def run_apply(store_root: str | Path, slug: str, text: str) -> str:
    """Apply confirmed glossary terms to text, respecting rejected terms."""
    store = DomainMemoryStore(store_root)
    glossary_dict = {entry.source: entry.target for entry in store.load_glossary(slug)}
    rejected = store.rejected_terms(slug)
    return apply_glossary(text, glossary_dict, rejected)


def run_detect(store_root: str | Path, slug: str, text: str) -> list[TermCandidate]:
    """Detect candidate terms, excluding already-confirmed glossary entries."""
    store = DomainMemoryStore(store_root)
    confirmed = {entry.source for entry in store.load_glossary(slug)}
    return detect_candidates(text, confirmed)
