"""Glossary UI acceptance checks against production assets with isolated fake IPC."""
from pathlib import Path
import functools,http.server,json,os,re,threading,traceback
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get("QDT_UI_EVIDENCE_DIR",ROOT/'검증자료'/'20261018-용어집UI'))
OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'apps/desktop/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
mock=(ROOT/'apps/desktop/node_modules/@tauri-apps/api/mocks.js').read_text().rsplit('export {',1)[0]
snapshot={'version':1,'state':{'runId':'run-glossary-ui','reviewOpen':False,'files':[{'id':'one','name':'sample.pdf','kind':'file','status':'completed','progress':100,'pages':1,'sourcePath':'F:\\QA\\sample.pdf'}],
 'activeJobId':'one','translationMode':'machine','engine':'gemini-flash-lite','outputMode':'dual','reviewMode':'on','domain':'quality-manufacturing',
 'lastRunResult':{'ok':True,'message':'complete','outputFiles':['F:\\QA\\sample.pdf'],'reviewItems':[]}}}
handler=r'''
mockWindows("main"); window.__calls=[]; window.__failLoad=false; window.__failAdd=false; window.__slow=false;
window.__data={"quality-manufacturing":[{source:"FMEA",target:"고장형태 및 영향분석",notes:"설계 및 공정"},{source:"Control Plan",target:"관리계획서",notes:""},{source:"Long source term with several words",target:"긴 용어 이름의 번역",notes:"긴 메모는 줄바꿈되어 보여야 합니다."}],empty:[]};
const domains=()=>Object.entries(window.__data).map(([slug,terms])=>({slug,terms:terms.length}));
mockIPC(async(command,args)=>{
 window.__calls.push({command,args});
 if(command==="load_review_session")return window.__snapshot;
 if(command==="save_review_session")return null;
 if(command==="wiki_list_domains")return domains();
 if(command==="wiki_list_glossary"){
   if(window.__slow&&args.domain==="quality-manufacturing")await new Promise(resolve=>setTimeout(resolve,450));
   if(window.__failLoad)throw new Error("용어 목록을 읽지 못했습니다.");
   return JSON.stringify(window.__data[args.domain]??[]);
 }
 if(command==="wiki_add_term"){
   if(window.__failAdd)throw new Error("용어 저장에 실패했습니다.");
   window.__data[args.domain].push({source:args.source,target:args.target,notes:args.notes});return JSON.stringify({added:true});
 }
 if(command==="wiki_delete_term"){window.__data[args.domain]=window.__data[args.domain].filter(x=>x.source!==args.source);return JSON.stringify({deleted:true});}
 if(command==="wiki_create_domain"){window.__data[args.slug]=[];return domains();}
 if(command==="wiki_delete_domain"){delete window.__data[args.slug];return {domains:domains(),backupPath:"F:\\QA\\backup"};}
 if(command==="wiki_export_glossary")return JSON.stringify({exported:window.__data[args.domain].length,path:"F:\\QA\\glossary.tbx",format:args.format});
 if(command==="plugin:dialog|open")return "F:\\QA\\incoming.tbx";
 if(command==="wiki_import_glossary")return JSON.stringify({imported:2,mode:args.mode,format:args.format});
 if(command.startsWith("wiki_"))return "[]";
 throw new Error("Unexpected command: "+command);
},{shouldMockEvents:true});'''
report={'scope':'Synthetic IPC; no real glossary mutations or API requests','screens':[],'checks':[],'errors':[]}
def select_choice(page,control,value):
 control.click()
 page.locator('[role="option"][data-value="'+value+'"]').click()

def capture(page,name):
    metrics=page.evaluate('''() => ({overflow:document.documentElement.scrollWidth>innerWidth,
     borders:[...document.querySelectorAll('.glossary-workspace button,.glossary-workspace input,.glossary-workspace select,.glossary-workspace summary')].filter(e=>e.offsetWidth&&parseFloat(getComputedStyle(e).borderTopWidth)>0).map(e=>e.textContent),
     controls:[...document.querySelectorAll('.glossary-workspace button,.glossary-workspace input,.glossary-workspace select')].filter(e=>e.offsetWidth).map(e=>({height:e.getBoundingClientRect().height,font:getComputedStyle(e).fontSize})),
     heading:getComputedStyle(document.querySelector('.glossary-workspace h2')).fontSize
    })''')
    assert not metrics['overflow'] and not metrics['borders'],metrics
    assert metrics['heading']=='20px' and all(c['height']>=44 and c['font']=='14px' for c in metrics['controls']),metrics
    page.screenshot(path=str(OUT/(name+'.png')),full_page=True);report['screens'].append({'name':name,**metrics})
try:
  with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
    for dark in (False,True):
      ctx=browser.new_context(viewport={'width':1280,'height':900},reduced_motion='reduce')
      ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
      ctx.add_init_script(mock+'\nwindow.__snapshot='+json.dumps(snapshot)+';\n'+
        'localStorage.setItem("qdt-settings",'+json.dumps(json.dumps({'darkMode':dark}))+');\n'+handler)
      page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
      page.goto(origin,wait_until='networkidle');page.locator('.sidebar-nav button').filter(has_text='용어집').click()
      section=page.get_by_role('region',name='용어집',exact=True)
      expect(section.get_by_text('FMEA',exact=True)).to_be_visible()
      assert section.get_by_role('combobox').count()==1,'Only one domain selector should be visible'
      assert section.get_by_text('GLOSSARY',exact=True).count()==0
      exchange=section.locator('.glossary-exchange')
      assert exchange.count()==1 and exchange.get_attribute('open') is None
      assert section.get_by_role('heading',name=re.compile('^용어 목록')).bounding_box()['y']<exchange.bounding_box()['y']
      search=section.get_by_role('searchbox',name='용어 검색')
      search.fill('관리계획서');expect(section.get_by_text('Control Plan',exact=True)).to_be_visible();assert section.get_by_text('FMEA',exact=True).count()==0
      search.fill('no-match');expect(section.get_by_text('검색 결과가 없습니다.',exact=True)).to_be_visible();search.fill('')
      for width in (1280,960,640,375):
        page.set_viewport_size({'width':width,'height':900});capture(page,f'glossary-list-{width}-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':1280,'height':900})
      exchange.locator('summary').focus();page.keyboard.press('Enter')
      expect(exchange.get_by_role('combobox',name='내보낼 파일 형식')).to_be_visible()
      select_choice(page,exchange.get_by_role('combobox',name='내보낼 파일 형식'),'tbx')
      exchange.get_by_role('button',name='용어집 파일로 내보내기',exact=True).click()
      expect(section.get_by_role('status').filter(has_text='내보내기 완료')).to_be_visible()
      select_choice(page,exchange.get_by_role('combobox',name='가져올 파일 형식'),'tbx')
      select_choice(page,exchange.get_by_role('combobox',name='가져온 용어 처리'),'candidates')
      exchange.get_by_role('button',name='용어집 파일 가져오기',exact=True).click()
      expect(section.get_by_role('status').filter(has_text='가져오기 완료')).to_be_visible()
      args=page.evaluate('window.__calls.filter(x=>x.command==="wiki_import_glossary").at(-1).args')
      assert args['format']=='tbx' and args['mode']=='candidates' and args['domain']=='quality-manufacturing'
      for width in (1280,640,375):
        page.set_viewport_size({'width':width,'height':900});capture(page,f'glossary-exchange-{width}-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':1280,'height':900});exchange.locator('summary').click()
      add=section.get_by_role('button',name='용어 추가',exact=True);add.click()
      dialog=page.get_by_role('dialog',name='새 용어 추가')
      expect(dialog.get_by_role('textbox',name='원문',exact=True)).to_be_focused()
      dialog.get_by_role('textbox',name='원문',exact=True).fill('QA term')
      dialog.get_by_role('textbox',name='번역',exact=True).fill('검증 용어')
      dialog.get_by_role('textbox',name='메모 (선택)',exact=True).fill('테스트')
      page.evaluate('window.__failAdd=true');dialog.get_by_role('button',name='용어 추가',exact=True).click()
      expect(dialog.get_by_role('alert')).to_contain_text('저장에 실패')
      expect(dialog.get_by_role('textbox',name='원문',exact=True)).to_have_value('QA term')
      page.evaluate('window.__failAdd=false')
      dialog.get_by_role('textbox',name='원문',exact=True).focus()
      for _ in range(7):
        page.keyboard.press('Shift+Tab')
        assert dialog.evaluate('(element)=>element.contains(document.activeElement)'), 'Modal focus escaped'
      capture(page,'glossary-add-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':375,'height':900});capture(page,'glossary-add-375-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':1280,'height':900})
      dialog.get_by_role('button',name='용어 추가',exact=True).click();expect(dialog).not_to_be_visible()
      expect(section.get_by_text('검증 용어',exact=True)).to_be_visible();expect(add).to_be_focused()
      section.get_by_role('button',name='QA term 삭제',exact=True).click();expect(section.get_by_text('검증 용어',exact=True)).not_to_be_visible()
      add.click();page.keyboard.press('Escape');expect(dialog).not_to_be_visible();expect(add).to_be_focused()
      manage=section.get_by_role('button',name='분류 관리',exact=True);manage.click()
      manager=page.get_by_role('dialog',name='분류 관리');expect(manager.get_by_role('textbox',name='새 분류',exact=True)).to_be_focused()
      capture(page,'glossary-domain-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':375,'height':900});capture(page,'glossary-domain-375-'+('dark' if dark else 'light'))
      page.set_viewport_size({'width':1280,'height':900})
      manager.get_by_role('textbox',name='새 분류',exact=True).fill('qa-domain')
      manager.get_by_role('button',name='추가',exact=True).click();expect(manager).not_to_be_visible()
      domain=section.get_by_role('combobox',name='분류',exact=True);expect(domain).to_have_attribute('data-value','qa-domain')
      expect(section.get_by_text('등록된 용어가 없습니다.',exact=True)).to_be_visible()
      capture(page,'glossary-empty-'+('dark' if dark else 'light'))
      manage.click();manager.get_by_role('button',name='백업 후 제거',exact=True).click();expect(manager).not_to_be_visible()
      expect(domain).to_have_attribute('data-value','quality-manufacturing')
      # A late response from another domain must never replace the selected domain's list.
      select_choice(page,domain,'empty');expect(section.get_by_text('등록된 용어가 없습니다.',exact=True)).to_be_visible()
      page.evaluate('window.__slow=true');select_choice(page,domain,'quality-manufacturing');select_choice(page,domain,'empty')
      page.wait_for_timeout(600);expect(section.get_by_text('등록된 용어가 없습니다.',exact=True)).to_be_visible();assert section.get_by_text('FMEA',exact=True).count()==0
      page.evaluate('window.__slow=false;window.__failLoad=true');select_choice(page,domain,'quality-manufacturing')
      expect(section.get_by_role('alert').filter(has_text='읽지 못했습니다')).to_be_visible()
      capture(page,'glossary-load-error-'+('dark' if dark else 'light'))
      assert section.get_by_text('등록된 용어가 없습니다.',exact=True).count()==0
      page.evaluate('window.__failLoad=false');section.get_by_role('button',name='다시 불러오기',exact=True).click()
      expect(section.get_by_text('FMEA',exact=True)).to_be_visible()
      assert not page.evaluate('window.__calls.some(x=>/engine|translate/.test(x.command))')
      report['checks'].append({'dark':dark,'singleSelector':True,'search':True,'fileExchange':True,'addDelete':True,'domainManagement':True,'errorRecovery':True,'staleResponseGuard':True,'keyboardDialogs':True})
      ctx.close()
    browser.close()
  assert not report['errors'];report['passed']=True
except Exception:
  report['failure']=traceback.format_exc();print(report['failure'])
finally:
  server.shutdown();server.server_close()
  (OUT/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'screens':len(report['screens']),'passed':report.get('passed',False)}))
  if not report.get('passed'):raise SystemExit(1)
