from scholar_translator.scholarly_cleanup import (
    is_references_heading,
    lookup_scholarly_phrase_override,
    prepare_scholarly_source,
    should_drop_isolated_table_label,
    should_preserve_reference_text,
    stitch_scholarly_fragments,
)
from scholar_translator.audit import generate_review_items


def test_prepare_scholarly_source_removes_table_label_contamination():
    source = (
        "Figure 8 presents the cumulative temperature curves for three selected "
        "mesh points of the model (2614, 2801, D 3088) along with the weld "
        "current waveforms. The results concern two variants, namely V3 and D"
    )

    cleaned = prepare_scholarly_source(source)

    assert "D 3088" not in cleaned.text
    assert "(2614, 2801, 3088)" in cleaned.text
    assert cleaned.text.endswith("namely V3 and")
    assert "table_label_contamination" in cleaned.flags


def test_prepare_scholarly_source_repairs_truncated_and_fragment():
    source = "Figure 8 presents mesh points of the model (2614, 2801, an"

    cleaned = prepare_scholarly_source(source)

    assert cleaned.text.endswith("(2614, 2801, and")
    assert "truncated_word_fragment" in cleaned.flags


def test_drop_isolated_table_label_letters():
    assert should_drop_isolated_table_label("d")
    assert should_drop_isolated_table_label("D")
    assert should_drop_isolated_table_label("D)") is False
    assert should_drop_isolated_table_label("DCc") is False


def test_scholarly_phrase_overrides_for_back_matter():
    assert lookup_scholarly_phrase_override(
        "Conflict of interest The authors declare that they have no competing interests."
    ) == "이해관계 충돌 저자들은 경쟁 관계가 없음을 선언합니다."
    assert lookup_scholarly_phrase_override(
        "Data availability This article does not contain results taken from external databases. All source data is provided through citations to the relevant articles."
    ).startswith("데이터 가용성")


def test_scholarly_phrase_override_translates_abstract_heading_only():
    assert lookup_scholarly_phrase_override("Abstract") == "초록"
    assert lookup_scholarly_phrase_override("Abstract:") == "초록:"
    assert lookup_scholarly_phrase_override("This abstract model explains human error.") is None


def test_scholarly_phrase_override_for_welding_abbreviations_block():
    source = (
        "Upslope Welding current upslope time-in electrical engineering referred to as “rise time” "
        "Downslope Welding current downslope time-in electrical engineering referred to as “fall time” "
        "BWC Best welding conditions TCFT Total current flow time MCPT Main current period time "
        "DCimp Pulsed welding DC AC 50 Hz Alternating welding current with a frequency of 50 Hz "
        "DCc Direct welding current of constant value"
    )

    translated = lookup_scholarly_phrase_override(source)

    assert translated is not None
    assert "Upslope\t용접 전류 상승 시간" in translated
    assert "Downslope\t용접 전류 하강 시간" in translated
    assert "BWC\t최적 용접 조건" in translated
    assert "TCFT\t총 전류 통전 시간" in translated
    assert "MCPT\t주전류 구간 시간" in translated
    assert "DCimp\t펄스 직류 용접" in translated
    assert "AC 50 Hz\t주파수 50 Hz의 교류 용접 전류" in translated
    assert "DCc\t일정값 직류 용접 전류" in translated


def test_scholarly_phrase_override_repairs_fragmented_table_caption():
    source = "Table{v2}4 Resistance wel ding cycle parameters and characteristic process parameters (V ariant 5, FEM)"

    translated = lookup_scholarly_phrase_override(source)

    assert translated == "표{v2}4 저항 용접 사이클 매개변수 및 특성 공정 매개변수(변형 5, FEM)"


def test_scholarly_phrase_override_repairs_fragmented_back_matter():
    assert lookup_scholarly_phrase_override(
        "Data availability This article does not contain results taken from external databases. All source data is provided throug"
    ) == "데이터 가용성 이 논문은 외부 데이터베이스 결과를 포함하지 않습니다. 모든 원천 데이터는 관련 논문 인용으로 제공됩니다."
    assert lookup_scholarly_phrase_override("h") == ""
    assert lookup_scholarly_phrase_override("Conflict o") == "이해관계 충돌"
    assert lookup_scholarly_phrase_override(
        "f interest The authors declare that they have no competing in"
    ) == "저자들은 경쟁 관계가 없음을 선언합니다."
    assert lookup_scholarly_phrase_override("terests.") == ""


def test_scholarly_phrase_override_uses_generic_table_cell_labels():
    assert lookup_scholarly_phrase_override("Weld rupture force") == "용접부 파단 하중"
    assert lookup_scholarly_phrase_override("Average current") == "평균 전류"
    assert lookup_scholarly_phrase_override("Key: MCPT-main current period time") == "키: MCPT-주전류 구간 시간"


def test_stitch_scholarly_fragments_keeps_list_shape():
    sources = [
        "Table{v2}4 Resistance wel",
        "ding cycle parameters and characteristic process parameters (V",
        "ariant 5, FEM)",
        "Data availability This article does not contain results taken from external databases. All source data is provided throug",
        "h",
        "citations to the relevant articles.",
        "Figure 8 results concern two variants, namely V3 and",
        "V9.",
        "Supplementary Information The online version contains supplementary material available at https://doi.org/10.1007/s4",
        "3",
        "4 5 2 - 0 2 5 - 0 1 4 0 1 - 5.",
    ]

    stitched = stitch_scholarly_fragments(sources)

    assert stitched[0] == "Table{v2}4 Resistance welding cycle parameters and characteristic process parameters (Variant 5, FEM)"
    assert stitched[1] == ""
    assert stitched[2] == ""
    assert stitched[3] == "Data availability This article does not contain results taken from external databases. All source data is provided through citations to the relevant articles."
    assert stitched[4] == ""
    assert stitched[5] == ""
    assert stitched[6].endswith("namely V3 and V9.")
    assert stitched[7] == ""
    assert stitched[8].endswith("https://doi.org/10.1007/s43452-025-01401-5")
    assert stitched[9] == ""
    assert stitched[10] == ""


def test_prepare_scholarly_source_repairs_spaced_doi_url():
    source = (
        "Supplementary Information The online version contains supplementary "
        "material available at h t t p s://do i . o r g / 1 0 . 1 0 0 7 / "
        "s 4 3 4 5 2 - 0 2 5 - 0 1 4 0 1 - 5."
    )

    cleaned = prepare_scholarly_source(source)

    assert "https://doi.org/10.1007/s43452-025-01401-5" in cleaned.text
    assert "spaced_doi_repaired" in cleaned.flags


def test_prepare_scholarly_source_repairs_other_spaced_doi_urls():
    source = "Available at h t t p s : / / d o i . o r g / 1 0 . 5 5 5 5 / a b c - 1 2 3."

    cleaned = prepare_scholarly_source(source)

    assert "https://doi.org/10.5555/abc-123" in cleaned.text


def test_reference_heading_and_preservation_policy():
    assert is_references_heading("References")
    assert is_references_heading("REFERENCES")
    assert not is_references_heading("References to Figure 8")

    assert should_preserve_reference_text(True, "Smith J. Welding science. 2024.")
    assert should_preserve_reference_text(False, "Smith J. Welding science. 2024.") is False


def test_audit_flags_scholarly_pdf_artifacts():
    items = generate_review_items(
        19,
        "Conflict of interest The authors declare no competing interests.",
        "갈등 오 f 관심 저자는 경쟁 관계가 없음을 선언합니다.",
    )

    assert any(item["kind"] == "scholarly_pdf_artifact" for item in items)


def test_audit_flags_abstract_heading_mistranslation():
    items = generate_review_items(1, "Abstract", "추상적인")

    assert any(item["kind"] == "scholarly_heading_mistranslation" for item in items)


def test_audit_flags_acronym_explanation_left_in_english():
    source = (
        "SHERPA is a method used to identify, predict, and reduce the potential "
        "for human error in a system."
    )
    translated = (
        "CREAM(인지 신뢰성 및 오류 분석 방법)은 인간 신뢰성을 평가합니다. "
        "SHERPA is a method used to identify, predict, and reduce the potential "
        "for human error in a system."
    )

    items = generate_review_items(1, source, translated)

    assert any(item["kind"] == "acronym_explanation_residual" for item in items)


def test_audit_flags_source_sentence_left_in_english():
    source = (
        "This research aims to analyze the role of human error in the production "
        "process using various analytical methods found in the literature."
    )
    translated = (
        "인적 오류는 생산 실패의 일반적인 원인입니다. "
        "This research aims to analyze the role of human error in the production "
        "process using various analytical methods found in the literature."
    )

    items = generate_review_items(1, source, translated)

    assert any(item["kind"] == "untranslated_source_sentence" for item in items)
