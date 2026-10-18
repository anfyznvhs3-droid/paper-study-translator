from __future__ import annotations

import logging
import os
import statistics
from pathlib import Path
from typing import Any

import fitz

from scholar_translator.table_structure import (
    lookup_table_cell_override,
    should_preserve_table_cell,
)

logger = logging.getLogger(__name__)


def should_overlay_table_cells(envs: dict | None = None) -> bool:
    raw = (envs or {}).get("QDT_TABLE_CELL_OVERLAY", os.environ.get("QDT_TABLE_CELL_OVERLAY"))
    if raw is None:
        return True
    return str(raw).strip().casefold() not in {"0", "false", "off", "no"}


def translate_table_cell_text(text: str, translator: Any) -> str | None:
    normalized = " ".join(str(text).replace("\n", " ").split()).strip()
    if not normalized or should_preserve_table_cell(normalized):
        return None

    override = lookup_table_cell_override(normalized)
    if override:
        return override

    translated = translator.translate(normalized)
    translated = " ".join(str(translated).split()).strip()
    if not translated or translated == normalized:
        return None
    return translated


def apply_table_cell_overlays(
    source_pdf: str | Path,
    target_pdf: str | Path,
    translator: Any,
    font_file: str | None = None,
    audit_records: list | None = None,
    pages: set[int] | None = None,
) -> int:
    source_doc = fitz.open(source_pdf)
    target_doc = fitz.open(target_pdf)
    replacement_count = 0
    try:
        page_count = min(source_doc.page_count, target_doc.page_count)
        for page_index in range(page_count):
            if pages is not None and page_index not in pages:
                continue
            source_page = source_doc[page_index]
            target_page = target_doc[page_index]
            try:
                tables = source_page.find_tables().tables
            except Exception:
                logger.exception("Failed to find tables on page %s", page_index + 1)
                continue

            for table in tables:
                rows = table.extract()
                for row_index, row in enumerate(rows):
                    table_row = table.rows[row_index]
                    for col_index, text in enumerate(row):
                        if text is None or col_index >= len(table_row.cells):
                            continue
                        cell_rect = table_row.cells[col_index]
                        if cell_rect is None:
                            continue
                        from scholar_translator.translation_failures import attempt_translation
                        translated = attempt_translation(lambda:translate_table_cell_text(text,translator),
                            text,audit_records if audit_records is not None else [],page_index,cell_rect,"table")
                        if translated is None:
                            continue
                        from scholar_translator.image_ocr import background_color
                        rect=fitz.Rect(cell_rect)
                        background=background_color(source_page, rect+ (2,2,-2,-2))
                        spans=[span for block in source_page.get_text("dict",clip=rect)["blocks"]
                               if block.get("type")==0 for line in block["lines"] for span in line["spans"]]
                        sizes=[span["size"] for span in spans if span["text"].strip()]
                        size=statistics.median(sizes) if sizes else 11
                        color=fitz.sRGB_to_pdf(spans[0]["color"]) if spans else (0,0,0)
                        fitted=background is not None and _paint_cell_text(
                            target_page, rect, translated, font_file, row_index == 0,
                            size, background, color)
                        if fitted:
                            replacement_count += 1
                        if audit_records is not None:
                            audit_records.append({"page":page_index,"kind":"table_overlay",
                                "source_text":text,"translated_text":translated,"bbox":list(rect),
                                "fitted":bool(fitted),"status":"candidate" if fitted else "open",
                                "reason":"표 셀의 번역과 배치를 확인하세요." if fitted else "표 셀의 배경 또는 글자 공간을 안전하게 보정하지 못했습니다."})
    finally:
        source_doc.close()
        if replacement_count:
            target_doc.saveIncr()
        target_doc.close()

    return replacement_count


def _paint_cell_text(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    font_file: str | None,
    strong: bool,
    source_size: float = 11,
    background: tuple = (1,1,1),
    foreground: tuple = (0.03,0.03,0.03),
) -> bool:
    # Match the source font and cell background. Commit only a fitting result,
    # leaving all existing content intact if no readable layout fits.
    inner = fitz.Rect(rect.x0+3,rect.y0+2,rect.x1-3,rect.y1-2)
    if inner.is_empty or inner.width<4 or inner.height<4:
        return False
    base=max(7,min(28,source_size))
    kwargs={"color":foreground,"align":fitz.TEXT_ALIGN_LEFT,
            "fontname":"qdt_table_overlay" if font_file else "helv","lineheight":1.2}
    if font_file:
        kwargs["fontfile"]=font_file
    for factor in (1,.95,.9,.85,.8,.75,.7):
        size=base*factor
        if size<max(6,base*.7):continue
        shape=page.new_shape()
        shape.draw_rect(rect+(1,1,-1,-1))
        shape.finish(color=None,fill=background)
        if shape.insert_textbox(inner,text,fontsize=size,**kwargs)>=0:
            shape.commit(overlay=True)
            return True
    return False
