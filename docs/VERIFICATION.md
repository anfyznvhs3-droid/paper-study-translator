# Release verification — 0.1.0

Verified on Windows x64, 2026-10-18. No live translation API requests were made.

| Check | Result |
| --- | --- |
| `scripts/check-all.ps1` | 372 Python, 59 Node and 76 Rust tests passed; TypeScript and Cargo checks passed |
| `npm run build` | Production frontend built |
| `cargo build --release --features custom-protocol --offline` | Windows native executable built |
| `scripts/verify-entry-ui.py` | 32 screenshots; entry navigation, setting preservation, themes, responsive layouts and keyboard behavior passed |
| `scripts/audit-source.py` | No credential patterns, private runtime files or developer home paths found in the public source selection |
| Packaged `--check-runtime` | 9 checks passed: imports, Korean font, Tesseract OCR, layout model, offline Korean PDF and side-by-side DUAL output |

The packaged check was run after moving the distribution into a different
directory with Korean characters and spaces. PATH was restricted to Windows
system tools; Python/resource overrides and provider keys were removed.
The executable selected its own embedded Python and resources. A fresh mock
Windows profile received the default glossary; no saved key or review session
was present. Network connections were blocked inside the diagnostic process.

The public source starts a new Git history. Developer environments, personal
PDFs, user glossary decisions, cache databases, saved API keys, agent transcripts,
test screenshots and local execution logs are excluded. The Windows package
uses newly installed pinned Python dependencies, not a copy of the developer's
site-packages. Only the static font and layout model were reused as assets.

Limits: this is a relocation/clean-profile test on the build PC, not a test on
a second physical PC or a fresh Windows VM. Tesseract, WebView2 and the Visual
C++ runtime were already installed on that PC and remain documented prerequisites.
Live Gemini quota/model access, paid translations and agent account login are
not covered by this release check. The executable is not code-signed.
