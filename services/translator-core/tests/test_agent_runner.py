"""Tests for the Agent CLI batch runner.

Run from services/translator-core:
    PYTHONPATH=src python -m pytest tests/test_agent_runner.py -q
"""

from pathlib import Path
import os

from qdt.agent_runner import (
    AgentResponseFormatError,
    AgentTask,
    AgentTranslation,
    build_batch_prompt,
    load_agent_tasks,
    load_glossary_csv,
    parse_batch_response,
    run_agent_batches,
    run_agent_job_from_tasks,
    split_batches,
    write_offline_translation_map,
)


def test_load_agent_tasks_reads_offline_task_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "tasks.jsonl"
    path.write_text(
        '{"id": 1, "source": "Failure mode"}\n'
        '{"id": 2, "source": "Control Plan"}\n',
        encoding="utf-8",
    )

    assert load_agent_tasks(path) == [
        AgentTask(id=1, source="Failure mode"),
        AgentTask(id=2, source="Control Plan"),
    ]


def test_split_batches_preserves_order_and_size() -> None:
    tasks = [AgentTask(id=i, source=f"source {i}") for i in range(1, 6)]

    batches = split_batches(tasks, max_items=2)

    assert batches == [
        [AgentTask(id=1, source="source 1"), AgentTask(id=2, source="source 2")],
        [AgentTask(id=3, source="source 3"), AgentTask(id=4, source="source 4")],
        [AgentTask(id=5, source="source 5")],
    ]


def test_build_batch_prompt_includes_quality_review_domain_and_json_contract() -> None:
    prompt = build_batch_prompt(
        tasks=[AgentTask(id=1, source="shall retain Control Plan")],
        engine="codex-agent",
        quality="true",
        review_mode="on",
        output_mode="dual",
        domain="quality-manufacturing",
        glossary={"Control Plan": "Control Plan KO"},
    )

    assert "Output only valid JSON" in prompt
    assert '"id": 1' in prompt
    assert "literal faithfulness" in prompt
    assert "review mode: on" in prompt
    assert "quality-manufacturing" in prompt
    assert "Control Plan -> Control Plan KO" in prompt


def test_load_glossary_csv_merges_profile_and_domain_path_list(tmp_path: Path) -> None:
    profile = tmp_path / "scholarly.csv"
    domain = tmp_path / "domain.csv"
    profile.write_text("source,target,notes\nAbstract,초록,exact-heading\nFMEA,프로필 FMEA,\n", encoding="utf-8")
    domain.write_text("source,target,notes\nFMEA,고장모드 및 영향분석(FMEA),\n", encoding="utf-8")

    glossary = load_glossary_csv(os.pathsep.join([str(profile), str(domain)]))

    assert glossary == {
        "Abstract": "초록",
        "FMEA": "고장모드 및 영향분석(FMEA)",
    }


def test_parse_batch_response_accepts_json_array() -> None:
    raw = """
    [
      {"id": 1, "source": "Failure mode", "translation": "Failure mode KO"},
      {"id": 2, "source": "Control Plan", "translation": "Control Plan KO"}
    ]
    """

    assert parse_batch_response(raw) == [
        AgentTranslation(id=1, source="Failure mode", translation="Failure mode KO"),
        AgentTranslation(id=2, source="Control Plan", translation="Control Plan KO"),
    ]


def test_parse_batch_response_rejects_missing_translation() -> None:
    raw = '[{"id": 1, "source": "Failure mode"}]'

    try:
        parse_batch_response(raw)
    except AgentResponseFormatError as exc:
        assert "translation" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_batch_response_accepts_wrapped_translations_object() -> None:
    raw = '{"translations": [{"id": 1, "source": "Failure mode", "translation": "Failure mode KO"}]}'

    assert parse_batch_response(raw) == [
        AgentTranslation(id=1, source="Failure mode", translation="Failure mode KO"),
    ]


def test_write_offline_translation_map_uses_scholar_contract(tmp_path: Path) -> None:
    path = tmp_path / "map.jsonl"
    translations = [
        AgentTranslation(id=1, source="Failure mode", translation="Failure mode KO"),
        AgentTranslation(id=2, source="Control Plan", translation="Control Plan KO"),
    ]

    write_offline_translation_map(path, translations)

    assert path.read_text(encoding="utf-8").splitlines() == [
        '{"source": "Failure mode", "translation": "Failure mode KO"}',
        '{"source": "Control Plan", "translation": "Control Plan KO"}',
    ]


def test_run_agent_batches_calls_engine_once_per_batch() -> None:
    prompts: list[str] = []

    def fake_complete(prompt: str) -> str:
        prompts.append(prompt)
        if '"id": 1' in prompt:
            return '[{"id": 1, "source": "A", "translation": "A KO"}]'
        return '[{"id": 2, "source": "B", "translation": "B KO"}]'

    result = run_agent_batches(
        tasks=[AgentTask(id=1, source="A"), AgentTask(id=2, source="B")],
        complete=fake_complete,
        engine="codex-agent",
        quality="realistic",
        review_mode="off",
        output_mode="mono",
        domain="quality-manufacturing",
        glossary={},
        max_batch_items=1,
    )

    assert len(prompts) == 2
    assert result == [
        AgentTranslation(id=1, source="A", translation="A KO"),
        AgentTranslation(id=2, source="B", translation="B KO"),
    ]


def test_run_agent_batches_runs_batches_concurrently_and_preserves_order() -> None:
    import re
    import threading
    import time

    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_complete(prompt: str) -> str:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.15)
        with lock:
            active -= 1
        ids = re.findall(r'"id": (\d+)', prompt)
        items = ",".join(
            f'{{"id": {i}, "source": "s{i}", "translation": "t{i}"}}' for i in ids
        )
        return f"[{items}]"

    tasks = [AgentTask(id=i, source=f"s{i}") for i in range(1, 7)]
    result = run_agent_batches(
        tasks=tasks,
        complete=fake_complete,
        engine="codex-agent",
        quality="realistic",
        review_mode="off",
        output_mode="mono",
        domain="quality-manufacturing",
        glossary={},
        max_batch_items=1,  # 6 single-task batches
    )

    assert peak >= 2, f"batches should overlap, observed peak concurrency={peak}"
    assert [t.id for t in result] == list(range(1, 7)), "result order must be preserved"


def test_split_batches_char_cap_balances_and_preserves_order() -> None:
    tasks = [AgentTask(id=i, source="x" * 600) for i in range(1, 7)]  # 6 × 600

    batches = split_batches(tasks, max_items=32, max_chars=1500)

    # each batch within the char budget (2 × 600 = 1200 <= 1500; a 3rd would be 1800)
    assert all(sum(len(t.source) for t in b) <= 1500 for b in batches)
    assert max(len(b) for b in batches) == 2
    # contiguity preserved (no reordering across batches)
    assert [t.id for b in batches for t in b] == list(range(1, 7))
    # no char cap -> single item-capped batch
    assert len(split_batches(tasks, max_items=32)) == 1
    # an oversized single task is never dropped, it goes in its own batch
    big = [AgentTask(id=1, source="y" * 5000)]
    assert split_batches(big, max_items=32, max_chars=1500) == [big]


def test_run_agent_batches_rekeys_drifted_source_instead_of_failing() -> None:
    # The agent echoes a source that drifted from the task (extra space here),
    # which previously aborted the whole run ("Agent changed source"). It must
    # re-key the translation to the authoritative task source so the offline
    # render still finds it.
    def fake_complete(prompt: str) -> str:
        return '[{"id": 1, "source": "Failure  mode", "translation": "고장 모드"}]'

    result = run_agent_batches(
        tasks=[AgentTask(id=1, source="Failure mode")],
        complete=fake_complete,
        engine="codex-agent",
        quality="realistic",
        review_mode="off",
        output_mode="mono",
        domain="quality-manufacturing",
        glossary={},
        max_batch_items=1,
    )

    assert result == [AgentTranslation(id=1, source="Failure mode", translation="고장 모드")]


def test_run_agent_batches_reuses_existing_debug_responses(tmp_path: Path) -> None:
    (tmp_path / "batch-0001.response.txt").write_text(
        '[{"id": 1, "source": "A", "translation": "A KO"}]',
        encoding="utf-8",
    )
    prompts: list[str] = []

    def fake_complete(prompt: str) -> str:
        prompts.append(prompt)
        return '[{"id": 2, "source": "B", "translation": "B KO"}]'

    result = run_agent_batches(
        tasks=[AgentTask(id=1, source="A"), AgentTask(id=2, source="B")],
        complete=fake_complete,
        engine="codex-agent",
        quality="realistic",
        review_mode="off",
        output_mode="mono",
        domain="quality-manufacturing",
        glossary={},
        max_batch_items=1,
        debug_dir=tmp_path,
    )

    assert len(prompts) == 1
    assert '"id": 2' in prompts[0]
    assert (tmp_path / "batch-0002.prompt.txt").exists()
    assert result == [
        AgentTranslation(id=1, source="A", translation="A KO"),
        AgentTranslation(id=2, source="B", translation="B KO"),
    ]


def test_run_agent_batches_writes_debug_prompt_and_response_on_format_error(tmp_path: Path) -> None:
    try:
        run_agent_batches(
            tasks=[AgentTask(id=1, source="A")],
            complete=lambda prompt: "I translated it, but not as JSON.",
            engine="codex-agent",
            quality="realistic",
            review_mode="off",
            output_mode="mono",
            domain="quality-manufacturing",
            glossary={},
            max_batch_items=1,
            debug_dir=tmp_path,
        )
    except AgentResponseFormatError as exc:
        assert "Codex 응답이 JSON 배열 형식이 아닙니다" in str(exc)
        assert (tmp_path / "batch-0001.prompt.txt").exists()
        assert (tmp_path / "batch-0001.response.txt").read_text(encoding="utf-8") == (
            "I translated it, but not as JSON."
        )
    else:
        raise AssertionError("expected AgentResponseFormatError")


def test_run_agent_job_from_existing_tasks_writes_map_and_summary(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.jsonl"
    output_map = tmp_path / "map.jsonl"
    tasks.write_text(
        '{"id": 1, "source": "Failure mode"}\n'
        '{"id": 2, "source": "Control Plan"}\n',
        encoding="utf-8",
    )

    result = run_agent_job_from_tasks(
        task_output_path=tasks,
        translation_map_path=output_map,
        complete=lambda prompt: (
            "["
            '{"id": 1, "source": "Failure mode", "translation": "Failure mode KO"},'
            '{"id": 2, "source": "Control Plan", "translation": "Control Plan KO"}'
            "]"
        ),
        engine="codex-agent",
        quality="true",
        review_mode="on",
        output_mode="dual",
        domain="quality-manufacturing",
        glossary={"Control Plan": "Control Plan KO"},
        max_batch_items=10,
    )

    assert result["ok"] is True
    assert result["task_count"] == 2
    assert result["batch_count"] == 1
    assert output_map.exists()
