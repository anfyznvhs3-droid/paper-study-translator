export type ApiSettingsTarget = "key" | "model" | "connection" | "usage";
export interface ApiSettingsRequest { target: ApiSettingsTarget; id: number }
export interface FailureAction { target: ApiSettingsTarget; label: string }

// Only explicit connection/configuration codes lead to API settings.
// Content validation failures must keep users with the document and diagnostics.
export function failureActions(message: string): FailureAction[] {
  const codes = new Set([...message.matchAll(/\[QDT_GEMINI_([A-Z_]+)\]/g)].map(match => match[1]));
  const actions: FailureAction[] = [];
  if (["KEY_MISSING", "AUTH", "ACCESS"].some(code => codes.has(code)))
    actions.push({target: "key", label: "API 키 설정으로 이동"});
  if (codes.has("MODEL") || codes.has("ACCESS"))
    actions.push({target: "model", label: "모델 설정으로 이동"});
  if (codes.has("RATE_LIMITED"))
    actions.push({target: "usage", label: "사용량 한도 확인으로 이동"});
  if (["TIMEOUT", "NETWORK", "CONNECTION"].some(code => codes.has(code)) || message.includes("[QDT_PROCESS_TIMEOUT]"))
    actions.push({target: "connection", label: "API 연결 확인으로 이동"});
  return actions;
}

// Google documentation: https://ai.google.dev/gemini-api/docs/rate-limits
export const geminiRateLimitUrl = "https://aistudio.google.com/rate-limit?timeRange=last-28-days";
