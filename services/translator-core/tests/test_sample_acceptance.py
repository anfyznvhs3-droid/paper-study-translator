from __future__ import annotations

import json
import zipfile
from pathlib import Path

import fitz

from qdt.sample_acceptance import build_acceptance_report, run_cli


def _write_pdf(path: Path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
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


def test_build_report_records_pdf_text_layer_and_missing_pptx_watch(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_pdf(sample_root / "english.pdf", ["Control plan and supplier audit", "Failure mode analysis"])

    report = build_acceptance_report(sample_root)

    assert report["summary"]["pdf_count"] == 1
    assert report["summary"]["pptx_count"] == 0
    assert "sample-pptx-missing" in report["watch_items"]
    pdf = report["samples"][0]
    assert pdf["kind"] == "pdf"
    assert pdf["pages"] == 2
    assert pdf["chars"] > 40
    assert pdf["latin"] > 30
    assert pdf["profile"] == "english-text-pdf"


def test_build_report_counts_pptx_native_tasks(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_minimal_pptx(sample_root / "deck.pptx", "Control Plan")

    report = build_acceptance_report(sample_root)

    assert report["summary"]["pptx_count"] == 1
    assert "sample-pptx-missing" not in report["watch_items"]
    pptx = report["samples"][0]
    assert pptx["kind"] == "pptx"
    assert pptx["slides"] == 1
    assert pptx["translation_tasks"] == 1
    assert pptx["profile"] == "pptx-native"


def test_build_report_counts_pptx_slides_even_without_text_tasks(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    sample_root.mkdir()
    _write_minimal_pptx(sample_root / "blank-deck.pptx", "")

    report = build_acceptance_report(sample_root)

    pptx = report["samples"][0]
    assert pptx["slides"] == 1
    assert pptx["translation_tasks"] == 0
    assert "pptx-no-text-tasks" in pptx["risk_flags"]


def test_run_cli_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    sample_root = tmp_path / "SAMPLE"
    output_dir = tmp_path / "out"
    sample_root.mkdir()
    _write_pdf(sample_root / "manual.pdf", ["Specifications and maintenance"])

    result = run_cli(["--sample-root", str(sample_root), "--output-dir", str(output_dir)])

    assert result["ok"] is True
    json_path = Path(result["json_report"])
    markdown_path = Path(result["markdown_report"])
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["sample_count"] == 1
    assert "Sample Acceptance Report" in markdown_path.read_text(encoding="utf-8")
