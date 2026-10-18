<p align="center">
  <img src="apps/desktop/src/assets/app-icon.png" width="64" alt="Paper Study Translator 아이콘">
</p>

<h1 align="center">Paper Study Translator</h1>

<p align="center"><strong>논문과 강의자료, 원문 옆에서 한국어로 읽으세요.</strong><br>
Study papers and lecture slides with English and Korean side by side.</p>

<p align="center">
  <a href="https://github.com/anfyznvhs3-droid/paper-study-translator/releases/latest">Windows 다운로드</a> ·
  <a href="docs/SHOWCASE.md">실제 결과 자세히 보기</a> ·
  <a href="#시작하기">시작하기</a> ·
  <a href="docs/DEVELOPMENT.md">개발 문서</a>
</p>

<p align="center">Windows x64 · 한국어 UI · Gemini API / Codex / Claude Code</p>

## 원문과 번역을 한 페이지에

**DUAL PDF는 왼쪽에 영어 원문, 오른쪽에 한국어 번역을 배치합니다.**
일반 PDF 뷰어에서 열어 문장과 배치를 나란히 비교할 수 있습니다.
한국어만 읽고 싶을 때는 **MONO**를 선택하세요.

<p>
  <img src="docs/assets/paper-abstract-en.png" width="49%" alt="공개 논문 초록의 영어 원문 확대">
  <img src="docs/assets/paper-abstract-ko.png" width="49%" alt="같은 초록을 앱에서 출력한 한국어 번역 확대">
</p>

*실제 DUAL 결과의 초록 영역을 확대했습니다. 왼쪽은 원문, 오른쪽은 번역문입니다.*

[전체 DUAL PDF 내려받기](https://github.com/anfyznvhs3-droid/paper-study-translator/releases/download/v0.1.0/paper-dual-example.pdf)
· [원문 논문](https://aclanthology.org/2025.emnlp-demos.71/)

예시: Ouyang 외(2025), *PDFMathTranslate: Scientific Document Translation Preserving Layouts*,
p. 918, CC BY 4.0. **Codex 에이전트가 작성한 번역을 앱 v0.1.0의 PDF 엔진으로 출력**했습니다.
원문에 있는 프로젝트 이름·수치·주장은 해당 논문의 내용입니다.
[출처와 생성 조건](docs/SHOWCASE.md)을 함께 공개합니다.

<details>
<summary>한 페이지 전체의 좌우 배치 보기</summary>

![논문 첫 페이지의 영어·한국어 DUAL PDF 실제 출력](docs/assets/paper-dual.png)

</details>

## 그림 안의 영어도 OCR로

텍스트를 선택할 수 없는 이미지 속 글자는 OCR로 읽고 한국어를 배치합니다.
아래는 **실제 펭귄 측정 데이터로 만든 이미지 차트**를 처리한 결과입니다.

![실제 데이터 차트의 OCR 번역: 원문은 왼쪽, 한국어 제목·축·범례는 오른쪽](docs/assets/ocr-chart-dual.png)

- 제목·표본 수·범례·축 이름 **7곳을 번역**했습니다.
- 측정값 **342건**을 표시한 산점도 영역은 번역 전후 픽셀이 동일했습니다.
- 인식이 불확실하거나 번역되지 않은 영역은 **검수 후보**로 남깁니다.

[OCR 비교 PDF 내려받기](https://github.com/anfyznvhs3-droid/paper-study-translator/releases/download/v0.1.0/ocr-chart-dual-example.pdf)
· [데이터 출처: palmerpenguins](https://github.com/allisonhorst/palmerpenguins)
· [확인한 결과와 한계](docs/SHOWCASE.md#이미지-차트의-ocr-번역)

원자료 344건 중 두 측정값의 결측이 없는 342건을 사용했습니다. 데이터는 CC0이며,
이 소개용 차트를 이미지 한 장으로 PDF에 넣었습니다. 입력 PDF의 선택 가능한 텍스트는 0자입니다.
수치는 이 예시에서 확인한 결과이며 전체 문서의 번역·OCR 정확도를 뜻하지 않습니다.

## 두 가지 번역 방식

![Paper Study Translator의 Gemini와 에이전트 번역 선택 화면](docs/assets/app-start.png)

| 방식 | 준비할 것 | 사용 흐름 |
| --- | --- | --- |
| **바로 번역** | 본인의 Gemini API 키 | 설정에서 키·모델 등록 → 파일 선택 → 번역 |
| **에이전트 번역** | 설치·로그인된 Codex 또는 Claude Code CLI | 에이전트 선택 → 파일 선택 → 번역 |

*v0.1.0의 실제 프런트엔드를 개인정보 없는 미리보기 환경에서 캡처했습니다.*

파일/폴더 등록, MONO/DUAL, 검수 ON/OFF를 작업 준비 화면에서 선택합니다.
검수에서는 원문·번역문과 자동 수집 후보를 비교하고 용어를 관리할 수 있습니다.
결과 목록과 전달 폴더에는 **PDF만** 표시하며 내부 감사·복구 파일은 사용자 데이터 폴더에 보관합니다.

## 시작하기

1. [Releases](https://github.com/anfyznvhs3-droid/paper-study-translator/releases/latest)에서
   **Windows x64 ZIP**을 받고 폴더 전체를 압축 해제합니다. Python은 포함되어 있습니다.
2. 아래 Windows 구성요소를 설치합니다.
3. `PaperStudyTranslator.exe` 실행 → **API 설정**에서 본인의 키와 모델을 저장합니다.
4. **바로 번역 → 파일/폴더 선택 → 원문 + 한국어(좌우 비교) → 번역 시작**.
   PowerPoint 강의자료는 PDF로 내보낸 뒤 넣으면 이 README와 같은 PDF 학습 흐름으로 사용할 수 있습니다.
5. 완료 후 PDF를 열어 확인합니다. 실행 환경 문제가 있으면 `Check-Runtime.cmd`로 진단합니다.

| Windows 10/11 x64 구성요소 | 용도 |
| --- | --- |
| [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) | 앱 화면 |
| [Microsoft Visual C++ x64 Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) | PDF 처리 런타임 |
| [Tesseract OCR + English 언어 데이터](https://github.com/UB-Mannheim/tesseract/wiki) | 이미지 속 영어 인식 |

Tesseract는 별도 설치가 필요합니다. 기본 위치에 설치하거나 `tesseract.exe`를 PATH에 등록하세요.
실제 번역에는 네트워크와 선택한 서비스의 이용 권한이 필요합니다. Gemini 비용·한도는 본인의
Google 프로젝트에, 에이전트 이용 조건은 해당 계정에 따릅니다. 배포 실행 파일은 코드 서명되지 않았습니다.

## 데이터와 검수

- API 키는 현재 Windows 계정의 **DPAPI**로 암호화해 저장합니다.
- Gemini를 선택하면 번역할 내용이 Google로, 에이전트를 선택하면 해당 로컬 CLI를 통해 선택한 서비스로 전달됩니다.
- 사용자 설정·검수 기록: `%LOCALAPPDATA%\PaperStudyTranslator`.
- 기본 PDF 저장 위치: 첫 입력 파일 옆의 `QDT_Output`.
- 새 설치에는 개인 키·문서·대화 로그·기존 검수 기록이 들어 있지 않습니다. 기본 용어집은 `학술·학습`입니다.

OCR은 작은 글씨·회전된 글씨·복잡한 배경을 놓치거나 도형을 글자로 오인할 수 있습니다.
검수 ON은 자동 수집된 후보를 확인하는 기능입니다. 모든 번역 오류의 탐지나 PDF 자동 수정을 보장하지 않으므로
논문을 인용하거나 제출하기 전에 원문과 최종 PDF를 확인하세요.

## 문서와 검증

- [실제 예시, 출처, 확인한 한계](docs/SHOWCASE.md)
- [예시 재생성 스크립트와 번역 맵](docs/examples/ATTRIBUTION.md)
- [소스 설치·빌드·배포](docs/DEVELOPMENT.md)
- [v0.1.0 검증 범위](docs/VERIFICATION.md): 507개 테스트와 별도 런타임·UI 확인. 다른 물리 PC에서의 검증은 아직 포함하지 않습니다.
- [문제 신고](https://github.com/anfyznvhs3-droid/paper-study-translator/issues): 오류 코드와 재현 순서를 알려주세요. API 키나 비공개 문서는 올리지 마세요.

## License & credits

앱 소스는 **AGPL-3.0**입니다. [LICENSE](LICENSE)와 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 확인하세요.
Scholar Translator / PDFMathTranslate 등 오픈소스 구성요소를 바탕으로 개발했습니다.
README의 논문 발췌·번역 이미지와 데이터에는 [별도 출처 및 라이선스](docs/examples/ATTRIBUTION.md)가 적용됩니다.
