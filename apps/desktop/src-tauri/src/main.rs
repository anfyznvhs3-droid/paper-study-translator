#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]
fn main() {
    let args: Vec<_> = std::env::args_os().collect();
    if args.get(1).is_some_and(|arg| arg == "--check-runtime") {
        let report = args.get(2).map(std::path::PathBuf::from)
            .unwrap_or_else(|| std::env::temp_dir().join("PaperStudyTranslator-check.json"));
        std::process::exit(quality_doc_translator_desktop_lib::check_runtime(&report));
    }
    quality_doc_translator_desktop_lib::run()
}
