"""Keep rejected fragments as explicit review work, never as cached translations."""
from scholar_translator.gemini_client import GeminiError, is_fragment_error


def attempt_translation(call, source, records, page, bbox=None, phase="text"):
    prior=next((item for item in records
                if item.get("error_code") and item.get("source_text")==source),None)
    try:
        if prior:
            raise GeminiError(prior["error_code"],"이 문구는 앞선 검사에서 보류되었습니다.")
        return call()
    except GeminiError as error:
        if not is_fragment_error(error):
            raise
        record={"page":page,"kind":"translation_incomplete","phase":phase,
                "severity":"error","status":"open","fitted":False,
                "source_text":source,"translated_text":source,"error_code":error.code,
                "reason":str(error)+" 원문을 보존했습니다. 이 구간은 번역 미완료입니다."}
        if bbox is not None:record["bbox"]=list(bbox)
        records.append(record)
        return None
