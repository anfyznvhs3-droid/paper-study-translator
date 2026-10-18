"""Local production UI, synthetic failures and IPC. Never sends a real API request."""
from pathlib import Path
import functools,http.server,json,os,threading,traceback
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get("QDT_UI_EVIDENCE_DIR",ROOT/'검증자료'/'20261018-목록형UI'))
OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'apps/desktop/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
mock=(ROOT/'apps/desktop/node_modules/@tauri-apps/api/mocks.js').read_text().rsplit('export {',1)[0]
def fixture(code):
    return {'version':1,'state':{'runId':'run-api-navigation','reviewOpen':False,'files':[{'id':'one','name':'sample.pdf','kind':'file','status':'failed','progress':10,'pages':12,'sourcePath':'F:\\QA\\sample.pdf'}],
      'activeJobId':'one','translationMode':'machine','engine':'gemini-flash-lite','outputMode':'dual','reviewMode':'on','domain':'quality-manufacturing',
      'lastRunResult':{'ok':False,'status':'failure','message':f'[QDT_GEMINI_{code}] synthetic failure','outputDir':'F:\\QA\\PDF',
      'outputFiles':['F:\\QA\\PDF\\sample-dual.pdf'],'reviewItems':[],
      'diagnosis':{'summary':'테스트 실패 원인','cause':f'[QDT_GEMINI_{code}] 테스트 원인','solution':'관련 위치에서 확인하세요.'}}}}
handler=r'''
mockWindows("main");window.__calls=[];
const settings={provider:"gemini",model:"gemini-2.5-flash-lite",has_api_key:true,has_saved_key:true,key_source:"saved"};
mockIPC(async(command,args)=>{
  window.__calls.push({command,args});
  if(command==="load_review_session")return window.__snapshot;
  if(command==="save_review_session"){window.__saved=args.snapshot;return null;}
  if(command==="get_engine_settings")return settings;
  if(command==="save_engine_settings")return settings;
  if(command==="test_engine_connection")return {ok:false,model:settings.model,message:"[QDT_GEMINI_RATE_LIMITED] 요청 한도 테스트"};
  if(command==="wiki_list_shared_packs")return [];
  if(command==="wiki_list_domains")return [{slug:"quality-manufacturing",name:"품질·제조",glossary_count:0,candidate_count:0}];
  if(command.startsWith("wiki_"))return "[]";
  if(command==="plugin:opener|open_url"||command==="open_system_path")return null;
  throw new Error("Unexpected command: "+command);
},{shouldMockEvents:true});'''
report={'scope':'Production bundle in isolated browser; synthetic IPC only','cases':[],'screens':[],'errors':[]}
try:
  with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
    for dark in (False,True):
      for code,label,selector in [('AUTH','API 키 설정으로 이동','#gemini-api-key'),('MODEL','모델 설정으로 이동','#gemini-model'),('RATE_LIMITED','사용량 한도 확인으로 이동','.api-usage button'),('NETWORK','API 연결 확인으로 이동','.api-actions button:nth-child(2)'),('PRESERVATION',None,None),('UNKNOWN',None,None)]:
        ctx=browser.new_context(viewport={'width':1280,'height':900},reduced_motion='reduce')
        ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
        ctx.add_init_script(mock+'\nwindow.__snapshot='+json.dumps(fixture(code))+';\n'+
          'localStorage.setItem("qdt-settings",'+json.dumps(json.dumps({'darkMode':dark}))+');\n'+handler)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.goto(origin,wait_until='networkidle')
        page.get_by_role('heading',name='실행 결과 확인',exact=True).wait_for()
        if label:
          page.get_by_role('button',name=label,exact=True).click()
          expect(page.locator('.api-disclosure')).to_have_attribute('aria-expanded','true')
          expect(page.locator(selector)).to_be_focused()
          assert not page.evaluate('window.__calls.some(x=>["save_engine_settings","test_engine_connection","clear_engine_api_key"].includes(x.command))')
          if code=='RATE_LIMITED':
            page.get_by_role('button',name='AI Studio 사용량 한도 열기',exact=True).click()
            assert page.evaluate('window.__calls.filter(x=>x.command==="plugin:opener|open_url").at(-1).args.url')=='https://aistudio.google.com/rate-limit?timeRange=last-28-days'
          if code=='AUTH':
            page.locator('#gemini-api-key').fill('synthetic-unsaved-value')
            page.locator('.api-disclosure').click()
            expect(page.locator('#gemini-api-key')).to_be_hidden()
            page.locator('.api-disclosure').click()
            expect(page.locator('#gemini-api-key')).to_have_value('synthetic-unsaved-value')
            page.locator('#gemini-api-key').fill('')
            for width in (1280,640,375):
              page.set_viewport_size({'width':width,'height':900})
              assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
              assert not page.evaluate('[...document.querySelectorAll("button")].filter(e=>e.offsetWidth&&parseFloat(getComputedStyle(e).borderTopWidth)>0).length')
              name=f'api-expanded-{width}-'+('dark' if dark else 'light')
              page.screenshot(path=str(OUT/(name+'.png')),full_page=True);report['screens'].append(name)
            page.set_viewport_size({'width':1280,'height':900})
          page.get_by_role('button',name='작업으로 돌아가기',exact=True).click()
          page.get_by_role('heading',name='실행 결과 확인',exact=True).wait_for()
          assert page.evaluate('window.__saved.state.runId')=='run-api-navigation'
          assert page.get_by_role('button',name='sample-dual.pdf 열기',exact=True).is_visible()
          page.get_by_role('button',name=label,exact=True).click()
          expect(page.locator(selector)).to_be_focused()
          page.get_by_role('button',name='작업으로 돌아가기',exact=True).click()
        else:
          assert page.get_by_role('region',name='실패 원인과 해결 방법').get_by_role('button').count()==2
        page.get_by_role('button',name='실행 상세로 이동',exact=True).click()
        expect(page.locator('.pdf-run-details')).to_have_attribute('open','')
        assert page.get_by_text(f'[QDT_GEMINI_{code}] synthetic failure',exact=True).is_visible()
        page.get_by_role('button',name='결과 폴더 열기',exact=True).click()
        assert page.evaluate('window.__calls.filter(x=>x.command==="open_system_path").at(-1).args.request.path')=='F:\\QA\\PDF'
        page.locator('.sidebar-nav button').filter(has_text='설정').click()
        expect(page.locator('.api-disclosure')).to_have_attribute('aria-expanded','false')
        expect(page.locator('#gemini-api-key')).to_be_hidden()
        if code=='AUTH':
          name='api-collapsed-'+('dark' if dark else 'light')
          page.screenshot(path=str(OUT/(name+'.png')),full_page=True);report['screens'].append(name)
          page.locator('.api-disclosure').focus();page.keyboard.press('Enter')
          expect(page.locator('#gemini-api-key')).to_be_visible()
          page.get_by_role('button',name='저장 후 연결 확인',exact=True).click()
          page.get_by_role('button',name='사용량 한도 확인으로 이동',exact=True).click()
          expect(page.locator('.api-usage button')).to_be_focused()
          assert page.evaluate('window.__calls.filter(x=>x.command==="test_engine_connection").length')==1
        report['cases'].append({'code':code,'dark':dark,'passed':True})
        ctx.close()
    browser.close()
  assert not report['errors'];report['passed']=True
except Exception:
  report['failure']=traceback.format_exc();print(report['failure'])
finally:
  server.shutdown();server.server_close()
  (OUT/'api-navigation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'cases':len(report['cases']),'screens':len(report['screens']),'passed':report.get('passed',False)}))
  if not report.get('passed'):raise SystemExit(1)
