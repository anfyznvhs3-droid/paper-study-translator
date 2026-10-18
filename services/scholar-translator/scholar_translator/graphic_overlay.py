"""Overlay translated text onto labels that live inside figure/diagram regions.

The page-frame converter preserves text inside layout-model "figure" regions
verbatim (it treats those pixels as a reserved/formula area and redraws the
original glyphs). That is correct for formulas and logos, but flow-chart and
diagram boxes ("APQP Gate", "PPAP Release", ...) are meaningful labels that must
be translated. This module mirrors :mod:`table_overlay`: it re-uses the same
per-cell translate + paint helpers, but selects spans by figure-region geometry
instead of by ``find_tables``.

The figure regions come from the layout model's authoritative ``figure``-class
boxes, captured by the converter (``high_level.translate_patch``) while it already
runs the model per page and passed in here as page-normalized fractions, so this
module never runs the model itself and stays unit-testable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import fitz

from scholar_translator.table_overlay import translate_table_cell_text

logger = logging.getLogger(__name__)

Region = Sequence[float]  # normalized (x0, y0, x1, y1) fractions in [0, 1]


def should_overlay_graphic_text(envs: dict | None = None) -> bool:
    """Kill switch, mirroring ``should_overlay_table_cells``. Default on."""
    if not envs:
        return True
    raw = envs.get("QDT_GRAPHIC_TEXT_OVERLAY")
    if raw is None:
        return True
    return str(raw).strip().casefold() not in {"0", "false", "off", "no"}


def _denormalize(region: Region, page_rect: fitz.Rect) -> fitz.Rect:
    x0, y0, x1, y1 = region
    return fitz.Rect(
        page_rect.x0 + x0 * page_rect.width,
        page_rect.y0 + y0 * page_rect.height,
        page_rect.x0 + x1 * page_rect.width,
        page_rect.y0 + y1 * page_rect.height,
    )


def _center_inside(region: fitz.Rect, span_bbox: fitz.Rect) -> bool:
    cx = (span_bbox.x0 + span_bbox.x1) / 2
    cy = (span_bbox.y0 + span_bbox.y1) / 2
    return region.x0 <= cx <= region.x1 and region.y0 <= cy <= region.y1


def iter_graphic_label_spans(
    page: fitz.Page, figure_regions: Sequence[Region]
) -> Iterator[tuple[fitz.Rect, str]]:
    """Yield ``(bbox, text)`` for text spans whose center lies in a figure region.

    Selection is purely geometric; value/unit/number filtering and domain
    overrides are applied later by ``translate_table_cell_text`` so the same
    rules cover table cells and figure labels alike (axis ticks like "100" are
    dropped there, not here).
    """
    if not figure_regions:
        return
    page_rect = page.rect
    rects = [_denormalize(r, page_rect) for r in figure_regions]
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:  # text blocks only
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                normalized = " ".join(str(span.get("text", "")).split()).strip()
                if not normalized:
                    continue
                bbox = fitz.Rect(span["bbox"])
                if any(_center_inside(r, bbox) for r in rects):
                    yield bbox, normalized


def _paint_label_text(
    page: fitz.Page,
    bbox: fitz.Rect,
    text: str,
    font_file: str | None,
) -> bool:
    """Paint a translated single-line label centered on ``bbox``.

    Figure labels are tight one-line boxes, so ``table_overlay._paint_cell_text``
    (tuned for taller table rows) cannot fit a line: ``insert_textbox`` reserves
    line-height overhead that exceeds the ~7-9pt label height. Here we cover the
    original glyphs and write into a box generously sized around the label center
    (clamped to the page), shrinking the font until one line fits.
    """
    from scholar_translator.image_ocr import background_color, paint_translation
    color=background_color(page,bbox)
    return color is not None and paint_translation(page,bbox,text,font_file,color)


def apply_graphic_text_overlays(
    source_pdf: str | Path,
    target_pdf: str | Path,
    translator: Any,
    figure_regions_by_page: Mapping[int, Sequence[Region]],
    font_file: str | None = None,
    audit_records: list | None = None,
) -> int:
    """Overlay translated labels onto figure regions of ``target_pdf``.

    During extraction (``translator`` writes tasks) this records every figure
    label as its own task; during render (``translator`` reads the offline map)
    it paints the agent translation in place. Returns the number of labels
    painted.
    """
    source_doc = fitz.open(source_pdf)
    target_doc = fitz.open(target_pdf)
    replacement_count = 0
    try:
        page_count = min(source_doc.page_count, target_doc.page_count)
        for page_index in range(page_count):
            regions = figure_regions_by_page.get(page_index) or []
            if not regions:
                continue
            source_page = source_doc[page_index]
            target_page = target_doc[page_index]
            for bbox, text in iter_graphic_label_spans(source_page, regions):
                from scholar_translator.translation_failures import attempt_translation
                translated = attempt_translation(lambda:translate_table_cell_text(text,translator),
                    text,audit_records if audit_records is not None else [],page_index,bbox,"graphic")
                if translated is None:
                    continue
                if _paint_label_text(target_page, bbox, translated, font_file):
                    replacement_count += 1
    finally:
        source_doc.close()
        if replacement_count:
            target_doc.saveIncr()
        target_doc.close()

    return replacement_count
