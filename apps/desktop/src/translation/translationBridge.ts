import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type {
  EngineOption,
  FailureDiagnosis,
  OutputMode,
  ReviewMode,
  ReviewItem,
  AgentRunStatus,
  SourceFile,
  TranslationMode,
  TranslationQuality,
  TargetRunResult
} from "../state/projectState";

export type { FailureDiagnosis };

export interface BridgeRunRequest {
  files: string[];
  engine: EngineOption;
  mode: TranslationMode;
  quality: TranslationQuality;
  outputMode: OutputMode;
  reviewMode: ReviewMode;
  domain: string;
  sharedKnowledgeEnabled: boolean;
  outputDir?: string;
}

export interface BridgeRunResult {
  ok: boolean;
  status: "success" | "failure" | "paused" | "cancelled";
  targetResults?: TargetRunResult[];
  outputDir?: string;
  message: string;
  outputFiles: string[];
  reviewItems: ReviewItem[];
  diagnosis?: FailureDiagnosis;
}

interface ProgressEventPayload {
  phase: string;
  target?: TargetRunResult;
  batch?: number;
  totalBatches?: number;
  message?: string;
  agent_status?: AgentRunStatus;
}

function toPath(file: SourceFile): string | null {
  const absolute = file.sourcePath?.trim();
  return absolute || null;
}

export function canRunRealAgentEngine(files: SourceFile[]): boolean {
  return files.every((file) => Boolean(toPath(file)));
}

export async function runAgentTranslation(
  request: BridgeRunRequest,
  onProgress?: (payload: ProgressEventPayload) => void
): Promise<BridgeRunResult> {
  const unlisteners: Array<() => void> = [];

  try {
    if (onProgress) {
      unlisteners.push(await listen<ProgressEventPayload>("translation-progress", (event) => {
        onProgress(event.payload);
      }));
      unlisteners.push(await listen<TargetRunResult>("translation-target", (event) => {
        onProgress({phase:"target",target:event.payload});
      }));
    }

    const result = await invoke<{ ok: boolean; message: string; output_files: string[]; review_items: ReviewItem[]; diagnosis?: FailureDiagnosis; exit_code?: number; output_dir?: string; target_results?: TargetRunResult[] }>(
      "run_translation_job",
      {
        request: {
          files: request.files,
          engine: request.engine,
          mode: request.mode,
          quality: request.quality,
          output_mode: request.outputMode,
          review_mode: request.reviewMode,
          domain: request.domain,
          shared_knowledge: request.sharedKnowledgeEnabled,
          output_dir: request.outputDir
        }
      }
    );

    return {
      ok: result.ok,
      status: result.ok ? "success" : result.exit_code === 130 || result.message.includes("[QDT_CANCELLED]") ? "cancelled" : result.message.includes("일시 중단") ? "paused" : "failure",
      targetResults: result.target_results,
      outputDir: result.output_dir,
      message: result.message,
      outputFiles: result.output_files ?? [],
      reviewItems: result.review_items ?? [],
      diagnosis: result.diagnosis
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      status: message.includes("[QDT_CANCELLED]") ? "cancelled" : message.includes("일시 중단") ? "paused" : "failure",
      message: `번역 실행 실패: ${message}`,
      outputFiles: [],
      outputDir: request.outputDir,
      targetResults: request.files.map((source_path)=>({source_path,status:message.includes("[QDT_CANCELLED]")?"cancelled" as const:"failure" as const,message,output_files:[]})),
      reviewItems: [],
      diagnosis: {summary:"번역 실행 실패",cause:message,solution:"메시지의 고장 코드를 확인하고 설정 또는 입력 파일을 확인하세요."}
    };
  } finally {
    unlisteners.forEach((unlisten) => unlisten());
  }
}

export function buildBridgeRequestFromState(
  files: SourceFile[],
  state: Pick<BridgeRunRequest, "engine" | "mode" | "quality" | "outputMode" | "reviewMode" | "domain" | "sharedKnowledgeEnabled">
): BridgeRunRequest | null {
  const sourcePaths = files
    .map((file) => toPath(file))
    .filter((path): path is string => Boolean(path));

  if (sourcePaths.length === 0 || sourcePaths.length !== files.length) {
    return null;
  }

  return {
    files: sourcePaths,
    engine: state.engine,
    mode: state.mode,
    quality: state.quality,
    outputMode: state.outputMode,
    reviewMode: state.reviewMode,
    domain: state.domain,
    sharedKnowledgeEnabled: state.sharedKnowledgeEnabled,
    outputDir: defaultOutputDir(sourcePaths[0])
  };
}

function defaultOutputDir(sourcePath: string) {
  const normalized = sourcePath.replace(/\//g, "\\");
  const index = normalized.lastIndexOf("\\");
  if (index < 0) {
    return undefined;
  }

  return `${normalized.slice(0, index)}\\QDT_Output`;
}

export const cancelTranslation = () => invoke<boolean>("cancel_translation_job");
