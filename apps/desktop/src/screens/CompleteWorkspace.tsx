import { Icon } from "../components/Icon";
import { useRef, useState } from "react";
import { failureActions, type ApiSettingsTarget } from "../translation/failureActions";
import { persistReviewSession, sessionErrorMessage } from "../translation/reviewSession";
import { fileLabel, pdfResults } from "../translation/pdfResults";
import { SummaryCards } from "../components/SummaryCards";
import { invoke } from "@tauri-apps/api/core";
import type { ProjectAction, ProjectState } from "../state/projectState";

interface CompleteWorkspaceProps {state: ProjectState; dispatch: React.Dispatch<ProjectAction>; onOpenSettings: (target: ApiSettingsTarget) => void}

export function CompleteWorkspace({ state, dispatch, onOpenSettings }: CompleteWorkspaceProps) {
  const detailsRef = useRef<HTMLDetailsElement>(null);
  function openDetails() {
    if (detailsRef.current) {
      detailsRef.current.open = true;
      detailsRef.current.querySelectorAll("details").forEach(detail => {detail.open = true;});
      detailsRef.current.querySelector("summary")?.focus();
      detailsRef.current.scrollIntoView({block:"start"});
    }
  }
  const [resetError,setResetError]=useState("");
  const [openError,setOpenError]=useState("");
  const [resetting,setResetting]=useState(false);
  async function openPath(path:string) {
    setOpenError("");
    try {await invoke("open_system_path",{request:{path}});}
    catch(error){setOpenError("파일 또는 폴더를 열지 못했습니다: "+sessionErrorMessage(error));}
  }
  async function startNew() {
    setResetting(true);
    try {await persistReviewSession({...state,runId:null,lastRunResult:null});dispatch({type:"resetToSetup"});}
    catch(error){setResetError("최근 작업 표시를 정리하지 못했습니다: "+sessionErrorMessage(error));setResetting(false);}
  }
  const result=state.lastRunResult;
  const activeFile=state.files.find(file=>file.id===state.activeJobId);
  const outputFiles=pdfResults(result?.outputFiles??[]);
  const outputDir=result?.outputDir??(outputFiles[0]?dirname(outputFiles[0]):"");
  const cancelled=result?.status==="cancelled" || activeFile?.status==="cancelled";
  const paused=result?.status==="paused" || activeFile?.status==="paused";
  const missingPdf=result?.ok===true && outputFiles.length===0;
  const failed=!cancelled && !paused && (result?.ok===false || activeFile?.status==="failed" || missingPdf);
  const reviewCount=result?.reviewItems.filter(item=>item.status==="open").length??0;
  const incompleteCount=result?.reviewItems.filter(item=>item.status==="open" && ["translation_incomplete","untranslated_region","untranslated_source_sentence"].includes(item.kind)).length??0;
  const status=cancelled?"중지됨":paused?"일시 중단":failed?"실패":incompleteCount?"미번역 구간 있음":"파일 생성 완료";

  return <section className="progress-workspace pdf-results-workspace" aria-labelledby="complete-title">
    <div className="pdf-results-heading">
      <h2 id="complete-title">{cancelled?"중지 결과 확인":paused?"중간 작업 확인":failed?"실행 결과 확인":"결과 확인"}</h2>
      <button type="button" className="primary-button" onClick={()=>void startNew()} disabled={resetting}>새 작업 시작</button>
    </div>
    {resetError?<p role="alert">{resetError}</p>:null}
    {openError?<p role="alert">{openError}</p>:null}
    <SummaryCards label="결과 요약" items={[
      {label:"상태",value:status,textValue:true},
      {label:"대상",value:state.files.length,unit:"개"},
      {label:"PDF",value:outputFiles.length,unit:"개"},
      {label:"확인할 후보",value:reviewCount,unit:"건"}
    ]} />
    {incompleteCount>0?<p className="result-inline-note" role="alert">{incompleteCount}개 구간은 번역이 완료되지 않아 원문으로 남았습니다. 검수 목록에서 원인과 해당 페이지를 확인하세요.</p>:null}
    {(reviewCount>0 || state.files.some(file=>file.status==="review_wait"))?<div><button type="button" className="secondary-button" onClick={()=>dispatch({type:"openReview"})}>생성된 결과 검수</button></div>:null}
    <section className="pdf-result-list" aria-label="생성된 PDF">
      <div className="pdf-results-heading">
        <h3>{outputFiles.length?"번역 PDF":"생성된 PDF 없음"}</h3>
        <button type="button" className="secondary-button" onClick={()=>void openPath(outputDir)} disabled={!outputDir}>폴더 열기</button>
      </div>
      {outputFiles.length?<ul>{outputFiles.map(path=><li key={path}>
        <span title={path}>{fileLabel(path)}</span>
        <button type="button" className="secondary-button" onClick={()=>void openPath(path)} aria-label={`${fileLabel(path)} 열기`}>PDF 열기</button>
      </li>)}</ul>:<p className="result-inline-note">{missingPdf?"PDF 결과가 생성되지 않았습니다. 실행 내역을 확인하세요.":"대상별 상태와 실행 메시지를 확인하세요."}</p>}
      {(failed || cancelled || paused) && outputFiles.length>0?<p className="result-inline-note" role="status">중단 전 생성된 PDF입니다. 실행 내역과 파일 내용을 확인하세요.</p>:null}
    </section>
    {failed ? <section className="pdf-result-diagnosis" aria-label="실패 원인과 해결 방법">
      <h3>{result?.diagnosis?.summary ?? "실행을 완료하지 못했습니다"}</h3>
      {result?.diagnosis ? <dl><div><dt>원인</dt><dd>{result.diagnosis.cause}</dd></div><div><dt>해결 방법</dt><dd>{result.diagnosis.solution}</dd></div></dl> : <p>실행 상세에서 오류 메시지를 확인하세요.</p>}
      <div className="failure-actions">
        {failureActions([result?.message,result?.diagnosis?.cause,...(result?.targetResults?.map(target=>target.status === "failure" ? target.message : "") ?? [])].join("\n")).map(action =>
          <button type="button" key={action.target} className="secondary-button" onClick={() => onOpenSettings(action.target)}>{action.label}</button>)}
        <button type="button" className="secondary-button" onClick={openDetails}>실행 상세로 이동</button>
        {outputDir ? <button type="button" className="secondary-button" onClick={() => void openPath(outputDir)}>결과 폴더 열기</button> : null}
      </div>
    </section>:null}
    <details className="pdf-run-details" ref={detailsRef}>
      <summary>실행 내역<Icon name="chevron" className="disclosure-icon" /></summary>
      {outputDir?<p className="result-location">저장 위치 <span>{outputDir}</span></p>:null}
      {result?.targetResults?.length?<section aria-label="대상별 실행 결과" className="pdf-target-results">
        <h3>대상별 결과</h3>
        <ul>{result.targetResults.map(target=><li key={target.source_path}>
          <span title={target.source_path}>{fileLabel(target.source_path)}</span>
          <span>{target.status==="success"?"파일 생성 완료":target.status==="failure"?"실패":target.status==="cancelled"?"중지됨":"미실행"}</span>
          {target.status!=="success" && target.message?<details><summary>실행 메시지 보기<Icon name="chevron" className="disclosure-icon" /></summary><pre>{target.message}</pre></details>:null}
        </li>)}</ul>
      </section>:null}
      {result?.message && (failed || cancelled || paused)?<details><summary>기술 상세<Icon name="chevron" className="disclosure-icon" /></summary><pre>{result.message}</pre></details>:null}
    </details>
  </section>;
}

function dirname(path:string) {const value=path.replace(/\//g,"\\");const index=value.lastIndexOf("\\");return index<0?value:value.slice(0,index);}
