"""Local OCR for raster labels. Originals stay intact; failed regions enter review."""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import fitz

def tesseract_command():
    explicit=os.environ.get("QDT_TESSERACT")
    if explicit:
        return explicit
    found=shutil.which("tesseract")
    if found:return found
    candidate=Path(os.environ.get("ProgramFiles",r"C:\Program Files"))/"Tesseract-OCR/tesseract.exe"
    return str(candidate) if candidate.is_file() else None

def parse_tsv(text, region, pixel_width, pixel_height):
    groups=defaultdict(list)
    for row in csv.DictReader(io.StringIO(text),delimiter="\t",quoting=csv.QUOTE_NONE):
        if row.get("level")!="5" or not row.get("text","").strip():continue
        try:
            row={**row,**{k:float(row[k]) for k in ("left","top","width","height","conf")}}
        except (ValueError,KeyError):continue
        groups[tuple(row[k] for k in ("page_num","block_num","par_num","line_num"))].append(row)
    result=[]
    for rows in groups.values():
        x0=min(r["left"] for r in rows);y0=min(r["top"] for r in rows)
        x1=max(r["left"]+r["width"] for r in rows);y1=max(r["top"]+r["height"] for r in rows)
        result.append({"text":" ".join(r["text"].strip() for r in rows),
            "bbox":[region.x0+x0*region.width/pixel_width,region.y0+y0*region.height/pixel_height,
                    region.x0+x1*region.width/pixel_width,region.y0+y1*region.height/pixel_height],
            "confidence":min(r["conf"] for r in rows)})
    return result

def recognize(page, region):
    executable=tesseract_command()
    if not executable:raise RuntimeError("Tesseract OCR 실행 파일이 없습니다.")
    # Bound memory and OCR time; PNG is passed over stdin, never to a remote service.
    from PIL import Image, ImageOps
    scale=min(4.0,3200/max(region.width,region.height))
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=region,colorspace=fitz.csRGB,alpha=False)
    original=Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    variants=(original,ImageOps.invert(ImageOps.grayscale(original)))
    found=[]
    for image in variants:
        buffer=io.BytesIO();image.save(buffer,format="PNG")
        run=subprocess.run([executable,"stdin","stdout","-l","eng","--psm","11","tsv"],
            input=buffer.getvalue(),capture_output=True,timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        if run.returncode:
            raise RuntimeError("OCR 실행 실패: "+run.stderr.decode("utf-8",errors="replace")[-300:])
        for line in parse_tsv(run.stdout.decode("utf-8",errors="replace"),region,pix.width,pix.height):
            box=fitz.Rect(line["bbox"])
            previous=next((i for i,v in enumerate(found)
                if (box & fitz.Rect(v["bbox"])).get_area()/max(1,min(box.get_area(),fitz.Rect(v["bbox"]).get_area()))>.65),None)
            if previous is None:found.append(line)
            elif line["confidence"]>found[previous]["confidence"]:found[previous]=line
    return sorted(found,key=lambda v:(v["bbox"][1],v["bbox"][0]))

def background_color(page, bbox):
    box=fitz.Rect(bbox)
    sample=(box+(-2,-2,2,2)) & page.rect
    pix=page.get_pixmap(matrix=fitz.Matrix(2,2),clip=sample,colorspace=fitz.csRGB,alpha=False)
    if not pix.width or not pix.height:return None
    # Quantize antialiasing noise. A nonuniform photograph is not painted over.
    samples=pix.samples
    colors=Counter(tuple((samples[i+j]//8)*8+4 for j in range(3)) for i in range(0,len(samples),3))
    color,count=colors.most_common(1)[0]
    if count/(pix.width*pix.height)<.42:
        # JPEG diagrams often have a mildly varying highlight color. Group a
        # narrow neighborhood around the dominant coarse color, not the text.
        triples=[tuple(samples[i:i+3]) for i in range(0,len(samples),3)]
        buckets=Counter(tuple(c//32 for c in p) for p in triples)
        dominant=buckets.most_common(1)[0][0]
        group=[p for p in triples if tuple(c//32 for c in p)==dominant]
        center=tuple(sum(p[j] for p in group)/len(group) for j in range(3))
        near=[p for p in triples if max(abs(p[j]-center[j]) for j in range(3))<=24]
        if len(near)/len(triples)<.55:return None
        return tuple(sum(p[j] for p in near)/len(near)/255 for j in range(3))
    # Use the actual average in the winning bucket, not its quantized center.
    # Otherwise a visible rectangle remains on a flat diagram background.
    pixels=[tuple(samples[i:i+3]) for i in range(0,len(samples),3)
            if tuple((samples[i+j]//8)*8+4 for j in range(3))==color]
    return tuple(sum(p[j] for p in pixels)/len(pixels)/255 for j in range(3))

def paint_translation(page,bbox,text,font_file,background,limit=None,glyph_box=False):
    """Commit the cover and text atomically only after a fitting layout is found."""
    bbox=fitz.Rect(bbox)
    if bbox.width<4 or bbox.height<3 or not text.strip():return False
    boundary=fitz.Rect(limit) if limit is not None else page.rect
    cover=fitz.Rect(bbox.x0-1,bbox.y0-1,bbox.x1+1,bbox.y1+1)&boundary
    if glyph_box:
        # OCR boxes bound visible ink, unlike native font ascender/descender boxes.
        # Size to that ink height and center the baseline instead of shrinking
        # labels into a textbox with oversized CJK leading.
        font=fitz.Font(fontfile=font_file) if font_file else fitz.Font("helv")
        size=min(22,max(7,bbox.height*1.25))
        available=min(boundary.width-4,max(bbox.width*1.4,bbox.width+24))
        length=font.text_length(text,fontsize=size)
        if length>available:size*=available/length
        if size<max(5,bbox.height*.7):return False
        length=font.text_length(text,fontsize=size)
        center=(bbox.x0+bbox.x1)/2
        left=max(boundary.x0+2,min(center-length/2,boundary.x1-length-2))
        if size*1.05>boundary.height:return False
        baseline=max(boundary.y0+size*.85,min((bbox.y0+bbox.y1)/2+size*.35,boundary.y1-size*.2))
        shape=page.new_shape()
        shape.draw_rect(cover);shape.finish(color=None,fill=background)
        foreground=(1,1,1) if sum(c*w for c,w in zip(background,(.2126,.7152,.0722)))<.55 else (.03,.03,.03)
        kwargs={"fontname":"qdt_ocr" if font_file else "helv","fontsize":size,"color":foreground}
        if font_file:kwargs["fontfile"]=font_file
        shape.insert_text((left,baseline),text,**kwargs)
        shape.commit(overlay=True)
        return True
    base=max(5,min(18,bbox.height*.8))
    foreground=(1,1,1) if sum(c*w for c,w in zip(background,(.2126,.7152,.0722)))<.48 else (.03,.03,.03)
    for factor in (1,.9,.8,.7,.6):
        size=max(4.5,base*factor)
        # Keep the center and enough leading for CJK; do not exceed the image bounds.
        width=min(boundary.width,max(bbox.width+2,len(text)*size*.95))
        cx=(bbox.x0+bbox.x1)/2
        left=max(boundary.x0,min(cx-width/2,boundary.x1-width))
        top=max(boundary.y0,bbox.y0-1)
        rect=fitz.Rect(left,top,left+width,min(boundary.y1,top+max(bbox.height+2,size*2.2)))
        shape=page.new_shape()
        shape.draw_rect(cover);shape.finish(color=None,fill=background)
        kwargs={"fontname":"qdt_ocr" if font_file else "helv","fontsize":size,"color":foreground,"align":fitz.TEXT_ALIGN_CENTER}
        if font_file:kwargs["fontfile"]=font_file
        if shape.insert_textbox(rect,text,**kwargs)>=0:
            shape.commit(overlay=True)
            return True
    return False

def image_regions(page):
    seen=set()
    for info in page.get_image_info():
        rect=fitz.Rect(info["bbox"])&page.rect
        key=tuple(round(v,1) for v in rect)
        if key in seen or rect.width<25 or rect.height<12 or info["width"]<60 or info["height"]<25:continue
        seen.add(key);yield rect

def should_preserve_image_text(text):
    from scholar_translator.table_structure import classify_table_cell, TableCellRole
    # Do not reuse the table identifier rule: it calls every ALL-CAPS word
    # an identifier, including ordinary headings such as QUANTITATIVE.
    role=classify_table_cell(text).role
    from scholar_translator.gemini_client import protected_tokens
    if text.strip() in protected_tokens(text):return True
    return role in (TableCellRole.VALUE,TableCellRole.UNIT) or bool(
        re.fullmatch(r"[A-Z]{1,5}|[A-Z]{1,4}\s+\d{1,4}|[A-Z]+[-_]?\d+(?:[/.-]\d+)*",text.strip()))


def apply_image_ocr(source_pdf,target_pdf,translator,font_file=None,envs=None,pages=None):
    records=[];changed=False
    enabled=str((envs or {}).get("QDT_IMAGE_OCR",os.environ.get("QDT_IMAGE_OCR","1"))).lower() not in ("0","false","off")
    with fitz.open(source_pdf) as source,fitz.open(target_pdf) as target:
        for index,page in enumerate(source):
            if pages is not None and index not in pages:continue
            native=page.get_text()
            for region in image_regions(page):
                record={"page":index,"bbox":list(region),"kind":"image_ocr","status":"open","fitted":False}
                if not enabled:
                    records.append({**record,"source_text":"이미지 영역","reason":"이미지 OCR이 꺼져 있어 그림 속 글자를 확인하지 못했습니다."});continue
                try:lines=recognize(page,region)
                except (RuntimeError,subprocess.TimeoutExpired,OSError) as error:
                    records.append({**record,"source_text":"이미지 영역","reason":str(error)});continue
                if not lines:
                    records.append({**record,"source_text":"이미지 영역","reason":"OCR에서 글자를 찾지 못했습니다. 글자 없는 그림인지 원본을 확인하세요."});continue
                uncertain=[]
                for line in lines:
                    text=line["text"];bbox=fitz.Rect(line["bbox"])
                    # Native text overlapping a raster should be translated through native flow.
                    if text in native and page.get_text(clip=bbox).strip():continue
                    if not re.search(r"[A-Za-z]{2}",text) or should_preserve_image_text(text):continue
                    rec={**record,"bbox":list(bbox),"source_text":text,"confidence":line["confidence"]}
                    if line["confidence"]<50:
                        uncertain.append({"text":text,"bbox":list(bbox),"confidence":line["confidence"]});continue
                    from scholar_translator.translation_failures import attempt_translation
                    translated=attempt_translation(lambda:translator.translate(text),text,records,index,bbox,"image_ocr")
                    if translated is None:continue
                    translated=" ".join(str(translated).split())
                    if not translated or translated==text:
                        records.append({**rec,"translated_text":translated,"reason":"이미지 글자의 번역이 원문과 같거나 비어 있습니다."});continue
                    color=background_color(page,bbox)
                    fitted=color is not None and paint_translation(target[index],bbox,translated,font_file,color,region,glyph_box=True)
                    changed=changed or fitted
                    records.append({**rec,"translated_text":translated,"status":"candidate" if fitted else "open",
                        "fitted":bool(fitted),"reason":"OCR 번역: 인식한 원문과 그림 배치를 확인하세요." if fitted else "이미지 배경 또는 글자 공간을 안전하게 보정하지 못해 원문을 보존했습니다."})
                if uncertain:
                    # One image containing many uncertain strokes needs one visual
                    # review, not dozens of meaningless per-character candidates.
                    snippets=" / ".join(item["text"] for item in uncertain[:8])[:240]
                    records.append({**record,"source_text":"판독 불확실 이미지: "+snippets,
                        "uncertain_lines":uncertain,"severity":"warning",
                        "reason":f"그림 안 {len(uncertain)}개 구간의 OCR 인식이 불확실합니다. 원본 이미지를 보존했으며, 실제 글자가 있는지 확인하세요."})
        if changed:target.saveIncr()
    return records
