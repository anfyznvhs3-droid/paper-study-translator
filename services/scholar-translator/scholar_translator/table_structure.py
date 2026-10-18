from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TableCellRole(str, Enum):
    HEADER = "header"
    VALUE = "value"
    UNIT = "unit"
    IDENTIFIER = "identifier"
    MIXED = "mixed"


@dataclass(frozen=True)
class TableCellDecision:
    role: TableCellRole
    translated_text: str | None
    preserve_original: bool


UNIT_VALUES = {
    "%",
    "a",
    "hz",
    "j",
    "ka",
    "kj",
    "kn",
    "mm",
    "ms",
    "v",
}

IDENTIFIER_RE = re.compile(r"(?:[A-Z]{2,}\d*|[A-Z]+[a-z]*\d+|V\d+(?:/[A-Z0-9]+)*)")
SPACED_IDENTIFIER_RE = re.compile(r"[A-Z]{1,4}\s+\d{1,4}", re.IGNORECASE)
NUMERIC_VALUE_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:\s*(?:%|hz|j|ka|kj|kn|mm|ms|v))?", re.IGNORECASE)

HEADER_TRANSLATIONS = {
    "average current": "평균 전류",
    "break": "휴지",
    "characteristic parameters": "특성 매개변수",
    "current": "전류",
    "down": "하강",
    "down-slope": "하강 기울기",
    "electrode pressure": "전극 가압력",
    "energy": "에너지",
    "file name": "파일명",
    "force": "하중",
    "gap": "간격",
    "main current period time": "주전류 구간 시간",
    "mcpt-main current period time": "MCPT-주전류 구간 시간",
    "other information": "기타 정보",
    "series name": "시리즈명",
    "slope": "기울기",
    "technology cycle parameters": "기술/사이클 매개변수",
    "time": "시간",
    "total current flow time": "총 전류 통전 시간",
    "up": "상승",
    "up-slope": "상승 기울기",
    "variant no.": "변형 번호",
    "variant no": "변형 번호",
    "weld rupture force": "용접부 파단 하중",
}


def classify_table_cell(text: str) -> TableCellDecision:
    normalized = normalize_table_cell(text)
    lower = normalized.casefold()

    if not normalized:
        return TableCellDecision(TableCellRole.VALUE, None, True)

    if lower in HEADER_TRANSLATIONS:
        return TableCellDecision(TableCellRole.HEADER, HEADER_TRANSLATIONS[lower], False)

    if _is_unit_cell(lower):
        return TableCellDecision(TableCellRole.UNIT, None, True)

    if _is_value_cell(normalized):
        return TableCellDecision(TableCellRole.VALUE, None, True)

    if _is_identifier_cell(normalized):
        return TableCellDecision(TableCellRole.IDENTIFIER, None, True)

    translated = _translate_compound_header(normalized)
    if translated:
        return TableCellDecision(TableCellRole.HEADER, translated, False)

    return TableCellDecision(TableCellRole.MIXED, None, False)


def normalize_table_cell(text: str) -> str:
    return " ".join(text.replace("\x00", "").split()).strip()


def lookup_table_cell_override(text: str) -> str | None:
    decision = classify_table_cell(text)
    return decision.translated_text


def should_preserve_table_cell(text: str) -> bool:
    return classify_table_cell(text).preserve_original


def _is_unit_cell(lower: str) -> bool:
    return lower in UNIT_VALUES


def _is_value_cell(text: str) -> bool:
    parts = text.split()
    if not parts:
        return False
    return all(NUMERIC_VALUE_RE.fullmatch(part) for part in parts)


def _is_identifier_cell(text: str) -> bool:
    stripped = text.strip()
    if re.fullmatch(r"[A-Z]", stripped):
        return True
    if SPACED_IDENTIFIER_RE.fullmatch(stripped):
        return True
    if " " in stripped:
        return False
    return bool(IDENTIFIER_RE.fullmatch(stripped))


def _looks_like_prose(text: str) -> bool:
    """True for sentence-like body text that must not be treated as a table cell.

    HEADER_TRANSLATIONS keys are short, generic words ("time", "current", "up",
    "down", "break"). The compound-header path replaces them as unanchored
    substrings, so applied to a body paragraph it matches incidental letters,
    returns a non-None "translation", and short-circuits real agent translation
    via the override path in the converter. Table headers are short; prose is not.
    """
    normalized = " ".join(text.split())
    if len(normalized.split()) > 6:
        return True
    if re.search(r"[.!?]\s+\S", normalized):  # contains more than one sentence
        return True
    return False


def _replace_header_tokens(text: str, mapping: dict[str, str]) -> str:
    """Substitute mapping keys as whole tokens, never spliced inside a word.

    Letter-adjacency lookarounds keep a short generic key ("up", "time") from
    matching inside a longer word ("setUP" -> "set상승", "UPdated" -> "상승dated");
    adjacency to digits / hyphens / dots / spaces still matches genuine header
    tokens ("up-slope", "variant no."). Longest keys first so a multi-word key
    wins over its sub-words. Shared by both header-override paths so neither can
    reintroduce the intra-word splice.
    """
    for source, target in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"(?<![A-Za-z])" + re.escape(source) + r"(?![A-Za-z])"
        text = re.sub(pattern, target, text, flags=re.IGNORECASE)
    return text


KEY_LINE_REPLACEMENTS = {
    "MCPT-main current period time": "MCPT-주전류 구간 시간",
    "TCFT-Total current flow time": "TCFT-총 전류 통전 시간",
    "green color-OK": "녹색-OK",
    "light red NOK": "연한 빨간색-NOK",
    "orange color-normal/ typical parameters": "주황색-정상/일반 매개변수",
    "orange color-BWK": "주황색-BWK",
}


def _translate_compound_header(text: str) -> str | None:
    lower = text.casefold()
    if lower.startswith("key:"):
        return _translate_key_line(text)

    if _looks_like_prose(text):
        return None

    translated = _replace_header_tokens(text, HEADER_TRANSLATIONS)
    return translated if translated != text else None


def _translate_key_line(text: str) -> str:
    translated = _replace_header_tokens(text, KEY_LINE_REPLACEMENTS)
    translated = re.sub(r"^Key:", "키:", translated, flags=re.IGNORECASE)
    return translated
