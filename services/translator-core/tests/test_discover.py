"""Tests for parsing agent term-discovery responses (task T2.4, testable slice).

The agent (2nd pass) returns a JSON array of candidate terms. This parses that
response into candidate dicts. The prompt design, the actual LLM call, and the
quality eval are NOT here (fuzzy oracle, handled separately).

    cd services/translator-core && PYTHONPATH=src python -m pytest tests/test_discover.py -q
    cd services/translator-core && PYTHONPATH=src python -m pytest tests/ -q   # regression
"""

from qdt.discover import parse_candidates


def test_parse_candidates_from_clean_json():
    raw = '[{"source":"control","suggested_target":"대조군","reason":"medical","confidence":"high"}]'
    cands = parse_candidates(raw)
    assert len(cands) == 1
    assert cands[0]["source"] == "control"
    assert cands[0]["suggested_target"] == "대조군"
    assert cands[0]["confidence"] == "high"


def test_parse_candidates_empty_array():
    assert parse_candidates("[]") == []


def test_parse_candidates_extracts_array_from_surrounding_prose():
    # agents sometimes wrap the JSON in explanation text
    raw = 'Here are the terms:\n[{"source":"FMEA","suggested_target":"고장모드","reason":"x","confidence":"low"}]\nDone.'
    cands = parse_candidates(raw)
    assert cands[0]["source"] == "FMEA"


def test_parse_candidates_skips_items_missing_required_fields():
    raw = '[{"source":"ok","suggested_target":"좋음","reason":"r","confidence":"low"},{"reason":"no source"}]'
    cands = parse_candidates(raw)
    assert [c["source"] for c in cands] == ["ok"]


def test_parse_candidates_returns_empty_on_garbage():
    assert parse_candidates("not json at all") == []
