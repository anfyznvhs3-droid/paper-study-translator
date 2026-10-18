"""Tests for discovery orchestration with an INJECTED llm (task T2.4 integration core).

The real LLM call + eval are out of scope (fuzzy). Here the llm is a plain
callable (str -> str), so the orchestration is fully unit-testable.

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_discover_run.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

import pytest

from qdt.discover import agent_llm, format_discovery_prompt, run_discovery
from qdt.memory import DomainMemoryStore


def test_agent_llm_rejects_unknown_engine():
    # error path needs no qdt_agents import (hits else before lazy import)
    with pytest.raises(ValueError):
        agent_llm("bogus")


def test_format_discovery_prompt_includes_domain_and_texts():
    prompt = format_discovery_prompt(
        "medical",
        [{"source": "FMEA", "target": "고장모드"}],
        "The FMEA appears here",
        "여기 FMEA 가 있다",
    )
    assert "medical" in prompt
    assert "The FMEA appears here" in prompt
    assert "여기 FMEA 가 있다" in prompt


def test_run_discovery_records_candidates_from_injected_llm(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Quality", "q")

    def fake_llm(prompt: str) -> str:
        return '[{"source":"control","suggested_target":"대조군","reason":"medical sense","confidence":"high"}]'

    run_discovery(store, "q", "control group study", "관리 그룹 연구", fake_llm)

    cands = store.list_candidates("q")
    assert len(cands) == 1
    assert cands[0].source == "control"
    assert cands[0].target == "대조군"
    assert cands[0].status == "candidate"
    assert cands[0].confidence == "high"
    assert cands[0].origin == "agent"


def test_run_discovery_empty_response_records_nothing(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Quality", "q")

    run_discovery(store, "q", "x", "y", lambda prompt: "[]")

    assert store.list_candidates("q") == []
