import { Icon } from "../components/Icon";
import { useState } from "react";
import type { ProjectState } from "../state/projectState";
import { SummaryCards } from "../components/SummaryCards";
import { pdfResults } from "../translation/pdfResults";

interface PatchNotesWorkspaceProps {
  state: ProjectState;
}

type PatchNoteStatus = "applied" | "verified" | "watch";

interface PatchNote {
  date: string;
  title: string;
  scope: string;
  details: string[];
  evidence: string;
  status: PatchNoteStatus;
}

const patchNotes: PatchNote[] = [
  {
    date: "2026-10-18",
    title: "두 카드 시작 화면과 작업 설정 통합",
    scope: "시작 화면·작업 준비 — Gemini와 에이전트 진입",
    details: [
      "번역 방식을 고른 뒤 엔진·출력·검수를 반복해서 선택하던 흐름을 정리했습니다. Gemini와 에이전트 카드 전체를 누르면 바로 파일 등록 화면으로 이동합니다.",
      "출력·검수와 에이전트 종류·번역 기준을 작업 준비 화면에서 설정합니다. 방식을 다시 골라도 파일과 출력·검수·번역 기준을 유지하며, 같은 에이전트 방식을 고를 때 Claude가 초기화되던 문제를 수정했습니다.",
      "테두리 없는 두 카드, 문서·에이전트 그림, 로컬 SVG와 공통 버튼·선택창을 사용합니다. 설정 이동이나 방식 선택만으로 번역을 실행하지 않습니다."
    ],
    evidence: "설정 보존 단위 검사와 격리된 브라우저에서 단일 클릭 진입·설정 이동·키보드·화면 크기·테마·실행 요청 값 검증. 검증자료/20261018-두카드시작. 실제 번역 API 호출은 포함하지 않습니다.",
    status: "applied"
  },
  {
    date: "2026-10-18",
    title: "선택 컨트롤 통일과 Google 웹 번역 종료",
    scope: "UI — 드롭다운 8곳, 파일·폴더 전환, API 상태, 접기·펼치기",
    details: [
      "기본 브라우저 드롭다운과 화면별 테두리가 공통 스타일에서 빠져 있던 원인을 수정했습니다. 선택창의 목록까지 같은 테마·44px 높이·14px 글자·8px 모서리를 사용합니다.",
      "파일·폴더 선택 표시는 버튼을 누르면 한 배경이 슬라이드합니다. API 키 상태는 설정 버튼 왼쪽 아이콘으로, 접기·펼치기는 로컬 Lucide SVG로 표시합니다. 제목의 불필요한 포커스 테두리를 제거했습니다.",
      "Google 웹 번역 메뉴와 실행 경로를 제거했습니다. 기존 설정은 Gemini로 읽되 저장된 검수 결정과 PDF 경로는 유지합니다. 연결 검사나 번역은 자동 실행하지 않습니다."
    ],
    evidence: "이전 엔진 설정·검수 복원 회귀 검사, 선택창 키보드/포인터 동작과 밝은·어두운 테마 화면 검증. 실제 번역 API 호출은 검증 범위에서 제외합니다.",
    status: "applied"
  },
  {
    date: "2026-10-18",
    title: "용어집의 중복 분류와 혼합 스타일 정리",
    scope: "용어집 UI — 분류, 용어 목록, 파일 교환, 입력 모달",
    details: [
      "분류 선택을 한 곳으로 모으고 용어 검색·목록을 먼저 배치했습니다. 큰 현재 분류 카드와 버튼처럼 보이던 장식 배지를 제거했습니다.",
      "파일 가져오기·내보내기는 목록 아래에서 펼칩니다. 두 작업의 형식과 실행 버튼을 각각 묶고 입력란·제목·버튼을 공통 크기로 통일했습니다.",
      "분류를 빠르게 바꿀 때 이전 응답이 현재 목록을 덮지 않도록 했습니다. 읽기·저장 오류를 화면에 표시하고 모달의 키보드 초점과 닫기 동작을 보완했습니다."
    ],
    evidence: "가상 IPC 브라우저에서 분류 전환·검색·추가/삭제·파일 교환·오류 복구·모달과 반응형 화면 검증. 실제 사용자 용어집을 수정하거나 번역 API를 호출하지 않습니다.",
    status: "applied"
  },
  {
    date: "2026-10-18",
    title: "패치노트 목록·작은 현황 카드·API 오류 이동",
    scope: "패치노트, 결과·검수 요약, API 설정과 실패 안내",
    details: [
      "패치노트를 검색 가능한 10건 단위 목록으로 정리했습니다. 제목을 누르면 해당 변경의 상세와 검증 기록이 펼쳐집니다.",
      "현황 카드는 작은 라벨과 핵심 값 중심의 공통 컴포넌트로 통일했습니다.",
      "API 및 모델 설정은 기본으로 접습니다. 오류 안내의 이동 버튼은 관련 입력란을 펼치고 초점을 옮깁니다. 이동만으로 키·모델을 바꾸거나 API를 호출하지 않습니다."
    ],
    evidence: "오류 코드별 이동 단위 테스트, 격리된 브라우저에서 목록·반응형·설정 이동 검증. 실제 API 호출은 검증 범위에 포함하지 않습니다.",
    status: "applied"
  },
  {
    date: "2026-10-18",
    title: "PDF 중심 결과 화면과 안내 스타일 정리",
    scope: "산출물·결과 UI — PDF 전달, 내부 검수 자료, 글자 크기",
    details: [
      "검수용 JSON을 PDF와 함께 산출물로 세던 문제를 수정했습니다. 결과 목록과 개수는 PDF만 표시하며, 새 작업은 PDF 폴더에 최종 파일만 모읍니다. 내부 검수 자료와 중간 작업은 보존합니다.",
      "결과 화면은 파일명과 PDF 열기를 먼저 보여줍니다. 긴 입력 경로와 실행 내역은 접고, 정상 완료 때 반복되던 안내 박스와 테두리 요약표를 제거했습니다.",
      "세로 강조선 안내를 제거하고 결과 제목·본문·보조 설명 크기를 통일했습니다. 실제 미번역이나 실패는 문장과 원인으로 계속 표시합니다."
    ],
    evidence: "PDF 필터·복사·이름 충돌·실패 시 보존 테스트, 실제 PDF의 바이트 보존과 결과 화면 검증. 번역 API를 다시 호출하지 않습니다.",
    status: "applied"
  },
  {
    date: "2026-10-17",
    title: "최근 작업 복원과 상태 안내 수정",
    scope: "작업 기록 — 정상 결과의 빈 진단 값, 검수 기록, 안내 표시",
    details: [
      "네이티브 결과의 빈 진단 값(null)을 저장 형식 오류로 거부하던 원인을 수정했습니다. 기존 기록을 삭제하지 않고 검수 결정과 결과 경로를 복원합니다.",
      "문서 전체 검사 경고(페이지 0)와 선택 항목의 빈 값도 저장 계약에 맞게 처리하며, 실제 잘못된 형식은 계속 거부합니다.",
      "상태 안내의 큰 배경 박스와 굵은 테두리를 제거했습니다. Error 접두사 없이 테마에 맞는 간결한 문장으로 표시합니다."
    ],
    evidence: "네이티브 저장 형식 회귀 테스트와 실제 저장 기록 복원, 브라우저 재시작 및 오류 안내 검증. 번역 API를 다시 호출하지 않습니다.",
    status: "applied"
  },
  {
    date: "2026-10-17",
    title: "기존 테마에 맞춘 공통 버튼 복구",
    scope: "UI — 검수, 설정, 작업 준비, 진행, 결과, 용어집",
    details: [
      "뒤에 추가된 CSS가 기존 테두리 없는 버튼을 덮어쓰던 원인을 제거했습니다. 화면별 버튼 규칙을 공통 스타일로 통합했습니다.",
      "주요 동작은 기존 파스텔 그라데이션, 보조 동작은 테마 배경색을 사용합니다. 높이·모서리·문자 크기와 비활성·누름·포커스 상태를 통일했습니다.",
      "검수 화면의 중복 제목, 긴 파일 경로, 고정 회색 테두리와 그림자를 정리했습니다. 검수 결정과 번역 결과는 변경하지 않습니다."
    ],
    evidence: "36개 브라우저 화면에서 버튼 테두리, 공통 크기, 밝은/어두운 4종 테마, 키보드 포커스와 비활성 상태를 확인했습니다. 시각적 선호의 최종 판단은 사용자가 합니다.",
    status: "verified"
  },
  {
    date: "2026-10-17",
    title: "PDF 좌우 비교·그림 OCR·최종 검수 복구",
    scope: "API PDF — 출력, 그림·표 번역, 누락 검사, 작업 준비",
    details: [
      "DUAL PDF는 한 페이지에 원문을 왼쪽, 보정을 마친 한국어 결과를 오른쪽에 배치합니다.",
      "그림 속 영어를 로컬 OCR로 읽어 선택한 모델로 번역합니다. 인식 실패나 배치 실패는 원문을 보존하고 검수 후보로 남깁니다. 모델 차단·보존 검사 실패 문구는 번역 미완료로 먼저 표시하며, 키·권한·한도 오류는 중단합니다.",
      "일반 이탤릭 문장과 누락된 제목을 번역 대상으로 복구하고, 최종 PDF에서 그대로 남은 영어를 검사합니다. 표의 배경·글자 크기와 본문 글자 색상도 보존합니다.",
      "영문 월 이름을 한국어 날짜로 옮길 때 숫자 보존 검사가 오탐하던 문제를 수정했습니다. 날짜·금액 변경은 계속 차단하며, 페이지 번호와 수식만 있는 조각은 API를 호출하지 않습니다.",
      "준비 화면에서 출력·검수 설정을 바로 바꿀 수 있습니다. 모델과 API 설정은 간결하게 표시합니다."
    ],
    evidence: "실제 문제 PDF 3종의 5쪽으로 좌우 배치, 도표 5개 라벨, 이탤릭 본문, 표를 확인했습니다. 검수 후보는 사람이 확인할 항목이며 문서 전체의 번역 정확성을 보증하지 않습니다.",
    status: "verified"
  },

  {
    date: "2026-10-17",
    title: "상태 안내·검수 화면·테마 일관성 개선",
    scope: "UI — 작업 준비, 진행, 검수, 결과, 설정, 피드백",
    details: [
      "고장모드: 후보 확인을 문서 전체 검증으로 오해하게 하는 안내, 테마에 맞지 않는 고정 색상, 후보 수에 따라 늘어나는 비교 화면을 수정했습니다.",
      "검수는 확인 기록만 저장하며 PDF를 교정하지 않습니다. 후보 확인률과 파일 생성 완료를 구분하고, 오류 로그는 상세 영역으로 정리했습니다.",
      "입력 목록에서 파일 제외, 파일 열기 실패 안내, 실제 후보 수 표시, 메일 수신 주소 확인을 추가했습니다.",
      "이 UI 변경 당시 남았던 영어 잔류와 API PDF DUAL 문제는 위의 기능 복구 변경에서 별도로 처리했습니다."
    ],
    evidence: "프론트엔드 테스트와 TypeScript 검사 통과. 가상 작업을 이용한 브라우저 상태 전환·복구 검증 및 밝은/어두운 테마 실화면 점검. 실제 번역과 네이티브 통합 검증은 별도입니다.",
    status: "applied"
  },
  {
    date: "2026-07-03",
    title: "논문 공통 WIKI 자동 적용",
    scope: "knowledge-base/profiles/scholarly / Google Scholar wrapper / Agent/PPTX glossary loader / mixed renderer",
    details: [
      "고장모드 `scholarly-common-term-drift`를 WIKI 규칙으로 흡수했습니다. 논문 공통 헤딩과 메타데이터 라벨을 `knowledge-base/profiles/scholarly/glossary.csv`에 두고, 번역 실행 시 선택 도메인 glossary보다 먼저 자동 병합합니다.",
      "`Abstract`, `Keywords`, `Article history`, `Conflict of interest`, `Data availability`, `References` 같은 항목은 exact-heading 정책으로 기록해 `abstract model` 같은 일반 본문 표현을 과잉 치환하지 않도록 했습니다.",
      "Google/Scholar wrapper, Agent glossary loader, PPTX native loader, mixed renderer가 모두 path-list glossary를 읽을 수 있게 해 profile WIKI와 domain WIKI를 함께 소비합니다."
    ],
    evidence: "qdt_scholar_with_glossary, agent_runner, pptx_native, mixed_renderer path-list 병합 테스트와 Rust runtime glossary 병합 테스트 RED→GREEN 확인",
    status: "verified"
  },
  {
    date: "2026-07-03",
    title: "논문 Abstract 헤딩 다의어 흡수",
    scope: "scholar-translator scholarly phrase override / layout audit / 논문 섹션 헤딩",
    details: [
      "고장모드 `scholarly-heading-polysemy`를 translation/audit 규칙으로 흡수했습니다. 논문 섹션 헤딩 `Abstract`는 일반 형용사 `추상적인`이 아니라 `초록`으로 고정합니다.",
      "`Abstract:`처럼 콜론이 붙은 짧은 헤딩도 `초록:`으로 보존 번역하고, 본문 안의 `abstract model` 같은 일반 문맥은 override하지 않아 과잉 치환을 피합니다.",
      "이미 번역기가 `추상적인`을 반환한 결과는 `scholarly_heading_mistranslation` audit 항목으로 올려 검수 모드에서 놓치지 않게 했습니다."
    ],
    evidence: "test_scholarly_cleanup.py에 Abstract heading override와 audit mistranslation 회귀 테스트 추가 후 RED→GREEN 확인",
    status: "verified"
  },
  {
    date: "2026-07-03",
    title: "약어 설명문 영어 잔류 audit 흡수",
    scope: "scholar-translator layout audit / Google draft residual detection / 논문 abstract·방법론 문장",
    details: [
      "고장모드 `untranslated-source-sentence`를 audit 규칙으로 흡수했습니다. Google draft가 원문 영어 문장을 그대로 섞어 반환하면, 원문에도 있는 단어라는 이유로 residual_english가 놓치던 케이스를 별도 오류로 올립니다.",
      "고장모드 `acronym-explanation-residual`을 추가했습니다. SHERPA, FMEA, CREAM, HEART 같은 도메인 약어 자체는 보존할 수 있지만, `SHERPA is a method used to...`처럼 약어 뒤 설명 문장 전체가 영어로 남으면 검수 대상으로 표시합니다.",
      "이 규칙은 출력 문서를 자동 수정하지 않는 report-only audit입니다. 약어 보존 정책과 문장 번역 정책을 분리해, 도메인 용어 보호가 설명문 미번역으로 확장되는 것을 막습니다."
    ],
    evidence: "test_scholarly_cleanup.py에 acronym explanation residual, source sentence residual 회귀 테스트 추가 후 RED→GREEN 확인",
    status: "verified"
  },
  {
    date: "2026-07-03",
    title: "PPTX 네이티브 번역 경로 추가",
    scope: "PPTX Office XML / Tauri pipeline routing / qdt.pptx_native sidecar / 입력 정책",
    details: [
      "고장모드 `pptx-run-fragmentation`을 postprocess 규칙으로 흡수했습니다. PPTX가 한 문장을 여러 a:t run으로 쪼개도 문단 단위로 합쳐 번역 태스크를 만들고, 첫 run에 번역문을 재배치해 문맥 조각 번역을 피합니다.",
      "고장모드 `pptx-korean-font-fallback`을 렌더링 규칙으로 흡수했습니다. 번역된 run에는 East Asian 폰트(a:ea)를 명시해 PowerPoint의 침묵 폰트 치환을 줄입니다.",
      "고장모드 `pptx-text-overflow`를 레이아웃 규칙으로 흡수했습니다. 번역 후 텍스트 박스에는 normAutofit을 보장해 짧은 영어 라벨이 긴 한국어로 바뀌는 슬라이드형 문서의 넘침 위험을 낮춥니다.",
      "고장모드 `pptx-dual-output-shape`을 출력 정책으로 고정했습니다. PPTX DUAL은 PDF 대역 병기가 아니라 원본 슬라이드 뒤에 번역 슬라이드 clone을 삽입하는 구조로 생성합니다.",
      "고장모드 `ppt-legacy-binary-accepted`를 입력 정책으로 차단했습니다. 구형 .ppt 바이너리는 XML 경로로 안전하게 처리할 수 없어 UI 선택 필터에서 제외하고, Rust 파이프라인에서도 실행 전 미지원으로 진단합니다."
    ],
    evidence: "test_pptx_native.py 5건, Rust PPTX 라우팅/진단 테스트 3건, setupFlowCopy .ppt 제외 테스트, node UI 테스트, cargo test/check로 검증",
    status: "verified"
  },
  {
    date: "2026-07-03",
    title: "도메인 CAT 용어집 상호운용 추가",
    scope: "knowledge-base 도메인 용어집 / OmegaT tab glossary / TBX import-export / qdt CLI",
    details: [
      "고장모드 `cat-import-pollutes-confirmed-glossary`를 서비스 규칙으로 흡수했습니다. 외부 CAT 용어집을 가져올 때 기본 모드는 확정 glossary.csv를 직접 오염시키지 않고 term-decisions.jsonl 후보로 기록합니다.",
      "고장모드 `cat-domain-cross-contamination`을 차단하기 위해 import/export는 항상 knowledge-base/domains/<domain> 단위로 동작합니다. 품질/제조 외 도메인이 늘어나도 각 도메인의 glossary와 decision log가 섞이지 않습니다.",
      "OmegaT tab glossary와 최소 TBX를 지원해 기존 번역사/CAT 생태계와 용어집을 주고받을 수 있게 했습니다. 신뢰 가능한 파일은 --mode confirmed로 glossary.csv에 upsert하고, 기본 candidates 모드는 사람 승인 루프를 유지합니다.",
      "V1 범위는 용어집 상호운용입니다. TMX 번역 메모리와 UI 노출은 다음 단계로 남기고, 현재는 CLI와 도메인 SSOT를 먼저 고정했습니다."
    ],
    evidence: "test_glossary_exchange.py 7건, CLI export/import 테스트 2건, translator-core 113건, node 23건, cargo test 31건, cargo check, scripts/check-all.ps1 전체 게이트 통과",
    status: "verified"
  },
  {
    date: "2026-06-22",
    title: "실패 시 원인·해결방법 안내 (사용자용 고장 진단)",
    scope: "translate 결과 / lib.rs diagnose_failure / 결과 화면",
    details: [
      "지금까지 번역 실패 시 결과 화면에 'mono output validation failed ... latin=12591, cjk=735' 같은 엔진 원시 문자열만 떠서 사용자가 무엇이 문제이고 무엇을 해야 하는지 알 수 없었습니다.",
      "Rust에 고장 분류기 `diagnose_failure(message, exit_code)`를 추가해 알려진 고장모드를 {요약·원인·해결방법}으로 매핑합니다 — 영어 잔류(오검증 vs 실제), 제한시간 초과(exit 124/timeout), 번역 대상 없음, 스캔/이미지 PDF, 산출물 미생성, 파이썬 환경 문제, 그리고 미분류 오류용 일반 폴백(원시 메시지는 기술 상세로 보존).",
      "`TranslateJobResult`에 `diagnosis` 필드를 실어 모든 실패 반환 지점에서 채우고, bridge→상태→결과 화면으로 전달합니다. 결과 화면은 원인/해결방법을 강조해 보여주고 엔진 원시 메시지는 '기술 상세'로 접어둡니다. AGENTS.md의 '고장모드 명명' 원칙을 사용자 표면으로 끌어낸 것."
    ],
    evidence: "Rust diagnose_failure 단위 테스트(알려진 모드 매핑, 성공/일시중단 None, 미분류도 완전한 진단) 통과, lib.rs 31건; tsc --noEmit 클린",
    status: "applied"
  },
  {
    date: "2026-06-22",
    title: "추출 부산물 오검증 재발 차단 (스캐너 둘, 스킵 하나)",
    scope: "산출물 스캔 / mono 검증 (lib.rs)",
    details: [
      "고장모드 `byproduct-validated-as-output` 재발 — 최종 한글 PDF는 정상(latin=7406, cjk=8442, 한글 53%)인데 'mono 검증 실패(latin=12591, cjk=735)'로 표시됐습니다. 검증 대상이 최종본이 아니라 `.qdt-agent/<문서>/layout-extract`의 번역 전 추출 부산물 mono였습니다.",
      "지난 수정은 `.qdt-agent` 스킵을 재귀 스캐너 `collect_recent_artifacts` 한 곳에만 넣었는데, `enforce_output_mode`는 **다른 스캐너** `collect_recent_pdfs`로 출력 디렉터리를 다시 훑었고 여기엔 스킵이 없어 부산물 mono를 산출물 목록에 재유입시켰습니다.",
      "스킵 판단을 공유 헬퍼 `is_agent_workspace_dir`로 추출해 두 스캐너가 모두 사용하게 했습니다 — 새 스캐너가 생겨도 같은 버그를 조용히 되살리지 못하도록."
    ],
    evidence: "신규 Rust 테스트(enforce_output_mode가 .qdt-agent 부산물 스킵, RED→GREEN) + 기존 스캔 스킵 테스트, lib.rs 29건 통과; 실샘플: 최종본 cjk=8442로 정상인데 검증이 부산물(cjk=735)을 보던 것 확인",
    status: "applied"
  },
  {
    date: "2026-06-22",
    title: "차트/다이어그램 라벨 번역 (figure 텍스트 overlay)",
    scope: "scholar_translator.graphic_overlay / high_level 렌더 파이프라인",
    details: [
      "고장모드 `figure-label-left-untranslated`를 서비스 규칙으로 흡수했습니다 — Figure 1 플로우 박스의 'APQP Gate', 'PPAP Release', 'lot disposition' 같은 다이어그램 라벨이 한글 변환 없이 영어로 남던 문제입니다.",
      "근본원인: 페이지프레임 converter는 레이아웃 모델이 'figure'로 분류한 영역의 텍스트를 수식·로고처럼 원문 그대로 보존(재출력)합니다. 다이어그램 라벨도 이 영역 안에 있어 보존됐고, 번역본은 'Figure N…' 캡션 하나로 통째 병합돼 따로 렌더됐습니다(박스는 영어).",
      "표 셀 overlay와 동일한 패턴의 figure 라벨 overlay를 추가했습니다 — 추출 단계의 converter가 이미 쓰는 권위 신호(DocLayout 'figure' 클래스 박스)만 재사용해 박스 안 라벨 span을 박스별로 추출·번역·in-place 덮어쓰기 합니다. 숫자/단위/약어/신조어(SARGAL)는 기존 표 셀 분류 규칙으로 그대로 보존합니다(하드코딩 라벨 목록 없음).",
      "킬스위치 `QDT_GRAPHIC_TEXT_OVERLAY`(기본 ON). 좌표는 페이지 정규화(0~1)로 전달해 DPI·크롭박스에 무관합니다. figure 라벨은 단일행 박스라 표 셀 페인터로는 줄높이가 안 맞아, 전용 라벨 페인터(라벨 상단 기준·넉넉한 박스·폰트 축소 적합)를 따로 둡니다."
    ],
    evidence: "graphic_overlay 단위 4건 통과(스킵 필터·기하 선택·렌더·노옵), scholar-translator 38건 통과; 실샘플 결정 검증: 모델이 figure 영역 검출 → 라벨 63개 선택(번역 49 / 보존 14: 숫자·약어·SARGAL) → 49개 페인트, 전부 figure 영역 내부·이탈 0",
    status: "applied"
  },
  {
    date: "2026-06-22",
    title: "표 셀 단어내부 부분치환 오염 + 추출 누락 (단일 근본원인)",
    scope: "scholar_translator.table_structure 헤더 override",
    details: [
      "고장모드 `intra-word-header-splice`를 서비스 규칙으로 흡수했습니다 — 'Daily setup verification…' → 'Daily set상승 verification…', 'register updated…' → 'register 상승dated…' 처럼 단어 내부가 오염되던 문제입니다.",
      "근본원인(증상 둘, 버그 하나): `_translate_compound_header`가 HEADER_TRANSLATIONS 키('up' 등)를 앵커 없는 substring으로 치환해 'setUP'·'UPdated' 단어 내부에 매칭됐습니다. 이 override는 추출·렌더 양쪽에서 번역 호출 '이전'에 검사되므로, non-None 결과가 ① 추출 단계에서 해당 셀을 task로 기록하지 못하게(추출 누락) 막고 ② 렌더 단계에서 맵 조회를 건너뛰고 오염값을 직출력했습니다.",
      "기존 `_looks_like_prose` 가드(>6단어/다중문장)는 6단어+세미콜론 셀을 못 걸렀습니다 — 단어 단위 가드는 단어 '내부' 치환 버그엔 틀린 레이어라, 정규식 자체를 알파벳 인접 금지(`(?<![A-Za-z])`…`(?![A-Za-z])`)로 앵커링했습니다. 하이픈·숫자·점·공백 인접 헤더('up-slope', 'variant no.')는 그대로 번역됩니다."
    ],
    evidence: "신규 단위(단어내부 치환 금지 RED→GREEN, 구두점 인접 헤더 회귀) + scholar-translator 34→38건 통과; 실샘플: 문제 셀 2개가 override None으로 번역 경로 라우팅, 둘 다 page 3 실제 find_tables 셀임을 확인",
    status: "applied"
  },
  {
    date: "2026-06-22",
    title: "Agent 배치 번역 병렬화 + 글자수 균등 분할",
    scope: "qdt.agent_runner 배치 실행 / Codex CLI",
    details: [
      "고장모드 `sequential-batch-walltime`을 서비스 규칙으로 흡수했습니다 — 8쪽 샘플 기준 Codex 배치 4개를 순차 호출해 ~7.5분이 걸렸고, 이 중 배치 단계가 전체 시간의 약 90%였습니다(추출·렌더는 ~1분).",
      "배치는 서로 독립이고 CodexCliEngine.complete()가 호출마다 고유 임시파일을 써서 재진입 안전이므로, ThreadPoolExecutor로 동시 실행하도록 바꿨습니다(기본 동시 4). 결과는 제출 순서로 수집해 by_id 결정성과 '첫 배치 에러 전파'를 순차 경로와 동일하게 보존합니다.",
      "항목 수(32개) 고정 분할은 밀집 페이지를 한 배치에 몰아 느린 단일 배치를 만들었습니다. split_batches에 글자수 상한을 추가해 연속성(문맥)을 유지한 채 batch당 약 총량/동시수 글자로 균등 분할하고, 180초 타임아웃 안쪽(상한 10000자)·콜드스타트 과다 방지(하한 2000자)로 클램프합니다.",
      "동시 실행 수는 `QDT_AGENT_BATCH_CONCURRENCY` 환경변수로 조정합니다(레이트리밋 여유 시 상향)."
    ],
    evidence: "동시 실행(peak≥2)·순서 보존, 글자 상한 분할·연속성 테스트 추가, translator-core 104건 통과, 8쪽 샘플 배치 단계 ~7.5분 → ~2분",
    status: "applied"
  },
  {
    date: "2026-06-22",
    title: "진행률 batch 카운트 정확화 + 완료 시 모니터 해제",
    scope: "Agent progress snapshot / projectState",
    details: [
      "고장모드 `finished-run-looks-stuck`을 서비스 규칙으로 흡수했습니다 — 번역이 끝났는데도 화면이 'batch 1/4 · 정체 의심'에 멈춰 보이는 문제입니다.",
      "total_batches를 작업수÷배치크기로 추정해 글자 균등분할에서 분모가 틀렸습니다(완료 4개인데 추정과 어긋남). 실제 생성된 prompt 파일 수(authoritative)로 교체했습니다.",
      "finishMockJob이 종료 시 agentStatus를 비우지 않아 결과 화면에 모니터가 남았습니다 — 특히 Codex 타임아웃 실패는 render 단계를 못 거쳐 '정체 의심' 패널이 실패 메시지 옆에 박혀 있었습니다. 모든 종료 상태(성공/실패/일시중단)에서 모니터를 해제합니다."
    ],
    evidence: "Rust agent progress snapshot 테스트 통과, tsc --noEmit 클린",
    status: "applied"
  },
  {
    date: "2026-06-21",
    title: "추출 부산물 오검증으로 인한 거짓 실패 제거",
    scope: "mono 출력 검증 / 산출물 스캔",
    details: [
      "고장모드 `byproduct-validated-as-output`을 서비스 규칙으로 흡수했습니다 — 최종 한글 PDF는 정상(latin=2339, cjk=12102)인데 'mono 검증 실패'로 표시되던 문제입니다.",
      "산출물 재귀 스캔이 작업공간 `.qdt-agent/<문서>/layout-extract`까지 내려가, 의도적으로 번역 전 상태인 추출 부산물 렌더(영어, latin=33262)를 산출물로 집어 검증에 걸렸습니다.",
      "재귀 스캔에서 `.qdt-agent` 작업공간을 제외해 실제 산출물(<output>/<문서>-ko)만 검증하도록 했습니다."
    ],
    evidence: "scan_recent_artifact_outputs_skips_qdt_agent_workspace 회귀 테스트 추가, 실 샘플로 최종 한글 vs 부산물 영어 비율 대조 확인",
    status: "applied"
  },
  {
    date: "2026-06-21",
    title: "런타임 경로 이식성 + C 드라이브 완전 탈출",
    scope: "Python 인터프리터 / 캐시 / 임시 경로",
    details: [
      "고장모드 `hardcoded-dev-path`와 `c-drive-runtime-coupling`을 서비스 규칙으로 흡수했습니다 — python 경로가 특정 개발 PC 경로로 하드코딩돼 있었고, 캐시·모델·임시파일이 C: 사용자 프로필에 묶여 정크션이 깨지면 서비스가 멈췄습니다.",
      "python 경로를 포터블하게 해석합니다: SCHOLAR_TRANSLATOR_PYTHON → repo의 .venv → PYENV_ROOT의 3.12.x → PATH. 개인 경로를 repo에서 제거했고, clone 후 setup.ps1 한 번이면 결정적 인터프리터를 씁니다.",
      "모든 Python 자식 프로세스의 캐시/임시를 repo-상대 .qdt-home으로 보냅니다(QDT_HOME으로 변경 가능). 렌더/추출은 USERPROFILE/HOME까지 덮어써 `~/.cache`를 하드코딩하는 babeldoc 레이아웃 모델 캐시도 이동시키고, Codex 에이전트는 CLI 인증을 위해 실제 프로필을 유지합니다."
    ],
    evidence: "cargo check 통과, default_scholar_translator_home 벤더 경로 테스트, babeldoc/scholar/~ 경로가 .qdt-home으로 해석됨 실측",
    status: "applied"
  },
  {
    date: "2026-06-20",
    title: "용어 일관성 드리프트 흡수",
    scope: "Translation map / glossary candidate mining / audit review",
    details: [
      "고장모드 `batch-term-consistency-drift`를 서비스 규칙으로 흡수했습니다 — 배치 단위 Agent 번역이 같은 도메인 용어나 표 셀을 배치마다 다르게 번역해 문서 전체 용어 일관성이 깨지는 문제입니다(예: disposition→처분 판정/처리 판정, control→관리/통제, control sample→샘플/시료).",
      "특정 용어를 하드코딩으로 강제하지 않고, translation-map에서 용어→번역 후보와 충돌을 일반적으로 채굴하는 `glossary_candidates`를 추가했습니다. 매 Agent 실행마다 맵 옆에 `glossary-candidates.json`(후보 + 셀 충돌 + 단어 단위 용어 드리프트)을 생성합니다.",
      "report-only라 번역 결과를 절대 바꾸지 않습니다(안전, kill switch 불필요). 채굴된 후보는 도메인 용어집을 풍부화해 다음 실행 프롬프트로 일관성을 끌어올리는 재사용 루프가 됩니다 — 사람/용어집이 루프에 있어 강제가 아닙니다.",
      "도메인 중립: 용어 목록을 박지 않고, 짧은 term-like 항목과 단어 단위 표준 한글 부재로 일반 검출합니다."
    ],
    evidence: "test_glossary_candidates.py 6개(term-like 판정·정규화·후보 추출·셀 충돌·용어 드리프트·리포트) 통과, 도메인-트랩 샘플에서 후보 90·용어 드리프트 12건(control·disposition·sample 포함) 추출 확인",
    status: "applied"
  },
  {
    date: "2026-06-18",
    title: "Agent 렌더링 일원화",
    scope: "Agent translation-map / layout-preserved offline renderer",
    details: [
      "고장모드 `agent-direct-pdf-reflow-collapse`를 서비스 규칙으로 흡수했습니다.",
      "Agent가 PDF를 직접 재조판하지 않고, 기존 레이아웃 보존 renderer가 추출한 task를 Agent가 translation-map으로 채우도록 경계를 나눴습니다.",
      "최종 PDF/HTML/MD 산출은 `scholar_translator` offline renderer가 담당하므로 논문/PPTX형 PDF의 2단, 그림, 표 배치가 direct renderer 때문에 무너지는 경로를 차단했습니다.",
      "direct PDF Agent 출력은 production PDF가 아니라 중간 map/debug sidecar 역할로 낮췄습니다."
    ],
    evidence: "Agent runner args 테스트와 direct sidecar PDF 미생성 테스트 추가",
    status: "applied"
  },
  {
    date: "2026-06-17",
    title: "Agent 실제 진행/정체 상태 표시",
    scope: "Agent direct PDF runtime monitor / progress UI",
    details: [
      "고장모드 `alive-but-stalled`와 `resumable wall-clock pause`를 서비스 규칙으로 흡수했습니다.",
      "프로세스 생존 여부만으로 진행 중이라고 표시하지 않고, batch response 생성 수와 stdout/stderr/workspace 수정 시간을 함께 봅니다.",
      "진행 화면에 현재 batch, 전체 batch, 완료 batch, 마지막 활동, 중간 저장 위치를 표시하고, Agent 작업 모니터에서 최근 prompt/response 파일과 최근 응답 미리보기를 펼쳐볼 수 있게 했습니다.",
      "2분 이상 새 batch 활동이 없으면 `정체 의심`, 4분 이상 새 batch response가 없으면 조기 `일시 중단됨`으로 잘라 다시 실행 시 이어가기 가능하다는 메시지를 냅니다."
    ],
    evidence: "Rust agent progress snapshot 테스트, projectState paused 상태 테스트, ProgressWorkspace 문자열 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-17",
    title: "Agent 장문 PDF timeout 재시작 방어",
    scope: "Agent direct PDF batch runner",
    details: [
      "고장모드 `Agent CLI long-document timeout`을 서비스 규칙으로 흡수했습니다.",
      "장문 PDF에서 task가 수백 개로 늘어날 때 batch size 8로 Codex CLI를 100회 이상 호출하던 병목을 direct PDF 기본 32개 batch로 완화했습니다.",
      "timeout 후 재실행할 때 `.qdt-agent/<문서명>/agent-batches`의 완료 response를 재사용하고, 같은 task 목록이면 작업 폴더를 삭제하지 않습니다.",
      "`QDT_DIRECT_AGENT_BATCH_ITEMS` 환경변수로 direct PDF batch size를 조정할 수 있게 해 문서 난이도와 CLI 안정성에 따라 운영자가 튜닝할 수 있습니다."
    ],
    evidence: "test_agent_runner.py resume 테스트, test_direct_pdf_agent.py batch size/workspace 보존 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-17",
    title: "Agent 검수 후보 과다 생성 억제",
    scope: "Agent direct PDF audit / 검수 UI",
    details: [
      "고장모드 `audit 후보 과다 생성`을 서비스 규칙으로 흡수했습니다.",
      "정상 번역된 Agent direct PDF 문단은 검수 큐에 올리지 않고, 빈 번역문·원문 그대로 반환·한글 없는 번역문만 위험 후보로 분리합니다.",
      "검수 화면은 open 상태 후보만 큐에 표시하고, 대량 후보를 한 번에 처리할 수 있도록 `후보 전체 확인` 액션을 추가했습니다.",
      "후보가 10개를 넘으면 드래그 스크롤 대신 `이전 10개`/`다음 10개`/`현재 10개 확인` 배치 흐름으로 처리합니다.",
      "검수 결정 toolbar를 상단 고정하고 `현재 항목 확인`을 추가해 스크롤 위치와 상관없이 단일 항목 처리가 가능하게 했습니다.",
      "논문 저자명, 이메일, 참고문헌형 식별자는 원문 보존 가능성이 높으므로 후보 생성을 줄여 실제 판단이 필요한 항목에 집중하게 했습니다."
    ],
    evidence: "test_direct_pdf_agent.py audit 후보 축소 테스트, reviewWorkspaceCopy.test.mjs bulk approval 문구 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-17",
    title: "Agent PDF direct-read 파이프라인 추가",
    scope: "Codex/Claude Agent 모드 PDF 번역",
    details: [
      "고장모드 `Agent PDF direct-read bypass failure`를 서비스 규칙으로 흡수했습니다.",
      "Agent 모드가 더 이상 scholar-translator layout fragment를 Codex 입력으로 쓰지 않고, PyMuPDF/pdfminer 기반 원문 텍스트를 직접 chunk로 추출합니다.",
      "Codex/Claude Agent 배치 번역은 JSON schema 계약을 유지하고, 결과는 MD/HTML/간단 PDF/audit sidecar로 생성합니다.",
      "문서별 `.qdt-agent/<문서명>` 작업 폴더를 초기화해 이전 batch 응답과 translation-map이 다음 실행에 섞이지 않게 정리했습니다.",
      "scholar-translator layout-preserving 경로는 Google/Scholar 계열에 남기고, Agent 계열은 문서 이해 기반 경로로 분리했습니다."
    ],
    evidence: "tests/test_direct_pdf_agent.py 4건 통과, 원본 PDF 텍스트 직접 추출과 fake Agent 산출물 생성 검증",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "논문 PDF 표/후면부 조각 번역 보정",
    scope: "scholar-translator table cell / fragmented scholarly text",
    details: [
      "표 제목 내부에서 welding, Variant 같은 단어가 조각나 '웰딩', 'V아리안트'처럼 섞여 번역되는 문제를 fragment 고장모드로 등록했습니다.",
      "표 셀은 header/value/unit/identifier로 분류하고, header 계열만 일반 번역 맵으로 처리하는 generic table cell layer를 추가했습니다.",
      "Data availability, Conflict of interest 문구가 through/h, of/interest처럼 끊겨 '제공 시간', '갈등 오 f 관심'으로 출력되는 문제를 fragment override로 보정합니다.",
      "Supplementary DOI가 s4/3/452...처럼 여러 블록으로 갈라지는 경우 번역 전에 하나의 DOI로 결합하고, 빈 문자열 override도 실제 출력에 적용되도록 수정했습니다.",
      "Abbreviations 블록은 약어 라벨을 보존하고 정의만 한국어로 정돈하는 전용 경로를 적용합니다."
    ],
    evidence: "test_scholarly_cleanup.py 13개 단위 테스트, py_compile, welding 논문 PDF 재번역 검증",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "PDF 표 셀 단위 번역 overlay 추가",
    scope: "scholar-translator table cell overlay",
    details: [
      "논문 PDF 표 본문이 번역되지 않는 원인은 OCR이 아니라 doclayout의 table 영역이 예약 영역으로 마스킹되어 번역 문단 스택에 들어가지 않는 구조임을 확인했습니다.",
      "table 마스크를 단순 해제하면 표 셀 텍스트는 번역되지만 셀 좌표가 유지되지 않고 한 문단처럼 풀려 표 레이아웃이 붕괴되는 것을 실제 welding 논문 PDF로 확인했습니다.",
      "기본 번역 경로는 table 마스크를 계속 닫아 표 레이아웃을 보존하고, mono PDF 저장 후 PyMuPDF table finder로 잡힌 셀 안쪽에만 번역 라벨을 overlay합니다.",
      "숫자, 단위, 행 식별자, A/B/C 같은 열 표식은 보존하고, 표 헤더와 설명 라벨만 도메인 맵 또는 선택 번역기로 처리합니다.",
      "문제가 있는 문서에서는 QDT_TABLE_CELL_OVERLAY=0으로 셀 overlay를 끌 수 있습니다."
    ],
    evidence: "welding 논문 PDF 재번역 115개 셀 overlay, p.5/p.6 렌더 검수, test_table_overlay.py 추가",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "논문 PDF 레이아웃 오염 방어 규칙 추가",
    scope: "scholar-translator PDF 전처리 및 audit",
    details: [
      "표 내부 라벨 A/B/C/D가 본문 문단에 섞여 '디'처럼 번역되는 고장모드를 등록하고, 번역 전 원문 정화 단계에서 제거합니다.",
      "문자 단위로 깨진 DOI/URL 패턴을 원문 DOI 형태로 복원해 링크 식별자가 번역기에서 분해되지 않도록 했습니다.",
      "References 섹션부터는 참고문헌 추적성을 우선해 번역하지 않고 원문 그대로 보존합니다.",
      "Conflict of interest가 '갈등 오 f 관심'처럼 깨지거나 DOI/URL이 손상된 경우 scholar PDF artifact audit 항목으로 표시합니다."
    ],
    evidence: "test_scholarly_cleanup.py 단위 테스트 추가 및 scholar-translator py_compile 검증",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "논문 PDF 프로파일 분류 추가",
    scope: "pdf_scholarly 판정 기준",
    details: [
      "DOI, Abstract, References, Keywords, Fig./Table 캡션, Introduction/Conclusion, 이메일, 2단 레이아웃 신호를 점수화합니다.",
      "scholarly score가 기준 이상이면 일반 PDF와 구분해 논문 PDF로 분류합니다.",
      "논문 PDF는 번역 경로는 유지하되, 영어 잔류/표/그림/참고문헌 검수 기준을 별도로 적용할 수 있는 스위치로 사용합니다.",
      "인용 마커 [1], DOI, ORCID, URL, 이메일, 도메인 문자열은 번역하지 않고 원문 그대로 보존하도록 프롬프트 규칙을 강화했습니다.",
      "Table 하나만 있는 일반 문서가 논문으로 오분류되지 않도록 강한 신호를 함께 요구합니다."
    ],
    evidence: "ScholarlyText profile과 scanned/general/mixed/scholarly 단위 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "스캔 PDF 미지원 정책 고정",
    scope: "이미지 기반 PDF, 텍스트 레이어가 거의 없는 PDF",
    details: [
      "OCR/vision 경로는 처리 비용과 구현 무게가 커서 현재 버전에서는 미구현으로 명확히 고정했습니다.",
      "번역 실행 전 PDF 프로파일을 검사해 텍스트 레이어가 거의 없고 이미지 페이지가 많은 PDF는 실행 전에 차단합니다.",
      "PPTX, 일반 PDF, 논문 PDF, MIX PDF는 계속 지원하되 내부 처리 경로만 분리하는 정책으로 정리했습니다.",
      "스캔 PDF로 보이면 실패 결과에 '스캔 PDF 또는 이미지 기반 PDF는 현재 버전에서 지원하지 않습니다' 메시지를 표시합니다."
    ],
    evidence: "PDF profile classifier 추가, scanned/general scholarly/mixed profile 단위 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-13",
    title: "논문 PDF mono 검증 기준 보정",
    scope: "Pulsed operation of a DC welding power source in resistance projection welding 논문",
    details: [
      "20페이지 논문 PDF를 Google draft 경로로 실제 변환해 mono/dual 산출물이 생성되는지 확인했습니다.",
      "논문 mono 출력은 DOI, 저자명, 단위, 약어, 표 내부 영어, 참고문헌 때문에 라틴 문자가 많이 남을 수 있어 기존 영어 과다 실패 기준을 완화했습니다.",
      "기술 슬라이드처럼 API, 코드, 모델명 영어가 남는 한국어 우세 mono 산출물은 실패가 아니라 검수 가능 산출물로 통과하도록 기준을 분리했습니다.",
      "Abstract는 '초록', Nomenclature는 '기호 설명', resistance projection welding은 '저항 프로젝션 용접' 등 용접 논문 핵심 용어를 에이전트 프롬프트 규칙에 추가했습니다.",
      "표 내부 헤더와 그림 내부 라벨은 scholar-translator 기본 경로에서 영어가 남는 한계가 있어 검수 대상으로 분리했습니다."
    ],
    evidence: "20p 논문 mono/dual 생성, p.1/p.6/p.11/p.17/p.20 렌더 검수, scholarly latin-heavy mono 단위 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "사용자 피드백 접수 화면 추가",
    scope: "FEEDBACK 메뉴, PDF 페이지 캡처, 불편 사항 메일 초안",
    details: [
      "사이드바에 FEEDBACK 메뉴를 추가해 사용자가 번역 품질, 레이아웃 깨짐, 앱 사용성 문제를 바로 기록할 수 있게 했습니다.",
      "PDF 캡처하기 버튼은 선택한 PDF의 지정 페이지를 PNG로 렌더링하고 미리보기와 캡처 파일 경로를 남깁니다.",
      "메일 작성하기는 프로젝트 상태, 문제 PDF 경로, 캡처 PNG 경로, 사용자가 입력한 내용을 제작자 메일 초안에 자동 입력합니다."
    ],
    evidence: "Tauri PDF capture command, FeedbackWorkspace, sidebar route 추가 및 desktop build 검증",
    status: "applied"
  },
  {
    date: "2026-06-12",
    title: "표 셀 번역 검수 강화",
    scope: "Week 7-2 Policy Feedback Theory p.17 비교표",
    details: [
      "표 블록에서 row label과 본문 셀이 합쳐질 때 생기는 오역을 검수 규칙으로 잡습니다.",
      "policy window는 '정책의 창', stream은 '흐름', feedback effects는 '피드백 효과'로 고정합니다.",
      "PFT의 피드백 메커니즘 문장과 MSF의 흐름 결합 문장을 기계번역 용어 메모리에 추가했습니다.",
      "mono 산출물에 followed, feedback effects, policy window, stream 같은 영어 원문이 남으면 검수 대상으로 올립니다."
    ],
    evidence: "Week 7-2 p.17 표에서 발견한 policy window/stream/feedback residual 오류 재현 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "표 라벨 명사형 번역 및 굵기 보존",
    scope: "Week 10-1 p.3/p.4 비교표의 Focus, Actors, How?, 정책학 표 셀",
    details: [
      "표의 왼쪽 행 라벨이나 짧은 헤더는 문장 동사로 번역하지 않고 명사형 라벨로 고정합니다.",
      "Focus는 '집중하다'가 아니라 '분석 초점', How?는 '작동 방식'으로 처리합니다.",
      "원문 PDF span의 bold 여부를 추출해 번역 텍스트 렌더링과 layout audit에 반영합니다.",
      "Actors 행의 'Focuses more on...' 설명문은 행위자 목록이 아니라 PFT 설명문으로 번역하도록 고정했습니다."
    ],
    evidence: "Focus/How?/Actors 설명문 용어 테스트 및 bold span 감지 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "MIX PDF + mono 출력 라우팅 보정",
    scope: "7-1, 7-2, 9-1처럼 원문과 기존 한국어가 섞인 PDF",
    details: [
      "mono 요청인데 혼합 언어 PDF로 감지되면 scholar-translator 일반 경로가 아니라 mixed renderer 경로를 타게 했습니다.",
      "dual 요청은 기존처럼 일반 번역 경로를 유지해서 원문 병기 출력과 충돌하지 않게 했습니다."
    ],
    evidence: "mixed 입력 감지 시 mono는 MixedRenderer, dual은 ScholarTranslator로 분기하는 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "선택한 엔진/프롬프트가 MIX 경로에도 전달되도록 수정",
    scope: "Codex, Claude Code, Antigravity, Google Translate Draft",
    details: [
      "mixed renderer가 더 이상 Google 고정 번역기로만 돌지 않고 앱에서 선택한 service:model 값을 받습니다.",
      "에이전트 번역에서는 품질 레벨이 반영된 프롬프트 파일을 renderer에 넘기도록 연결했습니다."
    ],
    evidence: "mixed renderer에 --service, --prompt 인자 추가 및 service:model 파싱 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "가짜 mono 완료 방지 검수",
    scope: "mono라고 저장됐지만 영어가 과다하게 남는 결과물",
    details: [
      "일반 번역 경로에서 mono 산출물이 영어 비율이 높은 PDF로 나오면 성공 처리하지 않도록 품질 게이트를 추가했습니다.",
      "사용자가 본 Week 11-1처럼 파일명은 mono인데 내용은 사실상 mixed인 결과를 잡기 위한 방어선입니다."
    ],
    evidence: "영어 과다 PDF reject, 한국어 우세 PDF accept 단위 테스트 추가",
    status: "verified"
  },
  {
    date: "2026-06-12",
    title: "MIX renderer 검증 범위 확장",
    scope: "PDF 레이아웃 보존, 프롬프트 로딩, 한국어 간격 보정",
    details: [
      "프롬프트 파일을 Template으로 읽어 번역기에 전달하는 경로를 테스트했습니다.",
      "kiwipiepy가 있는 환경에서는 PDF 추출로 깨진 한국어 간격 보정 테스트가 돌도록 분리했습니다."
    ],
    evidence: "mixed renderer unittest 31개 통과, kiwipiepy 미설치 환경은 spacing 정책 테스트만 skip",
    status: "verified"
  }
];

const statusLabels: Record<PatchNoteStatus, string> = {
  applied: "적용됨",
  verified: "검증됨",
  watch: "관찰 필요"
};

export function PatchNotesWorkspace({ state }: PatchNotesWorkspaceProps) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const artifactCount = pdfResults(state.lastRunResult?.outputFiles ?? []).length;
  const verifiedCount = patchNotes.filter((note) => note.status === "verified").length;
  const filtered = patchNotes.filter(note => `${note.title} ${note.date} ${note.scope}`.toLowerCase().includes(query.trim().toLowerCase()));
  const pageCount = Math.max(1, Math.ceil(filtered.length / 10));
  const visible = filtered.slice(page * 10, page * 10 + 10);
  function movePage(next: number) { setPage(next); setExpanded(null); }

  return (
    <section className="patch-notes-workspace" aria-labelledby="patch-notes-title">
      <div className="patch-history-heading">
        <h2 id="patch-notes-title">패치노트</h2>
        <span>변경 및 검증 기록</span>
      </div>
      <SummaryCards label="패치노트 요약" items={[
        {label:"업데이트",value:patchNotes.length,unit:"건"},
        {label:"검증 기록",value:verifiedCount,unit:"건"},
        {label:"최근 PDF",value:artifactCount,unit:"개"}
      ]} />
      <section className="patch-history-panel" aria-label="업데이트 목록">
        <div className="patch-history-tools">
          <span role="status">{filtered.length}건 · 최신순</span>
          <input type="search" aria-label="패치노트 검색" placeholder="제목·날짜 검색" value={query}
            onChange={event => { setQuery(event.currentTarget.value); movePage(0); }} />
        </div>
        <div>
          {visible.map(note => {
            const key = `${note.date}-${note.title}`;
            return <details key={key} className="patch-note-row" open={expanded === key}>
              <summary onClick={event => { event.preventDefault(); setExpanded(expanded === key ? null : key); }}>
                <span className="patch-note-row-heading"><span className="patch-note-title">{note.title}</span><time dateTime={note.date}>{note.date}</time></span>
                <span className="patch-note-status">{statusLabels[note.status]}</span>
              <Icon name="chevron" className="disclosure-icon" /></summary>
              <div className="patch-note-body">
                <p>{note.scope}</p>
                <ul>{note.details.map(detail => <li key={detail}>{detail}</li>)}</ul>
                <p className="patch-note-evidence">검증 기록 · {note.evidence}</p>
              </div>
            </details>;
          })}
          {!filtered.length ? <p className="patch-history-empty">검색 결과가 없습니다.</p> : null}
        </div>
        <nav className="patch-history-pagination" aria-label="패치노트 페이지">
          <button type="button" className="secondary-button" disabled={page === 0} onClick={() => movePage(page - 1)}>이전 페이지</button>
          <span>{page + 1} / {pageCount}</span>
          <button type="button" className="secondary-button" disabled={page + 1 >= pageCount} onClick={() => movePage(page + 1)}>다음 페이지</button>
        </nav>
      </section>
    </section>
  );
}
