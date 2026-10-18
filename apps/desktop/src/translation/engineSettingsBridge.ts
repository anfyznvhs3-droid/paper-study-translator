import { invoke } from "@tauri-apps/api/core";
export interface EngineSettings {
  provider: string; model: string; has_api_key: boolean; has_saved_key: boolean;
  key_source: "saved" | "environment" | "none";
}
export interface EngineConnectionResult { ok: boolean; model: string; message: string }
export const geminiModels = [
  { id: "gemini-2.5-flash-lite", name: "Gemini 2.5 Flash-Lite", input: "0.10", output: "0.40", note: "가장 낮은 단가입니다. 신규 프로젝트에서는 접근이 제한될 수 있으므로 연결 확인이 필요합니다." },
  { id: "gemini-3.1-flash-lite", name: "Gemini 3.1 Flash-Lite", input: "0.25", output: "1.50", note: "2.5 모델에 접근할 수 없을 때 직접 선택할 수 있습니다." },
  { id: "gemini-3.5-flash-lite", name: "Gemini 3.5 Flash-Lite", input: "0.30", output: "2.50", note: "선택한 모델로만 요청합니다. 다른 모델로 자동 전환하지 않습니다." }
] as const;
export const getEngineSettings = () => invoke<EngineSettings>("get_engine_settings");
export const saveEngineSettings = (model: string, apiKey?: string) =>
  invoke<EngineSettings>("save_engine_settings", { request: { model, api_key: apiKey || null } });
export const clearEngineApiKey = () => invoke<EngineSettings>("clear_engine_api_key");
export const testEngineConnection = () => invoke<EngineConnectionResult>("test_engine_connection");
