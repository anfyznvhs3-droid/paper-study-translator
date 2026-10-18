# Development

## Build from source (Windows x64)

Install Python 3.12 x64, Node.js 22 LTS, Rust stable with the MSVC toolchain,
Visual Studio C++ build tools and the Windows prerequisites above.

```powershell
git clone https://github.com/anfyznvhs3-droid/paper-study-translator.git
cd paper-study-translator
powershell -ExecutionPolicy Bypass -File setup.ps1
cd apps/desktop
npm ci
npm run tauri dev
```

`setup.ps1 -Python <path-to-python.exe>` selects a particular Python 3.12 install.
It creates `.venv` and installs the pinned runtime set. Source runs download the
layout model and Korean font on their first PDF translation.

Verification from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-all.ps1
cd apps/desktop
npm run build
cd ../..
```

Optional UI checks use `playwright` with Chromium and isolated mock data:
`python scripts/verify-entry-ui.py` (see the other `verify-*-ui.py` scripts).

Release build:

```powershell
python scripts/build-windows.py
python scripts/package-windows.py --exe .release-work/release-target/release/qdt-gemini.exe --assets <asset-directory>
```

Use the release script so the application and every Rust dependency are compiled
with source paths remapped to generic locations. It respects `CARGO_HOME` and
supports `--offline` and `--target-dir`. The executable audit rejects developer
home paths, absolute Rust source paths and credential patterns; packaging repeats
this check before creating a distribution. Direct `cargo build` is suitable for
development, but does not apply these release privacy settings.

The asset directory must contain `SourceHanSerifKR-Regular.ttf` and
`doclayout_yolo_docstructbench_imgsz1024.onnx`. Sources and licenses are listed in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). The packager downloads the official
Python embeddable runtime and installs fresh wheels from the dependency lockfile;
it does not copy the developer's installed packages or personal cache database.
Run the packaged `Check-Runtime.cmd` before zipping the whole output directory.
Release verification scope and results: [Verification](VERIFICATION.md).

Compatibility identifiers (`QDT_*`, internal crate names) remain stable. Advanced
development overrides: `QDT_HOME`, `QDT_RESOURCE_ROOT`, `QDT_KNOWLEDGE_BASE`,
`SCHOLAR_TRANSLATOR_PYTHON`, `QDT_TESSERACT`, `QDT_BUNDLED_ASSETS`.
Normal installations do not need an `.env` file or these overrides.
