from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qdt.pptx_native import extract_pptx_tasks

LATIN_RE = re.compile(r"[A-Za-z]")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]")
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".html", ".md"}


def build_acceptance_report(sample_root: str | Path) -> dict[str, Any]:
    root = Path(sample_root)
    samples = [_analyze_sample(path, root) for path in _iter_sample_files(root)]
    summary = _summarize(samples)
    watch_items = _watch_items(samples, summary)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_root": str(root),
        "summary": summary,
        "watch_items": watch_items,
        "samples": samples,
    }


def write_reports(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "acceptance-report.json"
    markdown_path = output / "acceptance-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    return {
        "json_report": str(json_path),
        "markdown_report": str(markdown_path),
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Sample Acceptance Report",
        "",
        f"- Sample root: `{report['sample_root']}`",
        f"- Samples: {summary['sample_count']}",
        f"- PDF: {summary['pdf_count']}",
        f"- PPTX: {summary['pptx_count']}",
        f"- Legacy PPT: {summary['ppt_count']}",
        f"- HTML/MD references: {summary['reference_count']}",
        "",
        "## Watch Items",
        "",
    ]
    watch_items = report.get("watch_items", [])
    if watch_items:
        lines.extend(f"- `{item}`" for item in watch_items)
    else:
        lines.append("- none")
    lines.extend(["", "## Samples", ""])
    lines.append("| File | Kind | Profile | Pages/Slides | Text chars | Latin | CJK | Flags |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---|")
    for sample in report["samples"]:
        page_or_slide = sample.get("pages", sample.get("slides", ""))
        flags = ", ".join(sample.get("risk_flags", [])) or "-"
        lines.append(
            "| {file} | {kind} | {profile} | {page_or_slide} | {chars} | {latin} | {cjk} | {flags} |".format(
                file=sample["relative_path"].replace("|", "\\|"),
                kind=sample["kind"],
                profile=sample["profile"],
                page_or_slide=page_or_slide,
                chars=sample.get("chars", ""),
                latin=sample.get("latin", ""),
                cjk=sample.get("cjk", ""),
                flags=flags,
            )
        )
    return "\n".join(lines) + "\n"


def run_cli(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Build a QDT sample acceptance report.")
    parser.add_argument("--sample-root", default="SAMPLE")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    sample_root = Path(args.sample_root)
    output_dir = Path(args.output_dir) if args.output_dir else sample_root / "QDT_Output" / "acceptance"
    report = build_acceptance_report(sample_root)
    written = write_reports(report, output_dir)
    return {"ok": True, **written, "summary": report["summary"], "watch_items": report["watch_items"]}


def main() -> None:
    print(json.dumps(run_cli(), ensure_ascii=False, indent=2))


def _iter_sample_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "QDT_Output" in path.parts:
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return sorted(files, key=lambda path: path.name.lower())


def _analyze_sample(path: Path, root: Path) -> dict[str, Any]:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _analyze_pdf(path, root)
    if extension == ".pptx":
        return _analyze_pptx(path, root)
    if extension == ".ppt":
        return _base_record(path, root, "ppt", "unsupported-legacy-ppt", ["unsupported-legacy-ppt"])
    if extension in {".html", ".md"}:
        return _analyze_reference(path, root)
    return _base_record(path, root, "unknown", "unsupported", ["unsupported-extension"])


def _base_record(path: Path, root: Path, kind: str, profile: str, risk_flags: list[str]) -> dict[str, Any]:
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "file": path.name,
        "kind": kind,
        "profile": profile,
        "size_bytes": path.stat().st_size,
        "risk_flags": risk_flags,
    }


def _analyze_pdf(path: Path, root: Path) -> dict[str, Any]:
    record = _base_record(path, root, "pdf", "pdf", [])
    try:
        import fitz  # type: ignore
    except Exception as err:  # pragma: no cover - depends on local environment
        record.update({"profile": "pdf-uninspected", "error": f"PyMuPDF unavailable: {err}"})
        record["risk_flags"].append("pdf-inspection-unavailable")
        return record

    doc = fitz.open(path)
    texts = []
    image_pages = 0
    images = 0
    empty_pages = 0
    for page in doc:
        text = page.get_text("text") or ""
        texts.append(text)
        if len(text.strip()) < 20:
            empty_pages += 1
        page_images = page.get_images(full=True)
        images += len(page_images)
        if page_images:
            image_pages += 1
    body = "\n".join(texts)
    pages = len(doc)
    chars = len(body)
    latin = len(LATIN_RE.findall(body))
    cjk = len(CJK_RE.findall(body))
    avg_chars_page = round(chars / pages) if pages else 0
    risk_flags = _pdf_risk_flags(
        pages=pages,
        chars=chars,
        latin=latin,
        cjk=cjk,
        empty_pages=empty_pages,
        image_pages=image_pages,
        avg_chars_page=avg_chars_page,
    )
    record.update(
        {
            "pages": pages,
            "chars": chars,
            "latin": latin,
            "cjk": cjk,
            "empty_pages": empty_pages,
            "image_pages": image_pages,
            "images": images,
            "avg_chars_page": avg_chars_page,
            "risk_flags": risk_flags,
            "profile": _pdf_profile(
                pages=pages,
                latin=latin,
                cjk=cjk,
                image_pages=image_pages,
                avg_chars_page=avg_chars_page,
                empty_pages=empty_pages,
            ),
        }
    )
    return record


def _pdf_risk_flags(
    *,
    pages: int,
    chars: int,
    latin: int,
    cjk: int,
    empty_pages: int,
    image_pages: int,
    avg_chars_page: int,
) -> list[str]:
    flags = []
    if pages and empty_pages:
        flags.append("empty-text-pages")
    if pages and empty_pages == pages:
        flags.append("image-only-or-scanned")
    if pages and image_pages / pages >= 0.6:
        flags.append("image-heavy")
    if pages and avg_chars_page < 800:
        flags.append("sparse-text-layer")
    if cjk and latin > cjk:
        flags.append("mixed-language")
    if latin and not cjk:
        flags.append("english-only-source")
    if chars == 0:
        flags.append("no-text-layer")
    return flags


def _pdf_profile(
    *,
    pages: int,
    latin: int,
    cjk: int,
    image_pages: int,
    avg_chars_page: int,
    empty_pages: int,
) -> str:
    if pages and empty_pages == pages:
        return "scanned-or-image-pdf"
    if pages and image_pages / pages >= 0.6 and avg_chars_page < 900:
        return "slide-pdf-image-heavy"
    if cjk and latin > cjk:
        return "mixed-language-pdf"
    if latin and not cjk:
        return "english-text-pdf"
    return "pdf"


def _analyze_pptx(path: Path, root: Path) -> dict[str, Any]:
    record = _base_record(path, root, "pptx", "pptx-native", [])
    try:
        tasks = extract_pptx_tasks(path)
        record.update(
            {
                "slides": _count_pptx_slides(path),
                "translation_tasks": len(tasks),
                "chars": sum(len(task.source) for task in tasks),
                "latin": sum(len(LATIN_RE.findall(task.source)) for task in tasks),
                "cjk": sum(len(CJK_RE.findall(task.source)) for task in tasks),
            }
        )
        if not tasks:
            record["risk_flags"].append("pptx-no-text-tasks")
    except Exception as err:
        record.update({"profile": "pptx-unreadable", "error": str(err)})
        record["risk_flags"].append("pptx-inspection-failed")
    return record


def _count_pptx_slides(path: Path) -> int:
    with zipfile.ZipFile(path) as pptx:
        return sum(
            1
            for name in pptx.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )


def _analyze_reference(path: Path, root: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    record = _base_record(path, root, path.suffix.lower().lstrip("."), "reference-artifact", [])
    record.update(
        {
            "chars": len(text),
            "latin": len(LATIN_RE.findall(text)),
            "cjk": len(CJK_RE.findall(text)),
        }
    )
    return record


def _summarize(samples: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "sample_count": len(samples),
        "pdf_count": _count_kind(samples, "pdf"),
        "pptx_count": _count_kind(samples, "pptx"),
        "ppt_count": _count_kind(samples, "ppt"),
        "reference_count": sum(1 for sample in samples if sample["kind"] in {"html", "md"}),
    }


def _count_kind(samples: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for sample in samples if sample["kind"] == kind)


def _watch_items(samples: list[dict[str, Any]], summary: dict[str, int]) -> list[str]:
    items = []
    if summary["sample_count"] == 0:
        items.append("sample-root-empty")
    if summary["pptx_count"] == 0:
        items.append("sample-pptx-missing")
    if summary["ppt_count"]:
        items.append("legacy-ppt-present")
    if any("image-only-or-scanned" in sample.get("risk_flags", []) for sample in samples):
        items.append("scanned-pdf-present")
    if any("image-heavy" in sample.get("risk_flags", []) for sample in samples):
        items.append("image-heavy-slide-pdf-present")
    if any("mixed-language" in sample.get("risk_flags", []) for sample in samples):
        items.append("mixed-language-pdf-present")
    return items


if __name__ == "__main__":
    main()
