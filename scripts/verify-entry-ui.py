"""Approved two-card entry, production frontend with isolated Tauri fixtures."""
from pathlib import Path
import functools, http.server, json, os, threading, traceback
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('QDT_UI_EVIDENCE_DIR', ROOT/'.qdt-home/ui/20261018-두카드시작/entry'))
OUT.mkdir(parents=True, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT/'apps/desktop/dist')))
threading.Thread(target=server.serve_forever, daemon=True).start()
origin = f'http://127.0.0.1:{server.server_port}'
mock = (ROOT/'apps/desktop/node_modules/@tauri-apps/api/mocks.js').read_text().rsplit('export {', 1)[0]
fixture = (ROOT/'scripts/verify-ui-buttons.py').read_text(encoding='utf-8').split("init=mock+r'''")[1].split("'''")[0]
report = {'scope':'Production assets; isolated Chrome and synthetic Tauri IPC. No real API calls or user data writes.', 'screens':[], 'checks':[], 'errors':[]}

def create_page(browser, settings=None, fixture_code=fixture):
    ctx = browser.new_context(viewport={'width':1280,'height':820})
    ctx.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
    ctx.add_init_script(mock+'\n'+fixture_code+'\nlocalStorage.setItem("qdt-settings",'+json.dumps(json.dumps(settings or {}))+');')
    page = ctx.new_page()
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    page.goto(origin, wait_until='networkidle')
    expect(page.get_by_role('dialog')).to_be_visible()
    return ctx, page

def capture(page, name, gate=False):
    metrics = page.evaluate('''() => ({
      overflow:document.documentElement.scrollWidth>innerWidth,
      gateOverflow:!!document.querySelector('.mode-gate') && document.querySelector('.mode-gate').scrollWidth>innerWidth,
      bordered:[...document.querySelectorAll('button')].filter(e=>e.offsetWidth&&parseFloat(getComputedStyle(e).borderTopWidth)>0).map(e=>e.className),
      cards:[...document.querySelectorAll('.entry-choice')].map(e=>({name:e.getAttribute('aria-label'),font:getComputedStyle(e.querySelector('strong')).fontSize,rect:e.getBoundingClientRect().toJSON()}))
    })''')
    assert not metrics['overflow'] and not metrics['gateOverflow'] and not metrics['bordered'], metrics
    if gate:
        assert len(metrics['cards'])==2
        a,b=[c['rect'] for c in metrics['cards']]
        assert (abs(a['y']-b['y'])<1 and b['x']>a['x']) if page.viewport_size['width']>650 else b['y']>a['y']
        if page.viewport_size['width']>650: assert abs(a['height']-b['height'])<1,metrics
        if page.viewport_size['width']<=650:
            modal=page.locator('.mode-gate')
            modal.evaluate('(e)=>e.scrollTop=0')
            page.screenshot(path=str(OUT/(name+'.png')))
            modal.evaluate('(e)=>e.scrollTop=e.scrollHeight')
            last=page.get_by_role('button',name='에이전트 번역으로 시작',exact=True)
            box=last.bounding_box()
            assert box['y']>=0 and box['y']+box['height']<=page.viewport_size['height'],box
            page.screenshot(path=str(OUT/(name+'-bottom.png')))
            report['screens'].append({'name':name+'-bottom','agentReachable':True})
            modal.evaluate('(e)=>e.scrollTop=0')
        else:
            page.locator('.mode-gate-panel').screenshot(path=str(OUT/(name+'.png')))
    else:
        page.screenshot(path=str(OUT/(name+'.png')), full_page=True)
    report['screens'].append({'name':name,**metrics})

def choose(page, name, value):
    page.get_by_role('combobox', name=name, exact=True).click()
    page.locator('[role="option"][data-value="'+value+'"]').click()

def assert_idle(page):
    assert not page.evaluate('window.__QA__.calls.some(x=>["run_translation_job","test_engine_connection","save_engine_settings","clear_engine_api_key"].includes(x))')

try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        for dark in (False, True):
            ctx,page=create_page(browser, {'darkMode':dark})
            dialog=page.get_by_role('dialog')
            expect(dialog.get_by_role('heading',name='어떻게 번역할까요?')).to_be_focused()
            assert page.locator('.workspace').evaluate('(e)=>e.inert')
            assert '최적 대상' not in dialog.inner_text() and 'Google' not in dialog.inner_text()
            for width,height in [(1280,820),(960,800),(755,597),(640,820),(375,812),(320,720)]:
                page.set_viewport_size({'width':width,'height':height})
                capture(page,f'entry-{width}-{dark}',True)
            page.set_viewport_size({'width':1280,'height':820})
            first=dialog.get_by_role('button',name='닫기',exact=True)
            last=dialog.get_by_role('button',name='에이전트 번역으로 시작',exact=True)
            first.focus();page.keyboard.press('Shift+Tab');expect(last).to_be_focused()
            page.keyboard.press('Tab');expect(first).to_be_focused()
            page.emulate_media(reduced_motion='reduce')
            last.hover();assert last.evaluate('(e)=>getComputedStyle(e).transform')=='none'
            assert last.evaluate('(e)=>getComputedStyle(e).transitionDuration')=='0s'
            dialog.get_by_role('button',name='API 설정',exact=True).click()
            expect(page.locator('#gemini-api-key')).to_be_focused()
            assert not page.locator('.workspace').evaluate('(e)=>e.inert')
            page.get_by_role('button',name='작업으로 돌아가기',exact=True).click()
            expect(dialog).to_be_visible();assert_idle(page)
            dialog.get_by_role('button',name='Gemini 번역으로 시작',exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role('heading',name='번역 준비',exact=True)).to_be_visible()
            expect(page.get_by_role('combobox',name='에이전트',exact=True)).to_have_count(0)
            expect(page.get_by_role('button',name='API 키 저장됨 · 설정 확인')).to_be_visible()
            page.get_by_role('button',name='파일 선택',exact=True).click()
            choose(page,'출력 방식','mono');choose(page,'검수 방식','off')
            change=page.get_by_role('button',name='방식 변경',exact=True)
            change.click();page.keyboard.press('Escape');expect(change).to_be_focused()
            change.click();dialog.get_by_role('button',name='에이전트 번역으로 시작',exact=True).click()
            expect(page.get_by_role('combobox',name='에이전트',exact=True)).to_have_attribute('data-value','codex-agent')
            choose(page,'에이전트','claude-code-agent');choose(page,'번역 기준','true')
            change.click();dialog.get_by_role('button',name='에이전트 번역으로 시작',exact=True).click()
            for label,value in [('에이전트','claude-code-agent'),('번역 기준','true'),('출력 방식','mono'),('검수 방식','off')]:
                expect(page.get_by_role('combobox',name=label,exact=True)).to_have_attribute('data-value',value)
            expect(page.get_by_role('button',name='a.pdf 목록에서 제외')).to_be_visible()
            expect(page.get_by_role('button',name='b.pdf 목록에서 제외')).to_be_visible()
            for width in [1280,755,375,320]:
                page.set_viewport_size({'width':width,'height':820})
                capture(page,f'agent-setup-{width}-{dark}')
            assert_idle(page)
            page.get_by_role('button',name='번역 시작',exact=True).click()
            page.wait_for_function('window.__QA__.finish!==null')
            request=page.evaluate('window.__QA__.request')
            assert {k:request[k] for k in ['engine','mode','quality','output_mode','review_mode']}==dict(engine='claude-code-agent',mode='agent',quality='true',output_mode='mono',review_mode='off'),request
            assert len(request['files'])==2
            report['checks'].append({'dark':dark,'submitted':request})
            ctx.close()
        for theme in ['rosy-purple','lavender','custom']:
            for dark in (False,True):
                ctx,page=create_page(browser,{'darkMode':dark,'themePreset':theme,'darkPreset':theme})
                capture(page,f'entry-{theme}-{dark}',True);ctx.close()
        # Saved agent preference is also retained on a fresh app launch.
        ctx,page=create_page(browser,{'translationMode':'agent','engine':'claude-code-agent','quality':'complete'})
        page.get_by_role('button',name='에이전트 번역으로 시작',exact=True).click()
        expect(page.get_by_role('combobox',name='에이전트',exact=True)).to_have_attribute('data-value','claude-code-agent')
        expect(page.get_by_role('combobox',name='번역 기준',exact=True)).to_have_attribute('data-value','complete')
        assert_idle(page);ctx.close()
        # Missing API key leads to settings, without starting a request.
        ctx,page=create_page(browser,fixture_code=fixture.replace('has_api_key:true,has_saved_key:true,key_source:"saved"','has_api_key:false,has_saved_key:false,key_source:"none"'))
        page.get_by_role('button',name='Gemini 번역으로 시작',exact=True).click()
        page.get_by_role('button',name='파일 선택',exact=True).click()
        expect(page.get_by_role('button',name='번역 시작',exact=True)).to_be_disabled()
        page.get_by_role('button',name='API 설정 열기',exact=True).click()
        expect(page.locator('#gemini-api-key')).to_be_focused();assert_idle(page);ctx.close()
        browser.close()
    assert not report['errors'],report['errors']
    report['checks'].extend(['one-click Gemini/agent entry','file, output, review, quality and same-mode engine preservation','API navigation without execution','keyboard focus trap, Escape return, reduced motion','saved Claude preference and missing-key recovery'])
    report['status']='passed'
except Exception:
    report['status']='failed';report['traceback']=traceback.format_exc();raise
finally:
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');server.shutdown()
print(json.dumps({'status':report['status'],'screens':len(report['screens']),'checks':len(report['checks'])}))
