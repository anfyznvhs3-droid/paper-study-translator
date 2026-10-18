"""Final-output composition and visible residual checks, after all repairs."""
from pathlib import Path
import re
import os
import fitz
import numpy as np

def compose_dual(source,translated):
    if len(source)!=len(translated):raise ValueError("DUAL page count mismatch")
    result=fitz.open()
    try:
        for i in range(len(source)):
            left,right=source[i].rect,translated[i].rect
            page=result.new_page(width=left.width+right.width,height=max(left.height,right.height))
            if source[i].get_contents():page.show_pdf_page(fitz.Rect(0,0,left.width,left.height),source,i)
            if translated[i].get_contents():page.show_pdf_page(fitz.Rect(left.width,0,left.width+right.width,right.height),translated,i)
        return result
    except Exception:
        result.close();raise

def write_dual(source_path,translated_path,output_path):
    with fitz.open(source_path) as source,fitz.open(translated_path) as translated:
        with compose_dual(source,translated) as dual:
            # Caller reserves a unique output directory; never replace an old result.
            with Path(output_path).open("xb") as f:f.write(dual.tobytes(garbage=3,deflate=True))

def needs_english_translation(text):
    text=re.sub(r"https?://\S+|10\.\d{4,9}/\S+|\{v\d+\}","",text)
    words=re.findall(r"[A-Za-z][A-Za-z'-]*",text)
    ordinary=[w for w in words if len(w)>=3 and not w.isupper()]
    return len(ordinary)>=2 or (len(words)==1 and len(ordinary)==1 and len(ordinary[0])>=4) or any(w.isupper() and len(w)>=6 for w in words)

def final_native_review(source_path,target_path,pages=None):
    """Detect visible unchanged native text, including spans omitted by translation.
    Raster regions have their separate OCR audit. Hidden source text under overlays
    is excluded by comparing the rendered crop, not just extracted strings.
    """
    items=[];references=False
    with fitz.open(source_path) as source,fitz.open(target_path) as target:
        for index,page in enumerate(source):
            if pages is not None and index not in pages:continue
            page_text=page.get_text()
            if re.search(r"(?im)^\s*(references|bibliography)\s*$",page_text):references=True
            if references:continue
            target_text=" ".join(target[index].get_text().split())
            for block in page.get_text("dict")["blocks"]:
                if block.get("type")!=0:continue
                for line in block["lines"]:
                    text=" ".join(s["text"] for s in line["spans"]).strip()
                    if not needs_english_translation(text) or " ".join(text.split()) not in target_text:continue
                    box=fitz.Rect(line["bbox"])&page.rect
                    if box.is_empty:continue
                    before=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=box,colorspace=fitz.csRGB,alpha=False)
                    after=target[index].get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=box,colorspace=fitz.csRGB,alpha=False)
                    a=np.frombuffer(before.samples,dtype=np.uint8).astype(float)
                    b=np.frombuffer(after.samples,dtype=np.uint8).astype(float)
                    if a.shape==b.shape and np.mean(np.abs(a-b))<3:
                        items.append({"page":index,"kind":"untranslated_region","source_text":text,"translated_text":text,
                            "bbox":list(box),"status":"open","severity":"error",
                            "reason":"최종 PDF에서 원문 영어가 같은 위치에 그대로 보입니다. 번역 누락을 확인하세요."})
    return items

def repair_native_residuals(source_path,target_path,translator,font_file=None,pages=None):
    from scholar_translator.image_ocr import background_color, paint_translation
    pending=final_native_review(source_path,target_path,pages)
    if os.environ.get("QDT_FINAL_NATIVE_REPAIR","1").strip().lower() in ("0","false","off"):
        return pending
    records=[];changed=False
    with fitz.open(source_path) as source,fitz.open(target_path) as target:
        for item in pending:
            index=item["page"];bbox=fitz.Rect(item["bbox"]);text=item["source_text"]
            from scholar_translator.translation_failures import attempt_translation
            translated=attempt_translation(lambda:translator.translate(text),text,records,index,bbox,"native")
            if translated is None:continue
            translated=" ".join(str(translated).split())
            if not translated or translated==text:
                records.append(item);continue
            color=background_color(source[index],bbox)
            fitted=color is not None and paint_translation(target[index],bbox,translated,font_file,color)
            changed=changed or fitted
            records.append({**item,"kind":"native_repair","translated_text":translated,"fitted":bool(fitted),
                "status":"candidate" if fitted else "open",
                "reason":"최종 출력에서 발견한 미번역 글자를 보정했습니다. 배치를 확인하세요." if fitted else "미번역 글자의 배치를 안전하게 보정하지 못해 원문을 보존했습니다."})
        if changed:target.saveIncr()
    return records
