import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const progressWorkspacePath = fileURLToPath(
  new URL("../src/screens/ProgressWorkspace.tsx", import.meta.url)
);

test("progress workspace shows observable Codex Agent runtime health", () => {
  const source = readFileSync(progressWorkspacePath, "utf8");

  assert.match(source, /Codex Agent 실제 진행 상태/);
  assert.match(source, /Agent 작업 모니터/);
  assert.match(source, /완료 batch/);
  assert.match(source, /다음 batch 응답/);
  assert.match(source, /마지막 활동/);
  assert.match(source, /중간 저장/);
  assert.match(source, /최근 파일/);
  assert.match(source, /최근 응답 미리보기/);
  assert.match(source, /모니터 자세히 보기/);
  assert.match(source, /정체 의심/);
  assert.match(source, /일시 중단됨/);
});

test("progress workspace shows waiting and cancellation without fabricated heartbeat", () => {
  const source = readFileSync(progressWorkspacePath, "utf8");

  assert.doesNotMatch(source, /advanceMachineHeartbeat/);
  assert.match(source, /전체 완료율은 아직 계산할 수 없습니다/);
  assert.match(source, /번역 중지/);
  assert.doesNotMatch(source, /Google 번역 진행 상태/);
  assert.doesNotMatch(source, /machine-live-status/);
  assert.doesNotMatch(source, />대상</);
  assert.doesNotMatch(source, />상태</);
  assert.doesNotMatch(source, />안내</);
  assert.doesNotMatch(source, /긴 문서는 몇 분 걸릴 수 있습니다/);
});
