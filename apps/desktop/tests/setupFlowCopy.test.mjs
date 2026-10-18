import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const setupFlowPath = fileURLToPath(new URL("../src/screens/SetupFlow.tsx", import.meta.url));

test("setup flow accepts PDF/PPTX but excludes legacy PPT binary inputs", () => {
  const source = readFileSync(setupFlowPath, "utf8");

  assert.match(source, /PDF\/PPTX/);
  assert.match(source, /"pptx"/);
  assert.doesNotMatch(source, /"ppt"/);
  assert.doesNotMatch(source, /accept="[^"]*\.ppt(?:,|")/);
});
