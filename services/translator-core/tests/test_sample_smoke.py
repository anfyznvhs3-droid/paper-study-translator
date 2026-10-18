from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import fitz
import pytest

from qdt import sample_smoke
from qdt.sample_smoke import build_smoke_report, plan_smoke_row, run_cli


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)


def _write_minimal_pptx(path: Path, slide_text: str) -> None:
    slide_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:bodyPr/>
          <a:p><a:r><a:t>{slide_text}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
    presentation_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""
    with zipfile.ZipFile(path, "w") as pptx:
        pptx.writestr("[Content_Types].xml", content_types)
        pptx.writestr("_rels/.rels", root_rels)
        pptx.writestr("ppt/presentation.xml", presentation_xml)
        pptx.writestr("ppt/_rels/presentation.xml.rels", rels_xml)
        pptx.writestr("ppt/slides/slide1.xml", slide_xml)


def test_dry_run_creates_google_and_agent_rows_for_pdf(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")

    report = build_smoke_report(sample_root, modes=["google", "agent"])

    assert report["summary"]["row_count"] == 2
    assert {row["mode"] for row in report["rows"]} == {"google", "agent"}
    assert {row["route"] for row in report["rows"]} == {"pdf-scholar", "pdf-agent"}
    assert all(row["status"] == "ready" for row in report["rows"])


def test_mixed_language_pdf_is_needs_review_for_both_modes() -> None:
    sample = {
        "relative_path": "mixed.pdf",
        "kind": "pdf",
        "profile": "mixed-language-pdf",
        "risk_flags": ["mixed-language"],
    }

    rows = [
        plan_smoke_row(sample, mode="google"),
        plan_smoke_row(sample, mode="agent"),
    ]

    assert {row["status"] for row in rows} == {"needs-review"}
    assert all("mixed-language" in row["reasons"] for row in rows)
    assert {row["route"] for row in rows} == {"pdf-mixed-renderer", "pdf-agent"}


def test_reference_artifacts_are_skipped_for_both_modes(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    (sample_root / "notes.md").write_text("review notes", encoding="utf-8")

    report = build_smoke_report(sample_root, modes=["google", "agent"])

    assert {row["status"] for row in report["rows"]} == {"skipped"}
    assert all(row["route"] == "unsupported" for row in report["rows"])
    assert all("reference-artifact" in row["reasons"] for row in report["rows"])


def test_pptx_routes_to_native_for_google_and_agent(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_minimal_pptx(sample_root / "deck.pptx", "Control Plan")

    report = build_smoke_report(sample_root, modes=["google", "agent"])

    assert report["summary"]["row_count"] == 2
    assert {row["route"] for row in report["rows"]} == {"pptx-native"}
    assert {row["expected_suffix"] for row in report["rows"]} == {".pptx"}
    assert all(row["status"] == "ready" for row in report["rows"])


def test_cli_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")

    result = run_cli(["--sample-root", str(sample_root), "--output-dir", str(output_dir)])

    assert result["ok"] is True
    json_path = Path(result["json_report"])
    markdown_path = Path(result["markdown_report"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["row_count"] == 2
    assert "Sample Smoke Report" in markdown_path.read_text(encoding="utf-8")


def test_live_requires_one_mode_and_positive_limit(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")

    with pytest.raises(ValueError, match="one explicit mode"):
        run_cli(["--sample-root", str(sample_root), "--live"])

    with pytest.raises(ValueError, match="positive --limit"):
        run_cli(["--sample-root", str(sample_root), "--live", "--mode", "google", "--limit", "0"])


def test_live_google_executes_first_ready_row_with_injected_runner(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")
    (sample_root / "notes.md").write_text("reference notes", encoding="utf-8")
    calls: list[tuple[str, Path, Path]] = []

    def runner(row: dict[str, Any], root: Path, output: Path) -> dict[str, Any]:
        calls.append((row["sample"], root, output))
        return {
            "live_status": "passed",
            "live_runner": "test-runner",
            "live_exit_code": 0,
            "live_elapsed_seconds": 0.01,
            "live_output_files": [str(output / "paper-ko.pdf")],
        }

    report = build_smoke_report(
        sample_root,
        modes=["google"],
        live=True,
        limit=1,
        output_dir=output_dir,
        live_runner=runner,
    )

    assert calls == [("paper.pdf", sample_root, output_dir)]
    assert report["summary"]["live_executed"] == 1
    assert report["summary"]["live_passed"] == 1
    assert report["summary"]["live_failed"] == 0
    assert report["summary"]["live_skipped"] == 1
    rows = {row["sample"]: row for row in report["rows"]}
    assert rows["paper.pdf"]["live_status"] == "passed"
    assert rows["paper.pdf"]["live_runner"] == "test-runner"
    assert rows["notes.md"]["live_status"] == "skipped"
    assert "not-ready" in rows["notes.md"]["live_reasons"]


def test_live_agent_is_not_enabled_yet(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")

    with pytest.raises(ValueError, match="agent live smoke"):
        build_smoke_report(sample_root, modes=["agent"], live=True, limit=1)


def test_cli_live_google_writes_contract_artifact(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")

    result = run_cli(
        [
            "--sample-root",
            str(sample_root),
            "--output-dir",
            str(output_dir),
            "--mode",
            "google",
            "--live",
            "--limit",
            "1",
        ]
    )

    assert result["summary"]["live_executed"] == 1
    assert result["summary"]["live_passed"] == 1
    contract_files = list((output_dir / "live-contract").glob("*.json"))
    assert len(contract_files) == 1
    contract = json.loads(contract_files[0].read_text(encoding="utf-8"))
    assert contract["mode"] == "google"
    assert contract["route"] == "pdf-scholar"
    assert contract["source"].endswith("paper.pdf")
    report = json.loads(Path(result["json_report"]).read_text(encoding="utf-8"))
    assert report["rows"][0]["live_status"] == "passed"


def test_google_runner_uses_app_scholar_cli_contract_and_collects_outputs(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    translator_home = tmp_path / "scholar-translator"
    glossary = tmp_path / "knowledge-base" / "domains" / "quality-manufacturing" / "glossary.csv"
    sample_root.mkdir()
    output_dir.mkdir()
    translator_home.mkdir()
    glossary.parent.mkdir(parents=True)
    glossary.write_text("source,target,notes\nFMEA,FMEA,\n", encoding="utf-8")
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")
    calls: list[dict[str, Any]] = []

    def command_runner(
        args: list[str],
        cwd: Path,
        env: dict[str, str],
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        mono = output_dir / "paper-mono.pdf"
        dual = output_dir / "paper-dual.pdf"
        mono.write_bytes(b"%PDF-1.4\n")
        dual.write_bytes(b"%PDF-1.4\n")
        calls.append(
            {
                "args": args,
                "cwd": cwd,
                "env": env,
                "timeout_seconds": timeout_seconds,
            }
        )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=f"{mono}\n{dual}", stderr="")

    runner = sample_smoke.make_google_scholar_runner(
        python_exe="python-x",
        translator_home=translator_home,
        glossary_path=glossary,
        command_runner=command_runner,
        timeout_seconds=11,
    )

    result = runner(
        {
            "sample": "paper.pdf",
            "mode": "google",
            "output_mode": "mono",
            "route": "pdf-scholar",
            "expected_suffix": ".pdf",
        },
        sample_root,
        output_dir,
    )

    wrapper = translator_home / "qdt_scholar_with_glossary.py"
    assert calls[0]["args"] == [
        "python-x",
        str(wrapper),
        str(sample_root / "paper.pdf"),
        "--lang-out",
        "ko",
        "--service",
        "google",
        "--output",
        str(output_dir),
        "--thread",
        "4",
    ]
    assert calls[0]["cwd"] == translator_home
    assert str(translator_home) in calls[0]["env"]["PYTHONPATH"]
    assert calls[0]["env"]["QDT_GLOSSARY"] == str(glossary)
    assert calls[0]["timeout_seconds"] == 11
    assert result["live_status"] == "passed"
    assert result["live_runner"] == "google-scholar"
    assert result["live_exit_code"] == 0
    assert result["live_output_files"] == [str(output_dir / "paper-mono.pdf")]


def test_default_google_glossary_includes_scholarly_profile_before_domain(tmp_path: Path) -> None:
    profile = tmp_path / "knowledge-base" / "profiles" / "scholarly" / "glossary.csv"
    domain = tmp_path / "knowledge-base" / "domains" / "quality-manufacturing" / "glossary.csv"
    profile.parent.mkdir(parents=True)
    domain.parent.mkdir(parents=True)
    profile.write_text("source,target,notes\nAbstract,초록,exact-heading\n", encoding="utf-8")
    domain.write_text("source,target,notes\nFMEA,고장모드,\n", encoding="utf-8")

    spec = sample_smoke._default_glossary_path(tmp_path)

    assert [Path(part) for part in str(spec).split(os.pathsep)] == [profile, domain]


def test_cli_live_google_accepts_google_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    sample_root.mkdir()
    _write_pdf(sample_root / "paper.pdf", "Control plan and supplier audit")
    executed: list[str] = []

    def fake_google_runner(**_kwargs: Any) -> sample_smoke.LiveRunner:
        def runner(row: dict[str, Any], _root: Path, output: Path) -> dict[str, Any]:
            executed.append(row["sample"])
            output_file = output / "paper-mono.pdf"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(b"%PDF-1.4\n")
            return {
                "live_status": "passed",
                "live_runner": "google-scholar",
                "live_exit_code": 0,
                "live_elapsed_seconds": 0.01,
                "live_output_files": [str(output_file)],
            }

        return runner

    monkeypatch.setattr(sample_smoke, "make_google_scholar_runner", fake_google_runner)

    result = run_cli(
        [
            "--sample-root",
            str(sample_root),
            "--output-dir",
            str(output_dir),
            "--mode",
            "google",
            "--live",
            "--limit",
            "1",
            "--runner",
            "google",
        ]
    )

    assert executed == ["paper.pdf"]
    assert result["summary"]["live_executed"] == 1
    report = json.loads(Path(result["json_report"]).read_text(encoding="utf-8"))
    assert report["live_runner"] == "google"
    assert report["rows"][0]["live_runner"] == "google-scholar"
