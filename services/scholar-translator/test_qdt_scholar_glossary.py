"""Tests for the glossary-aware scholar_translator wrapper.

The wrapper applies the user-approved domain glossary to the machine (Google)
ScholarTranslator path without modifying the vendored scholar_translator source.

Run from services/scholar-translator:

    python -m pytest test_qdt_scholar_glossary.py -q
"""

import csv
import os

import qdt_scholar_with_glossary as w


def _write_glossary(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "notes"])
        for row in rows:
            writer.writerow(row)


def test_load_glossary_overrides_normalizes_and_skips_incomplete(tmp_path):
    path = tmp_path / "glossary.csv"
    _write_glossary(
        path,
        [
            ["FMEA", "고장모드 및 영향분석(FMEA)", ""],
            ["", "x", "no source"],
            ["LonelySource", "", "no target"],
            ["Control Plan", "관리계획서(Control Plan)", "keep"],
        ],
    )
    overrides = w.load_glossary_overrides(str(path))
    assert overrides == {
        "fmea": "고장모드 및 영향분석(FMEA)",
        "control plan": "관리계획서(Control Plan)",
    }


def test_load_glossary_overrides_missing_file_is_empty(tmp_path):
    assert w.load_glossary_overrides(str(tmp_path / "nope.csv")) == {}


def test_load_glossary_overrides_merges_profile_and_domain_csvs(tmp_path):
    profile = tmp_path / "scholarly.csv"
    domain = tmp_path / "domain.csv"
    _write_glossary(profile, [["Abstract", "초록", "exact-heading"], ["FMEA", "프로필 FMEA", ""]])
    _write_glossary(domain, [["FMEA", "고장모드 및 영향분석(FMEA)", ""]])

    spec = os.pathsep.join([str(profile), str(domain)])
    policy = w.load_glossary_policy(spec)

    assert policy.overrides["abstract"] == "초록"
    assert policy.overrides["fmea"] == "고장모드 및 영향분석(FMEA)"
    assert "abstract" in policy.exact_only
    assert "fmea" not in policy.exact_only


def test_lookup_direct_override_matches_whole_segment_with_punctuation():
    ov = {"fmea": "고장모드 및 영향분석(FMEA)"}
    assert w.lookup_direct_override("FMEA", ov) == "고장모드 및 영향분석(FMEA)"
    assert w.lookup_direct_override("FMEA.", ov) == "고장모드 및 영향분석(FMEA)."
    assert w.lookup_direct_override("some running text", ov) is None


def test_apply_embedded_overrides_rewrites_acronym_with_korean_particle():
    # Google commonly leaves acronyms in place: "FMEA는 ...". ASCII-boundary
    # lookarounds must rewrite it even though 는 is a regex word char.
    ov = {"fmea": "고장모드 및 영향분석(FMEA)"}
    out = w.apply_embedded_overrides("The FMEA shall be reviewed.", "FMEA는 검토되어야 한다.", ov)
    assert out == "고장모드 및 영향분석(FMEA)는 검토되어야 한다."


def test_apply_embedded_overrides_does_not_split_longer_ascii_runs():
    ov = {"fmea": "X"}
    # source mentions the term so the loop runs, but XFMEAS must stay intact.
    assert w.apply_embedded_overrides("fmea note", "그대로 XFMEAS 유지", ov) == "그대로 XFMEAS 유지"


def test_apply_embedded_overrides_skips_exact_only_profile_terms():
    ov = {"abstract": "초록", "fmea": "고장모드 및 영향분석(FMEA)"}
    exact_only = {"abstract"}

    out = w.apply_embedded_overrides(
        "This abstract model mentions FMEA.",
        "abstract model mentions FMEA.",
        ov,
        exact_only=exact_only,
    )

    assert out == "abstract model mentions 고장모드 및 영향분석(FMEA)."


def test_collapse_duplicate_korean_parenthetical():
    assert w.collapse_duplicate_korean_parenthetical("관리계획서(관리계획서)") == "관리계획서"
    assert w.collapse_duplicate_korean_parenthetical("관리계획서(Control Plan)") == "관리계획서(Control Plan)"


def test_install_glossary_patch_wraps_translate_and_noops_when_empty():
    from scholar_translator.translator import BaseTranslator

    original = BaseTranslator.translate
    try:
        assert w.install_glossary_patch({}) is False
        assert BaseTranslator.translate is original

        assert w.install_glossary_patch({"fmea": "고장모드 및 영향분석(FMEA)"}) is True
        assert getattr(BaseTranslator.translate, "__qdt_glossary_patched__", False) is True
    finally:
        BaseTranslator.translate = original
