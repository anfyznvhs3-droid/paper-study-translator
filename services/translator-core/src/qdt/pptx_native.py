"""Native PPTX translation sidecar for QDT.

This module edits Office Open XML directly. It intentionally handles a narrow,
testable V1 surface: slide text paragraphs in ``ppt/slides/slide*.xml``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from qdt.agent_runner import AgentTask, load_glossary_csv as load_agent_glossary_csv
from qdt.agent_runner import run_agent_batches

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

NS = {"a": A_NS, "p": P_NS, "r": R_NS}
SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")

ET.register_namespace("a", A_NS)
ET.register_namespace("p", P_NS)
ET.register_namespace("r", R_NS)


@dataclass(frozen=True)
class PptxTask:
    id: int
    slide: int
    source: str


def extract_pptx_tasks(pptx_path: str | Path) -> list[PptxTask]:
    tasks: list[PptxTask] = []
    seen: set[str] = set()
    with zipfile.ZipFile(pptx_path, "r") as zf:
        for slide_name in _slide_names(zf):
            slide_number = _slide_number(slide_name)
            root = ET.fromstring(zf.read(slide_name))
            for text in _slide_texts(root):
                if text in seen or not _is_translatable(text):
                    continue
                seen.add(text)
                tasks.append(PptxTask(id=len(tasks) + 1, slide=slide_number, source=text))
    return tasks


def write_mono_pptx(
    pptx_path: str | Path,
    output_path: str | Path,
    translations: dict[str, str],
) -> Path:
    source = Path(pptx_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source, "r") as zf_in, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for item in zf_in.infolist():
            data = zf_in.read(item.filename)
            if SLIDE_RE.match(item.filename):
                data = _replace_slide_xml(data, translations)
            zf_out.writestr(item, data)
    return output


def write_dual_pptx(
    pptx_path: str | Path,
    output_path: str | Path,
    translations: dict[str, str],
) -> Path:
    source = Path(pptx_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source, "r") as zf_in:
        parts = {item.filename: zf_in.read(item.filename) for item in zf_in.infolist()}
        infos = {item.filename: item for item in zf_in.infolist()}
        slide_names = _slide_names(zf_in)

    max_slide = max((_slide_number(name) for name in slide_names), default=0)
    clone_names: dict[str, str] = {}
    new_parts: dict[str, bytes] = dict(parts)
    for offset, slide_name in enumerate(slide_names, start=1):
        clone_name = f"ppt/slides/slide{max_slide + offset}.xml"
        clone_names[slide_name] = clone_name
        new_parts[clone_name] = _replace_slide_xml(parts[slide_name], translations)

        rel_name = f"ppt/slides/_rels/slide{_slide_number(slide_name)}.xml.rels"
        if rel_name in parts:
            clone_rel_name = f"ppt/slides/_rels/slide{max_slide + offset}.xml.rels"
            new_parts[clone_rel_name] = parts[rel_name]

    _rewrite_dual_manifest_parts(new_parts, slide_names, clone_names)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf_out:
        written = set()
        for name in parts:
            zf_out.writestr(infos[name], new_parts[name])
            written.add(name)
            clone_name = clone_names.get(name)
            if clone_name:
                zf_out.writestr(clone_name, new_parts[clone_name])
                written.add(clone_name)
                clone_rel_name = f"ppt/slides/_rels/slide{_slide_number(clone_name)}.xml.rels"
                if clone_rel_name in new_parts:
                    zf_out.writestr(clone_rel_name, new_parts[clone_rel_name])
                    written.add(clone_rel_name)
        for name, data in new_parts.items():
            if name not in written:
                zf_out.writestr(name, data)
    return output


def translate_tasks(
    tasks: list[PptxTask],
    service: str,
    engine: str,
    quality: str,
    review_mode: str,
    output_mode: str,
    domain: str,
    offline_map: str | None = None,
    glossary: str | None = None,
) -> dict[str, str]:
    glossary_terms = load_glossary_csv(glossary)
    if service == "offline":
        translations = load_offline_map(offline_map)
    elif service == "google":
        translations = _translate_with_google(tasks)
    elif service == "gemini":
        from scholar_translator.translator import GeminiTranslator
        translator = GeminiTranslator("en", "ko", None)
        translations = {task.source: translator.translate(task.source) for task in tasks}
    elif service == "agent":
        agent_translations = run_agent_batches(
            tasks=[AgentTask(id=task.id, source=task.source) for task in tasks],
            complete=_complete_for_agent_engine(engine),
            engine=engine,
            quality=quality,
            review_mode=review_mode,
            output_mode=output_mode,
            domain=domain,
            glossary=glossary_terms,
            max_batch_items=12,
        )
        translations = {item.source: item.translation for item in agent_translations}
    else:
        raise ValueError(f"Unsupported PPTX translation service: {service}")

    return {
        task.source: apply_glossary_overrides(
            task.source,
            translations.get(task.source, task.source),
            glossary_terms,
        )
        for task in tasks
    }


def run_cli(argv: list[str]) -> dict:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_dir = Path(args.output)
    mode = args.output_mode.lower()
    if mode not in {"mono", "dual"}:
        raise ValueError("--output-mode must be mono or dual")

    tasks = extract_pptx_tasks(input_path)
    translations = translate_tasks(
        tasks,
        service=args.service,
        engine=args.engine,
        quality=args.quality,
        review_mode=args.review_mode,
        output_mode=mode,
        domain=args.domain,
        offline_map=args.offline_map,
        glossary=args.glossary,
    )

    output_path = output_dir / f"{input_path.stem}-ko-{mode}.pptx"
    if mode == "dual":
        write_dual_pptx(input_path, output_path, translations)
    else:
        write_mono_pptx(input_path, output_path, translations)

    return {
        "ok": True,
        "format": "pptx-native",
        "task_count": len(tasks),
        "output_files": [str(output_path)],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate PPTX files natively for QDT.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-mode", choices=["mono", "dual"], default="mono")
    parser.add_argument("--service", choices=["offline", "google", "gemini", "agent"], default="offline")
    parser.add_argument("--engine", default="codex-agent")
    parser.add_argument("--quality", default="realistic")
    parser.add_argument("--review-mode", default="off")
    parser.add_argument("--domain", default="quality-manufacturing")
    parser.add_argument("--offline-map")
    parser.add_argument("--glossary")
    return parser.parse_args(argv)


def load_offline_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    rows: dict[str, str] = {}
    with Path(path).open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            source = row.get("source")
            translation = row.get("translation")
            if not isinstance(source, str) or not isinstance(translation, str):
                raise ValueError(f"Invalid offline map row at line {line_number}")
            rows[source] = translation
    return rows


def load_glossary_csv(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    glossary: dict[str, str] = {}
    for raw_path in str(path).split(os.pathsep):
        if not raw_path.strip():
            continue
        glossary_path = Path(raw_path)
        if not glossary_path.is_file():
            continue
        with glossary_path.open("r", encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file):
                source = (row.get("source") or "").strip()
                target = (row.get("target") or "").strip()
                if source and target:
                    glossary[source] = target
    return glossary


def apply_glossary_overrides(source: str, translated: str, glossary: dict[str, str]) -> str:
    direct = glossary.get(source)
    if direct:
        return direct
    source_lower = source.lower()
    result = translated
    for english, korean in sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True):
        if english.lower() not in source_lower:
            continue
        pattern = r"(?<![A-Za-z0-9])" + re.escape(english) + r"(?![A-Za-z0-9])"
        result = re.sub(pattern, korean, result, flags=re.IGNORECASE)
    return result


def _slide_names(zf: zipfile.ZipFile) -> list[str]:
    return sorted(
        [name for name in zf.namelist() if SLIDE_RE.match(name)],
        key=_slide_number,
    )


def _slide_number(name: str) -> int:
    match = SLIDE_RE.match(name)
    if not match:
        raise ValueError(f"Not a slide XML part: {name}")
    return int(match.group(1))


def _slide_texts(root: ET.Element) -> list[str]:
    texts: list[str] = []
    for paragraph in root.findall(".//a:p", NS):
        text = _paragraph_text(paragraph)
        if text:
            texts.append(text)
    return texts


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(t.text or "" for t in paragraph.findall(".//a:t", NS)).strip()


def _is_translatable(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[\d\s.,:/%+\-()]+", stripped):
        return False
    if re.fullmatch(r"https?://\S+|\S+@\S+|\S+\.(?:com|org|net|co|io)\S*", stripped, flags=re.I):
        return False
    return bool(re.search(r"[A-Za-z]", stripped))


def _replace_slide_xml(slide_xml: bytes, translations: dict[str, str]) -> bytes:
    root = ET.fromstring(slide_xml)
    for tx_body in root.findall(".//p:txBody", NS) + root.findall(".//a:txBody", NS):
        for paragraph in tx_body.findall("a:p", NS):
            source = _paragraph_text(paragraph)
            translation = translations.get(source)
            if not translation or translation == source:
                continue
            _replace_paragraph_text(paragraph, translation)
            _ensure_norm_autofit(tx_body)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _replace_paragraph_text(paragraph: ET.Element, translation: str) -> None:
    text_nodes = paragraph.findall(".//a:t", NS)
    if not text_nodes:
        return
    text_nodes[0].text = translation
    for node in text_nodes[1:]:
        node.text = ""

    first_run = paragraph.find("a:r", NS)
    if first_run is not None:
        _ensure_korean_font(first_run)


def _ensure_korean_font(run: ET.Element) -> None:
    r_pr = run.find("a:rPr", NS)
    if r_pr is None:
        r_pr = ET.Element(f"{{{A_NS}}}rPr")
        run.insert(0, r_pr)
    r_pr.set("lang", "ko-KR")
    east_asian = r_pr.find("a:ea", NS)
    if east_asian is None:
        east_asian = ET.SubElement(r_pr, f"{{{A_NS}}}ea")
    east_asian.set("typeface", "Malgun Gothic")


def _ensure_norm_autofit(tx_body: ET.Element) -> None:
    body_pr = tx_body.find("a:bodyPr", NS)
    if body_pr is None:
        body_pr = ET.Element(f"{{{A_NS}}}bodyPr")
        tx_body.insert(0, body_pr)
    for child in list(body_pr):
        if child.tag in {f"{{{A_NS}}}noAutofit", f"{{{A_NS}}}spAutoFit"}:
            body_pr.remove(child)
    if body_pr.find("a:normAutofit", NS) is None:
        ET.SubElement(body_pr, f"{{{A_NS}}}normAutofit")


def _rewrite_dual_manifest_parts(
    parts: dict[str, bytes],
    slide_names: list[str],
    clone_names: dict[str, str],
) -> None:
    if "ppt/presentation.xml" in parts and "ppt/_rels/presentation.xml.rels" in parts:
        parts["ppt/presentation.xml"], parts["ppt/_rels/presentation.xml.rels"] = _rewrite_presentation(
            parts["ppt/presentation.xml"],
            parts["ppt/_rels/presentation.xml.rels"],
            slide_names,
            clone_names,
        )
    if "[Content_Types].xml" in parts:
        parts["[Content_Types].xml"] = _rewrite_content_types(parts["[Content_Types].xml"], clone_names.values())


def _rewrite_presentation(
    presentation_xml: bytes,
    rels_xml: bytes,
    slide_names: list[str],
    clone_names: dict[str, str],
) -> tuple[bytes, bytes]:
    pres_root = ET.fromstring(presentation_xml)
    rels_root = ET.fromstring(rels_xml)
    sld_id_list = pres_root.find("p:sldIdLst", NS)
    if sld_id_list is None:
        return presentation_xml, rels_xml

    rel_by_id = {
        rel.get("Id"): rel
        for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")
        if rel.get("Id")
    }
    target_to_rid = {
        _target_to_slide_name(rel.get("Target", "")): rid
        for rid, rel in rel_by_id.items()
    }
    next_rel_id = _next_rid(rel_by_id.keys())
    next_slide_id = max((int(node.get("id", "255")) for node in sld_id_list), default=255) + 1

    original_nodes = list(sld_id_list)
    for node in original_nodes:
        rid = node.get(f"{{{R_NS}}}id")
        slide_name = _target_to_slide_name(rel_by_id.get(rid).get("Target", "")) if rid in rel_by_id else ""
        clone_name = clone_names.get(slide_name)
        if not clone_name:
            continue
        new_rid = f"rId{next_rel_id}"
        next_rel_id += 1
        new_rel = ET.SubElement(rels_root, f"{{{PKG_REL_NS}}}Relationship")
        new_rel.set("Id", new_rid)
        new_rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")
        new_rel.set("Target", clone_name.removeprefix("ppt/"))

        new_node = ET.Element(f"{{{P_NS}}}sldId")
        new_node.set("id", str(next_slide_id))
        next_slide_id += 1
        new_node.set(f"{{{R_NS}}}id", new_rid)
        sld_id_list.insert(list(sld_id_list).index(node) + 1, new_node)

    ET.register_namespace("", PKG_REL_NS)
    return (
        ET.tostring(pres_root, encoding="utf-8", xml_declaration=True),
        ET.tostring(rels_root, encoding="utf-8", xml_declaration=True),
    )


def _rewrite_content_types(content_xml: bytes, clone_names: list[str] | tuple[str, ...] | object) -> bytes:
    root = ET.fromstring(content_xml)
    existing = {node.get("PartName") for node in root.findall(f"{{{CONTENT_TYPES_NS}}}Override")}
    for clone_name in clone_names:
        part_name = f"/{clone_name}"
        if part_name in existing:
            continue
        override = ET.SubElement(root, f"{{{CONTENT_TYPES_NS}}}Override")
        override.set("PartName", part_name)
        override.set(
            "ContentType",
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )
    ET.register_namespace("", CONTENT_TYPES_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _target_to_slide_name(target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        target = target.lstrip("/")
    if target.startswith("ppt/"):
        return target
    return f"ppt/{target}"


def _next_rid(ids) -> int:
    max_seen = 0
    for rid in ids:
        match = re.fullmatch(r"rId(\d+)", rid or "")
        if match:
            max_seen = max(max_seen, int(match.group(1)))
    return max_seen + 1


def _translate_with_google(tasks: list[PptxTask]) -> dict[str, str]:
    from scholar_translator.translator import GoogleTranslator

    translator = GoogleTranslator("en", "ko", "")
    return {task.source: translator.translate(task.source) for task in tasks}


def _complete_for_agent_engine(engine: str):
    from qdt.agent_runner import complete_for_engine

    return complete_for_engine(engine)


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_cli(sys.argv[1:] if argv is None else argv)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
