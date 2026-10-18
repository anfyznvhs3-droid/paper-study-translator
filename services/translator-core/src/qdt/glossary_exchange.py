"""CAT glossary import/export helpers.

QDT keeps `knowledge-base/domains/<domain>` as the source of truth. This module
only converts confirmed glossary entries to/from external CAT exchange formats.
"""

from __future__ import annotations

import csv
import io
from xml.etree import ElementTree as ET

from qdt.memory import DomainMemoryStore, GlossaryEntry


SUPPORTED_FORMATS = {"omegat", "tbx"}
SUPPORTED_IMPORT_MODES = {"candidates", "confirmed"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def export_glossary(entries: list[GlossaryEntry], fmt: str) -> str:
    normalized = _normalize_format(fmt)
    if normalized == "omegat":
        return _export_omegat(entries)
    if normalized == "tbx":
        return _export_tbx(entries)
    raise AssertionError("unreachable")


def parse_glossary_exchange(text: str, fmt: str) -> list[GlossaryEntry]:
    normalized = _normalize_format(fmt)
    if normalized == "omegat":
        return _parse_omegat(text)
    if normalized == "tbx":
        return _parse_tbx(text)
    raise AssertionError("unreachable")


def import_glossary_entries(
    store: DomainMemoryStore,
    slug: str,
    entries: list[GlossaryEntry],
    mode: str,
) -> dict[str, int | str]:
    normalized_mode = mode.strip().casefold()
    if normalized_mode not in SUPPORTED_IMPORT_MODES:
        raise ValueError(f"Unsupported import mode: {mode}")

    imported = 0
    for entry in entries:
        source = entry.source.strip()
        if not source:
            continue
        target = entry.target.strip()
        if normalized_mode == "confirmed":
            store.add_term(slug, source, target, entry.notes)
            store.record_decision(
                slug,
                source,
                target,
                status="confirmed",
                origin="cat-import",
            )
        else:
            store.record_decision(
                slug,
                source,
                target,
                status="candidate",
                origin="cat-import",
            )
        imported += 1

    return {"imported": imported, "mode": normalized_mode}


def _normalize_format(fmt: str) -> str:
    normalized = fmt.strip().casefold()
    if normalized not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported glossary exchange format: {fmt}")
    return normalized


def _export_omegat(entries: list[GlossaryEntry]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for entry in entries:
        writer.writerow([entry.source, entry.target, entry.notes])
    return buffer.getvalue()


def _parse_omegat(text: str) -> list[GlossaryEntry]:
    entries: list[GlossaryEntry] = []
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    for row in reader:
        if not row:
            continue
        source = row[0].strip()
        if not source:
            continue
        target = row[1].strip() if len(row) > 1 else ""
        notes = row[2].strip() if len(row) > 2 else ""
        entries.append(GlossaryEntry(source, target, notes))
    return entries


def _export_tbx(entries: list[GlossaryEntry]) -> str:
    ET.register_namespace("xml", "http://www.w3.org/XML/1998/namespace")
    root = ET.Element("tbx")
    body = ET.SubElement(root, "body")
    for index, entry in enumerate(entries, start=1):
        term_entry = ET.SubElement(body, "termEntry", {"id": f"term-{index}"})
        source_lang = ET.SubElement(term_entry, "langSet", {XML_LANG: "en"})
        source_tig = ET.SubElement(source_lang, "tig")
        ET.SubElement(source_tig, "term").text = entry.source

        target_lang = ET.SubElement(term_entry, "langSet", {XML_LANG: "ko"})
        target_tig = ET.SubElement(target_lang, "tig")
        ET.SubElement(target_tig, "term").text = entry.target

        if entry.notes:
            ET.SubElement(term_entry, "descrip", {"type": "note"}).text = entry.notes

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _parse_tbx(text: str) -> list[GlossaryEntry]:
    root = ET.fromstring(text)
    entries: list[GlossaryEntry] = []
    for term_entry in root.findall(".//termEntry"):
        source = ""
        target = ""
        for lang_set in term_entry.findall("langSet"):
            lang = (
                lang_set.get(XML_LANG)
                or lang_set.get("lang")
                or lang_set.get("xml:lang")
                or ""
            ).casefold()
            term = lang_set.findtext(".//term", default="").strip()
            if not term:
                continue
            if lang.startswith("en") and not source:
                source = term
            elif lang.startswith("ko") and not target:
                target = term
        if not source:
            continue
        notes = _entry_note(term_entry)
        entries.append(GlossaryEntry(source, target, notes))
    return entries


def _entry_note(term_entry: ET.Element) -> str:
    for descrip in term_entry.findall("descrip"):
        if descrip.get("type", "").casefold() == "note":
            return (descrip.text or "").strip()
    return ""

