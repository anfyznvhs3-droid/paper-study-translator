"""Batch runner primitives for QDT Agent mode."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

# Codex batches are independent network-bound calls, so run several at once.
# Each `complete()` uses its own temp files (reentrant-safe). Bounded to avoid
# hammering the Codex API; override with QDT_AGENT_BATCH_CONCURRENCY.
DEFAULT_AGENT_BATCH_CONCURRENCY = 4

# Per-batch character budget bounds. We target total/concurrency chars per batch
# (so balanced batches finish in ~one parallel wave), clamped to keep each Codex
# call comfortably under its per-call timeout (upper) and avoid cold-start-dominated
# tiny batches (lower). The upper bound was 10000 when the Codex per-call cap was
# 180s; the cap is now 300s (codex_cli), so a larger batch still finishes with
# margin — fewer/larger batches mean fewer parallel waves on big documents (the
# main bottleneck), without raising API concurrency. ~15000 chars ≈ 240s observed.
MAX_BATCH_CHARS = 15000
MIN_BATCH_CHARS = 2000


def _agent_batch_concurrency() -> int:
    raw = os.environ.get("QDT_AGENT_BATCH_CONCURRENCY", "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            return DEFAULT_AGENT_BATCH_CONCURRENCY
        if value > 0:
            return value
    return DEFAULT_AGENT_BATCH_CONCURRENCY


@dataclass(frozen=True)
class AgentTask:
    id: int
    source: str


@dataclass(frozen=True)
class AgentTranslation:
    id: int
    source: str
    translation: str


QUALITY_RULES = {
    "true": (
        "Prioritize literal faithfulness, modal force, technical nouns, "
        "abbreviations, and requirement strength."
    ),
    "realistic": "Balance practical Korean readability with domain accuracy and preserve compliance meaning.",
    "complete": "Produce polished, complete, natural Korean while preserving technical meaning and constraints.",
}


class AgentResponseFormatError(ValueError):
    """Raised when an agent CLI response cannot be converted to translations."""


def load_agent_tasks(path: str | Path) -> list[AgentTask]:
    tasks: list[AgentTask] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        task_id = row.get("id")
        source = row.get("source")
        if not isinstance(task_id, int) or not isinstance(source, str):
            raise ValueError(f"Invalid task row at line {line_number}: expected integer id and string source")
        tasks.append(AgentTask(id=task_id, source=source))
    return tasks


def split_batches(
    tasks: list[AgentTask],
    max_items: int,
    max_chars: int | None = None,
) -> list[list[AgentTask]]:
    if max_items < 1:
        raise ValueError("max_items must be >= 1")
    if max_chars is not None and max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if max_chars is None:
        return [tasks[index : index + max_items] for index in range(0, len(tasks), max_items)]

    # Char-aware contiguous split: keep tasks in original order (preserves
    # within-batch context for the translator) but start a new batch once the
    # current one would exceed the item OR character budget. Capping by chars
    # balances batch *work* — without it a fixed item count makes dense pages a
    # single slow batch while sparse pages run tiny ones.
    batches: list[list[AgentTask]] = []
    current: list[AgentTask] = []
    current_chars = 0
    for task in tasks:
        task_chars = len(task.source)
        over_items = len(current) >= max_items
        over_chars = bool(current) and current_chars + task_chars > max_chars
        if current and (over_items or over_chars):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(task)
        current_chars += task_chars
    if current:
        batches.append(current)
    return batches


def build_batch_prompt(
    tasks: list[AgentTask],
    engine: str,
    quality: str,
    review_mode: str,
    output_mode: str,
    domain: str,
    glossary: dict[str, str],
) -> str:
    quality_rule = QUALITY_RULES.get(quality, QUALITY_RULES["realistic"])
    glossary_lines = "\n".join(f"- {source} -> {target}" for source, target in sorted(glossary.items()))
    task_json = json.dumps(
        [{"id": task.id, "source": task.source} for task in tasks],
        ensure_ascii=False,
        indent=2,
    )
    return f"""Translate the JSON array under INPUT now. Do not ask for source text; the source text is already included in INPUT. Return only one JSON object containing the translated result array.

Context:
- Engine: {engine}
- Domain: {domain}
- Translation style: {quality}
- Style rule: {quality_rule}
- review mode: {review_mode}
- output mode: {output_mode}
- Target language: Korean
- Document family: quality, manufacturing, automotive QMS, IATF 16949, FMEA, APQP, control-plan, warranty, audit, and supplier-quality documents

Required glossary, highest priority:
{glossary_lines if glossary_lines else "- No user-approved glossary terms."}

Output only valid JSON. Return one object with this shape:
{{"translations":[{{"id":1,"source":"exact source","translation":"Korean translation"}}]}}
The translations array must contain exactly one object per input item.
Critical output contract:
- The first non-whitespace character of your final answer must be {{
- The last non-whitespace character of your final answer must be }}
- Do not use Markdown fences.
- Do not include explanations, notes, apologies, headings, or prose.
- If an item is already Korean or cannot be improved, copy it into translation.
Each translations item must contain:
- id: same integer id as input
- source: exact source string from input
- translation: Korean translation only

INPUT:
{task_json}
"""


def parse_batch_response(raw: str) -> list[AgentTranslation]:
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end < start:
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise AgentResponseFormatError(
                    f"Agent response contained invalid JSON object: {exc}"
                ) from exc
            for key in ("translations", "items", "results"):
                rows = obj.get(key)
                if isinstance(rows, list):
                    return parse_batch_response(json.dumps(rows, ensure_ascii=False))
        raise AgentResponseFormatError("Agent response did not contain a JSON array")
    try:
        rows = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AgentResponseFormatError(f"Agent response contained invalid JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise AgentResponseFormatError("Agent response JSON must be an array")

    translations: list[AgentTranslation] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise AgentResponseFormatError(f"Agent response row {index} must be an object")
        task_id = row.get("id")
        source = row.get("source")
        translation = row.get("translation")
        if not isinstance(task_id, int) or not isinstance(source, str) or not isinstance(translation, str):
            raise AgentResponseFormatError(
                f"Agent response row {index} requires integer id, string source, and string translation"
            )
        translations.append(AgentTranslation(id=task_id, source=source, translation=translation))
    return translations


def write_offline_translation_map(path: str | Path, translations: list[AgentTranslation]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for item in translations:
            file.write(
                json.dumps({"source": item.source, "translation": item.translation}, ensure_ascii=False)
                + "\n"
            )


def _batch_debug_index(path: Path) -> int | None:
    try:
        return int(path.name.split(".", 1)[0].split("-")[-1])
    except ValueError:
        return None


def _load_debug_translations(debug_path: Path, expected_by_id: dict[int, str]) -> tuple[dict[int, AgentTranslation], int]:
    translations: dict[int, AgentTranslation] = {}
    batch_indices = [
        index
        for path in debug_path.glob("batch-*.txt")
        for index in [_batch_debug_index(path)]
        if index is not None
    ]
    next_batch_index = max(batch_indices, default=0) + 1

    for response_path in sorted(debug_path.glob("batch-*.response.txt")):
        try:
            batch_translations = parse_batch_response(response_path.read_text(encoding="utf-8"))
        except (OSError, AgentResponseFormatError):
            continue
        for translation in batch_translations:
            expected_source = expected_by_id.get(translation.id)
            if expected_source is None:
                continue
            # Re-key cached responses to the authoritative source too, so a
            # source that drifted from the agent echo is still reused, not
            # re-translated.
            translations[translation.id] = replace(translation, source=expected_source)
    return translations, next_batch_index


def run_agent_batches(
    tasks: list[AgentTask],
    complete: Callable[[str], str],
    engine: str,
    quality: str,
    review_mode: str,
    output_mode: str,
    domain: str,
    glossary: dict[str, str],
    max_batch_items: int,
    debug_dir: str | Path | None = None,
) -> list[AgentTranslation]:
    translations: list[AgentTranslation] = []
    expected_by_id = {task.id: task.source for task in tasks}
    debug_path = Path(debug_dir) if debug_dir else None
    if debug_path:
        debug_path.mkdir(parents=True, exist_ok=True)
        by_id, next_batch_index = _load_debug_translations(debug_path, expected_by_id)
        translations.extend(by_id.values())
    else:
        by_id = {}
        next_batch_index = 1

    pending_tasks = [task for task in tasks if task.id not in by_id]

    def process_batch(batch_index: int, batch: list[AgentTask]) -> list[AgentTranslation]:
        prompt = build_batch_prompt(
            tasks=batch,
            engine=engine,
            quality=quality,
            review_mode=review_mode,
            output_mode=output_mode,
            domain=domain,
            glossary=glossary,
        )
        prompt_path = debug_path / f"batch-{batch_index:04d}.prompt.txt" if debug_path else None
        response_path = debug_path / f"batch-{batch_index:04d}.response.txt" if debug_path else None
        if prompt_path:
            prompt_path.write_text(prompt, encoding="utf-8")

        raw_response = complete(prompt)
        if response_path:
            response_path.write_text(raw_response, encoding="utf-8")

        try:
            batch_translations = parse_batch_response(raw_response)
        except AgentResponseFormatError as exc:
            if response_path:
                raise AgentResponseFormatError(
                    f"Codex 응답이 JSON 배열 형식이 아닙니다. 응답 원문: {response_path}"
                ) from exc
            raise
        normalized_batch: list[AgentTranslation] = []
        for translation in batch_translations:
            expected_source = expected_by_id.get(translation.id)
            if expected_source is None:
                raise ValueError(f"Agent returned unknown task id: {translation.id}")
            if translation.source != expected_source:
                # LLMs do not always echo the source byte-for-byte (whitespace,
                # quotes, minor normalization). The original task source is
                # authoritative and is what the offline render looks up, so
                # re-key the translation to it instead of failing the whole run.
                translation = replace(translation, source=expected_source)
            normalized_batch.append(translation)
        return normalized_batch

    concurrency = _agent_batch_concurrency()
    total_chars = sum(len(task.source) for task in pending_tasks)
    # Aim for ~`concurrency` balanced batches so they finish in one parallel
    # wave, clamped to a safe per-call size.
    target_chars = (total_chars + concurrency - 1) // concurrency if concurrency > 0 else total_chars
    per_batch_chars = max(MIN_BATCH_CHARS, min(MAX_BATCH_CHARS, target_chars or MIN_BATCH_CHARS))
    batches = list(
        enumerate(
            split_batches(pending_tasks, max_items=max_batch_items, max_chars=per_batch_chars),
            start=next_batch_index,
        )
    )
    if batches:
        workers = max(1, min(len(batches), concurrency))
        if workers == 1:
            ordered = [(index, process_batch(index, batch)) for index, batch in batches]
        else:
            # complete() is reentrant (per-call temp files), so batches run
            # concurrently. Reading result() in submission order preserves the
            # original deterministic by_id override order and re-raises the first
            # batch error exactly like the sequential path did.
            with ThreadPoolExecutor(max_workers=workers) as executor:
                submitted = [
                    (index, executor.submit(process_batch, index, batch))
                    for index, batch in batches
                ]
                ordered = [(index, future.result()) for index, future in submitted]
        for _index, normalized_batch in ordered:
            translations.extend(normalized_batch)
            by_id.update({item.id: item for item in normalized_batch})

    missing = [task.id for task in tasks if task.id not in by_id]
    if missing:
        raise ValueError(f"Agent response missing task ids: {missing}")
    return [by_id[task.id] for task in tasks]


def run_agent_job_from_tasks(
    task_output_path: str | Path,
    translation_map_path: str | Path,
    complete: Callable[[str], str],
    engine: str,
    quality: str,
    review_mode: str,
    output_mode: str,
    domain: str,
    glossary: dict[str, str],
    max_batch_items: int,
) -> dict:
    tasks = load_agent_tasks(task_output_path)
    debug_dir = Path(translation_map_path).parent / "agent-batches"
    translations = run_agent_batches(
        tasks=tasks,
        complete=complete,
        engine=engine,
        quality=quality,
        review_mode=review_mode,
        output_mode=output_mode,
        domain=domain,
        glossary=glossary,
        max_batch_items=max_batch_items,
        debug_dir=debug_dir,
    )
    write_offline_translation_map(translation_map_path, translations)
    glossary_report = _write_glossary_report(translation_map_path, translations)
    return {
        "ok": True,
        "task_count": len(tasks),
        "batch_count": len(split_batches(tasks, max_items=max_batch_items)),
        "translation_map": str(Path(translation_map_path)),
        **glossary_report,
    }


def _write_glossary_report(
    translation_map_path: str | Path, translations: list[AgentTranslation]
) -> dict:
    """Mine reusable glossary candidates + term-consistency conflicts and write a
    sidecar report. Report-only: this never alters the translation and must never
    fail the run, so any error is swallowed and reported as a soft field.
    """
    try:
        from dataclasses import asdict

        from qdt.glossary_candidates import build_report

        rows = [{"source": t.source, "translation": t.translation} for t in translations]
        report = build_report(rows)
        path = Path(translation_map_path).parent / "glossary-candidates.json"
        path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "glossary_candidates": str(path),
            "glossary_candidate_count": len(report.candidates),
            "term_drift_count": len(report.term_drift),
            "cell_conflict_count": len(report.conflicts),
        }
    except Exception as exc:  # noqa: BLE001 - report-only, never break the run
        return {"glossary_report_error": str(exc)}


def load_glossary_csv(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}

    glossary: dict[str, str] = {}
    for raw_path in str(path).split(os.pathsep):
        if not raw_path.strip():
            continue
        csv_path = Path(raw_path)
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                source = (row.get("source") or "").strip()
                target = (row.get("target") or "").strip()
                if source and target:
                    glossary[source] = target
    return glossary


def complete_for_engine(engine: str) -> Callable[[str], str]:
    if engine == "codex-agent":
        from qdt_agents.codex_cli import TRANSLATION_RESPONSE_SCHEMA, CodexCliEngine

        codex = CodexCliEngine()
        return lambda prompt: codex.complete(prompt, output_schema=TRANSLATION_RESPONSE_SCHEMA)
    if engine == "claude-code-agent":
        from qdt_agents.claude_code_cli import ClaudeCodeCliEngine

        return ClaudeCodeCliEngine().complete
    raise ValueError(f"Unsupported agent engine: {engine}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run QDT Agent CLI batch translation from offline tasks.")
    parser.add_argument("--task-output", required=True)
    parser.add_argument("--translation-map", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--quality", default="realistic")
    parser.add_argument("--review-mode", default="off")
    parser.add_argument("--output-mode", default="mono")
    parser.add_argument("--domain", default="quality-manufacturing")
    parser.add_argument("--glossary")
    parser.add_argument("--max-batch-items", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = run_agent_job_from_tasks(
            task_output_path=args.task_output,
            translation_map_path=args.translation_map,
            complete=complete_for_engine(args.engine),
            engine=args.engine,
            quality=args.quality,
            review_mode=args.review_mode,
            output_mode=args.output_mode,
            domain=args.domain,
            glossary=load_glossary_csv(args.glossary),
            max_batch_items=args.max_batch_items,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
