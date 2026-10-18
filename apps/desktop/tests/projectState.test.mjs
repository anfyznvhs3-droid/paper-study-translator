import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";

function loadProjectState() {
  return loadTsModule(fileURLToPath(new URL("../src/state/projectState.ts", import.meta.url)));
}

test("shared knowledge opt-in defaults off and can be toggled without resetting a run", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  assert.equal(initialProjectState.sharedKnowledgeEnabled, false);

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  const runBeforeToggle = state.translationRun;
  const activeJobBeforeToggle = state.activeJobId;

  state = projectReducer(state, { type: "setSharedKnowledgeEnabled", value: true });

  assert.equal(state.sharedKnowledgeEnabled, true);
  assert.equal(state.translationRun, runBeforeToggle);
  assert.equal(state.activeJobId, activeJobBeforeToggle);

  state = projectReducer(state, { type: "setSharedKnowledgeEnabled", value: false });

  assert.equal(state.sharedKnowledgeEnabled, false);
  assert.equal(state.translationRun, runBeforeToggle);
  assert.equal(state.activeJobId, activeJobBeforeToggle);
});

test("setRunPhase advances stage and progress but keeps the file running", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, { type: "setRunPhase", phase: "translate" });

  const activeFile = state.files.find((file) => file.id === state.activeJobId);

  assert.equal(activeFile.status, "running");
  assert.equal(activeFile.progress, 56);
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "translate").status, "running");
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "intake").status, "done");
});

test("setRunPhase at the consistency phase keeps the file running until finishMockJob arrives", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, { type: "setRunPhase", phase: "consistency" });

  let activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.status, "running");
  assert.equal(activeFile.progress, 78);

  state = projectReducer(state, {
    type: "finishMockJob",
    status: "success",
    message: "done",
    outputFiles: ["out.pdf"],
    reviewItems: []
  });

  activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.status, "review_wait");
  assert.equal(activeFile.progress, 100);
  assert.equal(state.lastRunResult.ok, true);
});

test("setRunPhase maps agent pipeline phases to stages and progress", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });

  state = projectReducer(state, { type: "setRunPhase", phase: "agent-extract" });
  let activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 34);
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "extract").status, "running");

  state = projectReducer(state, { type: "setRunPhase", phase: "agent-batch" });
  activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 56);
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "translate").status, "running");
});

test("agent batch status advances visible progress inside the translate phase", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, { type: "setRunPhase", phase: "agent-batch" });

  let activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 56);

  state = projectReducer(state, {
    type: "setAgentStatus",
    status: {
      health: "active",
      current_batch: 3,
      total_batches: 4,
      completed_batches: 2,
      last_activity_seconds: 3,
      message: "Codex Agent가 batch 3 / 4 응답을 생성 중입니다.",
      workspace: "ws"
    }
  });

  activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.ok(activeFile.progress > 56, `expected batch progress to move past 56, got ${activeFile.progress}`);
  assert.ok(activeFile.progress < 78, `batch progress should stay before render, got ${activeFile.progress}`);
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "translate").status, "running");
});

test("elapsed time does not advance translation completion", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "setTranslationMode", value: "machine" });
  state = projectReducer(state, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, { type: "setRunPhase", phase: "translate" });

  let activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 56);

  state = projectReducer(state, { type: "advanceMachineHeartbeat" });
  activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 56);
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "translate").status, "running");

  for (let index = 0; index < 20; index += 1) {
    state = projectReducer(state, { type: "advanceMachineHeartbeat" });
  }
  activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 56);
});

test("setRunPhase agent-render clears the batch monitor and advances progress", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, {
    type: "setAgentStatus",
    status: {
      health: "active",
      current_batch: 1,
      total_batches: 1,
      completed_batches: 0,
      last_activity_seconds: 5,
      message: "Codex Agent가 다음 batch 응답을 생성 중입니다.",
      workspace: "ws"
    }
  });
  assert.ok(state.agentStatus, "batch monitor present during agent-batch");

  state = projectReducer(state, { type: "setRunPhase", phase: "agent-render" });

  const activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.progress, 78);
  assert.equal(state.agentStatus, null, "batch monitor cleared once render starts");
  assert.equal(state.translationRun.stages.find((stage) => stage.id === "consistency").status, "running");
});

test("agent status updates are kept and paused jobs remain resumable", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  let state = projectReducer(initialProjectState, { type: "addMockFiles" });
  state = projectReducer(state, { type: "startMockJob" });
  state = projectReducer(state, {
    type: "setAgentStatus",
    status: {
      health: "waiting",
      current_batch: 46,
      total_batches: 121,
      completed_batches: 45,
      last_activity_seconds: 8,
      message: "Codex Agent가 batch 46 / 121 응답을 생성 중입니다.",
      workspace: "D:\\Downloads\\QDT_Output\\.qdt-agent\\paper"
    }
  });
  state = projectReducer(state, {
    type: "finishMockJob",
    status: "paused",
    message: "처리 시간이 길어 일시 중단됨",
    outputFiles: [],
    reviewItems: []
  });

  const activeFile = state.files.find((file) => file.id === state.activeJobId);
  assert.equal(activeFile.status, "paused");
  assert.notEqual(activeFile.progress, 100);
  assert.equal(state.lastRunResult.ok, false);
  assert.equal(state.agentStatus.completed_batches, 45);
});

test("light and dark modes remember separate theme presets", () => {
  const { projectReducer, initialProjectState } = loadProjectState();

  // Choose lavender while in light mode.
  let state = projectReducer(initialProjectState, { type: "setThemePreset", value: "lavender" });
  assert.equal(state.themePreset, "lavender");
  assert.equal(state.darkPreset, "soft-pink"); // dark selection untouched

  // Switch to dark and choose a different preset.
  state = projectReducer(state, { type: "setDarkMode", value: true });
  state = projectReducer(state, { type: "setThemePreset", value: "rosy-purple" });
  assert.equal(state.darkPreset, "rosy-purple");
  assert.equal(state.themePreset, "lavender"); // light selection preserved

  // Editing a custom color in dark mode flips only the dark preset to custom.
  state = projectReducer(state, { type: "setCustomThemeToken", key: "primary", value: "#112233" });
  assert.equal(state.darkPreset, "custom");
  assert.equal(state.themePreset, "lavender");
});

test("machine mode selects Gemini as its only API provider", () => {
  const { projectReducer, initialProjectState, engineOptionsByMode, engineLabels } = loadProjectState();
  const state = projectReducer(initialProjectState, { type: "setTranslationMode", value: "machine" });
  assert.equal(state.engine, "gemini-flash-lite");
  assert.deepEqual([...engineOptionsByMode.machine], ["gemini-flash-lite"]);
  assert.equal(engineLabels[state.engine], "Gemini Flash-Lite");
});
