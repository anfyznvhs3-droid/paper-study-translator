import { installSharedPack, type SharedPackInfo } from "./wikiBridge";

export interface SharedKnowledgePackManifestItem {
  id: string;
  domain: string;
  displayName: string;
  version: string;
  format: "qdt-glossary-csv";
  glossaryUrl: string;
  sha256: string;
  terms: number;
}

export interface SharedKnowledgeManifest {
  schemaVersion: 1;
  generatedAt: string;
  packs: SharedKnowledgePackManifestItem[];
}

export const DEFAULT_SHARED_KNOWLEDGE_MANIFEST_URL = "https://quality-doc-translator.github.io/shared-packs/manifest.json";

export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export function validateManifest(value: unknown): SharedKnowledgeManifest {
  if (!value || typeof value !== "object") {
    throw new Error("공식 공유팩 목록 형식이 올바르지 않습니다.");
  }

  const manifest = value as Partial<SharedKnowledgeManifest>;
  if (manifest.schemaVersion !== 1 || !Array.isArray(manifest.packs)) {
    throw new Error("지원하지 않는 공식 공유팩 목록입니다.");
  }

  for (const pack of manifest.packs) {
    if (
      !pack ||
      typeof pack.id !== "string" ||
      typeof pack.domain !== "string" ||
      typeof pack.displayName !== "string" ||
      typeof pack.version !== "string" ||
      pack.format !== "qdt-glossary-csv" ||
      typeof pack.glossaryUrl !== "string" ||
      typeof pack.sha256 !== "string" ||
      typeof pack.terms !== "number"
    ) {
      throw new Error("공식 공유팩 항목 형식이 올바르지 않습니다.");
    }
  }

  return manifest as SharedKnowledgeManifest;
}

export async function fetchOfficialSharedPacks(
  manifestUrl: string = DEFAULT_SHARED_KNOWLEDGE_MANIFEST_URL,
  fetcher: typeof fetch = fetch
): Promise<SharedPackInfo[]> {
  const manifestResponse = await fetcher(manifestUrl);
  if (!manifestResponse.ok) {
    throw new Error(`공식 공유팩 목록을 받을 수 없습니다: ${manifestResponse.status}`);
  }

  const manifest = validateManifest(await manifestResponse.json());
  const installed: SharedPackInfo[] = [];

  for (const pack of manifest.packs) {
    const glossaryResponse = await fetcher(pack.glossaryUrl);
    if (!glossaryResponse.ok) {
      throw new Error(`공식 공유팩을 받을 수 없습니다: ${pack.displayName}`);
    }

    const glossaryCsv = await glossaryResponse.text();
    const digest = await sha256Hex(glossaryCsv);
    if (digest.toLowerCase() !== pack.sha256.trim().toLowerCase()) {
      throw new Error(`공식 공유팩 무결성 확인 실패: ${pack.displayName}`);
    }

    installed.push(
      await installSharedPack({
        id: pack.id,
        domain: pack.domain,
        displayName: pack.displayName,
        version: pack.version,
        sha256: pack.sha256,
        terms: pack.terms,
        glossaryCsv
      })
    );
  }

  return installed;
}
