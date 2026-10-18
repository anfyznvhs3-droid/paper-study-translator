# Scholar Translator (modified vendored engine)

Derived from [hi-space/scholar-translator](https://github.com/hi-space/scholar-translator),
itself derived from [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate).
The upstream AGPL-3.0 license is retained in LICENSE. The combined application
is distributed under AGPL-3.0; third-party components retain their own licenses.

This is a modified copy, maintained by Paper Study Translator contributors in 2026.
Changes include the Gemini client, numeric/citation protection, bounded retries,
offline translation maps for agent batches, glossary integration, review data,
OCR integration, side-by-side output, and portable resource/cache paths.
Legacy upstream providers remain for compatibility; the desktop UI offers Gemini
and locally authenticated Codex/Claude agents.

Install the tested dependency set with the repository's setup.ps1. The Windows
portable release includes its Python environment, document layout model and Korean
fonts. Source installations download model/font assets on their first PDF run.
QDT_BUNDLED_ASSETS optionally points to the directory containing the ONNX model and
SourceHanSerifKR-Regular.ttf. Private configuration belongs in QDT_HOME, never here.

When updating upstream code, retain these integration changes and run the repository
checks. See the root README for application setup and limitations.
