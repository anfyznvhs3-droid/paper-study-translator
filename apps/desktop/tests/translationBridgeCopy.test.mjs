import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const bridgePath = new URL("../src/translation/translationBridge.ts", import.meta.url);
const setupPath = new URL("../src/screens/SetupFlow.tsx", import.meta.url);

test("translation bridge sends selected domain and shared knowledge opt-in", () => {
  const bridge = readFileSync(bridgePath, "utf8");
  const setup = readFileSync(setupPath, "utf8");

  assert.match(bridge, /domain:\s*string/);
  assert.match(bridge, /sharedKnowledgeEnabled:\s*boolean/);
  assert.match(bridge, /domain:\s*request\.domain/);
  assert.match(bridge, /shared_knowledge:\s*request\.sharedKnowledgeEnabled/);
  assert.match(setup, /domain:\s*state\.domain/);
  assert.match(setup, /sharedKnowledgeEnabled:\s*state\.sharedKnowledgeEnabled/);
});
