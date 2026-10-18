from dataclasses import dataclass
from pathlib import Path

from qdt.queue import SourceBlock, TranslationQueue, TranslationQueueItem

try:
    import fitz as _fitz
except ImportError:
    _fitz = None


class PdfDependencyError(ImportError):
    """Raised when PDF ingest requires PyMuPDF but it is unavailable."""


@dataclass(frozen=True)
class PdfClassification:
    path: Path
    kind: str
    page_count: int = 0
    message: str | None = None


def classify_pdf(path: str | Path) -> PdfClassification:
    pdf_path = Path(path)
    if not pdf_path.exists():
        return PdfClassification(path=pdf_path, kind="missing", message="PDF path does not exist.")
    if _fitz is None:
        return PdfClassification(
            path=pdf_path,
            kind="dependency-missing",
            message="Install PyMuPDF to classify PDF page content.",
        )

    with _fitz.open(pdf_path) as document:
        page_count = len(document)
        has_text = any(page.get_text("text").strip() for page in document)
    return PdfClassification(path=pdf_path, kind="text" if has_text else "image", page_count=page_count)


def ingest_pdf(path: str | Path, document_id: str | None = None) -> TranslationQueue:
    if _fitz is None:
        raise PdfDependencyError("PyMuPDF is required for PDF ingest. Install the 'pymupdf' package.")

    pdf_path = Path(path)
    doc_id = document_id or pdf_path.stem
    items: list[TranslationQueueItem] = []
    with _fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                block = SourceBlock(
                    document_id=doc_id,
                    page_number=page_index,
                    block_id=f"p{page_index}-b1",
                    text=text,
                    classifier="pdf-text",
                )
                items.append(TranslationQueueItem(source=block))
    return TranslationQueue(items=items)

