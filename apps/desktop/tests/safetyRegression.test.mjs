import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";
const load = (p) => loadTsModule(fileURLToPath(new URL(p, import.meta.url)));

test("untrusted and retired settings cannot crash theme creation", () => {
  const { validateSettings } = load("../src/state/persistedSettings.ts");
  const { getThemeTokens } = load("../src/theme/themeOptions.ts");
  for (const input of [null, [], "bad", 1, {themePreset:"retired-theme",darkPreset:{},engine:"unknown"}]) {
    const settings = validateSettings(input);
    assert.equal(getThemeTokens(settings.themePreset ?? "soft-pink").background !== undefined,true);
    assert.equal(settings.engine,undefined);
  }
  const valid = validateSettings({themePreset:"lavender",darkMode:true,sharedKnowledgeEnabled:true,domain:"quality-manufacturing"});
  assert.equal(valid.themePreset,"lavender");
  assert.equal(valid.darkMode,true);
});

test("batch completion records every target without marking failed inputs successful", () => {
  const {projectReducer:r,initialProjectState:initial}=load("../src/state/projectState.ts");
  let state=r(initial,{type:"addSourceItems",inputMode:"file",items:[
    {name:"a.pdf",relativePath:"D:\\a.pdf",kind:"file"},
    {name:"b.pdf",relativePath:"D:\\b.pdf",kind:"file"},
    {name:"c.pdf",relativePath:"D:\\c.pdf",kind:"file"}]});
  state=r(state,{type:"startMockJob"});
  state=r(state,{type:"setTargetStatus",sourcePath:"D:\\b.pdf",status:"running"});
  assert.equal(state.activeJobId,state.files[1].id);
  state=r(state,{type:"finishMockJob",status:"failure",outputFiles:["a-ko.pdf"],targetResults:[
    {source_path:"D:\\a.pdf",status:"success",message:"ok",output_files:["a-ko.pdf"]},
    {source_path:"D:\\b.pdf",status:"failure",message:"429",output_files:[]},
    {source_path:"D:\\c.pdf",status:"skipped",message:"not run",output_files:[]}]});
  assert.equal(state.files[0].status,"review_wait");
  assert.equal(state.files[1].status,"failed");
  assert.equal(state.files[2].status,"skipped");
  assert.equal(state.lastRunResult.outputFiles[0],"a-ko.pdf");
});

test("elapsed time cannot manufacture completion percentage",()=>{
 const {projectReducer:r,initialProjectState:initial}=load("../src/state/projectState.ts");
 let state=r({...initial,translationMode:"machine"},{type:"addMockFiles"});
 state=r(state,{type:"startMockJob"});state=r(state,{type:"setRunPhase",phase:"translate"});
 const before=state.files[0].progress;
 for(let n=0;n<30;n++)state=r(state,{type:"advanceMachineHeartbeat"});
 assert.equal(state.files[0].progress,before);
});

test("review cannot finish with unresolved candidates",()=>{
 const {projectReducer:r,initialProjectState:initial}=load("../src/state/projectState.ts");
 let state=r(initial,{type:"addMockFiles"});state=r(state,{type:"startMockJob"});
 state=r(state,{type:"finishMockJob",status:"success",outputFiles:["result.pdf"],reviewItems:[
  {page:1,kind:"term_mismatch",source_text:"A",reason:"check",status:"open"}]});
 const unchanged=r(state,{type:"completeReview"});
 assert.equal(unchanged.files[0].status,"review_wait");
 state=r(state,{type:"approveAllReviewItems"});
 state=r(state,{type:"completeReview"});
 assert.equal(state.files[0].status,"completed");
});

test("action and semantic text remain readable across presets and conflicting custom colors",()=>{
 const {themePresets,themePresetsDark,defaultCustomTheme,themeCssVariables,contrastRatio}=load("../src/theme/themeOptions.ts");
 for(const tokens of [...Object.values(themePresets),...Object.values(themePresetsDark),{...defaultCustomTheme,surface:"#000000",surfaceSelected:"#ffffff",text:"#000000"}]) {
  const vars=themeCssVariables(tokens);
  assert.ok(contrastRatio(vars["--action-bg"],vars["--action-fg"])>=4.5);
  assert.ok(contrastRatio(vars["--surface-selected"],vars["--on-selected"])>=4.5);
  for(const key of ["--surface","--surface-strong","--surface-hover","--surface-selected","--bg"])
   assert.ok(contrastRatio(vars[key],vars["--text"])>=4.5,key);
 }
});
test("review identity includes its document so repeated page/text pairs do not share approvals",()=>{
 const {projectReducer:r,initialProjectState:initial}=load("../src/state/projectState.ts");
 let state=r(initial,{type:"addMockFiles"});state=r(state,{type:"startMockJob"});
 const a={source_path:"A.pdf",page:1,kind:"term_mismatch",source_text:"same",reason:"check",status:"open"};
 const b={...a,source_path:"B.pdf"};
 state=r(state,{type:"finishMockJob",status:"success",reviewItems:[a,b]});
 state=r(state,{type:"approveReviewItems",keys:[a]});
 assert.equal(state.lastRunResult.reviewItems[0].status,"approved");
 assert.equal(state.lastRunResult.reviewItems[1].status,"open");
});
