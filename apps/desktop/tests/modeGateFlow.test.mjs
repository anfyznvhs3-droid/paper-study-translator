import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";

const { initialProjectState, projectReducer } = loadTsModule(fileURLToPath(new URL("../src/state/projectState.ts", import.meta.url)));
const prepared = () => ({ ...initialProjectState, engine: "claude-code-agent", quality: "true", outputMode: "mono", reviewMode: "off", files: [{ id: "source", name: "sample.pdf", relativePath: "F:\\sample.pdf", kind: "file" }] });

test("Gemini entry selects its engine while preserving prepared inputs and settings", () => {
  const before = prepared();
  const after = projectReducer(before, { type: "setTranslationMode", value: "machine" });
  assert.equal(after.engine, "gemini-flash-lite");
  for (const key of ["files", "quality", "outputMode", "reviewMode"]) assert.equal(after[key], before[key]);
});

test("reselecting agent entry retains the chosen Claude engine and prepared settings", () => {
  const before = prepared();
  const after = projectReducer(before, { type: "setTranslationMode", value: "agent" });
  for (const key of ["engine", "files", "quality", "outputMode", "reviewMode"]) assert.equal(after[key], before[key]);
});

test("switching from Gemini to agent selects a supported agent without clearing inputs", () => {
  const before = { ...prepared(), translationMode: "machine", engine: "gemini-flash-lite" };
  const after = projectReducer(before, { type: "setTranslationMode", value: "agent" });
  assert.equal(after.engine, "codex-agent");
  assert.equal(after.files, before.files);
  assert.equal(projectReducer(after, { type: "setEngine", value: "gemini-flash-lite" }), after);
});
