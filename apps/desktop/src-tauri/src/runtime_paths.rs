//! Read-only installation resources and per-user writable data are separate.
use std::{fs, io::{self, Write}, path::{Path, PathBuf}};

pub fn find_asset_root(executable: &Path) -> Option<PathBuf> {
    for parent in executable.parent()?.ancestors().take(6) {
        for candidate in [parent.to_path_buf(), parent.join("resources")] {
            if candidate.join("services/scholar-translator/scholar_translator/cli.py").is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

pub fn asset_root() -> PathBuf {
    if let Some(path) = std::env::var_os("QDT_RESOURCE_ROOT").filter(|v| !v.is_empty()) {
        return PathBuf::from(path);
    }
    let executable = std::env::current_exe().unwrap_or_default();
    if let Some(root) = find_asset_root(&executable) { return root; }
    #[cfg(debug_assertions)]
    { return Path::new(env!("CARGO_MANIFEST_DIR")).join("../../.."); }
    #[cfg(not(debug_assertions))]
    { executable.parent().unwrap_or(Path::new(".")).to_path_buf() }
}

pub fn data_root() -> PathBuf {
    if let Some(path) = std::env::var_os("QDT_HOME").filter(|v| !v.is_empty()) { return path.into(); }
    if let Some(path) = std::env::var_os("LOCALAPPDATA").filter(|v| !v.is_empty()) {
        return PathBuf::from(path).join("PaperStudyTranslator");
    }
    asset_root().join(".qdt-home")
}

pub fn bundled_python(root: &Path) -> Option<PathBuf> {
    [root.join("runtime/python/python.exe"), root.join(".venv/Scripts/python.exe")]
        .into_iter().find(|p| p.is_file())
}

/// Copy only missing seed files. User edits always win during an upgrade.
pub fn seed_knowledge(source: &Path, destination: &Path) -> io::Result<()> {
    fs::create_dir_all(destination)?;
    for item in fs::read_dir(source)? {
        let item=item?;
        if item.file_type()?.is_symlink() { continue; }
        let target=destination.join(item.file_name());
        if item.file_type()?.is_dir() { seed_knowledge(&item.path(), &target)?; }
        else {
            match fs::OpenOptions::new().write(true).create_new(true).open(&target) {
                Ok(mut file) => { file.write_all(&fs::read(item.path())?)?; }
                Err(err) if err.kind()==io::ErrorKind::AlreadyExists => {}
                Err(err) => return Err(err),
            }
        }
    }
    Ok(())
}

pub fn initialize() -> io::Result<()> {
    let data=data_root();fs::create_dir_all(&data)?;
    if std::env::var_os("QDT_KNOWLEDGE_BASE").is_none() {
        seed_knowledge(&asset_root().join("knowledge-base"), &data.join("knowledge-base"))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn temporary() -> PathBuf {
        std::env::temp_dir().join(format!("pst-paths-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()))
    }
    #[test]
    fn relocated_resources_and_python_are_resolved_from_executable() {
        let root=temporary().join("another location");
        fs::create_dir_all(root.join("services/scholar-translator/scholar_translator")).unwrap();
        fs::write(root.join("services/scholar-translator/scholar_translator/cli.py"),"").unwrap();
        fs::create_dir_all(root.join("runtime/python")).unwrap();
        fs::write(root.join("runtime/python/python.exe"),"").unwrap();
        assert_eq!(find_asset_root(&root.join("PaperStudyTranslator.exe")),Some(root.clone()));
        assert_eq!(bundled_python(&root),Some(root.join("runtime/python/python.exe")));
        assert!(find_asset_root(&temporary().join("missing.exe")).is_none());
        fs::remove_dir_all(root.parent().unwrap()).unwrap();
    }
    #[test]
    fn initialization_preserves_existing_user_glossary() {
        let root=temporary();let seed=root.join("seed");let data=root.join("user");
        fs::create_dir_all(&seed).unwrap();fs::create_dir_all(&data).unwrap();
        fs::write(seed.join("glossary.csv"),"seed").unwrap();fs::write(data.join("glossary.csv"),"user edits").unwrap();
        fs::write(seed.join("new-rule.md"),"new rule").unwrap();
        seed_knowledge(&seed,&data).unwrap();
        assert_eq!(fs::read_to_string(data.join("glossary.csv")).unwrap(),"user edits");
        assert_eq!(fs::read_to_string(data.join("new-rule.md")).unwrap(),"new rule");
        fs::remove_dir_all(root).unwrap();
    }
}
