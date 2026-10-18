import { invoke } from "@tauri-apps/api/core";

export interface GlossaryEntry {
  source: string;
  target: string;
  notes: string;
}

export interface Candidate {
  source: string;
  target: string;
  status: string;
  confidence: string;
  origin: string;
  ts: string;
  signal?: string;
}

export async function listGlossary(domain: string): Promise<GlossaryEntry[]> {
  const raw = await invoke<string>("wiki_list_glossary", { domain });
  return JSON.parse(raw);
}

export async function addTerm(domain: string, source: string, target: string, notes: string = ""): Promise<{ added: boolean }> {
  const raw = await invoke<string>("wiki_add_term", { domain, source, target, notes });
  return JSON.parse(raw);
}

export async function deleteTerm(domain: string, source: string): Promise<{ deleted: boolean }> {
  const raw = await invoke<string>("wiki_delete_term", { domain, source });
  return JSON.parse(raw);
}

export async function listCandidates(domain: string): Promise<Candidate[]> {
  const raw = await invoke<string>("wiki_list_candidates", { domain });
  return JSON.parse(raw);
}

export async function promote(domain: string, source: string): Promise<{ promoted: boolean }> {
  const raw = await invoke<string>("wiki_promote", { domain, source });
  return JSON.parse(raw);
}

export async function reject(domain: string, source: string, reason: string = ""): Promise<{ ok: boolean }> {
  const raw = await invoke<string>("wiki_reject", { domain, source, reason });
  return JSON.parse(raw);
}

export async function proposeDomain(textFile: string): Promise<{ domain: string | null }> {
  const raw = await invoke<string>("wiki_propose_domain", { textFile });
  return JSON.parse(raw);
}

export interface DomainInfo {
  slug: string;
  terms: number;
}

export interface DomainDeleteResult {
  domains: DomainInfo[];
  backupPath: string;
}

export type CatGlossaryFormat = "omegat" | "tbx";
export type CatImportMode = "candidates" | "confirmed";

export interface GlossaryExportResult {
  exported: number;
  path: string;
  format: CatGlossaryFormat;
}

export interface GlossaryImportResult {
  imported: number;
  mode: CatImportMode;
  format: CatGlossaryFormat;
}

export interface SharedPackInfo {
  id: string;
  domain: string;
  displayName: string;
  version: string;
  sha256: string;
  terms: number;
  installedAt: string;
}

export interface SharedPackInstallRequest {
  id: string;
  domain: string;
  displayName: string;
  version: string;
  sha256: string;
  glossaryCsv: string;
  terms: number;
}

export async function listDomains(): Promise<DomainInfo[]> {
  return invoke<DomainInfo[]>("wiki_list_domains");
}

export async function createDomain(slug: string): Promise<DomainInfo[]> {
  return invoke<DomainInfo[]>("wiki_create_domain", { slug });
}

export async function deleteDomain(slug: string): Promise<DomainDeleteResult> {
  return invoke<DomainDeleteResult>("wiki_delete_domain", { slug });
}

export async function exportGlossary(domain: string, format: CatGlossaryFormat): Promise<GlossaryExportResult> {
  const raw = await invoke<string>("wiki_export_glossary", { domain, format });
  return JSON.parse(raw);
}

export async function importGlossary(
  domain: string,
  format: CatGlossaryFormat,
  inputPath: string,
  mode: CatImportMode = "candidates"
): Promise<GlossaryImportResult> {
  const raw = await invoke<string>("wiki_import_glossary", { domain, format, inputPath, mode });
  return JSON.parse(raw);
}

export async function listSharedPacks(): Promise<SharedPackInfo[]> {
  return invoke<SharedPackInfo[]>("wiki_list_shared_packs");
}

export async function installSharedPack(request: SharedPackInstallRequest): Promise<SharedPackInfo> {
  return invoke<SharedPackInfo>("wiki_install_shared_pack", { request });
}

export async function removeSharedPack(id: string): Promise<SharedPackInfo[]> {
  return invoke<SharedPackInfo[]>("wiki_remove_shared_pack", { id });
}
