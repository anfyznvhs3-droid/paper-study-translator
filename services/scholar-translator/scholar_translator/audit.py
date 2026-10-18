"""Layout audit generator for scholar-translator output.

Generates .layout-audit.json files compatible with the unified ReviewItem schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ReviewItem:
    """Unified review item matching packages/schemas/review-item.schema.json."""

    page: int
    kind: str
    severity: str
    source_text: str
    translated_text: Optional[str] = None
    reason: str = ""
    status: str = "open"
    fitted: Optional[bool] = None


@dataclass
class PageAudit:
    page: int
    replacements: list[dict] = field(default_factory=list)


# Domain-specific term checks
TERM_CHECKS: list[tuple[str, str, str]] = [
    ("shall", "modal_misuse", "shall 표현은 의무 요구사항입니다. 번역을 확인하세요."),
    ("must", "modal_misuse", "must 표현은 강한 의무입니다. 번역을 확인하세요."),
    ("should", "modal_misuse", "should 표현은 권고입니다. shall과 구분하세요."),
    ("may", "modal_misuse", "may 표현은 허용입니다. can과 구분하세요."),
    ("failure mode", "term_mismatch", "FMEA 용어: '고장 형태'로 번역해야 합니다."),
    ("field issues", "term_mismatch", "도메인 용어: '현장 이슈'로 번역해야 합니다."),
]

# Residual English pattern (Korean text with significant English left)
RESIDUAL_ENG_PATTERN = re.compile(r"[A-Za-z]{4,}")
ENGLISH_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
UNTRANSLATED_SOURCE_SENTENCE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z'-]*(?:[\s,;:\-()]+[A-Za-z][A-Za-z'-]*){7,}\b"
)
ACRONYM_EXPLANATION_RESIDUAL_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9-]{2,}\b"
    r"(?:\s*\([A-Za-z][^)]+\))?"
    r"\s+(?:is|are|was|were|means|refers|uses|used|helps|can|may|should|will|has|have)\b"
    r"(?:[^.!?]*\b[A-Za-z][A-Za-z'-]*\b){4,}"
)
SCHOLARLY_ARTIFACT_PATTERNS = [
    re.compile(r"오\s*f", re.IGNORECASE),
    re.compile(r"\b[에이비씨디]\b"),
    re.compile(r"h\s*t\s*t\s*p|d\s*o\s*i|1\s*0\s*\.\s*1\s*0\s*0\s*7", re.IGNORECASE),
]
SCHOLARLY_HEADING_TRANSLATIONS = {
    "abstract": {"초록", "요약"},
}
SCHOLARLY_HEADING_MISTRANSLATIONS = {
    "abstract": {"추상", "추상적인"},
}


def _check_term_rules(source: str, translated: str) -> list[ReviewItem]:
    """Check source/translated pair against domain term rules."""
    items: list[ReviewItem] = []
    source_lower = source.lower()

    for term, kind, reason in TERM_CHECKS:
        if term in source_lower:
            # Check if the term is properly translated
            if _is_term_mistranslated(term, translated):
                items.append(
                    ReviewItem(
                        page=0,  # Will be set by caller
                        kind=kind,
                        severity="warning",
                        source_text=source[:200],
                        translated_text=translated[:200] if translated else None,
                        reason=reason,
                        status="open",
                    )
                )
    return items


def _is_term_mistranslated(term: str, translated: str) -> bool:
    """Check if a term is likely mistranslated."""
    if not translated:
        return True

    # Simple heuristic: if the English term appears in the translation, it's likely not translated
    if term.lower() in translated.lower():
        return True

    return False


def _check_residual_english(translated: str, source: str) -> list[ReviewItem]:
    """Check for residual English in Korean translation."""
    items: list[ReviewItem] = []

    if not translated:
        return items

    # Find English words in translation
    eng_words = RESIDUAL_ENG_PATTERN.findall(translated)

    # Filter out words that are also in the source (might be proper nouns, abbreviations)
    source_words = set(RESIDUAL_ENG_PATTERN.findall(source))
    residual = [w for w in eng_words if w not in source_words and len(w) > 3]

    if len(residual) >= 3:
        items.append(
            ReviewItem(
                page=0,
                kind="residual_english",
                severity="warning",
                source_text=source[:200],
                translated_text=translated[:200],
                reason=f"번역문에 영어 단어 {len(residual)}개가 남아있습니다: {', '.join(residual[:5])}",
                status="open",
            )
        )

    return items


def _source_contains_english_phrase(source: str, phrase: str, *, min_words: int) -> bool:
    """Return whether a long English phrase in the translation came from source."""
    source_words = [word.lower() for word in ENGLISH_WORD_PATTERN.findall(source)]
    phrase_words = [word.lower() for word in ENGLISH_WORD_PATTERN.findall(phrase)]
    if len(phrase_words) < min_words:
        return False

    return " ".join(phrase_words) in " ".join(source_words)


def _check_untranslated_source_sentences(source: str, translated: str) -> list[ReviewItem]:
    """Flag source English sentences that survived inside the Korean translation."""
    if not translated:
        return []

    items: list[ReviewItem] = []
    from scholar_translator.final_output import needs_english_translation
    if " ".join(source.split()).casefold() == " ".join(translated.split()).casefold() and needs_english_translation(source):
        return [ReviewItem(page=0,kind="untranslated_source_sentence",severity="error",
            source_text=source[:200],translated_text=translated[:200],
            reason="짧은 제목 또는 문장이 원문 영어 그대로 남았습니다.",status="open")]
    for match in ACRONYM_EXPLANATION_RESIDUAL_PATTERN.finditer(translated):
        phrase = match.group(0).strip()
        if _source_contains_english_phrase(source, phrase, min_words=7):
            items.append(
                ReviewItem(
                    page=0,
                    kind="acronym_explanation_residual",
                    severity="error",
                    source_text=source[:200],
                    translated_text=translated[:200],
                    reason=(
                        "약어/도메인 용어는 보존할 수 있지만, 약어 뒤 설명 문장이 영어로 남았습니다. "
                        "약어만 보존하고 설명문은 번역하세요."
                    ),
                    status="open",
                )
            )
            return items

    for match in UNTRANSLATED_SOURCE_SENTENCE_PATTERN.finditer(translated):
        phrase = match.group(0).strip()
        if _source_contains_english_phrase(source, phrase, min_words=8):
            items.append(
                ReviewItem(
                    page=0,
                    kind="untranslated_source_sentence",
                    severity="error",
                    source_text=source[:200],
                    translated_text=translated[:200],
                    reason="원문 영어 문장이 번역문에 그대로 남았습니다. 해당 문장을 한국어 번역 대상으로 검수하세요.",
                    status="open",
                )
            )
            return items

    return items


def _check_scholarly_heading_translation(source: str, translated: str) -> list[ReviewItem]:
    """Flag common scholarly section headings translated as ordinary adjectives."""
    source_key = source.strip().strip(":：").casefold()
    translated_key = translated.strip().strip(":：")
    if source_key not in SCHOLARLY_HEADING_TRANSLATIONS:
        return []
    if translated_key in SCHOLARLY_HEADING_TRANSLATIONS[source_key]:
        return []
    if translated_key in SCHOLARLY_HEADING_MISTRANSLATIONS.get(source_key, set()):
        return [
            ReviewItem(
                page=0,
                kind="scholarly_heading_mistranslation",
                severity="warning",
                source_text=source[:200],
                translated_text=translated[:200],
                reason="논문 섹션 헤딩 Abstract는 형용사 '추상적인'이 아니라 '초록'으로 번역해야 합니다.",
                status="open",
            )
        ]
    return []


def _check_scholarly_pdf_artifacts(source: str, translated: str) -> list[ReviewItem]:
    """Flag PDF extraction/translation artifacts common in scholarly papers."""
    if not translated:
        return []

    if any(pattern.search(translated) for pattern in SCHOLARLY_ARTIFACT_PATTERNS):
        return [
            ReviewItem(
                page=0,
                kind="scholarly_pdf_artifact",
                severity="error",
                source_text=source[:200],
                translated_text=translated[:200],
                reason=(
                    "논문 PDF 레이아웃/문자 추출 잔재가 번역문에 남았습니다. "
                    "표 라벨, DOI/URL, Conflict of interest 문구를 원문과 대조하세요."
                ),
                status="open",
            )
        ]

    if "doi.org" in source.lower() and "doi.org" not in translated.lower():
        return [
            ReviewItem(
                page=0,
                kind="scholarly_pdf_artifact",
                severity="error",
                source_text=source[:200],
                translated_text=translated[:200],
                reason="원문의 DOI/URL이 번역문에서 보존되지 않았습니다.",
                status="open",
            )
        ]

    return []


def generate_review_items(
    page: int,
    source: str,
    translated: str,
) -> list[dict]:
    """Generate review items for a source/translated pair.

    Returns list of review item dicts matching the unified schema.
    """
    items: list[ReviewItem] = []

    # Skip empty or formula-only content
    if not source.strip() or re.match(r"^\{v\d+\}$", source.strip()):
        return []

    # Scholarly section headings are short, so they need explicit checks.
    items.extend(_check_scholarly_heading_translation(source, translated))

    # Exact source-sentence residuals must take priority over softer term warnings.
    items.extend(_check_untranslated_source_sentences(source, translated))

    # Term checks
    items.extend(_check_term_rules(source, translated))

    # Residual English check
    items.extend(_check_residual_english(translated, source))

    # Scholarly PDF extraction artifacts
    items.extend(_check_scholarly_pdf_artifacts(source, translated))

    # Set page number for all items
    result = []
    for item in items:
        d = asdict(item)
        d["page"] = page
        # Remove None values for cleaner JSON
        d = {k: v for k, v in d.items() if v is not None}
        result.append(d)

    return result


def build_audit_json(
    page_audits: list[PageAudit],
) -> dict:
    """Build the complete audit JSON structure."""
    pages = []
    total_needs_review = 0

    for audit in page_audits:
        page_data = {
            "page": audit.page,
            "replacements": audit.replacements,
        }
        pages.append(page_data)
        total_needs_review += sum(
            1 for r in audit.replacements if r.get("status") == "open"
        )

    return {
        "summary": {
            "total_replacements": sum(len(a.replacements) for a in page_audits),
            "needs_review_count": total_needs_review,
            "status": "ok" if total_needs_review == 0 else "needs_review",
        },
        "pages": pages,
    }


def write_audit_file(
    output_path: Path,
    page_pairs: list[tuple[int, list[tuple[str, str]]]],
    final_records: list[dict] | None = None,
) -> Path:
    """Write layout audit JSON file.

    Args:
        output_path: Path to write the audit file
        page_pairs: List of (page_number, [(source, translated), ...])

    Returns:
        Path to the written audit file
    """
    page_audits: list[PageAudit] = []

    for page_num, pairs in page_pairs:
        audit = PageAudit(page=page_num + 1)
        for source, translated in pairs:
            review_items = generate_review_items(page_num, source, translated)

            replacement = {
                "source_preview": source[:200],
                "translated_preview": translated[:200] if translated else "",
                "fitted": None,  # fit is unknown until measured
                "status": "open" if review_items else "candidate",
                "reason": review_items[0]["reason"] if review_items else "원문과 번역문을 비교하세요.",
            }

            # Add kind and severity if review items exist
            if review_items:
                replacement["kind"] = review_items[0]["kind"]
                replacement["severity"] = review_items[0]["severity"]

            audit.replacements.append(replacement)

        page_audits.append(audit)

    for record in final_records or []:
        number=record["page"] + 1
        audit=next((a for a in page_audits if a.page==number),None)
        if audit is None:
            audit=PageAudit(page=number);page_audits.append(audit)
        audit.replacements.append({**record,"source_preview":record.get("source_text",""),
            "translated_preview":record.get("translated_text","")})
    audit_json = build_audit_json(page_audits)
    audit_json["scope"] = "translation pairs + final native PDF visibility + raster OCR"


    # Write with .layout-audit.json suffix
    audit_path = output_path.with_suffix(".layout-audit.json")
    audit_path.write_text(json.dumps(audit_json, ensure_ascii=False, indent=2), encoding="utf-8")

    return audit_path
