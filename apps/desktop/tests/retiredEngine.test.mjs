import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";
const load = path => loadTsModule(fileURLToPath(new URL(path, import.meta.url)));

test("machine translation exposes only Gemini and cannot select the retired provider", () => {
  const { engineOptionsByMode, projectReducer, initialProjectState } = load("../src/state/projectState.ts");
  assert.deepEqual([...engineOptionsByMode.machine], ["gemini-flash-lite"]);
  const state = projectReducer(initialProjectState, {type:"setTranslationMode",value:"machine"});
  assert.equal(projectReducer(state, {type:"setEngine",value:"google-translate-draft"}).engine, "gemini-flash-lite");
});
test("old Google preferences migrate without losing output, review, domain or theme settings", () => {
  const { validateSettings } = load("../src/state/persistedSettings.ts");
  const old = {translationMode:"machine",engine:"google-translate-draft",outputMode:"dual",reviewMode:"on",domain:"quality-manufacturing",darkMode:true};
  assert.deepEqual({...validateSettings(old)}, {...old,engine:"gemini-flash-lite"});
  assert.equal(old.engine, "google-translate-draft");
});
