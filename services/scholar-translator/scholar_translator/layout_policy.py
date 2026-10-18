from __future__ import annotations


def reserved_layout_classes(translate_table_text: bool = True) -> set[str]:
    """Return layout classes that should be preserved as non-translatable regions."""
    reserved = {"figure", "isolate_formula", "formula_caption"}
    if not translate_table_text:
        reserved.add("table")
    return reserved


def should_translate_table_text(envs: dict | None = None) -> bool:
    if not envs:
        return False
    raw = envs.get("QDT_TRANSLATE_TABLE_TEXT")
    if raw is None:
        return False
    return str(raw).strip().casefold() in {"1", "true", "on", "yes"}

def is_formula_font(font: str) -> bool:
    import re
    if isinstance(font, bytes):
        font = font.decode("utf-8", errors="ignore")
    font = font.split("+")[-1]
    # Italic is emphasis in ordinary prose. Only mathematical/code font families
    # are reserved; unicode math and layout formula boxes are checked separately.
    return bool(re.match(r"(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Sym|.*Math)",font))


def text_color_operator(color) -> str:
    """Preserve native Gray/RGB/CMYK text fill, resetting black when absent."""
    import math
    values=(color,) if isinstance(color,(float,int)) else color
    if not isinstance(values,(tuple,list)) or len(values) not in (1,3,4):
        return "0 g"
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
        return "0 g"
    operator={1:"g",3:"rg",4:"k"}[len(values)]
    return " ".join(f"{min(1,max(0,v)):g}" for v in values)+" "+operator

def is_nontext_fragment(text: str) -> bool:
    """Page numbers, punctuation and protected formula placeholders need no API."""
    import re
    visible=re.sub(r"\{\s*v\d+\s*\}", "", text, flags=re.IGNORECASE)
    return not any(character.isalpha() for character in visible)


def numeric_token_at(text: str, index: int) -> str:
    """Keep a complete numeric literal together when a line wraps."""
    import re
    if index and (text[index-1].isalnum() and text[index-1].isascii()
                  or text[index-1] in ".,"):
        return ""
    match=re.match(r"[-+]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?(?:%[pP]?|‰)?",text[index:])
    return match.group() if match else ""
