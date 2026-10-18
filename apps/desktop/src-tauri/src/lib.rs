mod review_session;
mod job_control;
mod pdf_delivery;
mod engine_settings;
mod runtime_paths;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::Emitter;

const PYTHON_TIMEOUT_SECS: u64 = 300; // 5 minutes
const AGENT_PIPELINE_TIMEOUT_SECS: u64 = 1200; // 20 minutes
const AGENT_STALL_SECONDS: u64 = 120; // UI warning after 2 minutes without observable batch output
const AGENT_INACTIVITY_CUT_SECONDS: u64 = 360; // pause/resume before the hard timeout; kept ABOVE the Codex per-call cap (300s) so the monitor never cuts a legitimately-running call
const DIRECT_AGENT_BATCH_ITEMS: usize = 32;
const NO_TRANSLATABLE_TASKS_MESSAGE: &str = "번역할 문장이 없습니다.";

/// Per-user writable runtime; QDT_HOME is an explicit development/test override.
fn qdt_runtime_home() -> PathBuf {
    runtime_paths::data_root()
}

fn qdt_runtime_tmp() -> PathBuf {
    let tmp = qdt_runtime_home().join("tmp");
    let _ = fs::create_dir_all(&tmp);
    tmp
}

/// Point a Python child's caches and temp off C:. With `override_home`, `~`
/// itself is relocated (USERPROFILE/HOME), which also moves third-party caches
/// that hardcode `~/.cache` (e.g. babeldoc's `Path.home()/.cache/babeldoc`).
/// Never override home for the Codex agent process — its CLI reads auth from the
/// real user profile.
fn apply_offc_env(command: &mut Command, override_home: bool) {
    let assets = runtime_paths::asset_root();
    let tesseract = assets.join("runtime/tesseract/tesseract.exe");
    if tesseract.is_file() && std::env::var_os("QDT_TESSERACT").is_none() {
        command.env("QDT_TESSERACT", tesseract).env("TESSDATA_PREFIX", assets.join("runtime/tesseract/tessdata"));
    }
    let models = assets.join("runtime/assets");
    if models.is_dir() { command.env("QDT_BUNDLED_ASSETS", models); }
    command.env("PYTHONDONTWRITEBYTECODE", "1").env("QDT_HOME", qdt_runtime_home());
    let home = qdt_runtime_home();
    let cache = home.join(".cache");
    let tmp = home.join("tmp");
    let _ = fs::create_dir_all(&cache);
    let _ = fs::create_dir_all(&tmp);
    command
        .env("XDG_CACHE_HOME", &cache)
        .env("HF_HOME", cache.join("huggingface"))
        .env("TMP", &tmp)
        .env("TEMP", &tmp);
    if override_home {
        command.env("USERPROFILE", &home).env("HOME", &home);
    }
}

fn stop_child_tree(child: &mut std::process::Child) {
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        let _ = Command::new("taskkill.exe").args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(0x08000000)
            .stdout(std::process::Stdio::null()).stderr(std::process::Stdio::null()).status();
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn run_translation_command_with_timeout(command: &mut Command, timeout: Duration) -> Result<(String,String,i32),String> {
    command.env("QDT_CANCELLABLE", "1");
    run_command_with_timeout(command,timeout)
}

fn run_command_with_timeout(
    command: &mut Command,
    timeout: Duration,
) -> Result<(String, String, i32), String> {
    let capture_id = SystemTime::now().duration_since(UNIX_EPOCH).map(|d|d.as_nanos()).unwrap_or(0);
    let cancellable = command.get_envs().any(|(key, value)| key == "QDT_CANCELLABLE" && value.is_some());
    apply_offc_env(command,true);
    let temp_dir = qdt_runtime_tmp();
    let stdout_path = temp_dir.join(format!("qdt-cmd-{}-{capture_id}.stdout",std::process::id()));
    let stderr_path = temp_dir.join(format!("qdt-cmd-{}-{capture_id}.stderr",std::process::id()));
    let stdout_file = fs::File::create(&stdout_path).map_err(|e|e.to_string())?;
    let stderr_file = fs::File::create(&stderr_path).map_err(|e|e.to_string())?;
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command.env("PYTHONIOENCODING","utf-8")
        .stdout(std::process::Stdio::from(stdout_file)).stderr(std::process::Stdio::from(stderr_file))
        .spawn().map_err(|_|"[QDT_PROCESS_START] 번역 프로세스를 실행하지 못했습니다. 실행 환경을 확인하세요.".to_string())?;
    let start=std::time::Instant::now();
    loop {
        if let Some(status)=child.try_wait().map_err(|e|e.to_string())? {
            let _=child.wait();
            let stdout=String::from_utf8_lossy(&fs::read(&stdout_path).unwrap_or_default()).into_owned();
            let mut stderr=String::from_utf8_lossy(&fs::read(&stderr_path).unwrap_or_default()).into_owned();
            if status.success() {
                let _=fs::remove_file(&stdout_path);let _=fs::remove_file(&stderr_path);
            } else {
                stderr.push_str(&format!("\n[QDT_DIAGNOSTICS] 로그: {} / {}",stdout_path.display(),stderr_path.display()));
            }
            return Ok((stdout,stderr,status.code().unwrap_or(-1)));
        }
        let cancelled=cancellable && job_control::cancelled();
        if cancelled || start.elapsed()>=timeout {
            stop_child_tree(&mut child);
            let stdout=String::from_utf8_lossy(&fs::read(&stdout_path).unwrap_or_default()).into_owned();
            let message=if cancelled { "[QDT_CANCELLED] 사용자가 번역을 중지했습니다.".to_string() }
                else {format!("[QDT_PROCESS_TIMEOUT] Process timed out after {} seconds. 응답 대기 시간을 초과했습니다.",timeout.as_secs())};
            return Ok((stdout,format!("{message}\n[QDT_DIAGNOSTICS] 로그: {} / {}",stdout_path.display(),stderr_path.display()),if cancelled {130} else {124}));
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn run_agent_command_with_monitor(
    command: &mut Command,
    timeout: Duration,
    app_handle: &tauri::AppHandle,
    workspace: &Path,
    batch_items: usize,
) -> Result<(String, String, i32), String> {
    let capture_id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or(0);
    apply_offc_env(command, false);
    let temp_dir = qdt_runtime_tmp();
    let stdout_path = temp_dir.join(format!("qdt-agent-{}-{capture_id}.stdout", std::process::id()));
    let stderr_path = temp_dir.join(format!("qdt-agent-{}-{capture_id}.stderr", std::process::id()));
    let stdout_file = fs::File::create(&stdout_path)
        .map_err(|err| format!("Failed to create stdout capture file: {err}"))?;
    let stderr_file = fs::File::create(&stderr_path)
        .map_err(|err| format!("Failed to create stderr capture file: {err}"))?;

    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let mut child = command
        .env("PYTHONIOENCODING", "utf-8")
        .stdout(std::process::Stdio::from(stdout_file))
        .stderr(std::process::Stdio::from(stderr_file))
        .spawn()
        .map_err(|err| format!("Failed to spawn process: {err}"))?;

    let start = std::time::Instant::now();
    let mut last_emit: Option<std::time::Instant> = None;
    loop {
        if job_control::cancelled() {
            stop_child_tree(&mut child);
            let stdout = fs::read(&stdout_path).unwrap_or_default();
            return Ok((String::from_utf8_lossy(&stdout).into_owned(),
                format!("[QDT_CANCELLED] 사용자가 번역을 중지했습니다. 로그: {} / {}", stdout_path.display(), stderr_path.display()),130));
        }
        if let Some(status) = child.try_wait().map_err(|err| err.to_string())? {
            let _ = child.wait();
            let stdout = fs::read(&stdout_path).unwrap_or_default();
            let stderr = fs::read(&stderr_path).unwrap_or_default();
            if status.success() {
                let _ = fs::remove_file(&stdout_path);
                let _ = fs::remove_file(&stderr_path);
            }
            return Ok((
                String::from_utf8_lossy(&stdout).to_string(),
                if status.success() {String::from_utf8_lossy(&stderr).to_string()} else {format!("{}\n[QDT_DIAGNOSTICS] 로그: {} / {}",String::from_utf8_lossy(&stderr),stdout_path.display(),stderr_path.display())},
                status.code().unwrap_or(-1),
            ));
        }

        if last_emit.map_or(true, |instant| instant.elapsed() >= Duration::from_secs(2)) {
            let visible_snapshot = build_agent_progress_snapshot(workspace, &[], batch_items, None);
            emit_agent_progress(app_handle, visible_snapshot);
            last_emit = Some(std::time::Instant::now());

            let batch_snapshot = build_agent_progress_snapshot(workspace, &[], batch_items, None);
            if start.elapsed() >= Duration::from_secs(AGENT_INACTIVITY_CUT_SECONDS)
                && batch_snapshot.last_activity_seconds >= AGENT_INACTIVITY_CUT_SECONDS
            {
                let snapshot = build_agent_progress_snapshot(
                    workspace,
                    &[],
                    batch_items,
                    Some("paused"),
                );
                emit_agent_progress(app_handle, snapshot.clone());
                let stdout = fs::read(&stdout_path).unwrap_or_default();
                stop_child_tree(&mut child);
                // Keep capture for diagnosis.
                
                return Ok((
                    String::from_utf8_lossy(&stdout).to_string(),
                    format!("{}\n로그: {} / {}",format_agent_inactivity_cut_message(&snapshot, AGENT_INACTIVITY_CUT_SECONDS),stdout_path.display(),stderr_path.display()),
                    124,
                ));
            }
        }

        if start.elapsed() >= timeout {
            let snapshot = build_agent_progress_snapshot(
                workspace,
                &[&stdout_path, &stderr_path],
                batch_items,
                Some("paused"),
            );
            emit_agent_progress(app_handle, snapshot.clone());
            let stdout = fs::read(&stdout_path).unwrap_or_default();
            stop_child_tree(&mut child);
            // Keep capture for diagnosis.
            
            return Ok((
                String::from_utf8_lossy(&stdout).to_string(),
                format!("{}\n로그: {} / {}",format_agent_timeout_message(&snapshot, timeout.as_secs()),stdout_path.display(),stderr_path.display()),
                124,
            ));
        }

        std::thread::sleep(Duration::from_millis(200));
    }
}

fn build_agent_progress_snapshot(
    workspace: &Path,
    extra_activity_paths: &[&Path],
    fallback_batch_items: usize,
    forced_health: Option<&str>,
) -> AgentProgressSnapshot {
    let task_count = count_lines(&workspace.join("tasks.jsonl")).unwrap_or(0);
    let batch_dir = workspace.join("agent-batches");
    let completed_batches = count_matching_files(&batch_dir, ".response.txt");
    let latest_prompt = latest_batch_index(&batch_dir, ".prompt.txt").unwrap_or(completed_batches);
    let recent_files = recent_agent_files(&batch_dir, 6);
    let recent_response_preview = latest_agent_response_preview(&batch_dir, 1_200);
    // Number of batches the runner actually created == number of prompt files it
    // wrote. This is authoritative even when batches are balanced by character
    // weight, where a fixed task_count / batch_items estimate would be wrong
    // (e.g. report "1 / 4" while four balanced batches are already done). Fall
    // back to the item-count estimate only before any prompt exists.
    let prompt_count = count_matching_files(&batch_dir, ".prompt.txt");
    let inferred_batch_items = infer_prompt_batch_items(&batch_dir.join("batch-0001.prompt.txt"))
        .unwrap_or(fallback_batch_items.max(1));
    let total_batches = if prompt_count > 0 {
        prompt_count.max(completed_batches)
    } else if task_count > 0 {
        div_ceil(task_count, inferred_batch_items.max(1))
    } else {
        0
    };
    let current_batch = if total_batches > 0 && completed_batches >= total_batches {
        total_batches
    } else if total_batches > 0 {
        latest_prompt.max(completed_batches + 1).min(total_batches)
    } else {
        latest_prompt.max(completed_batches + 1)
    };
    let latest_activity = latest_agent_activity(workspace, extra_activity_paths);
    let last_activity_seconds = latest_activity
        .and_then(|time| SystemTime::now().duration_since(time).ok())
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    let health = forced_health
        .map(|value| value.to_string())
        .unwrap_or_else(|| {
            if last_activity_seconds >= AGENT_STALL_SECONDS {
                "stalled".to_string()
            } else if latest_prompt > completed_batches {
                "waiting".to_string()
            } else {
                "active".to_string()
            }
        });
    let message = format_agent_progress_message(
        &health,
        current_batch,
        total_batches,
        completed_batches,
        last_activity_seconds,
    );

    AgentProgressSnapshot {
        health,
        current_batch,
        total_batches,
        completed_batches,
        last_activity_seconds,
        message,
        workspace: workspace.to_string_lossy().to_string(),
        recent_files,
        recent_response_preview,
    }
}

fn format_agent_progress_message(
    health: &str,
    current_batch: usize,
    total_batches: usize,
    completed_batches: usize,
    last_activity_seconds: u64,
) -> String {
    let total = if total_batches > 0 {
        total_batches.to_string()
    } else {
        "?".to_string()
    };
    match health {
        "paused" => format!(
            "처리 시간이 길어 일시 중단되었습니다. 완료 batch {completed_batches}개가 저장되어 있으며 중간 파일은 보존됩니다. 다시 실행하면 새 작업을 시작합니다."
        ),
        "stalled" => format!(
            "Codex 프로세스는 실행 중이지만 {last_activity_seconds}초 동안 새 활동이 없습니다. 현재 batch {current_batch} / {total}, 완료 batch {completed_batches}개입니다."
        ),
        "waiting" => format!(
            "Codex Agent가 batch {current_batch} / {total} 응답을 생성 중입니다. 완료 batch {completed_batches}개, 마지막 활동 {last_activity_seconds}초 전입니다."
        ),
        _ => format!(
            "Codex Agent 실행 중입니다. 현재 batch {current_batch} / {total}, 완료 batch {completed_batches}개, 마지막 활동 {last_activity_seconds}초 전입니다."
        ),
    }
}

fn format_agent_timeout_message(snapshot: &AgentProgressSnapshot, timeout_seconds: u64) -> String {
    format!(
        "처리 시간이 길어 일시 중단됨: {timeout_seconds}초 제한 도달\n{}\n중간 작업 저장 위치: {}",
        snapshot.message, snapshot.workspace
    )
}

fn format_agent_inactivity_cut_message(snapshot: &AgentProgressSnapshot, inactivity_seconds: u64) -> String {
    format!(
        "새 batch 응답이 {inactivity_seconds}초 동안 생성되지 않아 조기 일시 중단됨\n{}\n중간 작업 저장 위치: {}",
        snapshot.message, snapshot.workspace
    )
}

fn count_lines(path: &Path) -> Option<usize> {
    fs::read_to_string(path).ok().map(|text| text.lines().count())
}

fn count_matching_files(dir: &Path, suffix: &str) -> usize {
    fs::read_dir(dir)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .filter(|entry| entry.file_name().to_string_lossy().ends_with(suffix))
        .count()
}

fn latest_batch_index(dir: &Path, suffix: &str) -> Option<usize> {
    fs::read_dir(dir)
        .ok()?
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let name = entry.file_name().to_string_lossy().to_string();
            if !name.ends_with(suffix) {
                return None;
            }
            parse_batch_index(&name)
        })
        .max()
}

fn parse_batch_index(name: &str) -> Option<usize> {
    let stem = name.split('.').next()?;
    stem.strip_prefix("batch-")?.parse::<usize>().ok()
}

fn infer_prompt_batch_items(path: &Path) -> Option<usize> {
    let text = fs::read_to_string(path).ok()?;
    let input = text.split("INPUT:").nth(1).unwrap_or(&text);
    let count = input.matches("\"id\"").count();
    (count > 0).then_some(count)
}

fn latest_agent_activity(workspace: &Path, extra_paths: &[&Path]) -> Option<SystemTime> {
    let mut latest = modified_time(&workspace.join("tasks.jsonl"));
    let batch_dir = workspace.join("agent-batches");
    if let Ok(entries) = fs::read_dir(&batch_dir) {
        for entry in entries.flatten() {
            latest = max_time(latest, modified_time(&entry.path()));
        }
    }
    for path in extra_paths {
        latest = max_time(latest, modified_time(path));
    }
    latest
}

fn recent_agent_files(batch_dir: &Path, limit: usize) -> Vec<String> {
    let mut files = fs::read_dir(batch_dir)
        .ok()
        .into_iter()
        .flat_map(|entries| entries.filter_map(Result::ok))
        .filter_map(|entry| {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            if !name.starts_with("batch-") {
                return None;
            }
            let modified = modified_time(&path)?;
            Some((modified, name))
        })
        .collect::<Vec<_>>();

    files.sort_by(|left, right| right.0.cmp(&left.0).then_with(|| right.1.cmp(&left.1)));
    files
        .into_iter()
        .take(limit)
        .map(|(_, name)| name)
        .collect()
}

fn latest_agent_response_preview(batch_dir: &Path, limit_chars: usize) -> Option<String> {
    let latest_response = fs::read_dir(batch_dir)
        .ok()?
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            if !name.ends_with(".response.txt") {
                return None;
            }
            let modified = modified_time(&path)?;
            Some((modified, path))
        })
        .max_by(|left, right| left.0.cmp(&right.0))?
        .1;

    let text = fs::read_to_string(latest_response).ok()?;
    Some(text.chars().take(limit_chars).collect())
}

fn modified_time(path: &Path) -> Option<SystemTime> {
    fs::metadata(path).and_then(|metadata| metadata.modified()).ok()
}

fn max_time(left: Option<SystemTime>, right: Option<SystemTime>) -> Option<SystemTime> {
    match (left, right) {
        (Some(a), Some(b)) => Some(a.max(b)),
        (Some(a), None) => Some(a),
        (None, Some(b)) => Some(b),
        (None, None) => None,
    }
}

fn div_ceil(value: usize, divisor: usize) -> usize {
    if value == 0 {
        0
    } else {
        (value + divisor - 1) / divisor
    }
}

#[derive(Serialize, Deserialize, Clone)]
struct TranslateJobRequest {
    files: Vec<String>,
    engine: String,
    mode: String,
    quality: Option<String>,
    output_mode: String,
    review_mode: String,
    output_dir: Option<String>,
    domain: Option<String>,
    shared_knowledge: Option<bool>,
}

#[derive(Serialize)]
struct TranslateJobResult {
    ok: bool,
    message: String,
    output_files: Vec<String>,
    review_items: Vec<ReviewItem>,
    exit_code: i32,
    /// Human-readable failure breakdown (cause + fix) for the result screen. None
    /// on success or when the raw message is already user-facing.
    diagnosis: Option<FailureDiagnosis>,
}

/// User-facing translation of a raw failure into a named cause and a concrete fix.
/// Keeps the project's "name the failure mode" rule on the surface instead of
/// dumping a cryptic engine string like "latin=12591, cjk=735" on the user.
#[derive(Clone, Serialize, PartialEq, Debug)]
struct FailureDiagnosis {
    /// One-line label of WHAT failed (the failure mode), in Korean.
    summary: String,
    /// WHY it happened, in plain language.
    cause: String,
    /// WHAT the user can do about it.
    solution: String,
}

/// Map a finished job's raw error message + exit code to a named diagnosis.
/// Matching is by stable substrings emitted at the failure sites; an unmatched
/// failure falls back to a generic "share the technical detail" diagnosis so the
/// user always gets cause + next step, never a bare engine string.
fn diagnose_failure(message: &str, exit_code: i32) -> Option<FailureDiagnosis> {
    let trimmed = message.trim();
    if trimmed.is_empty() {
        return None;
    }
    // Paused is a user action, not a failure.
    if trimmed.contains("일시 중단") {
        return None;
    }

    if trimmed.contains("[QDT_PROCESS_TIMEOUT]") {
        return Some(FailureDiagnosis {summary:"번역 응답 대기 시간 초과".into(),cause:"제한 시간 안에 번역 프로세스가 끝나지 않았습니다. 생성된 파일과 진단 로그는 보존했습니다.".into(),solution:"출력 폴더와 로그를 확인하고 문서를 나누거나 API 연결을 확인한 뒤 다시 실행하세요.".into()});
    }
    if trimmed.contains("[QDT_GOOGLE_RATE_LIMITED]") {
        return Some(FailureDiagnosis {summary:"Google 웹 번역 요청 제한".into(),cause:"Google 웹 번역이 요청을 제한해 중단됐습니다.".into(),solution:"잠시 기다린 뒤 재시도하거나 설정한 API 엔진을 직접 선택하세요. 다른 제공자로 자동 전환하지 않습니다.".into()});
    }
    if trimmed.contains("[QDT_GEMINI_") {
        // Keep tracebacks/paths in technical details, not the user-facing cause.
        let cases = [
            ("PRESERVATION", "번역 결과의 원문 보존 검사 실패",
             "API 응답은 받았지만 숫자·단위·인용 또는 자리표시자가 원문과 달라 중단했습니다. 원문에 없는 번호를 추가한 답변도 여기에 해당합니다.",
             "앱은 같은 모델로 최대 1회 교정 요청한 뒤 다시 검사합니다. 계속 실패하면 해당 문단을 나누어 재시도하고 기술 상세의 오류 코드를 함께 알려주세요."),
            ("FORMAT", "Gemini 번역 출력 형식 오류",
             "번역 응답에 원문에 없는 JSON 포장 문자나 응답 형식이 포함되어 중단했습니다.",
             "앱은 같은 모델로 최대 1회 교정 요청합니다. 계속되면 기술 상세의 오류 코드를 확인하세요."),
            ("EXPANSION", "번역 대신 추가 설명이 생성됐습니다",
             "Gemini가 짧은 원문에 과도하게 긴 설명을 추가해 중단했습니다.",
             "앱은 같은 모델로 최대 1회 교정 요청합니다. 계속 실패하면 해당 문단을 나누어 다시 실행하세요."),
            ("RATE_LIMITED", "Gemini 사용량 또는 요청 한도 도달",
             "Gemini가 요청 한도 초과 응답을 반환했습니다.",
             "AI Studio에서 선택한 프로젝트와 모델의 사용량 한도를 확인한 뒤 다시 실행하세요. 모델을 자동 변경하지 않습니다."),
            ("KEY_MISSING", "Gemini API 키가 없습니다",
             "번역 프로세스에 사용할 API 키가 설정되지 않았습니다.",
             "설정 → API 및 모델에서 Gemini API 키를 저장하고 연결 확인을 실행하세요."),
            ("AUTH", "Gemini API 키 인증 실패",
             "Gemini가 API 키 인증을 거부했습니다.",
             "설정 → API 및 모델에서 API 키를 확인하고 저장 후 연결 확인을 누르세요."),
            ("ACCESS", "Gemini 접근 권한 없음",
             "저장한 키로 Gemini API 또는 선택 모델에 접근할 수 없습니다.",
             "AI Studio에서 API 키의 프로젝트와 선택 모델 접근 권한을 확인하세요."),
            ("MODEL", "선택한 Gemini 모델을 사용할 수 없습니다",
             "선택 모델을 찾을 수 없거나 이 프로젝트에서 접근할 수 없습니다.",
             "설정 → API 및 모델에서 사용 가능한 모델을 직접 선택하고 연결 확인을 실행하세요. 자동으로 다른 모델을 사용하지 않습니다."),
            ("TIMEOUT", "Gemini 응답 대기 시간 초과",
             "Gemini 응답이 제한 시간 안에 도착하지 않았습니다.",
             "네트워크와 API 연결을 확인한 뒤 재시도하세요. 실패 로그와 기존 산출물은 보존했습니다."),
            ("NETWORK", "Gemini 연결 실패",
             "네트워크 오류로 Gemini에 연결하지 못했습니다.",
             "인터넷 연결과 방화벽을 확인하고 설정의 연결 확인을 실행하세요."),
            ("BLOCKED", "Gemini가 문구 처리를 차단했습니다",
             "Gemini의 처리 제한으로 해당 문구의 번역 응답을 받지 못했습니다.",
             "해당 원문과 기술 상세의 오류 코드를 확인하세요. 차단 응답은 번역 성공으로 처리하지 않습니다."),
            ("TRUNCATED", "Gemini 번역 출력 한도 도달",
             "번역 응답이 출력 길이 제한으로 잘렸습니다.",
             "문서를 더 작은 문단이나 페이지 범위로 나누어 다시 실행하세요."),
        ];
        for (suffix, summary, cause, solution) in cases {
            let code = format!("[QDT_GEMINI_{suffix}]");
            if trimmed.contains(&code) {
                return Some(FailureDiagnosis {
                    summary: summary.into(), cause: format!("{code} {cause}"),
                    solution: solution.into(),
                });
            }
        }
        return Some(FailureDiagnosis {
            summary: "Gemini 번역 응답 처리 실패".into(),
            cause: "Gemini 요청 또는 응답을 정상적으로 처리하지 못했습니다. 오류 코드는 기술 상세에 보존했습니다.".into(),
            solution: "설정의 연결 확인을 실행하고, 반복되면 기술 상세와 진단 로그를 확인하세요. 모델을 자동 변경하지 않습니다.".into(),
        });
    }

    if trimmed.contains("스캔 PDF 또는 이미지 기반") {
        return Some(FailureDiagnosis {
            summary: "스캔/이미지 PDF는 아직 지원하지 않습니다".to_string(),
            cause: "본문이 글자가 아니라 그림(스캔 이미지)으로 들어있는 PDF입니다. 현재 번역기는 글자 레이어가 있는 PDF만 처리합니다.".to_string(),
            solution: "OCR 도구로 텍스트 레이어를 입힌 PDF로 변환한 뒤 다시 시도하세요.".to_string(),
        });
    }

    if trimmed.contains("구형 PowerPoint .ppt") {
        return Some(FailureDiagnosis {
            summary: "구형 PPT 파일은 지원하지 않습니다".to_string(),
            cause: ".ppt는 Office Open XML이 아닌 구형 바이너리 형식이라 현재 PPTX native 경로로 안전하게 수정할 수 없습니다.".to_string(),
            solution: "PowerPoint에서 파일을 .pptx로 저장한 뒤 다시 실행하세요.".to_string(),
        });
    }

    if trimmed == NO_TRANSLATABLE_TASKS_MESSAGE {
        return Some(FailureDiagnosis {
            summary: "번역할 텍스트를 찾지 못했습니다".to_string(),
            cause: "추출 단계에서 번역 대상 문장이 0건이었습니다. 스캔(이미지) PDF이거나 본문이 글자가 아닌 그림으로 들어있는 문서일 수 있습니다.".to_string(),
            solution: "텍스트를 복사할 수 있는(선택 가능한) PDF인지 확인하세요. 스캔 문서라면 OCR로 텍스트 레이어를 먼저 입혀야 합니다.".to_string(),
        });
    }

    if trimmed.contains("mono output validation failed") {
        let is_byproduct = trimmed.contains(".qdt-agent");
        return Some(FailureDiagnosis {
            summary: "번역 결과에 영어가 너무 많습니다".to_string(),
            cause: if is_byproduct {
                "검증이 최종 산출물이 아니라 작업 폴더(.qdt-agent)의 번역 전 임시 파일을 본 것일 수 있습니다(오검증). 또는 표·차트가 많아 본문 외 영어가 다량 남았을 수 있습니다.".to_string()
            } else {
                "번역은 완료됐지만 한글 대비 영어 비율이 검증 기준을 넘었습니다. 표/차트/약어가 많은 문서이거나 일부 구간이 번역되지 않았을 수 있습니다.".to_string()
            },
            solution: "최종 출력 폴더의 -ko-mono.pdf를 직접 열어 실제 번역 품질을 확인하세요. 정상이면 오검증입니다. 영어가 실제로 많으면 도메인/엔진 설정을 확인하고 다시 시도하세요.".to_string(),
        });
    }

    if exit_code == 124 || trimmed.contains("timed out") || trimmed.contains("timeout") {
        return Some(FailureDiagnosis {
            summary: "제한 시간 초과로 중단됐습니다".to_string(),
            cause: "에이전트(번역 엔진) 호출이 시간 안에 끝나지 않았습니다. 문서가 크거나, 네트워크가 느리거나, API 요청이 몰렸을 수 있습니다.".to_string(),
            solution: "다시 시도하세요. 반복되면 동시 실행 수를 낮추거나(QDT_AGENT_BATCH_CONCURRENCY) 문서를 나눠 번역하세요.".to_string(),
        });
    }

    if trimmed.contains("without output files") || trimmed.contains("required output files were not found") {
        return Some(FailureDiagnosis {
            summary: "산출물이 생성되지 않았습니다".to_string(),
            cause: "번역 과정은 끝났지만 출력 폴더에 결과 파일이 만들어지지 않았습니다. 출력 폴더 권한/디스크 공간 문제이거나 렌더 단계가 조용히 실패했을 수 있습니다.".to_string(),
            solution: "출력 폴더에 쓰기 권한과 디스크 여유가 있는지 확인하고 다시 시도하세요.".to_string(),
        });
    }

    // Match real interpreter/dependency failures, NOT just any message that
    // contains the python.exe path (almost every agent failure embeds it). Key
    // on concrete not-found / missing-module signatures.
    if trimmed.contains("ModuleNotFoundError")
        || trimmed.contains("No module named")
        || trimmed.contains("No such file or directory")
        || trimmed.contains("is not recognized")
        || trimmed.contains("cannot find the file")
    {
        return Some(FailureDiagnosis {
            summary: "파이썬 실행 환경 문제".to_string(),
            cause: "번역 엔진을 실행할 파이썬 또는 의존 패키지를 찾지 못했거나 실행에 실패했습니다.".to_string(),
            solution: "프로젝트의 setup.ps1로 .venv를 다시 만들고 의존 패키지를 설치한 뒤 다시 시도하세요.".to_string(),
        });
    }

    // Unknown failure: still give the user a cause line + an action, with the raw
    // message preserved as the technical detail (the frontend shows `message`).
    Some(FailureDiagnosis {
        summary: "예기치 못한 오류로 번역이 실패했습니다".to_string(),
        cause: "자동 분류되지 않은 오류입니다. 아래 기술 상세에 원인 단서가 들어 있습니다.".to_string(),
        solution: "다시 시도해 보고, 반복되면 아래 기술 상세를 개발자에게 공유하세요.".to_string(),
    })
}

#[derive(Clone, Serialize)]
struct ProgressPayload {
    phase: &'static str,
    agent_status: Option<AgentProgressSnapshot>,
}

#[derive(Clone, Debug, Serialize)]
struct AgentProgressSnapshot {
    health: String,
    current_batch: usize,
    total_batches: usize,
    completed_batches: usize,
    last_activity_seconds: u64,
    message: String,
    workspace: String,
    recent_files: Vec<String>,
    recent_response_preview: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct PdfCaptureRequest {
    pdf_path: String,
    page: usize,
}

#[derive(Serialize, Deserialize)]
struct PdfCaptureResult {
    ok: bool,
    message: String,
    page: usize,
    image_path: String,
    data_url: String,
}

#[derive(Serialize, Deserialize)]
struct OpenPathRequest {
    path: String,
}

#[derive(Clone, Debug, Serialize)]
struct ReviewItem {
    #[serde(default)]
    source_path: Option<String>,
    page: usize,
    kind: String,
    severity: String,
    source_text: String,
    translated_text: Option<String>,
    reason: String,
    status: String,
    fitted: Option<bool>,
}

#[derive(Clone, Debug)]
struct MonoOutputQuality {
    latin: usize,
    cjk: usize,
}

impl MonoOutputQuality {
    fn is_acceptable(&self) -> bool {
        if self.cjk < 100 {
            return false;
        }

        let total = (self.latin + self.cjk).max(1) as f64;
        let latin_ratio = self.latin as f64 / total;

        self.latin <= 250
            || latin_ratio <= 0.12
            || (self.cjk >= 3_000 && latin_ratio <= 0.30)
            || (self.cjk >= 5_000 && latin_ratio <= 0.50)
    }
}

#[derive(Clone, Debug)]
struct MixedLanguageInput {
    path: PathBuf,
    report: String,
}

#[derive(Clone, Debug)]
struct PdfProfileStats {
    pages: usize,
    latin: usize,
    cjk: usize,
    image_pages: usize,
    low_text_pages: usize,
    scholarly_score: usize,
}

#[derive(Clone, Debug, PartialEq)]
enum PdfDocumentProfile {
    GeneralText,
    ScholarlyText,
    MixedLanguage,
    ScannedUnsupported,
}

#[derive(Clone, Debug, PartialEq)]
enum TranslationPipeline {
    ScholarTranslator,
    MixedRenderer(Vec<PathBuf>),
    AgentCliRunner,
    PptxNative(Vec<PathBuf>),
}

#[tauri::command]
async fn capture_pdf_page_snapshot(
    request: PdfCaptureRequest,
) -> Result<PdfCaptureResult, String> {
    if request.pdf_path.trim().is_empty() {
        return Err("PDF path is empty".to_string());
    }

    let python_exe =
        std::env::var("SCHOLAR_TRANSLATOR_PYTHON").unwrap_or_else(|_| default_python_exe());
    let pdf_path = request.pdf_path.clone();
    let page = request.page.max(1);

    let (stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking(move || {
        run_pdf_capture_once(&python_exe, &pdf_path, page)
    })
    .await
    .map_err(|err| err.to_string())?
    .map_err(|err| err)?;

    if exit_code != 0 {
        let detail = stderr.trim();
        return Err(if detail.is_empty() {
            "PDF capture failed".to_string()
        } else {
            detail.to_string()
        });
    }

    serde_json::from_str::<PdfCaptureResult>(&stdout).map_err(|err| err.to_string())
}

#[tauri::command]
async fn open_system_path(request: OpenPathRequest) -> Result<(), String> {
    let path = request.path.trim();
    if path.is_empty() {
        return Err("Path is empty".to_string());
    }

    if !Path::new(path).exists() {
        return Err(format!("Path does not exist: {path}"));
    }

    Command::new("explorer")
        .arg(path)
        .spawn()
        .map_err(|err| err.to_string())?;

    Ok(())
}

fn run_pdf_capture_once(
    python_exe: &str,
    pdf_path: &str,
    page: usize,
) -> Result<(String, String, i32), String> {
    let script = r#"
import base64
import json
import pathlib
import sys
import tempfile

import fitz

pdf_path = sys.argv[1]
page_number = max(1, int(sys.argv[2]))
doc = fitz.open(pdf_path)
if doc.page_count == 0:
    raise SystemExit("PDF has no pages")
page_index = min(page_number, doc.page_count) - 1
page = doc.load_page(page_index)
pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
output_dir = pathlib.Path(tempfile.gettempdir()) / "qdt-feedback-captures"
output_dir.mkdir(parents=True, exist_ok=True)
safe_stem = pathlib.Path(pdf_path).stem[:72] or "pdf"
output_path = output_dir / f"{safe_stem}-p{page_index + 1}.png"
pix.save(str(output_path))
raw = output_path.read_bytes()
print(json.dumps({
    "ok": True,
    "message": "PDF page captured",
    "page": page_index + 1,
    "image_path": str(output_path),
    "data_url": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
}, ensure_ascii=False))
"#;

    let (stdout, stderr, exit_code) = run_command_with_timeout(
        Command::new(python_exe)
            .arg("-c")
            .arg(script)
            .arg(pdf_path)
            .arg(page.to_string()),
        Duration::from_secs(PYTHON_TIMEOUT_SECS),
    )?;

    Ok((stdout, stderr, exit_code))
}

fn emit_progress(app_handle: &tauri::AppHandle, phase: &'static str) {
    let _ = app_handle.emit(
        "translation-progress",
        ProgressPayload {
            phase,
            agent_status: None,
        },
    );
}

fn emit_agent_progress(app_handle: &tauri::AppHandle, snapshot: AgentProgressSnapshot) {
    let _ = app_handle.emit(
        "translation-progress",
        ProgressPayload {
            phase: "agent-batch",
            agent_status: Some(snapshot),
        },
    );
}


#[derive(Serialize, Clone)]
struct TargetRunResult {
    source_path: String,
    status: String,
    message: String,
    output_files: Vec<String>,
}
#[derive(Serialize)]
struct BatchJobResult {
    output_dir: String,
    #[serde(flatten)]
    result: TranslateJobResult,
    target_results: Vec<TargetRunResult>,
}
#[tauri::command]
fn cancel_translation_job() -> bool { job_control::cancel() }

#[tauri::command]
async fn run_translation_job(app_handle: tauri::AppHandle, request: TranslateJobRequest) -> Result<BatchJobResult, String> {
    job_control::validate_engine(&request.engine, &request.mode)?;
    if request.files.is_empty() { return Err("[QDT_INPUT_EMPTY] 번역할 입력을 선택하세요.".into()); }
    let _guard = job_control::JobGuard::acquire()?;
    let base = request.output_dir.as_ref().map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| qdt_runtime_home().join("QDT_Output")));
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).map_err(|e|e.to_string())?.as_millis();
    let run_dir = job_control::reserve_directory(&base, &format!("QDT-Run-{stamp}"))?;
    let delivery_dir=run_dir.join("PDF");
    fs::create_dir(&delivery_dir).map_err(|_|"[QDT_OUTPUT_CREATE] PDF 저장 폴더를 만들지 못했습니다.")?;
    let mut targets = Vec::new();
    let mut outputs = Vec::new();
    let mut reviews = Vec::new();
    let mut seen = BTreeSet::new();
    let mut stopped = false;
    let mut failure_message = String::new();
    let mut exit_code = 0;
    for (target_index, source) in request.files.iter().enumerate() {
        if stopped || job_control::cancelled() {
            targets.push(TargetRunResult {source_path:source.clone(),status:"skipped".into(),message:"앞선 작업 중단으로 실행하지 않았습니다.".into(),output_files:Vec::new()});
            continue;
        }
        let _ = app_handle.emit("translation-target",TargetRunResult {source_path:source.clone(),status:"running".into(),message:"입력을 처리하고 있습니다.".into(),output_files:Vec::new()});
        let source_path = Path::new(source);
        let mut documents = collect_files_by_extension(source_path, &["pdf", "pptx", "ppt"]);
        let excluded = base.canonicalize().ok();
        let input_root = source_path.canonicalize().ok();
        documents.retain(|path| {
            let canonical = path.canonicalize().ok();
            if canonical.is_none() { return false; }
            if source_path.is_dir() && excluded != input_root
                && excluded.as_ref().is_some_and(|output|canonical.as_ref().unwrap().starts_with(output)) { return false; }
            seen.insert(canonical.unwrap())
        });
        documents.sort();
        let mut target_outputs = Vec::new();
        let mut target_status = "success";
        let mut target_message = "번역이 완료되었습니다.".to_string();
        if documents.is_empty() {
            target_status = "failure";
            target_message = "[QDT_INPUT_EMPTY] 처리할 PDF/PPTX가 없거나 다른 선택과 중복됩니다.".into();
            exit_code = -2;
        }
        for (document_index, document) in documents.iter().enumerate() {
            if job_control::cancelled() {
                target_status = "cancelled"; target_message = "[QDT_CANCELLED] 사용자가 번역을 중지했습니다.".into(); exit_code = 130; break;
            }
            let file_dir = job_control::reserve_directory(&run_dir,&format!("input-{}-{}",target_index+1,document_index+1))?;
            let mut single = request.clone();
            single.files = vec![document.to_string_lossy().into_owned()];
            single.output_dir = Some(file_dir.to_string_lossy().into_owned());
            let outcome = run_translation_input(app_handle.clone(),single).await;
            match outcome {
                Ok(mut result) => {
                    for item in &mut result.review_items { item.source_path = Some(document.to_string_lossy().into_owned()); }
                    target_outputs.extend(result.output_files);
                    reviews.extend(result.review_items);
                    if !result.ok {
                        target_outputs.extend(scan_recent_artifact_outputs(&file_dir.to_string_lossy(),UNIX_EPOCH));
                        target_status = if job_control::cancelled() { "cancelled" } else { "failure" };
                        target_message = result.message;
                        exit_code = result.exit_code;
                        break;
                    }
                }
                Err(error) => {
                    target_outputs.extend(scan_recent_artifact_outputs(&file_dir.to_string_lossy(),UNIX_EPOCH));
                    target_status = if job_control::cancelled() { "cancelled" } else { "failure" };
                    target_message = error;
                    exit_code = if job_control::cancelled() {130} else {-1};
                    break;
                }
            }
        }
        target_outputs = deduplicate_existing_outputs(target_outputs);
        let (published,publish_errors)=pdf_delivery::publish_pdfs(&run_dir,target_outputs);
        target_outputs=published;
        if !publish_errors.is_empty() {
            target_status="failure";target_message=publish_errors.join("\n");exit_code=-3;
        } else if target_status=="success" && target_outputs.is_empty() {
            target_status="failure";target_message="[QDT_PDF_MISSING] PDF 결과가 생성되지 않았습니다. 중간 파일은 작업 폴더에 보존했습니다.".into();exit_code=-3;
        }
        outputs.extend(target_outputs.clone());
        if target_status != "success" {
            stopped = true;
            failure_message = target_message.clone();
        }
        let target = TargetRunResult {source_path:source.clone(),status:target_status.into(),message:target_message,output_files:target_outputs};
        let _ = app_handle.emit("translation-target",target.clone());
        targets.push(target);
    }
    let cancelled = job_control::cancelled();
    let ok = !stopped && !cancelled && targets.iter().all(|v|v.status=="success");
    let message = if ok { format!("대상 {}개 번역이 완료되었습니다. 저장 위치: {}",targets.len(),delivery_dir.display()) }
        else if cancelled { "[QDT_CANCELLED] 사용자가 번역을 중지했습니다. 생성된 산출물은 보존했습니다.".into() }
        else { format!("{failure_message}\n생성된 산출물과 중간 작업은 보존했습니다. 저장 위치: {}",run_dir.display()) };
    Ok(BatchJobResult {
        output_dir: delivery_dir.to_string_lossy().into_owned(),
        result:TranslateJobResult {ok,diagnosis:if ok || cancelled {None} else {diagnose_failure(&message,exit_code)},message,
            output_files:deduplicate_existing_outputs(outputs),review_items:reviews,exit_code:if cancelled {130} else {exit_code}},
        target_results:targets,
    })
}
async fn run_translation_input(
    app_handle: tauri::AppHandle,
    request: TranslateJobRequest,
) -> Result<TranslateJobResult, String> {
    if request.files.is_empty() {
        return Err("No files were provided".to_string());
    }

    let python_exe =
        std::env::var("SCHOLAR_TRANSLATOR_PYTHON").unwrap_or_else(|_| default_python_exe());
    let translator_home = std::env::var("SCHOLAR_TRANSLATOR_HOME")
        .unwrap_or_else(|_| default_scholar_translator_home());
    let output_dir = request.output_dir.unwrap_or_else(|| {
        std::env::current_dir()
            .map(|cwd| cwd.to_string_lossy().to_string())
            .unwrap_or_else(|_| translator_home.clone())
    });

    let quality = request
        .quality
        .clone()
        .unwrap_or_else(|| "realistic".to_string());

    if request.mode == "manual" {
        return Ok(TranslateJobResult {
            ok: true,
            message: "Manual mode: translation skipped.".to_string(),
            output_files: Vec::new(),
            review_items: Vec::new(),
            exit_code: 0,
            diagnosis: None,
        });
    }

    let is_machine = request.mode == "machine";
    let is_agent_cli = request.mode == "agent" && is_agent_cli_engine(&request.engine);
    let include_shared = request.shared_knowledge.unwrap_or(false);
    let (service, mut model) = map_engine_to_service(&request.engine);
    if service == "gemini" {
        model = engine_settings::credentials_at(&qdt_runtime_home())?.model;
    }
    let prompt_path = if is_machine || is_agent_cli {
        None
    } else {
        // Agent engines (codex-cli / claude-code-cli) honor this prompt; embed the
        // domain glossary so the user's approved terms apply to the ScholarTranslator
        // path too (dual / non-mixed), not only the MixedRenderer path.
        let glossary_terms = load_runtime_glossary_terms(
            &knowledge_base_root(),
            resolve_domain(request.domain.as_deref()),
            include_shared,
        );
        write_prompt_file(
            &output_dir,
            &quality,
            &request.output_mode,
            &request.review_mode,
            &glossary_terms,
        )?
    };
    let service_flag = if model.is_empty() {
        service.clone()
    } else {
        format!("{service}:{model}")
    };

    emit_progress(&app_handle, "intake");

    if contains_unsupported_ppt(&request.files) {
        let message = "구형 PowerPoint .ppt 파일은 현재 버전에서 지원하지 않습니다. .pptx로 저장한 뒤 다시 실행하세요.".to_string();
        let diagnosis = diagnose_failure(&message, -3);
        return Ok(TranslateJobResult {
            ok: false,
            message,
            output_files: Vec::new(),
            review_items: Vec::new(),
            exit_code: -3,
            diagnosis,
        });
    }

    let pdf_profiles = collect_pdf_document_profiles(&python_exe, &request.files)?;
    let scanned_reports = pdf_profiles
        .iter()
        .filter(|profile| profile.profile == PdfDocumentProfile::ScannedUnsupported)
        .map(|profile| profile.report.as_str())
        .collect::<Vec<_>>();
    if !scanned_reports.is_empty() {
        let message = format!(
            "스캔 PDF 또는 이미지 기반 PDF는 현재 버전에서 지원하지 않습니다. OCR/vision 경로가 필요한 형식입니다. 감지 정보: {}",
            scanned_reports.join("; ")
        );
        let diagnosis = diagnose_failure(&message, -2);
        return Ok(TranslateJobResult {
            ok: false,
            message,
            output_files: Vec::new(),
            review_items: Vec::new(),
            exit_code: -2,
            diagnosis,
        });
    }

    let mixed_inputs = pdf_profiles
        .iter()
        .filter(|profile| profile.profile == PdfDocumentProfile::MixedLanguage)
        .map(|profile| MixedLanguageInput {
            path: profile.path.clone(),
            report: profile.report.clone(),
        })
        .collect::<Vec<_>>();
    let selected_pipeline = select_translation_pipeline_for_inputs(
        &request.mode,
        &request.output_mode,
        &request.engine,
        &request.files,
        mixed_inputs.clone(),
    );

    if let TranslationPipeline::PptxNative(paths) = &selected_pipeline {
        let mut output_files = Vec::new();
        let mut last_stderr = String::new();
        let mut last_exit_code = 0;
        let started_at = SystemTime::now();
        let domain = resolve_domain(request.domain.as_deref()).to_string();
        let glossary = glossary_paths_for_translation(&knowledge_base_root(), &domain, include_shared);
        let pptx_service = if is_agent_cli { "agent" } else if service == "gemini" { "gemini" }
            else { return Err("[QDT_ENGINE_SELECTION] 지원하는 번역 엔진을 다시 선택하세요.".into()); };

        emit_progress(&app_handle, "translate");
        for input_path in paths {
            let args = pptx_native_args(
                &input_path.to_string_lossy(),
                &output_dir,
                &request.output_mode,
                pptx_service,
                &request.engine,
                &quality,
                &request.review_mode,
                &domain,
                glossary.as_deref(),
            );
            let (stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
                let python_exe = python_exe.clone();
                let args = args.clone();
                let use_agent_timeout = pptx_service == "agent" || pptx_service == "gemini";
                move || run_pptx_native_once(&python_exe, args, use_agent_timeout)
            })
            .await
            .map_err(|err| err.to_string())?
            .map_err(|err| err)?;

            if exit_code != 0 {
                last_exit_code = exit_code;
                last_stderr = stderr;
                break;
            }

            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stdout)));
            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stderr)));
            output_files.extend(scan_recent_artifact_outputs(&output_dir, started_at));
        }

        emit_progress(&app_handle, "consistency");
        let mut ok = last_exit_code == 0;
        if ok {
            output_files =
                enforce_output_mode(&output_dir, output_files, &request.output_mode, started_at)?;
        }
        output_files = deduplicate_existing_outputs(output_files);
        ok = ok && !output_files.is_empty();
        let message = if ok {
            "PPTX native pipeline finished successfully".to_string()
        } else if last_stderr.trim().is_empty() {
            format!("PPTX native pipeline finished without output files in {output_dir}")
        } else {
            format!("PPTX native pipeline failed with {python_exe}: {}", last_stderr.trim())
        };
        let diagnosis = if ok {
            None
        } else {
            diagnose_failure(&message, last_exit_code)
        };
        return Ok(TranslateJobResult {
            ok,
            message,
            output_files,
            review_items: Vec::new(),
            exit_code: last_exit_code,
            diagnosis,
        });
    }

    if let TranslationPipeline::AgentCliRunner = selected_pipeline {
        let mut output_files = Vec::new();
        let mut last_stderr = String::new();
        let mut last_exit_code = 0;
        let started_at = SystemTime::now();
        let domain = resolve_domain(request.domain.as_deref()).to_string();
        let glossary = glossary_paths_for_translation(&knowledge_base_root(), &domain, include_shared);

        for input_path in request.files {
            emit_progress(&app_handle, "agent-extract");
            let task_output = agent_task_output_path(&output_dir, &input_path)
                .to_string_lossy()
                .to_string();
            let translation_map = agent_translation_map_path(&output_dir, &input_path)
                .to_string_lossy()
                .to_string();

            let (_stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
                let python_exe = python_exe.clone();
                let translator_home = translator_home.clone();
                let input_path = input_path.clone();
                let task_output = task_output.clone();
                move || {
                    run_scholar_task_extraction_once(
                        &python_exe,
                        &translator_home,
                        &input_path,
                        &task_output,
                    )
                }
            })
            .await
            .map_err(|err| err.to_string())?
            .map_err(|err| err)?;

            if exit_code != 0 {
                last_exit_code = exit_code;
                last_stderr = stderr;
                break;
            }
            if count_lines(Path::new(&task_output)).unwrap_or(0) == 0 {
                last_stderr = NO_TRANSLATABLE_TASKS_MESSAGE.to_string();
                continue;
            }

            emit_progress(&app_handle, "agent-batch");
            let (_stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
                let python_exe = python_exe.clone();
                let engine = request.engine.clone();
                let quality = quality.clone();
                let output_mode = request.output_mode.clone();
                let review_mode = request.review_mode.clone();
                let domain = domain.clone();
                let glossary = glossary.clone();
                let app_handle = app_handle.clone();
                let task_output = task_output.clone();
                let translation_map = translation_map.clone();
                move || {
                    run_agent_translation_map_once(
                        &python_exe,
                        &task_output,
                        &translation_map,
                        &engine,
                        &quality,
                        &output_mode,
                        &review_mode,
                        &domain,
                        glossary.as_deref(),
                        &app_handle,
                    )
                }
            })
            .await
            .map_err(|err| err.to_string())?
            .map_err(|err| err)?;

            if exit_code != 0 {
                last_exit_code = exit_code;
                last_stderr = stderr;
                break;
            }
            if stderr.trim() == NO_TRANSLATABLE_TASKS_MESSAGE {
                last_stderr = stderr.clone();
            }

            emit_progress(&app_handle, "agent-render");
            let (stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
                let python_exe = python_exe.clone();
                let translator_home = translator_home.clone();
                let input_path = input_path.clone();
                let output_dir = output_dir.clone();
                let translation_map = translation_map.clone();
                move || {
                    run_layout_preserved_offline_once(
                        &python_exe,
                        &translator_home,
                        &input_path,
                        &output_dir,
                        &translation_map,
                    )
                }
            })
            .await
            .map_err(|err| err.to_string())?
            .map_err(|err| err)?;

            if exit_code != 0 {
                last_exit_code = exit_code;
                last_stderr = stderr;
                break;
            }

            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stdout)));
            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stderr)));
            output_files.extend(scan_recent_artifact_outputs(&output_dir, started_at));
        }

        emit_progress(&app_handle, "consistency");
        let mut output_files = deduplicate_existing_outputs(output_files);
        let mut ok = last_exit_code == 0;
        if ok {
            output_files =
                enforce_output_mode(&output_dir, output_files, &request.output_mode, started_at)?;
            if let Err(err) = validate_mono_outputs(&python_exe, &output_files, &request.output_mode) {
                ok = false;
                last_stderr = err;
            }
        }
        let review_items = if ok && request.review_mode.eq_ignore_ascii_case("on") {
            collect_review_items_from_outputs(&output_files)
        } else {
            Vec::new()
        };
        let output_files = if request.review_mode.eq_ignore_ascii_case("on") {
            output_files
        } else {
            remove_layout_audit_artifacts(output_files)
        };
        let ok = ok && !output_files.is_empty();
        let message = if ok {
            "agent CLI pipeline finished successfully".to_string()
        } else if last_exit_code == 124 {
            last_stderr.trim().to_string()
        } else if last_stderr.trim() == NO_TRANSLATABLE_TASKS_MESSAGE {
            NO_TRANSLATABLE_TASKS_MESSAGE.to_string()
        } else if last_stderr.trim().is_empty() {
            format!("agent CLI pipeline finished without output files in {output_dir}")
        } else {
            format!("agent CLI pipeline failed with {python_exe}: {}", last_stderr.trim())
        };
        let diagnosis = if ok {
            None
        } else {
            diagnose_failure(&message, last_exit_code)
        };
        return Ok(TranslateJobResult {
            ok,
            message,
            output_files,
            review_items,
            exit_code: last_exit_code,
            diagnosis,
        });
    }

    emit_progress(&app_handle, "extract");
    if let TranslationPipeline::MixedRenderer(paths) = select_translation_pipeline(
        &request.mode,
        &request.output_mode,
        &request.engine,
        mixed_inputs.clone(),
    )
    {
        let mixed_script = default_mixed_renderer_path();
        let mut output_files = Vec::new();
        let mut last_stderr = String::new();
        let mut last_exit_code = 0;
        let started_at = SystemTime::now();

        emit_progress(&app_handle, "translate");
        for input_path in paths {
            let (stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
                let python_exe = python_exe.clone();
                let translator_home = translator_home.clone();
                let mixed_script = mixed_script.clone();
                let output_dir = output_dir.clone();
                let quality = quality.clone();
                let output_mode = request.output_mode.clone();
                let service_flag = service_flag.clone();
                let prompt_path = prompt_path.clone();
                let domain = resolve_domain(request.domain.as_deref()).to_string();
                move || {
                    run_mixed_renderer_once(
                        &python_exe,
                        &translator_home,
                        &mixed_script,
                        &input_path,
                        &output_dir,
                        &quality,
                        &output_mode,
                        &service_flag,
                        prompt_path.as_deref(),
                        &domain,
                        include_shared,
                    )
                }
            })
            .await
            .map_err(|err| err.to_string())?
            .map_err(|err| err)?;

            if exit_code != 0 {
                last_exit_code = exit_code;
                last_stderr = stderr;
                break;
            }

            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stdout)));
            output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stderr)));
            output_files.extend(scan_recent_artifact_outputs(&output_dir, started_at));
        }

        emit_progress(&app_handle, "consistency");
        let reports = mixed_inputs
            .iter()
            .map(|input| input.report.as_str())
            .collect::<Vec<_>>()
            .join("; ");
        let ok = last_exit_code == 0;

        let output_files = deduplicate_existing_outputs(output_files);
        let ok = ok && has_required_mixed_outputs(&output_files);
        let review_items = if ok {
            collect_review_items_from_outputs(&output_files)
        } else {
            Vec::new()
        };

        // .layout-audit.json only feeds the 검수(review) screen. With review
        // mode off that screen never shows, so leaving the file behind just
        // clutters the user's output folder as an unexplained extra "산출물".
        let output_files = if request.review_mode.eq_ignore_ascii_case("on") {
            output_files
        } else {
            remove_layout_audit_artifacts(output_files)
        };

        let message = if ok {
            format!("혼합 언어 PDF를 레이아웃 보존 방식으로 처리했습니다. 감지 정보: {reports}")
        } else {
            let stderr = last_stderr.trim();
            if stderr.is_empty() {
                format!("mixed renderer finished but required output files were not found in {output_dir}")
            } else {
                format!("mixed renderer failed with {python_exe}: {stderr}")
            }
        };
        let diagnosis = if ok {
            None
        } else {
            diagnose_failure(&message, last_exit_code)
        };
        return Ok(TranslateJobResult {
            ok,
            message,
            output_files,
            review_items,
            exit_code: last_exit_code,
            diagnosis,
        });
    }

    let mut output_files = Vec::new();
    let mut last_stderr = String::new();
    let mut last_exit_code = 0;
    let started_at = SystemTime::now();

    // Machine (Google) goes through scholar_translator, which has no glossary
    // hook of its own. When a domain glossary exists, route the job through our
    // wrapper so the default dual / non-mixed path enforces the same terms the
    // MixedRenderer path does. The agent path already applies terms via the
    // prompt, so it stays on the plain CLI (avoids double-substitution).
    let cli_glossary = if is_machine {
        glossary_paths_for_translation(
            &knowledge_base_root(),
            resolve_domain(request.domain.as_deref()),
            include_shared,
        )
    } else {
        None
    };
    let wrapper_script = cli_glossary
        .as_ref()
        .map(|_| default_scholar_glossary_wrapper_path());

    emit_progress(&app_handle, "translate");
    for input_path in request.files {
        let args = base_cli_args(
            &input_path,
            &service_flag,
            &output_dir,
            prompt_path.as_deref(),
            wrapper_script.as_deref(),
        );

        let (stdout, stderr, exit_code) = tauri::async_runtime::spawn_blocking({
            let python_exe = python_exe.clone();
            let translator_home = translator_home.clone();
            let args = args.clone();
            let cli_glossary = cli_glossary.clone();
            move || run_cli_once(&python_exe, &translator_home, args, cli_glossary.as_deref())
        })
        .await
        .map_err(|err| err.to_string())?
        .map_err(|err| err)?;

        if exit_code != 0 {
            last_exit_code = exit_code;
            last_stderr = stderr;
            break;
        }

        output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stdout)));
        output_files.extend(confined_outputs(&output_dir,collect_artifact_outputs(&stderr)));
        output_files.extend(scan_recent_artifact_outputs(&output_dir, started_at));
    }

    emit_progress(&app_handle, "consistency");
    let mut ok = last_exit_code == 0;
    if ok {
        output_files =
            enforce_output_mode(&output_dir, output_files, &request.output_mode, started_at)?;
        if let Err(err) = validate_mono_outputs(&python_exe, &output_files, &request.output_mode) {
            ok = false;
            last_stderr = err;
        }
    }

    let review_items = if ok && request.review_mode.eq_ignore_ascii_case("on") {
        collect_review_items_from_outputs(&output_files)
    } else {
        Vec::new()
    };
    let output_files = if request.review_mode.eq_ignore_ascii_case("on") {
        output_files
    } else {
        remove_layout_audit_artifacts(output_files)
    };

    let message = if ok {
        "scholar-translator finished successfully".to_string()
    } else {
        format!(
            "scholar-translator failed with {python_exe}: {}",
            last_stderr.trim()
        )
    };
    let diagnosis = if ok {
        None
    } else {
        diagnose_failure(&message, last_exit_code)
    };

    Ok(TranslateJobResult {
        ok,
        message,
        output_files,
        review_items,
        exit_code: last_exit_code,
        diagnosis,
    })
}

fn map_engine_to_service(engine: &str) -> (String, String) {
    match engine {
        "codex-agent" => ("codex-cli".to_string(), String::new()),
        "claude-code-agent" => ("claude-code-cli".to_string(), String::new()),
        "antigravity-agent" => ("unsupported".to_string(), String::new()),
        "gemini-flash-lite" => ("gemini".to_string(), std::env::var("QDT_GEMINI_MODEL")
            .unwrap_or_else(|_| "gemini-2.5-flash-lite".to_string())),
        _ => ("unsupported".to_string(), String::new()),
    }
}

fn default_python_exe() -> String {
    if let Some(path) = std::env::var_os("SCHOLAR_TRANSLATOR_PYTHON").filter(|v| !v.is_empty()) {
        return PathBuf::from(path).to_string_lossy().into_owned();
    }
    if let Some(path) = runtime_paths::bundled_python(&runtime_paths::asset_root()) {
        return path.to_string_lossy().into_owned();
    }
    "python".to_string()
}

fn default_scholar_translator_home() -> String {
    runtime_paths::asset_root()
        .join("services")
        .join("scholar-translator")
        .to_string_lossy()
        .to_string()
}

fn default_scholar_glossary_wrapper_path() -> String {
    std::env::var("QDT_SCHOLAR_GLOSSARY_WRAPPER").unwrap_or_else(|_| {
        Path::new(&default_scholar_translator_home())
            .join("qdt_scholar_with_glossary.py")
            .to_string_lossy()
            .to_string()
    })
}

#[derive(Clone, Debug)]
struct PdfDocumentProfileReport {
    path: PathBuf,
    profile: PdfDocumentProfile,
    report: String,
}

fn collect_pdf_document_profiles(
    python_exe: &str,
    input_paths: &[String],
) -> Result<Vec<PdfDocumentProfileReport>, String> {
    let mut profiles = Vec::new();

    for input_path in input_paths {
        let pdf_paths = collect_input_pdfs(Path::new(input_path));
        for pdf_path in pdf_paths {
            let (profile, report) = analyze_pdf_document_profile(python_exe, &pdf_path)?;
            if profile != PdfDocumentProfile::GeneralText {
                profiles.push(PdfDocumentProfileReport {
                    path: pdf_path,
                    profile,
                    report,
                });
            }
        }
    }

    Ok(profiles)
}

fn select_translation_pipeline(
    mode: &str,
    output_mode: &str,
    engine: &str,
    mixed_inputs: Vec<MixedLanguageInput>,
) -> TranslationPipeline {
    if mode.eq_ignore_ascii_case("agent") && is_agent_cli_engine(engine) {
        return TranslationPipeline::AgentCliRunner;
    }

    if output_mode.eq_ignore_ascii_case("mono") && !mixed_inputs.is_empty() {
        return TranslationPipeline::MixedRenderer(
            mixed_inputs.into_iter().map(|input| input.path).collect(),
        );
    }

    TranslationPipeline::ScholarTranslator
}

fn select_translation_pipeline_for_inputs(
    mode: &str,
    output_mode: &str,
    engine: &str,
    input_paths: &[String],
    mixed_inputs: Vec<MixedLanguageInput>,
) -> TranslationPipeline {
    let pptx_paths = input_paths
        .iter()
        .flat_map(|input_path| collect_input_pptx(Path::new(input_path)))
        .collect::<Vec<_>>();
    if !pptx_paths.is_empty() {
        return TranslationPipeline::PptxNative(pptx_paths);
    }

    select_translation_pipeline(mode, output_mode, engine, mixed_inputs)
}

fn is_agent_cli_engine(engine: &str) -> bool {
    matches!(engine, "codex-agent" | "claude-code-agent")
}

fn default_mixed_renderer_path() -> String {
    std::env::var("QDT_MIXED_RENDERER").unwrap_or_else(|_| {
        runtime_paths::asset_root()
            .join("services")
            .join("mixed-renderer")
            .join("qdt_mixed_renderer.py")
            .to_string_lossy()
            .to_string()
    })
}

// Default domain until per-document domain selection (T2.1b) is wired through the request.
const DEFAULT_DOMAIN: &str = "academic";
const SCHOLARLY_PROFILE: &str = "scholarly";

fn resolve_domain<'a>(requested: Option<&'a str>) -> &'a str {
    requested.unwrap_or(DEFAULT_DOMAIN)
}

fn knowledge_base_root() -> PathBuf {
    std::env::var("QDT_KNOWLEDGE_BASE")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            qdt_runtime_home().join("knowledge-base")
        })
}

fn glossary_path_for_domain(kb_root: &Path, slug: &str) -> Option<String> {
    let path = kb_root.join("domains").join(slug).join("glossary.csv");
    if path.is_file() {
        Some(path.to_string_lossy().to_string())
    } else {
        None
    }
}

fn glossary_path_for_profile(kb_root: &Path, profile: &str) -> Option<PathBuf> {
    let path = kb_root.join("profiles").join(profile).join("glossary.csv");
    path.is_file().then_some(path)
}

fn glossary_paths_for_translation(
    kb_root: &Path,
    slug: &str,
    include_shared: bool,
) -> Option<String> {
    let mut paths = Vec::new();
    if let Some(path) = glossary_path_for_profile(kb_root, SCHOLARLY_PROFILE) {
        paths.push(path);
    }
    if include_shared {
        paths.extend(shared_glossary_paths_for_domain(kb_root, slug));
    }
    if let Some(path) = glossary_path_for_domain(kb_root, slug) {
        paths.push(PathBuf::from(path));
    }
    if paths.is_empty() {
        return None;
    }
    std::env::join_paths(paths)
        .ok()
        .map(|joined| joined.to_string_lossy().to_string())
}

fn collect_input_pdfs(input_path: &Path) -> Vec<PathBuf> {
    collect_files_by_extension(input_path, &["pdf"])
}

fn collect_input_pptx(input_path: &Path) -> Vec<PathBuf> {
    collect_files_by_extension(input_path, &["pptx"])
}

fn collect_files_by_extension(input_path: &Path, extensions: &[&str]) -> Vec<PathBuf> {
    if input_path.is_file() || (!input_path.exists() && input_path.extension().is_some()) {
        let ext = input_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        if extensions.iter().any(|allowed| ext == *allowed) {
            return vec![input_path.to_path_buf()];
        }
        return vec![];
    }

    let mut files = Vec::new();
    collect_files_recursive(input_path, extensions, &mut files);
    files
}

fn collect_files_recursive(dir: &Path, extensions: &[&str], files: &mut Vec<PathBuf>) {
    let Ok(root) = dir.canonicalize() else {return};
    let mut visited = BTreeSet::new();
    visit_input_directory(dir,&root,extensions,files,&mut visited);
}
fn visit_input_directory(dir:&Path,root:&Path,extensions:&[&str],files:&mut Vec<PathBuf>,visited:&mut BTreeSet<PathBuf>) {
    if job_control::generated_directory(dir) || job_control::linked(dir) {return;}
    let Ok(canonical)=dir.canonicalize() else {return};
    if !canonical.starts_with(root) || !visited.insert(canonical) {return;}
    let Ok(entries)=fs::read_dir(dir) else {return};
    for entry in entries.flatten() {
        let path=entry.path();
        if job_control::linked(&path) {continue;}
        if path.is_dir() {visit_input_directory(&path,root,extensions,files,visited);}
        else if path.is_file() {
            let ext=path.extension().and_then(|v|v.to_str()).unwrap_or("").to_ascii_lowercase();
            if extensions.contains(&ext.as_str()) {files.push(path);}
        }
    }
}

fn contains_unsupported_ppt(input_paths: &[String]) -> bool {
    input_paths
        .iter()
        .any(|path| collect_files_by_extension(Path::new(path), &["ppt"]).len() > 0)
}

fn analyze_pdf_document_profile(
    python_exe: &str,
    pdf_path: &Path,
) -> Result<(PdfDocumentProfile, String), String> {
    let script = r#"
import re
import sys
from pathlib import Path

import fitz

path = Path(sys.argv[1])
doc = fitz.open(path)
page_texts = [page.get_text("text") for page in doc]
text = "\n".join(page_texts)
latin = len(re.findall(r"[A-Za-z]", text))
cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]", text))
total = max(1, latin + cjk)
image_pages = sum(1 for page in doc if page.get_images(full=True))
low_text_pages = sum(1 for page_text in page_texts if len(page_text.strip()) < 80)
lower = text.lower()
scholarly_score = 0
if re.search(r"doi\.org|10\.\d{4,9}/", lower):
    scholarly_score += 3
if re.search(r"\babstract\b", lower):
    scholarly_score += 2
if re.search(r"\breferences\b", lower):
    scholarly_score += 2
if re.search(r"\bkeywords?\b", lower):
    scholarly_score += 1
if len(re.findall(r"\b(?:fig\.|figure|table)\s*\d+", lower)) >= 3:
    scholarly_score += 1
if re.search(r"\bintroduction\b", lower) and re.search(r"\bconclusions?\b", lower):
    scholarly_score += 1
if re.search(r"[\w.+-]+@[\w.-]+\.\w+", text):
    scholarly_score += 1
two_col_pages = 0
for page in doc:
    words = page.get_text("words") or []
    width = page.rect.width
    left = sum(1 for word in words if word[0] < width * 0.45)
    right = sum(1 for word in words if word[0] > width * 0.55)
    if left > 80 and right > 80:
        two_col_pages += 1
if two_col_pages >= max(2, len(doc) // 3):
    scholarly_score += 2
print(f"{len(doc)}\t{latin}\t{cjk}\t{total}\t{image_pages}\t{low_text_pages}\t{scholarly_score}")
"#;

    let (stdout, stderr, exit_code) = run_translation_command_with_timeout(
        Command::new(python_exe)
            .arg("-c")
            .arg(script)
            .arg(pdf_path),
        Duration::from_secs(PYTHON_TIMEOUT_SECS),
    )?;

    if exit_code != 0 {
        return Err(format!(
            "failed to inspect PDF language mix with {python_exe}: {}",
            stderr.trim()
        ));
    }

    let mut parts = stdout.trim().split('\t');
    let pages = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);
    let latin = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);
    let cjk = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);
    let total = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(1);
    let image_pages = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);
    let low_text_pages = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);
    let scholarly_score = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .unwrap_or(0);

    let stats = PdfProfileStats {
        pages,
        latin,
        cjk,
        image_pages,
        low_text_pages,
        scholarly_score,
    };

    let latin_ratio = latin as f64 / total as f64;
    let cjk_ratio = cjk as f64 / total as f64;
    let profile = classify_pdf_document_profile(&stats);
    let report = format!(
        "{} / pages={}, latin={} ({:.0}%), cjk={} ({:.0}%), image_pages={}, low_text_pages={}, scholarly_score={}",
            pdf_path.display(),
            pages,
            latin,
            latin_ratio * 100.0,
            cjk,
            cjk_ratio * 100.0,
            image_pages,
            low_text_pages,
            scholarly_score
        );

    Ok((profile, report))
}

fn classify_pdf_document_profile(stats: &PdfProfileStats) -> PdfDocumentProfile {
    let text_chars = stats.latin + stats.cjk;
    let pages = stats.pages.max(1);
    let image_heavy = stats.image_pages >= pages.div_ceil(2);
    let mostly_low_text = stats.low_text_pages >= pages.div_ceil(2);

    if text_chars < pages * 80 && (image_heavy || mostly_low_text) {
        return PdfDocumentProfile::ScannedUnsupported;
    }

    if stats.scholarly_score >= 5 {
        return PdfDocumentProfile::ScholarlyText;
    }

    let total = text_chars.max(1) as f64;
    let latin_ratio = stats.latin as f64 / total;
    let cjk_ratio = stats.cjk as f64 / total;
    if stats.latin > 150 && stats.cjk > 150 && latin_ratio > 0.10 && cjk_ratio > 0.10 {
        return PdfDocumentProfile::MixedLanguage;
    }

    PdfDocumentProfile::GeneralText
}

fn collect_artifact_outputs(logs: &str) -> Vec<String> {
    logs.lines()
        .map(str::trim)
        .filter(|line| {
            let lower = line.to_ascii_lowercase();
            lower.ends_with(".pdf")
                || lower.ends_with(".pptx")
                || lower.ends_with(".md")
                || lower.ends_with(".html")
                || lower.ends_with(".json")
        })
        .map(ToString::to_string)
        .collect()
}

fn scan_recent_artifact_outputs(output_dir: &str, started_at: SystemTime) -> Vec<String> {
    let mut outputs = Vec::new();
    collect_recent_artifacts(Path::new(output_dir), started_at, &mut outputs);
    outputs
}

/// The agent workspace `.qdt-agent/<doc>/layout-extract` holds the task-extraction
/// byproduct render, which is intentionally untranslated (it exists only to pull
/// translation tasks). Every recursive output scanner MUST skip it, or the English
/// byproduct is treated as a deliverable and fails mono-output validation even
/// though the real `<output>/<doc>-ko` render is correct. Shared so a new scanner
/// cannot silently reintroduce the `byproduct-validated-as-output` failure mode.
fn is_agent_workspace_dir(path: &Path) -> bool {
    path.file_name().and_then(|name| name.to_str()) == Some(".qdt-agent")
}

fn confined_outputs(root:&str,paths:Vec<String>)->Vec<String> {
    let Ok(root)=Path::new(root).canonicalize() else {return Vec::new()};
    paths.into_iter().filter(|value|Path::new(value).canonicalize().is_ok_and(|path|path.starts_with(&root))).collect()
}
fn collect_recent_artifacts(dir:&Path,started_at:SystemTime,outputs:&mut Vec<String>) {
    collect_recent_outputs(dir,started_at,true,outputs);
}
fn collect_recent_outputs(dir:&Path,started_at:SystemTime,sidecars:bool,outputs:&mut Vec<String>) {
    let Ok(root)=dir.canonicalize() else {return};
    let mut visited=BTreeSet::new();
    visit_recent_outputs(dir,&root,started_at,sidecars,outputs,&mut visited);
}
fn visit_recent_outputs(dir:&Path,root:&Path,started_at:SystemTime,sidecars:bool,outputs:&mut Vec<String>,visited:&mut BTreeSet<PathBuf>) {
    if job_control::linked(dir) {return;}
    let Ok(canonical)=dir.canonicalize() else {return};
    if !canonical.starts_with(root) || !visited.insert(canonical) {return;}
    let Ok(entries)=fs::read_dir(dir) else {return};
    for entry in entries.flatten() {
        let path=entry.path();
        if job_control::linked(&path) {continue;}
        if path.is_dir() {
            if !is_agent_workspace_dir(&path) {visit_recent_outputs(&path,root,started_at,sidecars,outputs,visited);}
            continue;
        }
        let ext=path.extension().and_then(|v|v.to_str()).unwrap_or("");
        let accepted=if sidecars {is_artifact_path(&path)} else {ext.eq_ignore_ascii_case("pdf") || ext.eq_ignore_ascii_case("pptx")};
        if accepted && entry.metadata().and_then(|m|m.modified()).is_ok_and(|modified|is_recent_enough(modified,started_at)) {
            outputs.push(path.to_string_lossy().into_owned());
        }
    }
}

fn is_artifact_path(path: &Path) -> bool {
    let Some(file_name) = path.file_name().and_then(|file_name| file_name.to_str()) else {
        return false;
    };
    let lower = file_name.to_ascii_lowercase();
    lower.ends_with(".pdf")
        || lower.ends_with(".pptx")
        || lower.ends_with(".md")
        || lower.ends_with(".html")
        || lower.ends_with(".layout-audit.json")
}

fn remove_layout_audit_artifacts(paths: Vec<String>) -> Vec<String> {
    paths
        .into_iter()
        .filter(|path| {
            if path.to_ascii_lowercase().ends_with(".layout-audit.json") {
                let _ = fs::remove_file(path);
                false
            } else {
                true
            }
        })
        .collect()
}

fn deduplicate_existing_outputs(paths: Vec<String>) -> Vec<String> {
    deduplicate(paths)
        .into_iter()
        .filter(|path| {
            fs::metadata(path)
                .map(|metadata| metadata.is_file() && metadata.len() > 0)
                .unwrap_or(false)
        })
        .collect()
}

fn has_required_mixed_outputs(paths: &[String]) -> bool {
    let has_pdf = paths
        .iter()
        .any(|path| path.to_ascii_lowercase().ends_with(".pdf"));
    let has_audit = paths
        .iter()
        .any(|path| path.to_ascii_lowercase().ends_with(".layout-audit.json"));
    has_pdf && has_audit
}

fn scan_recent_pdf_outputs(output_dir: &str, started_at: SystemTime) -> Vec<String> {
    let mut outputs = Vec::new();
    collect_recent_pdfs_and_pptx(Path::new(output_dir), started_at, &mut outputs);
    outputs
}

fn collect_recent_pdfs_and_pptx(dir:&Path,started_at:SystemTime,outputs:&mut Vec<String>) {
    collect_recent_outputs(dir,started_at,false,outputs);
}

fn is_recent_enough(modified: SystemTime, started_at: SystemTime) -> bool {
    modified >= started_at
        || started_at
            .duration_since(modified)
            .is_ok_and(|delta| delta <= Duration::from_secs(3))
}

fn enforce_output_mode(
    output_dir: &str,
    output_files: Vec<String>,
    output_mode: &str,
    started_at: SystemTime,
) -> Result<Vec<String>, String> {
    let output_files=confined_outputs(output_dir,output_files);
    let normalized_mode = output_mode.to_ascii_lowercase();
    let (keep_suffixes, remove_suffixes): (&[&str], &[&str]) = match normalized_mode.as_str() {
        "mono" => (&["-mono.pdf", "-mono.pptx"], &["-dual.pdf", "-dual.pptx"]),
        "dual" => (&["-dual.pdf", "-dual.pptx"], &["-mono.pdf", "-mono.pptx"]),
        _ => return Ok(deduplicate(output_files)),
    };

    let recent_outputs = scan_recent_pdf_outputs(output_dir, started_at);
    for path in &recent_outputs {
        let lower = path.to_ascii_lowercase();
        if remove_suffixes.iter().any(|suffix| lower.ends_with(suffix)) {
            fs::remove_file(path)
                .map_err(|err| format!("failed to remove unselected output {path}: {err}"))?;
        }
    }

    let selected = output_files
        .into_iter()
        .chain(recent_outputs)
        .filter(|path| is_selected_mode_artifact(path, keep_suffixes, remove_suffixes))
        .collect();

    Ok(deduplicate_existing_outputs(selected))
}

fn is_selected_mode_artifact(path: &str, keep_suffixes: &[&str], remove_suffixes: &[&str]) -> bool {
    let lower = path.to_ascii_lowercase();

    if keep_suffixes.iter().any(|suffix| lower.ends_with(suffix)) {
        return true;
    }
    if remove_suffixes.iter().any(|suffix| lower.ends_with(suffix)) {
        return false;
    }

    let sidecar_suffixes = [".md", ".html", ".layout-audit.json"];
    let keep_stems = keep_suffixes
        .iter()
        .map(|suffix| suffix.trim_end_matches(".pdf").trim_end_matches(".pptx"))
        .collect::<Vec<_>>();
    let remove_stems = remove_suffixes
        .iter()
        .map(|suffix| suffix.trim_end_matches(".pdf").trim_end_matches(".pptx"))
        .collect::<Vec<_>>();
    keep_stems.iter().any(|stem| {
        sidecar_suffixes
            .iter()
            .any(|suffix| lower.ends_with(&format!("{stem}{suffix}")))
    }) && !remove_stems.iter().any(|stem| {
        sidecar_suffixes
            .iter()
            .any(|suffix| lower.ends_with(&format!("{stem}{suffix}")))
    })
}

fn validate_mono_outputs(
    python_exe: &str,
    output_files: &[String],
    output_mode: &str,
) -> Result<(), String> {
    for path in output_files
        .iter()
        .filter(|path| path.to_ascii_lowercase().ends_with(".pdf"))
    {
        let quality = inspect_pdf_language_quality_mode(python_exe, path, output_mode.eq_ignore_ascii_case("dual"))?;
        if !quality.is_acceptable() {
            return Err(format!(
                "mono output validation failed for {path}: latin={}, cjk={}. The PDF still contains too much English text.",
                quality.latin, quality.cjk
            ));
        }
    }

    Ok(())
}

fn inspect_pdf_language_quality_mode(python_exe: &str, path: &str, dual: bool) -> Result<MonoOutputQuality, String> {
    let script = r#"
import re
import sys

import fitz

doc = fitz.open(sys.argv[1])
dual = sys.argv[2] == "1"
text = "\n".join(page.get_text("text", clip=fitz.Rect(page.rect.width/2,0,page.rect.width,page.rect.height)) if dual else page.get_text("text") for page in doc)
latin = len(re.findall(r"[A-Za-z]", text))
cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]", text))
print(f"{latin}\t{cjk}")
"#;

    let (stdout, stderr, exit_code) = run_translation_command_with_timeout(
        Command::new(python_exe)
            .arg("-c")
            .arg(script)
            .arg(path)
            .arg(if dual { "1" } else { "0" }),
        Duration::from_secs(PYTHON_TIMEOUT_SECS),
    )?;

    if exit_code != 0 {
        return Err(format!(
            "failed to inspect translated PDF output {path}: {}",
            stderr.trim()
        ));
    }

    let mut parts = stdout.trim().split('\t');
    let latin = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .ok_or_else(|| format!("failed to parse mono output latin count for {path}"))?;
    let cjk = parts
        .next()
        .and_then(|part| part.parse::<usize>().ok())
        .ok_or_else(|| format!("failed to parse mono output CJK count for {path}"))?;

    Ok(MonoOutputQuality { latin, cjk })
}

fn deduplicate(paths: Vec<String>) -> Vec<String> {
    BTreeSet::from_iter(paths).into_iter().collect()
}

fn collect_review_items_from_outputs(output_files: &[String]) -> Vec<ReviewItem> {
    let mut items = Vec::new();
    for path in output_files {
        if !path.to_ascii_lowercase().ends_with(".layout-audit.json") {
            continue;
        }

        items.extend(read_review_items_from_audit(Path::new(path)));
    }

    items.sort_by_key(|item| match item.severity.as_str() {
        "blocking" | "error" => 0,
        "warning" => 1,
        _ => 2,
    });
    items
}

fn unreadable_audit_item(path: &Path) -> Vec<ReviewItem> {
    vec![ReviewItem { source_path: None, page: 0,
        kind: "audit_unavailable".to_string(), severity: "error".to_string(),
        source_text: path.to_string_lossy().to_string(), translated_text: None,
        reason: "검수 기록을 읽지 못했습니다. 후보 없음으로 처리하지 않았습니다. 최종 PDF를 확인하고 다시 실행하세요.".to_string(),
        status: "open".to_string(), fitted: None }]
}

fn read_review_items_from_audit(path: &Path) -> Vec<ReviewItem> {
    let Ok(content) = fs::read_to_string(path) else {
        return unreadable_audit_item(path);
    };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(&content) else {
        return unreadable_audit_item(path);
    };
    let Some(pages) = value.get("pages").and_then(|pages| pages.as_array()) else {
        return unreadable_audit_item(path);
    };

    let mut items = Vec::new();
    for page in pages {
        let page_number = page.get("page").and_then(|page| page.as_u64()).unwrap_or(0) as usize;
        let Some(replacements) = page
            .get("replacements")
            .and_then(|replacements| replacements.as_array())
        else {
            continue;
        };

        for replacement in replacements {
            let source_text = replacement
                .get("source_preview")
                .and_then(|s| s.as_str())
                .unwrap_or("")
                .to_string();
            let translated_text = replacement
                .get("translated_preview")
                .and_then(|t| t.as_str())
                .map(|t| t.to_string());
            if source_text.is_empty() && translated_text.as_deref().unwrap_or("").is_empty() {
                continue;
            }

            let fitted = replacement
                .get("fitted")
                .and_then(|f| f.as_bool());
            let reason = replacement
                .get("reason")
                .and_then(|r| r.as_str())
                .map(|r| r.to_string())
                .unwrap_or_else(|| {
                    if fitted == Some(false) {
                        "번역문이 원래 텍스트 박스 안에 전부 들어가지 않습니다.".to_string()
                    } else {
                        "원문과 번역문을 의미 및 레이아웃 기준으로 비교하세요.".to_string()
                    }
                });
            let audit_status = replacement
                .get("status")
                .and_then(|s| s.as_str())
                .unwrap_or("open");
            let kind = replacement
                .get("kind")
                .and_then(|k| k.as_str())
                .unwrap_or(if fitted == Some(false) { "layout_overflow" } else { "term_mismatch" })
                .to_string();
            let severity = replacement
                .get("severity")
                .and_then(|s| s.as_str())
                .unwrap_or(if fitted == Some(false) { "warning" } else { "info" })
                .to_string();

            let status = match audit_status {
                "needs_review" | "candidate" => "open",
                "approved" | "rejected" | "resolved" => audit_status,
                _ => "open",
            };

            items.push(ReviewItem {
                source_path: None,
                page: page_number,
                kind,
                severity,
                source_text,
                translated_text,
                reason,
                status: status.to_string(),
                fitted,
            });
        }
    }

    items
}

fn base_cli_args(
    input_path: &str,
    service_flag: &str,
    output_dir: &str,
    prompt_path: Option<&str>,
    wrapper_script: Option<&str>,
) -> Vec<String> {
    // With a glossary wrapper we run our own script (which monkey-patches the
    // translator, then delegates to scholar_translator.cli). Otherwise invoke the
    // vendored CLI module directly. The argument list after this is identical.
    let mut args = match wrapper_script {
        Some(script) => vec![script.to_string()],
        None => vec!["-m".to_string(), "scholar_translator.cli".to_string()],
    };
    args.extend([
        input_path.to_string(),
        "--lang-out".to_string(),
        "ko".to_string(),
        "--service".to_string(),
        service_flag.to_string(),
        "--output".to_string(),
        output_dir.to_string(),
        "--thread".to_string(),
        if service_flag.starts_with("gemini") { "1" } else { "4" }.to_string(),
    ]);

    if let Some(prompt_path) = prompt_path {
        args.push("--prompt".to_string());
        args.push(prompt_path.to_string());
    }

    if Path::new(input_path).is_dir() {
        args.push("--dir".to_string());
    }

    args
}

fn write_prompt_file(
    output_dir: &str,
    quality: &str,
    output_mode: &str,
    review_mode: &str,
    glossary_terms: &[(String, String)],
) -> Result<Option<String>, String> {
    let dir = PathBuf::from(output_dir);
    fs::create_dir_all(&dir).map_err(|err| err.to_string())?;
    let prompt_path = dir.join("quality_doc_translator_prompt.md");
    let prompt = build_prompt(quality, output_mode, review_mode, glossary_terms);
    fs::write(&prompt_path, prompt).map_err(|err| err.to_string())?;
    Ok(Some(prompt_path.to_string_lossy().to_string()))
}

/// Read one glossary CSV as (source, target) pairs. Returns an empty vec (never
/// errors) when the CSV is missing or unreadable, so a job with no glossary
/// simply omits the section instead of failing.
fn load_glossary_terms_from_path(path: &Path) -> Vec<(String, String)> {
    let Ok(content) = fs::read_to_string(&path) else {
        return Vec::new();
    };

    let mut terms = Vec::new();
    for line in content.lines() {
        let line = line.trim_end_matches('\r');
        if line.trim().is_empty() {
            continue;
        }
        let fields = parse_csv_line(line);
        if fields.len() < 2 {
            continue;
        }
        let source = fields[0].trim();
        let target = fields[1].trim();
        if source.is_empty() || target.is_empty() {
            continue;
        }
        // Skip the header row.
        if source.eq_ignore_ascii_case("source") && target.eq_ignore_ascii_case("target") {
            continue;
        }
        terms.push((source.to_string(), target.to_string()));
    }
    terms
}

fn load_glossary_terms(kb_root: &Path, slug: &str) -> Vec<(String, String)> {
    let Some(path) = glossary_path_for_domain(kb_root, slug) else {
        return Vec::new();
    };
    load_glossary_terms_from_path(Path::new(&path))
}

fn load_runtime_glossary_terms(
    kb_root: &Path,
    slug: &str,
    include_shared: bool,
) -> Vec<(String, String)> {
    let mut terms = Vec::new();
    if let Some(path) = glossary_path_for_profile(kb_root, SCHOLARLY_PROFILE) {
        terms.extend(load_glossary_terms_from_path(&path));
    }
    if include_shared {
        for path in shared_glossary_paths_for_domain(kb_root, slug) {
            terms.extend(load_glossary_terms_from_path(&path));
        }
    }
    if let Some(path) = glossary_path_for_domain(kb_root, slug) {
        terms.extend(load_glossary_terms_from_path(Path::new(&path)));
    }
    terms
}

/// Minimal RFC-4180-ish single-line CSV split: handles quoted fields and
/// doubled-quote escapes. Good enough for the flat `source,target,notes` rows.
fn parse_csv_line(line: &str) -> Vec<String> {
    let mut fields = Vec::new();
    let mut cur = String::new();
    let mut in_quotes = false;
    let mut chars = line.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' => {
                if in_quotes && chars.peek() == Some(&'"') {
                    cur.push('"');
                    chars.next();
                } else {
                    in_quotes = !in_quotes;
                }
            }
            ',' if !in_quotes => {
                fields.push(std::mem::take(&mut cur));
            }
            _ => cur.push(c),
        }
    }
    fields.push(cur);
    fields
}

fn build_prompt(
    quality: &str,
    output_mode: &str,
    review_mode: &str,
    glossary_terms: &[(String, String)],
) -> String {
    let quality_rule = match quality {
        "true" => {
            "Prioritize literal faithfulness. Preserve source sentence force, modal verbs, \
             technical nouns, abbreviations, and requirement strength even when Korean is less fluent."
        }
        "complete" => {
            "Prioritize final-document completeness. Improve Korean readability while preserving \
             every technical meaning, requirement strength, and original abbreviation."
        }
        _ => {
            "Balance source fidelity and practical Korean readability. Keep regulatory language precise \
             and avoid over-localizing technical terms."
        }
    };

    let glossary_block = if glossary_terms.is_empty() {
        String::new()
    } else {
        let mut block = String::from(
            "

User-approved domain glossary (HIGHEST priority — always render the source term \
             exactly as its target, overriding any rule above when they conflict):\n",
        );
        for (source, target) in glossary_terms {
            block.push_str(&format!("- \"{source}\" → \"{target}\"
"));
        }
        block
    };

    format!(
        r#"You are translating English quality, manufacturing, automotive QMS, IATF 16949, FMEA, APQP, control-plan, warranty, audit, and supplier-quality documents into Korean.

Output only the translated Korean text. Do not add explanations.

Quality mode:
{quality_rule}

Required terminology rules:
- Translate "failure mode" as "고장 모드".
- Translate "Foundation FMEA" as "기반(FOUNDATION) FMEA".
- Translate "Field issues" as "현장 이슈".
- Translate "Registration Approval" as "등록 승인".
- Translate "Multi-point Fault/Failure" as "복합 결함".
- For scholarly papers, translate "Abstract" as "초록", not "추상적인".
- For scholarly papers, translate "Nomenclature" as "기호 설명", not "용어".
- In welding papers, translate "resistance projection welding" as "저항 프로젝션 용접".
- In welding papers, translate "pulsed welding current" as "펄스 용접 전류".
- In welding papers, translate "weld rupture force" as "용접부 파단 하중".
- In welding papers, translate "welded joint" as "용접 이음" or "용접부" according to context.
- In welding paper abbreviation sections, keep abbreviations and translate definitions as:
  Upslope: "상승 구간" / "용접 전류 상승 시간(전기공학상 rise time)"
  Downslope: "하강 구간" / "용접 전류 하강 시간(전기공학상 fall time)"
  BWC: "최적 용접 조건"
  TCFT: "총 전류 통전 시간"
  MCPT: "주 전류 구간 시간"
  DCimp: "펄스 직류 용접 전류"
  AC 50 Hz: "50 Hz 교류 용접 전류"
  DCc: "일정값의 직류 용접 전류"
- Preserve uppercase abbreviations by writing Korean translation followed by the original abbreviation in parentheses when needed. Examples: 설계 FMEA(D-FMEA), 공정 FMEA(P-FMEA), FMEA.
- For non-conforming/discrepant/defective distinctions, prefer "부적합 제품(non-conforming product)", "불일치 제품(discrepant product)", and "결함 제품(defective product)" when distinction matters.{glossary_block}

IATF-style modal language:
- shall: mandatory requirement. Translate as "하여야 한다" or "해야 한다(shall)" when compliance force must be visible.
- should: recommendation. Translate as "해야 한다(should)" or "하는 것이 권고된다" depending on sentence flow.
- may: permission. Translate as "할 수 있다(may)".
- can: capability/possibility. Translate as "할 수 있다(can)" only when distinction from permission matters.
- must: strong obligation. Translate as "해야만 한다(must)".

Document handling:
- Preserve numeric values, units, clause references, table labels, figure labels, document IDs, and revision markers.
- Preserve citation markers such as [1], [2, 3], and [12-15] exactly.
- Preserve URLs, DOI strings, ORCID links, email addresses, and domain names exactly. Never translate "doi.org", "orcid.org", "http", "https", ".com", ".org", or email/domain fragments.
- Keep placeholders such as {{v*}}, <b0>, </b0>, formula markers, and markup unchanged.
- Output mode selected by the user: {output_mode}.
- Review mode selected by the user: {review_mode}.

Source Text: $text

Translated Text:"#,
    )
}

fn run_cli_once(
    python_exe: &str,
    translator_home: &str,
    args: Vec<String>,
    glossary_path: Option<&str>,
) -> Result<(String, String, i32), String> {
    let timeout = if args.iter().any(|arg| arg == "gemini" || arg.starts_with("gemini:")) {
        AGENT_PIPELINE_TIMEOUT_SECS
    } else {
        PYTHON_TIMEOUT_SECS
    };
    run_cli_once_with_timeout(python_exe, translator_home, args, glossary_path, Duration::from_secs(timeout))
}

fn run_cli_once_with_timeout(
    python_exe: &str,
    translator_home: &str,
    args: Vec<String>,
    glossary_path: Option<&str>,
    timeout: Duration,
) -> Result<(String, String, i32), String> {
    let mut command = Command::new(python_exe);
    command.current_dir(translator_home).args(&args);
    if args.iter().any(|value| value == "gemini" || value.starts_with("gemini:")) {
        engine_settings::configure_command(&qdt_runtime_home(), &mut command)?;
    }
    if let Some(glossary_path) = glossary_path {
        // Consumed by qdt_scholar_with_glossary.py to apply domain terms.
        command.env("QDT_GLOSSARY", glossary_path);
    }
    let (stdout, stderr, exit_code) = run_translation_command_with_timeout(&mut command, timeout)?;

    Ok((stdout, stderr, exit_code))
}

fn run_mixed_renderer_once(
    python_exe: &str,
    translator_home: &str,
    mixed_script: &str,
    input_path: &Path,
    output_dir: &str,
    quality: &str,
    output_mode: &str,
    service: &str,
    prompt_path: Option<&str>,
    domain: &str,
    include_shared: bool,
) -> Result<(String, String, i32), String> {
    fs::create_dir_all(output_dir).map_err(|err| err.to_string())?;

    let mut command = Command::new(python_exe);
    command
        .current_dir(translator_home)
        .arg(mixed_script)
        .arg("--input")
        .arg(input_path)
        .arg("--output")
        .arg(output_dir)
        .arg("--quality")
        .arg(quality)
        .arg("--output-mode")
        .arg(output_mode)
        .arg("--service")
        .arg(service)
        .arg("--require-spacing");

    if let Some(glossary) =
        glossary_paths_for_translation(
            &knowledge_base_root(),
            resolve_domain(Some(domain)),
            include_shared,
        )
    {
        command.arg("--glossary").arg(glossary);
    }

    if let Some(prompt_path) = prompt_path {
        command.arg("--prompt").arg(prompt_path);
    }

    if service == "gemini" || service.starts_with("gemini:") {
        engine_settings::configure_command(&qdt_runtime_home(), &mut command)?;
    }
    let timeout = if service.starts_with("gemini") { AGENT_PIPELINE_TIMEOUT_SECS } else { PYTHON_TIMEOUT_SECS };
    let (stdout, stderr, exit_code) = run_translation_command_with_timeout(
        &mut command, Duration::from_secs(timeout),
    )?;

    Ok((stdout, stderr, exit_code))
}

fn run_scholar_task_extraction_once(
    python_exe: &str,
    translator_home: &str,
    input_path: &str,
    task_output: &str,
) -> Result<(String, String, i32), String> {
    let workspace = Path::new(task_output)
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    fs::create_dir_all(&workspace).map_err(|err| err.to_string())?;
    let extract_output = workspace.join("layout-extract").to_string_lossy().to_string();
    let mut args = base_cli_args(input_path, "offline", &extract_output, None, None);
    args.push("--extract-translation-tasks".to_string());
    args.push(task_output.to_string());
    // Task extraction runs the full layout renderer (slow). Part of the agent
    // pipeline, so it gets the agent budget, not the tight 300s CLI default.
    run_cli_once_with_timeout(
        python_exe,
        translator_home,
        args,
        None,
        Duration::from_secs(AGENT_PIPELINE_TIMEOUT_SECS),
    )
}

fn agent_runner_args(
    task_output: &str,
    translation_map: &str,
    engine: &str,
    quality: &str,
    output_mode: &str,
    review_mode: &str,
    domain: &str,
    glossary: Option<&str>,
) -> Vec<String> {
    let mut args = vec![
        "-m".to_string(),
        "qdt.agent_runner".to_string(),
        "--task-output".to_string(),
        task_output.to_string(),
        "--translation-map".to_string(),
        translation_map.to_string(),
        "--engine".to_string(),
        engine.to_string(),
        "--quality".to_string(),
        quality.to_string(),
        "--review-mode".to_string(),
        review_mode.to_string(),
        "--output-mode".to_string(),
        output_mode.to_string(),
        "--domain".to_string(),
        domain.to_string(),
        "--max-batch-items".to_string(),
        DIRECT_AGENT_BATCH_ITEMS.to_string(),
    ];
    if let Some(glossary) = glossary {
        args.push("--glossary".to_string());
        args.push(glossary.to_string());
    }
    args
}

fn pptx_native_args(
    input_path: &str,
    output_dir: &str,
    output_mode: &str,
    service: &str,
    engine: &str,
    quality: &str,
    review_mode: &str,
    domain: &str,
    glossary: Option<&str>,
) -> Vec<String> {
    let mut args = vec![
        "-m".to_string(),
        "qdt.pptx_native".to_string(),
        "--input".to_string(),
        input_path.to_string(),
        "--output".to_string(),
        output_dir.to_string(),
        "--output-mode".to_string(),
        output_mode.to_string(),
        "--service".to_string(),
        service.to_string(),
        "--engine".to_string(),
        engine.to_string(),
        "--quality".to_string(),
        quality.to_string(),
        "--review-mode".to_string(),
        review_mode.to_string(),
        "--domain".to_string(),
        domain.to_string(),
    ];
    if let Some(glossary) = glossary {
        args.push("--glossary".to_string());
        args.push(glossary.to_string());
    }
    args
}

fn run_pptx_native_once(
    python_exe: &str,
    args: Vec<String>,
    use_agent_timeout: bool,
) -> Result<(String, String, i32), String> {
    let mut command = Command::new(python_exe);
    command.env("PYTHONPATH", qdt_python_path()?).args(&args);
    if args.iter().any(|value| value == "gemini" || value.starts_with("gemini:")) {
        engine_settings::configure_command(&qdt_runtime_home(), &mut command)?;
    }
    let timeout = if use_agent_timeout {
        Duration::from_secs(AGENT_PIPELINE_TIMEOUT_SECS)
    } else {
        Duration::from_secs(PYTHON_TIMEOUT_SECS)
    };
    run_translation_command_with_timeout(&mut command, timeout)
}

fn run_agent_translation_map_once(
    python_exe: &str,
    task_output: &str,
    translation_map: &str,
    engine: &str,
    quality: &str,
    output_mode: &str,
    review_mode: &str,
    domain: &str,
    glossary_path: Option<&str>,
    app_handle: &tauri::AppHandle,
) -> Result<(String, String, i32), String> {
    let args = agent_runner_args(
        task_output,
        translation_map,
        engine,
        quality,
        output_mode,
        review_mode,
        domain,
        glossary_path,
    );
    let mut command = Command::new(python_exe);
    command.env("PYTHONPATH", qdt_python_path()?).args(&args);
    let workspace = Path::new(translation_map)
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    run_agent_command_with_monitor(
        &mut command,
        Duration::from_secs(AGENT_PIPELINE_TIMEOUT_SECS),
        app_handle,
        &workspace,
        DIRECT_AGENT_BATCH_ITEMS,
    )
}

fn run_layout_preserved_offline_once(
    python_exe: &str,
    translator_home: &str,
    input_path: &str,
    output_dir: &str,
    translation_map: &str,
) -> Result<(String, String, i32), String> {
    let mut args = base_cli_args(input_path, "offline", output_dir, None, None);
    args.push("--offline-map".to_string());
    args.push(translation_map.to_string());
    // Final layout-preserving render is heavy; give it the agent budget so a
    // large document does not die at the 300s CLI default with zero artifacts.
    run_cli_once_with_timeout(
        python_exe,
        translator_home,
        args,
        None,
        Duration::from_secs(AGENT_PIPELINE_TIMEOUT_SECS),
    )
}

fn agent_workspace_path(output_dir: &str, input_path: &str) -> PathBuf {
    let stem = Path::new(input_path)
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("document");
    Path::new(output_dir).join(".qdt-agent").join(stem)
}

fn agent_task_output_path(output_dir: &str, input_path: &str) -> PathBuf {
    agent_workspace_path(output_dir, input_path).join("tasks.jsonl")
}

fn agent_translation_map_path(output_dir: &str, input_path: &str) -> PathBuf {
    agent_workspace_path(output_dir, input_path).join("translation-map.jsonl")
}

fn wiki_cli_args(command: &str, kb: &str, domain: &str, extra: &[(&str, &str)]) -> Vec<String> {
    let mut args = vec![
        command.to_string(),
        "--kb".to_string(),
        kb.to_string(),
        "--domain".to_string(),
        domain.to_string(),
    ];
    for (key, value) in extra {
        args.push(key.to_string());
        args.push(value.to_string());
    }
    args
}

fn qdt_python_path() -> Result<std::ffi::OsString, String> {
    let services = runtime_paths::asset_root().join("services");

    std::env::join_paths([
        services.join("translator-core").join("src"),
        services.join("agent-adapters").join("src"),
        services.join("scholar-translator"),
    ])
    .map_err(|err| err.to_string())
}

fn run_wiki_cli(args: Vec<String>) -> Result<String, String> {
    let python_exe = default_python_exe();
    let full_args = vec!["-m".to_string(), "qdt.cli".to_string()]
        .into_iter()
        .chain(args)
        .collect::<Vec<_>>();

    let (stdout, stderr, exit_code) = run_command_with_timeout(
        Command::new(&python_exe)
            .env("PYTHONPATH", qdt_python_path()?)
            .args(&full_args),
        Duration::from_secs(PYTHON_TIMEOUT_SECS),
    )?;

    if exit_code != 0 {
        return Err(format!("WIKI CLI failed: {}", stderr.trim()));
    }

    Ok(stdout)
}

#[tauri::command]
fn wiki_list_glossary(domain: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let args = wiki_cli_args("list-glossary", &kb, &domain, &[]);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_add_term(domain: String, source: String, target: String, notes: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let extra = vec![("--source", source.as_str()), ("--target", target.as_str()), ("--notes", notes.as_str())];
    let args = wiki_cli_args("add-term", &kb, &domain, &extra);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_delete_term(domain: String, source: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let extra = vec![("--source", source.as_str())];
    let args = wiki_cli_args("delete-term", &kb, &domain, &extra);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_list_candidates(domain: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let args = wiki_cli_args("list-candidates", &kb, &domain, &[]);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_promote(domain: String, source: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let extra = vec![("--source", source.as_str())];
    let args = wiki_cli_args("promote", &kb, &domain, &extra);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_reject(domain: String, source: String, reason: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let extra = vec![("--source", source.as_str()), ("--reason", reason.as_str())];
    let args = wiki_cli_args("reject", &kb, &domain, &extra);
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_propose_domain(text_file: String) -> Result<String, String> {
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let args = vec![
        "propose-domain".to_string(),
        "--kb".to_string(),
        kb,
        "--text-file".to_string(),
        text_file,
    ];
    run_wiki_cli(args)
}

fn normalize_cat_glossary_format(format: &str) -> Result<&'static str, String> {
    match format.trim().to_ascii_lowercase().as_str() {
        "omegat" => Ok("omegat"),
        "tbx" => Ok("tbx"),
        _ => Err(format!("지원하지 않는 CAT 용어집 형식입니다: {format}")),
    }
}

fn normalize_cat_import_mode(mode: &str) -> Result<&'static str, String> {
    match mode.trim().to_ascii_lowercase().as_str() {
        "candidates" => Ok("candidates"),
        "confirmed" => Ok("confirmed"),
        _ => Err(format!("지원하지 않는 CAT 가져오기 모드입니다: {mode}")),
    }
}

fn glossary_export_extension(format: &str) -> Result<&'static str, String> {
    match normalize_cat_glossary_format(format)? {
        "omegat" => Ok("txt"),
        "tbx" => Ok("tbx"),
        _ => unreachable!("normalized CAT glossary format must be known"),
    }
}

fn normalize_domain_arg(domain: &str) -> Result<String, String> {
    let slug = sanitize_domain_slug(domain);
    if slug.is_empty() {
        return Err("분야 이름은 영문, 숫자, 공백, 하이픈으로 입력하세요.".to_string());
    }
    Ok(slug)
}

fn cat_glossary_export_target(
    kb_root: &Path,
    domain: &str,
    format: &str,
) -> Result<(String, String, &'static str), String> {
    let domain = normalize_domain_arg(domain)?;
    let format = normalize_cat_glossary_format(format)?;
    let extension = glossary_export_extension(format)?;
    let out = kb_root
        .join("exports")
        .join(format!("{domain}-glossary.{extension}"))
        .to_string_lossy()
        .to_string();
    Ok((domain, out, format))
}

#[tauri::command]
fn wiki_export_glossary(domain: String, format: String) -> Result<String, String> {
    let kb_root = knowledge_base_root();
    let kb = kb_root.join("domains").to_string_lossy().to_string();
    let (domain, out, format) = cat_glossary_export_target(&kb_root, &domain, &format)?;
    let export_dir = kb_root.join("exports");
    fs::create_dir_all(&export_dir).map_err(|err| format!("CAT 내보내기 폴더 생성 실패: {err}"))?;
    let args = vec![
        "export-glossary".to_string(),
        "--kb".to_string(),
        kb,
        "--domain".to_string(),
        domain,
        "--format".to_string(),
        format.to_string(),
        "--out".to_string(),
        out,
    ];
    run_wiki_cli(args)
}

#[tauri::command]
fn wiki_import_glossary(
    domain: String,
    format: String,
    input_path: String,
    mode: String,
) -> Result<String, String> {
    let domain = normalize_domain_arg(&domain)?;
    let format = normalize_cat_glossary_format(&format)?;
    let mode = normalize_cat_import_mode(&mode)?;
    let kb = knowledge_base_root().join("domains").to_string_lossy().to_string();
    let args = vec![
        "import-glossary".to_string(),
        "--kb".to_string(),
        kb,
        "--domain".to_string(),
        domain,
        "--format".to_string(),
        format.to_string(),
        "--input".to_string(),
        input_path,
        "--mode".to_string(),
        mode.to_string(),
    ];
    run_wiki_cli(args)
}

#[derive(Serialize)]
struct DomainInfo {
    slug: String,
    terms: usize,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DomainDeleteResult {
    domains: Vec<DomainInfo>,
    backup_path: String,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct SharedPackInfo {
    id: String,
    domain: String,
    display_name: String,
    version: String,
    sha256: String,
    terms: usize,
    installed_at: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SharedPackInstallRequest {
    id: String,
    domain: String,
    display_name: String,
    version: String,
    sha256: String,
    glossary_csv: String,
    terms: usize,
}

fn sanitize_domain_slug(input: &str) -> String {
    let mut slug = String::new();
    for ch in input.trim().to_lowercase().chars() {
        if ch.is_ascii_alphanumeric() {
            slug.push(ch);
        } else if ch == ' ' || ch == '-' || ch == '_' {
            slug.push('-');
        }
    }
    while slug.contains("--") {
        slug = slug.replace("--", "-");
    }
    slug.trim_matches('-').to_string()
}

fn sanitize_pack_id(input: &str) -> String {
    sanitize_domain_slug(input)
}

fn list_domain_infos_at(kb: &Path) -> Vec<DomainInfo> {
    let mut domains = Vec::new();
    if let Ok(entries) = fs::read_dir(kb.join("domains")) {
        for entry in entries.flatten() {
            if entry.file_type().map(|file_type| file_type.is_dir()).unwrap_or(false) {
                let slug = entry.file_name().to_string_lossy().to_string();
                if slug.starts_with('.') {
                    continue;
                }
                let terms = load_glossary_terms(&kb, &slug).len();
                domains.push(DomainInfo { slug, terms });
            }
        }
    }
    domains.sort_by(|left, right| left.slug.cmp(&right.slug));
    domains
}

fn list_domain_infos() -> Vec<DomainInfo> {
    let kb = knowledge_base_root();
    list_domain_infos_at(&kb)
}

fn copy_dir_all(source: &Path, destination: &Path) -> Result<(), String> {
    fs::create_dir_all(destination).map_err(|err| format!("도메인 백업 생성 실패: {err}"))?;
    for entry in fs::read_dir(source).map_err(|err| format!("도메인 백업 읽기 실패: {err}"))? {
        let entry = entry.map_err(|err| format!("도메인 백업 항목 읽기 실패: {err}"))?;
        let file_type = entry.file_type().map_err(|err| format!("도메인 백업 항목 확인 실패: {err}"))?;
        let target = destination.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_all(&entry.path(), &target)?;
        } else {
            fs::copy(entry.path(), &target).map_err(|err| format!("도메인 백업 복사 실패: {err}"))?;
        }
    }
    Ok(())
}

fn domain_backup_path(kb: &Path, slug: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    kb.join("backups").join("domains").join(format!("{slug}-{nanos}"))
}

fn shared_pack_dir(kb: &Path, id: &str) -> PathBuf {
    kb.join("shared").join("packs").join(id)
}

fn list_shared_packs_at(kb: &Path) -> Vec<SharedPackInfo> {
    let mut packs = Vec::new();
    if let Ok(entries) = fs::read_dir(kb.join("shared").join("packs")) {
        for entry in entries.flatten() {
            if !entry.file_type().map(|file_type| file_type.is_dir()).unwrap_or(false) {
                continue;
            }
            let pack_json = entry.path().join("pack.json");
            let glossary = entry.path().join("glossary.csv");
            if !glossary.exists() {
                continue;
            }
            let Ok(raw) = fs::read_to_string(pack_json) else {
                continue;
            };
            let Ok(info) = serde_json::from_str::<SharedPackInfo>(&raw) else {
                continue;
            };
            if sanitize_pack_id(&info.id).is_empty() || info.domain.trim().is_empty() {
                continue;
            }
            packs.push(info);
        }
    }
    packs.sort_by(|left, right| left.id.cmp(&right.id));
    packs
}

fn shared_glossary_paths_for_domain(kb: &Path, domain: &str) -> Vec<PathBuf> {
    list_shared_packs_at(kb)
        .into_iter()
        .filter(|pack| pack.domain == domain)
        .map(|pack| shared_pack_dir(kb, &pack.id).join("glossary.csv"))
        .filter(|path| path.exists())
        .collect()
}

fn install_shared_pack_at(kb: &Path, request: SharedPackInstallRequest) -> Result<SharedPackInfo, String> {
    let id = sanitize_pack_id(&request.id);
    let domain = sanitize_domain_slug(&request.domain);
    let display_name = request.display_name.trim();
    let version = request.version.trim();
    let sha256 = request.sha256.trim();
    let glossary_csv = request.glossary_csv.trim_start_matches('\u{feff}');

    if id.is_empty() {
        return Err("공유팩 ID는 영문, 숫자, 하이픈으로 입력하세요.".to_string());
    }
    if domain.is_empty() {
        return Err("공유팩 도메인은 영문, 숫자, 하이픈으로 입력하세요.".to_string());
    }
    if display_name.is_empty() {
        return Err("공유팩 이름이 비어 있습니다.".to_string());
    }
    if version.is_empty() {
        return Err("공유팩 버전이 비어 있습니다.".to_string());
    }
    if sha256.is_empty() {
        return Err("공유팩 무결성 해시가 비어 있습니다.".to_string());
    }
    if !glossary_csv.starts_with("source,target,notes") {
        return Err("공유팩 glossary.csv 헤더가 올바르지 않습니다.".to_string());
    }

    let packs_root = kb.join("shared").join("packs");
    fs::create_dir_all(&packs_root).map_err(|err| format!("공유팩 폴더 생성 실패: {err}"))?;
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let temp_dir = packs_root.join(format!(".{id}-{nanos}.tmp"));
    let target_dir = shared_pack_dir(kb, &id);
    fs::create_dir_all(&temp_dir).map_err(|err| format!("공유팩 임시 폴더 생성 실패: {err}"))?;

    let installed_at = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        .to_string();
    let info = SharedPackInfo {
        id,
        domain,
        display_name: display_name.to_string(),
        version: version.to_string(),
        sha256: sha256.to_string(),
        terms: request.terms,
        installed_at,
    };

    fs::write(temp_dir.join("glossary.csv"), glossary_csv)
        .map_err(|err| format!("공유팩 용어집 저장 실패: {err}"))?;
    fs::write(
        temp_dir.join("pack.json"),
        serde_json::to_string_pretty(&info).map_err(|err| format!("공유팩 메타데이터 직렬화 실패: {err}"))? + "\n",
    )
    .map_err(|err| format!("공유팩 메타데이터 저장 실패: {err}"))?;

    if target_dir.exists() {
        fs::remove_dir_all(&target_dir).map_err(|err| format!("기존 공유팩 제거 실패: {err}"))?;
    }
    fs::rename(&temp_dir, &target_dir).map_err(|err| format!("공유팩 설치 실패: {err}"))?;

    Ok(info)
}

fn remove_shared_pack_at(kb: &Path, id: &str) -> Result<Vec<SharedPackInfo>, String> {
    let id = sanitize_pack_id(id);
    if id.is_empty() {
        return Err("공유팩 ID는 영문, 숫자, 하이픈으로 입력하세요.".to_string());
    }
    let dir = shared_pack_dir(kb, &id);
    if dir.exists() {
        fs::remove_dir_all(&dir).map_err(|err| format!("공유팩 제거 실패: {err}"))?;
    }
    Ok(list_shared_packs_at(kb))
}

fn delete_domain_at(kb: &Path, slug: &str) -> Result<DomainDeleteResult, String> {
    let slug = sanitize_domain_slug(slug);
    if slug.is_empty() {
        return Err("도메인 이름은 영문, 숫자, 공백, 하이픈으로 입력하세요.".to_string());
    }
    let domains = list_domain_infos_at(kb);
    if domains.len() <= 1 {
        return Err("마지막 도메인은 제거할 수 없습니다.".to_string());
    }
    if !domains.iter().any(|domain| domain.slug == slug) {
        return Err(format!("도메인을 찾을 수 없습니다: {slug}"));
    }

    let dir = kb.join("domains").join(&slug);
    let backup = domain_backup_path(kb, &slug);
    copy_dir_all(&dir, &backup)?;
    fs::remove_dir_all(&dir).map_err(|err| format!("도메인 제거 실패: {err}"))?;
    Ok(DomainDeleteResult {
        domains: list_domain_infos_at(kb),
        backup_path: backup.to_string_lossy().to_string(),
    })
}

#[tauri::command]
fn wiki_list_domains() -> Result<Vec<DomainInfo>, String> {
    Ok(list_domain_infos())
}

#[tauri::command]
fn wiki_create_domain(slug: String) -> Result<Vec<DomainInfo>, String> {
    let slug = sanitize_domain_slug(&slug);
    if slug.is_empty() {
        return Err("분야 이름은 영문, 숫자, 공백, 하이픈으로 입력하세요.".to_string());
    }
    let dir = knowledge_base_root().join("domains").join(&slug);
    fs::create_dir_all(&dir).map_err(|err| format!("분야 폴더 생성 실패: {err}"))?;
    let glossary = dir.join("glossary.csv");
    if !glossary.exists() {
        fs::write(&glossary, "source,target,notes\n")
            .map_err(|err| format!("용어집 생성 실패: {err}"))?;
    }
    Ok(list_domain_infos())
}

#[tauri::command]
fn wiki_delete_domain(slug: String) -> Result<DomainDeleteResult, String> {
    let kb = knowledge_base_root();
    delete_domain_at(&kb, &slug)
}

#[tauri::command]
fn wiki_list_shared_packs() -> Result<Vec<SharedPackInfo>, String> {
    Ok(list_shared_packs_at(&knowledge_base_root()))
}

#[tauri::command]
fn wiki_install_shared_pack(request: SharedPackInstallRequest) -> Result<SharedPackInfo, String> {
    install_shared_pack_at(&knowledge_base_root(), request)
}

#[tauri::command]
fn wiki_remove_shared_pack(id: String) -> Result<Vec<SharedPackInfo>, String> {
    remove_shared_pack_at(&knowledge_base_root(), &id)
}


#[tauri::command]
fn get_engine_settings() -> Result<engine_settings::EngineSettingsView, String> {
    engine_settings::view_at(&qdt_runtime_home())
}

#[tauri::command]
fn save_engine_settings(request: engine_settings::SaveEngineSettingsRequest) -> Result<engine_settings::EngineSettingsView, String> {
    if job_control::active() {return Err("[QDT_JOB_BUSY] 번역이 끝난 뒤 API 설정을 변경하세요.".into());}
    engine_settings::save_at(&qdt_runtime_home(), request)
}

#[tauri::command]
fn clear_engine_api_key() -> Result<engine_settings::EngineSettingsView, String> {
    if job_control::active() {return Err("[QDT_JOB_BUSY] 번역이 끝난 뒤 API 설정을 변경하세요.".into());}
    engine_settings::clear_key_at(&qdt_runtime_home())
}

#[derive(Serialize, Deserialize)]
struct EngineConnectionResult {
    ok: bool,
    model: String,
    message: String,
}

#[tauri::command]
async fn test_engine_connection() -> Result<EngineConnectionResult, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let root = qdt_runtime_home();
        let model = engine_settings::view_at(&root)?.model;
        let python = std::env::var("SCHOLAR_TRANSLATOR_PYTHON").unwrap_or_else(|_| default_python_exe());
        let mut command = Command::new(python);
        command.current_dir(default_scholar_translator_home()).arg("-c").arg(r#"
import json, os
from scholar_translator.gemini_client import GeminiClient, GeminiError, api_key_from_environment
model = os.environ["QDT_GEMINI_MODEL"]
try:
    GeminiClient(api_key_from_environment(), model).translate("Hello", "ko")
    result = {"ok": True, "model": model, "message": "연결 확인 성공. 선택한 모델에서 응답을 받았습니다."}
except GeminiError as error:
    result = {"ok": False, "model": model, "message": str(error)}
except Exception:
    result = {"ok": False, "model": model, "message": "[QDT_GEMINI_CONNECTION] 연결 확인에 실패했습니다. 키와 네트워크를 확인하세요."}
print(json.dumps(result, ensure_ascii=False))
"#);
        engine_settings::configure_command(&root, &mut command)?;
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let (stdout, _, exit_code) = run_command_with_timeout(&mut command, Duration::from_secs(45))
            .map_err(|_| "[QDT_GEMINI_CONNECTION] 45초 안에 연결을 확인하지 못했습니다. 네트워크와 API 상태를 확인하세요.".to_string())?;
        if exit_code != 0 {
            return Ok(EngineConnectionResult { ok: false, model, message: "[QDT_GEMINI_RUNTIME] Python 번역 모듈을 실행하지 못했습니다. 실행 환경을 확인하세요.".into() });
        }
        serde_json::from_str::<EngineConnectionResult>(stdout.trim())
            .map_err(|_| "[QDT_GEMINI_CONNECTION] 연결 확인 결과를 읽지 못했습니다.".into())
    }).await.map_err(|_| "[QDT_GEMINI_CONNECTION] 연결 확인 작업을 완료하지 못했습니다.".to_string())?
}

#[tauri::command]
fn load_review_session() -> Result<Option<serde_json::Value>,String> {review_session::load_at(&qdt_runtime_home())}
#[tauri::command]
fn save_review_session(snapshot:Option<serde_json::Value>) -> Result<(),String> {review_session::save_at(&qdt_runtime_home(),snapshot)}

pub fn check_runtime(report: &Path) -> i32 {
    let root = runtime_paths::asset_root();
    let python = default_python_exe();
    let mut command = Command::new(&python);
    command.args(["-X", "utf8", "-B"]).arg(root.join("scripts/runtime-check.py"));
    command.current_dir(&root);
    if let Ok(paths) = qdt_python_path() { command.env("PYTHONPATH", paths); }
    for key in ["GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"] { command.env_remove(key); }
    let result = runtime_paths::initialize().map_err(|e| e.to_string()).and_then(|_| {
        run_command_with_timeout(&mut command, Duration::from_secs(180))
    });
    let (ok, details) = match result {
        Ok((stdout, stderr, code)) => {
            let parsed = stdout.lines().rev().find_map(|line| serde_json::from_str::<serde_json::Value>(line).ok());
            (code == 0 && parsed.as_ref().and_then(|v| v.get("ok")).and_then(|v| v.as_bool()) == Some(true),
             parsed.unwrap_or_else(|| serde_json::json!({"error": stderr})))
        }
        Err(error) => (false, serde_json::json!({"error": error})),
    };
    let data = serde_json::json!({"ok":ok,"resource_root":root,"python":python,"data_root":qdt_runtime_home(),"details":details});
    if fs::write(report, serde_json::to_vec_pretty(&data).unwrap()).is_err() { return 2; }
    if ok { 0 } else { 1 }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|_| { runtime_paths::initialize()?; Ok(()) })
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            load_review_session,
            save_review_session,
            get_engine_settings,
            save_engine_settings,
            clear_engine_api_key,
            test_engine_connection,
            capture_pdf_page_snapshot,
            open_system_path,
            run_translation_job,
            cancel_translation_job,
            wiki_list_glossary,
            wiki_add_term,
            wiki_delete_term,
            wiki_list_candidates,
            wiki_promote,
            wiki_reject,
            wiki_propose_domain,
            wiki_export_glossary,
            wiki_import_glossary,
            wiki_list_domains,
            wiki_create_domain,
            wiki_delete_domain,
            wiki_list_shared_packs,
            wiki_install_shared_pack,
            wiki_remove_shared_pack
        ])
        .run(tauri::generate_context!())
        .expect("failed to run app");
}

#[cfg(test)]
mod tests {
    #[test]
    fn gemini_engine_routes_to_authenticated_service() {
        let (service, model) = super::map_engine_to_service("gemini-flash-lite");
        assert_eq!(service, "gemini");
        assert!(!model.is_empty());
    }

    #[test]
    fn gemini_guard_failure_has_short_specific_guidance() {
        let raw = format!("scholar-translator failed: {} [QDT_GEMINI_PRESERVATION] bad output [QDT_DIAGNOSTICS] private paths", "traceback ".repeat(3000));
        let diagnosis = super::diagnose_failure(&raw, 1).unwrap();
        assert!(diagnosis.cause.contains("QDT_GEMINI_PRESERVATION"));
        assert!(diagnosis.cause.len() < 500);
        assert!(!diagnosis.cause.contains("private paths"));
        assert!(diagnosis.solution.contains("교정"));
        assert!(!diagnosis.solution.contains("AI Studio"));
        assert!(!diagnosis.solution.contains("키를"));
        let expansion = super::diagnose_failure("[QDT_GEMINI_EXPANSION] expansion", 1).unwrap();
        assert!(expansion.cause.contains("설명"));
    }

    #[test]
    fn gemini_format_error_has_output_guidance() {
        let d=super::diagnose_failure("[QDT_GEMINI_FORMAT] traceback",1).unwrap();
        assert!(d.cause.contains("JSON"));
        assert!(d.solution.contains("교정"));
        assert!(!d.solution.contains("키"));
    }

    #[test]
    fn gemini_access_and_quota_failures_have_distinct_guidance() {
        let quota = super::diagnose_failure("[QDT_GEMINI_RATE_LIMITED] raw server body", 1).unwrap();
        let auth = super::diagnose_failure("[QDT_GEMINI_AUTH] raw server body", 1).unwrap();
        assert!(quota.solution.contains("AI Studio"));
        assert!(auth.solution.contains("API 키"));
        assert!(!auth.cause.contains("raw server body"));
        assert_ne!(quota.solution, auth.solution);
    }

    #[test]
    fn gemini_cli_limits_parallel_requests_to_one() {
        let args = super::base_cli_args("sample.pdf", "gemini:gemini-2.5-flash-lite", "out", None, None);
        let thread_index = args.iter().position(|arg| arg == "--thread").unwrap();
        assert_eq!(args[thread_index + 1], "1");
        assert!(args.contains(&"gemini:gemini-2.5-flash-lite".to_string()));
    }

    #[test]
    fn gemini_errors_keep_the_named_cause() {
        let diagnosis = super::diagnose_failure("[QDT_GEMINI_RATE_LIMITED] limit", 1).unwrap();
        assert!(diagnosis.cause.contains("QDT_GEMINI_RATE_LIMITED"));
        assert!(diagnosis.summary.contains("Gemini"));
    }

    use super::*;

    #[test]
    fn glossary_path_for_domain_returns_some_only_when_file_exists() {
        let base = std::env::temp_dir().join("qdt_kb_test_glossary");
        let dir = base.join("domains").join("q");
        std::fs::create_dir_all(&dir).unwrap();
        let glossary = dir.join("glossary.csv");
        std::fs::write(&glossary, "source,target,notes\n").unwrap();

        assert_eq!(
            glossary_path_for_domain(&base, "q"),
            Some(glossary.to_string_lossy().to_string())
        );
        assert_eq!(glossary_path_for_domain(&base, "missing"), None);

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn parse_batch_index_reads_prompt_and_response_names() {
        assert_eq!(parse_batch_index("batch-0046.prompt.txt"), Some(46));
        assert_eq!(parse_batch_index("batch-0045.response.txt"), Some(45));
        assert_eq!(parse_batch_index("not-a-batch.txt"), None);
    }

    #[test]
    fn infer_prompt_batch_items_counts_input_rows_only() {
        let base = std::env::temp_dir().join("qdt_prompt_batch_items_test");
        std::fs::create_dir_all(&base).unwrap();
        let prompt = base.join("batch-0001.prompt.txt");
        std::fs::write(
            &prompt,
            r#"Output shape: {"translations":[{"id":1}]}
INPUT:
[
  {"id": 1, "source": "A"},
  {"id": 2, "source": "B"},
  {"id": 3, "source": "C"}
]"#,
        )
        .unwrap();

        assert_eq!(infer_prompt_batch_items(&prompt), Some(3));

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn build_agent_progress_snapshot_reports_batches_and_workspace() {
        let base = std::env::temp_dir().join("qdt_agent_progress_snapshot_test");
        let batch_dir = base.join("agent-batches");
        std::fs::create_dir_all(&batch_dir).unwrap();
        std::fs::write(base.join("tasks.jsonl"), "1\n2\n3\n4\n").unwrap();
        std::fs::write(
            batch_dir.join("batch-0001.prompt.txt"),
            "INPUT:\n[{\"id\":1},{\"id\":2}]",
        )
        .unwrap();
        std::fs::write(
            batch_dir.join("batch-0001.response.txt"),
            "[{\"id\":1,\"source\":\"A\",\"translation\":\"가\"}]",
        )
        .unwrap();
        std::fs::write(
            batch_dir.join("batch-0002.prompt.txt"),
            "INPUT:\n[{\"id\":3},{\"id\":4}]",
        )
        .unwrap();

        let snapshot = build_agent_progress_snapshot(&base, &[], 64, None);

        assert_eq!(snapshot.current_batch, 2);
        assert_eq!(snapshot.total_batches, 2);
        assert_eq!(snapshot.completed_batches, 1);
        assert_eq!(snapshot.health, "waiting");
        assert!(snapshot.workspace.contains("qdt_agent_progress_snapshot_test"));
        assert!(snapshot
            .recent_files
            .contains(&"batch-0002.prompt.txt".to_string()));
        assert!(snapshot
            .recent_response_preview
            .as_deref()
            .unwrap_or("")
            .contains("\"translation\""));

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn parse_csv_line_handles_quotes_and_commas() {
        assert_eq!(parse_csv_line("a,b,c"), vec!["a", "b", "c"]);
        assert_eq!(
            parse_csv_line(r#"FMEA,"고장모드, 영향분석",note"#),
            vec!["FMEA", "고장모드, 영향분석", "note"]
        );
        assert_eq!(parse_csv_line(r#""he said ""hi""","x""#), vec!["he said \"hi\"", "x"]);
    }

    #[test]
    fn load_glossary_terms_skips_header_blank_and_incomplete_rows() {
        let base = std::env::temp_dir().join("qdt_kb_test_load_terms");
        let dir = base.join("domains").join("q");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("glossary.csv"),
            "source,target,notes
FMEA,고장모드 및 영향분석(FMEA),

LonelySource,,skip-empty-target
Control Plan,관리계획서(Control Plan),keep
",
        )
        .unwrap();

        let terms = load_glossary_terms(&base, "q");
        assert_eq!(
            terms,
            vec![
                ("FMEA".to_string(), "고장모드 및 영향분석(FMEA)".to_string()),
                ("Control Plan".to_string(), "관리계획서(Control Plan)".to_string()),
            ]
        );
        // Missing domain → empty, never panics.
        assert!(load_glossary_terms(&base, "missing").is_empty());

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn glossary_paths_for_translation_include_scholarly_profile_before_domain() {
        let base = std::env::temp_dir().join("qdt_kb_test_runtime_glossaries");
        let profile_dir = base.join("profiles").join("scholarly");
        let domain_dir = base.join("domains").join("q");
        std::fs::create_dir_all(&profile_dir).unwrap();
        std::fs::create_dir_all(&domain_dir).unwrap();
        let profile = profile_dir.join("glossary.csv");
        let domain = domain_dir.join("glossary.csv");
        std::fs::write(&profile, "source,target,notes\nAbstract,초록,exact-heading\n").unwrap();
        std::fs::write(&domain, "source,target,notes\nFMEA,고장모드,\n").unwrap();

        let joined = glossary_paths_for_translation(&base, "q", false).unwrap();
        let paths = std::env::split_paths(&joined).collect::<Vec<_>>();

        assert_eq!(paths, vec![profile, domain]);

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn glossary_paths_include_shared_packs_between_profile_and_local_domain() {
        let base = std::env::temp_dir().join(format!(
            "qdt_shared_merge_{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));
        let profile_dir = base.join("profiles").join("scholarly");
        let domain_dir = base.join("domains").join("quality-manufacturing");
        std::fs::create_dir_all(&profile_dir).unwrap();
        std::fs::create_dir_all(&domain_dir).unwrap();
        std::fs::write(profile_dir.join("glossary.csv"), "source,target,notes\nAbstract,초록,\n").unwrap();
        std::fs::write(domain_dir.join("glossary.csv"), "source,target,notes\nFMEA,고장모드,\n").unwrap();
        install_shared_pack_at(&base, SharedPackInstallRequest {
            id: "official-quality-v1".to_string(),
            domain: "quality-manufacturing".to_string(),
            display_name: "Quality Pack".to_string(),
            version: "1".to_string(),
            sha256: "hash".to_string(),
            glossary_csv: "source,target,notes\nControl plan,관리계획서,\n".to_string(),
            terms: 1,
        }).unwrap();

        let joined = glossary_paths_for_translation(&base, "quality-manufacturing", true).unwrap();
        let paths: Vec<PathBuf> = std::env::split_paths(&joined).collect();

        assert_eq!(paths.len(), 3);
        assert!(paths[0].ends_with("profiles/scholarly/glossary.csv") || paths[0].ends_with(r"profiles\scholarly\glossary.csv"));
        assert!(paths[1].ends_with("shared/packs/official-quality-v1/glossary.csv") || paths[1].ends_with(r"shared\packs\official-quality-v1\glossary.csv"));
        assert!(paths[2].ends_with("domains/quality-manufacturing/glossary.csv") || paths[2].ends_with(r"domains\quality-manufacturing\glossary.csv"));

        assert_eq!(
            load_runtime_glossary_terms(&base, "quality-manufacturing", true),
            vec![
                ("Abstract".to_string(), "초록".to_string()),
                ("Control plan".to_string(), "관리계획서".to_string()),
                ("FMEA".to_string(), "고장모드".to_string()),
            ]
        );

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn load_runtime_glossary_terms_merges_scholarly_profile_and_domain_terms() {
        let base = std::env::temp_dir().join("qdt_kb_test_runtime_terms");
        let profile_dir = base.join("profiles").join("scholarly");
        let domain_dir = base.join("domains").join("q");
        std::fs::create_dir_all(&profile_dir).unwrap();
        std::fs::create_dir_all(&domain_dir).unwrap();
        std::fs::write(
            profile_dir.join("glossary.csv"),
            "source,target,notes\nAbstract,초록,exact-heading\n",
        )
        .unwrap();
        std::fs::write(
            domain_dir.join("glossary.csv"),
            "source,target,notes\nFMEA,고장모드,\n",
        )
        .unwrap();

        assert_eq!(
            load_runtime_glossary_terms(&base, "q", false),
            vec![
                ("Abstract".to_string(), "초록".to_string()),
                ("FMEA".to_string(), "고장모드".to_string()),
            ]
        );

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn build_prompt_embeds_glossary_terms_only_when_present() {
        let terms = vec![("FMEA".to_string(), "고장모드 및 영향분석(FMEA)".to_string())];
        let with = build_prompt("realistic", "dual", "on", &terms);
        assert!(with.contains("User-approved domain glossary"));
        assert!(with.contains("\"FMEA\" → \"고장모드 및 영향분석(FMEA)\""));

        let without = build_prompt("realistic", "dual", "on", &[]);
        assert!(!without.contains("User-approved domain glossary"));
    }

    #[test]
    fn resolve_domain_uses_request_value_else_default() {
        assert_eq!(resolve_domain(Some("medical")), "medical");
        assert_eq!(resolve_domain(None), DEFAULT_DOMAIN);
    }

    #[test]
    fn agent_mode_uses_agent_cli_pipeline_instead_of_scholar_service() {
        let pipeline = select_translation_pipeline("agent", "dual", "codex-agent", Vec::new());

        assert!(matches!(pipeline, TranslationPipeline::AgentCliRunner));
    }

    #[test]
    fn machine_mode_keeps_scholar_translator_for_plain_dual_pdf() {
        let pipeline =
            select_translation_pipeline("machine", "dual", "gemini-flash-lite", Vec::new());

        assert!(matches!(pipeline, TranslationPipeline::ScholarTranslator));
    }

    #[test]
    fn unsupported_engine_is_rejected_before_service_mapping() {
        assert!(job_control::validate_engine("antigravity-agent","agent").is_err());
        assert_eq!(map_engine_to_service("antigravity-agent").0,"unsupported");
    }

    #[test]
    fn mono_with_mixed_language_pdf_uses_mixed_renderer_for_machine_translation() {
        let mixed_inputs = vec![MixedLanguageInput {
            path: PathBuf::from(r"D:\docs\mixed.pdf"),
            report: "mixed.pdf / latin=6379 (65%), cjk=3423 (35%)".to_string(),
        }];

        let pipeline =
            select_translation_pipeline("machine", "mono", "gemini-flash-lite", mixed_inputs);

        assert!(matches!(
            pipeline,
            TranslationPipeline::MixedRenderer(paths) if paths == vec![PathBuf::from(r"D:\docs\mixed.pdf")]
        ));
    }

    #[test]
    fn dual_with_mixed_language_pdf_uses_scholar_translator() {
        let mixed_inputs = vec![MixedLanguageInput {
            path: PathBuf::from(r"D:\docs\mixed.pdf"),
            report: "mixed.pdf / latin=6379 (65%), cjk=3423 (35%)".to_string(),
        }];

        let pipeline =
            select_translation_pipeline("machine", "dual", "gemini-flash-lite", mixed_inputs);

        assert!(matches!(pipeline, TranslationPipeline::ScholarTranslator));
    }

    #[test]
    fn pptx_input_uses_native_pipeline() {
        let pipeline = select_translation_pipeline_for_inputs(
            "machine",
            "mono",
            "gemini-flash-lite",
            &[r"D:\docs\deck.pptx".to_string()],
            Vec::new(),
        );

        assert!(matches!(
            pipeline,
            TranslationPipeline::PptxNative(paths) if paths == vec![PathBuf::from(r"D:\docs\deck.pptx")]
        ));
    }

    #[test]
    fn ppt_legacy_binary_is_rejected_before_translation() {
        assert!(contains_unsupported_ppt(&[r"D:\docs\legacy.ppt".to_string()]));
        assert!(!contains_unsupported_ppt(&[r"D:\docs\deck.pptx".to_string()]));
    }

    #[test]
    fn pptx_native_args_include_mode_service_domain_and_glossary() {
        let args = pptx_native_args(
            r"D:\docs\deck.pptx",
            r"D:\out",
            "dual",
            "agent",
            "codex-agent",
            "true",
            "on",
            "medical-device",
            Some(r"D:\kb\glossary.csv"),
        );

        assert_eq!(args[0], "-m");
        assert_eq!(args[1], "qdt.pptx_native");
        assert!(args.contains(&"--input".to_string()));
        assert!(args.contains(&r"D:\docs\deck.pptx".to_string()));
        assert!(args.contains(&"--output-mode".to_string()));
        assert!(args.contains(&"dual".to_string()));
        assert!(args.contains(&"--service".to_string()));
        assert!(args.contains(&"agent".to_string()));
        assert!(args.contains(&"--engine".to_string()));
        assert!(args.contains(&"codex-agent".to_string()));
        assert!(args.contains(&"--domain".to_string()));
        assert!(args.contains(&"medical-device".to_string()));
        assert!(args.contains(&"--glossary".to_string()));
        assert!(args.contains(&r"D:\kb\glossary.csv".to_string()));
    }

    #[test]
    fn cat_export_target_sanitizes_domain_and_uses_known_extension() {
        let (domain, out, format) =
            cat_glossary_export_target(Path::new(r"D:\kb"), "../Medical Device", "TBX").unwrap();

        assert_eq!(domain, "medical-device");
        assert_eq!(format, "tbx");
        assert!(out.ends_with(r"D:\kb\exports\medical-device-glossary.tbx"));
        assert!(!out.contains(".."));
    }

    #[test]
    fn cat_import_mode_rejects_unknown_values() {
        assert_eq!(normalize_cat_import_mode("confirmed").unwrap(), "confirmed");
        assert_eq!(normalize_cat_import_mode("candidates").unwrap(), "candidates");
        assert!(normalize_cat_import_mode("replace").is_err());
    }

    #[test]
    fn collect_artifact_outputs_includes_review_sidecars() {
        let logs = r#"
D:\out\paper-ko-mono.pdf
D:\out\paper-ko-mono.md
D:\out\paper-ko-mono.html
D:\out\paper-ko-mono.layout-audit.json
ignored line
"#;

        assert_eq!(
            collect_artifact_outputs(logs),
            vec![
                r"D:\out\paper-ko-mono.pdf".to_string(),
                r"D:\out\paper-ko-mono.md".to_string(),
                r"D:\out\paper-ko-mono.html".to_string(),
                r"D:\out\paper-ko-mono.layout-audit.json".to_string(),
            ]
        );
    }

    #[test]
    fn collect_artifact_outputs_includes_pptx_decks() {
        let logs = r#"
D:\out\deck-ko-mono.pptx
D:\out\deck-ko-dual.pptx
"#;

        assert_eq!(
            collect_artifact_outputs(logs),
            vec![
                r"D:\out\deck-ko-mono.pptx".to_string(),
                r"D:\out\deck-ko-dual.pptx".to_string(),
            ]
        );
    }

    #[test]
    fn scan_recent_artifact_outputs_skips_qdt_agent_workspace() {
        let base = std::env::temp_dir().join(format!("qdt_scan_skip_{}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        let final_dir = base.join("doc-ko");
        // The agent workspace holds the untranslated task-extraction byproduct.
        let byproduct = base
            .join(".qdt-agent")
            .join("doc")
            .join("layout-extract")
            .join("doc-ko");
        fs::create_dir_all(&final_dir).unwrap();
        fs::create_dir_all(&byproduct).unwrap();
        fs::write(final_dir.join("doc-ko-mono.pdf"), b"x").unwrap();
        fs::write(byproduct.join("doc-ko-mono.pdf"), b"x").unwrap();

        let started = std::time::SystemTime::now() - std::time::Duration::from_secs(120);
        let outputs = scan_recent_artifact_outputs(base.to_str().unwrap(), started);
        let _ = fs::remove_dir_all(&base);

        assert!(
            !outputs.iter().any(|p| p.contains(".qdt-agent")),
            "agent-workspace byproduct must be skipped: {outputs:?}"
        );
        assert_eq!(outputs.len(), 1, "only the final render is a deliverable: {outputs:?}");
    }

    #[test]
    fn enforce_output_mode_keeps_review_sidecars_for_selected_pdf() {
        let base = std::env::temp_dir().join(format!(
            "qdt_mode_sidecars_{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&base);
        std::fs::create_dir_all(&base).unwrap();

        let mono = base.join("paper-ko-mono.pdf").to_string_lossy().to_string();
        let dual = base.join("paper-ko-dual.pdf").to_string_lossy().to_string();
        let md = base.join("paper-ko-mono.md").to_string_lossy().to_string();
        let html = base.join("paper-ko-mono.html").to_string_lossy().to_string();
        let audit = base
            .join("paper-ko-mono.layout-audit.json")
            .to_string_lossy()
            .to_string();
        let dual_html = base.join("paper-ko-dual.html").to_string_lossy().to_string();

        for path in [&mono, &dual, &md, &html, &audit, &dual_html] {
            std::fs::write(path, "x").unwrap();
        }

        let selected = enforce_output_mode(
            base.to_string_lossy().as_ref(),
            vec![
                dual,
                dual_html,
                html.clone(),
                audit.clone(),
                md.clone(),
                mono.clone(),
            ],
            "mono",
            SystemTime::now(),
        )
        .unwrap();

        assert!(selected.contains(&mono));
        assert!(selected.contains(&md));
        assert!(selected.contains(&html));
        assert!(selected.contains(&audit));
        assert!(!selected.iter().any(|path| path.ends_with("-dual.pdf")));
        assert!(!selected.iter().any(|path| path.ends_with("-dual.html")));

        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn enforce_output_mode_drops_nonexistent_relative_stdout_paths() {
        let base = std::env::temp_dir().join(format!(
            "qdt_mode_relative_stdout_{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&base);
        let final_dir = base.join("paper-ko");
        std::fs::create_dir_all(&final_dir).unwrap();
        let final_mono = final_dir
            .join("paper-ko-mono.pdf")
            .to_string_lossy()
            .to_string();
        std::fs::write(&final_mono, "x").unwrap();

        let selected = enforce_output_mode(
            base.to_string_lossy().as_ref(),
            vec![r"tag-ko\paper-ko-mono.pdf".to_string()],
            "mono",
            SystemTime::now(),
        )
        .unwrap();

        let _ = std::fs::remove_dir_all(&base);
        assert_eq!(selected, vec![final_mono]);
    }

    #[test]
    fn enforce_output_mode_skips_qdt_agent_byproduct_mono() {
        // The agent extraction pass renders an intentionally-untranslated mono into
        // `.qdt-agent/<doc>/layout-extract/<doc>-ko`. enforce_output_mode re-scans the
        // output dir for the selected mode's PDFs; it must NOT pull that English
        // byproduct in, or validate_mono_outputs fails even though the real render is
        // correct (the `byproduct-validated-as-output` failure mode).
        let base = std::env::temp_dir().join(format!(
            "qdt_mode_skip_agent_{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&base);
        let final_dir = base.join("paper-ko");
        let byproduct_dir = base
            .join(".qdt-agent")
            .join("paper")
            .join("layout-extract")
            .join("paper-ko");
        std::fs::create_dir_all(&final_dir).unwrap();
        std::fs::create_dir_all(&byproduct_dir).unwrap();
        let final_mono = final_dir
            .join("paper-ko-mono.pdf")
            .to_string_lossy()
            .to_string();
        let byproduct_mono = byproduct_dir
            .join("paper-ko-mono.pdf")
            .to_string_lossy()
            .to_string();
        std::fs::write(&final_mono, "x").unwrap();
        std::fs::write(&byproduct_mono, "x").unwrap();

        let selected = enforce_output_mode(
            base.to_string_lossy().as_ref(),
            vec![final_mono.clone()],
            "mono",
            SystemTime::now(),
        )
        .unwrap();

        let _ = std::fs::remove_dir_all(&base);
        assert!(selected.contains(&final_mono));
        assert!(
            !selected.iter().any(|path| path.contains(".qdt-agent")),
            "agent-workspace byproduct must be skipped: {selected:?}"
        );
    }

    #[test]
    fn diagnose_failure_maps_known_failure_modes_to_cause_and_fix() {
        // Byproduct false-validation vs real "too much English" differ in cause text.
        let byproduct = diagnose_failure(
            r"mono output validation failed for C:\out\.qdt-agent\doc\layout-extract\doc-ko\doc-ko-mono.pdf: latin=12591, cjk=735. The PDF still contains too much English text.",
            1,
        )
        .unwrap();
        assert!(byproduct.summary.contains("영어"));
        assert!(byproduct.cause.contains(".qdt-agent") || byproduct.cause.contains("임시"));
        assert!(!byproduct.solution.is_empty());

        let real_english = diagnose_failure(
            r"mono output validation failed for C:\out\doc-ko\doc-ko-mono.pdf: latin=9000, cjk=200. The PDF still contains too much English text.",
            1,
        )
        .unwrap();
        assert!(!real_english.cause.contains(".qdt-agent"));

        // Timeout via exit code or message.
        assert_eq!(
            diagnose_failure("Codex CLI timed out after 180 seconds", 0).unwrap().summary,
            diagnose_failure("anything", 124).unwrap().summary
        );

        // No translatable tasks.
        assert!(diagnose_failure(NO_TRANSLATABLE_TASKS_MESSAGE, 0)
            .unwrap()
            .summary
            .contains("텍스트"));

        // Scanned PDF.
        assert!(diagnose_failure(
            "스캔 PDF 또는 이미지 기반 PDF는 현재 버전에서 지원하지 않습니다. 감지 정보: x",
            -2,
        )
        .unwrap()
        .summary
        .contains("스캔"));
    }

    #[test]
    fn diagnose_failure_is_none_for_success_and_paused_and_always_has_fields() {
        // Classifier contract: empty and user-paused are not failures. (Success
        // strings never reach it — call sites only invoke it when !ok.)
        assert!(diagnose_failure("", 0).is_none());
        assert!(diagnose_failure("번역이 일시 중단되었습니다", 0).is_none());

        // Unknown error still yields a complete, non-empty diagnosis (cause + fix).
        let generic = diagnose_failure("some unrecognized engine explosion", 1).unwrap();
        assert!(!generic.summary.is_empty());
        assert!(!generic.cause.is_empty());
        assert!(!generic.solution.is_empty());
    }

    #[test]
    fn agent_mono_with_mixed_language_pdf_uses_agent_cli_pipeline() {
        let mixed_inputs = vec![MixedLanguageInput {
            path: PathBuf::from(r"D:\docs\mixed.pdf"),
            report: "mixed.pdf / latin=6379 (65%), cjk=3423 (35%)".to_string(),
        }];

        let pipeline = select_translation_pipeline("agent", "mono", "codex-agent", mixed_inputs);

        assert!(matches!(pipeline, TranslationPipeline::AgentCliRunner));
    }

    #[test]
    fn agent_runner_args_include_manifest_fields() {
        let args = agent_runner_args(
            r"D:\out\.qdt-agent\paper\tasks.jsonl",
            r"D:\out\.qdt-agent\paper\translation-map.jsonl",
            "codex-agent",
            "true",
            "dual",
            "on",
            "quality-manufacturing",
            Some(r"D:\kb\glossary.csv"),
        );

        assert_eq!(args[0], "-m");
        assert_eq!(args[1], "qdt.agent_runner");
        assert!(args.contains(&"--task-output".to_string()));
        assert!(args.contains(&r"D:\out\.qdt-agent\paper\tasks.jsonl".to_string()));
        assert!(args.contains(&"--translation-map".to_string()));
        assert!(args.contains(&r"D:\out\.qdt-agent\paper\translation-map.jsonl".to_string()));
        assert!(args.contains(&"--engine".to_string()));
        assert!(args.contains(&"codex-agent".to_string()));
        assert!(args.contains(&"--quality".to_string()));
        assert!(args.contains(&"true".to_string()));
        assert!(args.contains(&"--review-mode".to_string()));
        assert!(args.contains(&"on".to_string()));
        assert!(args.contains(&"--output-mode".to_string()));
        assert!(args.contains(&"dual".to_string()));
        assert!(args.contains(&"--domain".to_string()));
        assert!(args.contains(&"quality-manufacturing".to_string()));
        assert!(args.contains(&"--glossary".to_string()));
        assert!(args.contains(&r"D:\kb\glossary.csv".to_string()));
        assert!(args.contains(&"--max-batch-items".to_string()));
        assert!(args.contains(&DIRECT_AGENT_BATCH_ITEMS.to_string()));
    }

    #[test]
    fn pdf_profile_rejects_scanned_or_image_only_pdf() {
        let profile = classify_pdf_document_profile(&PdfProfileStats {
            pages: 12,
            latin: 45,
            cjk: 0,
            image_pages: 12,
            low_text_pages: 12,
            scholarly_score: 0,
        });

        assert_eq!(profile, PdfDocumentProfile::ScannedUnsupported);
    }

    #[test]
    fn pdf_profile_detects_scholarly_text_pdf() {
        let profile = classify_pdf_document_profile(&PdfProfileStats {
            pages: 20,
            latin: 46_539,
            cjk: 0,
            image_pages: 8,
            low_text_pages: 1,
            scholarly_score: 10,
        });

        assert_eq!(profile, PdfDocumentProfile::ScholarlyText);
    }

    #[test]
    fn pdf_profile_keeps_plain_text_pdf_general() {
        let profile = classify_pdf_document_profile(&PdfProfileStats {
            pages: 20,
            latin: 46_539,
            cjk: 0,
            image_pages: 0,
            low_text_pages: 0,
            scholarly_score: 2,
        });

        assert_eq!(profile, PdfDocumentProfile::GeneralText);
    }

    #[test]
    fn pdf_profile_detects_mixed_language_pdf() {
        let profile = classify_pdf_document_profile(&PdfProfileStats {
            pages: 12,
            latin: 6_379,
            cjk: 3_423,
            image_pages: 2,
            low_text_pages: 0,
            scholarly_score: 1,
        });

        assert_eq!(profile, PdfDocumentProfile::MixedLanguage);
    }

    #[test]
    fn mono_output_quality_rejects_english_heavy_pdf() {
        let quality = MonoOutputQuality {
            latin: 3979,
            cjk: 4286,
        };

        assert!(!quality.is_acceptable());
    }

    #[test]
    fn mono_output_quality_accepts_korean_dominant_pdf() {
        let quality = MonoOutputQuality {
            latin: 120,
            cjk: 4286,
        };

        assert!(quality.is_acceptable());
    }

    #[test]
    fn mono_output_quality_accepts_scholarly_pdf_with_references_and_units() {
        let quality = MonoOutputQuality {
            latin: 7526,
            cjk: 11296,
        };

        assert!(quality.is_acceptable());
    }

    #[test]
    fn mono_output_quality_accepts_technical_slides_with_api_terms() {
        let quality = MonoOutputQuality {
            latin: 1702,
            cjk: 4730,
        };

        assert!(quality.is_acceptable());
    }

    #[test]
    fn default_scholar_translator_home_points_at_vendored_package() {
        let home = default_scholar_translator_home();
        let path = Path::new(&home);

        assert!(
            path.ends_with("services/scholar-translator")
                || path.ends_with(r"services\scholar-translator"),
            "expected vendored scholar-translator path, got {home}"
        );
        assert!(
            path.join("scholar_translator").join("cli.py").is_file(),
            "expected vendored scholar_translator/cli.py under {home}"
        );
    }

    #[test]
    fn wiki_cli_args_includes_command_flags_and_extras() {
        let args = wiki_cli_args("add-term", "/kb/domains", "q", &[("--source", "FMEA"), ("--target", "고장모드")]);
        assert_eq!(args[0], "add-term");
        assert!(args.contains(&"--kb".to_string()));
        assert!(args.contains(&"/kb/domains".to_string()));
        assert!(args.contains(&"--domain".to_string()));
        assert!(args.contains(&"q".to_string()));
        assert!(args.contains(&"--source".to_string()));
        assert!(args.contains(&"FMEA".to_string()));
        assert!(args.contains(&"--target".to_string()));
        assert!(args.contains(&"고장모드".to_string()));
    }

    #[test]
    fn shared_pack_install_writes_metadata_and_glossary() {
        let base = std::env::temp_dir().join(format!(
            "qdt_shared_pack_{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));

        let request = SharedPackInstallRequest {
            id: "official-quality-v1".to_string(),
            domain: "quality-manufacturing".to_string(),
            display_name: "Quality Pack".to_string(),
            version: "2026.07.04".to_string(),
            sha256: "test-sha".to_string(),
            glossary_csv: "source,target,notes\nFMEA,고장모드,\n".to_string(),
            terms: 1,
        };

        let installed = install_shared_pack_at(&base, request).unwrap();
        let pack_dir = base.join("shared").join("packs").join("official-quality-v1");

        assert_eq!(installed.id, "official-quality-v1");
        assert_eq!(installed.domain, "quality-manufacturing");
        assert_eq!(installed.display_name, "Quality Pack");
        assert_eq!(installed.terms, 1);
        assert!(pack_dir.join("pack.json").exists());
        assert_eq!(
            std::fs::read_to_string(pack_dir.join("glossary.csv")).unwrap(),
            "source,target,notes\nFMEA,고장모드,\n"
        );
        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn shared_pack_paths_are_domain_scoped_and_sorted() {
        let base = std::env::temp_dir().join(format!(
            "qdt_shared_paths_{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));

        install_shared_pack_at(&base, SharedPackInstallRequest {
            id: "b-pack".to_string(),
            domain: "quality-manufacturing".to_string(),
            display_name: "B".to_string(),
            version: "1".to_string(),
            sha256: "b".to_string(),
            glossary_csv: "source,target,notes\nB,비,\n".to_string(),
            terms: 1,
        }).unwrap();
        install_shared_pack_at(&base, SharedPackInstallRequest {
            id: "a-pack".to_string(),
            domain: "medical-device".to_string(),
            display_name: "A".to_string(),
            version: "1".to_string(),
            sha256: "a".to_string(),
            glossary_csv: "source,target,notes\nA,에이,\n".to_string(),
            terms: 1,
        }).unwrap();

        let paths = shared_glossary_paths_for_domain(&base, "quality-manufacturing");

        assert_eq!(paths.len(), 1);
        assert!(paths[0].ends_with("glossary.csv"));
        assert!(paths[0].ends_with("shared/packs/b-pack/glossary.csv") || paths[0].ends_with(r"shared\packs\b-pack\glossary.csv"));
        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn delete_domain_at_backs_up_then_removes_domain_and_returns_remaining_infos() {
        let base = std::env::temp_dir().join(format!(
            "qdt_delete_domain_{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));
        let keep = base.join("domains").join("keep");
        let remove = base.join("domains").join("remove-me");
        std::fs::create_dir_all(&keep).unwrap();
        std::fs::create_dir_all(&remove).unwrap();
        std::fs::write(keep.join("glossary.csv"), "source,target,notes\nA,B,\n").unwrap();
        std::fs::write(remove.join("glossary.csv"), "source,target,notes\nX,Y,\n").unwrap();

        let result = delete_domain_at(&base, "remove-me").unwrap();
        let domains = result.domains;
        let backup = PathBuf::from(result.backup_path);

        assert!(!remove.exists());
        assert!(keep.exists());
        assert!(backup.exists());
        assert!(backup.join("glossary.csv").exists());
        assert_eq!(
            std::fs::read_to_string(backup.join("glossary.csv")).unwrap(),
            "source,target,notes\nX,Y,\n"
        );
        assert_eq!(domains.len(), 1);
        assert_eq!(domains[0].slug, "keep");
        assert_eq!(domains[0].terms, 1);
        let _ = std::fs::remove_dir_all(&base);
    }

    #[test]
    fn delete_domain_at_refuses_to_remove_the_last_domain() {
        let base = std::env::temp_dir().join(format!(
            "qdt_delete_last_domain_{}",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ));
        let only = base.join("domains").join("only");
        std::fs::create_dir_all(&only).unwrap();
        std::fs::write(only.join("glossary.csv"), "source,target,notes\n").unwrap();

        let result = delete_domain_at(&base, "only");

        assert!(result.is_err());
        assert!(only.exists());
        let _ = std::fs::remove_dir_all(&base);
    }
}


#[cfg(all(test,windows))]
mod safety_runtime_tests {
    use super::*;
    #[test]
    fn timeout_keeps_diagnostic_files_and_returns_a_named_code() {
        let mut command=Command::new("powershell.exe");
        command.args(["-NoProfile","-Command","Write-Output 'fixture-log'; Start-Sleep -Seconds 15"]);
        let start=std::time::Instant::now();
        let (_,message,code)=run_command_with_timeout(&mut command,Duration::from_millis(500)).unwrap();
        assert_eq!(code,124);
        assert!(start.elapsed()<Duration::from_secs(7));
        assert!(message.contains("[QDT_PROCESS_TIMEOUT]"));
        let paths=message.split("로그: ").nth(1).unwrap().split(" / ").collect::<Vec<_>>();
        assert_eq!(paths.len(),2);
        assert!(paths.iter().all(|p|Path::new(p).is_file()));
    }
    #[test]
    fn cancellation_stops_a_running_subprocess_and_keeps_logs() {
        let _serial=job_control::TEST_JOB_LOCK.lock().unwrap();
        let _guard=job_control::JobGuard::acquire().unwrap();
        let cancel=std::thread::spawn(||{std::thread::sleep(Duration::from_millis(500));job_control::cancel();});
        let mut command=Command::new("powershell.exe");
        command.args(["-NoProfile","-Command","Start-Sleep -Seconds 15"]);
        let start=std::time::Instant::now();
        let (_,message,code)=run_translation_command_with_timeout(&mut command,Duration::from_secs(20)).unwrap();
        cancel.join().unwrap();
        assert_eq!(code,130);
        assert!(start.elapsed()<Duration::from_secs(7));
        assert!(message.contains("[QDT_CANCELLED]"));
        assert!(message.split("로그: ").nth(1).unwrap().split(" / ").all(|p|Path::new(p).is_file()));
    }
    #[test]
    fn input_scan_skips_generated_trees_while_artifact_scan_keeps_final_files() {
        let stamp=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let root=qdt_runtime_tmp().join(format!("input-scan-{stamp}"));
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("source.pdf"),b"source").unwrap();
        for name in ["QDT_Output",".qdt-agent",".qdt-home","custom-generated"] {
            let dir=root.join(name);fs::create_dir_all(&dir).unwrap();
            fs::write(dir.join("result.pdf"),b"result").unwrap();
            if name=="custom-generated" {fs::write(dir.join(".qdt-output"),b"QDT").unwrap();}
        }
        let inputs=collect_files_by_extension(&root,&["pdf"]);
        assert_eq!(inputs,vec![root.join("source.pdf")]);
        let artifacts=scan_recent_artifact_outputs(root.join("custom-generated").to_str().unwrap(),UNIX_EPOCH);
        assert_eq!(artifacts.len(),1);
    }
}

#[cfg(test)]
mod output_ownership_tests {
    use super::*;
    #[test]
    fn stdout_paths_outside_job_directory_are_not_selected_or_modified() {
        let stamp=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let base=qdt_runtime_tmp().join(format!("output-owner-{stamp}"));
        let owned=base.join("owned");fs::create_dir_all(&owned).unwrap();
        let original=base.join("original-mono.pdf");fs::write(&original,b"original").unwrap();
        let result=owned.join("new-mono.pdf");fs::write(&result,b"result").unwrap();
        let selected=enforce_output_mode(owned.to_str().unwrap(),vec![original.to_string_lossy().into_owned(),result.to_string_lossy().into_owned()],"mono",UNIX_EPOCH).unwrap();
        assert_eq!(selected,vec![result.to_string_lossy().to_string()]);
        assert_eq!(fs::read(original).unwrap(),b"original");
    }
}

#[cfg(test)]
mod final_output_repair_tests {
    use super::*;
    #[test]
    fn missing_audit_is_an_explicit_review_problem() {
        let path=std::env::temp_dir().join(format!("qdt-missing-audit-{}.json",std::process::id()));
        let items=read_review_items_from_audit(&path);
        assert_eq!(items.len(),1);
        assert_eq!(items[0].kind,"audit_unavailable");
        assert_eq!(items[0].status,"open");
    }
    #[test]
    fn dual_validation_inspects_only_the_translated_right_half() {
        let _serial=job_control::TEST_JOB_LOCK.lock().unwrap();
        let _guard=job_control::JobGuard::acquire().unwrap();
        let python=std::env::var("QDT_TEST_PYTHON").unwrap_or_else(|_|"python".to_string());
        let root=qdt_runtime_tmp().join(format!("dual-quality-{}",SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        fs::create_dir_all(&root).unwrap();
        let good=root.join("good-dual.pdf");
        let bad=root.join("bad-dual.pdf");
        let script=r#"
import fitz,sys
for path,korean in [(sys.argv[1],True),(sys.argv[2],False)]:
    d=fitz.open();p=d.new_page(width=600,height=500)
    for row in range(10):
        p.insert_text((10,30+row*35),'Original English text for comparison.',fontsize=10)
        p.insert_text((310,30+row*35),'\ud55c\uad6d\uc5b4 \ubc88\uc5ed \uacb0\uacfc \ubb38\uc11c \ud655\uc778 \uc644\ub8cc' if korean else 'English was never translated.',fontname='korea' if korean else 'helv',fontsize=10)
    d.save(path);d.close()
"#;
        let (_,stderr,code)=run_translation_command_with_timeout(
            Command::new(&python).arg("-c").arg(script).arg(&good).arg(&bad),Duration::from_secs(30)).unwrap();
        assert_eq!(code,0,"{}",stderr);
        let quality=inspect_pdf_language_quality_mode(&python,good.to_str().unwrap(),true).unwrap();
        assert_eq!(quality.latin,0);
        assert!(quality.cjk>=100);
        assert!(validate_mono_outputs(&python,&[good.to_string_lossy().to_string()],"dual").is_ok());
        assert!(validate_mono_outputs(&python,&[bad.to_string_lossy().to_string()],"dual").is_err());
    }

    #[test]
    fn unresolved_fragments_are_shown_before_generic_candidates() {
        let path=qdt_runtime_tmp().join(format!("review-priority-{}.layout-audit.json",
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        fs::write(&path,r#"{"pages":[{"page":1,"replacements":[
            {"source_preview":"Ordinary candidate","translated_preview":"번역","severity":"info"},
            {"source_preview":"Blocked phrase","translated_preview":"Blocked phrase",
             "kind":"translation_incomplete","severity":"error","status":"open","fitted":false}
        ]}]}"#).unwrap();
        let items=collect_review_items_from_outputs(&[path.to_string_lossy().to_string()]);
        assert_eq!(items[0].kind,"translation_incomplete");
        assert_eq!(items[0].status,"open");
        assert_eq!(items[0].page,1);
    }

}
