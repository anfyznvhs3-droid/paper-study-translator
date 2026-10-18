import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const wikiBridgePath = fileURLToPath(new URL("../src/translation/wikiBridge.ts", import.meta.url));

test("wiki bridge exposes CAT glossary import and export", () => {
  const source = readFileSync(wikiBridgePath, "utf8");

  assert.match(source, /exportGlossary/);
  assert.match(source, /importGlossary/);
  assert.match(source, /wiki_export_glossary/);
  assert.match(source, /wiki_import_glossary/);
});

test("wiki bridge exposes domain deletion", () => {
  const source = readFileSync(wikiBridgePath, "utf8");

  assert.match(source, /export interface DomainDeleteResult/);
  assert.match(source, /domains: DomainInfo\[\]/);
  assert.match(source, /backupPath: string/);
  assert.match(source, /export async function deleteDomain\(slug: string\): Promise<DomainDeleteResult>/);
  assert.match(source, /wiki_delete_domain/);
});

test("wiki bridge exposes official shared knowledge pack commands", () => {
  const source = readFileSync(wikiBridgePath, "utf8");

  assert.match(source, /export interface SharedPackInfo/);
  assert.match(source, /export interface SharedPackInstallRequest/);
  assert.match(source, /listSharedPacks/);
  assert.match(source, /installSharedPack/);
  assert.match(source, /removeSharedPack/);
  assert.match(source, /wiki_list_shared_packs/);
  assert.match(source, /wiki_install_shared_pack/);
  assert.match(source, /wiki_remove_shared_pack/);
});
