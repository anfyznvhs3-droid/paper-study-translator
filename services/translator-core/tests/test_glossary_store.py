"""Tests for glossary.csv CRUD on DomainMemoryStore (task T1.3a).

These are the acceptance contract. The task is GREEN when every test here passes
without modifying this file. Run from services/translator-core:

    PYTHONPATH=src python -m pytest tests/test_glossary_store.py -q
"""

import pytest

from qdt.memory import DomainMemoryStore, DomainNotFound, GlossaryEntry


@pytest.fixture
def store(tmp_path):
    s = DomainMemoryStore(tmp_path)
    s.create_domain("Quality Manufacturing", "quality-manufacturing")
    return s


def test_load_glossary_empty_returns_empty_list(store):
    # create_domain writes a header-only glossary.csv → no entries yet.
    assert store.load_glossary("quality-manufacturing") == []


def test_add_term_then_load_returns_entry(store):
    store.add_term("quality-manufacturing", "Failure Mode", "고장모드", notes="approved")
    assert store.load_glossary("quality-manufacturing") == [
        GlossaryEntry(source="Failure Mode", target="고장모드", notes="approved")
    ]


def test_add_term_defaults_notes_to_empty_string(store):
    store.add_term("quality-manufacturing", "Control Plan", "관리계획서")
    assert store.load_glossary("quality-manufacturing")[0].notes == ""


def test_add_term_upserts_on_duplicate_source_case_insensitive(store):
    store.add_term("quality-manufacturing", "FMEA", "고장모드 및 영향분석")
    store.add_term("quality-manufacturing", "fmea", "고장형태 및 영향분석(FMEA)")
    entries = store.load_glossary("quality-manufacturing")
    assert len(entries) == 1
    assert entries[0].target == "고장형태 및 영향분석(FMEA)"


def test_add_term_appends_without_clobbering_existing(store):
    store.add_term("quality-manufacturing", "FMEA", "고장모드 및 영향분석")
    store.add_term("quality-manufacturing", "Control Plan", "관리계획서")
    sources = {e.source for e in store.load_glossary("quality-manufacturing")}
    assert sources == {"FMEA", "Control Plan"}


def test_delete_term_removes_and_returns_true(store):
    store.add_term("quality-manufacturing", "FMEA", "고장모드 및 영향분석")
    assert store.delete_term("quality-manufacturing", "fmea") is True
    assert store.load_glossary("quality-manufacturing") == []


def test_delete_term_missing_returns_false_and_keeps_others(store):
    store.add_term("quality-manufacturing", "FMEA", "고장모드 및 영향분석")
    assert store.delete_term("quality-manufacturing", "Nonexistent") is False
    assert len(store.load_glossary("quality-manufacturing")) == 1


def test_notes_with_comma_roundtrips(store):
    store.add_term("quality-manufacturing", "shall", "하여야 한다", notes="mandatory, IATF modal")
    assert store.load_glossary("quality-manufacturing")[0].notes == "mandatory, IATF modal"


def test_korean_unicode_roundtrips(store):
    store.add_term("quality-manufacturing", "Action Priority", "조치 우선순위(Action Priority)")
    assert store.load_glossary("quality-manufacturing")[0].target == "조치 우선순위(Action Priority)"


def test_load_glossary_unknown_domain_raises(tmp_path):
    store = DomainMemoryStore(tmp_path)
    with pytest.raises(DomainNotFound):
        store.load_glossary("does-not-exist")


def test_add_term_unknown_domain_raises(tmp_path):
    store = DomainMemoryStore(tmp_path)
    with pytest.raises(DomainNotFound):
        store.add_term("does-not-exist", "x", "y")


def test_delete_term_unknown_domain_raises(tmp_path):
    store = DomainMemoryStore(tmp_path)
    with pytest.raises(DomainNotFound):
        store.delete_term("does-not-exist", "x")
