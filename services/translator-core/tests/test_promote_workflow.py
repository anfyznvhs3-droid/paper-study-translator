"""Tests for the candidate -> confirmed promote workflow (task T2.5).

Acceptance contract. GREEN when every test passes without editing this file.
Run from services/translator-core:

    PYTHONPATH=src python -m pytest tests/test_promote_workflow.py -q

Full suite must stay green (regression gate):

    PYTHONPATH=src python -m pytest tests/ -q

State model: a source's CURRENT state = the status of its LAST-appended decision
in term-decisions.jsonl (append order wins, not timestamp comparison).
"""

import pytest

from qdt.memory import DomainMemoryStore, DomainNotFound, TermDecision

SLUG = "quality-manufacturing"


@pytest.fixture
def store(tmp_path):
    s = DomainMemoryStore(tmp_path)
    s.create_domain("Quality Manufacturing", SLUG)
    return s


def test_record_and_list_decisions_roundtrip(store):
    store.record_decision(SLUG, "control", "관리", status="candidate", confidence="low", origin="machine")
    decisions = store.list_decisions(SLUG)
    assert len(decisions) == 1
    d = decisions[0]
    assert (d.source, d.target, d.status, d.confidence, d.origin) == (
        "control", "관리", "candidate", "low", "machine",
    )


def test_list_decisions_empty_returns_empty(store):
    assert store.list_decisions(SLUG) == []


def test_record_decision_rejects_invalid_status(store):
    with pytest.raises(ValueError):
        store.record_decision(SLUG, "x", "y", status="bogus")


def test_list_candidates_returns_only_latest_candidate_sources(store):
    store.record_decision(SLUG, "control", "관리", status="candidate", confidence="low", origin="machine")
    store.record_decision(SLUG, "stress", "응력", status="candidate", confidence="low", origin="machine")
    # control is later confirmed -> its latest state is no longer "candidate"
    store.record_decision(SLUG, "control", "관리", status="confirmed", confidence="high", origin="user")
    assert {c.source for c in store.list_candidates(SLUG)} == {"stress"}


def test_promote_moves_candidate_into_glossary(store):
    store.record_decision(SLUG, "control", "관리", status="candidate", confidence="low", origin="machine")
    assert store.promote(SLUG, "control") is True
    assert {e.source: e.target for e in store.load_glossary(SLUG)} == {"control": "관리"}
    # promotion records a confirmed decision -> no longer a candidate
    assert {c.source for c in store.list_candidates(SLUG)} == set()


def test_promote_non_candidate_returns_false_and_leaves_glossary(store):
    assert store.promote(SLUG, "missing") is False
    assert store.load_glossary(SLUG) == []


def test_reject_adds_to_rejected_terms_and_clears_candidate(store):
    store.record_decision(SLUG, "FMEA", "", status="candidate", confidence="low", origin="machine")
    store.reject(SLUG, "FMEA", reason="keep acronym")
    assert "FMEA" in store.rejected_terms(SLUG)
    assert {c.source for c in store.list_candidates(SLUG)} == set()


def test_rejected_terms_empty_returns_empty_set(store):
    assert store.rejected_terms(SLUG) == set()


def test_list_decisions_unknown_domain_raises(tmp_path):
    s = DomainMemoryStore(tmp_path)
    with pytest.raises(DomainNotFound):
        s.list_decisions("nope")


def test_record_decision_unknown_domain_raises(tmp_path):
    s = DomainMemoryStore(tmp_path)
    with pytest.raises(DomainNotFound):
        s.record_decision("nope", "a", "b", status="candidate")
