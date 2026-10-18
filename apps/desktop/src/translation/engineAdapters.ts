import type { EngineOption, OutputMode, ReviewMode, SourceFile, TranslationMode, TranslationQuality } from "../state/projectState";

export type TranslationStageStatus = "waiting" | "running" | "done";

export interface TranslationStage {
  id: string;
  label: string;
  description: string;
  progressAt: number;
  status: TranslationStageStatus;
}

export interface TranslationReviewPoint {
  source: string;
  target: string;
  type: string;
  note: string;
}

export interface TranslationRun {
  engine: EngineOption;
  engineName: string;
  mode: TranslationMode;
  quality: TranslationQuality;
  outputMode: OutputMode;
  reviewMode: ReviewMode;
  summary: string;
  stages: TranslationStage[];
  reviewPoints: TranslationReviewPoint[];
}

export interface TranslationEngineRequest {
  engine: EngineOption;
  mode: TranslationMode;
  quality: TranslationQuality;
  outputMode: OutputMode;
  reviewMode: ReviewMode;
  files: SourceFile[];
}

interface EngineProfile {
  name: string;
  summary: string;
  stageTone: string;
}

const engineProfiles: Record<EngineOption, EngineProfile> = {
  "codex-agent": {
    name: "CODEX",
    summary: "문맥 보존, 용어 일관성, 기준 표현을 함께 고려해 번역합니다.",
    stageTone: "코덱스"
  },
  "claude-code-agent": {
    name: "CLAUDE CODE",
    summary: "문장 구조를 보존하고 전문 용어 번역 정확도를 높이기 위해 검증 중심으로 작업합니다.",
    stageTone: "클로드코드"
  },
  "antigravity-agent": {
    name: "ANTIGRAVITY",
    summary: "규격 문서 특성에 맞춰 번역 규칙을 일괄 적용하고 품질 검토를 보강합니다.",
    stageTone: "안티그라비티"
  },
  "gemini-flash-lite": {
    name: "Gemini Flash-Lite",
    summary: "Gemini API로 한국어 번역본을 생성합니다. API 키와 선택 모델의 사용 권한이 필요합니다.",
    stageTone: "Gemini"
  },
  "manual-fill": {
    name: "Manual",
    summary: "자동 번역 없이 수작업 입력 또는 교정 모드에서 사용하는 결과 패턴입니다.",
    stageTone: "수동입력"
  }
};

const qualityTone: Record<TranslationQuality, string> = {
  true: "정확성 중심",
  realistic: "균형형 실무 스타일",
  complete: "완성도 강화"
};

export function createMockTranslationRun(request: TranslationEngineRequest): TranslationRun {
  const profile = engineProfiles[request.engine];
  const reviewEnabled = request.reviewMode === "on";

  return {
    engine: request.engine,
    engineName: profile.name,
    mode: request.mode,
    quality: request.quality,
    outputMode: request.outputMode,
    reviewMode: request.reviewMode,
    summary: request.mode === "machine" ? profile.summary : `${profile.summary} (품질: ${qualityTone[request.quality]})`,
    stages: createStages(profile.stageTone, reviewEnabled),
    reviewPoints: reviewEnabled ? createReviewPoints(request.mode, request.quality) : []
  };
}

export function updateRunStages(run: TranslationRun | null, progress: number): TranslationRun | null {
  if (!run) {
    return null;
  }

  return {
    ...run,
    stages: run.stages.map((stage) => ({
      ...stage,
      status: progress >= stage.progressAt ? "done" : isCurrentStage(run.stages, stage.id, progress) ? "running" : "waiting"
    }))
  };
}

const phaseOrder: readonly string[] = ["intake", "extract", "translate", "consistency"];
const phaseAlias: Record<string, string> = {
  "agent-extract": "extract",
  "agent-batch": "translate",
  "agent-render": "consistency"
};

export function setStageByPhase(run: TranslationRun | null, phase: string): TranslationRun | null {
  if (!run) {
    return null;
  }

  const normalizedPhase = phaseAlias[phase] ?? phase;
  const phaseIndex = phaseOrder.indexOf(normalizedPhase);
  if (phaseIndex === -1) {
    return run;
  }

  return {
    ...run,
    stages: run.stages.map((stage) => {
      const stageIndex = phaseOrder.indexOf(stage.id);
      if (stageIndex === -1) {
        return stage;
      }

      const status: TranslationStageStatus =
        stageIndex < phaseIndex ? "done" : stageIndex === phaseIndex ? "running" : "waiting";

      return { ...stage, status };
    })
  };
}

export function getEngineName(engine: EngineOption) {
  return engineProfiles[engine].name;
}

function createStages(stageTone: string, reviewEnabled: boolean): TranslationStage[] {
  const finalStage = reviewEnabled
    ? {
        id: "review-queue",
        label: "검수 대기",
        description: "자동 후보와 생성된 파일을 사용자가 확인합니다.",
        progressAt: 88
      }
    : {
        id: "package",
        label: "출력 완료",
        description: "선택한 형식으로 번역 결과를 패키징합니다.",
        progressAt: 100
      };

  return [
    {
      id: "intake",
      label: "입력 수집",
      description: "요청한 파일/폴더를 판독하고 대상 페이지를 인식합니다.",
      progressAt: 12
    },
    {
      id: "extract",
      label: "문서 추출",
      description: "텍스트와 표, 그림 캡션을 추출해 번역 가능 형태로 정리합니다.",
      progressAt: 34
    },
    {
      id: "translate",
      label: `${stageTone} 번역`,
      description: "문장별 번역을 수행하고 용어 규칙을 반영해 후보를 생성합니다.",
      progressAt: 56
    },
    {
      id: "consistency",
      label: "결과 파일 확인",
      description: "생성된 파일과 실행 결과를 확인합니다. 내용 검수는 별도로 진행합니다.",
      progressAt: 78
    },
    finalStage
  ].map((stage) => ({ ...stage, status: "waiting" as const }));
}

function createReviewPoints(mode: TranslationMode, quality: TranslationQuality): TranslationReviewPoint[] {
  const base = [
    {
      source: "shall retain",
      target: "유지하여야 한다(shall)",
      type: "강제 규정",
      note: "규정 문구는 원문 의미를 보존해 번역합니다."
    },
    {
      source: "should",
      target: "해야 한다(should)",
      type: "권고",
      note: "요구사항과 권고문은 구분해 번역합니다."
    },
    {
      source: "field issues",
      target: "현장 이슈",
      type: "문구",
      note: "사전 동의어(Registration Approval)처럼 용어 사전 적용 우선."
    }
  ];

  const extra = mode === "machine"
    ? [
        {
          source: "machine draft",
          target: "기계번역 초안",
          type: "기계 출력",
          note: "기계 번역 결과에서 고유용어 표기는 따로 교차 확인 권장."
        }
      ]
    : [
        {
          source: mode === "agent" ? "agent review" : "manual fill",
          target: mode === "agent" ? "에이전트 리뷰" : "수동 작성",
          type: "모드 구분",
          note: "도메인 용어 우선순위는 사용자 규칙에 따라 반영됩니다."
        }
      ];

  if (quality === "true") {
    return [
      ...base,
      {
        source: "failure mode",
        target: "고장 형태",
        type: "도메인 규칙",
        note: "FMEA 문맥에서 고유 규칙을 적용해 충실히 번역합니다."
      },
      ...extra
    ];
  }

  return [...base, ...extra];
}

function isCurrentStage(stages: TranslationStage[], stageId: string, progress: number) {
  const stageIndex = stages.findIndex((stage) => stage.id === stageId);
  const previous = stages[stageIndex - 1];
  const current = stages[stageIndex];
  return Boolean(current && progress < current.progressAt && (!previous || progress >= previous.progressAt));
}
