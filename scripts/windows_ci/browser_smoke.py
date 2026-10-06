"""Preinstalled native Chrome/ChromeDriver, W3C loopback commands; no downloads.
Only fresh SYNTHETIC profile/session, no credentials printed or persisted by this code.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from urllib.parse import quote
from parkweave.process_env import minimal_environment

INJECTION_GOAL='SYNTHETIC native browser local case <script>globalThis.PARKWEAVE_NATIVE_SCRIPT_EXECUTED=true</script>'

def verify_case_rendering(driver,record,result):
    """Observe the actual intake -> worker -> API -> application render path."""
    assert record['case']['goal']==INJECTION_GOAL and INJECTION_GOAL in result
    assert driver.execute("return Boolean(globalThis.PARKWEAVE_NATIVE_SCRIPT_EXECUTED||document.querySelector('#result script'));") is False

class LocalDriver:
    def __init__(self,port):
        self.base='http://127.0.0.1:'+str(port)
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));self.session=None
    def call(self,path,method='GET',body=None):
        data=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(self.base+path,data=data,method=method,headers={'Content-Type':'application/json'})
        with self.opener.open(request,timeout=15) as response:result=json.load(response)
        value=result.get('value')
        if isinstance(value,dict) and value.get('error'):raise RuntimeError('native browser command failed')
        return value
    def execute(self,script,*arguments):
        return self.call('/session/'+quote(self.session,safe='')+'/execute/sync','POST',{'script':script,'args':list(arguments)})
    def wait(self,script,predicate,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=self.execute(script)
            if predicate(value):return value
            time.sleep(.1)
        raise AssertionError('native local browser readiness timeout')

@contextmanager
def owned_browser(binary,port):
    """Close owned session/process before profile; retain the primary fault."""
    profile=tempfile.TemporaryDirectory(prefix='parkweave-browser-synthetic-')
    proc=None;driver=None;primary=None
    try:
        proc=subprocess.Popen([str(binary),'--port='+str(port),'--allowed-ips=127.0.0.1'],env=minimal_environment(os.environ),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        driver=LocalDriver(port)
        yield driver,profile.name,proc
    except BaseException as exc:
        primary=exc
        raise
    finally:
        faults=[]
        if driver is not None and driver.session:
            try:driver.call('/session/'+quote(driver.session,safe=''),'DELETE');driver.session=None
            except Exception as exc:faults.append(type(exc).__name__)
        if proc is not None:
            try:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
            except Exception as exc:faults.append(type(exc).__name__)
        try:profile.cleanup()
        except Exception as exc:faults.append(type(exc).__name__)
        if faults:
            note='owned browser cleanup failed: '+','.join(faults)
            if primary is not None:
                primary.parkweave_owned_browser_cleanup=tuple(faults)
                primary.add_note(note)
            else:
                error=RuntimeError(note)
                error.parkweave_owned_browser_cleanup=tuple(faults)
                raise error

def run_browser(repo,token):
    if os.name!='nt':raise RuntimeError('NOT_RUN: native Server browser only')
    driver_root=os.environ.get('CHROMEWEBDRIVER')
    if not driver_root:raise RuntimeError('preinstalled ChromeDriver binding required')
    binary=Path(driver_root)/'chromedriver.exe'
    if not binary.is_file():raise RuntimeError('preinstalled ChromeDriver not found; no download')
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    with owned_browser(binary,port) as (driver,profile,proc):
        for _ in range(100):
            try:
                if driver.call('/status').get('ready'):break
            except OSError:pass
            if proc.poll() is not None:raise RuntimeError('native ChromeDriver exited')
            time.sleep(.1)
        else:raise RuntimeError('native ChromeDriver readiness timeout')
        caps={'capabilities':{'alwaysMatch':{'browserName':'chrome','goog:chromeOptions':{'args':['--headless=new','--disable-background-networking','--no-first-run','--user-data-dir='+profile]}}}}
        session=driver.call('/session','POST',caps);driver.session=session['sessionId']
        driver.call('/session/'+quote(driver.session,safe='')+'/url','POST',{'url':'http://127.0.0.1:8765'})
        driver.execute("document.querySelector('#token').value=arguments[0];return null;",token)
        driver.execute("document.querySelector('#goal').value=arguments[0];document.querySelector('#intake button').click();return null;",INJECTION_GOAL)
        run=driver.wait("return document.querySelector('#run').value;",lambda value:isinstance(value,str) and len(value)==36)
        # Actual user button refresh on the active API/independent worker.
        driver.execute("document.querySelector('[data-tab=collaboration]').click();document.querySelector('#refresh').click();return null;")
        def record_ready(value):
            try:return json.loads(value).get('state')=='SUCCEEDED'
            except (ValueError,TypeError):return False
        for _ in range(30):
            result=driver.execute("return document.querySelector('#result').textContent;")
            if record_ready(result):break
            driver.execute("document.querySelector('#refresh').click();return null;");time.sleep(.1)
        else:raise AssertionError('native worker did not complete browser case')
        record=json.loads(result);assert record['case']['state']=='NEEDS_INPUT' and record['case']['external_acceptance']=='NOT_SUBMITTED'
        verify_case_rendering(driver,record,result)
        driver.execute("document.querySelector('#candidate-region').value='SYNTHETIC native region';document.querySelector('#candidate-intake button').click();return null;")
        parent=driver.wait("return document.querySelector('#run').value;",lambda value:isinstance(value,str) and len(value)==36 and value!=run)
        for _ in range(30):
            driver.execute("document.querySelector('#review').click();return null;");time.sleep(.1)
            review=driver.execute("return typeof currentReview==='undefined'?null:currentReview;")
            if review:break
        else:raise AssertionError('native grouped review unavailable')
        assert [q['field'] for q in review['document']['necessary_questions']]==['region','employees','service_need']
        driver.execute("document.querySelector('#answer-employees').value='15';document.querySelector('#clarifications button').click();return null;")
        child=driver.wait("return document.querySelector('#run').value;",lambda value:isinstance(value,str) and len(value)==36 and value!=parent)
        for _ in range(30):
            driver.execute("document.querySelector('#review').click();return null;");time.sleep(.1)
            after=driver.execute("return typeof currentReview==='undefined'?null:currentReview;")
            if after and after['run_id']==child:break
        else:raise AssertionError('native clarification child not assessed')
        assert all(x['state']=='UNKNOWN' for x in after['document']['results'])
        driver.execute("document.querySelector('#cancel-clarification').click();return null;")
        cancel=driver.wait("try{return JSON.parse(document.querySelector('#result').textContent)}catch{return null;}",lambda value:isinstance(value,dict) and value.get('decision')=='CANCEL')
        assert cancel['run_id'] is None
        browser_version=session['capabilities'].get('browserVersion')
        driver.call('/session/'+quote(driver.session,safe=''),'DELETE');driver.session=None
        return {'environment':'native Windows Server engineering, not Win11 acceptance','browser_version':browser_version,
                'case':'NEEDS_INPUT','grouped_questions':3,'clarification':'UNKNOWN','cancel_only_followup':True,'injection_text_only':True,'real_model_calls':0}
