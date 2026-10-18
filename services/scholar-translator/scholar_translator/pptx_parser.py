"""PPTX parser for extracting text boxes with position info.

Extracts text from .pptx files while preserving:
- Text box positions (x, y, width, height)
- Slide number
- Image references (kept as-is)
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

# PPTX XML namespaces
NSMAP = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


@dataclass
class TextBox:
    """A text box extracted from PPTX with position info."""

    slide: int
    shape_id: str
    text: str
    x: int  # EMU (English Metric Units) - 1 inch = 914400 EMU
    y: int
    width: int
    height: int
    font_size: Optional[float] = None


@dataclass
class SlideData:
    """Data extracted from a single slide."""

    slide_number: int
    text_boxes: list[TextBox] = field(default_factory=list)
    image_rids: list[str] = field(default_factory=list)


@dataclass
class PptxData:
    """All data extracted from a PPTX file."""

    slides: list[SlideData] = field(default_factory=list)
    total_text_boxes: int = 0

    @property
    def all_text_boxes(self) -> list[TextBox]:
        """Get all text boxes across all slides."""
        result = []
        for slide in self.slides:
            result.extend(slide.text_boxes)
        return result


def _parse_position(sp: ET.Element) -> tuple[int, int, int, int]:
    """Extract position (x, y, width, height) from a shape element."""
    sp_pr = sp.find(".//p:spPr", NSMAP)
    if sp_pr is None:
        sp_pr = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}spPr")
    if sp_pr is None:
        return (0, 0, 0, 0)

    xfrm = sp_pr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm")
    if xfrm is None:
        return (0, 0, 0, 0)

    off = xfrm.find("{http://schemas.openxmlformats.org/drawingml/2006/main}off")
    ext = xfrm.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ext")

    x = int(off.get("x", 0)) if off is not None else 0
    y = int(off.get("y", 0)) if off is not None else 0
    cx = int(ext.get("cx", 0)) if ext is not None else 0
    cy = int(ext.get("cy", 0)) if ext is not None else 0

    return (x, y, cx, cy)


def _extract_text_from_tx_body(tx_body: ET.Element) -> str:
    """Extract text from a txBody element."""
    texts = []
    for p in tx_body.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}p"):
        p_texts = []
        for r in p.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}r"):
            t = r.find("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
            if t is not None and t.text:
                p_texts.append(t.text)
        # Also check for <a:t> directly under <a:p>
        if not p_texts:
            for t in p.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
                if t.text:
                    p_texts.append(t.text)
        if p_texts:
            texts.append("".join(p_texts))
    return "\n".join(texts)


def _get_font_size(sp: ET.Element) -> Optional[float]:
    """Try to extract font size from shape properties."""
    for rPr in sp.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}rPr"):
        sz = rPr.get("sz")
        if sz:
            try:
                return int(sz) / 100  # PPTX stores font size in hundredths of a point
            except ValueError:
                pass
    return None


def _extract_slide_images(slide_xml: ET.Element) -> list[str]:
    """Extract image relationship IDs from a slide."""
    rids = []
    for blip in slide_xml.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
        rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
        if rid:
            rids.append(rid)
    return rids


def parse_slide(slide_xml: bytes, slide_number: int) -> SlideData:
    """Parse a single slide XML and extract text boxes."""
    root = ET.fromstring(slide_xml)
    slide_data = SlideData(slide_number=slide_number)

    # Extract images
    slide_data.image_rids = _extract_slide_images(root)

    # Extract text boxes
    for sp in root.findall(".//{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
        # Check if it's a text box (has txBody)
        tx_body = sp.find("{http://schemas.openxmlformats.org/drawingml/2006/main}txBody")
        if tx_body is None:
            continue

        text = _extract_text_from_tx_body(tx_body)
        if not text.strip():
            continue

        # Get shape ID
        nvSpPr = sp.find("{http://schemas.openxmlformats.org/presentationml/2006/main}nvSpPr")
        if nvSpPr is None:
            nvSpPr = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}nvSpPr")

        cNvPr = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")
        shape_id = cNvPr.get("id", "unknown") if cNvPr is not None else "unknown"

        # Get position
        x, y, width, height = _parse_position(sp)

        # Get font size
        font_size = _get_font_size(sp)

        text_box = TextBox(
            slide=slide_number,
            shape_id=shape_id,
            text=text,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
        )
        slide_data.text_boxes.append(text_box)

    return slide_data


def parse_pptx(pptx_path: Path) -> PptxData:
    """Parse a PPTX file and extract all text boxes with position info.

    Args:
        pptx_path: Path to the .pptx file

    Returns:
        PptxData with all extracted text boxes
    """
    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

    pptx_data = PptxData()

    with zipfile.ZipFile(pptx_path, "r") as zf:
        # Find all slide files
        slide_files = sorted(
            [f for f in zf.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")],
            key=lambda x: int(x.split("slide")[1].split(".xml")[0])
        )

        for slide_file in slide_files:
            slide_number = int(slide_file.split("slide")[1].split(".xml")[0])
            slide_xml = zf.read(slide_file)
            slide_data = parse_slide(slide_xml, slide_number)
            pptx_data.slides.append(slide_data)
            pptx_data.total_text_boxes += len(slide_data.text_boxes)

    return pptx_data


def replace_text_in_pptx(
    pptx_path: Path,
    output_path: Path,
    translations: dict[int, dict[str, str]],
) -> Path:
    """Replace text in PPTX file with translations.

    Args:
        pptx_path: Path to the input .pptx file
        output_path: Path to write the translated .pptx file
        translations: Dict of {slide_number: {original_text: translated_text}}

    Returns:
        Path to the output file
    """
    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX file not found: {pptx_path}")

    with zipfile.ZipFile(pptx_path, "r") as zf_in:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                data = zf_in.read(item.filename)

                # Process slide files
                if item.filename.startswith("ppt/slides/slide") and item.filename.endswith(".xml"):
                    slide_number = int(item.filename.split("slide")[1].split(".xml")[0])
                    if slide_number in translations:
                        data = _replace_text_in_slide_xml(data, translations[slide_number])

                zf_out.writestr(item, data)

    return output_path


def _replace_text_in_slide_xml(slide_xml: bytes, translations: dict[str, str]) -> bytes:
    """Replace text in a slide XML with translations."""
    root = ET.fromstring(slide_xml)

    for t_elem in root.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
        if t_elem.text and t_elem.text.strip():
            original = t_elem.text.strip()
            if original in translations:
                t_elem.text = translations[original]

    return ET.tostring(root, encoding="unicode", xml_declaration=True).encode("utf-8")
