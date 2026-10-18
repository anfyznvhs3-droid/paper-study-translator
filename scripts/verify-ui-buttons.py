from pathlib import Path
import functools,http.server,json,os,re,threading,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('QDT_UI_EVIDENCE_DIR',ROOT/'검증자료'/'20261017-버튼통일'/'browser'))
OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'apps/desktop/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
mock=(ROOT/'apps/desktop/node_modules/@tauri-apps/api/mocks.js').read_text().rsplit('export {',1)[0]
init=mock+r'''
mockWindows("main");
window.__QA__={calls:[],request:null,finish:null,failSave:false};
mockIPC(async(command,args)=>{
 const qa=window.__QA__;qa.calls.push(command);
 if(command==="get_engine_settings")return {provider:"Gemini Developer API",model:"gemini-2.5-flash-lite",has_api_key:true,has_saved_key:true,key_source:"saved"};
 if(command==="load_review_session"){const raw=localStorage.getItem("qa-review-session");return raw?JSON.parse(raw):null;}
 if(command==="save_review_session"){
   if(qa.failSave)throw new Error("fixture disk write failure");
   if(args.snapshot)localStorage.setItem("qa-review-session",JSON.stringify(args.snapshot));
   else localStorage.removeItem("qa-review-session");
   return null;
 }
 if(command==="plugin:dialog|open")return ["D:\\QA-fixtures\\a.pdf","D:\\QA-fixtures\\b.pdf"];
 if(command==="run_translation_job") {
  qa.request=args.request;
  await window.__TAURI_INTERNALS__.invoke("plugin:event|emit",{event:"translation-target",payload:{source_path:args.request.files[0],status:"running",message:"fixture",output_files:[]}});
  await window.__TAURI_INTERNALS__.invoke("plugin:event|emit",{event:"translation-progress",payload:{phase:"translate"}});
  return new Promise(resolve=>{qa.finish=resolve;});
 }
 if(command==="cancel_translation_job"){
  qa.finish({ok:false,exit_code:130,message:"[QDT_CANCELLED] 사용자가 번역을 중지했습니다.",output_dir:"D:\\QA-fixtures\\QDT_Output\\run-cancel",output_files:[],review_items:[],
   target_results:qa.request.files.map((source_path,i)=>({source_path,status:i?"skipped":"cancelled",message:i?"not run":"cancelled",output_files:[]}))});
  return true;
 }
 if(command==="wiki_list_domains")return [{slug:"quality-manufacturing",name:"품질·제조",glossary_count:0,candidate_count:0}];
 if(command==="wiki_list_shared_packs")return [];
 if(command.startsWith("wiki_"))return "[]";
 return null;
},{shouldMockEvents:true});
'''
report={'scope':'Production frontend in isolated Chrome; official Tauri IPC mocks, not native integration or live translation','screens':[],'errors':[]}
def select_choice(page,control,value):
 control.click()
 page.locator('[role="option"][data-value="'+value+'"]').click()

def capture(page,name):
 page.evaluate('scrollTo(0,0)')
 page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
 (OUT/(name+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
 metrics=page.evaluate(r"""() => {
 const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
 const els=[...document.querySelectorAll('button,input,select,textarea,a[href],summary')].filter(visible);
 return {
 width:innerWidth, scrollWidth:document.documentElement.scrollWidth,
 borderedButtons:els.filter(e=>e.tagName==='BUTTON'&&['Top','Right','Bottom','Left'].some(side=>parseFloat(getComputedStyle(e)['border'+side+'Width'])>0)).map(e=>({text:e.textContent?.trim().slice(0,50),classes:e.className})),
 actionSizes:els.filter(e=>e.matches('.primary-button,.secondary-button')).map(e=>({text:e.textContent?.trim().slice(0,30),height:e.getBoundingClientRect().height,font:getComputedStyle(e).fontSize,radius:getComputedStyle(e).borderRadius})),

 activeNav:[...document.querySelectorAll('.sidebar-nav button[aria-current]')].map(e=>e.textContent),
 smallTargets:els.filter(e=>{const r=e.getBoundingClientRect();return r.width<24||r.height<24}).map(e=>({text:e.textContent?.slice(0,60),tag:e.tagName,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})),
 unlabelledInputs:els.filter(e=>['INPUT','SELECT','TEXTAREA'].includes(e.tagName)&&!e.labels?.length&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')).map(e=>e.outerHTML.slice(0,180)),
 radios:[...document.querySelectorAll('[role=radiogroup]')].map(e=>({name:e.getAttribute('aria-label'),radios:e.querySelectorAll('[role=radio],input[type=radio]').length,buttons:e.querySelectorAll('button').length})),
 controls:els.slice(0,80).map(e=>{const s=getComputedStyle(e);return {text:e.textContent?.trim().slice(0,45),font:s.fontSize,radius:s.borderRadius,height:Math.round(e.getBoundingClientRect().height)}})
 };}""")
 report['screens'].append({'name':name,**metrics})
def choose(page):
 page.get_by_role('dialog').get_by_role('button',name='Gemini 번역으로 시작',exact=True).click()
 page.get_by_role('heading',name='번역 준비',exact=True).wait_for()
def start(page):
 page.get_by_role('button',name='파일 선택',exact=True).click()
 page.get_by_role('button',name='번역 시작',exact=True).click()
 page.wait_for_function('window.__QA__.finish!==null')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
  ctx=browser.new_context(viewport={'width':1280,'height':820},reduced_motion='reduce')
  ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
  ctx.add_init_script(init)
  page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
  page.goto(origin,wait_until='networkidle');page.get_by_role('dialog').wait_for();capture(page,'mode')
  choose(page);capture(page,'setup')
  for width in [960,640]:
   page.set_viewport_size({'width':width,'height':820});capture(page,f'setup-{width}')
  page.set_viewport_size({'width':1280,'height':820})
  page.get_by_role('button',name='파일 선택',exact=True).click()
  select_choice(page,page.get_by_role('combobox',name='출력 방식'),'dual')
  select_choice(page,page.get_by_role('combobox',name='검수 방식'),'off')
  assert page.get_by_role('button',name='a.pdf 목록에서 제외').count()==1
  assert page.get_by_role('button',name='b.pdf 목록에서 제외').count()==1
  select_choice(page,page.get_by_role('combobox',name='검수 방식'),'on')
  capture(page,'setup-selected')
  report['direct_settings_preserve_files']=True
  for label,slug in [('설정','settings'),('FEEDBACK|피드백','feedback'),('용어집','glossary')]:
   page.locator('.sidebar-nav').get_by_role('button',name=re.compile(label)).click()
   page.wait_for_timeout(300)
   capture(page,slug)
  page.locator('.sidebar-nav').get_by_role('button',name=re.compile('작업 현황')).click()
  start(page);capture(page,'progress')
  report['submitted_request']=page.evaluate('({output:window.__QA__.request.output_mode,review:window.__QA__.request.review_mode,files:window.__QA__.request.files.length})')
  assert report['submitted_request']=={'output':'dual','review':'on','files':2}
  page.evaluate(r"""window.__QA__.finish({
   ok:true,exit_code:0,message:'scholar-translator finished successfully',output_dir:'D:\\QA-fixtures\\QDT_Output\\run-1',
   output_files:['D:\\QA-fixtures\\QDT_Output\\run-1\\a-ko.pdf'],
   review_items:Array.from({length:12},(_,i)=>({source_path:'D:\\QA-fixtures\\a.pdf',page:i+1,kind:i?'term_mismatch':'image_ocr',source_text:i?'Sampling error':'Provinces (si-do)',translated_text:i?'Sampling error':'도 (시-도)',reason:'원문과 번역문을 비교하세요.',status:'open'})),
   target_results:window.__QA__.request.files.map(source_path=>({source_path,status:'success',message:'scholar-translator finished successfully',output_files:[]}))
  })""")
  page.get_by_role('button',name='검수 종료',exact=True).wait_for()
  assert page.get_by_text(re.compile(r'^그림 OCR · p\.1$')).count()>=1
  report['ocr_review_label_visible']=True

  capture(page,'review')
  button=page.get_by_role('button',name='문제없음',exact=True)
  button.hover()
  assert button.evaluate("(e)=>getComputedStyle(e).borderTopWidth==='0px'")
  assert 'linear-gradient' in button.evaluate("(e)=>getComputedStyle(e).backgroundImage")
  page.keyboard.press('Tab');button.focus()
  assert button.evaluate("(e)=>e.matches(':focus-visible')&&parseFloat(getComputedStyle(e).outlineWidth)>=2")
  capture(page,'review-keyboard-focus')
  disabled=page.get_by_role('button',name='검수 종료',exact=True)
  assert disabled.is_disabled()
  disabled.hover()
  assert disabled.evaluate("(e)=>parseFloat(getComputedStyle(e).opacity)<=.5&&getComputedStyle(e).transform==='none'")
  before=page.evaluate('window.__QA__.calls.length')
  disabled.evaluate('(e)=>e.click()')
  assert page.evaluate('window.__QA__.calls.length')==before
  report['borderless_hover_keyboard_and_disabled']=True
  for dark in [False,True]:
   for preset in ['Soft Pink','Rosy Purple','Lavender','Custom']:
    page.locator('.sidebar-nav').get_by_role('button',name=re.compile('설정')).click()
    page.get_by_role('button',name='다크' if dark else '라이트',exact=True).click()
    page.locator('.theme-choice-grid').get_by_role('button',name=re.compile('^'+preset)).click()
    capture(page,'settings-'+preset.replace(' ','-')+('-dark' if dark else '-light'))
    page.locator('.sidebar-nav').get_by_role('button',name=re.compile('작업 현황')).click()
    page.get_by_role('button',name='검수 종료',exact=True).wait_for()
    capture(page,'review-'+preset.replace(' ','-')+('-dark' if dark else '-light'))
  page.locator('.sidebar-nav').get_by_role('button',name=re.compile('설정')).click()
  page.get_by_role('button',name='라이트',exact=True).click()
  page.locator('.theme-choice-grid').get_by_role('button',name=re.compile('^Soft Pink')).click()
  page.locator('.sidebar-nav').get_by_role('button',name=re.compile('작업 현황')).click()

  for width in [960,640]:
   page.set_viewport_size({'width':width,'height':820});capture(page,f'review-{width}')
  page.set_viewport_size({'width':1280,'height':820})
  # Approve currently visible candidates until the queue is empty.
  for _ in range(2):
   page.get_by_role('button',name=re.compile('현재 .*문제없음')).click()
   page.wait_for_timeout(200)
  page.get_by_role('button',name='검수 종료',exact=True).click()
  page.get_by_role('heading',name='결과 확인',exact=True).wait_for();capture(page,'complete')
  page.get_by_role('button',name='새 작업 시작',exact=True).click();page.get_by_role('heading',name='번역 준비',exact=True).wait_for()
  page.evaluate('window.__QA__.finish=null');start(page)
  page.evaluate(r"""window.__QA__.finish({
   ok:false,exit_code:1,message:'[QDT_GEMINI_PRESERVATION] 숫자 보존 검사 실패. Traceback '+('implementation_stack_detail '.repeat(120)),output_dir:'D:\\QA-fixtures\\QDT_Output\\run-2',
   output_files:[],review_items:[],target_results:window.__QA__.request.files.map((source_path,i)=>({source_path,status:i?'skipped':'failure',message:i?'이전 문서 실패로 미실행':'scholar-translator failed: Traceback '+('implementation_stack_detail '.repeat(120)),output_files:[]}))
  })""")
  page.get_by_role('heading',name='실행 결과 확인',exact=True).wait_for();capture(page,'failure')
  page.get_by_role('button',name='새 작업 시작',exact=True).click()
  page.get_by_role('heading',name='번역 준비',exact=True).wait_for()
  select_choice(page,page.get_by_role('combobox',name='검수 방식'),'off')
  page.evaluate('window.__QA__.finish=null');start(page)
  page.evaluate(r"""window.__QA__.finish({
    ok:true,exit_code:0,message:'completed with review work',output_dir:'D:\\QA-fixtures\\run-incomplete',
    output_files:['D:\\QA-fixtures\\run-incomplete\\a-dual.pdf'],
    review_items:[{source_path:'D:\\QA-fixtures\\a.pdf',page:22,kind:'translation_incomplete',severity:'error',
      source_text:'Blocked phrase',translated_text:'Blocked phrase',reason:'모델이 해당 문구를 차단했습니다. 원문을 보존했습니다.',status:'open',fitted:false}],
    target_results:window.__QA__.request.files.map(source_path=>({source_path,status:'success',message:'generated',output_files:[]}))
  })""")
  page.get_by_role('heading',name='결과 확인',exact=True).wait_for()
  assert page.get_by_text('미번역 구간 있음',exact=True).count()==1
  assert page.get_by_role('alert').filter(has_text='원문으로 남았습니다').count()==1
  capture(page,'incomplete-review-off')
  page.get_by_role('button',name='생성된 결과 검수',exact=True).click()
  page.get_by_role('button',name='검수 종료',exact=True).wait_for()
  assert page.get_by_text(re.compile(r'^번역 미완료 · p\.22$')).count()>=1
  report['review_off_incomplete_is_visible_and_reviewable']=True
  capture(page,'incomplete-review-open')
  page.locator('.sidebar-nav').get_by_role('button',name=re.compile('설정')).click();page.get_by_role('button',name='다크',exact=True).click()
  capture(page,'settings-dark')
  for width in [960,640]:
   page.set_viewport_size({'width':width,'height':820});capture(page,f'settings-dark-{width}')
  browser.close()
except Exception:
 report['harness_error']=traceback.format_exc();print(report['harness_error'])
finally:
 server.shutdown();server.server_close()
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'screens':len(report['screens']),'errors':report['errors'],'bordered_buttons':[(s['name'],s['borderedButtons']) for s in report['screens'] if s['borderedButtons']]},ensure_ascii=False))
 if 'harness_error' in report or report['errors']:raise SystemExit(1)
 if any(s['scrollWidth']>s['width'] or s['unlabelledInputs'] or s['smallTargets'] or s['borderedButtons'] or any(a['height']<44 or a['font']!='14px' or a['radius']!='8px' for a in s['actionSizes']) for s in report['screens']):raise SystemExit(2)
