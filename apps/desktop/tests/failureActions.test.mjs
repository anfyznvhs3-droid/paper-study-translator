import assert from "node:assert/strict";
import test from "node:test";
import {fileURLToPath} from "node:url";
import {loadTsModule} from "./helpers/loadTsModule.mjs";
const {failureActions} = loadTsModule(fileURLToPath(new URL("../src/translation/failureActions.ts",import.meta.url)));
test("connection faults point to their specific settings without invoking a connection",()=>{
  for(const [code,target] of [["KEY_MISSING","key"],["AUTH","key"],["MODEL","model"],["RATE_LIMITED","usage"],["NETWORK","connection"],["TIMEOUT","connection"],["CONNECTION","connection"]])
    assert.equal(failureActions(`trace [QDT_GEMINI_${code}] failed`)[0].target,target);
  assert.deepEqual(Array.from(failureActions("[QDT_GEMINI_ACCESS]"),x=>x.target),["key","model"]);
  assert.equal(failureActions("[QDT_PROCESS_TIMEOUT]")[0].target,"connection");
});
test("content, local runtime and unknown failures do not suggest changing API credentials",()=>{
  for(const code of ["PRESERVATION","FORMAT","EXPANSION","BLOCKED","TRUNCATED","RUNTIME","EMPTY"])
    assert.equal(failureActions(`[QDT_GEMINI_${code}]`).length,0);
  assert.equal(failureActions("API key in path C:/MODEL/AUTH/test").length,0);
  assert.equal(failureActions("[QDT_GEMINI_AUTH_OTHER]").length,0);
  assert.equal(failureActions("[QDT_GEMINI_AUTH] repeated [QDT_GEMINI_AUTH]").length,1);
});
