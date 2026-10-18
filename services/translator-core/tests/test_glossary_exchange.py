import pytest

from qdt.glossary_exchange import (
    export_glossary,
    import_glossary_entries,
    parse_glossary_exchange,
)
from qdt.memory import DomainMemoryStore, GlossaryEntry


@pytest.fixture
def store(tmp_path):
    memory = DomainMemoryStore(tmp_path)
    memory.create_domain("Quality Manufacturing", "quality-manufacturing")
    memory.create_domain("Software Manual", "software-manual")
    return memory


def test_export_omegat_glossary_uses_tab_delimited_utf8_rows():
    text = export_glossary(
        [
            GlossaryEntry("FMEA", "고장모드 및 영향분석(FMEA)", "approved, IATF"),
            GlossaryEntry("Control Plan", "관리계획서(Control Plan)", ""),
        ],
        "omegat",
    )

    assert text.splitlines() == [
        "FMEA\t고장모드 및 영향분석(FMEA)\tapproved, IATF",
        "Control Plan\t관리계획서(Control Plan)\t",
    ]


def test_import_omegat_defaults_to_candidates_without_confirming_terms(store):
    entries = parse_glossary_exchange(
        "FMEA\t고장모드 및 영향분석(FMEA)\tfrom vendor\n"
        "Control Plan\t관리계획서(Control Plan)\n",
        "omegat",
    )

    result = import_glossary_entries(store, "quality-manufacturing", entries, "candidates")

    assert result == {"imported": 2, "mode": "candidates"}
    assert store.load_glossary("quality-manufacturing") == []
    candidates = store.list_candidates("quality-manufacturing")
    assert {candidate.source for candidate in candidates} == {"FMEA", "Control Plan"}
    assert {candidate.status for candidate in candidates} == {"candidate"}


def test_import_omegat_confirmed_mode_upserts_confirmed_glossary(store):
    store.add_term("quality-manufacturing", "fmea", "old")
    entries = parse_glossary_exchange(
        "FMEA\t고장모드 및 영향분석(FMEA)\ttrusted\n",
        "omegat",
    )

    result = import_glossary_entries(store, "quality-manufacturing", entries, "confirmed")

    assert result == {"imported": 1, "mode": "confirmed"}
    assert store.load_glossary("quality-manufacturing") == [
        GlossaryEntry("fmea", "고장모드 및 영향분석(FMEA)", "trusted")
    ]
    assert store.list_decisions("quality-manufacturing")[-1].status == "confirmed"


def test_export_tbx_contains_source_target_and_notes():
    text = export_glossary(
        [GlossaryEntry("release", "출하 승인", "manufacturing context")],
        "tbx",
    )

    assert "<tbx" in text
    assert "<term>release</term>" in text
    assert "<term>출하 승인</term>" in text
    assert "manufacturing context" in text


def test_import_tbx_preserves_korean_terms_and_notes(store):
    tbx = """<?xml version='1.0' encoding='utf-8'?>
<tbx>
  <body>
    <termEntry id="term-1">
      <langSet xml:lang="en">
        <tig><term>disposition</term></tig>
      </langSet>
      <langSet xml:lang="ko">
        <tig><term>처분 판정</term></tig>
      </langSet>
      <descrip type="note">MRB, quality</descrip>
    </termEntry>
  </body>
</tbx>
"""
    entries = parse_glossary_exchange(tbx, "tbx")

    assert entries == [GlossaryEntry("disposition", "처분 판정", "MRB, quality")]


def test_import_one_domain_does_not_change_another_domain(store):
    entries = [GlossaryEntry("release", "출하 승인", "quality")]

    import_glossary_entries(store, "quality-manufacturing", entries, "confirmed")

    assert store.load_glossary("quality-manufacturing") == [
        GlossaryEntry("release", "출하 승인", "quality")
    ]
    assert store.load_glossary("software-manual") == []


def test_invalid_format_and_mode_raise_value_error(store):
    with pytest.raises(ValueError, match="Unsupported glossary exchange format"):
        export_glossary([], "xlsx")

    with pytest.raises(ValueError, match="Unsupported import mode"):
        import_glossary_entries(store, "quality-manufacturing", [], "trusted")

