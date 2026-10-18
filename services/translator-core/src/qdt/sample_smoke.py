from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from qdt.sample_acceptance import build_acceptance_report

SUPPORTED_MODES = {"google", "agent"}
SUPPORTED_LIVE_RUNNERS = {"contract", "google"}
LiveRunner = Callable[[dict[str, Any], Path, Path], dict[str, Any]]
CommandRunner = Callable[[list[str], Path, dict[str, str], int], subprocess.CompletedProcess[str]]


def build_smoke_report(
    sample_root: str | Path,
    modes: list[str] | None = None,
    output_mode: str = "mono",
    live: bool = False,
    limit: int | None = None,
    output_dir: str | Path | None = None,
    live_runner: LiveRunner | None = None,
    live_runner_name: str = "contract",
) -> dict[str, Any]:
    selected_modes = _normalize_modes(modes or ["google", "agent"])
    live_runner_name = _normalize_live_runner(live_runner_name)
    _validate_live_guard(live=live, modes=selected_modes, limit=limit)
    sample_root_path = Path(sample_root)
    output_dir_path = Path(output_dir) if output_dir else sample_root_path / "QDT_Output" / "smoke"
    acceptance = build_acceptance_report(sample_root)
    rows = [
        plan_smoke_row(sample, mode=mode, output_mode=output_mode, live=live)
        for sample in acceptance["samples"]
        for mode in selected_modes
    ]
    if live:
        _apply_live_smoke(
            rows,
            sample_root=sample_root_path,
            output_dir=output_dir_path,
            limit=limit or 0,
            live_runner=live_runner or _make_live_runner(live_runner_name),
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_root": str(sample_root),
        "live": live,
        "live_runner": live_runner_name,
        "limit": limit,
        "output_mode": output_mode,
        "modes": selected_modes,
        "acceptance_watch_items": acceptance.get("watch_items", []),
        "summary": _summarize_rows(rows),
        "rows": rows,
    }


def plan_smoke_row(
    sample: dict[str, Any],
    mode: str,
    output_mode: str = "mono",
    live: bool = False,
) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported smoke mode: {mode}")
    route, status, reasons = _route_status_reasons(sample, mode)
    return {
        "sample": sample["relative_path"],
        "kind": sample["kind"],
        "profile": sample["profile"],
        "mode": mode,
        "output_mode": output_mode,
        "route": route,
        "status": status,
        "reasons": reasons,
        "expected_suffix": _expected_suffix(sample),
        "live_requested": live,
    }


def write_reports(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "smoke-report.json"
    markdown_path = output / "smoke-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    return {"json_report": str(json_path), "markdown_report": str(markdown_path)}


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Sample Smoke Report",
        "",
        f"- Sample root: `{report['sample_root']}`",
        f"- Live: {str(report['live']).lower()}",
        f"- Live runner: `{report['live_runner']}`",
        f"- Output mode: `{report['output_mode']}`",
        f"- Modes: {', '.join(report['modes'])}",
        f"- Rows: {summary['row_count']}",
        f"- Ready: {summary['ready']}",
        f"- Needs review: {summary['needs_review']}",
        f"- Skipped: {summary['skipped']}",
    ]
    if report["live"]:
        lines.extend(
            [
                f"- Live executed: {summary['live_executed']}",
                f"- Live passed: {summary['live_passed']}",
                f"- Live failed: {summary['live_failed']}",
                f"- Live skipped: {summary['live_skipped']}",
            ]
        )
    lines.extend(["", "## Acceptance Watch Items", ""])
    watch_items = report.get("acceptance_watch_items", [])
    lines.extend(f"- `{item}`" for item in watch_items) if watch_items else lines.append("- none")
    lines.extend(["", "## Rows", ""])
    lines.append("| Sample | Mode | Route | Status | Live | Expected | Reasons |")
    lines.append("|---|---:|---|---|---|---:|---|")
    for row in report["rows"]:
        reasons = ", ".join(row["reasons"]) or "-"
        lines.append(
            "| {sample} | {mode} | {route} | {status} | {live} | {suffix} | {reasons} |".format(
                sample=row["sample"].replace("|", "\\|"),
                mode=row["mode"],
                route=row["route"],
                status=row["status"],
                live=row.get("live_status", "-"),
                suffix=row["expected_suffix"] or "-",
                reasons=reasons,
            )
        )
    return "\n".join(lines) + "\n"


def run_cli(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Build a QDT sample smoke report.")
    parser.add_argument("--sample-root", default="SAMPLE")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--mode", choices=["google", "agent", "both"], default="both")
    parser.add_argument("--output-mode", choices=["mono", "dual"], default="mono")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--runner", choices=["contract", "google"], default="contract")
    args = parser.parse_args(argv)

    modes = ["google", "agent"] if args.mode == "both" else [args.mode]
    sample_root = Path(args.sample_root)
    output_dir = Path(args.output_dir) if args.output_dir else sample_root / "QDT_Output" / "smoke"
    report = build_smoke_report(
        sample_root,
        modes=modes,
        output_mode=args.output_mode,
        live=args.live,
        limit=args.limit,
        output_dir=output_dir,
        live_runner_name=args.runner,
    )
    written = write_reports(report, output_dir)
    return {"ok": True, **written, "summary": report["summary"], "acceptance_watch_items": report["acceptance_watch_items"]}


def main() -> None:
    print(json.dumps(run_cli(), ensure_ascii=False, indent=2))


def _route_status_reasons(sample: dict[str, Any], mode: str) -> tuple[str, str, list[str]]:
    profile = sample["profile"]
    flags = set(sample.get("risk_flags", []))
    if profile == "english-text-pdf":
        return ("pdf-scholar" if mode == "google" else "pdf-agent", "ready", [])
    if profile == "mixed-language-pdf":
        return (
            "pdf-mixed-renderer" if mode == "google" else "pdf-agent",
            "needs-review",
            _reasons_from_flags(flags, fallback=["mixed-language"]),
        )
    if profile == "slide-pdf-image-heavy":
        return (
            "pdf-scholar" if mode == "google" else "pdf-agent",
            "needs-review",
            _reasons_from_flags(flags, fallback=["image-heavy"]),
        )
    if profile == "pptx-native":
        return ("pptx-native", "ready", [])
    if profile == "reference-artifact":
        return ("unsupported", "skipped", ["reference-artifact"])
    if profile == "unsupported-legacy-ppt":
        return ("unsupported", "skipped", ["legacy-ppt-unsupported"])
    if sample["kind"] == "pdf":
        reasons = _reasons_from_flags(flags, fallback=[])
        status = "needs-review" if reasons else "ready"
        return ("pdf-scholar" if mode == "google" else "pdf-agent", status, reasons)
    return ("unsupported", "skipped", [f"unsupported-{sample['kind']}"])


def _reasons_from_flags(flags: set[str], fallback: list[str]) -> list[str]:
    reasons = []
    for reason in ["mixed-language", "image-heavy", "sparse-text-layer", "empty-text-pages", "english-only-source"]:
        if reason in flags:
            reasons.append(reason)
    for reason in fallback:
        if reason not in reasons:
            reasons.append(reason)
    return reasons


def _expected_suffix(sample: dict[str, Any]) -> str | None:
    if sample["kind"] == "pdf":
        return ".pdf"
    if sample["kind"] == "pptx":
        return ".pptx"
    return None


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "row_count": len(rows),
        "ready": _count_status(rows, "ready"),
        "needs_review": _count_status(rows, "needs-review"),
        "skipped": _count_status(rows, "skipped"),
        "google": _count_mode(rows, "google"),
        "agent": _count_mode(rows, "agent"),
        "live_executed": _count_live(rows, "passed") + _count_live(rows, "failed"),
        "live_passed": _count_live(rows, "passed"),
        "live_failed": _count_live(rows, "failed"),
        "live_skipped": _count_live(rows, "skipped"),
    }


def _count_status(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row["status"] == status)


def _count_mode(rows: list[dict[str, Any]], mode: str) -> int:
    return sum(1 for row in rows if row["mode"] == mode)


def _count_live(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if row.get("live_status") == status)


def _normalize_modes(modes: list[str]) -> list[str]:
    normalized = []
    for mode in modes:
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"unsupported smoke mode: {mode}")
        if mode not in normalized:
            normalized.append(mode)
    return normalized


def _normalize_live_runner(runner: str) -> str:
    normalized = runner.strip().lower()
    if normalized not in SUPPORTED_LIVE_RUNNERS:
        raise ValueError(f"unsupported live runner: {runner}")
    return normalized


def _validate_live_guard(*, live: bool, modes: list[str], limit: int | None) -> None:
    if not live:
        return
    if len(modes) != 1:
        raise ValueError("live smoke requires one explicit mode")
    if modes[0] == "agent":
        raise ValueError("agent live smoke is not enabled yet")
    if limit is None or limit <= 0:
        raise ValueError("live smoke requires a positive --limit")


def _make_live_runner(runner: str) -> LiveRunner:
    if runner == "google":
        return make_google_scholar_runner()
    return _write_live_contract


def _apply_live_smoke(
    rows: list[dict[str, Any]],
    *,
    sample_root: Path,
    output_dir: Path,
    limit: int,
    live_runner: LiveRunner,
) -> None:
    executed = 0
    for row in rows:
        if row["status"] != "ready":
            _mark_live_skipped(row, "not-ready")
            continue
        if row["mode"] != "google":
            _mark_live_skipped(row, "unsupported-live-mode")
            continue
        if executed >= limit:
            _mark_live_skipped(row, "limit-reached")
            continue

        executed += 1
        started = time.monotonic()
        try:
            result = live_runner(row, sample_root, output_dir)
        except Exception as exc:  # pragma: no cover - defensive failure capture
            row.update(
                {
                    "live_status": "failed",
                    "live_runner": "exception",
                    "live_exit_code": 1,
                    "live_elapsed_seconds": round(time.monotonic() - started, 3),
                    "live_output_files": [],
                    "live_error": str(exc),
                }
            )
            continue

        live_status = result.get("live_status", "passed")
        row.update(
            {
                "live_status": live_status,
                "live_runner": result.get("live_runner", "custom"),
                "live_exit_code": result.get("live_exit_code", 0 if live_status == "passed" else 1),
                "live_elapsed_seconds": result.get("live_elapsed_seconds", round(time.monotonic() - started, 3)),
                "live_output_files": result.get("live_output_files", []),
            }
        )
        if "live_error" in result:
            row["live_error"] = result["live_error"]


def _mark_live_skipped(row: dict[str, Any], reason: str) -> None:
    row["live_status"] = "skipped"
    row["live_reasons"] = [reason]
    row["live_output_files"] = []


def make_google_scholar_runner(
    *,
    python_exe: str | None = None,
    translator_home: str | Path | None = None,
    glossary_path: str | Path | None = None,
    command_runner: CommandRunner | None = None,
    timeout_seconds: int = 300,
) -> LiveRunner:
    repo_root = _repo_root()
    python = python_exe or os.environ.get("SCHOLAR_TRANSLATOR_PYTHON") or sys.executable
    home = Path(translator_home) if translator_home else _default_scholar_translator_home(repo_root)
    glossary = str(glossary_path) if glossary_path else _default_glossary_path(repo_root)
    runner = command_runner or _run_subprocess

    def run(row: dict[str, Any], sample_root: Path, output_dir: Path) -> dict[str, Any]:
        started = time.monotonic()
        source = sample_root / row["sample"]
        if not source.is_file():
            return _failed_live_result(
                runner="google-scholar",
                started=started,
                error=f"missing sample source: {source}",
            )
        if row["route"] != "pdf-scholar":
            return _failed_live_result(
                runner="google-scholar",
                started=started,
                error=f"google live runner only supports pdf-scholar rows, got {row['route']}",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        active_glossary = glossary if _glossary_spec_has_files(glossary) else None
        args = _google_scholar_args(
            python,
            home,
            source,
            output_dir,
            active_glossary,
        )
        env = _google_scholar_env(home, active_glossary)
        try:
            completed = runner(args, home, env, timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return _failed_live_result(
                runner="google-scholar",
                started=started,
                exit_code=124,
                error=f"google scholar runner timed out after {timeout_seconds}s: {exc}",
            )

        output_files = _filter_output_mode_files(
            _collect_live_output_files(output_dir, completed.stdout, completed.stderr),
            row["output_mode"],
        )
        status = "passed" if completed.returncode == 0 and output_files else "failed"
        result = {
            "live_status": status,
            "live_runner": "google-scholar",
            "live_exit_code": completed.returncode,
            "live_elapsed_seconds": round(time.monotonic() - started, 3),
            "live_output_files": output_files,
        }
        if status != "passed":
            result["live_error"] = _summarize_runner_error(completed, output_files)
        return result

    return run


def _google_scholar_args(
    python_exe: str,
    translator_home: Path,
    source: Path,
    output_dir: Path,
    glossary_path: str | None,
) -> list[str]:
    entrypoint = [str(translator_home / "qdt_scholar_with_glossary.py")] if glossary_path else [
        "-m",
        "scholar_translator.cli",
    ]
    return [
        python_exe,
        *entrypoint,
        str(source),
        "--lang-out",
        "ko",
        "--service",
        "google",
        "--output",
        str(output_dir),
        "--thread",
        "4",
    ]


def _google_scholar_env(translator_home: Path, glossary_path: str | None) -> dict[str, str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [str(translator_home)]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    if glossary_path:
        env["QDT_GLOSSARY"] = glossary_path
    else:
        env.pop("QDT_GLOSSARY", None)
    return env


def _run_subprocess(
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _collect_live_output_files(output_dir: Path, stdout: str, stderr: str) -> list[str]:
    candidates: list[Path] = []
    for text in (stdout, stderr):
        for token in _candidate_paths_from_text(text):
            path = Path(token)
            if path.is_file() and path.suffix.lower() in {".pdf", ".pptx"}:
                candidates.append(path)
    if output_dir.is_dir():
        for path in output_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".pdf", ".pptx"}:
                candidates.append(path)
    deduped = []
    seen = set()
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(str(path))
    return deduped


def _filter_output_mode_files(paths: list[str], output_mode: str) -> list[str]:
    selected_suffixes = {
        "mono": ("-mono.pdf", "-mono.pptx"),
        "dual": ("-dual.pdf", "-dual.pptx"),
    }.get(output_mode.lower())
    if selected_suffixes is None:
        return paths
    return [path for path in paths if path.lower().endswith(selected_suffixes)]


def _candidate_paths_from_text(text: str) -> list[str]:
    paths = []
    for raw in text.replace("\r", "\n").split():
        token = raw.strip().strip('"').strip("'").strip("()[]{}<>,;")
        if token.lower().endswith((".pdf", ".pptx")):
            paths.append(token)
    return paths


def _failed_live_result(
    *,
    runner: str,
    started: float,
    error: str,
    exit_code: int = 1,
) -> dict[str, Any]:
    return {
        "live_status": "failed",
        "live_runner": runner,
        "live_exit_code": exit_code,
        "live_elapsed_seconds": round(time.monotonic() - started, 3),
        "live_output_files": [],
        "live_error": error,
    }


def _summarize_runner_error(completed: subprocess.CompletedProcess[str], output_files: list[str]) -> str:
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    if completed.returncode == 0 and not output_files:
        return "google scholar runner finished without PDF/PPTX outputs"
    if stderr:
        return stderr[-1000:]
    if stdout:
        return stdout[-1000:]
    return f"google scholar runner failed with exit code {completed.returncode}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_scholar_translator_home(repo_root: Path) -> Path:
    return Path(os.environ.get("SCHOLAR_TRANSLATOR_HOME", repo_root / "services" / "scholar-translator"))


def _default_glossary_path(repo_root: Path) -> str | None:
    kb_root = Path(os.environ.get("QDT_KNOWLEDGE_BASE", repo_root / "knowledge-base"))
    paths = [
        kb_root / "profiles" / "scholarly" / "glossary.csv",
        kb_root / "domains" / "quality-manufacturing" / "glossary.csv",
    ]
    existing = [str(path) for path in paths if path.is_file()]
    return os.pathsep.join(existing) if existing else None


def _glossary_spec_has_files(glossary_spec: str | None) -> bool:
    if not glossary_spec:
        return False
    return any(Path(part).is_file() for part in glossary_spec.split(os.pathsep) if part.strip())


def _write_live_contract(row: dict[str, Any], sample_root: Path, output_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    source = sample_root / row["sample"]
    if not source.is_file():
        return {
            "live_status": "failed",
            "live_runner": "contract",
            "live_exit_code": 1,
            "live_elapsed_seconds": round(time.monotonic() - started, 3),
            "live_output_files": [],
            "live_error": f"missing sample source: {source}",
        }

    contract_dir = output_dir / "live-contract"
    contract_dir.mkdir(parents=True, exist_ok=True)
    contract_path = contract_dir / f"{_slug(row['sample'])}-{row['mode']}-{row['output_mode']}.json"
    contract = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "contract",
        "mode": row["mode"],
        "route": row["route"],
        "output_mode": row["output_mode"],
        "engine": "google-translate-draft",
        "source": str(source),
        "output_dir": str(output_dir),
        "expected_suffix": row["expected_suffix"],
    }
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "live_status": "passed",
        "live_runner": "contract",
        "live_exit_code": 0,
        "live_elapsed_seconds": round(time.monotonic() - started, 3),
        "live_output_files": [str(contract_path)],
    }


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "sample"


if __name__ == "__main__":
    main()
