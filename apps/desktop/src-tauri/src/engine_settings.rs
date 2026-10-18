use serde::{Deserialize, Serialize};
use std::{fs, path::{Path, PathBuf}, process::Command, time::{SystemTime, UNIX_EPOCH}};

pub const DEFAULT_MODEL: &str = "gemini-2.5-flash-lite";
const MODELS: &[&str] = &[DEFAULT_MODEL, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"];

#[derive(Serialize, Deserialize)]
struct StoredSettings {
    model: String,
    #[serde(default)]
    encrypted_api_key: Option<Vec<u8>>,
}

#[derive(Serialize, Clone)]
pub struct EngineSettingsView {
    pub provider: &'static str,
    pub model: String,
    pub has_api_key: bool,
    pub has_saved_key: bool,
    pub key_source: &'static str,
}

#[derive(Deserialize)]
pub struct SaveEngineSettingsRequest {
    pub model: String,
    pub api_key: Option<String>,
}

pub struct Credentials {
    pub model: String,
    pub api_key: String,
}

fn path(root: &Path) -> PathBuf { root.join("engine-settings.json") }

fn validate_model(model: &str) -> Result<(), String> {
    if MODELS.contains(&model) { Ok(()) }
    else { Err("[QDT_GEMINI_MODEL] 지원하는 Flash-Lite 모델을 선택하세요.".into()) }
}

fn read(root: &Path) -> Result<Option<StoredSettings>, String> {
    let target = path(root);
    if !target.exists() { return Ok(None); }
    let bytes = fs::read(target).map_err(|_| "[QDT_SETTINGS_READ] API 설정을 읽지 못했습니다.")?;
    if bytes.len() > 131_072 { return Err("[QDT_SETTINGS_READ] API 설정 파일이 올바르지 않습니다.".into()); }
    let saved: StoredSettings = serde_json::from_slice(&bytes)
        .map_err(|_| "[QDT_SETTINGS_READ] API 설정 파일을 읽을 수 없습니다. 설정을 다시 저장하세요.")?;
    validate_model(&saved.model)?;
    Ok(Some(saved))
}

fn write(root: &Path, saved: &StoredSettings) -> Result<(), String> {
    fs::create_dir_all(root).map_err(|_| "[QDT_SETTINGS_WRITE] API 설정 폴더를 만들지 못했습니다.")?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|_| "Clock error")?.as_nanos();
    let temporary = root.join(format!(".engine-settings-{stamp}.tmp"));
    let bytes = serde_json::to_vec(saved).map_err(|_| "[QDT_SETTINGS_WRITE] API 설정을 저장하지 못했습니다.")?;
    fs::write(&temporary, bytes).map_err(|_| "[QDT_SETTINGS_WRITE] API 설정을 저장하지 못했습니다.")?;
    fs::rename(&temporary, path(root)).map_err(|_| "[QDT_SETTINGS_WRITE] API 설정 교체에 실패했습니다.")?;
    Ok(())
}

#[cfg(windows)]
pub(crate) fn protect_bytes(bytes: &[u8], encrypt: bool) -> Result<Vec<u8>, String> {
    use windows_sys::Win32::{Foundation::LocalFree, Security::Cryptography::{
        CryptProtectData, CryptUnprotectData, CRYPT_INTEGER_BLOB, CRYPTPROTECT_UI_FORBIDDEN,
    }};
    let input = CRYPT_INTEGER_BLOB { cbData: bytes.len() as u32, pbData: bytes.as_ptr() as *mut u8 };
    let mut output = CRYPT_INTEGER_BLOB { cbData: 0, pbData: std::ptr::null_mut() };
    let success = unsafe {
        if encrypt {
            CryptProtectData(&input, std::ptr::null(), std::ptr::null(), std::ptr::null(),
                std::ptr::null(), CRYPTPROTECT_UI_FORBIDDEN, &mut output)
        } else {
            CryptUnprotectData(&input, std::ptr::null_mut(), std::ptr::null(), std::ptr::null(),
                std::ptr::null(), CRYPTPROTECT_UI_FORBIDDEN, &mut output)
        }
    };
    if success == 0 {
        return Err("[QDT_KEY_PROTECTION] 이 Windows 계정에서 키를 보호하거나 읽지 못했습니다. API 키를 다시 저장하세요.".into());
    }
    let result = unsafe {
        let value = std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec();
        LocalFree(output.pbData.cast());
        value
    };
    Ok(result)
}

#[cfg(not(windows))]
pub(crate) fn protect_bytes(_: &[u8], _: bool) -> Result<Vec<u8>, String> {
    Err("[QDT_KEY_PROTECTION] 저장된 API 키는 Windows에서만 지원합니다.".into())
}

fn environment_key() -> Option<String> {
    ["GOOGLE_API_KEY", "GEMINI_API_KEY"].iter()
        .filter_map(|name| std::env::var(name).ok())
        .find(|value| !value.trim().is_empty())
}

fn model_for(saved: Option<&StoredSettings>) -> Result<String, String> {
    let model = saved.map(|value| value.model.clone())
        .or_else(|| std::env::var("QDT_GEMINI_MODEL").ok())
        .unwrap_or_else(|| DEFAULT_MODEL.into());
    validate_model(&model)?;
    Ok(model)
}

fn credentials_with_environment(root: &Path, inherited_key: Option<String>) -> Result<Credentials, String> {
    let saved = read(root)?;
    let model = model_for(saved.as_ref())?;
    let api_key = if let Some(encrypted) = saved.as_ref().and_then(|value| value.encrypted_api_key.as_ref()) {
        String::from_utf8(protect_bytes(encrypted, false)?)
            .map_err(|_| "[QDT_KEY_PROTECTION] 저장된 키를 읽지 못했습니다.")?
    } else {
        inherited_key.unwrap_or_default()
    };
    if api_key.trim().is_empty() {
        return Err("[QDT_GEMINI_KEY_MISSING] 설정에서 Gemini API 키를 저장하세요.".into());
    }
    Ok(Credentials { model, api_key })
}

pub fn credentials_at(root: &Path) -> Result<Credentials, String> {
    credentials_with_environment(root, environment_key())
}

pub fn view_at(root: &Path) -> Result<EngineSettingsView, String> {
    let saved = read(root)?;
    let has_saved_key = saved.as_ref().is_some_and(|value| value.encrypted_api_key.is_some());
    let inherited = environment_key().is_some();
    Ok(EngineSettingsView {
        provider: "Gemini Developer API",
        model: model_for(saved.as_ref())?,
        has_api_key: has_saved_key || inherited,
        has_saved_key,
        key_source: if has_saved_key { "saved" } else if inherited { "environment" } else { "none" },
    })
}

pub fn save_at(root: &Path, request: SaveEngineSettingsRequest) -> Result<EngineSettingsView, String> {
    validate_model(&request.model)?;
    let previous = match read(root) {
        Ok(value) => value,
        Err(error) if request.api_key.is_some() => {
            let supplied=request.api_key.as_deref().unwrap_or("").trim();
            if supplied.len()<16 || supplied.len()>8192 || !supplied.is_ascii() || supplied.chars().any(char::is_whitespace) {return Err(error);}
            let stamp=SystemTime::now().duration_since(UNIX_EPOCH).map_err(|_|"Clock error")?.as_nanos();
            fs::copy(path(root),root.join(format!("engine-settings-damaged-{stamp}.json")))
                .map_err(|_|"[QDT_SETTINGS_WRITE] 손상된 설정의 백업을 만들지 못했습니다.")?;
            None
        }
        Err(error) => return Err(error),
    };
    let mut saved = previous.unwrap_or(StoredSettings { model: DEFAULT_MODEL.into(), encrypted_api_key: None });
    saved.model = request.model;
    if let Some(key) = request.api_key {
        let key = key.trim();
        if key.len() < 16 || key.len() > 8192 || !key.is_ascii() || key.chars().any(char::is_whitespace) {
            return Err("[QDT_GEMINI_KEY_FORMAT] API 키의 앞뒤 공백과 값을 확인하세요.".into());
        }
        saved.encrypted_api_key = Some(protect_bytes(key.as_bytes(), true)?);
    }
    write(root, &saved)?;
    view_at(root)
}

pub fn clear_key_at(root: &Path) -> Result<EngineSettingsView, String> {
    let mut saved = read(root)?.unwrap_or(StoredSettings { model: DEFAULT_MODEL.into(), encrypted_api_key: None });
    saved.encrypted_api_key = None;
    write(root, &saved)?;
    view_at(root)
}

pub fn configure_command(root: &Path, command: &mut Command) -> Result<(), String> {
    let credentials = credentials_at(root)?;
    // Settings belong to this child. Never change the host's global environment.
    command.env_remove("GOOGLE_API_KEY")
        .env("GEMINI_API_KEY", credentials.api_key)
        .env("QDT_GEMINI_MODEL", credentials.model);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn root() -> PathBuf {
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let path = std::env::temp_dir().join(format!("qdt-engine-settings-{}-{stamp}", std::process::id()));
        fs::create_dir_all(&path).unwrap();
        path
    }
    fn save(root: &Path, model: &str, key: Option<&str>) {
        save_at(root, SaveEngineSettingsRequest { model: model.into(), api_key: key.map(str::to_owned) }).unwrap();
    }
    #[test]
    fn rejects_unknown_model_before_writing_any_settings() {
        let root = root();
        let result = save_at(&root, SaveEngineSettingsRequest { model: "expensive-model".into(), api_key: None });
        assert!(result.is_err());
        assert!(!path(&root).exists());
    }
    #[cfg(windows)]
    #[test]
    fn key_roundtrip_is_encrypted_and_never_returned_to_frontend() {
        let root = root();
        let key = "TEST-KEY-DO-NOT-EXPOSE";
        save(&root, DEFAULT_MODEL, Some(key));
        assert!(!fs::read_to_string(path(&root)).unwrap().contains(key));
        let view = serde_json::to_string(&view_at(&root).unwrap()).unwrap();
        assert!(!view.contains(key));
        assert!(!view.contains("encrypted_api_key"));
        assert_eq!(credentials_with_environment(&root, None).unwrap().api_key, key);
    }
    #[cfg(windows)]
    #[test]
    fn changing_model_retains_key_across_reloads_and_overrides_environment() {
        let root = root();
        save(&root, DEFAULT_MODEL, Some("TEST-KEY-DO-NOT-EXPOSE"));
        save(&root, "gemini-3.1-flash-lite", None);
        let value = credentials_with_environment(&root, Some("inherited-key".into())).unwrap();
        assert_eq!(value.model, "gemini-3.1-flash-lite");
        assert_eq!(value.api_key, "TEST-KEY-DO-NOT-EXPOSE");
    }
    #[cfg(windows)]
    #[test]
    fn corrupted_ciphertext_is_an_explicit_failure() {
        let root = root();
        write(&root, &StoredSettings { model: DEFAULT_MODEL.into(), encrypted_api_key: Some(vec![1,2,3]) }).unwrap();
        assert!(credentials_with_environment(&root, Some("inherited-key".into())).is_err());
    }
    #[cfg(windows)]
    #[test]
    fn clearing_saved_key_keeps_model_and_does_not_touch_environment() {
        let root = root();
        save(&root, "gemini-3.1-flash-lite", Some("TEST-KEY-DO-NOT-EXPOSE"));
        clear_key_at(&root).unwrap();
        assert_eq!(model_for(read(&root).unwrap().as_ref()).unwrap(), "gemini-3.1-flash-lite");
        assert!(credentials_with_environment(&root, None).is_err());
        assert_eq!(credentials_with_environment(&root, Some("inherited-key".into())).unwrap().api_key, "inherited-key");
    }
    #[test]
    fn malformed_file_is_not_silently_replaced() {
        let root = root();
        fs::write(path(&root), "{broken-json").unwrap();
        assert!(view_at(&root).is_err());
        assert_eq!(fs::read_to_string(path(&root)).unwrap(), "{broken-json");
    }
    #[cfg(windows)]
    #[test]
    fn explicit_new_key_recovers_corrupt_settings_and_keeps_backup() {
        let root=root();
        fs::write(path(&root),"{broken-json").unwrap();
        assert!(save_at(&root,SaveEngineSettingsRequest{model:DEFAULT_MODEL.into(),api_key:None}).is_err());
        save(&root,DEFAULT_MODEL,Some("TEST-KEY-DO-NOT-EXPOSE"));
        assert_eq!(credentials_with_environment(&root,None).unwrap().api_key,"TEST-KEY-DO-NOT-EXPOSE");
        let backups:Vec<_>=fs::read_dir(&root).unwrap().flatten().filter(|e|e.file_name().to_string_lossy().starts_with("engine-settings-damaged-")).collect();
        assert_eq!(backups.len(),1);
        assert_eq!(fs::read_to_string(backups[0].path()).unwrap(),"{broken-json");
    }

}
