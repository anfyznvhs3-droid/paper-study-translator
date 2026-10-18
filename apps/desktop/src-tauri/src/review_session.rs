use base64::Engine;
use serde_json::Value;
use std::{fs,path::Path,time::{SystemTime,UNIX_EPOCH}};
const MAX_BYTES:usize=8*1024*1024;
fn encode(value:&Value)->Result<(String,Vec<u8>),String> {
    if value.get("version").and_then(Value::as_u64)!=Some(1) {return Err("[QDT_SESSION_SCHEMA] 저장 형식 버전이 올바르지 않습니다.".into());}
    let id=value.pointer("/state/runId").and_then(Value::as_str).unwrap_or("");
    if id.is_empty() || id.len()>100 || !id.chars().all(|c|c.is_ascii_alphanumeric() || c=='-') {
        return Err("[QDT_SESSION_SCHEMA] 작업 식별자가 올바르지 않습니다.".into());
    }
    let bytes=serde_json::to_vec(value).map_err(|_|"[QDT_SESSION_WRITE] 검수 기록을 저장하지 못했습니다.")?;
    if bytes.len()>MAX_BYTES {return Err("[QDT_SESSION_LIMIT] 검수 기록이 저장 한도(8MB)를 넘었습니다. 결과 파일과 후보 수를 확인하세요.".into());}
    Ok((id.into(),bytes))
}
fn atomic_write(path:&Path,bytes:&[u8])->Result<(),String>{
    let stamp=SystemTime::now().duration_since(UNIX_EPOCH).map_err(|_|"Clock error")?.as_nanos();
    let temporary=path.with_extension(format!("{stamp}.tmp"));
    fs::write(&temporary,bytes).map_err(|_|"[QDT_SESSION_WRITE] 검수 기록을 저장하지 못했습니다.")?;
    fs::rename(&temporary,path).map_err(|_|"[QDT_SESSION_WRITE] 검수 기록 교체에 실패했습니다.")?;
    Ok(())
}
pub fn save_at(root:&Path,value:Option<Value>)->Result<(),String>{
    let latest=root.join("review-session.json");
    let Some(value)=value else {
        if latest.exists(){fs::remove_file(latest).map_err(|_|"[QDT_SESSION_WRITE] 최근 작업 표시를 지우지 못했습니다.")?;}
        return Ok(());
    };
    let (id,plain)=encode(&value)?;
    let cipher=crate::engine_settings::protect_bytes(&plain,true)
        .map_err(|_|"[QDT_SESSION_PROTECTION] 이 Windows 계정으로 검수 기록을 보호하지 못했습니다.")?;
    let bytes=serde_json::to_vec(&serde_json::json!({"protected":true,"version":1,
        "ciphertext":base64::engine::general_purpose::STANDARD.encode(cipher)}))
        .map_err(|_|"[QDT_SESSION_WRITE] 검수 기록을 저장하지 못했습니다.")?;
    let history=root.join("review-history");
    fs::create_dir_all(&history).map_err(|_|"[QDT_SESSION_WRITE] 검수 기록 폴더를 만들지 못했습니다.")?;
    atomic_write(&history.join(format!("{id}.json")),&bytes)?;
    atomic_write(&latest,&bytes)
}
pub fn load_at(root:&Path)->Result<Option<Value>,String>{
    let latest=root.join("review-session.json");
    if !latest.exists(){return Ok(None);}
    if fs::metadata(&latest).map_err(|_|"[QDT_SESSION_READ] 검수 기록을 확인하지 못했습니다.")?.len()>(MAX_BYTES*2) as u64 {
        return Err("[QDT_SESSION_LIMIT] 저장된 검수 기록이 너무 큽니다. 새 작업을 시작할 수 있습니다.".into());
    }
    let stored:Value=serde_json::from_slice(&fs::read(latest).map_err(|_|"[QDT_SESSION_READ] 검수 기록을 읽지 못했습니다.")?)
        .map_err(|_|"[QDT_SESSION_READ] 이전 검수 기록이 손상됐습니다. 새 작업을 시작할 수 있습니다.")?;
    let value=if stored.get("protected").and_then(Value::as_bool)==Some(true) {
        let cipher=base64::engine::general_purpose::STANDARD.decode(stored.get("ciphertext").and_then(Value::as_str).unwrap_or(""))
            .map_err(|_|"[QDT_SESSION_READ] 검수 기록이 손상됐습니다.")?;
        let plain=crate::engine_settings::protect_bytes(&cipher,false)
            .map_err(|_|"[QDT_SESSION_PROTECTION] 이 Windows 계정에서 이전 검수 기록을 열지 못했습니다.")?;
        serde_json::from_slice(&plain).map_err(|_|"[QDT_SESSION_READ] 검수 기록을 읽지 못했습니다.")?
    } else {stored};
    encode(&value)?;
    Ok(Some(value))
}
#[cfg(test)]
mod tests{
    use super::*;
    fn root()->std::path::PathBuf{std::env::temp_dir().join(format!("qdt-review-test-{}",SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()))}
    #[test]
    fn decisions_survive_reload_and_new_task_keeps_history(){
        let root=root();
        let value=serde_json::json!({"version":1,"state":{"runId":"run-123","lastRunResult":{"reviewItems":[{"status":"approved","source_text":"fixture"}]}}});
        save_at(&root,Some(value.clone())).unwrap();
        assert!(!fs::read_to_string(root.join("review-session.json")).unwrap().contains("fixture"));
        assert_eq!(load_at(&root).unwrap(),Some(value));
        save_at(&root,None).unwrap();
        assert!(load_at(&root).unwrap().is_none());
        assert!(root.join("review-history/run-123.json").exists());
    }
    #[test]
    fn session_identifier_cannot_escape_storage_root(){
        let root=root();
        assert!(save_at(&root,Some(serde_json::json!({"version":1,"state":{"runId":"../outside"}}))).is_err());
        assert!(!root.exists());
    }
}
