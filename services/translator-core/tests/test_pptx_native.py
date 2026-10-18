"""Tests for native PPTX translation.

Run from services/translator-core:
    PYTHONPATH=src python -m pytest tests/test_pptx_native.py -q
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from qdt.pptx_native import (
    extract_pptx_tasks,
    load_glossary_csv,
    run_cli,
    write_dual_pptx,
    write_mono_pptx,
)


def write_minimal_pptx(
    tmp_path: Path,
    slides: list[list[list[str]]],
    extra_parts: dict[str, str] | None = None,
) -> Path:
    path = tmp_path / "deck.pptx"
    content_overrides = [
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
    ]
    slide_ids = []
    rels = []
    for index, paragraphs in enumerate(slides, start=1):
        content_overrides.append(
            f'<Override PartName="/ppt/slides/slide{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
        slide_ids.append(f'<p:sldId id="{255 + index}" r:id="rId{index}"/>')
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{index}.xml"/>'
        )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + "".join(content_overrides)
            + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="ppt/presentation.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<p:sldIdLst>{"".join(slide_ids)}</p:sldIdLst>'
            "</p:presentation>",
        )
        zf.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels)
            + "</Relationships>",
        )
        for index, paragraphs in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{index}.xml", slide_xml(paragraphs))
            zf.writestr(
                f"ppt/slides/_rels/slide{index}.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
            )
        for name, data in (extra_parts or {}).items():
            zf.writestr(name, data)
    return path


def slide_xml(paragraphs: list[list[str]]) -> str:
    rendered = []
    for paragraph in paragraphs:
        runs = "".join(
            f'<a:r><a:rPr lang="en-US" sz="1800"/><a:t>{text}</a:t></a:r>'
            for text in paragraph
        )
        rendered.append(f"<a:p>{runs}</a:p>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"TextBox 1\"/>"
        "</p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>"
        + "".join(rendered)
        + "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )


def read_part(pptx: Path, name: str) -> str:
    with zipfile.ZipFile(pptx, "r") as zf:
        return zf.read(name).decode("utf-8")


def slide_count(pptx: Path) -> int:
    with zipfile.ZipFile(pptx, "r") as zf:
        return len(
            [
                name
                for name in zf.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ]
        )


def test_fragmented_runs_are_one_paragraph_task(tmp_path: Path) -> None:
    pptx = write_minimal_pptx(tmp_path, [[["Failure ", "mode"]]])

    tasks = extract_pptx_tasks(pptx)

    assert [(task.id, task.slide, task.source) for task in tasks] == [(1, 1, "Failure mode")]


def test_replacement_sets_korean_font_and_autofit(tmp_path: Path) -> None:
    pptx = write_minimal_pptx(tmp_path, [[["Failure ", "mode"]]])
    out = tmp_path / "deck-ko-mono.pptx"

    write_mono_pptx(pptx, out, {"Failure mode": "고장 모드"})

    xml = read_part(out, "ppt/slides/slide1.xml")
    assert "고장 모드" in xml
    assert "Failure " not in xml
    assert 'typeface="Malgun Gothic"' in xml
    assert "normAutofit" in xml


def test_dual_output_inserts_translated_clone_after_original(tmp_path: Path) -> None:
    pptx = write_minimal_pptx(tmp_path, [[["Control Plan"]]])
    out = tmp_path / "deck-ko-dual.pptx"

    write_dual_pptx(pptx, out, {"Control Plan": "관리 계획"})

    assert slide_count(out) == 2
    assert "Control Plan" in read_part(out, "ppt/slides/slide1.xml")
    assert "관리 계획" in read_part(out, "ppt/slides/slide2.xml")
    presentation = read_part(out, "ppt/presentation.xml")
    assert presentation.index("rId1") < presentation.index("rId2")


def test_non_slide_parts_are_preserved_but_not_translated(tmp_path: Path) -> None:
    note_xml = "<p:notes>Control Plan</p:notes>"
    pptx = write_minimal_pptx(
        tmp_path,
        [[["Control Plan"]]],
        extra_parts={"ppt/notesSlides/notesSlide1.xml": note_xml},
    )
    out = tmp_path / "deck-ko-mono.pptx"

    write_mono_pptx(pptx, out, {"Control Plan": "관리 계획"})

    assert read_part(out, "ppt/notesSlides/notesSlide1.xml") == note_xml


def test_load_glossary_csv_merges_path_list(tmp_path: Path) -> None:
    profile = tmp_path / "scholarly.csv"
    domain = tmp_path / "domain.csv"
    profile.write_text("source,target,notes\nAbstract,초록,exact-heading\nFMEA,프로필 FMEA,\n", encoding="utf-8")
    domain.write_text("source,target,notes\nFMEA,고장모드 및 영향분석(FMEA),\n", encoding="utf-8")

    glossary = load_glossary_csv(os.pathsep.join([str(profile), str(domain)]))

    assert glossary == {
        "Abstract": "초록",
        "FMEA": "고장모드 및 영향분석(FMEA)",
    }


def test_cli_offline_mono_writes_output_file(tmp_path: Path) -> None:
    pptx = write_minimal_pptx(tmp_path, [[["Control Plan"]]])
    mapping = tmp_path / "map.jsonl"
    mapping.write_text(
        json.dumps({"source": "Control Plan", "translation": "관리 계획"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = run_cli(
        [
            "--input",
            str(pptx),
            "--output",
            str(tmp_path),
            "--output-mode",
            "mono",
            "--service",
            "offline",
            "--offline-map",
            str(mapping),
        ]
    )

    assert result["ok"] is True
    assert result["output_files"][0].endswith("-mono.pptx")
    assert Path(result["output_files"][0]).is_file()
