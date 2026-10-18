"""Exercise production controls with isolated Tauri fixtures, without real API calls."""
from pathlib import Path
import functools,http.server,json,os,re,threading,traceback
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('QDT_UI_EVIDENCE_DIR',ROOT/'.qdt-home/ui/20261018-공통컨트롤/browser'))
OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'apps/desktop/dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
origin=f'http://127.0.0.1:{server.server_port}'
mock=(ROOT/'apps/desktop/node_modules/@tauri-apps/api/mocks.js').read_text().rsplit('export {',1)[0]
fixture=(ROOT/'scripts/verify-ui-buttons.py').read_text(encoding='utf-8').split("init=mock+r'''")[1].split("'''")[0]
fixture=fixture.replace('name:"품질·제조",glossary_count:0,candidate_count:0','terms:0')
report={'scope':'Production assets, isolated Chrome and Tauri IPC fixtures; no real API requests','screens':[],'checks':[],'errors':[]}
def capture(page,name):
 metrics=page.evaluate('''() => ({overflow:document.documentElement.scrollWidth>innerWidth,
   bordered:[...document.querySelectorAll('button')].filter(e=>e.offsetWidth&&parseFloat(getComputedStyle(e).borderTopWidth)>0).map(e=>e.className),
   selects:[...document.querySelectorAll('[role="combobox"]')].filter(e=>e.offsetWidth).map(e=>({label:e.getAttribute('aria-label'),font:getComputedStyle(e).fontSize,height:e.getBoundingClientRect().height})),
   native:document.querySelectorAll('select').length})''')
 assert not metrics['overflow'] and not metrics['bordered'] and metrics['native']==0,metrics
 assert all(c['font']=='14px' and c['height']>=44 for c in metrics['selects']),metrics
 page.screenshot(path=str(OUT/(name+'.png')),full_page=True);report['screens'].append({'name':name,**metrics})
def menu_check(page,control,name):
 previous=control.get_attribute('data-value');control.focus();control.press('ArrowDown')
 menu=page.get_by_role('listbox',name=name,exact=True);expect(menu).to_be_visible()
 control.press('End');active=control.get_attribute('aria-activedescendant');assert active
 control.press('Escape');expect(menu).not_to_be_visible();expect(control).to_have_attribute('data-value',previous);expect(control).to_be_focused()
 control.click();expect(menu).to_be_visible()
 box=menu.bounding_box();size=page.viewport_size
 assert box['x']>=0 and box['x']+box['width']<=size['width']+1 and box['y']>=0 and box['y']+box['height']<=size['height']+1,box
 capture(page,'menu-'+str(len(report['screens'])))
 options=menu.get_by_role('option');value=options.last.get_attribute('data-value');options.last.click()
 expect(control).to_have_attribute('data-value',value);expect(control).to_be_focused()
 control.press('Home');control.press('Enter');expect(control).to_have_attribute('aria-expanded','false')
 previous=control.get_attribute('data-value');control.click()
 page.locator('.brand').click();expect(menu).not_to_be_visible();expect(control).to_have_attribute('data-value',previous)
 control.click();control.press('Tab');expect(menu).not_to_be_visible()
 report['checks'].append('keyboard, pointer, bounds, Escape and Tab: '+name)
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
  for dark in (False,True):
   ctx=browser.new_context(viewport={'width':1280,'height':900})
   ctx.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
   ctx.add_init_script(mock+'\n'+fixture+'\nlocalStorage.setItem("qdt-settings",'+json.dumps(json.dumps({'darkMode':dark})) +');')
   page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
   page.goto(origin,wait_until='networkidle');dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
   assert dialog.locator('h2').evaluate('(e)=>getComputedStyle(e).outlineStyle')=='none'
   assert dialog.locator('.mode-gate-panel').evaluate('(e)=>getComputedStyle(e).borderTopWidth')=='0px'
   capture(page,'gate-'+str(dark))
   assert dialog.locator('.entry-choice').count()==2
   assert 'Google' not in dialog.inner_text()
   dialog.get_by_role('button',name='Gemini 번역으로 시작',exact=True).click()
   expect(page.get_by_role('heading',name='번역 준비',exact=True)).to_be_visible()
   assert page.locator('.setup-status-strip').evaluate('(e)=>getComputedStyle(e).borderTopWidth')=='0px'
   key=page.get_by_role('button',name='API 키 저장됨 · 설정 확인');expect(key).to_be_visible();assert key.locator('svg').count()==2
   assert key.bounding_box()['x']<page.get_by_role('button',name='API 설정 열기',exact=True).bounding_box()['x']
   indicator=page.locator('.segment-indicator');before=indicator.evaluate('(e)=>getComputedStyle(e).transform')
   group=page.get_by_role('group',name='등록 방식',exact=True).last
   group.get_by_role('button',name='폴더',exact=True).click();page.wait_for_timeout(210)
   assert before!=indicator.evaluate('(e)=>getComputedStyle(e).transform')
   expect(group.get_by_role('button',name='폴더',exact=True)).to_have_attribute('aria-pressed','true')
   assert group.locator('button').evaluate_all('(els)=>els.every(e=>getComputedStyle(e).backgroundColor==="rgba(0, 0, 0, 0)")')
   expect(page.get_by_text('폴더를 끌어오거나 선택하세요',exact=True)).to_be_visible()
   page.emulate_media(reduced_motion='reduce');assert indicator.evaluate('(e)=>getComputedStyle(e).transitionDuration')=='0s'
   group.get_by_role('button',name='파일',exact=True).click()
   for width in [1280,640,375]:
    page.set_viewport_size({'width':width,'height':900});capture(page,f'setup-{width}-{dark}')
    menu_check(page,page.get_by_role('combobox',name='출력 방식'),'출력 방식')
   page.set_viewport_size({'width':1280,'height':900});menu_check(page,page.get_by_role('combobox',name='검수 방식'),'검수 방식')
   key.click();expect(page.locator('#gemini-api-key')).to_be_focused()
   model=page.get_by_role('combobox',name='번역 모델');menu_check(page,model,'번역 모델')
   model.focus();model.press('g');expect(model).to_have_attribute('aria-expanded','true');model.press('Escape')
   disclosure=page.locator('.api-disclosure');assert disclosure.locator('svg').count()==1
   disclosure.click();expect(model).not_to_be_visible();capture(page,'api-collapsed-'+str(dark));disclosure.click()
   for width in [1280,375]:
    page.set_viewport_size({'width':width,'height':900});capture(page,f'api-{width}-{dark}')
   page.set_viewport_size({'width':1280,'height':900})
   page.locator('.sidebar-nav button').filter(has_text='용어집').click()
   menu_check(page,page.get_by_role('combobox',name='분류',exact=True),'분류')
   page.locator('.glossary-exchange summary').click()
   for label in ['내보낼 파일 형식','가져올 파일 형식','가져온 용어 처리']:
    menu_check(page,page.get_by_role('combobox',name=label,exact=True),label)
   capture(page,'glossary-'+str(dark))
   page.locator('.sidebar-nav button').filter(has_text=re.compile('FEEDBACK|피드백')).click()
   menu_check(page,page.get_by_role('combobox',name='분류',exact=True),'분류')
   capture(page,'feedback-'+str(dark))
   page.locator('.sidebar-nav button').filter(has_text='패치노트').click();page.locator('.patch-note-row summary').first.click()
   assert page.locator('.patch-note-row summary svg').count()>0;capture(page,'patch-'+str(dark))
   assert not page.evaluate('window.__QA__.calls.some(x=>["run_translation_job","test_engine_connection","save_engine_settings","clear_engine_api_key"].includes(x))')
   ctx.close()
  browser.close()
 assert not report['errors'],report['errors']
 report['checks'].extend(['Google menu removed; heading frame removed','single sliding indicator and reduced motion','API status icon placement and navigation','no real or fixture API mutation'])
 report['status']='passed'
except Exception:
 report['status']='failed';report['traceback']=traceback.format_exc();raise
finally:
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');server.shutdown()
print(json.dumps({'status':report['status'],'screens':len(report['screens']),'checks':len(report['checks'])}))
