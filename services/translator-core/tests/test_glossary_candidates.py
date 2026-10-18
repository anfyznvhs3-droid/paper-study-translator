"""Tests for the reusable glossary-candidate / term-consistency miner."""

from qdt.glossary_candidates import (
    build_report,
    extract_candidates,
    find_cell_conflicts,
    find_term_drift,
    is_term_like,
    normalize_source,
)


def test_is_term_like_accepts_short_terms_rejects_prose_and_ids():
    assert is_term_like("Control Plan")
    assert is_term_like("detection control")
    assert not is_term_like("The supplier shall retain PPAP evidence. It is required.")  # sentence
    assert not is_term_like("a much longer phrase that is clearly prose not a term")  # >4 tokens
    assert not is_term_like("MRB-LOT-8821")  # bare identifier
    assert not is_term_like("123")  # number


def test_normalize_source_collapses_case_space_punctuation():
    assert normalize_source("  Access   Control. ") == "access control"
    assert normalize_source("Disposition:") == "disposition"


def test_extract_candidates_keeps_translated_terms_only():
    rows = [
        {"source": "Control Plan", "translation": "관리계획서"},
        {"source": "Abstract", "translation": "초록"},
        {"source": "RQ-1", "translation": "RQ-1"},  # identifier, no hangul -> skipped
        {"source": "A whole sentence here, definitely prose text.", "translation": "문장"},  # prose
    ]
    cands = extract_candidates(rows)
    assert "control plan" in cands
    assert "abstract" in cands
    assert "rq-1" not in cands


def test_find_cell_conflicts_flags_same_cell_translated_two_ways():
    rows = [
        {"source": "Disposition", "translation": "처분 판정"},
        {"source": "disposition.", "translation": "처리 판정"},  # same cell up to case/punct
        {"source": "Control", "translation": "관리"},
    ]
    conflicts = find_cell_conflicts(rows)
    assert len(conflicts) == 1
    assert set(conflicts[0]["variants"]) == {"처분 판정", "처리 판정"}


def test_find_term_drift_flags_inconsistent_term_across_sentences():
    rows = [
        {"source": "control", "translation": "관리"},  # canonical
        {"source": "detection control review", "translation": "검출 관리 검토"},  # consistent
        {"source": "Access control review should include owner", "translation": "접근 통제 검토에는 소유자가 포함된다"},  # drift -> 통제
    ]
    drift = find_term_drift(rows)
    terms = {d["term"]: d for d in drift}
    assert "control" in terms
    assert terms["control"]["canonical"] == "관리"
    assert terms["control"]["inconsistent"] >= 1


def test_build_report_is_report_only_and_combines_signals():
    rows = [
        {"source": "control", "translation": "관리"},
        {"source": "Access control matrix", "translation": "접근 통제 매트릭스"},
        {"source": "Cell", "translation": "셀1"},
        {"source": "cell", "translation": "셀2"},
    ]
    report = build_report(rows)
    assert report.candidates  # glossary candidates extracted
    assert any(c["term"] == "control" for c in report.term_drift)
    assert report.conflicts  # "Cell"/"cell" cell conflict
