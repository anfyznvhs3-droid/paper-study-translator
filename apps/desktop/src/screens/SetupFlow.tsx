import { Select } from "../components/Select";
import { Icon } from "../components/Icon";
import { geminiModels, getEngineSettings, type EngineSettings } from "../translation/engineSettingsBridge";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { SegmentedControl } from "../components/SegmentedControl";
import { engineLabels, engineOptionsByMode, translationQualityLabels, translationQualityOptions, estimateAgentCost, type InputMode, type ProjectAction, type ProjectState, type SourceInputItem } from "../state/projectState";
import { buildBridgeRequestFromState, runAgentTranslation } from "../translation/translationBridge";

interface SetupFlowProps {
  state: ProjectState;
  dispatch: React.Dispatch<ProjectAction>;
  onReconfigureMode: () => void;
  onOpenSettings: () => void;
}

type SelectableFile = File & {
  path?: string;
  webkitRelativePath?: string;
};

export function SetupFlow({ state, dispatch, onReconfigureMode, onOpenSettings }: SetupFlowProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [engineSettings, setEngineSettings] = useState<EngineSettings | null>(null);
  const [settingsError, setSettingsError] = useState("");
  const isGemini = state.engine === "gemini-flash-lite";
  const selectedModel = geminiModels.find((item) => item.id === engineSettings?.model);
  useEffect(() => {
    if (!isGemini) return;
    let active = true;
    void getEngineSettings().then((value) => { if (active) setEngineSettings(value); })
      .catch((error: unknown) => { if (active) setSettingsError(String(error)); });
    return () => { active = false; };
  }, [isGemini]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const cost = estimateAgentCost(state);
  const inputLabel = state.inputMode === "file" ? "파일" : "폴더";
  const canEstimateVolume = state.files.length > 0 && state.files.every((file)=>Boolean(file.sizeBytes));

  // HTML5 drag-and-drop never reaches the DOM in Tauri (the webview intercepts
  // OS-level drops), and the resulting File objects have no real filesystem path.
  // Use Tauri's own drag-drop event, which provides absolute paths directly.
  useEffect(() => {
    const unlistenPromise = getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === "enter") {
        setIsDragging(true);
      } else if (event.payload.type === "drop") {
        setIsDragging(false);
        dispatch({
          type: "addSourceItems",
          inputMode: state.inputMode,
          items: event.payload.paths.map((path) => ({
            name: basename(path),
            relativePath: path,
            kind: state.inputMode
          }))
        });
      } else if (event.payload.type === "leave") {
        setIsDragging(false);
      }
    });

    return () => {
      void unlistenPromise.then((unlisten) => unlisten());
    };
  }, [dispatch, state.inputMode]);

  const addSelectedItems = (event: ChangeEvent<HTMLInputElement>, inputMode: InputMode) => {
    addFiles(event.currentTarget.files, inputMode);
    event.currentTarget.value = "";
  };

  const addFiles = (files: FileList | null, inputMode: InputMode) => {
    const items = filesToInputItems(files, inputMode);
    if (items.length === 0) {
      return;
    }

    dispatch({ type: "addSourceItems", items, inputMode });
  };

  const selectNativeTargets = async () => {
    try {
      const selected = await open(
        state.inputMode === "folder"
          ? { directory: true, multiple: false }
          : {
              multiple: true,
              filters: [{ name: "PDF/PPTX", extensions: ["pdf", "pptx"] }]
            }
      );

      const paths = Array.isArray(selected) ? selected : selected ? [selected] : [];
      if (paths.length === 0) {
        return;
      }

      dispatch({
        type: "addSourceItems",
        inputMode: state.inputMode,
        items: paths.map((path) => ({
          name: basename(path),
          relativePath: path,
          kind: state.inputMode
        }))
      });
    } catch (error) {
      console.warn("[native picker fallback]", error);
      if (state.inputMode === "file") {
        fileInputRef.current?.click();
      } else {
        folderInputRef.current?.click();
      }
    }
  };

  const handleStartTranslation = async () => {
    if (state.files.length === 0) {
      return;
    }

    dispatch({ type: "startMockJob" });

    if (state.translationMode === "manual") {
      return;
    }

    const bridgeRequest = buildBridgeRequestFromState(state.files, {
      engine: state.engine,
      mode: state.translationMode,
      quality: state.quality,
      outputMode: state.outputMode,
      reviewMode: state.reviewMode,
      domain: state.domain,
      sharedKnowledgeEnabled: state.sharedKnowledgeEnabled
    });

    if (!bridgeRequest) {
      dispatch({
        type: "finishMockJob",
        status: "failure",
        message: "파일 경로를 확인할 수 없습니다. 드래그 대신 파일 선택 버튼으로 다시 등록하세요.",
        outputFiles: []
      });
      return;
    }

    const result = await runAgentTranslation(bridgeRequest, (progress) => {
      if (progress.target) dispatch({ type:"setTargetStatus", sourcePath:progress.target.source_path, status:progress.target.status });
      else dispatch({ type: "setRunPhase", phase: progress.phase });
      if (progress.agent_status) {
        dispatch({ type: "setAgentStatus", status: progress.agent_status });
      }
    });
    dispatch({
      type: "finishMockJob",
      status: result.status,
      targetResults: result.targetResults,
      outputDir: result.outputDir,
      message: result.message,
      outputFiles: result.outputFiles,
      reviewItems: result.reviewItems,
      diagnosis: result.diagnosis
    });
    if (!result.ok) {
      console.warn("[translation bridge]", result.message);
    }
  };

  return (
    <section className="setup-panel workbench-only setup-panel-minimal" aria-labelledby="setup-title" id="setup">
      <div className="section-heading">
        <span>작업 현황</span>
        <h2 id="setup-title">번역 준비</h2>
      </div>

      <div className="setup-status-strip" aria-label="현재 작업 설정">
        <div>
          <span>방식</span>
          <strong>{state.translationMode === "machine" ? "Gemini 번역" : "에이전트 번역"}</strong>
        </div>
        <label className="setup-inline-setting">
          <span>출력</span>
          <Select label="출력 방식" value={state.outputMode} onChange={value => dispatch({type:"setOutputMode",value:value as ProjectState["outputMode"]})} options={[{value:"mono",label:"한국어만"},{value:"dual",label:"좌우 비교 · 원문 + 한국어"}]} />
        </label>
        <label className="setup-inline-setting">
          <span>검수</span>
          <Select label="검수 방식" value={state.reviewMode} onChange={value => dispatch({type:"setReviewMode",value:value as ProjectState["reviewMode"]})} options={[{value:"on",label:"ON · 후보 확인"},{value:"off",label:"OFF · 바로 결과"}]} />
        </label>
        <div>
          <span>대상</span>
          <strong>{state.files.length > 0 ? `${state.files.length}개 대상` : "미선택"}</strong>
        </div>
        <button type="button" className="secondary-button setup-strip-action" onClick={onReconfigureMode}>
          방식 변경
        </button>
      </div>

      {state.translationMode === "agent" ? (
        <div className="setup-agent-options">
          <label>
            <span>에이전트</span>
            <Select label="에이전트" value={state.engine} onChange={value => dispatch({type:"setEngine",value:value as ProjectState["engine"]})} options={engineOptionsByMode.agent.map(value => ({value,label:engineLabels[value]}))} />
          </label>
          <label>
            <span>번역 기준</span>
            <Select label="번역 기준" value={state.quality} onChange={value => dispatch({type:"setQuality",value:value as ProjectState["quality"]})} options={translationQualityOptions.map(value => ({value,label:translationQualityLabels[value]}))} />
          </label>
        </div>
      ) : null}

      <SegmentedControl<InputMode>
        label="등록 방식"
        value={state.inputMode}
        onChange={(value) => dispatch({ type: "setInputMode", value })}
        options={[
          { value: "file", label: "파일" },
          { value: "folder", label: "폴더" }
        ]}
      />

      <input
        ref={fileInputRef}
        hidden
        aria-label="번역 파일 선택"
        type="file"
        accept=".pdf,.pptx"
        multiple
        onChange={(event) => addSelectedItems(event, "file")}
      />
      <input
        ref={folderInputRef}
        hidden
        aria-label="번역 폴더 선택"
        type="file"
        multiple
        onChange={(event) => addSelectedItems(event, "folder")}
        {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
      />

      <div className="setup-minimal-grid">
        <div className={`file-box file-box-minimal${isDragging ? " is-dragging" : ""}`}>
          <div>
            <span>PDF/PPTX</span>
            <strong>{state.files.length > 0 ? `${state.files.length}개 대상 선택됨` : `${inputLabel}를 끌어오거나 선택하세요`}</strong>
          </div>
          <button type="button" className="secondary-button" onClick={() => void selectNativeTargets()}>
            {inputLabel} 선택
          </button>
        </div>

      </div>

      <div className="setup-engine-line">
        <span>{state.translationMode === "agent" ? (canEstimateVolume ? "예상 번역량 "+cost.tokens.toLocaleString("ko-KR")+" 토큰" : "번역량 확인 전") : isGemini ? selectedModel?.name ?? "Gemini 설정 확인 중" : "번역 설정 확인 필요"}</span>
        {isGemini ? <div className="setup-api-actions">
          <button type="button" className="secondary-button api-key-indicator" onClick={onOpenSettings}
            aria-label={engineSettings?.has_api_key ? "API 키 저장됨 · 설정 확인" : settingsError ? "API 설정 확인 실패 · 설정 열기" : engineSettings ? "API 키 필요 · 설정 열기" : "API 키 확인 중 · 설정 열기"}
            title={engineSettings?.has_api_key ? "API 키 저장됨 · 연결 확인은 설정에서 실행" : "API 키 상태를 설정에서 확인하세요"}>
            <Icon name="key" /><Icon name={engineSettings?.has_api_key ? "success" : "alert"} className="api-key-badge" />
          </button>
          <button type="button" className="secondary-button" onClick={onOpenSettings}>API 설정 열기</button>
        </div> : null}
      </div>

      {state.files.length > 0 ? <div className="source-queue" aria-label="선택된 번역 대상 목록">
        {state.files.map((file) => (
          <div key={file.id}>
            <span>{file.kind === "folder" ? "폴더" : "파일"}</span>
            <strong>{file.name}</strong>
            <small>{formatBytes(file.sizeBytes)} / {file.sizeBytes ? "분량 추정 " + file.pages + "쪽" : "페이지 수 확인 전"}</small>
            <button type="button" className="secondary-button" aria-label={file.name + " 목록에서 제외"} onClick={() => dispatch({type:"removeSourceItem",id:file.id})}>제외</button>
          </div>
        ))}
      </div> : null}

      {isGemini ? <p className="mode-subtext" role="status">{settingsError || (engineSettings?.has_api_key ? "선택한 모델로 문서 텍스트를 Google에 전송합니다. 실제 과금은 Google 프로젝트에 따릅니다." : "번역 전에 설정에서 Gemini API 키를 저장하세요.")}</p> : null}
      <p className="mode-subtext">{isGemini ? "API PDF 번역은 그림 속 영어도 OCR로 번역합니다." : "선택한 에이전트와 번역 기준으로 문서를 처리합니다."} {state.reviewMode === "on" ? "번역 후 확인 후보를 검수합니다." : "검수 OFF에서는 결과 PDF를 직접 확인하세요."} 수식·숫자·인용은 보존합니다.</p>
      <p className="mode-subtext">저장 위치: 첫 번째 입력 파일 폴더의 QDT_Output 폴더</p>

      <div className="setup-start-row">
      <p id="start-disabled-reason" className="mode-subtext">{state.files.length === 0 ? "번역할 파일 또는 폴더를 먼저 선택하세요." : isGemini && !engineSettings?.has_api_key ? "API 설정을 확인하고 키를 저장하면 시작할 수 있습니다." : ""}</p>
      <button type="button" className="primary-button" aria-describedby="start-disabled-reason" onClick={() => void handleStartTranslation()} disabled={state.files.length === 0 || (isGemini && !engineSettings?.has_api_key)}>
        번역 시작
      </button>
      </div>
    </section>
  );
}

function filesToInputItems(files: FileList | null, inputMode: InputMode): SourceInputItem[] {
  return Array.from(files ?? []).map((file) => {
    const sourceFile = file as SelectableFile;
    return {
      name: sourceFile.name,
      relativePath: sourceFile.webkitRelativePath || sourceFile.path,
      sizeBytes: sourceFile.size,
      kind: inputMode
    };
  });
}

function basename(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

function formatBytes(sizeBytes?: number) {
  if (!sizeBytes) {
    return "사이즈 미확인";
  }

  if (sizeBytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(sizeBytes / 1024)).toLocaleString("ko-KR")} KB`;
  }

  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`;
}
