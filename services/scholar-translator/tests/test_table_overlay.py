from scholar_translator.table_overlay import (
    should_overlay_table_cells,
    translate_table_cell_text,
)


class FakeTranslator:
    def translate(self, text: str) -> str:
        return f"번역:{text}"


def test_table_cell_overlay_is_enabled_by_default_but_can_be_disabled():
    assert should_overlay_table_cells({}) is True
    assert should_overlay_table_cells({"QDT_TABLE_CELL_OVERLAY": "0"}) is False
    assert should_overlay_table_cells({"QDT_TABLE_CELL_OVERLAY": "false"}) is False


def test_table_cell_overlay_preserves_values_units_and_identifiers():
    translator = FakeTranslator()

    assert translate_table_cell_text("19.0", translator) is None
    assert translate_table_cell_text("kA", translator) is None
    assert translate_table_cell_text("A", translator) is None
    assert translate_table_cell_text("B 01", translator) is None


def test_table_cell_overlay_uses_domain_header_overrides_before_machine_translation():
    translator = FakeTranslator()

    assert translate_table_cell_text("Weld rupture force", translator) == "용접부 파단 하중"
    assert translate_table_cell_text("Technology Cycle Parameters", translator) == "기술/사이클 매개변수"
    assert translate_table_cell_text("up", translator) == "상승"
    assert translate_table_cell_text("down", translator) == "하강"
    assert translate_table_cell_text("break", translator) == "휴지"
    assert translate_table_cell_text("force", translator) == "하중"
    assert translate_table_cell_text("main fundamental impulses", translator) == "번역:main fundamental impulses"

def test_cell_overlay_preserves_font_scale_and_header_color():
    import fitz
    from scholar_translator.table_overlay import _paint_cell_text
    with fitz.open() as d:
        page=d.new_page(width=300,height=200)
        assert _paint_cell_text(page,fitz.Rect(10,10,290,70),"Translated header",None,True,16,(.2,.4,.7),(1,1,1))
        span=page.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]
        assert span["size"]==16
        assert span["color"] & 0xFFFFFF == 0xFFFFFF

def test_cell_that_cannot_fit_is_never_erased():
    import fitz
    from scholar_translator.table_overlay import _paint_cell_text
    with fitz.open() as d:
        page=d.new_page(width=300,height=200)
        page.insert_text((10,30),"Original content")
        before=page.get_pixmap().samples
        assert not _paint_cell_text(page,fitz.Rect(10,10,25,20),"A sentence that cannot fit.",None,False,16)
        assert page.get_pixmap().samples==before
