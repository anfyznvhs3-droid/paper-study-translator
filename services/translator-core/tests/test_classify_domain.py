"""Tests for keyword-based domain proposal (task T2.1a).

Acceptance contract. GREEN when every test passes without editing this file.
Run from services/translator-core:

    PYTHONPATH=src python -m pytest tests/test_classify_domain.py -q

Full suite must stay green (regression gate):

    PYTHONPATH=src python -m pytest tests/ -q

Score = number of a domain's keywords present (whole-word, case-insensitive) in
the text. Highest score wins; ties break to the first-inserted domain; zero -> None.
"""

from qdt.classify.domain import propose_domain

KW = {
    "quality-manufacturing": ["FMEA", "control plan", "APQP"],
    "medical": ["patient", "dose", "clinical"],
}


def test_proposes_domain_with_keyword_hits():
    assert propose_domain("The FMEA and control plan review", KW) == "quality-manufacturing"


def test_matching_is_case_insensitive():
    assert propose_domain("fmea results here", KW) == "quality-manufacturing"


def test_returns_none_when_no_keyword_matches():
    assert propose_domain("아무 신호 없는 한국어 텍스트", KW) is None


def test_picks_higher_scoring_domain():
    # medical: patient, dose, clinical = 3 ; quality: FMEA = 1
    assert propose_domain("patient dose clinical and FMEA", KW) == "medical"


def test_whole_word_only_not_substring():
    assert propose_domain("increase the dosage today", {"medical": ["dose"]}) is None


def test_tie_breaks_to_first_inserted_domain():
    assert propose_domain("foo bar", {"a": ["foo"], "b": ["bar"]}) == "a"


def test_empty_text_returns_none():
    assert propose_domain("", KW) is None
