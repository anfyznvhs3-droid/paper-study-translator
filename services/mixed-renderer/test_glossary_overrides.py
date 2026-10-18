"""Tests for glossary-backed term overrides in mixed-renderer (task T1.4).

Acceptance contract. GREEN when every test passes without editing this file.
Run from services/mixed-renderer:

    PYTHONPATH=".:../scholar-translator" python -m pytest test_glossary_overrides.py -q

The full existing suite must also stay green (regression gate):

    PYTHONPATH=".:../scholar-translator" python -m pytest -q
"""

import csv
import os

import qdt_mixed_renderer as mr


def _write_glossary(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "notes"])
        for row in rows:
            writer.writerow(row)


def test_load_glossary_overrides_normalizes_keys(tmp_path):
    path = tmp_path / "glossary.csv"
    _write_glossary(path, [["Failure Mode", "고장모드", ""], ["Action Priority", "조치 우선순위", "x"]])
    overrides = mr.load_glossary_overrides(path)
    assert overrides["failure mode"] == "고장모드"
    assert overrides["action priority"] == "조치 우선순위"


def test_load_glossary_overrides_missing_file_returns_empty(tmp_path):
    assert mr.load_glossary_overrides(tmp_path / "nope.csv") == {}


def test_load_glossary_overrides_merges_path_list(tmp_path):
    profile = tmp_path / "scholarly.csv"
    domain = tmp_path / "domain.csv"
    _write_glossary(profile, [["Abstract", "초록", "exact-heading"], ["FMEA", "프로필 FMEA", ""]])
    _write_glossary(domain, [["FMEA", "고장모드 및 영향분석(FMEA)", ""]])

    overrides = mr.load_glossary_overrides(os.pathsep.join([str(profile), str(domain)]))

    assert overrides["abstract"] == "초록"
    assert overrides["fmea"] == "고장모드 및 영향분석(FMEA)"


def test_load_glossary_overrides_skips_empty_source(tmp_path):
    path = tmp_path / "glossary.csv"
    _write_glossary(path, [["", "x", ""], ["control", "관리", ""]])
    assert mr.load_glossary_overrides(path) == {"control": "관리"}


def test_lookup_term_override_without_overrides_uses_builtin():
    # back-compat: no overrides arg -> existing TERM_OVERRIDES behavior unchanged
    assert mr.lookup_term_override("knowledge") == "지식"


def test_lookup_term_override_uses_injected_glossary():
    # a term not in TERM_OVERRIDES resolves via the injected glossary
    assert mr.lookup_term_override("control", overrides={"control": "관리"}) == "관리"


def test_lookup_term_override_glossary_takes_precedence_over_builtin():
    # "knowledge" is "지식" in TERM_OVERRIDES; glossary overrides it when provided
    assert mr.lookup_term_override("knowledge", overrides={"knowledge": "지식정보"}) == "지식정보"
