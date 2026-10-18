"""Tests for the qdt WIKI CLI (GUI part, task 1).

The CLI is the single interface the Tauri (Rust) backend shells out to. Each
command prints a JSON result to stdout. `run_cli(argv)` returns that JSON string.

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_cli.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

import json

import pytest

from qdt.cli import run_cli
from qdt.memory import DomainMemoryStore


@pytest.fixture
def kb(tmp_path):
    DomainMemoryStore(tmp_path).create_domain("Quality", "q")
    return str(tmp_path)


def _run(kb, *args):
    return json.loads(run_cli([args[0], "--kb", kb, "--domain", "q", *args[1:]]))


def test_list_glossary_empty(kb):
    assert _run(kb, "list-glossary") == []


def test_add_term_then_list(kb):
    _run(kb, "add-term", "--source", "FMEA", "--target", "고장모드")
    assert _run(kb, "list-glossary") == [{"source": "FMEA", "target": "고장모드", "notes": ""}]


def test_delete_term(kb):
    _run(kb, "add-term", "--source", "FMEA", "--target", "고장모드")
    assert _run(kb, "delete-term", "--source", "FMEA") == {"deleted": True}
    assert _run(kb, "list-glossary") == []


def test_list_candidates(kb):
    store = DomainMemoryStore(kb)
    store.record_decision("q", "control", "관리", status="candidate", confidence="low", origin="machine")
    cands = _run(kb, "list-candidates")
    assert len(cands) == 1
    assert cands[0]["source"] == "control"
    assert cands[0]["status"] == "candidate"


def test_promote_moves_to_glossary(kb):
    store = DomainMemoryStore(kb)
    store.record_decision("q", "control", "관리", status="candidate", confidence="low", origin="machine")
    assert _run(kb, "promote", "--source", "control") == {"promoted": True}
    assert _run(kb, "list-glossary") == [{"source": "control", "target": "관리", "notes": ""}]
    assert _run(kb, "list-candidates") == []


def test_reject_clears_candidate(kb):
    store = DomainMemoryStore(kb)
    store.record_decision("q", "FMEA", "", status="candidate", confidence="low", origin="machine")
    assert _run(kb, "reject", "--source", "FMEA", "--reason", "keep acronym") == {"ok": True}
    assert _run(kb, "list-candidates") == []


def test_cli_export_glossary_writes_omegat_file(kb, tmp_path):
    store = DomainMemoryStore(kb)
    store.add_term("q", "FMEA", "고장모드 및 영향분석(FMEA)", notes="approved")
    out = tmp_path / "glossary.txt"

    result = _run(kb, "export-glossary", "--format", "omegat", "--out", str(out))

    assert result == {"exported": 1, "path": str(out), "format": "omegat"}
    assert out.read_text(encoding="utf-8") == "FMEA\t고장모드 및 영향분석(FMEA)\tapproved\n"


def test_cli_import_glossary_defaults_to_candidates(kb, tmp_path):
    source = tmp_path / "vendor.txt"
    source.write_text("Control Plan\t관리계획서(Control Plan)\tvendor\n", encoding="utf-8")

    result = _run(kb, "import-glossary", "--format", "omegat", "--input", str(source))

    assert result == {"imported": 1, "mode": "candidates", "format": "omegat"}
    store = DomainMemoryStore(kb)
    assert store.load_glossary("q") == []
    candidates = store.list_candidates("q")
    assert len(candidates) == 1
    assert candidates[0].source == "Control Plan"
