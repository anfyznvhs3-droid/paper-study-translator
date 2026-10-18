import { Select } from "../components/Select";
import { Icon } from "../components/Icon";
import { useCallback, useEffect, useId, useRef, useState, type Dispatch, type ReactNode } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { ProjectAction, ProjectState } from "../state/projectState";
import { domainLabel } from "../state/domains";
import { sessionErrorMessage } from "../translation/reviewSession";
import {
  listGlossary, addTerm, deleteTerm, listDomains, createDomain, deleteDomain,
  exportGlossary, importGlossary, type GlossaryEntry, type DomainInfo,
  type CatGlossaryFormat, type CatImportMode
} from "../translation/wikiBridge";

interface GlossaryWorkspaceProps { state: ProjectState; dispatch: Dispatch<ProjectAction> }

function GlossaryDialog({ title, busy, onClose, children }: {title: string; busy: boolean; onClose: () => void; children: ReactNode}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = ref.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLInputElement>("input:not(:disabled)")?.focus();
    return () => { dialog?.close(); if (trigger?.isConnected) trigger.focus(); };
  }, []);
  return <dialog ref={ref} className="glossary-dialog" aria-labelledby={titleId}
    onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')).filter(element => element.getClientRects().length);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {event.preventDefault();last?.focus();}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault();first?.focus();}
    }}
    onCancel={event => {event.preventDefault(); if (!busy) onClose();}}>
    <div className="glossary-dialog-heading"><h3 id={titleId}>{title}</h3><button type="button" className="secondary-button" onClick={onClose} disabled={busy}>닫기</button></div>
    {children}
  </dialog>;
}

export function GlossaryWorkspace({ state, dispatch }: GlossaryWorkspaceProps) {
  const domain = state.domain;
  const domainRef = useRef(domain);
  domainRef.current = domain;
  const listRequest = useRef(0);
  const domainsRequest = useRef(0);
  const [loaded, setLoaded] = useState<{domain: string; entries: GlossaryEntry[]}>({domain:"",entries:[]});
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [domainError, setDomainError] = useState("");
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [notes, setNotes] = useState("");
  const [termAddOpen, setTermAddOpen] = useState(false);
  const [domainManagerOpen, setDomainManagerOpen] = useState(false);
  const [newDomainName, setNewDomainName] = useState("");
  const [saving, setSaving] = useState(false);
  const [catExportFormat, setCatExportFormat] = useState<CatGlossaryFormat>("omegat");
  const [catImportFormat, setCatImportFormat] = useState<CatGlossaryFormat>("omegat");
  const [catImportMode, setCatImportMode] = useState<CatImportMode>("candidates");
  const [catMessage, setCatMessage] = useState("");
  const [catError, setCatError] = useState("");
  const [catBusy, setCatBusy] = useState(false);
  const busy = saving || catBusy || state.jobRunning;
  const entries = loaded.domain === domain ? loaded.entries : [];
  const visible = entries.filter(entry => `${entry.source} ${entry.target} ${entry.notes}`.toLowerCase().includes(query.trim().toLowerCase()));

  const refresh = useCallback(async () => {
    const request = ++listRequest.current;
    setListLoading(true); setListError("");
    try {
      const data = await listGlossary(domain);
      if (request === listRequest.current) setLoaded({domain, entries:data});
    } catch (error) {
      if (request === listRequest.current) setListError(sessionErrorMessage(error));
    } finally { if (request === listRequest.current) setListLoading(false); }
  }, [domain]);
  const refreshDomains = useCallback(async () => {
    const request = ++domainsRequest.current;
    setDomainError("");
    try {
      const data = await listDomains();
      if (request !== domainsRequest.current) return;
      setDomains(data);
      if (data.length && !data.some(item => item.slug === domainRef.current)) dispatch({type:"setDomain",value:data[0].slug});
    } catch (error) { if (request === domainsRequest.current) setDomainError(sessionErrorMessage(error)); }
  }, [dispatch]);
  useEffect(() => { setQuery(""); void refresh(); return () => {listRequest.current++;}; }, [refresh]);
  useEffect(() => { void refreshDomains(); return () => {domainsRequest.current++;}; }, [refreshDomains]);

  async function handleAdd() {
    if (busy || !source.trim() || !target.trim()) return;
    setSaving(true); setActionError("");
    try {
      await addTerm(domain, source.trim(), target.trim(), notes.trim());
      setSource(""); setTarget(""); setNotes(""); setQuery("");
      setMessage("용어를 저장했습니다.");
      await Promise.all([refresh(), refreshDomains()]);
      setSaving(false); setTermAddOpen(false);
    } catch (error) { setActionError(sessionErrorMessage(error)); }
    finally { setSaving(false); }
  }
  async function handleDelete(value: string) {
    if (busy) return;
    setSaving(true); setActionError("");
    try {
      await deleteTerm(domain, value);
      setMessage(`“${value}” 용어를 삭제했습니다.`);
      await Promise.all([refresh(), refreshDomains()]);
    } catch (error) { setActionError(sessionErrorMessage(error)); }
    finally { setSaving(false); }
  }
  async function handleCreateDomain() {
    if (busy || !newDomainName.trim()) return;
    setSaving(true); setActionError(""); ++domainsRequest.current;
    try {
      const previous = new Set(domains.map(item => item.slug));
      const updated = await createDomain(newDomainName.trim());
      setDomains(updated);
      const added = updated.find(item => !previous.has(item.slug));
      if (added) {
        dispatch({type:"setDomain",value:added.slug}); setDomainManagerOpen(false); setNewDomainName("");
        setMessage(`“${domainLabel(added.slug)}” 분류를 추가했습니다.`);
      } else setActionError("이미 존재하는 분류입니다.");
    } catch (error) { setActionError(sessionErrorMessage(error)); }
    finally { setSaving(false); }
  }
  async function handleRemoveDomain() {
    if (busy || domains.length <= 1) return;
    setSaving(true); setActionError(""); ++domainsRequest.current;
    try {
      const result = await deleteDomain(domain);
      setDomains(result.domains);
      if (result.domains[0]) dispatch({type:"setDomain",value:result.domains[0].slug});
      setDomainManagerOpen(false);
      setMessage(`“${domainLabel(domain)}” 분류를 제거했습니다. 백업 위치: ${result.backupPath}`);
    } catch (error) { setActionError(sessionErrorMessage(error)); }
    finally { setSaving(false); }
  }
  async function handleExportGlossary() {
    if (busy) return;
    setCatBusy(true); setCatMessage(""); setCatError("");
    try {
      const result = await exportGlossary(domain, catExportFormat);
      setCatMessage(`내보내기 완료 · ${result.exported}개 · ${result.path}`);
    } catch (error) { setCatError(sessionErrorMessage(error)); }
    finally { setCatBusy(false); }
  }
  async function handleImportGlossary() {
    if (busy) return;
    setCatBusy(true); setCatMessage(""); setCatError("");
    try {
      const selected = await open({multiple:false, filters:[{name:catImportFormat === "tbx" ? "TBX" : "OmegaT glossary",extensions:catImportFormat === "tbx" ? ["tbx","xml"] : ["txt","tab","utf8"]}]});
      if (!selected || Array.isArray(selected)) return;
      const result = await importGlossary(domain, catImportFormat, selected, catImportMode);
      setCatMessage(`가져오기 완료 · ${result.imported}개 · ${result.mode === "confirmed" ? "표준 용어로 등록됨" : "검토 후보로 등록됨"}`);
      await Promise.all([refresh(), refreshDomains()]);
    } catch (error) { setCatError(sessionErrorMessage(error)); }
    finally { setCatBusy(false); }
  }

  return <section className="setup-panel workbench-only glossary-workspace" aria-label="용어집">
    <div className="glossary-heading"><h2>표준 용어집</h2></div>
    <div className="glossary-toolbar">
      <label className="glossary-field glossary-domain-select"><span>분류</span>
        <Select label="분류" value={domain} disabled={busy} onChange={value => {setMessage("");setActionError("");setCatMessage("");setCatError("");dispatch({type:"setDomain",value});}}
          options={domains.length ? domains.map(item=>({value:item.slug,label:`${domainLabel(item.slug)} · ${item.terms}개`})) : [{value:domain,label:domainLabel(domain)}]} />
      </label>
      <button type="button" className="secondary-button" disabled={busy} onClick={() => {setActionError("");setDomainManagerOpen(true);}}>분류 관리</button>
      <p>선택한 분류의 용어를 번역에 적용합니다.</p>
    </div>
    {state.jobRunning ? <p className="glossary-notice">번역 중에는 용어집을 변경할 수 없습니다.</p> : null}
    {message ? <p className="glossary-notice" role="status">{message}</p> : null}
    {actionError && !termAddOpen && !domainManagerOpen ? <p className="glossary-notice" role="alert">{actionError}</p> : null}
    <section className="glossary-list" aria-label="등록된 용어">
      <div className="glossary-list-heading">
        <h3>용어 목록 <span>{listLoading || listError ? "" : `${visible.length}${query ? ` / ${entries.length}` : ""}개`}</span></h3>
        <div className="glossary-list-actions">
          <input type="search" aria-label="용어 검색" placeholder="원문·번역·메모 검색" value={query} onChange={event => setQuery(event.currentTarget.value)} />
          <button type="button" className="primary-button" disabled={busy || listLoading || !!listError || !!domainError} onClick={() => {setActionError("");setTermAddOpen(true);}}>용어 추가</button>
        </div>
      </div>
      {listError || domainError ? <div className="glossary-load-error"><p role="alert">{listError || domainError}</p><button type="button" className="secondary-button" onClick={() => {void refresh();void refreshDomains();}}>다시 불러오기</button></div>
        : listLoading ? <p className="glossary-empty" role="status">용어를 불러오는 중입니다.</p>
        : !visible.length ? <p className="glossary-empty">{query ? "검색 결과가 없습니다." : "등록된 용어가 없습니다."}</p>
        : <div className="glossary-terms" role="table" aria-label="용어 목록">
          <div className="glossary-term-heading" role="row"><span role="columnheader">원문</span><span role="columnheader">번역</span><span role="columnheader">메모</span><span role="columnheader">관리</span></div>
          {visible.map(entry => <div className="glossary-term" role="row" key={entry.source}>
            <span role="cell" data-label="원문">{entry.source}</span><span role="cell" data-label="번역">{entry.target}</span>
            <span role="cell" className="glossary-term-note" data-label="메모">{entry.notes || "—"}</span>
            <span role="cell" className="glossary-term-action"><button type="button" className="secondary-button" aria-label={`${entry.source} 삭제`} disabled={busy} onClick={() => void handleDelete(entry.source)}>삭제</button></span>
          </div>)}
        </div>}
    </section>
    <details className="glossary-exchange">
      <summary><span><strong>파일 가져오기·내보내기</strong><small>OmegaT · TBX 용어집</small></span><span className="glossary-disclosure-state"><span className="when-closed">펼치기</span><span className="when-open">접기</span><Icon name="chevron" className="disclosure-icon" /></span></summary>
      <div className="glossary-exchange-content">
        <p className="glossary-notice">OmegaT는 탭으로 구분한 용어집, TBX는 용어 교환용 XML 파일입니다.</p>
        <div className="glossary-exchange-grid">
          <section className="glossary-exchange-group" aria-label="용어집 내보내기">
            <h4>내보내기</h4>
            <label className="glossary-field"><span>내보낼 파일 형식</span><Select label="내보낼 파일 형식" value={catExportFormat} disabled={busy} onChange={value=>setCatExportFormat(value as CatGlossaryFormat)} options={[{value:"omegat",label:"OmegaT"},{value:"tbx",label:"TBX"}]} /></label>
            <p>현재 분류의 표준 용어를 파일로 저장합니다.</p>
            <button type="button" className="secondary-button" onClick={() => void handleExportGlossary()} disabled={busy || !!domainError}>용어집 파일로 내보내기</button>
          </section>
          <section className="glossary-exchange-group" aria-label="용어집 가져오기">
            <h4>가져오기</h4>
            <label className="glossary-field"><span>가져올 파일 형식</span><Select label="가져올 파일 형식" value={catImportFormat} disabled={busy} onChange={value=>setCatImportFormat(value as CatGlossaryFormat)} options={[{value:"omegat",label:"OmegaT"},{value:"tbx",label:"TBX"}]} /></label>
            <label className="glossary-field"><span>가져온 용어 처리</span><Select label="가져온 용어 처리" value={catImportMode} disabled={busy} onChange={value=>setCatImportMode(value as CatImportMode)} options={[{value:"candidates",label:"검토 후보로 넣기"},{value:"confirmed",label:"바로 표준 용어로 등록"}]} /></label>
            <button type="button" className="secondary-button" onClick={() => void handleImportGlossary()} disabled={busy || !!domainError}>용어집 파일 가져오기</button>
          </section>
        </div>
        {catBusy ? <p className="glossary-notice" role="status">파일을 처리하는 중입니다.</p> : null}
        {catMessage ? <p className="glossary-notice" role="status">{catMessage}</p> : null}
        {catError ? <p className="glossary-notice" role="alert">{catError}</p> : null}
      </div>
    </details>
    {termAddOpen ? <GlossaryDialog title="새 용어 추가" busy={busy} onClose={() => setTermAddOpen(false)}>
      <form onSubmit={event => {event.preventDefault();void handleAdd();}}>
        <p className="glossary-notice">{domainLabel(domain)}에 등록합니다.</p>
        <label className="glossary-field"><span>원문</span><input value={source} disabled={busy} onChange={event => setSource(event.currentTarget.value)} placeholder="FMEA" /></label>
        <label className="glossary-field"><span>번역</span><input value={target} disabled={busy} onChange={event => setTarget(event.currentTarget.value)} placeholder="고장형태 및 영향분석" /></label>
        <label className="glossary-field"><span>메모 (선택)</span><input value={notes} disabled={busy} onChange={event => setNotes(event.currentTarget.value)} /></label>
        {actionError ? <p className="glossary-notice" role="alert">{actionError}</p> : null}
        <div className="glossary-dialog-actions"><button type="submit" className="primary-button" disabled={busy || !source.trim() || !target.trim()}>용어 추가</button></div>
      </form>
    </GlossaryDialog> : null}
    {domainManagerOpen ? <GlossaryDialog title="분류 관리" busy={busy} onClose={() => setDomainManagerOpen(false)}>
      <form onSubmit={event => {event.preventDefault();void handleCreateDomain();}}>
        <div className="glossary-domain-create"><label className="glossary-field"><span>새 분류</span><input value={newDomainName} disabled={busy} onChange={event => setNewDomainName(event.currentTarget.value)} placeholder="medical-device" /></label><button type="submit" className="secondary-button" disabled={busy || !newDomainName.trim()}>추가</button></div>
      </form>
      <section className="glossary-domain-remove" aria-label="현재 분류 제거"><h4>{domainLabel(domain)} 제거</h4><p>현재 분류의 용어집을 백업한 뒤 제거합니다. 마지막 분류는 남겨 둡니다.</p><button type="button" className="secondary-button danger-button" onClick={() => void handleRemoveDomain()} disabled={busy || domains.length <= 1}>백업 후 제거</button></section>
      {actionError ? <p className="glossary-notice" role="alert">{actionError}</p> : null}
    </GlossaryDialog> : null}
  </section>;
}
