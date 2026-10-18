/** Public deliverables are PDFs; audit data remains an internal review input. */
export function pdfResults(paths: readonly string[]): string[] {
  const seen=new Set<string>();
  return paths.filter((path)=>{
    const key=path.replace(/\\/g,"/").toLowerCase();
    if(!key.endsWith(".pdf") || seen.has(key))return false;
    seen.add(key);return true;
  });
}
export function fileLabel(path:string):string {
  return path.replace(/\\/g,"/").split("/").filter(Boolean).pop()??path;
}
