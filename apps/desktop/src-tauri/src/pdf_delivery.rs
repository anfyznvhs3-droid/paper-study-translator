use std::{fs, path::{Path,PathBuf}, collections::BTreeSet, io::{Read,Seek,Write}};

/// Public delivery copies only PDFs, preserving review sidecars and originals.
pub fn publish_pdfs(root:&Path,paths:Vec<String>)->(Vec<String>,Vec<String>) {
    let mut outputs=Vec::new();let mut errors=Vec::new();let mut seen=BTreeSet::new();
    for path in paths {
        if !path.to_ascii_lowercase().ends_with(".pdf") {continue;}
        let key=fs::canonicalize(&path).unwrap_or_else(|_|PathBuf::from(&path));
        if !seen.insert(key) {continue;}
        match publish_one(root,Path::new(&path)) {
            Ok(path)=>outputs.push(shell_path(&path)),
            Err(error)=>errors.push(format!("[QDT_PDF_DELIVERY] PDF 결과를 저장하지 못했습니다: {error}")),
        }
    }
    (outputs,errors)
}
fn shell_path(path:&Path)->String {
    let text=path.to_string_lossy();
    if let Some(unc)=text.strip_prefix(r"\\?\UNC\") {return format!(r"\\{unc}");}
    text.strip_prefix(r"\\?\").unwrap_or(&text).to_string()
}
fn publish_one(root:&Path,source:&Path)->Result<PathBuf,String> {
    let root=root.canonicalize().map_err(|e|e.to_string())?;
    let source=source.canonicalize().map_err(|e|e.to_string())?;
    if !source.starts_with(&root) || !source.is_file() {return Err("작업 폴더 밖의 파일은 결과로 복사하지 않습니다.".into());}
    let mut input=fs::File::open(&source).map_err(|e|e.to_string())?;
    let mut header=[0u8;5];input.read_exact(&mut header).map_err(|e|e.to_string())?;
    if &header!=b"%PDF-" {return Err("PDF 형식이 아닌 파일입니다.".into());}
    input.rewind().map_err(|e|e.to_string())?;
    let delivery=root.join("PDF");fs::create_dir_all(&delivery).map_err(|e|e.to_string())?;
    let delivery=delivery.canonicalize().map_err(|e|e.to_string())?;
    if !delivery.starts_with(&root) {return Err("PDF 저장 폴더가 작업 폴더 밖을 가리킵니다.".into());}
    if source.parent()==Some(delivery.as_path()) {return Ok(source);}
    let stem=source.file_stem().and_then(|s|s.to_str()).unwrap_or("translated");
    for index in 1..10_000 {
        let name=if index==1 {format!("{stem}.pdf")} else {format!("{stem}-{index}.pdf")};
        let destination=delivery.join(name);
        match fs::OpenOptions::new().write(true).create_new(true).open(&destination) {
            Ok(mut output)=>{
                let copied=std::io::copy(&mut input,&mut output).and_then(|_|output.flush()).and_then(|_|output.sync_all());
                drop(output);
                if let Err(error)=copied {let _=fs::remove_file(&destination);return Err(error.to_string());}
                return Ok(destination);
            }
            Err(error) if error.kind()==std::io::ErrorKind::AlreadyExists=>continue,
            Err(error)=>return Err(error.to_string()),
        }
    }
    Err("같은 이름의 PDF가 너무 많습니다. 기존 결과는 보존했습니다.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn root()->PathBuf {
        let path=std::env::temp_dir().join(format!("qdt-pdf-delivery-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        fs::create_dir_all(path.join("input")).unwrap();path
    }
    #[test]
    fn only_pdf_is_published_and_internal_review_file_is_preserved() {
        let root=root();let pdf=root.join("input/result.pdf");let audit=root.join("input/result.layout-audit.json");
        fs::write(&pdf,b"%PDF-1.7\noriginal bytes").unwrap();fs::write(&audit,b"{\"review_items\":[]}").unwrap();
        let (files,errors)=publish_pdfs(&root,vec![pdf.display().to_string(),audit.display().to_string(),pdf.display().to_string()]);
        assert!(errors.is_empty());assert_eq!(files.len(),1);assert_eq!(fs::read(&files[0]).unwrap(),fs::read(&pdf).unwrap());
        assert!(audit.exists());assert_eq!(fs::read_dir(root.join("PDF")).unwrap().count(),1);
    }
    #[test]
    fn duplicate_names_never_overwrite_an_existing_pdf() {
        let root=root();fs::create_dir_all(root.join("second")).unwrap();
        let a=root.join("input/same.pdf");let b=root.join("second/same.pdf");
        fs::write(&a,b"%PDF-1.7 first").unwrap();fs::write(&b,b"%PDF-1.7 second").unwrap();
        let (files,errors)=publish_pdfs(&root,vec![a.display().to_string(),b.display().to_string()]);
        assert!(errors.is_empty());assert_eq!(files.len(),2);assert_ne!(files[0],files[1]);
        assert_eq!(fs::read(&files[0]).unwrap(),b"%PDF-1.7 first");assert_eq!(fs::read(&files[1]).unwrap(),b"%PDF-1.7 second");
    }
    #[test]
    fn invalid_or_external_pdf_does_not_hide_a_valid_partial_result() {
        let outside=root().join("input/outside.pdf");let root=root();
        let good=root.join("input/good.pdf");let bad=root.join("input/bad.pdf");
        fs::write(&good,b"%PDF-1.7 valid").unwrap();fs::write(&bad,b"not a pdf").unwrap();fs::write(&outside,b"%PDF-1.7 external").unwrap();
        let (files,errors)=publish_pdfs(&root,vec![good.display().to_string(),bad.display().to_string(),outside.display().to_string()]);
        assert_eq!(files.len(),1);assert_eq!(errors.len(),2);assert!(outside.exists());
    }
    #[test]
    fn json_only_success_has_no_public_pdf() {
        let root=root();let audit=root.join("input/a.layout-audit.json");fs::write(&audit,b"{}").unwrap();
        let (files,errors)=publish_pdfs(&root,vec![audit.display().to_string()]);assert!(files.is_empty());assert!(errors.is_empty());
    }
}
