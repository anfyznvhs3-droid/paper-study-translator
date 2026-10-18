import json

import pytest

from qdt.audit.checks import AuditIssue, audit_translation_output
from qdt.ingest.pdf import PdfDependencyError, classify_pdf, ingest_pdf
from qdt.memory import DomainAlreadyExists, DomainMemoryStore
from qdt.queue import FilledTranslationQueue, SourceBlock, TranslationQueue, TranslationQueueItem
from qdt.render.markdown import render_markdown


def test_domain_memory_store_creates_knowledge_base_files(tmp_path):
    domain = DomainMemoryStore(tmp_path).create_domain("Automotive Quality", "auto-quality")

    assert domain.slug == "auto-quality"
    assert domain.path == tmp_path / "auto-quality"
    assert json.loads((domain.path / "domain.json").read_text(encoding="utf-8")) == {
        "display_name": "Automotive Quality",
        "slug": "auto-quality",
    }
    for name in [
        "glossary.csv",
        "term-decisions.jsonl",
        "phrase-memory.jsonl",
        "review-rules.md",
        "rejected-terms.jsonl",
    ]:
        assert (domain.path / name).exists()


def test_domain_memory_store_blocks_duplicate_slug(tmp_path):
    store = DomainMemoryStore(tmp_path)
    store.create_domain("Automotive Quality", "auto-quality")

    with pytest.raises(DomainAlreadyExists):
        store.create_domain("Duplicate", "auto-quality")


def test_translation_queue_json_roundtrip_preserves_provenance(tmp_path):
    queue = TranslationQueue(
        items=[
            TranslationQueueItem(
                source=SourceBlock(
                    document_id="doc-1",
                    page_number=2,
                    block_id="p2-b4",
                    text="Supplier shall retain records.",
                    classifier="requirement",
                )
            )
        ]
    )
    path = tmp_path / "queue.json"

    queue.write_json(path)
    loaded = TranslationQueue.read_json(path)

    assert loaded.items[0].source.page_number == 2
    assert loaded.items[0].source.block_id == "p2-b4"
    assert loaded.items[0].source.text == "Supplier shall retain records."


def test_filled_translation_queue_json_roundtrip(tmp_path):
    filled = FilledTranslationQueue(
        items=[TranslationQueueItem(source=SourceBlock("doc-1", 1, "p1-b1", "Original"), korean="번역")]
    )
    path = tmp_path / "filled.json"

    filled.write_json(path)

    assert FilledTranslationQueue.read_json(path).items[0].korean == "번역"


def test_classify_pdf_uses_path_and_page_count_without_external_pdf(tmp_path):
    missing = tmp_path / "missing.pdf"

    assert classify_pdf(missing).kind == "missing"


def test_ingest_pdf_missing_dependency_error_is_actionable(monkeypatch, tmp_path):
    import qdt.ingest.pdf as pdf_module

    monkeypatch.setattr(pdf_module, "_fitz", None)

    with pytest.raises(PdfDependencyError, match="PyMuPDF"):
        ingest_pdf(tmp_path / "sample.pdf")


def test_render_markdown_mono_outputs_korean_by_page_only():
    filled = FilledTranslationQueue(
        items=[
            TranslationQueueItem(SourceBlock("doc", 1, "b1", "Original 1"), korean="한국어 1"),
            TranslationQueueItem(SourceBlock("doc", 2, "b2", "Original 2"), korean="한국어 2"),
        ]
    )

    assert render_markdown(filled, output_mode="mono") == (
        "## Page 1\n\n한국어 1\n\n## Page 2\n\n한국어 2\n"
    )


def test_render_markdown_dual_outputs_original_and_korean_sections():
    filled = FilledTranslationQueue(
        items=[TranslationQueueItem(SourceBlock("doc", 3, "b1", "Original"), korean="한국어")]
    )

    assert render_markdown(filled, output_mode="dual") == (
        "## Page 3\n\n### Original\n\nOriginal\n\n### Korean\n\n한국어\n"
    )


def test_audit_translation_output_detects_required_issues(tmp_path):
    output_path = tmp_path / "draft.md"
    output_path.write_text("번역 \ufffd\n[미번역]\n", encoding="utf-8")
    filled = FilledTranslationQueue(
        items=[
            TranslationQueueItem(SourceBlock("doc", 1, "b1", "Original"), korean=""),
            TranslationQueueItem(
                SourceBlock("doc", 1, "b2", "Google Translate Draft modal"),
                korean="Google Translate Draft modal",
            ),
        ]
    )

    issues = audit_translation_output(filled, output_path=output_path)

    assert AuditIssue("untranslated_marker", "Output contains [미번역].") in issues
    assert AuditIssue("replacement_character", "Output contains Unicode replacement character.") in issues
    assert AuditIssue("empty_translation", "Empty translation at page 1 block b1.") in issues
    assert AuditIssue(
        "google_translate_draft_modal",
        "Google Translate Draft modal-heavy content may require review.",
    ) in issues


def test_audit_translation_output_detects_missing_output_path(tmp_path):
    filled = FilledTranslationQueue(items=[])

    issues = audit_translation_output(filled, output_path=tmp_path / "missing.md")

    assert AuditIssue("missing_output_path", "Output path does not exist.") in issues
