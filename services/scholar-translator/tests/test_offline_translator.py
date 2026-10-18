"""Regression tests for the offline translator's missing-key handling.

A render-time source that is absent from the offline translation map must NOT
raise: converter.py wraps the per-paragraph worker in an unbounded
`@retry(wait=wait_fixed(1))`, so a raised exception there loops forever and
hangs the whole render. The offline translator falls back to the source text
instead, so an incomplete map degrades gracefully rather than deadlocking.
"""

import json

from scholar_translator.scholarly_cleanup import lookup_scholarly_phrase_override
from scholar_translator.table_structure import lookup_table_cell_override
from scholar_translator.translator import OfflineTranslator


def _make_offline(tmp_path, rows):
    map_path = tmp_path / "translation-map.jsonl"
    with map_path.open("w", encoding="utf-8") as fh:
        for source, translation in rows:
            fh.write(json.dumps({"source": source, "translation": translation}, ensure_ascii=False) + "\n")
    return OfflineTranslator(
        "en",
        "ko",
        "",
        envs={"OFFLINE_TRANSLATION_MAP": str(map_path)},
        ignore_cache=True,
    )


def test_offline_returns_mapped_translation(tmp_path):
    translator = _make_offline(tmp_path, [("Metric", "측정 지표")])
    assert translator.do_translate("Metric") == "측정 지표"


def test_offline_missing_source_falls_back_to_source_without_raising(tmp_path):
    translator = _make_offline(tmp_path, [("Metric", "측정 지표")])
    # Not in the map. Must return the source unchanged, never raise — otherwise
    # converter.py's unbounded retry worker deadlocks the render.
    assert translator.do_translate("Unmapped paragraph {v3}") == "Unmapped paragraph {v3}"


def test_offline_map_render_bypasses_translation_cache(tmp_path):
    # The persistent sqlite cache is keyed on the map PATH, not its contents, so
    # a stale value from an earlier run on the same path could shadow the map and
    # render the original text. An offline-map render must ignore the cache. Note:
    # ignore_cache is NOT passed here; map presence alone must force the bypass.
    map_path = tmp_path / "translation-map.jsonl"
    map_path.write_text(
        json.dumps({"source": "Metric", "translation": "측정 지표"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    translator = OfflineTranslator("en", "ko", "", envs={"OFFLINE_TRANSLATION_MAP": str(map_path)})
    assert translator.ignore_cache is True


def test_compound_header_override_does_not_match_body_prose():
    # HEADER_TRANSLATIONS has short generic keys ("time", "current", "up", "down").
    # A body sentence containing them must NOT be treated as a table-header override,
    # otherwise the converter skips real translation and the body stays English.
    prose = (
        "This synthetic benchmark paragraph describes a controlled evaluation "
        "scenario where the current process takes time to set up and break down."
    )
    assert lookup_scholarly_phrase_override(prose) is None


def test_compound_header_override_still_translates_real_header():
    # A short, genuine compound table header must still be overridden/translated.
    assert lookup_table_cell_override("Down-slope time") is not None


def test_compound_header_override_never_substitutes_inside_a_word():
    # FAILURE MODE: the compound-header path replaced HEADER_TRANSLATIONS keys as
    # unanchored substrings, so the generic key "up" matched INSIDE longer words
    # ("setUP" -> "set상승", "UPdated" -> "상승dated"). That both corrupted the
    # render AND short-circuited real translation (a non-None override means the
    # converter never sends the cell to the agent / offline map). Such cells must
    # return None so they route to real translation, never an intra-word splice.
    for cell in (
        "Daily setup verification; control sample retained",
        "Characteristic register updated after drawing release",
        "Setup approval required",
    ):
        override = lookup_table_cell_override(cell)
        assert override is None or "상승" not in override, override


def test_compound_header_override_matches_token_next_to_punctuation():
    # The anchor must only forbid LETTER-adjacent matches; header tokens adjacent to
    # hyphens / dots / spaces must still translate ("variant no." -> "변형 번호").
    assert lookup_table_cell_override("Variant no.") is not None
    assert lookup_table_cell_override("Up-slope") is not None


def test_key_line_override_still_translates_via_shared_anchored_helper():
    # _translate_key_line shares the same anchored-replacement helper as the
    # compound-header path; its phrase keys must keep translating (and "Key:"
    # becomes "키:"), so the shared anchoring did not break the legend path.
    out = lookup_table_cell_override("Key: green color-OK")
    assert out is not None
    assert "녹색-OK" in out
    assert "키:" in out


def test_task_extraction_accumulates_across_translator_instances(tmp_path):
    # One extraction run constructs several OfflineTranslator instances (per page).
    # A later instance must not truncate the shared task file and wipe earlier tasks.
    import scholar_translator.translator as translator_module

    translator_module.OfflineTranslator._prepared_task_paths.clear()
    task_path = tmp_path / "tasks.jsonl"

    def make_extractor():
        return OfflineTranslator("en", "ko", "", envs={"OFFLINE_TASK_OUTPUT": str(task_path)})

    first = make_extractor()
    first.do_translate("First body paragraph from page one.")

    second = make_extractor()  # constructed mid-run; must preserve page-one task
    second.do_translate("Second body paragraph from page two.")

    sources = {
        json.loads(line)["source"]
        for line in task_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert "First body paragraph from page one." in sources
    assert "Second body paragraph from page two." in sources
