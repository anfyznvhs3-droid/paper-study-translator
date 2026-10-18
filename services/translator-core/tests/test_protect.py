"""Tests for the global (domain-agnostic) protected-span detector (task T2.8).

Spans that must NEVER be translated, in any domain: URLs, DOIs, emails,
citation markers like [1], [2, 3], [12-15].

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_protect.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

from qdt.protect import find_protected_spans


def test_finds_urls():
    assert "https://example.org/a/b" in find_protected_spans("see https://example.org/a/b here")


def test_finds_doi():
    spans = find_protected_spans("DOI 10.1016/j.weld.2020.01 reference")
    assert any(s.startswith("10.1016/") for s in spans)


def test_finds_email():
    assert "a.b@lab.org" in find_protected_spans("contact a.b@lab.org now")


def test_finds_citation_markers():
    spans = find_protected_spans("as shown [1] and [2, 3] and [12-15].")
    assert "[1]" in spans
    assert "[2, 3]" in spans
    assert "[12-15]" in spans


def test_plain_text_returns_empty():
    assert find_protected_spans("순수 한국어 텍스트, 보호할 것 없음") == []


def test_dedup_preserves_first_seen():
    assert find_protected_spans("ref [1] and again [1] end") == ["[1]"]
