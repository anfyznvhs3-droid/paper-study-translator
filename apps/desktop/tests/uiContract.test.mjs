import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { loadTsModule } from "./helpers/loadTsModule.mjs";
const load = () => loadTsModule(fileURLToPath(new URL("../src/state/projectState.ts", import.meta.url)));
function prepared(r, initial) {
 return r(initial,{type:"addSourceItems",inputMode:"file",items:[
  {name:"a.pdf",relativePath:"D:\\a.pdf",kind:"file"},
  {name:"b.pdf",relativePath:"D:\\b.pdf",kind:"file"}]});
}
test("excluding a mistaken input preserves the remaining document and moves active selection",()=>{
 const {projectReducer:r,initialProjectState:initial}=load();
 const state=prepared(r,initial),first=state.files[0],second=state.files[1];
 const next=r(state,{type:"removeSourceItem",id:first.id});
 assert.deepEqual(next.files,[second]);
 assert.equal(next.activeJobId,second.id);
 assert.equal(state.files.length,2);
 const empty=r(next,{type:"removeSourceItem",id:second.id});
 assert.equal(empty.files.length,0);
 assert.equal(empty.activeJobId,null);
});
test("input removal cannot mutate a running job or a saved result",()=>{
 const {projectReducer:r,initialProjectState:initial}=load();
 const state=prepared(r,initial);
 const running=r(state,{type:"startMockJob"});
 assert.equal(r(running,{type:"removeSourceItem",id:running.files[0].id}),running);
 const done=r(running,{type:"finishMockJob",status:"success",outputFiles:["a.pdf"],reviewItems:[]});
 assert.equal(r(done,{type:"removeSourceItem",id:done.files[0].id}),done);
});
