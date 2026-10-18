"""Tests for deterministic candidate-term detection (task T2.2).

Acceptance contract. GREEN when every test passes without editing this file.
Run from services/translator-core:

    PYTHONPATH=src python -m pytest tests/test_detect.py -q

Full suite must stay green (regression gate):

    PYTHONPATH=src python -m pytest tests/ -q
"""

from qdt.detect import TermCandidate, detect_candidates, find_acronyms, find_residual_english


def test_find_acronyms_extracts_uppercase_runs():
    assert find_acronyms("The FMEA and IATF and DOI here") == ["FMEA", "IATF", "DOI"]


def test_find_acronyms_dedups_preserving_first_seen_order():
    assert find_acronyms("FMEA then FMEA again and APQP") == ["FMEA", "APQP"]


def test_find_acronyms_ignores_single_caps_and_lowercase():
    assert find_acronyms("A bC the Word and ok") == []


def test_find_residual_english_finds_long_latin_words():
    assert find_residual_english("번역 process 그리고 control 끝") == ["process", "control"]


def test_find_residual_english_min_len_excludes_short_words():
    # default min_len=4: "the" (3) excluded, "data" (4) included
    assert find_residual_english("한국어 the data") == ["data"]


def test_find_residual_english_dedups_case_insensitive_first_seen():
    assert find_residual_english("Data and data and DATA") == ["Data"]


def test_detect_candidates_labels_signals_with_acronym_precedence():
    by_source = {c.source: c.signal for c in detect_candidates("The FMEA process here")}
    assert by_source["FMEA"] == "acronym"
    assert by_source["process"] == "residual_english"


def test_detect_candidates_excludes_confirmed_case_insensitive():
    sources = {c.source for c in detect_candidates("The FMEA process", confirmed={"fmea"})}
    assert "FMEA" not in sources
    assert "process" in sources


def test_detect_candidates_returns_term_candidate_instances():
    cands = detect_candidates("FMEA")
    assert cands == [TermCandidate(source="FMEA", signal="acronym")]


def test_detect_candidates_empty_text_returns_empty():
    assert detect_candidates("") == []
