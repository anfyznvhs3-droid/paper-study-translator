import { loadReviewSession, persistReviewSession, sessionErrorMessage } from "../translation/reviewSession";
import { useReducer, useState, useEffect, type CSSProperties } from "react";
import appIcon from "../assets/app-icon.png";
import sidebarBunny from "../assets/sidebar-bunny.png";
import { CompleteWorkspace } from "../screens/CompleteWorkspace";
import { FeedbackWorkspace } from "../screens/FeedbackWorkspace";
import { GlossaryWorkspace } from "../screens/GlossaryWorkspace";
import { ModeGate } from "../screens/ModeGate";
import { PatchNotesWorkspace } from "../screens/PatchNotesWorkspace";
import { ProgressWorkspace } from "../screens/ProgressWorkspace";
import { ReviewWorkspace } from "../screens/ReviewWorkspace";
import { SetupFlow } from "../screens/SetupFlow";
import { SettingsWorkspace } from "../screens/SettingsWorkspace";
import type { ApiSettingsRequest, ApiSettingsTarget } from "../translation/failureActions";
import { defaultCustomTheme, getThemeTokens, themeCssVariables } from "../theme/themeOptions";
import { loadPersistedSettings, persistSettings } from "../state/persistedSettings";
import {
  initialProjectState,
  projectReducer,
  type ProjectState
} from "../state/projectState";

function createInitialState(): ProjectState {
  const saved = loadPersistedSettings();
  return {
    ...initialProjectState,
    customTheme: {...defaultCustomTheme,...saved.customTheme},
    ...(saved.translationMode && { translationMode: saved.translationMode as ProjectState["translationMode"] }),
    ...(saved.engine && { engine: saved.engine as ProjectState["engine"] }),
    ...(saved.outputMode && { outputMode: saved.outputMode as ProjectState["outputMode"] }),
    ...(saved.reviewMode && { reviewMode: saved.reviewMode as ProjectState["reviewMode"] }),
    ...(saved.quality && { quality: saved.quality as ProjectState["quality"] }),
    ...(saved.themePreset && { themePreset: saved.themePreset as ProjectState["themePreset"] }),
    ...(saved.darkPreset && { darkPreset: saved.darkPreset as ProjectState["darkPreset"] }),
    ...(typeof saved.darkMode === "boolean" && { darkMode: saved.darkMode }),
    ...(saved.domain && { domain: saved.domain }),
    ...(typeof saved.sharedKnowledgeEnabled === "boolean" && { sharedKnowledgeEnabled: saved.sharedKnowledgeEnabled }),
  };
}

export function App() {
  const [state, dispatch] = useReducer(projectReducer, null, createInitialState);
  const [modeSelected, setModeSelected] = useState(false);
  const [activePanel, setActivePanel] = useState<"workbench" | "patchNotes" | "settings" | "feedback" | "glossary">("workbench");
  const [sessionReady,setSessionReady] = useState(false);
  const [sessionNotice,setSessionNotice] = useState("");
  const [sessionError,setSessionError] = useState("");
  const [apiNavigation, setApiNavigation] = useState<ApiSettingsRequest | null>(null);
  function openApiSettings(target: ApiSettingsTarget = "key") {
    setApiNavigation(previous => ({target, id:(previous?.id ?? 0) + 1}));
    setActivePanel("settings");
  }
  useEffect(() => {
    let active=true;
    void loadReviewSession().then((session) => {
      if(!active)return;
      if(session) {
        dispatch({type:"restoreSession",session});
        setModeSelected(true);
        setSessionNotice("이 PC에 저장된 최근 작업과 검수 결정을 복원했습니다.");
      }
    }).catch((error:unknown)=>{if(active)setSessionError(sessionErrorMessage(error));})
      .finally(()=>{if(active)setSessionReady(true);});
    return ()=>{active=false;};
  },[]);
  useEffect(() => {
    if(!sessionReady || state.jobRunning || (!state.runId && !state.lastRunResult))return;
    let active=true;
    void persistReviewSession(state).then(()=>{if(active){setSessionError("");setSessionNotice(state.lastRunResult?"최근 결과와 검수 결정을 이 PC에 저장했습니다.":"");}})
      .catch((error:unknown)=>{if(active)setSessionError("작업 기록 저장 실패: "+sessionErrorMessage(error));});
    return ()=>{active=false;};
  },[sessionReady,state.runId,state.jobRunning,state.files,state.lastRunResult]);
  const workspaceStage = getWorkspaceStage(state);
  const activePreset = state.darkMode ? state.darkPreset : state.themePreset;
  const themeStyle = themeCssVariables(getThemeTokens(activePreset, state.customTheme, state.darkMode)) as CSSProperties;

  useEffect(() => {
    persistSettings({
      translationMode: state.translationMode,
      engine: state.engine,
      outputMode: state.outputMode,
      reviewMode: state.reviewMode,
      quality: state.quality,
      themePreset: state.themePreset,
      darkPreset: state.darkPreset,
      darkMode: state.darkMode,
      customTheme: state.customTheme,
      domain: state.domain,
      sharedKnowledgeEnabled: state.sharedKnowledgeEnabled,
    });
  }, [state.translationMode, state.engine, state.outputMode, state.reviewMode, state.quality, state.themePreset, state.darkPreset, state.darkMode, state.customTheme, state.domain, state.sharedKnowledgeEnabled]);

  if (!sessionReady) {
    return <main className="workspace" style={themeStyle} aria-busy="true"><h1>문서 번역기</h1><p role="status">이전 작업을 확인하고 있습니다.</p></main>;
  }
  return (
    <div className="app-shell" data-theme={state.darkMode ? "dark" : "light"} style={themeStyle}>
      {!modeSelected && activePanel === "workbench" ? <ModeGate state={state} onClose={() => setModeSelected(true)} dispatch={dispatch} onComplete={() => setModeSelected(true)} onOpenSettings={() => openApiSettings()} /> : null}

      <aside className="sidebar" aria-label="사이드 메뉴">
        <img className="sidebar-watermark" src={sidebarBunny} alt="" aria-hidden="true" />
        <div className="brand" aria-label="Paper Study Translator">
          <img src={appIcon} alt="" />
          <div>
            <strong>문서 번역기</strong>
            <span>PST</span>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="작업 메뉴">
          <button type="button" aria-current={activePanel === "workbench" ? "page" : undefined} className={activePanel === "workbench" ? "is-active" : ""} onClick={() => setActivePanel("workbench")}>
            <span>01</span>
            <strong>작업 현황</strong>
          </button>
          <button type="button" aria-current={activePanel === "patchNotes" ? "page" : undefined} className={activePanel === "patchNotes" ? "is-active" : ""} onClick={() => setActivePanel("patchNotes")}>
            <span>02</span>
            <strong>패치노트</strong>
          </button>
          <button type="button" aria-current={activePanel === "settings" ? "page" : undefined} className={activePanel === "settings" ? "is-active" : ""} onClick={() => {setApiNavigation(null);setActivePanel("settings");}}>
            <span>03</span>
            <strong>설정</strong>
          </button>
          <button type="button" aria-current={activePanel === "feedback" ? "page" : undefined} className={activePanel === "feedback" ? "is-active" : ""} onClick={() => setActivePanel("feedback")}>
            <span>04</span>
            <strong>피드백</strong>
          </button>
          <button type="button" aria-current={activePanel === "glossary" ? "page" : undefined} className={activePanel === "glossary" ? "is-active" : ""} onClick={() => setActivePanel("glossary")}>
            <span>05</span>
            <strong>용어집</strong>
          </button>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>문서 번역기</h1>
          </div>
          <div className="operator-badge" aria-label="현재 상태">
            <span />
            {workspaceStage === "setup"
              ? "설정 중"
              : workspaceStage === "progress"
                ? "번역 진행 중"
                : workspaceStage === "review"
                  ? "검수 진행 중"
                  : state.lastRunResult?.status === "cancelled" ? "번역 중지"
                  : state.lastRunResult?.status === "paused" ? "번역 일시 중단"
                  : state.lastRunResult?.ok === false ? "번역 실패" : "결과 파일 생성 완료"}
          </div>
        </header>

        {sessionError ? <p className="session-notice" role="alert">{sessionError}</p> : sessionNotice ? <p className="session-notice" role="status">{sessionNotice}</p> : null}
        <div className="content-grid single">
          {activePanel === "patchNotes" ? <PatchNotesWorkspace state={state} /> : null}
          {activePanel === "settings" ? <SettingsWorkspace state={state} dispatch={dispatch} apiNavigation={apiNavigation} onReturn={() => setActivePanel("workbench")} /> : null}
          {activePanel === "feedback" ? <FeedbackWorkspace state={state} /> : null}
          {activePanel === "glossary" ? <GlossaryWorkspace state={state} dispatch={dispatch} /> : null}
          {activePanel === "workbench" && workspaceStage === "setup" ? (
            <SetupFlow state={state} dispatch={dispatch} onReconfigureMode={() => setModeSelected(false)} onOpenSettings={() => openApiSettings()} />
          ) : null}
          {activePanel === "workbench" && workspaceStage === "progress" ? <ProgressWorkspace state={state} dispatch={dispatch} /> : null}
          {activePanel === "workbench" && workspaceStage === "review" ? <ReviewWorkspace state={state} dispatch={dispatch} /> : null}
          {activePanel === "workbench" && workspaceStage === "complete" ? <CompleteWorkspace state={state} dispatch={dispatch} onOpenSettings={openApiSettings} /> : null}
        </div>
      </main>
    </div>
  );
}

function getWorkspaceStage(state: ProjectState) {
  if (state.jobRunning) return "progress";
  if (state.reviewOpen && (state.files.some((file)=>file.status==="review_wait") || state.lastRunResult?.reviewItems.length)) return "review";
  if (state.lastRunResult) return "complete";
  const activeFile = state.files.find((file) => file.id === state.activeJobId);
  if (!activeFile || activeFile.status === "pending") {
    return "setup";
  }

  if (activeFile.status === "review_wait") {
    return "review";
  }

  if (activeFile.status === "completed" || activeFile.status === "failed" || activeFile.status === "paused" || activeFile.status === "cancelled" || activeFile.status === "skipped") {
    return "complete";
  }

  return "progress";
}
