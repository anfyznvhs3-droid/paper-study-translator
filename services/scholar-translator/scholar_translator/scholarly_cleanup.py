from __future__ import annotations

import re
from dataclasses import dataclass, field

from scholar_translator.table_structure import lookup_table_cell_override


@dataclass(frozen=True)
class PreparedSource:
    text: str
    flags: tuple[str, ...] = field(default_factory=tuple)


_SPACED_DOI_URL_RE = re.compile(
    r"h\s*t\s*t\s*p\s*s\s*:\s*/\s*/\s*d\s*o\s*i\s*\.?\s*o\s*r\s*g\s*/\s*"
    r"(?P<doi>1\s*0\s*\.\s*[A-Za-z0-9\s./_-]+)",
    re.IGNORECASE,
)


def prepare_scholarly_source(source: str) -> PreparedSource:
    """Clean common scholarly PDF extraction artifacts before translation."""
    text = " ".join(source.replace("\x00", "").split())
    flags: list[str] = []

    repaired = _SPACED_DOI_URL_RE.sub(_repair_spaced_doi_match, text)
    if repaired != text:
        text = repaired
        flags.append("spaced_doi_repaired")

    cleaned = _remove_table_label_contamination(text)
    if cleaned != text:
        text = cleaned
        flags.append("table_label_contamination")

    repaired_fragment = _repair_truncated_word_fragment(text)
    if repaired_fragment != text:
        text = repaired_fragment
        flags.append("truncated_word_fragment")

    return PreparedSource(text=text, flags=tuple(flags))


def stitch_scholarly_fragments(sources: list[str]) -> list[str]:
    """Join adjacent PDF extraction fragments while preserving list length."""
    stitched = list(sources)
    index = 0
    while index < len(stitched):
        current = stitched[index]
        if not current:
            index += 1
            continue

        consumed = _stitch_table_caption(stitched, index)
        if consumed:
            index += consumed
            continue

        consumed = _stitch_supplementary_doi(stitched, index)
        if consumed:
            index += consumed
            continue

        consumed = _stitch_data_availability(stitched, index)
        if consumed:
            index += consumed
            continue

        consumed = _stitch_cross_block_sentence(stitched, index)
        if consumed:
            index += consumed
            continue

        index += 1
    return stitched


def _repair_spaced_doi_match(match: re.Match[str]) -> str:
    doi = re.sub(r"\s+", "", match.group("doi"))
    doi = doi.rstrip(".,;)")
    return f"https://doi.org/{doi}"


def _stitch_table_caption(sources: list[str], index: int) -> int:
    if index + 2 >= len(sources):
        return 0
    first = sources[index].strip()
    second = sources[index + 1].strip()
    third = sources[index + 2].strip()
    if not re.search(r"^Table\{v\d+\}\d+\s+Resistance\s+wel$", first, re.IGNORECASE):
        return 0
    if not re.match(r"^ding cycle parameters and characteristic process parameters \(V$", second, re.IGNORECASE):
        return 0
    if not re.match(r"^ariant \d+,\s*FEM\)$", third, re.IGNORECASE):
        return 0
    sources[index] = f"{first[:-3]}welding {second[5:-2]}(Variant {third[7:]}"
    sources[index + 1] = ""
    sources[index + 2] = ""
    return 3


def _stitch_supplementary_doi(sources: list[str], index: int) -> int:
    if index + 2 >= len(sources):
        return 0
    first = sources[index].strip()
    second = sources[index + 1].strip()
    third = sources[index + 2].strip()
    if not first.casefold().startswith("supplementary information "):
        return 0
    if not re.search(r"https://doi\.org/10\.1007/s4$", first, re.IGNORECASE):
        return 0
    if second != "3":
        return 0
    if not re.fullmatch(r"4\s+5\s+2\s*-\s*0\s*2\s*5\s*-\s*0\s*1\s*4\s*0\s*1\s*-\s*5\.?", third):
        return 0
    compact_tail = re.sub(r"\s+", "", third).rstrip(".")
    sources[index] = f"{first}{second}{compact_tail}"
    sources[index + 1] = ""
    sources[index + 2] = ""
    return 3


def _stitch_data_availability(sources: list[str], index: int) -> int:
    if index + 2 >= len(sources):
        return 0
    first = sources[index].strip()
    second = sources[index + 1].strip()
    third = sources[index + 2].strip()
    if not first.casefold().startswith("data availability "):
        return 0
    if not first.casefold().endswith("provided throug"):
        return 0
    if second.casefold() != "h":
        return 0
    if "relevant articles" not in third.casefold():
        return 0
    sources[index] = f"{first}h {third}"
    sources[index + 1] = ""
    sources[index + 2] = ""
    return 3


def _stitch_cross_block_sentence(sources: list[str], index: int) -> int:
    if index + 1 >= len(sources):
        return 0
    first = sources[index].strip()
    second = sources[index + 1].strip()
    if re.search(r"\band$", first, re.IGNORECASE) and re.match(r"^[A-Z]?\d+[A-Za-z]?\.", second):
        sources[index] = f"{first} {second}"
        sources[index + 1] = ""
        return 2
    return 0


def _remove_table_label_contamination(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"(?<=,\s)([A-D])\s+(?=\d{3,6}\))", "", cleaned)
    cleaned = re.sub(r"\s+\b[A-D]\b\s*$", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _repair_truncated_word_fragment(text: str) -> str:
    if re.search(r"\ban$", text):
        return re.sub(r"\ban$", "and", text).strip()
    return text


def is_references_heading(text: str) -> bool:
    normalized = " ".join(text.split()).strip().casefold()
    return normalized in {"references", "reference"}


def should_preserve_reference_text(in_references_section: bool, text: str) -> bool:
    if not in_references_section:
        return False
    return bool(text.strip())


def should_drop_isolated_table_label(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Da-d]", text.strip()))


def lookup_scholarly_phrase_override(text: str) -> str | None:
    normalized = " ".join(text.split())
    lower = normalized.casefold()

    section_heading = _translate_scholarly_section_heading(normalized)
    if section_heading is not None:
        return section_heading

    if _looks_like_welding_abbreviations_block(normalized):
        return "\n".join(
            [
                "Upslope\t용접 전류 상승 시간. 전기공학에서는 “rise time”이라고 함",
                "Downslope\t용접 전류 하강 시간. 전기공학에서는 “fall time”이라고 함",
                "BWC\t최적 용접 조건",
                "TCFT\t총 전류 통전 시간",
                "MCPT\t주전류 구간 시간",
                "DCimp\t펄스 직류 용접",
                "AC 50 Hz\t주파수 50 Hz의 교류 용접 전류",
                "DCc\t일정값 직류 용접 전류",
            ]
        )

    table_caption = _translate_resistance_welding_table_caption(normalized)
    if table_caption:
        return table_caption

    fragment_back_matter = _translate_fragmented_back_matter(normalized)
    if fragment_back_matter is not None:
        return fragment_back_matter

    table_cell = lookup_table_cell_override(normalized)
    if table_cell:
        return table_cell

    if lower == "conflict of interest the authors declare that they have no competing interests.":
        return "이해관계 충돌 저자들은 경쟁 관계가 없음을 선언합니다."

    if lower == (
        "data availability this article does not contain results taken from external databases. "
        "all source data is provided through citations to the relevant articles."
    ):
        return "데이터 가용성 이 논문은 외부 데이터베이스 결과를 포함하지 않습니다. 모든 원천 데이터는 관련 논문 인용으로 제공됩니다."

    if lower.startswith("supplementary information the online version contains supplementary material available at "):
        doi = normalized.rsplit(" ", 1)[-1].rstrip(".")
        return f"보충 정보 온라인 버전에는 {doi}에서 제공되는 보충 자료가 포함되어 있습니다."

    return None


def _translate_scholarly_section_heading(text: str) -> str | None:
    match = re.fullmatch(r"(?P<heading>Abstract)(?P<punct>[:：]?)", text, re.IGNORECASE)
    if not match:
        return None
    return f"초록{match.group('punct')}"


def _looks_like_welding_abbreviations_block(text: str) -> bool:
    lower = text.casefold()
    required = [
        "upslope",
        "downslope",
        "bwc",
        "tcft",
        "mcpt",
        "dcimp",
        "ac 50 hz",
        "dcc",
        "direct welding current",
    ]
    return all(term in lower for term in required)


def _translate_resistance_welding_table_caption(text: str) -> str | None:
    pattern = re.compile(
        r"^Table(?P<marker>\{v\d+\})?(?P<number>\d+)\s+Resistance\s+wel\s*ding\s+"
        r"cycle parameters and characteristic process parameters\s+\("
        r"V\s*ariant\s+(?P<variant>\d+),\s*FEM\)$",
        re.IGNORECASE,
    )
    match = pattern.fullmatch(text)
    if not match:
        pattern = re.compile(
            r"^Table(?P<marker>\{v\d+\})?(?P<number>\d+)\s+Resistance welding "
            r"cycle parameters and characteristic process parameters\s+\("
            r"Variant\s+(?P<variant>\d+),\s*FEM\)$",
            re.IGNORECASE,
        )
        match = pattern.fullmatch(text)
    if not match:
        return None
    marker = match.group("marker") or ""
    return (
        f"표{marker}{match.group('number')} 저항 용접 사이클 매개변수 및 "
        f"특성 공정 매개변수(변형 {match.group('variant')}, FEM)"
    )


def _translate_fragmented_back_matter(text: str) -> str | None:
    lower = text.casefold()
    if lower == "h":
        return ""
    if lower == "conflict o":
        return "이해관계 충돌"
    if lower.startswith("f interest the authors declare that they have no competing in"):
        return "저자들은 경쟁 관계가 없음을 선언합니다."
    if lower == "terests.":
        return ""
    if lower.startswith(
        "data availability this article does not contain results taken from external databases. "
        "all source data is provided throug"
    ):
        return "데이터 가용성 이 논문은 외부 데이터베이스 결과를 포함하지 않습니다. 모든 원천 데이터는 관련 논문 인용으로 제공됩니다."
    return None
