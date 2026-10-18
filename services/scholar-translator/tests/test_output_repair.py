import fitz
import pytest
from scholar_translator.final_output import compose_dual, final_native_review
from scholar_translator.image_ocr import parse_tsv, paint_translation
from scholar_translator.layout_policy import reserved_layout_classes, is_formula_font
from scholar_translator.audit import generate_review_items

def document(text, width=300):
    d=fitz.open();p=d.new_page(width=width,height=200)
    p.insert_text((20,40),text)
    return d

def test_dual_is_one_spread_per_source_page_with_final_translation():
    with document("Original label") as source, document("FINAL repaired label") as translated:
        with compose_dual(source,translated) as dual:
            assert len(dual)==1
            assert dual[0].rect.width==600
            assert dual[0].rect.height==200
            assert "Original label" in dual[0].get_text(clip=fitz.Rect(0,0,300,200))
            assert "FINAL repaired label" in dual[0].get_text(clip=fitz.Rect(300,0,600,200))

def test_dual_rejects_page_count_mismatch():
    with document("source") as source, document("target") as target:
        target.new_page()
        with pytest.raises(ValueError,match="page count"):
            compose_dual(source,target)

def test_italic_body_is_not_formula_but_math_fonts_are():
    assert not is_formula_font("ABCDEF+TrebuchetMS-Italic")
    assert not is_formula_font("TimesNewRomanPS-ItalicMT")
    assert is_formula_font("CMMI10")
    assert is_formula_font("CambriaMath")
    assert "abandon" not in reserved_layout_classes()

@pytest.mark.parametrize("text",["Sampling error","Confidence Levels and Intervals","This sample uses a control group."])
def test_short_unchanged_english_is_reviewed(text):
    assert any(i["kind"]=="untranslated_source_sentence" for i in generate_review_items(0,text,text))

@pytest.mark.parametrize("text",["ISO 9001","FMEA","https://example.com/a","{v0}","123 mm"])
def test_identifiers_formulas_and_urls_are_not_ordinary_english(text):
    assert not any(i["kind"]=="untranslated_source_sentence" for i in generate_review_items(0,text,text))

def test_final_review_detects_text_omitted_before_translation(tmp_path):
    src=tmp_path/"src.pdf";tgt=tmp_path/"tgt.pdf"
    with document("Confidence Levels and Intervals") as d:d.save(src);d.save(tgt)
    items=final_native_review(src,tgt)
    assert any(i["kind"]=="untranslated_region" for i in items)

def test_final_review_does_not_flag_text_hidden_under_repair(tmp_path):
    src=tmp_path/"src.pdf";tgt=tmp_path/"tgt.pdf"
    with document("Confidence Levels and Intervals") as d:
        d.save(src)
        bbox=d[0].search_for("Confidence Levels and Intervals")[0]
        assert paint_translation(d[0],bbox,"REPAIRED",None,(1,1,1))
        d.save(tgt)
    assert not final_native_review(src,tgt)

def test_ocr_tsv_groups_words_and_maps_to_pdf_coordinates():
    tsv="level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    tsv+="5\t1\t1\t1\t1\t1\t20\t30\t40\t10\t95\tHousehold\n"
    tsv+="5\t1\t1\t1\t1\t2\t65\t30\t30\t10\t90\tincome\n"
    lines=parse_tsv(tsv,fitz.Rect(100,200,200,300),200,200)
    assert lines[0]["text"]=="Household income"
    assert lines[0]["bbox"]==pytest.approx([110,215,147.5,220])
    assert lines[0]["confidence"]==90

def test_failed_paint_does_not_cover_original():
    with document("Original") as d:
        before=d[0].get_pixmap().samples
        assert not paint_translation(d[0],fitz.Rect(10,10,11,11),"too long",None,(1,1,1))
        assert before==d[0].get_pixmap().samples

def test_audit_uses_human_page_numbers_and_retains_ocr_failure(tmp_path):
    import json
    from scholar_translator.audit import write_audit_file
    path=write_audit_file(tmp_path/"doc.pdf",[(0,[("Sampling error","표본 오차")])],
        [{"page":0,"source_text":"Raster label","kind":"image_ocr","status":"open","reason":"OCR failed","fitted":False}])
    result=json.loads(path.read_text(encoding="utf-8"))
    assert result["pages"][0]["page"]==1
    assert result["pages"][0]["replacements"][0]["fitted"] is None
    assert any(r["kind"]=="image_ocr" for r in result["pages"][0]["replacements"] if "kind" in r)

def test_native_omission_is_repaired_before_final_audit(tmp_path):
    from scholar_translator.final_output import repair_native_residuals
    src=tmp_path/"src.pdf";target=tmp_path/"target.pdf"
    with document("Sampling error") as d:d.save(src);d.save(target)
    class Translator:
        def translate(self,text):return "REPAIRED"
    records=repair_native_residuals(src,target,Translator())
    assert records[0]["fitted"] is True
    assert not final_native_review(src,target)

def test_ocr_failure_becomes_review_instead_of_clean_success(tmp_path,monkeypatch):
    from scholar_translator import image_ocr
    from PIL import Image
    import io
    bitmap=Image.new("RGB",(300,150),"white");buffer=io.BytesIO();bitmap.save(buffer,format="PNG")
    source=tmp_path/"src.pdf";target=tmp_path/"target.pdf"
    with fitz.open() as d:
        p=d.new_page(width=300,height=200);p.insert_image(fitz.Rect(20,20,280,150),stream=buffer.getvalue());d.save(source);d.save(target)
    def fail(*args):raise RuntimeError("OCR missing")
    monkeypatch.setattr(image_ocr,"recognize",fail)
    records=image_ocr.apply_image_ocr(source,target,None)
    assert records and records[0]["status"]=="open"
    assert records[0]["reason"]=="OCR missing"

def test_flat_background_is_sampled_without_visible_quantization_patch():
    from scholar_translator.image_ocr import background_color
    with fitz.open() as d:
        p=d.new_page(width=100,height=100)
        color=(.31,.47,.67)
        p.draw_rect(p.rect,color=None,fill=color)
        sampled=background_color(p,fitz.Rect(20,20,60,30))
        assert sampled==pytest.approx(color,abs=1/255)

def test_ocr_ink_box_keeps_readable_label_size():
    with fitz.open() as d:
        p=d.new_page(width=300,height=200)
        assert paint_translation(p,fitz.Rect(40,40,130,50),"Translated",None,(1,1,1),p.rect,glyph_box=True)
        span=p.get_text("dict")["blocks"][0]["lines"][0]["spans"][0]
        assert span["size"]>=10
        assert span["bbox"][2]<300

def test_native_repair_opt_out_keeps_omission_in_review(tmp_path,monkeypatch):
    from scholar_translator.final_output import repair_native_residuals
    src=tmp_path/"src.pdf";target=tmp_path/"target.pdf"
    with document("Sampling error") as d:d.save(src);d.save(target)
    before=target.read_bytes()
    monkeypatch.setenv("QDT_FINAL_NATIVE_REPAIR","0")
    records=repair_native_residuals(src,target,None)
    assert records[0]["status"]=="open"
    assert target.read_bytes()==before

@pytest.mark.parametrize("color,expected",[(1,"1 g"),((1,1,1),"1 1 1 rg"),((0,1,0,0),"0 1 0 0 k"),(None,"0 g")])
def test_source_text_color_keeps_pdf_color_space(color,expected):
    from scholar_translator.layout_policy import text_color_operator
    assert text_color_operator(color)==expected

@pytest.mark.parametrize("text",["22","3.14 ± 0.1","{v0} / {v1}","(2026)","   "])
def test_page_numbers_and_formula_only_fragments_need_no_request(text):
    from scholar_translator.layout_policy import is_nontext_fragment
    assert is_nontext_fragment(text)

@pytest.mark.parametrize("text",["2026 Sampling methods","Confidence: {v0}","검정 결과"])
def test_numeric_fragments_with_prose_still_translate(text):
    from scholar_translator.layout_policy import is_nontext_fragment
    assert not is_nontext_fragment(text)

@pytest.mark.parametrize("source,result",[
    ("2,500 — 4,500 won (Jan 2015)","2,500 — 4,500 원 (2015년 1월)"),
    ("January 5, 2015","2015년 1월 5일"),
    ("Sep. 2026","2026년 09월"),
])
def test_named_calendar_month_is_not_an_invented_quantity(source,result):
    from scholar_translator.gemini_client import preservation_difference
    missing,added=preservation_difference(source,result)
    assert not missing and not added

@pytest.mark.parametrize("source,result",[
    ("Jan 2015","2015년 2월"),
    ("Jan 2015","2016년 1월"),
    ("Jan 2015","2015년 1월, 1회 추가"),
    ("May reduce errors.","5월에 오류를 줄입니다."),
    ("Jan 2015: 2,500 won","2015년 1월: 4,500 원"),
])
def test_month_equivalence_does_not_allow_changed_or_added_values(source,result):
    from scholar_translator.gemini_client import preservation_difference
    missing,added=preservation_difference(source,result)
    assert missing or added

def test_ocr_literal_quote_never_consumes_subsequent_tsv_rows():
    tsv="level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\r\n"
    tsv+='5\t1\t1\t1\t1\t1\t20\t30\t40\t10\t95\t"Everyone\r\n'
    tsv+='5\t1\t1\t1\t1\t2\t65\t30\t30\t10\t90\tin\r\n'
    tsv+='5\t1\t2\t1\t1\t1\t20\t80\t40\t10\t95\tNext\r\n'
    lines=parse_tsv(tsv,fitz.Rect(0,0,200,200),200,200)
    assert lines[0]["text"]=='"Everyone in'
    assert lines[1]["text"]=="Next"
    assert all("\t" not in line["text"] and "\n" not in line["text"] for line in lines)

@pytest.mark.parametrize("text,index,expected",[
    ("65세",0,"65"),("범위 1,250.5%",3,"1,250.5%"),
    ("65세",1,""),("ISO9001",3,""),("오차 -3.5%",3,"-3.5%"),
])
def test_numeric_literals_wrap_as_a_unit(text,index,expected):
    from scholar_translator.layout_policy import numeric_token_at
    assert numeric_token_at(text,index)==expected

@pytest.mark.parametrize("text",["QUANTITATIVE","QUALITATIVE","Time 1","Cross-Sectional Design"])
def test_image_headings_are_not_mistaken_for_table_identifiers(text):
    from scholar_translator.image_ocr import should_preserve_image_text
    assert not should_preserve_image_text(text)

@pytest.mark.parametrize("text",["FMEA","ISO 9001","B 01","MPa","12.5%"])
def test_image_identifiers_and_values_are_preserved(text):
    from scholar_translator.image_ocr import should_preserve_image_text
    assert should_preserve_image_text(text)

def test_jpeg_highlight_gradient_can_be_overlaid_but_photo_pattern_cannot():
    from PIL import Image
    from scholar_translator.image_ocr import background_color
    import io
    for photo in (False,True):
        bitmap=Image.new("RGB",(240,80))
        for y in range(80):
            for x in range(240):
                color=([(230,40,30),(40,210,30),(40,50,220),(20,20,20)][(x//12+y//12)%4]
                       if photo else (255,211+x//30,50+x//10))
                bitmap.putpixel((x,y),color)
        buffer=io.BytesIO();bitmap.save(buffer,format="PNG")
        with fitz.open() as d:
            p=d.new_page(width=240,height=80);p.insert_image(p.rect,stream=buffer.getvalue())
            sampled=background_color(p,fitz.Rect(20,10,220,70))
            assert (sampled is None)==photo

def test_rejected_fragment_is_reviewed_and_next_fragment_can_translate():
    from scholar_translator.gemini_client import GeminiClient,GeminiError
    from scholar_translator.translation_failures import attempt_translation
    client=GeminiClient("test-only",session=object())
    calls=[]
    def fake(text,lang,correction=False):
        calls.append(text)
        if text=="Blocked fragment":raise GeminiError("QDT_GEMINI_BLOCKED","provider refused")
        return "다음 문장은 번역됩니다."
    client._request_translation=fake
    records=[]
    assert attempt_translation(lambda:client.translate("Blocked fragment"),"Blocked fragment",records,21,phase="image_ocr") is None
    assert records[0]["kind"]=="translation_incomplete"
    assert records[0]["severity"]=="error"
    assert records[0]["source_text"]==records[0]["translated_text"]
    assert client.translate("Next sentence")=="다음 문장은 번역됩니다."
    assert client._terminal_error is None

def test_bad_numeric_response_is_never_inserted_or_cached():
    from scholar_translator.gemini_client import GeminiClient
    from scholar_translator.translation_failures import attempt_translation
    client=GeminiClient("test-only",session=object())
    client._request_translation=lambda *a,**k:"표본은 999명입니다."
    records=[]
    assert attempt_translation(lambda:client.translate("Sample size is 20."),"Sample size is 20.",records,0) is None
    assert records[0]["error_code"]=="QDT_GEMINI_PRESERVATION"
    assert "999" not in str(records)
    assert client._terminal_error is None

def test_auth_failure_is_not_downgraded_to_a_review_candidate():
    from scholar_translator.gemini_client import GeminiClient,GeminiError
    from scholar_translator.translation_failures import attempt_translation
    client=GeminiClient("test-only",session=object())
    def fail(*args,**kwargs):raise GeminiError("QDT_GEMINI_AUTH","bad key")
    client._request_translation=fail
    records=[]
    with pytest.raises(GeminiError,match="QDT_GEMINI_AUTH"):
        attempt_translation(lambda:client.translate("Document text"),"Document text",records,0)
    assert not records
    assert client._terminal_error is not None

def test_unchanged_english_cache_is_rejected_but_acronyms_are_preserved():
    from scholar_translator.gemini_client import GeminiClient
    client=GeminiClient("test-only",session=object())
    assert client.validate_cached_translation("Words in real settings.","Words in real settings.") is None
    assert client.validate_cached_translation("FMEA","FMEA")=="FMEA"

def test_uncertain_strokes_are_grouped_per_image_without_hiding_evidence(tmp_path,monkeypatch):
    from scholar_translator import image_ocr
    from PIL import Image
    import io
    bitmap=Image.new("RGB",(300,150),"white");buffer=io.BytesIO();bitmap.save(buffer,format="PNG")
    source=tmp_path/"src.pdf";target=tmp_path/"target.pdf"
    with fitz.open() as d:
        p=d.new_page(width=300,height=200);p.insert_image(fitz.Rect(20,20,280,150),stream=buffer.getvalue());d.save(source);d.save(target)
    monkeypatch.setattr(image_ocr,"recognize",lambda *args:[
        {"text":"unclear one","bbox":[30,30,80,40],"confidence":20},
        {"text":"unclear two","bbox":[30,60,80,70],"confidence":30}])
    records=image_ocr.apply_image_ocr(source,target,None)
    assert len(records)==1
    assert len(records[0]["uncertain_lines"])==2
    assert records[0]["status"]=="open"
    assert records[0]["fitted"] is False
