import { ApiSettings } from "../components/ApiSettings";
import type { ApiSettingsRequest } from "../translation/failureActions";
import { useEffect, useState, type Dispatch } from "react";
import {
  getThemeTokens,
  type ThemePreset,
  type ThemeTokens
} from "../theme/themeOptions";
import type { ProjectAction, ProjectState } from "../state/projectState";
import { fetchOfficialSharedPacks } from "../translation/sharedKnowledge";
import { listSharedPacks, type SharedPackInfo } from "../translation/wikiBridge";

const presetLabels: Record<ThemePreset, { title: string; description: string }> = {
  "soft-pink": {
    title: "Soft Pink",
    description: "부드러운 분홍 계열 테마입니다."
  },
  "rosy-purple": {
    title: "Rosy Purple",
    description: "분홍과 보라 계열 테마입니다."
  },
  lavender: {
    title: "Lavender",
    description: "보라와 분홍을 낮은 채도로 섞은 작업용 테마입니다."
  },
  custom: {
    title: "Custom",
    description: "선택한 색을 적용하고 글자 대비를 보정합니다."
  }
};

const editableTokens: Array<{ key: keyof ThemeTokens; label: string }> = [
  { key: "primary", label: "주 강조색" },
  { key: "accent", label: "보조 강조색" },
  { key: "background", label: "배경" },
  { key: "surface", label: "패널" },
  { key: "text", label: "본문" },
  { key: "gradientStart", label: "그라데이션 시작" },
  { key: "gradientEnd", label: "그라데이션 끝" },
  { key: "sideStart", label: "메뉴 배경 시작" },
  { key: "sideEnd", label: "메뉴 배경 끝" }
];

export function SettingsWorkspace({ state, dispatch, apiNavigation, onReturn }: { state: ProjectState; dispatch: Dispatch<ProjectAction>; apiNavigation?: ApiSettingsRequest | null; onReturn?: () => void }) {
  const activePreset = state.darkMode ? state.darkPreset : state.themePreset;
  const activeTokens = getThemeTokens(activePreset, state.customTheme, state.darkMode);
  const [officialSharedKnowledgeStatus, setOfficialSharedKnowledgeStatus] = useState<string | null>(null);
  const [sharedKnowledgeBusy, setSharedKnowledgeBusy] = useState(false);
  const [sharedPacks, setSharedPacks] = useState<SharedPackInfo[]>([]);

  useEffect(() => {
    let cancelled = false;

    const refreshSharedPacks = async () => {
      try {
        const packs = await listSharedPacks();
        if (!cancelled) {
          setSharedPacks(packs);
        }
      } catch (error) {
        if (!cancelled) {
          setOfficialSharedKnowledgeStatus(error instanceof Error ? error.message : String(error));
        }
      }
    };

    void refreshSharedPacks();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleFetchOfficialSharedPacks = async () => {
    if (!state.sharedKnowledgeEnabled) {
      return;
    }

    setSharedKnowledgeBusy(true);
    setOfficialSharedKnowledgeStatus(null);
    try {
      const installed = await fetchOfficialSharedPacks();
      const packs = await listSharedPacks();
      setSharedPacks(packs);
      setOfficialSharedKnowledgeStatus(`공식 공유팩 ${installed.length}개를 설치했습니다.`);
    } catch (error) {
      setOfficialSharedKnowledgeStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setSharedKnowledgeBusy(false);
    }
  };

  return (
    <section className="setup-panel workbench-only settings-workspace" aria-label="설정">
      <div className="section-heading">
        <h2>설정</h2>
        {apiNavigation ? <button type="button" className="secondary-button" onClick={onReturn}>작업으로 돌아가기</button> : null}
      </div>

      <ApiSettings jobRunning={state.jobRunning} navigation={apiNavigation} />

      <div className="setup-step">
        <div className="step-copy">
          <span>화면</span>
          <h3>화면 모드</h3>
          <p>다크 모드를 켜면 분홍·커스텀 팔레트가 어두운 화면에 어울리는 색으로 함께 전환됩니다.</p>
        </div>

        <div className="mode-toggle-row" role="group" aria-label="화면 모드">
          <button
            type="button"
            className={state.darkMode ? "mode-toggle" : "mode-toggle is-active"}
            aria-pressed={!state.darkMode}
            onClick={() => dispatch({ type: "setDarkMode", value: false })}
          >
            <span aria-hidden="true">☀</span> 라이트
          </button>
          <button
            type="button"
            className={state.darkMode ? "mode-toggle is-active" : "mode-toggle"}
            aria-pressed={state.darkMode}
            onClick={() => dispatch({ type: "setDarkMode", value: true })}
          >
            <span aria-hidden="true">☾</span> 다크
          </button>
        </div>
      </div>

      <div className="setup-step">
        <div className="step-copy">
          <span>테마</span>
          <h3>{state.darkMode ? "다크 모드 테마" : "라이트 모드 테마"}</h3>
          <p>라이트와 다크는 각각 별도의 테마를 기억합니다. 지금 선택은 {state.darkMode ? "다크" : "라이트"} 모드에만 적용됩니다.</p>
        </div>

        <div className="choice-card-grid theme-choice-grid">
          {(Object.keys(presetLabels) as ThemePreset[]).map((preset) => {
            const tokens = getThemeTokens(preset, state.customTheme, state.darkMode);
            return (
              <button
                key={preset}
                type="button"
                className={activePreset === preset ? "choice-card theme-preset-card is-active" : "choice-card theme-preset-card"}
                onClick={() => dispatch({ type: "setThemePreset", value: preset })}
              >
                <span className="theme-swatch" style={{ background: `linear-gradient(135deg, ${tokens.gradientStart}, ${tokens.gradientEnd})` }} />
                <strong>{presetLabels[preset].title}</strong>
                <small>{presetLabels[preset].description}</small>
              </button>
            );
          })}
        </div>
      </div>

      <div className="setup-step shared-knowledge-panel">
        <div className="step-copy">
          <span>공유 용어팩</span>
          <h3>공식 공유 지식</h3>
          <p>동의하면 QDT가 관리하는 검수된 용어팩을 내려받아 번역에 참고합니다. 내 문서나 검수 내용은 업로드하지 않습니다.</p>
        </div>

        <div className="mode-toggle-row" role="group" aria-label="공식 공유 지식 사용">
          <button
            type="button"
            className={state.sharedKnowledgeEnabled ? "mode-toggle is-active" : "mode-toggle"}
            aria-pressed={state.sharedKnowledgeEnabled}
            onClick={() => dispatch({ type: "setSharedKnowledgeEnabled", value: true })}
          >
            사용
          </button>
          <button
            type="button"
            className={state.sharedKnowledgeEnabled ? "mode-toggle" : "mode-toggle is-active"}
            aria-pressed={!state.sharedKnowledgeEnabled}
            onClick={() => dispatch({ type: "setSharedKnowledgeEnabled", value: false })}
          >
            끔
          </button>
        </div>

        <div className="shared-knowledge-status">
          <div>
            <span>상태</span>
            <strong>{state.sharedKnowledgeEnabled ? "공식 공유팩 사용" : "사용 안 함"}</strong>
            <small>
              {officialSharedKnowledgeStatus ??
                (sharedPacks.length > 0 ? `설치된 공유팩 ${sharedPacks.length}개` : "설치된 공유팩 없음")}
            </small>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleFetchOfficialSharedPacks()}
            disabled={!state.sharedKnowledgeEnabled || sharedKnowledgeBusy}
          >
            {sharedKnowledgeBusy ? "확인 중" : "공식 공유팩 받기"}
          </button>
        </div>

        <div className="installed-shared-pack-list" aria-label="설치된 공유팩">
          <span>설치된 공유팩</span>
          {sharedPacks.length === 0 ? (
            <p>아직 설치된 공식 공유팩이 없습니다.</p>
          ) : (
            <ul>
              {sharedPacks.map((pack) => (
                <li key={pack.id}>
                  <strong>{pack.displayName}</strong>
                  <small>
                    {pack.domain} · v{pack.version} · {pack.terms.toLocaleString("ko-KR")}개
                  </small>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="setup-step">
        <div className="step-copy">
          <span>색상 설정</span>
          <h3>커스텀 팔레트</h3>
          <p>색을 수정하면 자동으로 Custom 테마가 선택됩니다. 글자와 표면의 대비가 부족하면 읽을 수 있는 색으로 보정합니다.</p>
        </div>

        <div className="custom-theme-grid">
          {editableTokens.map((token) => (
            <label key={token.key} className="color-field">
              <span>{token.label}</span>
              <input
                type="color"
                value={toColorInputValue(activeTokens[token.key])}
                onChange={(event) => dispatch({ type: "setCustomThemeToken", key: token.key, value: event.currentTarget.value })}
              />
              <code>{activeTokens[token.key]}</code>
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}

function toColorInputValue(value: string) {
  return /^#[0-9a-f]{6}$/i.test(value) ? value : "#ff8acb";
}
