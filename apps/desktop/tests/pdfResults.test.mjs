import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";
const { pdfResults }=loadTsModule(fileURLToPath(new URL("../src/translation/pdfResults.ts",import.meta.url)));

test("legacy mixed outputs show only unique PDFs and preserve the stored record",()=>{
 const paths=['F:\\out\\a-dual.pdf','F:\\out\\a-dual.layout-audit.json','F:\\out\\a.md','F:\\out\\a.html','F:\\out\\a.pptx','F:\\out\\B.PDF','F:/out/a-dual.pdf'];
 const before=JSON.stringify(paths);
 assert.deepEqual(Array.from(pdfResults(paths)),[paths[0],paths[5]]);
 assert.equal(JSON.stringify(paths),before);
});
test("audit-only results do not count as a generated PDF",()=>{
 assert.equal(pdfResults(['F:\\a.layout-audit.json','F:\\a.pdf.json']).length,0);
 assert.equal(pdfResults([]).length,0);
});
