# Third-party notices

Paper Study Translator is a modified AGPL-3.0 application (2026).
The source and build instructions corresponding to each release are available at
https://github.com/anfyznvhs3-droid/paper-study-translator (the matching release tag).

| Component | License / source |
| --- | --- |
| Scholar Translator, modified | AGPL-3.0; [upstream](https://github.com/hi-space/scholar-translator); source and license in services/scholar-translator |
| PDFMathTranslate lineage | AGPL-3.0; [source](https://github.com/Byaidu/PDFMathTranslate) |
| BabelDOC | AGPL-3.0; [source](https://github.com/funstory-ai/BabelDOC) |
| PyMuPDF 1.25.2 / MuPDF | AGPL-3.0; [corresponding sources](https://github.com/pymupdf/PyMuPDF/tree/1.25.2), [MuPDF source](https://mupdf.com/releases/) |
| DocLayout-YOLO / ONNX layout weights | upstream code AGPL-3.0, ONNX artifact model card Apache-2.0; [model source](https://github.com/opendatalab/DocLayout-YOLO), [ONNX artifact](https://huggingface.co/wybxc/DocLayout-YOLO-DocStructBench-onnx); license in licenses/DocLayout-YOLO.txt |
| Pretendard | SIL OFL 1.1; [source](https://github.com/orioncactus/pretendard); services/mixed-renderer/assets/fonts/OFL.txt |
| Source Han Serif Korean | SIL OFL 1.1; [source](https://github.com/adobe-fonts/source-han-serif); licenses/SourceHanSerif-OFL.txt |
| Lucide icons | ISC; apps/desktop/src/assets/icons/LICENSE; [source](https://github.com/lucide-icons/lucide) |
| CPython 3.12.10 | PSF license; runtime/python/LICENSE.txt in the Windows package; [source](https://www.python.org/ftp/python/3.12.10/Python-3.12.10.tgz) |
| React | MIT; [source](https://github.com/facebook/react) |
| Tauri / wry / tao | MIT or Apache-2.0; [source](https://github.com/tauri-apps/tauri) |

Python package versions are pinned in requirements-windows.lock.txt. Their
original wheel metadata and license files are retained under
runtime/python/Lib/site-packages in the Windows distribution.
JavaScript and Rust dependencies are recorded in package-lock.json and Cargo.lock.
Their original license notices are collected in [licenses/DEPENDENCIES.md](licenses/DEPENDENCIES.md)
and the associated dependency directories.
Tesseract, WebView2, Visual C++ runtime and the optional agent CLIs are installed
separately under their respective licenses; they are not redistributed in the ZIP.

The Korean font and layout model are read-only assets. They contain no user
translation cache, credentials or documents. Source builds can obtain them via
BabelDOC's official asset downloader or the upstream projects linked above.
