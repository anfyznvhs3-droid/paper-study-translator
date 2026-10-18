import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function loadEngineAdapters() {
  const source = fs.readFileSync(new URL("../src/translation/engineAdapters.ts", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020
    }
  });
  const context = { exports: {} };
  vm.runInNewContext(outputText, context);
  return context.exports;
}

function buildRun() {
  const { createMockTranslationRun } = loadEngineAdapters();
  return createMockTranslationRun({
    engine: "codex-agent",
    mode: "agent",
    quality: "realistic",
    outputMode: "dual",
    reviewMode: "on",
    files: []
  });
}

test("setStageByPhase marks earlier stages done, current stage running, later stages waiting", () => {
  const { setStageByPhase } = loadEngineAdapters();
  const run = buildRun();

  const updated = setStageByPhase(run, "translate");
  const byId = Object.fromEntries(updated.stages.map((stage) => [stage.id, stage.status]));

  assert.equal(byId.intake, "done");
  assert.equal(byId.extract, "done");
  assert.equal(byId.translate, "running");
  assert.equal(byId.consistency, "waiting");
  assert.equal(byId["review-queue"], "waiting");
});

test("setStageByPhase maps agent batch phase to translate stage", () => {
  const { setStageByPhase } = loadEngineAdapters();
  const run = buildRun();

  const updated = setStageByPhase(run, "agent-batch");
  const byId = Object.fromEntries(updated.stages.map((stage) => [stage.id, stage.status]));

  assert.equal(byId.intake, "done");
  assert.equal(byId.extract, "done");
  assert.equal(byId.translate, "running");
  assert.equal(byId.consistency, "waiting");
});

test("setStageByPhase leaves the run unchanged for an unknown phase", () => {
  const { setStageByPhase } = loadEngineAdapters();
  const run = buildRun();

  const updated = setStageByPhase(run, "unknown-phase");

  assert.equal(updated, run);
});

test("setStageByPhase returns null when given a null run", () => {
  const { setStageByPhase } = loadEngineAdapters();

  assert.equal(setStageByPhase(null, "translate"), null);
});
