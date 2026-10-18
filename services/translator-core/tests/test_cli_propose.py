"""Tests for the `propose-domain` CLI command (task T2.1b, testable core).

Loads every domain's glossary under the kb root as that domain's keyword set,
scores the document text, and returns the best-matching domain slug (or null).

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_cli_propose.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

import json

from qdt.cli import run_cli
from qdt.memory import DomainMemoryStore


def test_propose_domain_picks_matching_domain(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Quality", "quality-manufacturing")
    store.add_term("quality-manufacturing", "FMEA", "고장모드")
    store.add_term("quality-manufacturing", "Control Plan", "관리계획서")
    store.create_domain("Medical", "medical")
    store.add_term("medical", "patient", "환자")

    doc = tmp_path / "doc.txt"
    doc.write_text("The FMEA and Control Plan review", encoding="utf-8")

    out = run_cli(["propose-domain", "--kb", str(tmp_path), "--text-file", str(doc)])
    assert json.loads(out) == {"domain": "quality-manufacturing"}


def test_propose_domain_returns_null_when_no_match(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Quality", "quality-manufacturing")
    store.add_term("quality-manufacturing", "FMEA", "고장모드")

    doc = tmp_path / "doc.txt"
    doc.write_text("아무 신호 없는 한국어 텍스트", encoding="utf-8")

    out = run_cli(["propose-domain", "--kb", str(tmp_path), "--text-file", str(doc)])
    assert json.loads(out) == {"domain": None}
