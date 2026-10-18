from scholar_translator.layout_policy import (
    reserved_layout_classes,
    should_translate_table_text,
)


def test_table_regions_can_be_made_translatable_without_opening_figures():
    reserved = reserved_layout_classes(translate_table_text=True)

    assert "table" not in reserved
    assert "figure" in reserved
    assert "isolate_formula" in reserved


def test_table_regions_remain_reserved_when_table_translation_is_disabled():
    reserved = reserved_layout_classes(translate_table_text=False)

    assert "table" in reserved


def test_table_translation_is_opt_in_to_protect_pdf_table_layout():
    assert should_translate_table_text({}) is False
    assert should_translate_table_text({"QDT_TRANSLATE_TABLE_TEXT": "1"}) is True
    assert should_translate_table_text({"QDT_TRANSLATE_TABLE_TEXT": "false"}) is False
