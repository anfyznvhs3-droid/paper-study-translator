"""Functions that can be used for the most common use-cases for scholar-translator"""

import asyncio
from contextlib import ExitStack
from scholar_translator.file_safety import reserve_output_directory
import io
import os
import re
import sys
import tempfile
import logging
from asyncio import CancelledError
from pathlib import Path
from string import Template
from typing import Any, BinaryIO, List, Optional, Dict

import numpy as np
import requests
import tqdm
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfexceptions import PDFValueError
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pymupdf import Document, Font

from scholar_translator.converter import TranslateConverter
from scholar_translator.doclayout import OnnxModel
from scholar_translator.layout_policy import (
    reserved_layout_classes,
    should_translate_table_text,
)
from scholar_translator.pdfinterp import PDFPageInterpreterEx
from scholar_translator.graphic_overlay import (
    apply_graphic_text_overlays,
    should_overlay_graphic_text,
)
from scholar_translator.table_overlay import (
    apply_table_cell_overlays,
    should_overlay_table_cells,
)
from scholar_translator.translator import (
    BedrockTranslator,
    ClaudeCodeCliTranslator,
    CodexCliTranslator,
    GoogleTranslator,
    GeminiTranslator,
    OfflineTranslator,
)
from scholar_translator.audit import write_audit_file
from scholar_translator.image_ocr import apply_image_ocr
from scholar_translator.final_output import compose_dual, write_dual, final_native_review, repair_native_residuals

from scholar_translator.config import ConfigManager
from babeldoc.assets.assets import get_font_and_metadata

NOTO_NAME = "noto"

logger = logging.getLogger(__name__)

noto_list = [
    "am",  # Amharic
    "ar",  # Arabic
    "bn",  # Bengali
    "bg",  # Bulgarian
    "chr",  # Cherokee
    "el",  # Greek
    "gu",  # Gujarati
    "iw",  # Hebrew
    "hi",  # Hindi
    "kn",  # Kannada
    "ml",  # Malayalam
    "mr",  # Marathi
    "ru",  # Russian
    "sr",  # Serbian
    "ta",  # Tamil
    "te",  # Telugu
    "th",  # Thai
    "ur",  # Urdu
    "uk",  # Ukrainian
]


def check_files(files: List[str]) -> List[str]:
    files = [
        f for f in files if not f.startswith("http://")
    ]  # exclude online files, http
    files = [
        f for f in files if not f.startswith("https://")
    ]  # exclude online files, https
    missing_files = [file for file in files if not os.path.exists(file)]
    return missing_files


def translate_patch(
    inf: BinaryIO,
    pages: Optional[list[int]] = None,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_zh: Document = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    noto_name: str = "",
    noto: Font = None,
    callback: object = None,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    ignore_cache: bool = False,
    figure_regions: Optional[Dict] = None,
    review_records: Optional[list] = None,
    **kwarg: Any,
) -> None:
    rsrcmgr = PDFResourceManager()
    layout = {}
    device = TranslateConverter(
        rsrcmgr,
        vfont,
        vchar,
        thread,
        layout,
        lang_in,
        lang_out,
        service,
        noto_name,
        noto,
        envs,
        prompt,
        ignore_cache,
    )

    device.review_records = review_records if review_records is not None else []
    assert device is not None
    obj_patch = {}
    interpreter = PDFPageInterpreterEx(rsrcmgr, device, obj_patch)
    if pages:
        total_pages = len(pages)
    else:
        total_pages = doc_zh.page_count

    parser = PDFParser(inf)
    doc = PDFDocument(parser)
    with tqdm.tqdm(total=total_pages) as progress:
        for pageno, page in enumerate(PDFPage.create_pages(doc)):
            if cancellation_event and cancellation_event.is_set():
                raise CancelledError("task cancelled")
            if pages and (pageno not in pages):
                continue
            progress.update()
            if callback:
                callback(progress)
            page.pageno = pageno
            pix = doc_zh[page.pageno].get_pixmap()
            image = np.frombuffer(pix.samples, np.uint8).reshape(
                pix.height, pix.width, 3
            )[:, :, ::-1]
            page_layout = model.predict(image, imgsz=int(pix.height / 32) * 32)[0]
            # kdtree is not feasible; better to render directly as image, trading space for time
            box = np.ones((pix.height, pix.width))
            h, w = box.shape
            vcls = reserved_layout_classes(
                translate_table_text=should_translate_table_text(envs)
            )
            for i, d in enumerate(page_layout.boxes):
                if page_layout.names[int(d.cls)] not in vcls:
                    x0, y0, x1, y1 = d.xyxy.squeeze()
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    box[y0:y1, x0:x1] = i + 2
            for i, d in enumerate(page_layout.boxes):
                if page_layout.names[int(d.cls)] in vcls:
                    x0, y0, x1, y1 = d.xyxy.squeeze()
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    box[y0:y1, x0:x1] = 0
            if figure_regions is not None:
                # Capture the model's "figure"-class boxes here (it already ran)
                # so the graphic-label overlay reuses them instead of running the
                # ONNX model a second time. Page-normalized, top-left origin (NOT
                # the bottom-left flip used for the mask above) to match PyMuPDF
                # page coordinates the overlay uses.
                page_figures = []
                for d in page_layout.boxes:
                    if page_layout.names[int(d.cls)] != "figure":
                        continue
                    fx0, fy0, fx1, fy1 = (float(v) for v in d.xyxy.squeeze())
                    page_figures.append(
                        (fx0 / pix.width, fy0 / pix.height, fx1 / pix.width, fy1 / pix.height)
                    )
                if page_figures:
                    figure_regions[page.pageno] = page_figures
            layout[page.pageno] = box
            # Create a new xref to store the new instruction stream
            page.page_xref = doc_zh.get_new_xref()  # Hack: insert new xref for page
            doc_zh.update_object(page.page_xref, "<<>>")
            doc_zh.update_stream(page.page_xref, b"")
            doc_zh[page.pageno].set_contents(page.page_xref)
            interpreter.process_page(page)

    device.close()
    return obj_patch, device.translation_pairs


def translate_stream(
    stream: bytes,
    pages: Optional[list[int]] = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    ignore_cache: bool = False,
    figure_regions: Optional[Dict] = None,
    review_records: Optional[list] = None,
    **kwarg: Any,
):
    font_list = [("tiro", None)]

    font_path = download_remote_fonts(lang_out.lower())
    noto_name = NOTO_NAME
    noto = Font(noto_name, font_path)
    font_list.append((noto_name, font_path))

    doc_en = Document(stream=stream)
    stream = io.BytesIO()
    doc_en.save(stream)
    doc_zh = Document(stream=stream)
    page_count = doc_zh.page_count
    # font_list = [("GoNotoKurrent-Regular.ttf", font_path), ("tiro", None)]
    font_id = {}
    for page in doc_zh:
        for font in font_list:
            font_id[font[0]] = page.insert_font(font[0], font[1])
    xreflen = doc_zh.xref_length()
    for xref in range(1, xreflen):
        for label in ["Resources/", ""]:  # May be xobj-based resources
            try:  # xref read/write may fail
                font_res = doc_zh.xref_get_key(xref, f"{label}Font")
                target_key_prefix = f"{label}Font/"
                if font_res[0] == "xref":
                    resource_xref_id = re.search("(\\d+) 0 R", font_res[1]).group(1)
                    xref = int(resource_xref_id)
                    font_res = ("dict", doc_zh.xref_object(xref))
                    target_key_prefix = ""

                if font_res[0] == "dict":
                    for font in font_list:
                        target_key = f"{target_key_prefix}{font[0]}"
                        font_exist = doc_zh.xref_get_key(xref, target_key)
                        if font_exist[0] == "null":
                            doc_zh.xref_set_key(
                                xref,
                                target_key,
                                f"{font_id[font[0]]} 0 R",
                            )
            except Exception:
                pass

    fp = io.BytesIO()

    doc_zh.save(fp)
    obj_patch, translation_pairs = translate_patch(fp, **locals())

    for obj_id, ops_new in obj_patch.items():
        # ops_old=doc_en.xref_stream(obj_id)
        # print(obj_id)
        # print(ops_old)
        # print(ops_new.encode())
        doc_zh.update_stream(obj_id, ops_new.encode())

    doc_dual = compose_dual(doc_en, doc_zh)
    if not skip_subset_fonts:
        doc_zh.subset_fonts(fallback=True)
        doc_dual.subset_fonts(fallback=True)
    try:
        return (
            doc_zh.write(deflate=True, garbage=3, use_objstms=1),
            doc_dual.write(deflate=True, garbage=3, use_objstms=1),
            translation_pairs,
        )
    finally:
        doc_dual.close()


def convert_to_pdfa(input_path, output_path):
    """
    Convert PDF to PDF/A format

    Args:
        input_path: Path to source PDF file
        output_path: Path to save PDF/A file
    """
    from pikepdf import Dictionary, Name, Pdf

    # Open the PDF file
    pdf = Pdf.open(input_path)

    # Add PDF/A conformance metadata
    metadata = {
        "pdfa_part": "2",
        "pdfa_conformance": "B",
        "title": pdf.docinfo.get("/Title", ""),
        "author": pdf.docinfo.get("/Author", ""),
        "creator": "PDF Math Translate",
    }

    with pdf.open_metadata() as meta:
        meta.load_from_docinfo(pdf.docinfo)
        meta["pdfaid:part"] = metadata["pdfa_part"]
        meta["pdfaid:conformance"] = metadata["pdfa_conformance"]

    # Create OutputIntent dictionary
    output_intent = Dictionary(
        {
            "/Type": Name("/OutputIntent"),
            "/S": Name("/GTS_PDFA1"),
            "/OutputConditionIdentifier": "sRGB IEC61966-2.1",
            "/RegistryName": "http://www.color.org",
            "/Info": "sRGB IEC61966-2.1",
        }
    )

    # Add output intent to PDF root
    if "/OutputIntents" not in pdf.Root:
        pdf.Root.OutputIntents = [output_intent]
    else:
        pdf.Root.OutputIntents.append(output_intent)

    # Save as PDF/A
    pdf.save(output_path, linearize=True)
    pdf.close()


def translate(
    files: list[str],
    output: str = "",
    pages: Optional[list[int]] = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    thread: int = 0,
    vfont: str = "",
    vchar: str = "",
    callback: object = None,
    compatible: bool = False,
    cancellation_event: asyncio.Event = None,
    model: OnnxModel = None,
    envs: Dict = None,
    prompt: Template = None,
    skip_subset_fonts: bool = False,
    ignore_cache: bool = False,
    **kwarg: Any,
):
    if not files:
        raise PDFValueError("No files to process.")

    missing_files = check_files(files)

    if missing_files:
        print("The following files do not exist:", file=sys.stderr)
        for file in missing_files:
            print(f"  {file}", file=sys.stderr)
        raise PDFValueError("Some files do not exist.")

    result_files = []

    for file in files:
        with ExitStack() as owned:
            if type(file) is str and (
                file.startswith("http://") or file.startswith("https://")
            ):
                print("Online files detected, downloading...")
                try:
                    r = requests.get(file, allow_redirects=True, timeout=(5, 60))
                    if r.status_code == 200:
                        with tempfile.NamedTemporaryFile(
                            suffix=".pdf", delete=False
                        ) as tmp_file:
                            print(f"Writing the file: {file}...")
                            tmp_file.write(r.content)
                            file = tmp_file.name
                            owned.callback(Path(file).unlink, missing_ok=True)
                    else:
                        r.raise_for_status()
                except Exception as e:
                    raise PDFValueError(
                        f"Errors occur in downloading the PDF file. Please check the link(s).\nError:\n{e}"
                    )
            filename = os.path.splitext(os.path.basename(file))[0]

            # If the commandline has specified converting to PDF/A format
            # --compatible / -cp
            if compatible:
                with tempfile.NamedTemporaryFile(suffix="-pdfa.pdf", delete=False) as tmp_pdfa:
                    converted_path = Path(tmp_pdfa.name)
                owned.callback(converted_path.unlink, missing_ok=True)
                convert_to_pdfa(file, str(converted_path))
                s_raw = converted_path.read_bytes()
            else:
                s_raw = Path(file).read_bytes()

            # Captured by the converter (translate_patch) while it already runs the
            # layout model per page, so the figure-label overlay reuses those boxes
            # instead of re-running the ONNX model a second time. Passed by reference
            # via **locals() and filled in place.
            figure_regions: Dict[int, list] = {}
            review_records = []
            s_mono, s_dual, translation_pairs = translate_stream(
                s_raw,
                **locals(),
            )

            # Determine base output directory
            if output:
                base_output = Path(output)
            else:
                base_output = Path.cwd()  # Use current working directory

            # Reserve a fresh directory. Existing results are never overwritten.
            output_dir = reserve_output_directory(base_output, f"{filename}-{lang_out}")

            file_mono = output_dir / f"{filename}-{lang_out}-mono.pdf"
            file_dual = output_dir / f"{filename}-{lang_out}-dual.pdf"
            doc_mono = open(file_mono, "xb")
            doc_mono.write(s_mono)
            doc_mono.close()

            final_records = review_records
            selected_pages = set(pages) if pages else None
            if should_overlay_table_cells(envs):
                table_translator = _build_table_overlay_translator(
                    service,
                    lang_in,
                    lang_out,
                    envs,
                    prompt,
                    ignore_cache,
                )
                table_overlay_count = apply_table_cell_overlays(
                    file,
                    file_mono,
                    table_translator,
                    download_remote_fonts(lang_out.lower()),
                    audit_records=final_records,
                    pages=selected_pages,
                )
                if table_overlay_count:
                    logger.info("Applied %s table cell overlays: %s", table_overlay_count, file_mono)

            if should_overlay_graphic_text(envs):
                if figure_regions:
                    graphic_translator = _build_table_overlay_translator(
                        service,
                        lang_in,
                        lang_out,
                        envs,
                        prompt,
                        ignore_cache,
                    )
                    graphic_overlay_count = apply_graphic_text_overlays(
                        file,
                        file_mono,
                        graphic_translator,
                        figure_regions,
                        download_remote_fonts(lang_out.lower()),
                        audit_records=final_records,
                    )
                    if graphic_overlay_count:
                        logger.info(
                            "Applied %s figure label overlays: %s",
                            graphic_overlay_count,
                            file_mono,
                        )

            # Finish raster labels before composing the final DUAL spread.
            ocr_translator = _build_table_overlay_translator(service, lang_in, lang_out, envs, prompt, ignore_cache)
            final_records.extend(apply_image_ocr(file, file_mono, ocr_translator,
                download_remote_fonts(lang_out.lower()), envs, selected_pages))
            final_records.extend(repair_native_residuals(file, file_mono, ocr_translator,
                download_remote_fonts(lang_out.lower()), selected_pages))
            final_records.extend(final_native_review(file, file_mono, selected_pages))
            write_dual(file, file_mono, file_dual)
            # Both selected output modes carry the same final review evidence.
            for output_pdf in (file_mono, file_dual):
                audit_path = write_audit_file(output_pdf, translation_pairs, final_records)
                logger.info(f"Layout audit written: {audit_path}")

            result_files.append((str(file_mono), str(file_dual)))

    return result_files


def _build_table_overlay_translator(
    service: str,
    lang_in: str,
    lang_out: str,
    envs: Dict | None,
    prompt: Template | None,
    ignore_cache: bool,
):
    param = service.split(":", 1)
    service_name = param[0]
    service_model = param[1] if len(param) > 1 else None
    for translator in [GoogleTranslator, GeminiTranslator, BedrockTranslator, OfflineTranslator, CodexCliTranslator, ClaudeCodeCliTranslator]:
        if service_name == translator.name:
            return translator(lang_in, lang_out, service_model, envs=envs or {}, prompt=prompt, ignore_cache=ignore_cache)
    raise ValueError("Unsupported translation service")


def download_remote_fonts(lang: str):
    lang = lang.lower()
    LANG_NAME_MAP = {
        **{la: "GoNotoKurrent-Regular.ttf" for la in noto_list},
        **{
            la: f"SourceHanSerif{region}-Regular.ttf"
            for region, langs in {
                "CN": ["zh-cn", "zh-hans", "zh"],
                "TW": ["zh-tw", "zh-hant"],
                "JP": ["ja"],
                "KR": ["ko"],
            }.items()
            for la in langs
        },
    }
    font_name = LANG_NAME_MAP.get(lang, "GoNotoKurrent-Regular.ttf")
    bundled = Path(os.environ.get("QDT_BUNDLED_ASSETS", "")) / font_name
    if bundled.is_file():
        return str(bundled)

    # docker
    font_path = ConfigManager.get("NOTO_FONT_PATH", Path("/app", font_name).as_posix())
    if not Path(font_path).exists():
        font_path, _ = get_font_and_metadata(font_name)
        font_path = font_path.as_posix()

    logger.info(f"use font: {font_path}")

    return font_path
