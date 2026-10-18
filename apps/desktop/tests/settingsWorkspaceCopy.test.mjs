import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const settingsPath = new URL("../src/screens/SettingsWorkspace.tsx", import.meta.url);
const cssPath = new URL("../src/styles/global.css", import.meta.url);

test("settings exposes official shared knowledge as an opt-in section", () => {
  const source = readFileSync(settingsPath, "utf8");
  const css = readFileSync(cssPath, "utf8");

  assert.match(source, /공유 용어팩/);
  assert.match(source, /공식 공유 지식/);
  assert.match(source, /sharedKnowledgeEnabled/);
  assert.match(source, /setSharedKnowledgeEnabled/);
  assert.match(source, /공식 공유팩 받기/);
  assert.match(source, /내 문서나 검수 내용은 업로드하지 않습니다/);
  assert.match(css, /\.shared-knowledge-panel\s*{[\s\S]*?display: grid;/);
});
