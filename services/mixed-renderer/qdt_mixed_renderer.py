from __future__ import annotations

import argparse
import html
import json
import os
import re
from string import Template
from pathlib import Path

import fitz
from scholar_translator.translator import (
    BedrockTranslator,
    ClaudeCodeCliTranslator,
    CodexCliTranslator,
    GoogleTranslator,
    GeminiTranslator,
    OfflineTranslator,
)

try:
    from kiwipiepy import Kiwi
except Exception:  # pragma: no cover - optional runtime dependency
    Kiwi = None


CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]")
LATIN_RE = re.compile(r"[A-Za-z]")
TERM_OVERRIDES = {
    "knowledge": "지식",
    "evidence": "근거",
    "research": "연구",
    "global and globalization": "글로벌과 세계화",
    "internationalization": "국제화",
    "liberalization": "자유화",
    "universalization": "보편화",
    "mcdonaldization": "맥도날드화",
    "super territoriality": "초영토성(Super Territoriality)",
    "actor": "행위자",
    "actors": "행위자",
    "value": "가치",
    "power": "권력",
    "power of groups": "집단의 권력 구성",
    "policy feedback theory": "정책 피드백 이론",
    "public policy": "공공 정책",
    "politics": "정치",
    "policy legacies as input matter": "정책 유산(입력)의 중요성",
    "reciprocal relationship between policy and politics": "정책과 정치의 상호관계",
    "agenda-setting": "의제 설정",
    "agenda setting": "의제 설정",
    "policy formulation": "정책 형성",
    "policy formulatio": "정책 형성",
    "political decision": "정치적 결정",
    "policy implementation": "정책 집행",
    "policy implementa": "정책 집행",
    "policy implemen": "정책 집행",
    "policy evaluation": "정책 평가",
    "focus": "분석 초점",
    "key factors for policy change": "정책 변화의 핵심 요인",
    "time horizon": "시간 지평",
    "how": "작동 방식",
    "multiple streams framework": "다중흐름모형",
    "multiple stream framework": "다중흐름모형",
    "advocacy coalition framework": "옹호연합모형",
    "punctuated equilibrium theory": "단절균형이론",
    "punctuated equilibrium": "단절균형",
    "theory 4 punctuated equilibrium theory": "이론 4: 단절균형이론",
    "periods of equilibrium": "균형 기간",
    "periods of change": "변화 기간",
    "optimism bias": "낙관적 편향(Optimism Bias)",
    "confirmation bias": "확증 편향(Confirmation Bias)",
    "hindsight bias": "사후확신 편향(Hindsight Bias)",
    "status quo bias": "현상유지 편향(Status Quo Bias)",
    "representativeness heuristic": "대표성 휴리스틱(Representativeness Heuristic)",
    "availability heuristic": "가용성 휴리스틱(Availability Heuristic)",
    "anchoring heuristic": "기준점 휴리스틱(Anchoring Heuristic)",
    "tendency to judge an event or phenomenon based on its similarity to a typical pattern or case ignoring actual probabilities or context": "전형적인 패턴이나 사례와의 유사성에 근거해 사건이나 현상을 판단하고, 실제 확률이나 맥락은 무시하는 경향",
    "tendency to make judgments based on information that easily comes to mind": "쉽게 떠오르는 정보에 근거해 판단하는 경향",
    "relying heavily on the first piece of information encountered the anchor when making decisions": "의사결정 시 처음 접한 정보(앵커)에 과도하게 의존하는 경향",
    "selective acceptance of information that supports preexisting beliefs while ignoring or downplaying opposing information": "기존 신념을 지지하는 정보는 선택적으로 수용하고, 반대 정보는 무시하거나 축소 평가하는 경향",
    "tendency to overestimate positive outcomes and underestimate potential risks or challenges": "긍정적 결과는 과대평가하고 잠재적 위험이나 과제는 과소평가하는 경향",
    "policy monopoly": "정책독점",
    "policy monopolies": "정책독점",
    "policy image": "정책 이미지",
    "policy images": "정책 이미지",
    "policy entrepreneur": "정책기업가",
    "policy entrepreneurs": "정책기업가",
    "policy entrepreneurs who couple streams to exploit policy windows": "정책의 창을 활용하기 위해 흐름을 결합하는 정책 기업가",
    "coupling of streams during a policy window": "정책의 창이 열릴 때 흐름의 결합",
    "timing coupling": "타이밍과 흐름의 결합",
    "feedback effects": "피드백 효과",
    "a set of feedback mechanisms positive or negative feedback followed by the policy": "정책에 뒤따르는 일련의 피드백 메커니즘(긍정적 또는 부정적 피드백)",
    "focuses more on the enduring effects of past policies rather than ongoing group competition": "진행 중인 집단 경쟁보다 과거 정책의 지속적 효과에 더 초점을 둔다",
    "collective advocacy coalitions that coordinate actions based on shared belief": "공유된 신념에 기반해 행동을 조정하는 집단적 옹호 연합",
    "power in four theories": "네 가지 이론에서의 권력",
    "value in four theories": "네 가지 이론에서의 가치",
    "how is their power rooted": "그들의 권력은 무엇에 기반하는가",
    "global health financing": "글로벌 보건 재원 조달",
    "international health regulations": "국제보건규칙(IHR)",
    "bilateral health cooperation": "양자 보건 협력",
    "domestic health policy": "국내 보건정책",
    "international health policy": "국제 보건정책",
    "global health policy": "글로벌 보건정책",
    "policy instruments": "정책수단",
    "funding source": "재원",
    "definition": "정의",
    "implications": "의미",
    "health system prioritizes universal coverage ensuring access to medical services for all": "보건의료 시스템은 보편적 보장을 우선시하여 모든 사람이 의료서비스에 접근할 수 있도록 보장한다",
    "government health insurance providers healthcare professionals and patients": "정부, 건강보험자, 보건의료 전문가, 환자",
    "the government regulates premiums and benefits while providers handle services and claims": "정부는 보험료와 급여를 규제하고, 공급자는 서비스와 청구를 처리한다",
    "essential medicines": "필수의약품",
    "global food systems": "글로벌 식량 시스템",
    "politics of health policy": "보건정책의 정치",
    "failure mode": "고장 형태",
    "foundation fmea": "기반(FOUNDATION) FMEA",
    "field issues": "필드 이슈 사항",
    "registration approval": "등록 승인",
    "multi-point fault": "복합 결함",
    "multi-point failure": "복합 결함",
    "non-conforming product": "부적합 제품(non-conforming product)",
    "discrepant product": "부적합 제품(discrepant product)",
    "defective product": "결함 제품(defective product)",
}
KOREAN_SPACING_OVERRIDES = {
    "지중해 식": "지중해식",
    "임상 시험": "임상시험",
    "식이 요법": "식이요법",
    "이 끄는": "이끄는",
    "새로운 연구는 이끄는": "새로운 연구를 이끄는",
    "지식과연결": "지식과 연결",
    "의하위집합": "의 하위 집합",
    "새로운지식": "새로운 지식",
    "지식을생성": "지식을 생성",
    "지식을추가": "지식을 추가",
    "기존의지식": "기존의 지식",
    "하는것을목표": "하는 것을 목표",
    "탐구를수행": "탐구를 수행",
    "근거제공": "근거 제공",
    "자리잡음": "자리 잡음",
    "심근 경색": "심근경색",
    "항 고혈압제": "항고혈압제",
    "권한이 행사됩니다": "권력이 행사됩니다",
    "다양한 전력원을 배치": "다양한 권력 자원을 동원",
    "Punctuation에 의해": "단절에 의해",
    "Punctuation 에 의해": "단절에 의해",
    "낙관적편향 (낙관 편향)": "낙관적 편향(Optimism Bias)",
    "확증편향": "확증 편향(Confirmation Bias)",
    "사후확신편향 (사후판단 편향)": "사후확신 편향(Hindsight Bias)",
    "현상유지편향 (현상 유지 편향)": "현상유지 편향(Status Quo Bias)",
    "단속균형 이론": "단절균형이론",
    "변경 기간": "변화 기간",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render mixed-language PDFs without overlay collisions.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", default="realistic")
    parser.add_argument("--output-mode", default="mono")
    parser.add_argument("--service", default="google")
    parser.add_argument("--prompt")
    parser.add_argument("--require-spacing", action="store_true")
    parser.add_argument("--glossary")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output)
    output_dir = output_root / f"{input_path.stem}-ko"
    output_dir.mkdir(parents=True, exist_ok=True)

    overrides = load_glossary_overrides(args.glossary) if args.glossary else {}
    translator = create_translator(args.service, args.prompt)
    spacer = create_spacing_engine(require_spacing=args.require_spacing)
    translated_pages = extract_and_translate(input_path, translator, spacer, overrides)

    md_path, html_path, pdf_path = build_output_paths(input_path, output_dir, args.output_mode)
    audit_path = build_audit_path(input_path, output_dir, args.output_mode)

    md_path.write_text(render_markdown(input_path, translated_pages), encoding="utf-8")
    html_path.write_text(render_html(input_path, translated_pages), encoding="utf-8")
    audit = render_layout_preserved_pdf(input_path, translator, spacer, pdf_path, overrides)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(pdf_path)
    print(md_path)
    print(html_path)
    print(audit_path)
    return 0


def create_translator(service: str, prompt_path: str | None = None):
    service_name, service_model = parse_service_spec(service)
    prompt = load_prompt(prompt_path)
    translators = {
        "google": GoogleTranslator,
        "gemini": GeminiTranslator,
        "bedrock": BedrockTranslator,
        "offline": OfflineTranslator,
        "codex-cli": CodexCliTranslator,
        "claude-code-cli": ClaudeCodeCliTranslator,
    }
    translator_class = translators.get(service_name)
    if translator_class is None:
        raise ValueError(f"Unsupported translation service for mixed renderer: {service_name}")
    kwargs = {"ignore_cache": False}
    if prompt is not None:
        kwargs["prompt"] = prompt
    return translator_class("en", "ko", service_model, **kwargs)


def parse_service_spec(service: str) -> tuple[str, str | None]:
    normalized = (service or "google").strip().lower()
    if ":" not in normalized:
        return normalized, None
    name, model = normalized.split(":", 1)
    return name, model or None


def load_prompt(prompt_path: str | None) -> Template | None:
    if not prompt_path:
        return None
    return Template(Path(prompt_path).read_text(encoding="utf-8"))


def build_output_paths(input_path: Path, output_dir: Path, output_mode: str) -> tuple[Path, Path, Path]:
    normalized_mode = output_mode.lower()
    suffix = "dual" if normalized_mode == "dual" else "mono"
    base_name = f"{input_path.stem}-ko-{suffix}"
    return (
        output_dir / f"{base_name}.md",
        output_dir / f"{base_name}.html",
        output_dir / f"{base_name}.pdf",
    )


def build_audit_path(input_path: Path, output_dir: Path, output_mode: str) -> Path:
    normalized_mode = output_mode.lower()
    suffix = "dual" if normalized_mode == "dual" else "mono"
    return output_dir / f"{input_path.stem}-ko-{suffix}.layout-audit.json"


def resolve_font_file() -> str | None:
    candidates = [
        os.environ.get("QDT_FONT_PATH"),
        str(Path(__file__).resolve().parent / "assets" / "fonts" / "Pretendard-Regular.ttf"),
        r"C:\Windows\Fonts\malgun.ttf",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def create_spacing_engine(require_spacing: bool = False):
    if Kiwi:
        return Kiwi()
    if require_spacing:
        raise RuntimeError("kiwipiepy is required for Korean spacing normalization.")
    return None


def extract_and_translate(input_path: Path, translator: GoogleTranslator, spacer, overrides: dict[str, str] | None = None) -> list[dict]:
    doc = fitz.open(input_path)
    pages = []
    cache: dict[str, str] = {}

    for page_index, page in enumerate(doc, start=1):
        page_blocks = []
        blocks = merge_fragmented_text_blocks(
            sorted(page.get_text("blocks"), key=lambda block: (round(block[1], 1), round(block[0], 1)))
        )
        for block in blocks:
            text = clean_text(block[4])
            if not text:
                continue

            translated_lines = translate_source_text(text, translator, cache, spacer, overrides)

            if translated_lines:
                page_blocks.append(
                    {
                        "source": text,
                        "lines": translated_lines,
                    }
                )

        pages.append({"page": page_index, "blocks": page_blocks})

    return pages


def split_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.extend(split_embedded_bullet_line(line))
    return merge_wrapped_english_lines(merge_orphan_list_markers(lines))


def split_embedded_bullet_line(line: str) -> list[str]:
    if ") • " not in line:
        return [line]

    head, tail = line.split(") • ", 1)
    if not head.strip() or not tail.strip():
        return [line]
    return [f"{head})", f"• {tail}"]


def merge_fragmented_text_blocks(blocks: list[tuple]) -> list[tuple]:
    consumed: set[int] = set()
    merged_blocks: list[tuple] = []

    for index, block in enumerate(blocks):
        if index in consumed:
            continue

        source = clean_text(block[4])
        rect = fitz.Rect(block[:4])
        block_no = block[5] if len(block) > 5 else None
        merged = False

        while True:
            continuation = find_fragment_continuation(source, rect, blocks, consumed | {index})
            if continuation is None:
                break

            next_index, next_text, next_rect = continuation
            source = join_fragmented_text(source, next_text)
            rect |= next_rect
            consumed.add(next_index)
            merged = True

        if merged:
            merged_blocks.append((rect.x0, rect.y0, rect.x1, rect.y1, source, None))
        else:
            merged_blocks.append(block if len(block) > 5 else (*block[:4], source, block_no))

    return sorted(merged_blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))


def find_fragment_continuation(
    source: str,
    rect: fitz.Rect,
    blocks: list[tuple],
    consumed: set[int],
) -> tuple[int, str, fitz.Rect] | None:
    if not should_seek_fragment_continuation(source):
        return None

    candidates = []
    for index, block in enumerate(blocks):
        if index in consumed:
            continue

        text = clean_text(block[4])
        if not is_word_fragment_continuation(text):
            continue

        candidate_rect = fitz.Rect(block[:4])
        vertical_gap = candidate_rect.y0 - rect.y1
        if vertical_gap > 18:
            continue
        if candidate_rect.y1 < rect.y0:
            continue

        center_x = (candidate_rect.x0 + candidate_rect.x1) / 2
        if center_x < rect.x0 - 8 or center_x > rect.x1 + 40:
            continue

        candidates.append((abs(vertical_gap), candidate_rect.x0, index, text, candidate_rect))

    if not candidates:
        return None

    _, _, index, text, candidate_rect = min(candidates, key=lambda item: (item[0], item[1]))
    return index, text, candidate_rect


def should_seek_fragment_continuation(source: str) -> bool:
    stripped = source.strip()
    if stripped.endswith("-"):
        return True

    words = stripped.split()
    if not words:
        return False

    tail = words[-1].strip(".,;:()[]{}")
    if not re.fullmatch(r"[A-Za-z]{4,18}", tail):
        return False
    return tail.lower().endswith(("a", "e", "i", "o", "u", "men", "tion", "tio", "atio", "enta"))


def is_word_fragment_continuation(text: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{1,8}", text.strip()))


def join_fragmented_text(source: str, continuation: str) -> str:
    source = source.rstrip()
    continuation = continuation.strip()
    if source.endswith("-"):
        return f"{source}{continuation}"
    return f"{source}{continuation}"


def merge_orphan_list_markers(lines: list[str]) -> list[str]:
    merged = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if index + 1 < len(lines) and is_orphan_list_marker(line):
            merged.append(f"{line} {lines[index + 1]}")
            index += 2
            continue
        merged.append(line)
        index += 1
    return merged


def merge_wrapped_english_lines(lines: list[str]) -> list[str]:
    merged = []
    index = 0
    while index < len(lines):
        line = lines[index]
        while index + 1 < len(lines) and (
            should_merge_wrapped_parenthetical(line, lines[index + 1])
            or should_merge_wrapped_english(line, lines[index + 1])
        ):
            line = f"{line} {lines[index + 1]}"
            index += 1
        merged.append(line)
        index += 1
    return merged


def should_merge_wrapped_parenthetical(current: str, following: str) -> bool:
    if "(" not in current or ")" in current:
        return False
    if ")" not in following:
        return False
    if re.match(r"^[•❖◆◇□❑<>]|\d+[).]", following.strip()):
        return False
    return True


def should_merge_wrapped_english(current: str, following: str) -> bool:
    if not current.strip().startswith("•"):
        return False
    if CJK_RE.search(current) or CJK_RE.search(following):
        return False
    if not LATIN_RE.search(current) or not LATIN_RE.search(following):
        return False
    if re.match(r"^([•❖◆◇□❑<>]|\d+[).])", following.strip()):
        return False
    if current.rstrip().endswith((".", "?", "!", ":", ";")):
        return False
    if current.rstrip().endswith(")") and not re.match(r"^[a-z]", following.strip()):
        return False
    return True


def is_orphan_list_marker(line: str) -> bool:
    return line in {"•", "-", "–"} or bool(re.fullmatch(r"\d+[).]", line))


def clean_text(text: str) -> str:
    return text.replace("\x00", "").strip()


def translate_line(line: str, translator: GoogleTranslator, cache: dict[str, str], spacer, overrides: dict[str, str] | None = None) -> list[str]:
    bilingual_label = lookup_bilingual_label_override(line)
    if bilingual_label:
        return [bilingual_label]

    if not should_translate(line):
        return [polish_korean_spacing(line, spacer)]

    decorative_heading = translate_decorative_heading(line, translator, cache)
    if decorative_heading:
        return [decorative_heading]

    if ">>" in line:
        left, right = line.split(">>", 1)
        translated = translate_text(left.strip(), translator, cache, overrides) if should_translate(left) else left.strip()
        preserved = right.strip()
        if not translated and preserved and should_translate(preserved) and not CJK_RE.search(preserved):
            return [f">> {translate_text(preserved, translator, cache, overrides)}"]
        return [f"{translated}", f">> {polish_korean_spacing(preserved, spacer)}"] if preserved else [translated]

    cjk_match = CJK_RE.search(line)
    if cjk_match and cjk_match.start() >= 8:
        english_part = line[: cjk_match.start()].strip()
        local_part = line[cjk_match.start() :].strip()
        translated = translate_text(english_part, translator, cache, overrides) if should_translate(english_part) else english_part
        if english_part.endswith("(") or translated.endswith("("):
            collapsed = collapse_duplicate_parenthetical(translated, local_part)
            return [polish_korean_spacing(collapsed or f"{translated}{local_part}", spacer)]
        return [translated, polish_korean_spacing(local_part, spacer)]

    return [translate_text(line, translator, cache, overrides)]


def translate_source_text(text: str, translator: GoogleTranslator, cache: dict[str, str], spacer, overrides: dict[str, str] | None = None) -> list[str]:
    normalized = " ".join(text.split())
    lines = split_lines(text)
    if len(lines) == 1:
        decorative_heading = translate_decorative_heading(lines[0], translator, cache)
        if decorative_heading:
            return [decorative_heading]

    if lookup_term_override(normalized, overrides):
        return [translate_text(normalized, translator, cache, overrides)]

    translated_lines = []
    for line in lines:
        translated_lines.extend(translate_line(line, translator, cache, spacer, overrides))
    return collapse_duplicate_translated_lines(translated_lines)


def translate_decorative_heading(line: str, translator: GoogleTranslator, cache: dict[str, str]) -> str | None:
    match = re.fullmatch(r"([❑□■▪▫➢▶])\s*(.+)", line.strip())
    if not match:
        return None

    marker, body = match.groups()
    translated = translate_text(body, translator, cache)
    output_marker = "▶" if marker in {"➢", "▶"} else "□"
    return f"{output_marker} {translated}"


def collapse_duplicate_translated_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    for line in lines:
        stripped = line.strip()
        if collapsed and is_duplicate_parenthetical_line(collapsed[-1], stripped):
            continue
        collapsed.append(line)
    return collapsed


def is_duplicate_parenthetical_line(previous: str, current: str) -> bool:
    match = re.fullmatch(r"\(\s*(.+?)\s*\)", current.strip())
    if not match:
        return False
    parenthetical = match.group(1)
    return previous.strip().replace(" ", "") == parenthetical.replace(" ", "")


def polish_korean_spacing(text: str, spacer) -> str:
    if spacer is None:
        return text

    prefix = ""
    body = text.strip()
    if body.startswith(">>"):
        prefix = ">> "
        body = body[2:].strip()

    override_only = normalize_korean_spacing_artifacts(body)
    if override_only != body:
        return f"{prefix}{override_only}" if prefix else override_only

    latin = len(LATIN_RE.findall(body))
    cjk = len(CJK_RE.findall(body))
    if cjk < 8 or latin > cjk:
        return text

    if " " in body and len(body.replace(" ", "")) / max(1, len(body)) < 0.82:
        return text

    try:
        spaced = spacer.space(body)
    except Exception:
        return text

    spaced = normalize_korean_spacing_artifacts(spaced)
    return f"{prefix}{spaced}" if prefix else spaced


def normalize_korean_spacing_artifacts(text: str) -> str:
    text = re.sub(r"\s*·\s*", "·", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([“\"'(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([”\"')\]])", r"\1", text)
    for source, replacement in KOREAN_SPACING_OVERRIDES.items():
        text = text.replace(source, replacement)
    return text


def should_translate(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    first_cjk = CJK_RE.search(stripped)
    if first_cjk and lookup_term_override(stripped[: first_cjk.start()].strip()):
        return True

    latin = len(LATIN_RE.findall(stripped))
    cjk = len(CJK_RE.findall(stripped))
    if latin < 4:
        return False
    if cjk > 0 and latin < cjk * 1.5:
        return False
    if re.fullmatch(r"[\d\s\-–—_/().:]+", stripped):
        return False
    return True


def is_layout_replacement_candidate(text: str) -> bool:
    stripped = clean_text(text)
    if not stripped:
        return False
    if stripped.startswith(">>") and CJK_RE.search(stripped):
        return False

    latin = len(LATIN_RE.findall(stripped))
    cjk = len(CJK_RE.findall(stripped))
    if latin < 4:
        return False
    if cjk > 0 and latin < cjk * 1.15:
        return False
    if re.fullmatch(r"[\d\s\-–—_/().:]+", stripped):
        return False
    return True


def translate_text(text: str, translator: GoogleTranslator, cache: dict[str, str], overrides: dict[str, str] | None = None) -> str:
    normalized = " ".join(text.split())
    label_override = lookup_bilingual_label_override(normalized)
    if label_override:
        return label_override

    direct_override = lookup_term_override(normalized, overrides)
    if direct_override:
        return collapse_duplicate_korean_parenthetical(direct_override)

    if normalized in cache:
        return cache[normalized]
    try:
        translated = translator.translate(normalized)
    except Exception:
        translated = normalized
    translated = apply_term_overrides(normalized, translated, overrides)
    translated = collapse_duplicate_korean_parenthetical(translated)
    cache[normalized] = translated
    return translated


def lookup_bilingual_label_override(text: str) -> str | None:
    match = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", text.strip())
    if not match:
        return None

    korean_part, english_part = match.groups()
    english_part = " ".join(english_part.split())
    english_key = re.sub(r"[^a-z0-9 -]+", "", english_part.lower()).strip()
    english_key = " ".join(english_key.split())
    if english_key not in TERM_OVERRIDES:
        return None

    translated = TERM_OVERRIDES[english_key]
    if f"({english_part})" in translated:
        return translated
    if CJK_RE.search(korean_part):
        return f"{korean_part.strip()}({english_part})"
    return translated


def load_glossary_overrides(glossary_csv) -> dict[str, str]:
    """Load glossary CSV and return normalized key -> target mapping."""
    import csv
    import os
    from pathlib import Path

    overrides: dict[str, str] = {}
    for raw_path in str(glossary_csv).split(os.pathsep):
        if not raw_path.strip():
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source = row.get("source", "").strip()
                if not source:
                    continue
                key = re.sub(r"[^a-z0-9 -]+", "", source.lower()).strip()
                key = " ".join(key.split())
                overrides[key] = row.get("target", "")
    return overrides


def lookup_term_override(text: str, overrides: dict[str, str] | None = None) -> str | None:
    effective = {**TERM_OVERRIDES, **overrides} if overrides else TERM_OVERRIDES
    decorated = re.fullmatch(r"([^A-Za-z0-9]*)([A-Za-z][A-Za-z0-9 -]*[A-Za-z])([^A-Za-z0-9]*)", text)
    if decorated:
        prefix, core, suffix = decorated.groups()
        core_key = re.sub(r"[^a-z0-9 -]+", "", core.lower()).strip()
        core_key = " ".join(core_key.split())
        if core_key in effective:
            if core_key == "how" and suffix.strip() == "?":
                return f"{prefix}{effective[core_key]}"
            if CJK_RE.search(suffix) and "(" in suffix and ")" in suffix:
                return f"{prefix}{effective[core_key]}"
            return f"{prefix}{effective[core_key]}{suffix}"

    key = re.sub(r"[^a-z0-9 -]+", "", text.lower()).strip()
    key = " ".join(key.split())
    return effective.get(key)


def collapse_duplicate_parenthetical(translated_prefix: str, local_part: str) -> str | None:
    if not translated_prefix.endswith("(") or not local_part.endswith(")"):
        return None

    translated_without_open = translated_prefix[:-1].strip()
    local_core = local_part[:-1].strip()
    if translated_without_open.endswith(local_core):
        return translated_without_open

    return None


def collapse_duplicate_korean_parenthetical(text: str) -> str:
    normalized = text.strip()
    match = re.fullmatch(r"(.+?)\s*\(\s*(.+?)\s*\)", normalized)
    if not match:
        return text

    left, right = match.groups()
    if left.replace(" ", "") == right.replace(" ", ""):
        return left.strip()
    return text


def apply_term_overrides(source: str, translated: str, overrides: dict[str, str] | None = None) -> str:
    effective = {**TERM_OVERRIDES, **overrides} if overrides else TERM_OVERRIDES
    source_lower = source.lower()
    for english, korean in effective.items():
        if english not in source_lower:
            continue
        if source_lower.strip() == english:
            return korean
        translated = re.sub(r"\b" + re.escape(english) + r"\b", korean, translated, flags=re.IGNORECASE)

    if "evidence" in source_lower and translated.strip() in {"멸종", "증거"}:
        return "근거"
    return translated


def render_markdown(input_path: Path, pages: list[dict]) -> str:
    lines = [f"# {input_path.stem} - 혼합언어 번역본", ""]
    for page in pages:
        lines.append(f"## Page {page['page']}")
        lines.append("")
        for block in page["blocks"]:
            for line in block["lines"]:
                lines.append(line)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_html(input_path: Path, pages: list[dict]) -> str:
    body = []
    for page in pages:
        blocks = []
        for block in page["blocks"]:
            text = "<br>".join(html.escape(line) for line in block["lines"])
            blocks.append(f"<div class='block'>{text}</div>")
        body.append(f"<section class='page'><h2>Page {page['page']}</h2>{''.join(blocks)}</section>")

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{html.escape(input_path.stem)} - 혼합언어 번역본</title>
  <style>
    body {{ margin: 0; background: #f8f4f7; color: #2e2430; font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ margin: 0 0 24px; font-size: 28px; }}
    .page {{ margin: 0 0 18px; padding: 22px; background: white; border-radius: 8px; }}
    h2 {{ margin: 0 0 16px; font-size: 16px; color: #b83280; }}
    .block {{ margin: 0 0 13px; font-size: 14px; line-height: 1.65; white-space: normal; }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(input_path.stem)} - 혼합언어 번역본</h1>
    {''.join(body)}
  </main>
</body>
</html>
"""


def render_layout_preserved_pdf(input_path: Path, translator: GoogleTranslator, spacer, output_path: Path, overrides: dict[str, str] | None = None) -> dict:
    doc = fitz.open(input_path)
    font_file = resolve_font_file()
    cache: dict[str, str] = {}
    page_audits = []

    for page_index, page in enumerate(doc, start=1):
        page_audit = {"page": page_index, "replacements": []}
        blocks = merge_fragmented_text_blocks(
            sorted(page.get_text("blocks"), key=lambda block: (round(block[1], 1), round(block[0], 1)))
        )
        page_words = page.get_text("words")
        page_drawings = page.get_drawings()
        table_skip_rects = []
        panel_skip_rects = []
        table_audit = render_health_policy_comparison_table_if_present(page, font_file)
        if table_audit:
            page_audit["replacements"].extend(table_audit["replacements"])
            table_skip_rects.extend(table_audit["skip_rects"])
        diagram_audit = render_punctuated_equilibrium_diagram_if_present(page, font_file)
        if diagram_audit:
            page_audit["replacements"].extend(diagram_audit["replacements"])
            table_skip_rects.extend(diagram_audit["skip_rects"])
        figure_audit = render_bounded_rationality_image_text_if_present(page, font_file)
        if figure_audit:
            page_audit["replacements"].extend(figure_audit["replacements"])
        for block in blocks:
            rect = fitz.Rect(block[:4])
            if any(rects_overlap(rect, skip_rect, min_ratio=0.2) for skip_rect in table_skip_rects):
                continue
            if any(rect_center_inside(rect, skip_rect) for skip_rect in panel_skip_rects):
                continue

            source = clean_text(block[4])
            if not is_layout_replacement_candidate(source):
                continue

            panel_shape = find_text_panel_shape(rect, page_drawings) if is_card_panel_start(source) else None
            if panel_shape:
                panel_rect = fitz.Rect(panel_shape["rect"])
                panel_source = collect_panel_text(blocks, panel_rect)
                translated_lines = translate_source_text(panel_source, translator, cache, spacer, overrides)
                translated_text = "\n".join(line for line in translated_lines if line.strip())
                if translated_text:
                    fill_color = tuple(float(value) for value in panel_shape.get("fill", (1, 1, 1)))
                    source_style = source_style_for_rect(page, rect)
                    text_color = choose_text_color(fill_color, source_style["color"])
                    page.draw_rect(panel_rect, color=None, fill=fill_color, overlay=True)
                    text_rect = fitz.Rect(panel_rect.x0 + 8, panel_rect.y0 + 8, panel_rect.x1 - 8, panel_rect.y1 - 7)
                    fit_result = insert_layout_textbox(
                        page,
                        text_rect,
                        translated_text,
                        font_file,
                        color=text_color,
                        source_size=source_style["font_size"],
                        bold=source_style["bold"],
                    )
                    review_flags = review_flags_for_replacement(panel_source, translated_text, fit_result["fitted"])
                    page_audit["replacements"].append(
                        {
                            "fitted": fit_result["fitted"],
                            "font_size": fit_result["font_size"],
                            "bold": fit_result["bold"],
                            "rect": [
                                round(panel_rect.x0, 2),
                                round(panel_rect.y0, 2),
                                round(panel_rect.x1, 2),
                                round(panel_rect.y1, 2),
                            ],
                            "source_preview": preview_text(panel_source),
                            "translated_preview": preview_text(translated_text),
                            "route": "panel-redraw",
                            **review_flags,
                        }
                    )
                    panel_skip_rects.append(panel_rect)
                    continue

            block_no = block[5] if len(block) > 5 else None
            label_words = [word for word in page_words if block_no is not None and word[5] == block_no]
            normalized_source = " ".join(source.split())
            whole_block_term = lookup_term_override(normalized_source, overrides) is not None
            label_targets = [] if whole_block_term else build_label_replacement_targets(source, label_words)
            if label_targets:
                for target in label_targets:
                    translated_text = translate_text(target["source"], translator, cache, overrides)
                    if not translated_text:
                        continue

                    source_style = source_style_for_rect(page, target["rect"])
                    shape = None if is_light_color(source_style["color"]) else find_covering_filled_shape(target["rect"], page_drawings)
                    if shape:
                        shape_rect = fitz.Rect(shape["rect"])
                        fill_color = tuple(float(value) for value in shape.get("fill", (1, 1, 1)))
                        page.draw_oval(shape_rect, color=None, fill=fill_color, fill_opacity=1, overlay=True)
                        mask_rect = expand_rect(target["rect"], page.rect, 10)
                        route = "label-shape"
                    else:
                        mask_rect = expand_rect(target["rect"], page.rect, 2.2)
                        fill_color = mask_fill_color(page, target["rect"], page_drawings, source_style["color"])
                        page.draw_rect(mask_rect, color=None, fill=fill_color, overlay=True)
                        route = "label"

                    text_color = choose_text_color(fill_color, source_style["color"])
                    fit_result = insert_layout_textbox(
                        page,
                        mask_rect,
                        translated_text,
                        font_file,
                        color=text_color,
                        align=fitz.TEXT_ALIGN_CENTER,
                        source_size=source_style["font_size"],
                        bold=source_style["bold"],
                    )
                    review_flags = review_flags_for_replacement(target["source"], translated_text, fit_result["fitted"])
                    page_audit["replacements"].append(
                        {
                            "fitted": fit_result["fitted"],
                            "font_size": fit_result["font_size"],
                            "bold": fit_result["bold"],
                            "rect": [
                                round(mask_rect.x0, 2),
                                round(mask_rect.y0, 2),
                                round(mask_rect.x1, 2),
                                round(mask_rect.y1, 2),
                            ],
                            "source_preview": preview_text(target["source"]),
                            "translated_preview": preview_text(translated_text),
                            "route": route,
                            **review_flags,
                        }
                    )
                continue

            spread_targets = build_spread_line_replacement_targets(source, label_words)
            if spread_targets:
                for target in spread_targets:
                    translated_lines: list[str] = []
                    for line in split_lines(target["source"]):
                        translated_lines.extend(translate_line(line, translator, cache, spacer))
                    translated_text = "\n".join(line for line in translated_lines if line.strip())
                    if not translated_text:
                        continue

                    mask_rect = expand_rect(target["rect"], page.rect, 1.2)
                    source_style = source_style_for_rect(page, target["rect"])
                    fill_color = mask_fill_color(page, target["rect"], page_drawings, source_style["color"])
                    text_color = choose_text_color(fill_color, source_style["color"])
                    page.draw_rect(mask_rect, color=None, fill=fill_color, overlay=True)
                    fit_result = insert_layout_textbox(
                        page,
                        mask_rect,
                        translated_text,
                        font_file,
                        color=text_color,
                        source_size=source_style["font_size"],
                        bold=source_style["bold"],
                    )
                    review_flags = review_flags_for_replacement(target["source"], translated_text, fit_result["fitted"])
                    page_audit["replacements"].append(
                        {
                            "fitted": fit_result["fitted"],
                            "font_size": fit_result["font_size"],
                            "bold": fit_result["bold"],
                            "rect": [
                                round(mask_rect.x0, 2),
                                round(mask_rect.y0, 2),
                                round(mask_rect.x1, 2),
                                round(mask_rect.y1, 2),
                            ],
                            "source_preview": preview_text(target["source"]),
                            "translated_preview": preview_text(translated_text),
                            "route": "spread-line",
                            **review_flags,
                        }
                    )
                continue

            translated_lines = translate_source_text(source, translator, cache, spacer)
            translated_text = "\n".join(line for line in translated_lines if line.strip())
            if not translated_text:
                continue

            mask_rect = expand_rect(rect, page.rect, 1.2)
            source_style = source_style_for_rect(page, rect)
            fill_color = mask_fill_color(page, rect, page_drawings, source_style["color"])
            text_color = choose_text_color(fill_color, source_style["color"])
            align = fitz.TEXT_ALIGN_CENTER if should_center_layout_text(source, rect, page_drawings) else fitz.TEXT_ALIGN_LEFT
            page.draw_rect(mask_rect, color=None, fill=fill_color, overlay=True)
            fit_result = insert_layout_textbox(
                page,
                mask_rect,
                translated_text,
                font_file,
                color=text_color,
                align=align,
                source_size=source_style["font_size"],
                bold=source_style["bold"],
            )
            review_flags = review_flags_for_replacement(source, translated_text, fit_result["fitted"])
            page_audit["replacements"].append(
                {
                    "fitted": fit_result["fitted"],
                    "font_size": fit_result["font_size"],
                    "bold": fit_result["bold"],
                    "rect": [round(mask_rect.x0, 2), round(mask_rect.y0, 2), round(mask_rect.x1, 2), round(mask_rect.y1, 2)],
                    "source_preview": preview_text(source),
                    "translated_preview": preview_text(translated_text),
                    **review_flags,
                }
            )

        page_audits.append(page_audit)

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return summarize_layout_audit(page_audits, source_path=str(input_path), output_path=str(output_path))


def build_label_replacement_targets(source: str, words: list[tuple]) -> list[dict]:
    if not is_short_diagram_label_block(source, words):
        return []

    line_groups = []
    for line_no in sorted({word[6] for word in words}):
        line_words = sorted([word for word in words if word[6] == line_no], key=lambda word: word[7])
        text = " ".join(word[4] for word in line_words).strip()
        if not text:
            continue
        line_groups.append({"text": text, "words": line_words})

    targets = []
    index = 0
    while index < len(line_groups):
        current_text = line_groups[index]["text"]
        current_words = list(line_groups[index]["words"])

        if index + 1 < len(line_groups):
            combined_text = f"{current_text} {line_groups[index + 1]['text']}"
            if lookup_term_override(combined_text) or is_parenthetical_label_pair(current_text, line_groups[index + 1]["text"]):
                current_text = combined_text
                current_words.extend(line_groups[index + 1]["words"])
                index += 1

        targets.append({"source": current_text, "rect": union_word_rects(current_words)})
        index += 1

    return targets


def build_spread_line_replacement_targets(source: str, words: list[tuple]) -> list[dict]:
    if len(words) < 4:
        return []

    line_groups = []
    for line_no in sorted({word[6] for word in words}):
        line_words = sorted([word for word in words if word[6] == line_no], key=lambda word: word[7])
        text = " ".join(word[4] for word in line_words).strip()
        if text:
            line_groups.append({"source": text, "rect": union_word_rects(line_words)})

    if len(line_groups) < 2:
        return []

    x_positions = [group["rect"].x0 for group in line_groups]
    if max(x_positions) - min(x_positions) < 140:
        return []

    block_rect = union_word_rects(words)
    widest_line = max(group["rect"].width for group in line_groups)
    if block_rect.width < widest_line * 1.55:
        return []

    return line_groups


def is_short_diagram_label_block(source: str, words: list[tuple]) -> bool:
    if len(words) < 2 or len(words) > 8:
        return False

    lines = split_lines(source)
    if len(lines) < 2:
        return False
    if any(len(line) > 32 for line in lines):
        return False
    if any(not re.search(r"[A-Za-z]", line) for line in lines):
        return False

    block_rect = union_word_rects(words)
    total_word_width = sum(fitz.Rect(word[:4]).width for word in words)
    has_spread_out_words = block_rect.width > total_word_width * 1.35
    has_multi_line_term = any(lookup_term_override(f"{lines[index]} {lines[index + 1]}") for index in range(len(lines) - 1))
    return has_spread_out_words or has_multi_line_term


def is_parenthetical_label_pair(left: str, right: str) -> bool:
    return bool(CJK_RE.search(left) and re.fullmatch(r"\([A-Za-z][A-Za-z ]+\)", right.strip()))


def union_word_rects(words: list[tuple]) -> fitz.Rect:
    rect = fitz.Rect(words[0][:4])
    for word in words[1:]:
        rect |= fitz.Rect(word[:4])
    return rect


def find_covering_filled_shape(text_rect: fitz.Rect, drawings: list[dict]) -> dict | None:
    center = fitz.Point((text_rect.x0 + text_rect.x1) / 2, (text_rect.y0 + text_rect.y1) / 2)
    candidates = []
    for drawing in drawings:
        shape_rect = drawing.get("rect")
        fill = drawing.get("fill")
        if not shape_rect or fill is None:
            continue

        shape_rect = fitz.Rect(shape_rect)
        if shape_rect.width < text_rect.width or shape_rect.height < text_rect.height:
            continue
        if not shape_rect.contains(center):
            continue
        if shape_rect.width * shape_rect.height < text_rect.width * text_rect.height * 3:
            continue
        if shape_rect.height > text_rect.height * 6:
            continue
        if shape_rect.width > text_rect.width * 3:
            continue

        candidates.append((shape_rect.width * shape_rect.height, drawing))

    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def is_card_panel_start(source: str) -> bool:
    return source.strip().startswith(("❖", "◆", "◇"))


def find_text_panel_shape(text_rect: fitz.Rect, drawings: list[dict]) -> dict | None:
    center = fitz.Point((text_rect.x0 + text_rect.x1) / 2, (text_rect.y0 + text_rect.y1) / 2)
    candidates = []
    for drawing in drawings:
        shape_rect = drawing.get("rect")
        fill = drawing.get("fill")
        if not shape_rect or fill is None:
            continue

        shape_rect = fitz.Rect(shape_rect)
        if not shape_rect.contains(center):
            continue

        area_ratio = shape_rect.get_area() / max(1, text_rect.get_area())
        if area_ratio < 1.05 or area_ratio > 18:
            continue
        if shape_rect.width < text_rect.width * 1.03 or shape_rect.height < text_rect.height * 1.02:
            continue
        if color_luminance(tuple(float(value) for value in fill)) > 0.97:
            continue

        candidates.append((area_ratio, shape_rect.get_area(), drawing))

    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def collect_panel_text(blocks: list[tuple], panel_rect: fitz.Rect) -> str:
    panel_blocks = []
    for block in blocks:
        rect = fitz.Rect(block[:4])
        if rect_center_inside(rect, panel_rect):
            panel_blocks.append((rect.y0, rect.x0, clean_text(block[4])))

    return "\n".join(text for _, _, text in sorted(panel_blocks) if text.strip())


def background_fill_color(
    text_rect: fitz.Rect,
    drawings: list[dict],
    source_color: tuple[float, float, float] | None = None,
) -> tuple[float, float, float] | None:
    center = fitz.Point((text_rect.x0 + text_rect.x1) / 2, (text_rect.y0 + text_rect.y1) / 2)
    candidates = []
    for drawing in drawings:
        shape_rect = drawing.get("rect")
        fill = drawing.get("fill")
        if not shape_rect or fill is None:
            continue

        shape_rect = fitz.Rect(shape_rect)
        if not shape_rect.contains(center):
            continue
        area_ratio = shape_rect.width * shape_rect.height / max(1, text_rect.width * text_rect.height)
        if area_ratio < 2.8:
            continue
        if shape_rect.width < text_rect.width * 1.15 and shape_rect.height < text_rect.height * 1.4:
            continue
        if area_ratio > 25:
            continue

        candidates.append((area_ratio, fill))

    if not candidates:
        return None

    if is_light_color(source_color):
        dark_candidates = [candidate for candidate in candidates if color_luminance(candidate[1]) < 0.58]
        if dark_candidates:
            fill = min(dark_candidates, key=lambda item: item[0])[1]
            return (float(fill[0]), float(fill[1]), float(fill[2]))
    elif source_color is not None:
        light_candidates = [candidate for candidate in candidates if color_luminance(candidate[1]) > 0.76]
        if light_candidates:
            fill = min(light_candidates, key=lambda item: item[0])[1]
            return (float(fill[0]), float(fill[1]), float(fill[2]))

    fill = min(candidates, key=lambda item: item[0])[1]
    return (float(fill[0]), float(fill[1]), float(fill[2]))


def mask_fill_color(
    page,
    text_rect: fitz.Rect,
    drawings: list[dict],
    source_color: tuple[float, float, float] | None = None,
) -> tuple[float, float, float]:
    shape_fill = background_fill_color(text_rect, drawings, source_color=source_color)
    if shape_fill is not None:
        return shape_fill
    return sample_light_background_color(page, expand_rect(text_rect, page.rect, 4))


def source_style_for_rect(page, rect: fitz.Rect) -> dict:
    spans = []
    try:
        page_dict = page.get_text("dict")
    except Exception:
        return {"font_size": None, "color": None, "bold": False}

    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                span_rect = fitz.Rect(span.get("bbox", rect))
                if not rects_overlap(span_rect, rect, min_ratio=0.2):
                    continue
                if "Wingdings" in span.get("font", ""):
                    continue
                spans.append(span)

    if not spans:
        return {"font_size": None, "color": None, "bold": False}

    font_size = max(float(span.get("size", 0)) for span in spans) or None
    color_weights: dict[tuple[float, float, float], int] = {}
    bold_weight = 0
    total_style_weight = 0
    for span in spans:
        color = pdf_color_to_rgb(span.get("color", 0))
        weight = max(1, len(span.get("text", "").strip()))
        color_weights[color] = color_weights.get(color, 0) + weight
        total_style_weight += weight
        if is_bold_span(span):
            bold_weight += weight

    color = None
    if color_weights:
        color, dominant_weight = max(color_weights.items(), key=lambda item: item[1])
        total_weight = sum(color_weights.values())
        if len(color_weights) > 1 and dominant_weight / max(1, total_weight) < 0.68:
            saturated_title_colors = [
                (weight, candidate)
                for candidate, weight in color_weights.items()
                if font_size and font_size >= 24 and color_saturation(candidate) > 0.22 and color_luminance(candidate) < 0.65
            ]
            color = max(saturated_title_colors, key=lambda item: item[0])[1] if saturated_title_colors else (0, 0, 0)
    return {"font_size": font_size, "color": color, "bold": bold_weight / max(1, total_style_weight) >= 0.35}


def is_bold_span(span: dict) -> bool:
    font_name = str(span.get("font", "")).lower()
    flags = int(span.get("flags", 0))
    return "bold" in font_name or bool(flags & 16)


def pdf_color_to_rgb(color_value: int) -> tuple[float, float, float]:
    value = int(color_value) & 0xFFFFFF
    return (
        ((value >> 16) & 255) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    )


def review_flags_for_replacement(source: str, translated: str, fitted: bool) -> dict:
    if not fitted:
        return {
            "status": "needs_review",
            "reason": "번역문이 원래 텍스트 박스 안에 완전히 들어가지 않습니다.",
        }

    source_key = re.sub(r"[^a-z0-9 ]+", " ", source.lower())
    source_key = " ".join(source_key.split())
    translated_text = " ".join(translated.split())
    translated_lower = translated_text.lower()

    if "policy window" in source_key and ("창문" in translated_text or "정책 중" in translated_text or "정책 기간" in translated_text):
        return {"status": "needs_review", "reason": "policy window는 '정책의 창'으로 고정해야 합니다."}

    if "stream" in source_key and ("개울" in translated_text or "스트림" in translated_text):
        return {"status": "needs_review", "reason": "정책학 표의 stream은 '흐름'으로 번역해야 합니다."}

    residual_english_terms = ["followed", "feedback effects", "policy window", "stream"]
    if any(term in translated_lower for term in residual_english_terms):
        return {"status": "needs_review", "reason": "mono 번역문에 영어 원문 또는 미번역 정책학 용어가 남아 있습니다."}

    confirmed_ambiguous_phrases = {"power of groups"}
    if source_key in confirmed_ambiguous_phrases or any(phrase in source_key for phrase in confirmed_ambiguous_phrases):
        return {"status": "candidate", "reason": "문서 내 병기어 기반 확정 용어입니다."}

    ambiguous_terms = {
        "actor": "다의어 Actor는 문맥에 따라 행위자/주체/참여자로 달라질 수 있습니다.",
        "actors": "다의어 Actors는 문맥에 따라 행위자/주체/참여자로 달라질 수 있습니다.",
        "value": "다의어 Value는 문맥에 따라 가치/값/중요도로 달라질 수 있습니다.",
        "power": "다의어 Power는 문맥에 따라 권력/권한/힘으로 달라질 수 있습니다.",
    }
    for term, reason in ambiguous_terms.items():
        if re.search(rf"\b{re.escape(term)}\b", source_key):
            return {"status": "needs_review", "reason": reason}

    return {"status": "candidate", "reason": "원문과 번역문 의미 및 레이아웃을 비교하세요."}


def render_health_policy_comparison_table_if_present(page, font_file: str | None) -> dict | None:
    page_text = page.get_text("text")
    required = [
        "Domestic Health Policy",
        "International Health Policy",
        "Global Health Policy",
        "Funding Source",
    ]
    if not all(term in page_text for term in required):
        return None

    table_rect = fitz.Rect(86.79, 123.98, 899.69, 464.79)
    x_edges = [86.79, 199.82, 433.11, 666.4, 899.69]
    y_edges = [123.98, 151.22, 212.46, 274.73, 343.56, 395.96, 464.79]
    rows = [
        ["차원", "국내 보건정책", "국제 보건정책", "글로벌 보건정책"],
        [
            "범위",
            "국내 인구 및\n보건의료 체계",
            "둘 이상의 국가 간\n국경 간 협력",
            "국경을 초월하고\n글로벌 거버넌스가\n필요한 건강 문제",
        ],
        [
            "행위자(Actors)",
            "중앙정부, 보건부처,\n지방당국",
            "중앙정부, 양자기관\n(예: KOICA, USAID),\n정부 간 파트너십",
            "다자기구(예: WHO, UN),\n글로벌 재단,\n초국가 NGO",
        ],
        [
            "정책수단",
            "국내 법령, 보험제도,\n공중보건 프로그램",
            "양자협정, 기술지원,\n역량 강화",
            "글로벌 조약, 재원 조달\n메커니즘(예: Global Fund,\nCOVAX), 조정 프레임워크",
        ],
        [
            "예",
            "한국 국민건강보험,\n미국 부담적정보험법\n(Affordable Care Act)",
            "한-베트남 보건협력\n프로젝트",
            "팬데믹 대비\n글로벌 전략",
        ],
        [
            "재원",
            "주로 국내 세금 및\n사회보험 기여금",
            "정부 간 원조,\n개발 보조금",
            "공동 글로벌 재원\n(예: GAVI, Global Fund),\n민간 자선, 회원 기여금",
        ],
    ]
    sources = [
        ["Dimension", "Domestic Health Policy", "International Health Policy", "Global Health Policy"],
        [
            "Scope",
            "National population and healthcare systems",
            "Cross-border cooperation between two or more countries",
            "Health issues that transcend borders and require global governance",
        ],
        [
            "Actors",
            "National governments, ministries of health, local authorities",
            "National governments, bilateral agencies (e.g., KOICA, USAID), intergovernmental partnerships",
            "Multilateral organizations (e.g., WHO, UN), global foundations, transnational NGOs",
        ],
        [
            "Policy Instruments",
            "National legislation, insurance schemes, public health programs",
            "Bilateral agreements, technical assistance, capacity building",
            "Global treaties, funding mechanisms (e.g., Global Fund, COVAX), coordinated frameworks",
        ],
        [
            "Examples",
            "Korea's National Health Insurance, U.S. Affordable Care Act",
            "Korea-Vietnam health cooperation projects",
            "Global Strategy on Pandemic Preparedness",
        ],
        [
            "Funding Source",
            "Primarily domestic taxes and social contributions",
            "Government-to-government aid, development grants",
            "Pooled global funding (e.g., GAVI, Global Fund), private philanthropy, member contributions",
        ],
    ]

    page.draw_rect(table_rect, color=None, fill=(0.992, 0.98, 0.965), overlay=True)
    header_fills = [
        (0.906, 0.902, 0.902),
        (0.867, 0.906, 0.965),
        (0.894, 0.902, 0.745),
        (0.878, 0.847, 0.722),
    ]
    row_header_fill = (0.906, 0.902, 0.902)
    body_fill = (0.992, 0.98, 0.965)
    replacements = []

    for row_index, row in enumerate(rows):
        y0 = y_edges[row_index]
        y1 = y_edges[row_index + 1]
        for col_index, text in enumerate(row):
            x0 = x_edges[col_index]
            x1 = x_edges[col_index + 1]
            rect = fitz.Rect(x0, y0, x1, y1)
            fill = header_fills[col_index] if row_index == 0 else row_header_fill if col_index == 0 else body_fill
            page.draw_rect(rect, color=None, fill=fill, overlay=True)
            padded = fitz.Rect(rect.x0 + 4, rect.y0 + 4, rect.x1 - 4, rect.y1 - 3)
            fit_result = insert_table_textbox(page, padded, text, font_file, row_index == 0 or col_index == 0)
            review_flags = review_flags_for_replacement(sources[row_index][col_index], text, fit_result["fitted"])
            replacements.append(
                {
                    "fitted": fit_result["fitted"],
                    "font_size": fit_result["font_size"],
                    "rect": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                    "source_preview": preview_text(sources[row_index][col_index]),
                    "translated_preview": preview_text(text),
                    "route": "table-redraw",
                    **review_flags,
                }
            )

    for y in y_edges:
        page.draw_line(fitz.Point(x_edges[0], y), fitz.Point(x_edges[-1], y), color=(0, 0, 0), width=0.8, overlay=True)

    return {"skip_rects": [table_rect], "replacements": replacements}


def render_punctuated_equilibrium_diagram_if_present(page, font_file: str | None) -> dict | None:
    page_text = page.get_text("text")
    required = [
        "Punctuated Equilibrium Theory",
        "Periods of equilibrium",
        "Periods of change",
        "Optimism Bias",
        "Confirmation Bias",
        "Hindsight Bias",
        "Status Quo Bias",
    ]
    if not all(term in page_text for term in required):
        return None

    replacements = []
    skip_rects = [
        fitz.Rect(80.3, 37.3, 899.7, 71.5),
        fitz.Rect(259.2, 135.0, 445.1, 159.5),
        fitz.Rect(390.0, 183.9, 535.9, 225.4),
        fitz.Rect(167.1, 185.1, 287.4, 226.7),
        fitz.Rect(161.6, 253.7, 522.6, 295.4),
        fitz.Rect(52.1, 276.3, 76.6, 340.9),
        fitz.Rect(645.1, 413.1, 780.0, 435.1),
        fitz.Rect(441.0, 496.1, 486.8, 520.6),
    ]

    page_bg = (0.992, 0.98, 0.965)
    light_fill = (0.933, 0.953, 0.98)
    callout_fill = (0.973, 0.91, 0.91)
    blue = (0.0, 0.44, 0.75)
    red = (1.0, 0.0, 0.0)
    navy = (0.122, 0.173, 0.561)

    items = [
        {
            "source": "Theory 4: Punctuated Equilibrium Theory",
            "target": "이론 4: 단절균형이론",
            "rect": fitz.Rect(80.3, 32.0, 640.0, 82.0),
            "mask": fitz.Rect(80.3, 32.0, 650.0, 82.0),
            "shape": "rect",
            "fill": page_bg,
            "color": navy,
            "size": 27.0,
            "align": fitz.TEXT_ALIGN_LEFT,
        },
        {
            "source": "Periods of equilibrium",
            "target": "균형 기간",
            "rect": fitz.Rect(193.1, 128.2, 511.3, 166.5),
            "shape": "rect",
            "fill": light_fill,
            "color": blue,
            "size": 18.0,
        },
        {
            "source": "Optimism Bias",
            "target": "낙관적 편향\n(Optimism Bias)",
            "rect": fitz.Rect(128.0, 174.7, 340.6, 238.6),
            "shape": "oval",
            "fill": light_fill,
            "color": (0, 0, 0),
            "size": 16.0,
        },
        {
            "source": "Confirmation Bias",
            "target": "확증 편향\n(Confirmation Bias)",
            "rect": fitz.Rect(349.2, 173.5, 596.2, 237.3),
            "shape": "oval",
            "fill": light_fill,
            "color": (0, 0, 0),
            "size": 16.0,
        },
        {
            "source": "Status Quo Bias",
            "target": "현상유지 편향\n(Status Quo Bias)",
            "rect": fitz.Rect(122.4, 243.3, 344.3, 307.1),
            "shape": "oval",
            "fill": light_fill,
            "color": (0, 0, 0),
            "size": 15.0,
        },
        {
            "source": "Hindsight Bias",
            "target": "사후확신 편향\n(Hindsight Bias)",
            "rect": fitz.Rect(351.1, 243.4, 581.7, 307.3),
            "shape": "oval",
            "fill": light_fill,
            "color": (0, 0, 0),
            "size": 15.0,
        },
        {
            "source": "Periods of change",
            "target": "변화 기간",
            "rect": fitz.Rect(592.7, 405.0, 832.3, 443.4),
            "shape": "rect",
            "fill": callout_fill,
            "color": red,
            "size": 16.0,
        },
        {
            "source": "Change",
            "target": "변화",
            "rect": fitz.Rect(52.1, 276.3, 76.6, 340.9),
            "mask": fitz.Rect(50.0, 273.0, 82.0, 345.0),
            "shape": "rect",
            "fill": page_bg,
            "color": (0, 0, 0),
            "size": 16.0,
        },
        {
            "source": "Time",
            "target": "시간",
            "rect": fitz.Rect(420.0, 492.0, 520.0, 528.0),
            "mask": fitz.Rect(415.0, 490.0, 525.0, 528.0),
            "shape": "rect",
            "fill": page_bg,
            "color": (0, 0, 0),
            "size": 18.0,
        },
    ]

    for item in items:
        rect = item["rect"]
        draw_rect = item.get("mask", rect)
        if item["shape"] == "oval":
            page.draw_oval(rect, color=None, fill=item["fill"], overlay=True)
            text_rect = fitz.Rect(rect.x0 + 12, rect.y0 + 12, rect.x1 - 12, rect.y1 - 10)
        else:
            page.draw_rect(draw_rect, color=None, fill=item["fill"], overlay=True)
            text_rect = fitz.Rect(rect.x0 + 8, rect.y0 + 5, rect.x1 - 8, rect.y1 - 4)

        fit_result = insert_layout_textbox(
            page,
            text_rect,
            item["target"],
            font_file,
            color=item["color"],
            align=item.get("align", fitz.TEXT_ALIGN_CENTER),
            source_size=item["size"],
        )
        review_flags = review_flags_for_replacement(item["source"], item["target"], fit_result["fitted"])
        replacements.append(
            {
                "fitted": fit_result["fitted"],
                "font_size": fit_result["font_size"],
                "rect": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                "source_preview": item["source"],
                "translated_preview": item["target"],
                "route": "diagram-redraw",
                **review_flags,
            }
        )

    return {"skip_rects": skip_rects, "replacements": replacements}


def render_bounded_rationality_image_text_if_present(page, font_file: str | None) -> dict | None:
    page_text = page.get_text("text")
    overlays = bounded_rationality_image_text_overlays_for_page_text(page_text)
    if not overlays:
        return None

    replacements = []
    for item in overlays:
        mask_rect = item["mask"]
        fill_color = item["fill"]
        page.draw_rect(mask_rect, color=None, fill=fill_color, overlay=True)
        fit_result = insert_layout_textbox(
            page,
            item.get("text_rect", mask_rect),
            item["target"],
            font_file,
            color=item.get("color", (0.05, 0.05, 0.05)),
            align=item.get("align", fitz.TEXT_ALIGN_CENTER),
            source_size=item.get("size", 10.0),
        )
        review_flags = review_flags_for_replacement(item["source"], item["target"], fit_result["fitted"])
        replacements.append(
            {
                "fitted": fit_result["fitted"],
                "font_size": fit_result["font_size"],
                "rect": [
                    round(mask_rect.x0, 2),
                    round(mask_rect.y0, 2),
                    round(mask_rect.x1, 2),
                    round(mask_rect.y1, 2),
                ],
                "source_preview": preview_text(item["source"]),
                "translated_preview": preview_text(item["target"]),
                "route": "figure-image-text",
                **review_flags,
            }
        )

    return {"replacements": replacements}


def bounded_rationality_image_text_overlays_for_page_text(page_text: str) -> list[dict]:
    text = " ".join(page_text.split()).lower()
    if not is_bounded_rationality_heuristic_slide(text):
        return []

    common = {
        "color": (0.03, 0.07, 0.14),
        "align": fitz.TEXT_ALIGN_CENTER,
    }

    if "representativeness heuristic" in text:
        return [
            {
                **common,
                "source": "Making Quick Judgments Based on Mental Prototypes",
                "target": "머릿속 전형에 근거한 빠른 판단",
                "mask": fitz.Rect(509.0, 130.0, 924.0, 161.0),
                "fill": (0.58, 0.76, 0.94),
                "size": 12.0,
            }
        ]

    if "availability heuristic" in text:
        return [
            {
                **common,
                "source": "What comes to mind quickly is deemed significant--sometimes incorrectly.",
                "target": "쉽게 떠오르는 것을 중요하다고 판단한다. 때로는 잘못 판단한다.",
                "mask": fitz.Rect(509.0, 142.0, 924.0, 166.0),
                "fill": (0.62, 0.86, 0.72),
                "size": 10.5,
            }
        ]

    if "anchoring heuristic" in text:
        return [
            {
                **common,
                "source": "That's like free money!",
                "target": "공짜 돈 같아!",
                "mask": fitz.Rect(500.0, 238.0, 656.0, 304.0),
                "fill": (1.0, 1.0, 0.98),
                "size": 13.0,
            },
            {
                **common,
                "source": "MUG",
                "target": "머그컵",
                "mask": fitz.Rect(530.0, 158.0, 582.0, 190.0),
                "fill": (0.96, 0.55, 0.06),
                "size": 8.0,
            },
            {
                **common,
                "source": "MUG",
                "target": "머그컵",
                "mask": fitz.Rect(758.0, 158.0, 810.0, 190.0),
                "fill": (0.96, 0.55, 0.06),
                "size": 8.0,
            },
        ]

    if "confirmation bias" in text and "optimism bias" in text:
        cream = (0.965, 0.95, 0.78)
        return [
            {
                **common,
                "source": "CONFIRMATION BIAS",
                "target": "확증 편향",
                "mask": fitz.Rect(522.0, 168.0, 735.0, 194.0),
                "fill": cream,
                "size": 14.0,
                "align": fitz.TEXT_ALIGN_LEFT,
            },
            {
                **common,
                "source": "SEEKING EVIDENCE THAT CONFIRMS OUR BELIEFS",
                "target": "자신의 믿음을 확인해 주는 증거만 찾음",
                "mask": fitz.Rect(522.0, 198.0, 842.0, 224.0),
                "fill": cream,
                "size": 9.0,
                "align": fitz.TEXT_ALIGN_LEFT,
            },
            {
                **common,
                "source": "THEY'RE AT IT AGAIN. I KNEW IT.",
                "target": "또 저러네. 그럴 줄 알았어.",
                "mask": fitz.Rect(522.0, 236.0, 650.0, 276.0),
                "fill": cream,
                "size": 8.5,
                "align": fitz.TEXT_ALIGN_LEFT,
            },
            {
                **common,
                "source": "WHAT RUBBISH ARE THEY SAYING NOW?",
                "target": "이번엔 또 무슨 헛소리야?",
                "mask": fitz.Rect(760.0, 236.0, 922.0, 286.0),
                "fill": cream,
                "size": 8.5,
                "align": fitz.TEXT_ALIGN_LEFT,
            },
            {
                **common,
                "source": "NEWS",
                "target": "뉴스",
                "mask": fitz.Rect(638.0, 286.0, 782.0, 331.0),
                "fill": (0.86, 0.84, 0.64),
                "size": 20.0,
            },
            {
                **common,
                "source": "...AND IGNORING INFORMATION THAT CONTRADICTS",
                "target": "...그리고 반대되는 정보는 무시함",
                "mask": fitz.Rect(560.0, 448.0, 922.0, 476.0),
                "fill": cream,
                "size": 9.0,
            },
        ]

    return []


def is_bounded_rationality_heuristic_slide(normalized_lower_text: str) -> bool:
    return (
        "theory 4: bounded rationality" in normalized_lower_text
        and "types of heuristics/biases associated with bounded rationality" in normalized_lower_text
    )


def insert_table_textbox(page, rect: fitz.Rect, text: str, font_file: str | None, strong: bool = False) -> dict:
    fontname = "qdt_table_font" if font_file else "helv"
    sizes = [10.5, 9.4, 8.4, 7.6, 6.8] if strong else [9.8, 8.8, 7.8, 7.0, 6.3]
    last_size = sizes[-1]
    for size in sizes:
        last_size = size
        kwargs = {
            "fontsize": size,
            "color": (0.03, 0.03, 0.03),
            "align": fitz.TEXT_ALIGN_LEFT,
        }
        if font_file:
            kwargs["fontname"] = fontname
            kwargs["fontfile"] = font_file
        else:
            kwargs["fontname"] = fontname

        remaining = page.insert_textbox(rect, text, **kwargs)
        if remaining >= 0:
            return {"fitted": True, "font_size": round(size, 2)}

    return {"fitted": False, "font_size": round(last_size, 2)}


def rects_overlap(first: fitz.Rect, second: fitz.Rect, min_ratio: float = 0.1) -> bool:
    intersection = first & second
    if intersection.is_empty:
        return False
    return intersection.get_area() / max(1, first.get_area()) >= min_ratio


def rect_center_inside(rect: fitz.Rect, container: fitz.Rect) -> bool:
    center = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
    return container.contains(center)


def preview_text(text: str, limit: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def summarize_layout_audit(page_audits: list[dict], source_path: str, output_path: str) -> dict:
    replacement_count = sum(len(page["replacements"]) for page in page_audits)
    needs_review_count = sum(
        1
        for page in page_audits
        for replacement in page["replacements"]
        if replacement.get("status") == "needs_review" or not replacement.get("fitted", False)
    )
    return {
        "source": source_path,
        "output": output_path,
        "route": "layout-preserve",
        "summary": {
            "page_count": len(page_audits),
            "replacement_count": replacement_count,
            "needs_review_count": needs_review_count,
            "status": "needs_review" if needs_review_count else "ok",
        },
        "pages": page_audits,
    }


def expand_rect(rect: fitz.Rect, bounds: fitz.Rect, padding: float) -> fitz.Rect:
    expanded = fitz.Rect(rect.x0 - padding, rect.y0 - padding, rect.x1 + padding, rect.y1 + padding)
    expanded.x0 = max(bounds.x0, expanded.x0)
    expanded.y0 = max(bounds.y0, expanded.y0)
    expanded.x1 = min(bounds.x1, expanded.x1)
    expanded.y1 = min(bounds.y1, expanded.y1)
    return expanded


def sample_background_color(page, rect: fitz.Rect) -> tuple[float, float, float]:
    sample_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    if sample_rect.is_empty or sample_rect.width < 1 or sample_rect.height < 1:
        return (1, 1, 1)

    try:
        pix = page.get_pixmap(clip=sample_rect, alpha=False, matrix=fitz.Matrix(1.5, 1.5))
    except Exception:
        return (1, 1, 1)

    samples = pix.samples
    if not samples:
        return (1, 1, 1)

    buckets: dict[tuple[int, int, int], int] = {}
    fallback_buckets: dict[tuple[int, int, int], int] = {}
    for index in range(0, len(samples), pix.n):
        red, green, blue = samples[index], samples[index + 1], samples[index + 2]
        bucket = (round(red / 16) * 16, round(green / 16) * 16, round(blue / 16) * 16)
        fallback_buckets[bucket] = fallback_buckets.get(bucket, 0) + 1
        is_near_white = red > 230 and green > 230 and blue > 230
        is_near_black = red < 25 and green < 25 and blue < 25
        if not is_near_white and not is_near_black:
            buckets[bucket] = buckets.get(bucket, 0) + 1

    selected_buckets = buckets or fallback_buckets
    if not selected_buckets:
        return (1, 1, 1)

    red, green, blue = max(selected_buckets.items(), key=lambda item: item[1])[0]
    return (min(red, 255) / 255, min(green, 255) / 255, min(blue, 255) / 255)


def sample_light_background_color(page, rect: fitz.Rect) -> tuple[float, float, float]:
    sample_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    if sample_rect.is_empty or sample_rect.width < 1 or sample_rect.height < 1:
        return (1, 1, 1)

    try:
        pix = page.get_pixmap(clip=sample_rect, alpha=False, matrix=fitz.Matrix(1.2, 1.2))
    except Exception:
        return (1, 1, 1)

    samples = pix.samples
    if not samples:
        return (1, 1, 1)

    light_buckets: dict[tuple[int, int, int], int] = {}
    fallback_buckets: dict[tuple[int, int, int], int] = {}
    for index in range(0, len(samples), pix.n):
        red, green, blue = samples[index], samples[index + 1], samples[index + 2]
        bucket = (round(red / 16) * 16, round(green / 16) * 16, round(blue / 16) * 16)
        fallback_buckets[bucket] = fallback_buckets.get(bucket, 0) + 1
        if red > 215 and green > 215 and blue > 215:
            light_buckets[bucket] = light_buckets.get(bucket, 0) + 1

    selected_buckets = light_buckets or fallback_buckets
    if not selected_buckets:
        return (1, 1, 1)

    red, green, blue = max(selected_buckets.items(), key=lambda item: item[1])[0]
    return (min(red, 255) / 255, min(green, 255) / 255, min(blue, 255) / 255)


def text_color_for_background(fill_color: tuple[float, float, float]) -> tuple[float, float, float]:
    luminance = color_luminance(fill_color)
    saturation = max(fill_color) - min(fill_color)
    if luminance < 0.72 or saturation > 0.28:
        return (1, 1, 1)
    return (0.05, 0.05, 0.05)


def color_luminance(color: tuple[float, float, float]) -> float:
    red, green, blue = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def color_saturation(color: tuple[float, float, float]) -> float:
    return max(color) - min(color)


def is_light_color(color: tuple[float, float, float] | None) -> bool:
    if color is None:
        return False
    return color_luminance(color) > 0.78


def choose_text_color(
    fill_color: tuple[float, float, float],
    source_color: tuple[float, float, float] | None,
) -> tuple[float, float, float]:
    if source_color is not None and color_distance(fill_color, source_color) > 0.18:
        return source_color
    return text_color_for_background(fill_color)


def color_distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return sum((first[index] - second[index]) ** 2 for index in range(3)) ** 0.5


def should_center_layout_text(source: str, rect: fitz.Rect, drawings: list[dict]) -> bool:
    if len(source.split()) > 5:
        return False
    if not background_fill_color(rect, drawings):
        return False
    return rect.width < 180 or rect.height > 24


def insert_layout_textbox(
    page,
    rect: fitz.Rect,
    text: str,
    font_file: str | None,
    color: tuple[float, float, float] = (0.05, 0.05, 0.05),
    align: int = fitz.TEXT_ALIGN_LEFT,
    source_size: float | None = None,
    bold: bool = False,
) -> dict:
    line_count = max(1, len(text.splitlines()))
    height_limited_size = max(5.2, (rect.height / max(1, line_count)) * 0.72)
    if source_size:
        if line_count == 1:
            base_size = min(source_size * 0.98, rect.height * 0.78)
        else:
            base_size = min(source_size * 0.92, height_limited_size)
    else:
        base_size = min(12.0, height_limited_size)
    base_size = max(5.0, base_size)
    fontname = "qdt_layout_font" if font_file else ("hebo" if bold else "helv")
    last_size = base_size

    sizes = [base_size, base_size * 0.92, base_size * 0.84, base_size * 0.76, base_size * 0.68, 5.0]
    for size in sizes:
        last_size = size
        kwargs = {
            "fontsize": size,
            "color": color,
            "align": align,
            "overlay": True,
        }
        if font_file:
            kwargs["fontname"] = fontname
            kwargs["fontfile"] = font_file
        else:
            kwargs["fontname"] = fontname

        remaining = page.insert_textbox(rect, text, **kwargs)
        if remaining >= 0:
            if bold and font_file:
                bold_rect = fitz.Rect(rect.x0 + 0.28, rect.y0, rect.x1 + 0.28, rect.y1)
                page.insert_textbox(bold_rect, text, **kwargs)
            return {"fitted": True, "font_size": round(size, 2), "bold": bold}

    return {"fitted": False, "font_size": round(last_size, 2), "bold": bold}


def render_pdf(input_path: Path, pages: list[dict], output_path: Path) -> None:
    doc = fitz.open()
    font_file = resolve_font_file()

    for page_data in pages:
        page = doc.new_page(width=842, height=595)
        y = 38
        title = f"{input_path.stem} - Page {page_data['page']}"
        y = insert_wrapped(page, title, 36, y, 770, 18, font_file, bold=True) + 12

        for block in page_data["blocks"]:
            paragraph = "\n".join(block["lines"])
            next_y = insert_wrapped(page, paragraph, 36, y, 770, 10.5, font_file)
            y = next_y + 8
            if y > 540:
                page = doc.new_page(width=842, height=595)
                y = 38

    doc.save(output_path)
    doc.close()


def insert_wrapped(page, text: str, x: float, y: float, width: float, size: float, font_file: str | None, bold: bool = False) -> float:
    fontname = "qdt_font_bold" if bold else "qdt_font"
    kwargs = {"fontsize": size, "color": (0.12, 0.09, 0.12), "align": fitz.TEXT_ALIGN_LEFT}
    if font_file:
        kwargs["fontname"] = fontname
        kwargs["fontfile"] = font_file
    else:
        kwargs["fontname"] = "helv"

    rect = fitz.Rect(x, y, x + width, y + 160)
    page.insert_textbox(rect, text, **kwargs)
    line_count = sum(max(1, (len(line) // 78) + 1) for line in text.splitlines() or [""])
    return y + line_count * size * 1.55


if __name__ == "__main__":
    raise SystemExit(main())
