"""Tests for glossary-injectable apply_term_overrides (task T2.7b, testable slice).

Mirrors the T1.4 lookup_term_override injection pattern. GREEN when these pass
without editing this file.

    cd services/mixed-renderer && PYTHONPATH=".:../scholar-translator" python -m pytest test_apply_overrides.py -q

Regression gate (must stay green):

    cd services/mixed-renderer && PYTHONPATH=".:../scholar-translator" python -m pytest -q
"""

import qdt_mixed_renderer as mr


def test_apply_term_overrides_without_overrides_keeps_builtin_behavior():
    # back-compat: exact-source match returns the TERM_OVERRIDES value
    assert mr.apply_term_overrides("knowledge", "knowledge") == "지식"


def test_apply_term_overrides_uses_injected_glossary():
    # "control" is not in TERM_OVERRIDES; the injected glossary applies it
    out = mr.apply_term_overrides("control system", "control system", overrides={"control": "관리"})
    assert "관리" in out


def test_apply_term_overrides_glossary_takes_precedence():
    # "knowledge" -> "지식" in TERM_OVERRIDES; glossary overrides it when provided
    assert mr.apply_term_overrides("knowledge", "knowledge", overrides={"knowledge": "지식정보"}) == "지식정보"
