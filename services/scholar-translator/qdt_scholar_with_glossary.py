#!/usr/bin/env python3
"""Glossary-aware entrypoint for scholar_translator.

scholar_translator is vendored under AGPL and the roadmap (T3.1) wants its source
left untouched. So instead of editing it, this wrapper monkey-patches
``BaseTranslator.translate`` at runtime to apply the user-approved domain glossary,
then delegates to ``scholar_translator.cli.main()``.

The glossary CSV path is supplied via the ``QDT_GLOSSARY`` environment variable.
With no glossary (env unset / file missing / empty) the wrapper is a transparent
passthrough — identical to invoking ``python -m scholar_translator.cli``.

The override logic mirrors the Google path of services/mixed-renderer so the
default (dual / non-mixed) ScholarTranslator path enforces the same terms the
MixedRenderer path already does. Overrides are a *machine/Google*-path mechanism:
Google leaves acronyms (e.g. "FMEA") untranslated, and we rewrite them. It is NOT
meant to run on top of agent (codex/claude) output that already applied the
glossary via the prompt, which would double-substitute.
"""
from __future__ import annotations

import csv
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _normalize_key(text: str) -> str:
    key = re.sub(r"[^a-z0-9 -]+", "", text.lower())
    return " ".join(key.split())


@dataclass(frozen=True)
class GlossaryPolicy:
    overrides: dict[str, str] = field(default_factory=dict)
    exact_only: set[str] = field(default_factory=set)


def _split_glossary_paths(glossary_csv: str) -> list[Path]:
    return [Path(part) for part in glossary_csv.split(os.pathsep) if part.strip()]


def _is_exact_only_row(row: dict[str, str]) -> bool:
    notes = " ".join(
        str(row.get(key) or "").casefold()
        for key in ("notes", "note", "scope", "policy")
    )
    return "exact" in notes or "heading" in notes


def load_glossary_policy(glossary_csv: str) -> GlossaryPolicy:
    """Read one or more CSV files into overrides plus exact-only policy."""
    overrides: dict[str, str] = {}
    exact_only: set[str] = set()

    for path in _split_glossary_paths(glossary_csv):
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source = (row.get("source") or "").strip()
                target = (row.get("target") or "").strip()
                if not source or not target:
                    continue
                key = _normalize_key(source)
                if not key:
                    continue
                overrides[key] = target
                if _is_exact_only_row(row):
                    exact_only.add(key)
                else:
                    exact_only.discard(key)

    return GlossaryPolicy(overrides=overrides, exact_only=exact_only)


def load_glossary_overrides(glossary_csv: str) -> dict[str, str]:
    """Read source,target rows into a normalized-key -> target map."""
    return load_glossary_policy(glossary_csv).overrides


def collapse_duplicate_korean_parenthetical(text: str) -> str:
    """"X (X)" -> "X" so an override followed by Google's echo doesn't double up."""
    normalized = text.strip()
    match = re.fullmatch(r"(.+?)\s*\(\s*(.+?)\s*\)", normalized)
    if not match:
        return text
    left, right = match.groups()
    if left.replace(" ", "") == right.replace(" ", ""):
        return left.strip()
    return text


def lookup_direct_override(text: str, overrides: dict[str, str]) -> str | None:
    """Whole-segment match: the entire text (ignoring surrounding punctuation) is a term."""
    decorated = re.fullmatch(
        r"([^A-Za-z0-9]*)([A-Za-z][A-Za-z0-9 -]*[A-Za-z]|[A-Za-z])([^A-Za-z0-9]*)", text
    )
    if decorated:
        prefix, core, suffix = decorated.groups()
        core_key = _normalize_key(core)
        if core_key in overrides:
            return f"{prefix}{overrides[core_key]}{suffix}"
    return overrides.get(_normalize_key(text))


def apply_embedded_overrides(
    source: str,
    translated: str,
    overrides: dict[str, str],
    *,
    exact_only: set[str] | None = None,
) -> str:
    """Rewrite any source term left untranslated inside the output.

    Boundaries are ASCII-only lookarounds rather than ``\\b``: Python's ``\\b``
    treats Hangul as a word char, so ``\\bFMEA\\b`` would NOT match ``FMEA는``
    (acronym + Korean 조사) — the most common machine-translation leftover. We
    only avoid splitting runs of ASCII letters/digits, so ``FMEA는`` matches but
    ``XFMEA`` / ``FMEAS`` do not.
    """
    exact_only = exact_only or set()
    source_lower = source.lower()
    for english, korean in overrides.items():
        if english in exact_only:
            continue
        if english not in source_lower:
            continue
        if source_lower.strip() == english:
            return korean
        pattern = r"(?<![A-Za-z0-9])" + re.escape(english) + r"(?![A-Za-z0-9])"
        translated = re.sub(pattern, korean, translated, flags=re.IGNORECASE)
    return translated


def install_glossary_patch(overrides: dict[str, str], exact_only: set[str] | None = None) -> bool:
    """Wrap BaseTranslator.translate. Returns True if a patch was installed."""
    if not overrides:
        return False

    from scholar_translator.translator import BaseTranslator

    original_translate = BaseTranslator.translate

    def patched_translate(self, text, *args, **kwargs):
        direct = lookup_direct_override(text, overrides)
        if direct is not None:
            return collapse_duplicate_korean_parenthetical(direct)
        translated = original_translate(self, text, *args, **kwargs)
        translated = apply_embedded_overrides(text, translated, overrides, exact_only=exact_only)
        return collapse_duplicate_korean_parenthetical(translated)

    patched_translate.__qdt_glossary_patched__ = True  # type: ignore[attr-defined]
    BaseTranslator.translate = patched_translate  # type: ignore[method-assign]
    return True


def main() -> int:
    glossary_csv = os.environ.get("QDT_GLOSSARY", "").strip()
    policy = load_glossary_policy(glossary_csv) if glossary_csv else GlossaryPolicy()
    if install_glossary_patch(policy.overrides, policy.exact_only):
        print(
            f"[qdt] glossary patch active: {len(policy.overrides)} term(s) from {glossary_csv}",
            file=sys.stderr,
        )

    from scholar_translator.cli import main as scholar_main

    return scholar_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
