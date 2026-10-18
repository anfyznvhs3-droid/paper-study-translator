"""Offline smoke test of the installed PDF, font, model and OCR runtime."""
from pathlib import Path
import importlib
import json
import os
import socket
import sys
import tempfile

def main():
    checks=[]
    def check(name, action):
        try:
            action()
            checks.append({'name':name,'ok':True})
        except Exception as exc:
            checks.append({'name':name,'ok':False,'error':str(exc)[:600]})
    def block_network(*args,**kwargs):
        raise RuntimeError('Runtime check must not access the network.')
    socket.socket.connect=block_network
    socket.create_connection=block_network
    for module in ('scholar_translator.cli','qdt','qdt_agents','fitz','kiwipiepy','qdt_mixed_renderer'):
        check('import '+module,lambda module=module:importlib.import_module(module))
    import fitz
    from scholar_translator.doclayout import OnnxModel
    from scholar_translator.high_level import translate,download_remote_fonts
    from scholar_translator.image_ocr import recognize
    from scholar_translator.final_output import compose_dual
    root=Path(os.environ['QDT_HOME'])
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='runtime-check-',dir=root) as directory:
        work=Path(directory)
        source=work/'sample.pdf'
        with fitz.open() as doc:
            page=doc.new_page(width=500,height=280)
            page.insert_text((40,80),'Research evidence',fontsize=24)
            doc.save(source)
        def font():
            p=download_remote_fonts('ko')
            assert Path(p).is_file()
            assert fitz.Font(fontfile=p).has_glyph(ord('학'))
        check('Korean font',font)
        def ocr():
            with fitz.open(source) as doc:
                lines=recognize(doc[0],doc[0].rect)
                assert any('Research' in x['text'] for x in lines), 'OCR did not recognize the synthetic text.'
        check('Tesseract English OCR',ocr)
        def pdf():
            model=OnnxModel.from_pretrained()
            mapping=work/'map.jsonl'
            mapping.write_text(json.dumps({'source':'Research evidence','translation':'연구 근거'},ensure_ascii=False)+'\n',encoding='utf-8')
            out=work/'translated';out.mkdir()
            pairs=translate(files=[str(source)],output=str(out),lang_in='en',lang_out='ko',
                service='offline',thread=1,model=model,ignore_cache=True,
                envs={'OFFLINE_TRANSLATION_MAP':str(mapping)})
            mono,dual=pairs[0]
            with fitz.open(mono) as doc:
                assert '연구' in ''.join(page.get_text() for page in doc), 'Korean text missing from PDF.'
            with fitz.open(dual) as doc:
                assert len(doc)==1 and abs(doc[0].rect.width-1000)<1, 'DUAL is not side by side.'
                text=doc[0].get_text()
                assert 'Research' in text and '연구' in text
        check('Layout model + offline Korean PDF + side-by-side DUAL',pdf)
    print(json.dumps({'ok':all(c['ok'] for c in checks),'network':'blocked','checks':checks},ensure_ascii=False))
    return 0 if all(c['ok'] for c in checks) else 1

if __name__=='__main__': raise SystemExit(main())
