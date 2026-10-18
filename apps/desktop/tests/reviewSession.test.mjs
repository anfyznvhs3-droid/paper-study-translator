import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";

const { validateReviewSnapshot, sessionErrorMessage } = loadTsModule(fileURLToPath(new URL("../src/translation/reviewSession.ts", import.meta.url)));
const { projectReducer, initialProjectState } = loadTsModule(fileURLToPath(new URL("../src/state/projectState.ts", import.meta.url)));
function nativeSnapshot() {
  return {version:1,state:{runId:"run-native-success",reviewOpen:true,engine:"gemini-flash-lite",translationMode:"machine",outputMode:"dual",reviewMode:"on",domain:"quality-manufacturing",
    files:[{id:"file-1",name:"sample.pdf",kind:"file",sourcePath:"F:\\sample.pdf",status:"review_wait",progress:100,pages:1}],activeJobId:"file-1",
    lastRunResult:{ok:true,status:"success",message:"completed",outputDir:"F:\\output",outputFiles:["F:\\output\\sample-dual.pdf"],diagnosis:null,
      targetResults:[{source_path:"F:\\sample.pdf",status:"success",message:"completed",output_files:["F:\\output\\sample-dual.pdf"]}],
      reviewItems:[{source_path:"F:\\sample.pdf",page:1,kind:"image_ocr",severity:"warning",source_text:"Households",translated_text:"가구",reason:"check",status:"approved"}]}}};
}

test("retired provider snapshots keep approved reviews and PDF paths",()=>{
  const snapshot=nativeSnapshot();snapshot.state.engine="google-translate-draft";
  const session=validateReviewSnapshot(snapshot);
  assert.ok(session);
  assert.equal(session.engine,"gemini-flash-lite");
  assert.equal(session.lastRunResult.reviewItems[0].status,"approved");
  assert.equal(session.lastRunResult.outputFiles[0],snapshot.state.lastRunResult.outputFiles[0]);
  assert.equal(snapshot.state.engine,"google-translate-draft","do not rewrite historical input");
});

test("native success with null diagnosis restores approved decisions and output paths",()=>{
  const snapshot=nativeSnapshot();
  const session=validateReviewSnapshot(snapshot);
  assert.ok(session);
  assert.equal(session.lastRunResult.diagnosis,undefined);
  const restored=projectReducer(initialProjectState,{type:"restoreSession",session});
  assert.equal(restored.lastRunResult.reviewItems[0].status,"approved");
  assert.equal(restored.lastRunResult.outputFiles[0],"F:\\output\\sample-dual.pdf");
  assert.equal(restored.reviewOpen,true);
  assert.equal(snapshot.state.lastRunResult.diagnosis,null,"validation must not mutate the saved input");
});

test("native optional null text and document-level page zero remain reviewable",()=>{
  const snapshot=nativeSnapshot();
  Object.assign(snapshot.state.lastRunResult.reviewItems[0],{page:0,kind:"audit_unavailable",status:"open",source_path:null,translated_text:null});
  const session=validateReviewSnapshot(snapshot);
  assert.ok(session);
  assert.equal(session.lastRunResult.reviewItems[0].page,0);
  assert.equal(session.lastRunResult.reviewItems[0].source_path,undefined);
  assert.equal(session.lastRunResult.reviewItems[0].translated_text,undefined);
  assert.equal(session.lastRunResult.reviewItems[0].status,"open");
});

test("null compatibility does not accept malformed diagnosis or review data",()=>{
  for(const diagnosis of [42,[],{}, {summary:"a",cause:"b"}]) {
    const snapshot=nativeSnapshot();snapshot.state.lastRunResult.diagnosis=diagnosis;
    assert.equal(validateReviewSnapshot(snapshot),null);
  }
  for(const patch of [{page:-1},{page:1.5},{translated_text:42},{source_path:[]},{source_text:null},{status:"fake"}]) {
    const snapshot=nativeSnapshot();Object.assign(snapshot.state.lastRunResult.reviewItems[0],patch);
    assert.equal(validateReviewSnapshot(snapshot),null);
  }
});

test("session notices show the message without runtime Error or internal code prefixes",()=>{
  assert.equal(sessionErrorMessage(new Error("이전 작업을 열지 못했습니다.")),"이전 작업을 열지 못했습니다.");
  assert.equal(sessionErrorMessage("Error: [QDT_SESSION_READ] 검수 기록을 읽지 못했습니다."),"검수 기록을 읽지 못했습니다.");
});
