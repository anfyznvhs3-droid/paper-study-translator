use std::{fs, path::{Path, PathBuf}, sync::atomic::{AtomicBool, Ordering}};
static ACTIVE: AtomicBool = AtomicBool::new(false);
#[cfg(test)]
pub static TEST_JOB_LOCK:std::sync::Mutex<()> = std::sync::Mutex::new(());
static CANCELLED: AtomicBool = AtomicBool::new(false);

pub struct JobGuard;
impl JobGuard {
    pub fn acquire() -> Result<Self, String> {
        ACTIVE.compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| "[QDT_JOB_BUSY] 이미 번역 작업이 실행 중입니다.".to_string())?;
        CANCELLED.store(false, Ordering::SeqCst);
        Ok(Self)
    }
}
impl Drop for JobGuard {
    fn drop(&mut self) {
        CANCELLED.store(false, Ordering::SeqCst);
        ACTIVE.store(false, Ordering::SeqCst);
    }
}
pub fn cancel() -> bool {
    if !ACTIVE.load(Ordering::SeqCst) { return false; }
    CANCELLED.store(true, Ordering::SeqCst);
    true
}
pub fn active() -> bool { ACTIVE.load(Ordering::SeqCst) }
pub fn cancelled() -> bool { ACTIVE.load(Ordering::SeqCst) && CANCELLED.load(Ordering::SeqCst) }

pub fn reserve_directory(base: &Path, label: &str) -> Result<PathBuf, String> {
    fs::create_dir_all(base).map_err(|_| "[QDT_OUTPUT_CREATE] 출력 폴더를 만들지 못했습니다.")?;
    let safe: String = label.chars().map(|c| if c.is_control() || r#"<>:"/\|?*"#.contains(c) { '_' } else { c }).take(120).collect();
    let safe = safe.trim_matches([' ', '.']);
    let safe = if safe.is_empty() { "QDT-Run" } else { safe };
    for number in 1..10_000 {
        let candidate = base.join(if number == 1 { safe.into() } else { format!("{safe}-{number}") });
        match fs::create_dir(&candidate) {
            Ok(()) => {
                fs::write(candidate.join(".qdt-output"), b"QDT generated output v1\n")
                    .map_err(|_| "[QDT_OUTPUT_CREATE] 출력 폴더 표식을 저장하지 못했습니다.")?;
                return Ok(candidate);
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(_) => return Err("[QDT_OUTPUT_CREATE] 새 출력 폴더를 만들지 못했습니다. 기존 결과는 보존했습니다.".into()),
        }
    }
    Err("[QDT_OUTPUT_COLLISION] 기존 출력과 겹쳐 저장하지 못했습니다.".into())
}

pub fn generated_directory(path: &Path) -> bool {
    let name = path.file_name().and_then(|v| v.to_str()).unwrap_or("").to_ascii_lowercase();
    matches!(name.as_str(), "qdt_output" | ".qdt-agent" | ".qdt-home") || path.join(".qdt-output").exists()
}
pub fn linked(path: &Path) -> bool {
    let Ok(meta) = fs::symlink_metadata(path) else { return true };
    meta.file_type().is_symlink()
}
pub fn validate_engine(engine: &str, mode: &str) -> Result<(), String> {
    if engine == "antigravity-agent" {
        return Err("[QDT_ENGINE_UNAVAILABLE] Antigravity 연결은 구현되지 않았습니다. CODEX 또는 CLAUDE CODE를 직접 선택하세요. 다른 제공자로 전환하지 않습니다.".into());
    }
    let valid = match mode {
        "agent" => matches!(engine, "codex-agent" | "claude-code-agent"),
        "machine" => matches!(engine, "gemini-flash-lite"),
        "manual" => engine == "manual-fill",
        _ => false,
    };
    if valid { Ok(()) } else { Err("[QDT_ENGINE_SELECTION] 번역 방식과 엔진 설정을 다시 선택하세요.".into()) }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};
    fn root() -> PathBuf {
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("qdt-safe-output-{}-{stamp}",std::process::id()))
    }
    #[test]
    fn concurrent_output_allocation_keeps_prior_files() {
        let base=root();
        let first=reserve_directory(&base,"same").unwrap();
        fs::write(first.join("result.pdf"),b"prior").unwrap();
        let handles:Vec<_>=(0..12).map(|_|{let base=base.clone();std::thread::spawn(move||reserve_directory(&base,"same").unwrap())}).collect();
        let unique:std::collections::BTreeSet<_>=handles.into_iter().map(|h|h.join().unwrap()).collect();
        assert_eq!(unique.len(),12);
        assert!(!unique.contains(&first));
        assert_eq!(fs::read(first.join("result.pdf")).unwrap(),b"prior");
    }
    #[test]
    fn unsupported_engine_never_falls_back_to_a_different_provider() {
        assert!(validate_engine("antigravity-agent","agent").is_err());
        assert!(validate_engine("unknown","machine").is_err());
        assert!(validate_engine("google-translate-draft","agent").is_err());
        assert!(validate_engine("google-translate-draft","machine").is_err());
        assert!(validate_engine("gemini-flash-lite","machine").is_ok());
    }
    #[test]
    fn cancellation_is_scoped_to_an_active_guard_and_resets_on_drop() {
        let _test=TEST_JOB_LOCK.lock().unwrap();
        assert!(!cancel());
        {
            let _guard=JobGuard::acquire().unwrap();
            assert!(JobGuard::acquire().is_err());
            assert!(cancel());assert!(cancelled());
        }
        assert!(!cancelled());
        let _next=JobGuard::acquire().unwrap();
        assert!(!cancelled());
    }
}
