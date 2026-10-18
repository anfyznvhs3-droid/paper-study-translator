"""Figure/diagram label overlay.

Diagram-box labels ("APQP Gate", "PPAP Release", ...) live inside layout-model
"figure" regions, so the page-frame converter preserves them verbatim (English)
instead of translating them. This overlay translates such labels in place,
selecting them by figure-region geometry and reusing the table-cell translate +
paint helpers.
"""

import fitz

from scholar_translator.graphic_overlay import (
    apply_graphic_text_overlays,
    iter_graphic_label_spans,
    should_overlay_graphic_text,
)


class FakeTranslator:
    # ASCII output so the assertion checks the overlay mechanism, not Korean font
    # embedding (the default helv font cannot render Hangul; production passes Noto).
    def translate(self, text: str) -> str:
        return f"TR_{text}"


def _make_pdf(path, spans):
    # spans: list of (point, text)
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    for (x, y), text in spans:
        page.insert_text((x, y), text, fontsize=10)
    doc.save(str(path))
    doc.close()


def test_graphic_overlay_kill_switch_default_on():
    assert should_overlay_graphic_text({}) is True
    assert should_overlay_graphic_text({"QDT_GRAPHIC_TEXT_OVERLAY": "0"}) is False
    assert should_overlay_graphic_text({"QDT_GRAPHIC_TEXT_OVERLAY": "off"}) is False


def test_iter_selects_only_spans_whose_center_is_inside_a_figure_region(tmp_path):
    pdf = tmp_path / "src.pdf"
    _make_pdf(
        pdf,
        [
            ((20, 40), "APQP Gate"),   # inside the top-half figure region
            ((20, 60), "100"),          # inside region, but numeric (filtered later)
            ((20, 220), "Body outside"),  # outside the region
        ],
    )
    doc = fitz.open(str(pdf))
    page = doc[0]
    # Top half of a 300pt page.
    regions = [(0.0, 0.0, 1.0, 0.5)]
    found = {text for _bbox, text in iter_graphic_label_spans(page, regions)}
    doc.close()

    assert "APQP Gate" in found
    assert "100" in found  # geometric selection only; numeric drop happens downstream
    assert "Body outside" not in found


def test_apply_overlays_translates_label_skips_number_and_outside(tmp_path):
    src = tmp_path / "src.pdf"
    _make_pdf(
        src,
        [
            ((20, 40), "APQP Gate"),
            ((20, 60), "100"),
            ((20, 220), "Body outside"),
        ],
    )
    target = tmp_path / "tgt.pdf"
    fitz.open(str(src)).save(str(target))

    regions_by_page = {0: [(0.0, 0.0, 1.0, 0.5)]}
    count = apply_graphic_text_overlays(
        str(src), str(target), FakeTranslator(), regions_by_page
    )

    # Only "APQP Gate" is a translatable label inside the region.
    assert count == 1

    out = fitz.open(str(target))
    text = out[0].get_text()
    out.close()
    assert "TR_APQP Gate" in text
    assert "TR_100" not in text  # numeric axis tick preserved
    assert "TR_Body outside" not in text  # outside figure region untouched


def test_apply_overlays_noop_when_no_regions(tmp_path):
    src = tmp_path / "src.pdf"
    _make_pdf(src, [((20, 40), "APQP Gate")])
    target = tmp_path / "tgt.pdf"
    fitz.open(str(src)).save(str(target))

    count = apply_graphic_text_overlays(str(src), str(target), FakeTranslator(), {})
    assert count == 0
