"""Tests for the machine-mode glossary apply layer (task T2.3).

Acceptance contract. GREEN when every test passes without editing this file.
Run from services/translator-core:

    PYTHONPATH=src python -m pytest tests/test_apply.py -q

Full suite must stay green (regression gate):

    PYTHONPATH=src python -m pytest tests/ -q

CRITICAL GUARDRAIL: a source listed in `rejected` is NEVER replaced, even if it
also appears in the glossary. This is the silent-error defense.
"""

from qdt.apply import apply_glossary


def test_replaces_whole_word_case_insensitive():
    out = apply_glossary("The FMEA and fmea process", {"FMEA": "고장모드"})
    assert out == "The 고장모드 and 고장모드 process"


def test_replaces_whole_word_only_not_substrings():
    assert apply_glossary("FMEAX done", {"FMEA": "고장모드"}) == "FMEAX done"


def test_replaces_multiple_terms():
    out = apply_glossary("FMEA and APQP", {"FMEA": "고장모드", "APQP": "사전제품품질계획"})
    assert out == "고장모드 and 사전제품품질계획"


def test_empty_glossary_leaves_text_unchanged():
    assert apply_glossary("nothing here", {}) == "nothing here"


def test_rejected_term_is_never_replaced():
    out = apply_glossary("The FMEA here", {"FMEA": "고장모드"}, rejected={"FMEA"})
    assert out == "The FMEA here"


def test_rejected_match_is_case_insensitive():
    out = apply_glossary("The FMEA here", {"FMEA": "고장모드"}, rejected={"fmea"})
    assert out == "The FMEA here"


def test_only_listed_terms_are_rejected():
    out = apply_glossary(
        "FMEA and APQP", {"FMEA": "고장모드", "APQP": "사전제품품질계획"}, rejected={"FMEA"}
    )
    assert out == "FMEA and 사전제품품질계획"
