import { Select } from "./Select";
import { Icon } from "./Icon";
import { invoke } from "@tauri-apps/api/core";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { failureActions, geminiRateLimitUrl, type ApiSettingsRequest, type ApiSettingsTarget } from "../translation/failureActions";
import {
  clearEngineApiKey, geminiModels, getEngineSettings, saveEngineSettings,
  testEngineConnection, type EngineSettings
} from "../translation/engineSettingsBridge";

export function ApiSettings({ jobRunning, navigation }: { jobRunning: boolean; navigation?: ApiSettingsRequest | null }) {
  const [expanded, setExpanded] = useState(!!navigation);
  const [focusRequest, setFocusRequest] = useState<ApiSettingsRequest | null>(navigation ?? null);
  const keyRef = useRef<HTMLInputElement>(null);
  const modelRef = useRef<HTMLButtonElement>(null);
  const connectionRef = useRef<HTMLButtonElement>(null);
  const usageRef = useRef<HTMLButtonElement>(null);
  const [saved, setSaved] = useState<EngineSettings | null>(null);
  const [model, setModel] = useState<string>(geminiModels[0].id);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("API 설정을 읽는 중입니다.");
  const [error, setError] = useState("");
  const chosen = geminiModels.find((item) => item.id === model) ?? geminiModels[0];
  const disabled = busy || jobRunning;
  useEffect(() => {
    let active = true;
    getEngineSettings().then((value) => {
      if (!active) return;
      setSaved(value); setModel(value.model); setMessage("");
    }).catch((reason: unknown) => {
      if (active) { setError(String(reason)); setMessage(""); }
    }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (navigation) { setExpanded(true); setFocusRequest(navigation); }
  }, [navigation]);
  useEffect(() => {
    if (!expanded || !focusRequest || disabled) return;
    const target = { key: keyRef, model: modelRef, connection: connectionRef, usage: usageRef }[focusRequest.target].current;
    target?.focus();
    target?.scrollIntoView({block:"center"});
    setFocusRequest(null);
  }, [expanded, focusRequest, disabled]);
  function goTo(target: ApiSettingsTarget) {
    setExpanded(true); setFocusRequest({target,id:Date.now()});
  }
  async function save(check: boolean) {
    if (disabled) return;
    setBusy(true); setError(""); setMessage(check ? "저장 후 연결을 확인합니다. 최대 45초 걸릴 수 있습니다." : "설정을 저장하는 중입니다.");
    try {
      const value = await saveEngineSettings(model, apiKey.trim() || undefined);
      setSaved(value); setApiKey("");
      if (check) {
        const result = await testEngineConnection();
        if (result.ok) setMessage(result.message);
        else { setError(result.message); setMessage("설정은 저장됐지만 연결을 확인하지 못했습니다."); }
      } else {
        setMessage(value.has_api_key ? "API 설정을 저장했습니다. 연결 확인은 아직 하지 않았습니다." : "모델을 저장했습니다. 번역하려면 API 키를 입력하세요.");
      }
    } catch (reason) { setError(String(reason)); setMessage(""); }
    finally { setBusy(false); }
  }
  async function clear() {
    if (disabled) return;
    setBusy(true); setError("");
    try {
      const value = await clearEngineApiKey();
      setSaved(value); setModel(value.model); setApiKey("");
      setMessage(value.key_source === "environment" ? "저장된 키를 삭제했습니다. 실행 환경에서 전달된 키는 계속 사용할 수 있습니다." : "저장된 API 키를 삭제했습니다.");
    } catch (reason) { setError(String(reason)); setMessage(""); }
    finally { setBusy(false); }
  }
  async function openKeyPage() {
    try { await invoke("plugin:opener|open_url", { url: "https://aistudio.google.com/api-keys", with: null }); }
    catch { setError("브라우저를 열지 못했습니다. Google AI Studio의 API 키 페이지를 열어 주세요."); }
  }
  async function openUsagePage() {
    try { await invoke("plugin:opener|open_url", { url: geminiRateLimitUrl, with: null }); }
    catch { setError("브라우저를 열지 못했습니다. Google AI Studio에서 사용량 한도를 확인해 주세요."); }
  }
  return (
    <section className="api-settings" aria-labelledby="api-settings-title">
      <h3 id="api-settings-title" className="api-disclosure-heading">
        <button type="button" className="api-disclosure" aria-expanded={expanded} aria-controls="api-settings-content" onClick={() => setExpanded(!expanded)}>
          <span><strong>API 및 모델</strong><small>{saved ? `${geminiModels.find(item=>item.id===saved.model)?.name ?? saved.model} · ${saved.has_api_key ? "키 등록됨" : "키 등록 필요"}` : error ? "설정 읽기 실패 · 펼쳐서 확인" : "설정 확인 중"}</small></span>
          <span className="api-disclosure-state">{expanded ? "접기" : "펼치기"}<Icon name="chevron" className="disclosure-icon" /></span>
        </button>
      </h3>
      <div id="api-settings-content" hidden={!expanded}>
      <p className="api-intro">Gemini Developer API · 번역할 문서의 텍스트를 Google로 전송합니다.</p>
      <form onSubmit={(event: FormEvent) => { event.preventDefault(); void save(false); }} aria-busy={busy}>
        <fieldset disabled={disabled} aria-describedby="api-disabled-reason">
          <legend className="api-visually-hidden">Gemini 연결 설정</legend>
          <div className="api-field">
            <label htmlFor="gemini-api-key">Gemini API 키</label>
            <input id="gemini-api-key" ref={keyRef} type="password" value={apiKey} onChange={(event) => setApiKey(event.currentTarget.value)}
              autoComplete="off" spellCheck={false} autoCapitalize="none" maxLength={8192}
              aria-describedby="api-key-help api-key-state" placeholder={saved?.has_api_key ? "변경할 때만 새 키 입력" : "발급한 API 키 붙여넣기"} />
            <small id="api-key-help">이 Windows 계정으로 암호화해 저장합니다. 입력란을 비워 두면 기존 키를 유지합니다.</small>
            <button className="api-key-link" type="button" onClick={() => void openKeyPage()}>Google AI Studio에서 API 키 발급</button>
            <p id="api-key-state">{saved ? saved.key_source === "saved" ? "키 상태: 이 앱에 저장됨" : saved.key_source === "environment" ? "키 상태: 실행 환경에서 전달됨" : "키 상태: 등록되지 않음" : busy ? "키 상태: 확인 중" : "키 상태: 확인 실패 · 새 키를 저장해 복구할 수 있습니다."}</p>
          </div>
          <div className="api-field">
            <label htmlFor="gemini-model">번역 모델</label>
            <Select id="gemini-model" label="번역 모델" ref={modelRef} value={model} disabled={disabled} onChange={setModel} describedBy="api-model-help api-model-price" options={geminiModels.map(item=>({value:item.id,label:item.name}))} />
            <small id="api-model-help">{chosen.note}</small>
            <p id="api-model-price">표준 텍스트 요금 · 100만 토큰당 입력 US&#36;{chosen.input} / 출력 US&#36;{chosen.output}</p>
          </div>
          <div className="api-field api-usage">
            <h4>사용량 및 요청 한도</h4>
            <p>요청 제한 오류가 나면 AI Studio에서 API 키에 연결된 프로젝트와 선택 모델의 한도를 확인하세요.</p>
            <button ref={usageRef} type="button" className="secondary-button" onClick={() => void openUsagePage()}>AI Studio 사용량 한도 열기</button>
          </div>
          <p className="api-notice">실제 무료 할당량·결제 여부는 Google 프로젝트 설정에 따릅니다. 무료 등급은 입력·출력이 제품 개선에 사용될 수 있습니다. 연결 확인은 문서 대신 “Hello” 한 문장을 보내며 할당량을 사용합니다.</p>
          <div className="api-actions">
            <button className="primary-button" type="submit">설정 저장</button>
            <button ref={connectionRef} className="secondary-button" type="button" onClick={() => void save(true)}>저장 후 연결 확인</button>
            <button className="secondary-button danger-button" type="button" onClick={() => void clear()} disabled={!saved?.has_saved_key}>저장된 키 삭제</button>
          </div>
        </fieldset>
        <p id="api-disabled-reason">{jobRunning ? "번역 중에는 API 설정을 변경할 수 없습니다." : busy ? "처리 중에는 설정을 변경할 수 없습니다." : ""}</p>
        <p className="api-status" role="status" aria-live="polite">{message}</p>
        {error ? <div><p className="api-error" role="alert">{error}</p><div className="failure-actions">{failureActions(error).map(action => <button key={action.target} type="button" className="secondary-button" onClick={() => goTo(action.target)}>{action.label}</button>)}</div></div> : null}
      </form>
      </div>
    </section>
  );
}
