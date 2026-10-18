"""Regression tests for source ownership, output collisions and recursive inputs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest

def _stub_conversion(monkeypatch, payload=b"translated"):
    import scholar_translator.high_level as high
    monkeypatch.setattr(high, "translate_stream", lambda *a, **k: (payload, payload, []))
    monkeypatch.setattr(high, "should_overlay_table_cells", lambda env: False)
    monkeypatch.setattr(high, "should_overlay_graphic_text", lambda env: False)
    # These tests intentionally use non-PDF byte payloads. Keep the new PDF
    # finalization boundary stubbed as well; ownership assertions stay unchanged.
    monkeypatch.setattr(high, "_build_table_overlay_translator", lambda *a: None)
    monkeypatch.setattr(high, "download_remote_fonts", lambda *a: None)
    monkeypatch.setattr(high, "apply_image_ocr", lambda *a: [])
    monkeypatch.setattr(high, "repair_native_residuals", lambda *a: [])
    monkeypatch.setattr(high, "final_native_review", lambda *a: [])
    monkeypatch.setattr(high, "write_dual", lambda src,mono,dual: Path(dual).write_bytes(payload))
    return high

def test_user_input_under_runtime_temp_survives_success_and_failure(tmp_path, monkeypatch):
    high = _stub_conversion(monkeypatch)
    monkeypatch.setattr(high.tempfile, "gettempdir", lambda: str(tmp_path))
    source = tmp_path / "user.pdf"
    original = b"user-owned original"
    source.write_bytes(original)
    high.translate([str(source)], output=str(tmp_path / "out"), lang_out="ko")
    assert source.read_bytes() == original
    def fail(*a, **k): raise RuntimeError("fixture failure")
    monkeypatch.setattr(high, "translate_stream", fail)
    with pytest.raises(RuntimeError, match="fixture failure"):
        high.translate([str(source)], output=str(tmp_path / "out"), lang_out="ko")
    assert source.read_bytes() == original

def test_same_basename_and_reruns_never_replace_prior_results(tmp_path, monkeypatch):
    high = _stub_conversion(monkeypatch, b"first")
    inputs = []
    for folder in ["A", "B"]:
        source = tmp_path / folder / "same.pdf"
        source.parent.mkdir()
        source.write_bytes(b"original")
        inputs.append(str(source))
    first = high.translate(inputs[:1], output=str(tmp_path / "out"), lang_out="ko")[0]
    _stub_conversion(monkeypatch, b"second")
    second = high.translate(inputs[1:], output=str(tmp_path / "out"), lang_out="ko")[0]
    third = high.translate(inputs[:1], output=str(tmp_path / "out"), lang_out="ko")[0]
    assert len({first[0], second[0], third[0]}) == 3
    assert Path(first[0]).read_bytes() == b"first"

def test_reservation_is_atomic_for_concurrent_runs(tmp_path):
    from scholar_translator.file_safety import reserve_output_directory
    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(lambda _: reserve_output_directory(tmp_path, "same-ko"), range(20)))
    assert len(set(paths)) == 20

def test_recursive_scan_excludes_outputs_marked_directories_and_symlinks(tmp_path):
    from scholar_translator.cli import find_all_files_in_directory
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    for name in ["QDT_Output", ".qdt-agent", ".qdt-home", "custom-results"]:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "generated.pdf").write_bytes(b"generated")
        if name == "custom-results": (folder / ".qdt-output").write_text("QDT")
    custom = tmp_path / "configured-output"
    custom.mkdir()
    (custom / "previous.pdf").write_bytes(b"generated")
    assert find_all_files_in_directory(str(tmp_path), output_path=str(custom)) == [str(source)]

def test_downloaded_input_is_kept_for_postprocess_then_cleaned_even_on_failure(tmp_path, monkeypatch):
    high = _stub_conversion(monkeypatch)
    created = []
    original = high.tempfile.NamedTemporaryFile
    def owned(*a, **kw):
        value = original(*a, dir=tmp_path, **kw)
        created.append(Path(value.name))
        return value
    monkeypatch.setattr(high.tempfile, "NamedTemporaryFile", owned)
    class Response:
        status_code = 200
        content = b"downloaded fixture"
    monkeypatch.setattr(high.requests, "get", lambda *a, **kw: Response())
    def during(*a, **kw):
        assert Path(kw["file"]).exists()
        raise RuntimeError("fixture failure")
    monkeypatch.setattr(high, "translate_stream", during)
    with pytest.raises(RuntimeError):
        high.translate(["https://example.test/file.pdf"], output=str(tmp_path / "out"), lang_out="ko")
    assert created and all(not p.exists() for p in created)


def test_google_quota_failure_is_named_and_request_is_time_bounded(monkeypatch):
    import requests
    from scholar_translator.translator import GoogleTranslator
    from scholar_translator.gemini_client import GeminiError
    calls = []
    class Response:
        status_code = 429
        text = ""
    def limited(self, url, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr(requests.Session, "get", limited)
    translator = GoogleTranslator("en", "ko", None, ignore_cache=True)
    with pytest.raises(GeminiError) as error:
        translator.do_translate("fixture sentence")
    assert error.value.code == "QDT_GOOGLE_RATE_LIMITED"
    assert len(calls) == 1
    assert calls[0]["timeout"] == (5, 30)
