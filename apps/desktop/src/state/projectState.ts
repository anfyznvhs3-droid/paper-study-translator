import { createMockTranslationRun, setStageByPhase, updateRunStages, type TranslationRun } from "../translation/engineAdapters";
import { defaultCustomTheme, type ThemePreset, type ThemeTokens } from "../theme/themeOptions";

/** User-facing failure breakdown surfaced on the result screen (mirrors the
 *  Rust `FailureDiagnosis`). Defined here as a domain type; the bridge imports it. */
export interface FailureDiagnosis {
  summary: string;
  cause: string;
  solution: string;
}

export type ReviewMode = "on" | "off";
export type TranslationMode = "agent" | "machine" | "manual";
export type EngineOption = "codex-agent" | "claude-code-agent" | "antigravity-agent" | "gemini-flash-lite" | "manual-fill";
export type OutputMode = "mono" | "dual";
export type TranslationQuality = "true" | "realistic" | "complete";
export type InputMode = "file" | "folder";
export type JobStatus = "pending" | "running" | "review_wait" | "completed" | "failed" | "paused" | "cancelled" | "skipped";
export type SourceKind = "file" | "folder";

export interface SourceInputItem {
  name: string;
  relativePath?: string;
  sizeBytes?: number;
  kind: SourceKind;
}

export interface SourceFile {
  id: string;
  name: string;
  pages: number;
  status: JobStatus;
  progress: number;
  sizeBytes?: number;
  sourcePath?: string;
  kind: SourceKind;
}

export interface CostEstimate {
  tokens: number;
  costUsd: number;
}

export interface TargetRunResult {
  source_path: string;
  status: "running" | "success" | "failure" | "cancelled" | "skipped";
  message: string;
  output_files: string[];
}
export interface RunResult {
  status?: "success" | "failure" | "paused" | "cancelled";
  targetResults?: TargetRunResult[];
  outputDir?: string;

  ok: boolean;
  message: string;
  outputFiles: string[];
  reviewItems: ReviewItem[];
  diagnosis?: FailureDiagnosis;
}

export type AgentHealth = "active" | "waiting" | "stalled" | "paused";

export interface AgentRunStatus {
  health: AgentHealth;
  current_batch: number;
  total_batches: number;
  completed_batches: number;
  last_activity_seconds: number;
  message: string;
  workspace: string;
  recent_files?: string[];
  recent_response_preview?: string;
}

export type ReviewKind =
  | "translation_incomplete"
  | "image_ocr"
  | "table_overlay"
  | "native_repair"
  | "untranslated_region"
  | "untranslated_source_sentence"
  | "audit_unavailable"
  | "layout_overflow"
  | "agent_direct_pdf"
  | "term_mismatch"
  | "modal_misuse"
  | "acronym_inconsistent"
  | "table_cell_error"
  | "figure_label_error"
  | "residual_english"
  | "quality_gate_fail"
  | "engine_warning"
  | "conflict";

export type ReviewSeverity = "info" | "warning" | "error" | "blocking";
export type ReviewStatus = "open" | "approved" | "rejected" | "resolved";

export interface ReviewItem {
  source_path?: string;
  page: number;
  kind: ReviewKind;
  severity: ReviewSeverity;
  source_text: string;
  translated_text?: string;
  reason: string;
  status: ReviewStatus;
  fitted?: boolean;
}

export interface ReviewItemKey {
  source_path?: string;
  page: number;
  kind: ReviewKind;
  source_text: string;
  translated_text?: string;
}

export interface ProjectState {
  projectName: string;
  runId: string | null;
  jobRunning: boolean;
  reviewOpen: boolean;
  reviewMode: ReviewMode;
  files: SourceFile[];
  inputMode: InputMode;
  translationMode: TranslationMode;
  engine: EngineOption;
  quality: TranslationQuality;
  outputMode: OutputMode;
  activeJobId: string | null;
  translationRun: TranslationRun | null;
  lastRunResult: RunResult | null;
  agentStatus: AgentRunStatus | null;
  themePreset: ThemePreset;
  darkPreset: ThemePreset;
  customTheme: ThemeTokens;
  darkMode: boolean;
  domain: string;
  sharedKnowledgeEnabled: boolean;
}

export type ProjectAction =
  | { type: "setProjectName"; value: string }
  | { type: "setReviewMode"; value: ReviewMode }
  | { type: "setInputMode"; value: InputMode }
  | { type: "addMockFiles" }
  | { type: "addSourceItems"; items: SourceInputItem[]; inputMode: InputMode }
  | { type: "removeSourceItem"; id: string }
  | { type: "setTranslationMode"; value: TranslationMode }
  | { type: "setEngine"; value: EngineOption }
  | { type: "setQuality"; value: TranslationQuality }
  | { type: "setOutputMode"; value: OutputMode }
  | { type: "setDomain"; value: string }
  | { type: "setSharedKnowledgeEnabled"; value: boolean }
  | { type: "setThemePreset"; value: ThemePreset }
  | { type: "setCustomThemeToken"; key: keyof ThemeTokens; value: string }
  | { type: "setDarkMode"; value: boolean }
  | { type: "startMockJob" }
  | { type: "setTargetStatus"; sourcePath: string; status: TargetRunResult["status"] }
  | { type: "completeReview" }
  | { type: "openReview" }
  | { type: "restoreSession"; session: Pick<ProjectState,"runId"|"reviewOpen"|"files"|"activeJobId"|"lastRunResult"|"translationMode"|"engine"|"outputMode"|"reviewMode"|"domain"> }
  | { type: "advanceMockJob" }
  | { type: "approveReviewItems"; keys: ReviewItemKey[] }
  | { type: "approveAllReviewItems" }
  | { type: "setRunPhase"; phase: string }
  | { type: "setAgentStatus"; status: AgentRunStatus | null }
  | { type: "advanceMachineHeartbeat" }
  | { type: "finishMockJob"; status: "success" | "failure" | "paused" | "cancelled"; targetResults?: TargetRunResult[]; outputDir?: string; message?: string; outputFiles?: string[]; reviewItems?: ReviewItem[]; diagnosis?: FailureDiagnosis }
  | { type: "resetToSetup" };

export const initialProjectState: ProjectState = {
  projectName: "새 작업",
  runId: null,
  jobRunning: false,
  reviewOpen: false,
  reviewMode: "on",
  files: [],
  inputMode: "file",
  translationMode: "agent",
  engine: "codex-agent",
  quality: "realistic",
  outputMode: "dual",
  activeJobId: null,
  translationRun: null,
  lastRunResult: null,
  agentStatus: null,
  themePreset: "soft-pink",
  darkPreset: "soft-pink",
  customTheme: defaultCustomTheme,
  darkMode: false,
  domain: "academic",
  sharedKnowledgeEnabled: false
};

export const engineOptionsByMode: Record<TranslationMode, EngineOption[]> = {
  agent: ["codex-agent", "claude-code-agent"],
  machine: ["gemini-flash-lite"],
  manual: ["manual-fill"]
};

export const engineLabels: Record<EngineOption, string> = {
  "codex-agent": "CODEX",
  "claude-code-agent": "CLAUDE CODE",
  "antigravity-agent": "ANTIGRAVITY",
  "gemini-flash-lite": "Gemini Flash-Lite",
  "manual-fill": "Manual"
};

export const translationQualityOptions: ReadonlyArray<TranslationQuality> = ["true", "realistic", "complete"];

export const translationQualityLabels: Record<TranslationQuality, string> = {
  true: "원문 충실",
  realistic: "가독성 균형",
  complete: "완성본 정리"
};

const AGENT_BATCH_PROGRESS_START = 56;
const AGENT_BATCH_PROGRESS_END = 77;

function resetRun(state: ProjectState): ProjectState {
  return { ...state, translationRun: null, lastRunResult: null, agentStatus: null };
}

function matchesReviewItemKey(item: ReviewItem, key: ReviewItemKey): boolean {
  return (
    (item.source_path ?? "") === (key.source_path ?? "") &&
    item.page === key.page &&
    item.kind === key.kind &&
    item.source_text === key.source_text &&
    (item.translated_text ?? "") === (key.translated_text ?? "")
  );
}

function progressFromAgentStatus(status: AgentRunStatus): number | null {
  if (status.total_batches <= 0) {
    return null;
  }

  const completed = Math.max(0, Math.min(status.completed_batches, status.total_batches));
  const ratio = completed / status.total_batches;
  return AGENT_BATCH_PROGRESS_START + Math.floor((AGENT_BATCH_PROGRESS_END - AGENT_BATCH_PROGRESS_START) * ratio);
}

export function projectReducer(state: ProjectState, action: ProjectAction): ProjectState {
  switch (action.type) {
    case "setProjectName":
      return { ...state, projectName: action.value };
    case "setReviewMode":
      return { ...state, reviewMode: action.value };
    case "setInputMode":
      return { ...state, inputMode: action.value };
    case "removeSourceItem": {
      if (state.jobRunning || state.lastRunResult) return state;
      const files = state.files.filter((file) => file.id !== action.id);
      return { ...state, files, activeJobId: files.some((file)=>file.id===state.activeJobId) ? state.activeJobId : files[0]?.id ?? null };
    }
    case "addSourceItems": {
      const files = createSourceFiles(action.items);
      return resetRun({
        ...state,
        inputMode: action.inputMode,
        files,
        activeJobId: files[0]?.id ?? null,
      });
    }
    case "addMockFiles": {
      if (import.meta.env.PROD) {
        return state;
      }

      const items: SourceInputItem[] =
        state.inputMode === "folder"
          ? [
              { name: "FMEA_Foundation_01.pdf", sizeBytes: 2_400_000, kind: "folder", relativePath: "sample/FMEA_Foundation_01.pdf" },
              { name: "IATF_Manual_FMEA.pdf", sizeBytes: 920_000, kind: "folder", relativePath: "sample/IATF_Manual_FMEA.pdf" },
              { name: "Input_Process_Guide.pdf", sizeBytes: 640_000, kind: "folder", relativePath: "sample/Input_Process_Guide.pdf" }
            ]
          : [{ name: "AIAG_VDA_FMEA_Handbook.pdf", sizeBytes: 9_800_000, kind: "file" }];

      const files = createSourceFiles(items);
      return resetRun({ ...state, files, activeJobId: files[0].id });
    }
    case "setTranslationMode": {
      const options = engineOptionsByMode[action.value];
      const nextEngine = options.includes(state.engine) ? state.engine : options[0];
      return resetRun({ ...state, translationMode: action.value, engine: nextEngine });
    }
    case "setEngine":
      return engineOptionsByMode[state.translationMode].includes(action.value)
        ? resetRun({ ...state, engine: action.value }) : state;
    case "setQuality":
      return resetRun({ ...state, quality: action.value });
    case "setOutputMode":
      return resetRun({ ...state, outputMode: action.value });
    case "setDomain":
      return resetRun({ ...state, domain: action.value });
    case "setSharedKnowledgeEnabled":
      return { ...state, sharedKnowledgeEnabled: action.value };
    case "setThemePreset":
      // Light and dark each remember their own preset selection.
      return state.darkMode
        ? { ...state, darkPreset: action.value }
        : { ...state, themePreset: action.value };
    case "setDarkMode":
      return { ...state, darkMode: action.value };
    case "setCustomThemeToken":
      return {
        ...state,
        ...(state.darkMode ? { darkPreset: "custom" as ThemePreset } : { themePreset: "custom" as ThemePreset }),
        customTheme: {
          ...state.customTheme,
          [action.key]: action.value
        }
      };
    case "startMockJob": {
      const nextState = state.files.length === 0 ? projectReducer(state, { type: "addMockFiles" }) : state;
      const runningStatus: JobStatus = "running";
      const startedFiles = nextState.files.map((file, index) =>
        index === 0 ? { ...file, status: runningStatus, progress: Math.max(file.progress, 12) } : file
      );

      return {
        ...nextState,
        jobRunning: true,
        reviewOpen: false,
        runId: "run-"+Date.now()+"-"+Math.random().toString(36).slice(2,10),
        activeJobId: startedFiles[0]?.id ?? null,
        files: startedFiles,
        lastRunResult: null,
        translationRun: updateRunStages(
          createMockTranslationRun({
            engine: nextState.engine,
            mode: nextState.translationMode,
            quality: nextState.quality,
            outputMode: nextState.outputMode,
            reviewMode: nextState.reviewMode,
            files: startedFiles
          }),
          startedFiles[0]?.progress ?? 0
        )
      };
    }
    case "advanceMockJob": {
      const runningStatus: JobStatus = "running";
      const reviewWaitStatus: JobStatus = "review_wait";
      const completedStatus: JobStatus = "completed";
      const nextFiles = state.files.map((file) => {
        if (file.id !== state.activeJobId) {
          return file;
        }

        if (file.status === "review_wait") {
          return { ...file, progress: 100, status: completedStatus };
        }

        const progressLimit = state.reviewMode === "on" ? 88 : 100;
        const nextProgress = Math.min(file.progress + 22, progressLimit);

        return {
          ...file,
          progress: nextProgress,
          status:
            state.reviewMode === "on" && nextProgress >= 88
              ? reviewWaitStatus
              : nextProgress >= 100
                ? completedStatus
                : runningStatus
        };
      });

      const activeFile = nextFiles.find((file) => file.id === state.activeJobId);

      return {
        ...state,
        files: nextFiles,
        translationRun: updateRunStages(state.translationRun, activeFile?.progress ?? 0)
      };
    }
    case "approveAllReviewItems": {
      if (!state.lastRunResult) {
        return state;
      }

      return {
        ...state,
        lastRunResult: {
          ...state.lastRunResult,
          reviewItems: state.lastRunResult.reviewItems.map((item) =>
            item.status === "open" ? { ...item, status: "approved" } : item
          )
        }
      };
    }
    case "approveReviewItems": {
      if (!state.lastRunResult || action.keys.length === 0) {
        return state;
      }

      return {
        ...state,
        lastRunResult: {
          ...state.lastRunResult,
          reviewItems: state.lastRunResult.reviewItems.map((item) =>
            item.status === "open" && action.keys.some((key) => matchesReviewItemKey(item, key))
              ? { ...item, status: "approved" }
              : item
          )
        }
      };
    }
    case "setRunPhase": {
      if (state.activeJobId == null) {
        return state;
      }

      // Rust emits the agent pipeline phases as "agent-extract" / "agent-batch"
      // / "agent-render"; map them to the canonical stage ids so progress and
      // the stage list advance. Without this the lookup misses and the run
      // looks frozen at intake (12%) through the whole agent run.
      const phaseStageAlias: Record<string, string> = {
        "agent-extract": "extract",
        "agent-batch": "translate",
        "agent-render": "consistency"
      };
      const normalizedPhase = phaseStageAlias[action.phase] ?? action.phase;

      const progressByPhase: Record<string, number> = {
        intake: 12,
        extract: 34,
        translate: 56,
        consistency: 78
      };

      const nextProgress = progressByPhase[normalizedPhase];
      if (nextProgress == null) {
        return state;
      }

      const nextFiles = state.files.map((file) =>
        file.id === state.activeJobId ? { ...file, progress: Math.max(file.progress, nextProgress) } : file
      );

      // Reaching the render phase means the live agent batch step has finished;
      // drop the batch monitor so it stops showing a stale "generating 0/N"
      // while the (separate) render runs.
      const reachedRender = normalizedPhase === "consistency";

      return {
        ...state,
        files: nextFiles,
        agentStatus: reachedRender ? null : state.agentStatus,
        translationRun: setStageByPhase(state.translationRun, action.phase)
      };
    }
    case "setAgentStatus": {
      const agentProgress = action.status ? progressFromAgentStatus(action.status) : null;
      const nextFiles =
        agentProgress == null || state.activeJobId == null
          ? state.files
          : state.files.map((file) =>
              file.id === state.activeJobId ? { ...file, progress: Math.max(file.progress, agentProgress) } : file
            );

      return {
        ...state,
        files: nextFiles,
        agentStatus: action.status
      };
    }
    case "advanceMachineHeartbeat":
      // Elapsed time is not evidence of translation completion.
      return state;
    case "setTargetStatus": {
      const file = state.files.find((item) => item.sourcePath === action.sourcePath);
      if (!file) return state;
      const status: JobStatus = action.status === "success" ? (state.reviewMode === "on" ? "review_wait" : "completed")
        : action.status === "failure" ? "failed" : action.status;
      return {...state, activeJobId:action.status === "running" ? file.id : state.activeJobId,
        files:state.files.map((item) => item.id === file.id ? {...item,status,progress:action.status === "success" ? 100 : item.progress} : item),
        translationRun:action.status === "running" ? setStageByPhase(state.translationRun,"intake") : state.translationRun};
    }
    case "restoreSession":
      return {...state,...action.session};
    case "openReview":
      return {...state,reviewOpen:!state.jobRunning && (state.files.some((file)=>file.status==="review_wait") || Boolean(state.lastRunResult?.reviewItems.length))};
    case "completeReview":
      if (!state.lastRunResult || state.lastRunResult.reviewItems.some((item) => item.status === "open")) return state;
      return {...state,reviewOpen:false,files:state.files.map((file) => file.status === "review_wait" ? {...file,status:"completed"} : file)};
    case "finishMockJob": {
      const failedStatus: JobStatus = "failed";
      const pausedStatus: JobStatus = "paused";
      const reviewWaitStatus: JobStatus = "review_wait";
      const completedStatus: JobStatus = "completed";
      if (state.activeJobId == null) {
        return state;
      }

      const nextFiles = state.files.map((file) => {
        const target = action.targetResults?.find((item) => item.source_path === file.sourcePath);
        if (target) {
          const status: JobStatus = target.status === "success" ? (state.reviewMode === "on" ? "review_wait" : "completed")
            : target.status === "failure" ? "failed" : target.status;
          return {...file,status,progress:target.status === "success" ? 100 : file.progress};
        }
        const nextStatus: JobStatus =
          action.status === "cancelled" ? "cancelled" :
          action.status === "paused"
            ? pausedStatus
            : action.status === "failure"
            ? failedStatus
            : state.reviewMode === "on"
              ? reviewWaitStatus
              : completedStatus;

        return { ...file, progress: action.status === "success" ? 100 : file.progress, status: nextStatus };
      });

      const activeFile = nextFiles.find((file) => file.id === state.activeJobId);

      return {
        ...state,
        files: nextFiles,
        jobRunning: false,
        reviewOpen: action.status === "success" && state.reviewMode === "on",
        // Success/failure are terminal, so drop the live batch monitor. A paused
        // run is resumable and should keep the last observed batch snapshot.
        agentStatus: action.status === "paused" ? state.agentStatus : null,
        translationRun: action.status === "success" ? updateRunStages(state.translationRun, 100) : state.translationRun,
        lastRunResult: {
          ok: action.status === "success",
          status: action.status,
          targetResults: action.targetResults,
          outputDir: action.outputDir,
          message:
            action.message ??
            (action.status === "success"
              ? "번역이 완료되었습니다."
              : action.status === "paused"
                ? "처리 시간이 길어 일시 중단되었습니다. 다시 실행하면 새 작업을 시작합니다."
                : "번역 실행에 실패했습니다."),
          outputFiles: action.outputFiles ?? [],
          reviewItems: action.reviewItems ?? [],
          // Already None on success from Rust; the result screen also gates on
          // `failed`, so no need to re-null here.
          diagnosis: action.diagnosis
        }
      };
    }
    case "resetToSetup":
      return resetRun({ ...state, jobRunning: false, reviewOpen: false, runId: null, files: [], activeJobId: null });
    default:
      return state;
  }
}

export function estimateAgentCost(state: ProjectState): CostEstimate {
  const pageCount = state.files.reduce((sum, file) => sum + file.pages, 0) || 24;
  const reviewMultiplier = state.reviewMode === "on" ? 1.35 : 1;
  const qualityMultiplier = state.quality === "complete" ? 1.25 : state.quality === "true" ? 1.12 : 1.0;
  const baseTokens = pageCount * 1450 * reviewMultiplier * qualityMultiplier;
  const tokens = Math.round(baseTokens);

  return {
    tokens,
    costUsd: Number((tokens * 0.000012).toFixed(2))
  };
}

function createSourceFiles(items: SourceInputItem[]): SourceFile[] {
  return items.map((item, index) => ({
    id: `job-${Date.now()}-${index}`,
    name: item.relativePath ?? item.name,
    pages: estimatePageCount(item),
    status: "pending",
    progress: 0,
    sizeBytes: item.sizeBytes,
    sourcePath: item.relativePath,
    kind: item.kind
  }));
}

function estimatePageCount(item: SourceInputItem) {
  const size = item.sizeBytes ?? 800_000;
  const extension = item.name.split(".").pop()?.toLowerCase();
  const divisor = extension === "ppt" || extension === "pptx" ? 180_000 : 95_000;
  return Math.max(1, Math.round(size / divisor));
}
