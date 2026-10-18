import { invoke } from "@tauri-apps/api/core";
import type { ProjectState, ReviewItem, SourceFile } from "../state/projectState";
import { validateSettings } from "../state/persistedSettings";

export type SavedReviewState = Pick<ProjectState,"runId"|"reviewOpen"|"files"|"activeJobId"|"lastRunResult"|"translationMode"|"engine"|"outputMode"|"reviewMode"|"domain">;
interface Snapshot {version:1; state:SavedReviewState}
// Rust Option fields arrive as null; older snapshots retain those JSON values.
const optionalString=(value:unknown)=>value==null || typeof value==="string";
const record=(value:unknown):value is Record<string,unknown>=>!!value && typeof value==="object" && !Array.isArray(value);
const strings=(value:unknown):value is string[]=>Array.isArray(value) && value.every((v)=>typeof v==="string");
export function validateReviewSnapshot(value:unknown): SavedReviewState | null {
  if(!record(value) || value.version!==1 || !record(value.state))return null;
  const state=value.state;
  if(typeof state.runId!=="string" || !/^[a-zA-Z0-9-]{1,100}$/.test(state.runId))return null;
  const preferences=validateSettings(state);
  if(!preferences.engine || !preferences.translationMode || !preferences.outputMode || !preferences.reviewMode || !preferences.domain)return null;
  if(!Array.isArray(state.files) || state.files.length>10000)return null;
  const files:SourceFile[]=[];
  for(const item of state.files) {
    if(!record(item) || typeof item.id!=="string" || typeof item.name!=="string" || !["file","folder"].includes(String(item.kind))
      || !["pending","running","review_wait","completed","failed","paused","cancelled","skipped"].includes(String(item.status)))return null;
    if(!optionalString(item.sourcePath))return null;
    const file={...item,sourcePath:item.sourcePath??undefined} as unknown as SourceFile;
    file.progress=Number.isFinite(item.progress)?Math.max(0,Math.min(100,Number(item.progress))):0;
    file.pages=Number.isFinite(item.pages)?Math.max(0,Number(item.pages)):0;
    if(file.status==="running")file.status="paused";
    files.push(file);
  }
  const result=state.lastRunResult;
  if(!record(result) || typeof result.ok!=="boolean" || typeof result.message!=="string" || !strings(result.outputFiles) || !Array.isArray(result.reviewItems))return null;
  const reviewItems:ReviewItem[]=[];
  for(const item of result.reviewItems) {
    // Page 0 is the native audit's document-level warning, not a PDF page.
    if(!record(item) || !Number.isInteger(item.page) || Number(item.page)<0 || typeof item.source_text!=="string" || typeof item.reason!=="string"
       || typeof item.kind!=="string" || !optionalString(item.source_path) || !optionalString(item.translated_text)
       || !["open","approved","rejected","resolved"].includes(String(item.status)))return null;
    reviewItems.push({...item,source_path:item.source_path??undefined,translated_text:item.translated_text??undefined} as unknown as ReviewItem);
  }
  if(!optionalString(result.outputDir))return null;
  if(result.diagnosis!=null && (!record(result.diagnosis) || !["summary","cause","solution"].every((key)=>typeof (result.diagnosis as Record<string,unknown>)[key]==="string")))return null;
  if(result.targetResults!=null && (!Array.isArray(result.targetResults) || !result.targetResults.every((target)=>record(target) && typeof target.source_path==="string" && typeof target.message==="string" && ["running","success","failure","cancelled","skipped"].includes(String(target.status)) && strings(target.output_files))))return null;
  return {runId:state.runId,reviewOpen:typeof state.reviewOpen==="boolean"?state.reviewOpen:result.ok && files.some((file)=>file.status==="review_wait"),files,activeJobId:typeof state.activeJobId==="string" && files.some((f)=>f.id===state.activeJobId)?state.activeJobId:files[0]?.id??null,
    lastRunResult:{...result,reviewItems,diagnosis:result.diagnosis??undefined,outputDir:result.outputDir??undefined,targetResults:result.targetResults??undefined} as unknown as ProjectState["lastRunResult"],
    translationMode:preferences.translationMode as ProjectState["translationMode"],engine:preferences.engine as ProjectState["engine"],
    outputMode:preferences.outputMode as ProjectState["outputMode"],reviewMode:preferences.reviewMode as ProjectState["reviewMode"],domain:preferences.domain};
}
export function sessionErrorMessage(error:unknown):string {
  const message=record(error) && typeof error.message==="string" ? error.message : String(error);
  return message.replace(/^(?:Error:\s*)+/,"").replace(/^\[QDT_SESSION_[A-Z_]+\]\s*/,"");
}
export async function loadReviewSession():Promise<SavedReviewState|null>{
  const value=await invoke<unknown>("load_review_session");
  if(value===null)return null;
  const valid=validateReviewSnapshot(value);
  if(!valid)throw new Error("이전 작업의 저장 형식을 확인하지 못했습니다. 새 작업을 시작할 수 있습니다.");
  return valid;
}
let queue:Promise<void>=Promise.resolve();
export function persistReviewSession(state:ProjectState):Promise<void> {
  const snapshot:Snapshot|null=state.lastRunResult && state.runId ? {version:1,state:{
    runId:state.runId,reviewOpen:state.reviewOpen,files:state.files,activeJobId:state.activeJobId,lastRunResult:state.lastRunResult,
    translationMode:state.translationMode,engine:state.engine,outputMode:state.outputMode,reviewMode:state.reviewMode,domain:state.domain
  }}:null;
  const operation=queue.catch(()=>{}).then(()=>invoke<void>("save_review_session",{snapshot}));
  queue=operation;
  return operation;
}
