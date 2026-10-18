import type { ThemeTokens } from "../theme/themeOptions";
const STORAGE_KEY = "qdt-settings";

export interface PersistedSettings {
  translationMode?: string;
  engine?: string;
  outputMode?: string;
  reviewMode?: string;
  quality?: string;
  themePreset?: string;
  darkPreset?: string;
  customTheme?: Partial<ThemeTokens>;
  darkMode?: boolean;
  domain?: string;
  sharedKnowledgeEnabled?: boolean;
  sharedKnowledgeManifestUrl?: string;
}

export function validateSettings(value: unknown): PersistedSettings {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const source = value as Record<string,unknown>;
  const clean: Record<string,unknown> = {};
  const enums: Record<string,readonly string[]> = {
    translationMode:["agent","machine","manual"],
    engine:["codex-agent","claude-code-agent","gemini-flash-lite","manual-fill"],
    outputMode:["mono","dual"], reviewMode:["on","off"], quality:["true","realistic","complete"],
    themePreset:["soft-pink","rosy-purple","lavender","custom"], darkPreset:["soft-pink","rosy-purple","lavender","custom"]
  };
  for (const [key,values] of Object.entries(enums)) {
    if (typeof source[key] === "string" && values.includes(source[key] as string)) clean[key]=source[key];
  }
  // Retired web provider: migrate preferences without invalidating saved reviews.
  if (source.engine === "google-translate-draft") clean.engine = "gemini-flash-lite";
  for (const key of ["darkMode","sharedKnowledgeEnabled"]) if (typeof source[key] === "boolean") clean[key]=source[key];
  if (typeof source.domain === "string" && /^[a-z0-9][a-z0-9-]{0,63}$/.test(source.domain)) clean.domain=source.domain;
  if (source.customTheme && typeof source.customTheme === "object" && !Array.isArray(source.customTheme)) {
    const theme:Record<string,string>={};
    const allowed=["background","surface","surfaceStrong","surfaceHover","surfaceSelected","border","borderStrong","text","muted","primary","accent","nav","focus","gradientStart","gradientEnd","sideStart","sideEnd"];
    for(const [key,color] of Object.entries(source.customTheme)) {
      if(allowed.includes(key) && typeof color==="string" && /^(#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?|hsl\([\d.\s%,-]+\)|rgb\([\d.\s%,]+\))$/.test(color)) theme[key]=color;
    }
    clean.customTheme=theme;
  }
  return clean as PersistedSettings;
}

export function loadPersistedSettings(): PersistedSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    return validateSettings(JSON.parse(raw));
  } catch {
    return {};
  }
}

export function persistSettings(settings: PersistedSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({...validateSettings(settings),version:1}));
  } catch {
    // localStorage might be full or disabled
  }
}

export function clearPersistedSettings(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
