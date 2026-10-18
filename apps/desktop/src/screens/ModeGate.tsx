import { useEffect, useRef, type Dispatch, type KeyboardEvent } from "react";
import { Icon } from "../components/Icon";
import appIcon from "../assets/app-icon.png";
import { type ProjectAction, type ProjectState, type TranslationMode } from "../state/projectState";

interface ModeGateProps {
  dispatch: Dispatch<ProjectAction>;
  state: ProjectState;
  onClose: () => void;
  onComplete: () => void;
  onOpenSettings: () => void;
}

export function ModeGate({ state, dispatch, onComplete, onOpenSettings, onClose }: ModeGateProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const backgrounds = Array.from(document.querySelectorAll<HTMLElement>(".sidebar,.workspace"));
    backgrounds.forEach(element => { element.inert = true; });
    panelRef.current?.querySelector<HTMLElement>("h2")?.focus();
    return () => {
      backgrounds.forEach(element => { element.inert = false; });
      const target = previous && previous !== document.body && previous.isConnected ? previous : document.querySelector<HTMLElement>(".workspace h2");
      if (target && target !== previous) target.setAttribute("tabindex", "-1");
      target?.focus();
    };
  }, []);

  function handleKeys(event: KeyboardEvent) {
    if (event.key === "Escape") { event.preventDefault(); onClose(); return; }
    if (event.key !== "Tab") return;
    const controls = Array.from(panelRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
    const index = controls.indexOf(document.activeElement as HTMLButtonElement);
    if (event.shiftKey && index <= 0) { event.preventDefault(); controls[controls.length - 1]?.focus(); }
    else if (!event.shiftKey && (index < 0 || index === controls.length - 1)) { event.preventDefault(); controls[0]?.focus(); }
  }

  function chooseMode(value: TranslationMode) {
    if (state.jobRunning) return;
    dispatch({ type: "setTranslationMode", value });
    onComplete();
  }

  return (
    <div className="mode-gate" ref={panelRef} onKeyDown={handleKeys} role="dialog" aria-modal="true" aria-labelledby="mode-gate-title">
      <div className="mode-gate-panel">
        <div className="entry-chrome">
          <span className="entry-wordmark"><img src={appIcon} alt="" draggable={false} />PST <span>학술 문서 번역기</span></span>
          <button type="button" className="secondary-button" onClick={onClose}><Icon name="close" />닫기</button>
        </div>
        <div className="entry-main">
          <div className="entry-heading">
            <h2 id="mode-gate-title" tabIndex={-1}>어떻게 번역할까요?</h2>
            <button type="button" className="secondary-button" onClick={onOpenSettings}><Icon name="key" />API 설정</button>
          </div>
          <div className="entry-choices">
            <div className="entry-column">
              <button type="button" className="entry-choice entry-gemini" onClick={() => chooseMode("machine")} disabled={state.jobRunning} aria-label="Gemini 번역으로 시작" aria-describedby="entry-gemini-caption">
                <span className="entry-provider">GEMINI API</span>
                <strong className="entry-title">바로 번역</strong>
                <span className="entry-description">파일을 넣고 한국어 PDF로</span>
                <span className="entry-document-art" aria-hidden="true">
                  <span className="entry-paper entry-original"><b>English</b><span className="entry-lines" /><span className="entry-lines short" /><span className="entry-lines" /></span>
                  <Icon name="arrowRight" />
                  <span className="entry-paper entry-translated"><b>한국어</b><span className="entry-lines" /><span className="entry-lines short" /><span className="entry-lines" /></span>
                </span>
                <span className="entry-go">이 방식으로 시작<Icon name="arrowRight" /></span>
              </button>
              <p className="entry-caption" id="entry-gemini-caption">설정에 등록한 API 키와 모델을 사용합니다.</p>
            </div>
            <div className="entry-column">
              <button type="button" className="entry-choice entry-agent" onClick={() => chooseMode("agent")} disabled={state.jobRunning} aria-label="에이전트 번역으로 시작" aria-describedby="entry-agent-caption">
                <span className="entry-provider">CODEX · CLAUDE CODE</span>
                <strong className="entry-title">에이전트 번역</strong>
                <span className="entry-description">연결한 에이전트로 문서 번역</span>
                <span className="entry-agent-art" aria-hidden="true">
                  <span className="entry-agent-window">
                    <span className="entry-window-top"><Icon name="terminal" />AI AGENT</span>
                    <span className="entry-agent-row"><Icon name="fileText" />원문 읽기</span>
                    <span className="entry-agent-row"><Icon name="languages" />문서 번역</span>
                    <span className="entry-agent-row"><Icon name="success" />PDF 만들기</span>
                  </span>
                </span>
                <span className="entry-go">이 방식으로 시작<Icon name="arrowRight" /></span>
              </button>
              <p className="entry-caption" id="entry-agent-caption">내 PC의 에이전트 연결과 계정을 사용합니다.</p>
            </div>
          </div>
          <p className="entry-footer">파일·출력·검수는 다음 화면에서 설정합니다.</p>
        </div>
      </div>
    </div>
  );
}
