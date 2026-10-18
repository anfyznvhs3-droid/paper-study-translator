import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const sharedKnowledgePath = new URL("../src/translation/sharedKnowledge.ts", import.meta.url);
const settingsPath = new URL("../src/screens/SettingsWorkspace.tsx", import.meta.url);

test("shared knowledge module validates manifest and hashes downloaded glossary", () => {
  const source = readFileSync(sharedKnowledgePath, "utf8");

  assert.match(source, /export interface SharedKnowledgeManifest/);
  assert.match(source, /schemaVersion:\s*1/);
  assert.match(source, /sha256Hex/);
  assert.match(source, /crypto\.subtle\.digest/);
  assert.match(source, /fetchOfficialSharedPacks/);
  assert.match(source, /installSharedPack/);
  assert.match(source, /validateManifest/);
});

test("settings sync button calls official shared knowledge downloader", () => {
  const source = readFileSync(settingsPath, "utf8");

  assert.match(source, /fetchOfficialSharedPacks/);
  assert.match(source, /officialSharedKnowledgeStatus/);
  assert.match(source, /sharedKnowledgeBusy/);
  assert.match(source, /listSharedPacks/);
  assert.match(source, /installed-shared-pack-list/);
  assert.match(source, /설치된 공유팩/);
});
