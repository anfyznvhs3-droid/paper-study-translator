"""Tests for the core service layer that assembles the WIKI pieces (task T2.7a).

Composes DomainMemoryStore (glossary + rejected) with apply_glossary and
detect_candidates into the two operations the translation pipeline calls.

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_service.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

from qdt.memory import DomainMemoryStore
from qdt.service import run_apply, run_detect


def _store(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Quality", "q")
    return store


def test_run_apply_replaces_confirmed_terms(tmp_path):
    store = _store(tmp_path)
    store.add_term("q", "FMEA", "고장모드")
    assert run_apply(tmp_path, "q", "The FMEA process") == "The 고장모드 process"


def test_run_apply_respects_rejected_terms(tmp_path):
    store = _store(tmp_path)
    store.add_term("q", "FMEA", "고장모드")
    store.reject("q", "FMEA", reason="keep acronym")
    assert run_apply(tmp_path, "q", "The FMEA process") == "The FMEA process"


def test_run_apply_empty_glossary_returns_text(tmp_path):
    _store(tmp_path)
    assert run_apply(tmp_path, "q", "nothing to change") == "nothing to change"


def test_run_detect_excludes_confirmed_glossary_terms(tmp_path):
    store = _store(tmp_path)
    store.add_term("q", "FMEA", "고장모드")
    sources = {c.source for c in run_detect(tmp_path, "q", "The FMEA and IATF process")}
    assert "FMEA" not in sources   # already confirmed in glossary
    assert "IATF" in sources       # new acronym -> candidate


def test_run_detect_on_empty_glossary_returns_all_signals(tmp_path):
    _store(tmp_path)
    sources = {c.source for c in run_detect(tmp_path, "q", "FMEA process")}
    assert sources == {"FMEA", "process"}
