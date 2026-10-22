"""Pure injected driver checks: no browser, socket, database or model launch."""
import ast, io, json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts import receipt_status_css_browser_once as m

results=[]
def exercise(name, *, fail=False, shot_fail=False, close_fail=False, launch_fail=False):
    events=[]
    primary=RuntimeError('original failure')
    class Browser:
        def close(self):
            events.append('close')
            if close_fail: raise OSError('injected close')
    browser=Browser()
    class Page:
        def is_closed(self): return False
        def screenshot(self, **kw):
            events.append('screenshot')
            if shot_fail: raise OSError('injected screenshot')
    def launch(**kw):
        events.append('launch')
        assert kw['chromium_sandbox'] is True and kw['args']==['--enable-automation']
        if launch_fail: raise primary
        return browser
    class PW:
        def __enter__(self):
            events.append('enter');return SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        def __exit__(self,*exc): events.append('exit')
    m.REPORT={'cleanup_errors':[]};m.OUT=Path('/not-written');m.LAST_PAGE=Page()
    with patch.object(m,'sync_playwright',return_value=PW()):
        try:
            with m.browser_session({}) as actual:
                assert actual is browser
                events.append('body')
                if fail: raise primary
        except RuntimeError as error:
            assert error is primary and (fail or launch_fail)
        else: assert not fail and not launch_fail
    expected=['enter','launch']+([] if launch_fail else ['body']+(['screenshot'] if fail else [])+['close'])+['exit']
    assert events==expected,(name,events)
    assert m.REPORT['cleanup_errors']==(['browser:OSError'] if close_fail else [])
    assert m.REPORT.get('failure_screenshot_error')==('OSError' if shot_fail else None)
    results.append({'case':name,'events':events,'outcome':'PASS'})

exercise('normal close before transport exit')
exercise('primary failure screenshot then close',fail=True)
exercise('screenshot failure preserves primary and closes',fail=True,shot_fail=True)
exercise('close failure preserves primary',fail=True,close_fail=True)
exercise('launch failure exits transport',launch_fail=True)

# Call the exact GET handler without opening a listener. Only the narrowly named
# status fixture is modelled; unrelated paths must still be recorded as404.
for path,expected_code in [('/api/run-access/status',200),('/not-modelled',404)]:
    h=object.__new__(m.Handler);h.path=path;h.wfile=io.BytesIO();headers={};codes=[]
    h.send_response=codes.append;h.send_header=lambda k,v:headers.update({k:v});h.end_headers=lambda:None
    m.REPORT={'requests':[]};m.MODE='initial';h.do_GET()
    assert codes==[expected_code]
    assert 'unsafe-eval' not in headers['Content-Security-Policy']
    if expected_code==200:
        value=json.loads(h.wfile.getvalue());assert value=={'enabled':False,'read_available':False,'scope':'SYNTHETIC_CSS_GET_REPLAY_DISABLED'}
        assert not m.REPORT.get('unexpected_GET')
    else: assert m.REPORT['unexpected_GET']==[path]
    results.append({'case':'exact GET fixture '+path,'outcome':'PASS'})

source=Path(m.__file__).read_text();tree=ast.parse(source)
waits=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='wait_for_function']
assert len(waits)==3 and all(ast.literal_eval(n.args[0])=='() => !receiptSubmitBusy' for n in waits)
result={'status':'PASS','fault_fixture_cases':len(results),'results':results,'wait_predicates_ast_checked':3,
        'actual_browser_runs':0,'socket_listeners':0,'business_POSTs':0,'model_calls':0,'CI_runs':0,
        'scope':'Injected lifecycle/handler checks and static predicate shape only; CSP browser execution remains unverified'}
print(json.dumps(result,indent=2))
