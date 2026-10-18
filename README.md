# Paper Study Translator

Study university lecture slides and research papers with the original English
and Korean translation side by side. Windows desktop app, with a Korean interface.

- **바로 번역:** use your own Gemini API key and selected model.
- **에이전트 번역:** use a locally installed, authenticated Codex or Claude Code CLI.
- **DUAL PDF:** original on the left, Korean on the right, on the same PDF page.
- **MONO PDF:** Korean translation with the original page layout.
- OCR for English text inside figures; review candidates for unresolved regions,
  preserved numbers/citations, terminology and layout problems.
- Results list and delivery folder contain PDFs. Internal audit/recovery files
  stay in the per-user application data directory.

## 다른 PC에서 실행

1. [Releases](https://github.com/anfyznvhs3-droid/paper-study-translator/releases)에서
   Windows x64 ZIP을 받고 **폴더 전체를 압축 해제**합니다.
2. 아래 Windows 구성요소를 확인합니다. Python을 따로 설치할 필요는 없습니다.
3. `PaperStudyTranslator.exe`를 실행하고 **API 설정**에서 본인의 Gemini 키를
   저장합니다. 기존 PC의 키와 작업 이력은 배포본에 포함되지 않습니다.
4. **바로 번역 → 파일/폴더 선택 → 원문 + 한국어(좌우 비교) → 번역 시작**.
   슬라이드는 PowerPoint에서 PDF로 내보낸 뒤 넣으면 PDF 학습 흐름을 사용할 수 있습니다.
5. 실행 환경에 문제가 있으면 `Check-Runtime.cmd`를 실행합니다. API 호출 없이
   Python·글꼴·문서 모델·OCR·좌우 PDF 생성을 확인합니다.

Windows 10/11 x64 prerequisites:

- [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
  for the desktop interface.
- [Microsoft Visual C++ x64 Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
  for native Python dependencies.
- [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki)
  with English language data for image text. Install to its default location or
  put `tesseract.exe` on PATH. Tesseract is a separate prerequisite, not bundled.

The app requires network access and a configured provider for actual translation.
The runtime check uses synthetic text and blocks network connections; it does not
verify your API quota, model access or a separately installed agent account.
This release is unsigned. No publisher certificate is included.

## Data and privacy

- Writable data: `%LOCALAPPDATA%\PaperStudyTranslator`.
- API keys saved in the UI use Windows DPAPI for the current Windows account.
- Documents are sent to Google only when you choose Gemini translation, or to
  the selected agent through its local CLI when you choose agent translation.
- Output PDFs are saved under `QDT_Output` beside the first input by default.
- The source repository and release contain no API keys, `.env` files, agent
  conversations, user PDFs, translated-document caches, or saved review sessions.
- A new installation starts with the `학술·학습` domain and a generic scholarly
  glossary. Domain edits stay in your own profile and survive app updates.

Review candidates help find problems; they do not guarantee that every diagram,
formula or translation is correct. OCR may miss low-resolution or complex image
text. Keep the original PDF and check the translated result before relying on it.

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
cd apps/desktop
npm run build
cd src-tauri
cargo build --release --features custom-protocol --locked
cd ../../..
python scripts/package-windows.py --exe apps/desktop/src-tauri/target/release/qdt-gemini.exe --assets <asset-directory>
```

The asset directory must contain `SourceHanSerifKR-Regular.ttf` and
`doclayout_yolo_docstructbench_imgsz1024.onnx`. Sources and licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The packager downloads the official
Python embeddable runtime and installs fresh wheels from the dependency lockfile;
it does not copy the developer's installed packages or personal cache database.
Run the packaged `Check-Runtime.cmd` before zipping the whole output directory.
Release verification scope and results: [docs/VERIFICATION.md](docs/VERIFICATION.md).

Compatibility identifiers (`QDT_*`, internal crate names) remain stable. Advanced
development overrides: `QDT_HOME`, `QDT_RESOURCE_ROOT`, `QDT_KNOWLEDGE_BASE`,
`SCHOLAR_TRANSLATOR_PYTHON`, `QDT_TESSERACT`, `QDT_BUNDLED_ASSETS`.
Normal installations do not need an `.env` file or these overrides.

## License

AGPL-3.0; see [LICENSE](LICENSE). This is a modified application built on
Scholar Translator / PDFMathTranslate and other open-source components.
Third-party licenses and corresponding source links are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
