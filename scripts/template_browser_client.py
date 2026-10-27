"""Owned Chrome original page + explicitly disclosed read-only real HTTP relay.

No downloads, installs, runtime fallback, mock API bodies or bearer in Chrome.
All HTTP document/favicon/API GETs share the bootstrap's original20-GET budget.
"""
from contextlib import contextmanager
from hashlib import sha1,sha256
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
CHROME=Path('/opt/google/chrome/chrome')
FONT_RELATIVE='.runtime/approved-noto-run48'
ASSETS={'LICENSE':(4301,'d952d62c065f3f35fb83a173496e90b21525aef3'),
        'NotoSansCJKsc-Regular.otf':(16437364,'dc15562470b4f842321894787a0d066879ccff8b')}
IMAGES=('01-wide-checked.png','02-wide-refreshed.png','03-narrow-checked.png','04-narrow-refreshed.png')
FILE_LIMIT=10;BYTES_LIMIT=8*1024*1024;PNG_LIMIT=2*1024*1024
LABEL='SYNTHETIC / REAL LOCAL API VIA READ-ONLY RELAY / NO_MODEL'
PLACEHOLDER='Bearer SYNTHETIC_HTTP_SESSION'


class Closed(RuntimeError):pass


def small_fault(error):return {'type':type(error).__name__ if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}',type(error).__name__) else 'OTHER','errno':None}


def bytes_file(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise Closed('bounded ordinary asset required')
        chunks=[];size=0
        while size<=limit:
            raw=os.read(fd,min(1024*1024,limit+1-size))
            if not raw:break
            chunks.append(raw);size+=len(raw)
        after=os.fstat(fd)
        if size>limit or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or not os.path.samestat(after,path.lstat()):raise Closed('asset drift')
        return b''.join(chunks)
    finally:os.close(fd)


def asset_bytes(directory,name):
    size,blob=ASSETS[name];raw=bytes_file(directory/name,size)
    if len(raw)!=size or sha1(f'blob {size}\0'.encode()+raw).hexdigest()!=blob:raise Closed('approved font or license drift')
    return raw


def preflight(root,private):
    # Read-only requirements, before initdb/authority creation. No fallback.
    if importlib.util.find_spec('playwright.sync_api') is None:raise Closed('existing Playwright required')
    st=CHROME.lstat()
    if CHROME.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_uid not in (0,os.geteuid()) or st.st_mode&0o022 or not st.st_mode&0o111:raise Closed('existing standard Chrome required')
    directory=root/FONT_RELATIVE
    if directory.is_symlink() or directory.resolve()!=directory:raise Closed('fixed existing approved font cache required')
    for name in ASSETS:asset_bytes(directory,name)
    if not Path('/usr/bin/fc-match').is_file():raise Closed('existing fontconfig required')


def timeout(clock,seconds,*,cleanup=False):
    if clock.left(seconds,cleanup=cleanup)<seconds:raise TimeoutError('insufficient original time for required wait')
    return seconds*1000


@contextmanager
def private_driver_environment(private):
    # Enter only AFTER the original cluster receipt/migration, so Python's
    # tempfile ownership check continues to use its original/tmp contract.
    # This is the dedicated worker/child home configuration, never a shell
    # scratch variable or any alteration to the host account's home directory.
    browser_home_directory=private/'tmp/chrome-home'
    values={'TMPDIR':str(private/'tmp'),'HOME':str(browser_home_directory),
            'XDG_CACHE_HOME':str(private/'tmp/chrome-cache'),'XDG_CONFIG_HOME':str(private/'tmp/chrome-config'),
            'XDG_DATA_HOME':str(private/'tmp/chrome-data'),'XDG_STATE_HOME':str(private/'tmp/chrome-state'),
            'XDG_RUNTIME_DIR':str(private/'tmp/chrome-runtime')}
    old={key:os.environ.get(key) for key in values}
    try:
        for key,path in values.items():
            path=Path(path);path.mkdir(mode=0o700,exist_ok=True)
            st=path.lstat()
            if path.is_symlink() or path.resolve()!=path or st.st_uid!=os.geteuid() or st.st_mode&0o077:raise Closed('private driver directory required')
            os.environ[key]=str(path)
        yield values
    finally:
        for key,value in old.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def font_environment(private,clock):
    directory=private/'fonts';directory.mkdir(mode=0o700,exist_ok=False)
    for name in ASSETS:
        raw=asset_bytes(ROOT/FONT_RELATIVE,name)
        with (directory/name).open('xb') as stream:stream.write(raw)
    config=directory/'fonts.conf'
    config.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>'+escape(str(directory))+'</dir><cachedir>'+escape(str(directory/'cache'))+'</cachedir></fontconfig>')
    env=dict(os.environ,FONTCONFIG_FILE=str(config))
    resolved=subprocess.check_output(['/usr/bin/fc-match','-f','%{file}','Noto Sans CJK SC'],env=env,timeout=clock.left(5),stderr=subprocess.DEVNULL).decode()
    if resolved!=str(directory/'NotoSansCJKsc-Regular.otf'):raise Closed('private font resolution required')
    return env


class Relay:
    def __init__(self,http,record,page_sha):self.http=http;self.record=record;self.page_sha=page_sha;self.failed=False
    def route(self,route):
        request=route.request
        try:
            self.http.clock.left()
            parsed=urlsplit(request.url)
            if request.method!='GET' or request.post_data is not None or parsed.scheme not in ('http',) or request.url!=self.http.origin+parsed.path+('?' + parsed.query if parsed.query else ''):raise Closed('exact loopback GET required')
            path=parsed.path+('?' + parsed.query if parsed.query else '')
            api=path.startswith('/api/');headers=request.all_headers()
            if api and headers.get('authorization')!=PLACEHOLDER:raise Closed('browser placeholder identity required')
            if not api and headers.get('authorization'):raise Closed('no document credentials')
            if path=='/favicon.ico':
                if self.record['favicon_GET']>=2:raise Closed('favicon resource bound')
                self.record['favicon_GET']+=1
            code,(raw,headers)=self.http.request('GET',path,stage='browser',raw=True)
            if path=='/template-upgrade' and (code!=200 or sha256(raw).hexdigest()!=self.page_sha):raise Closed('original HTML response mismatch')
            if path=='/favicon.ico' and code!=404:raise Closed('original missing favicon expected')
            if api and code not in (200,403):raise Closed('unexpected real API status')
            self.record['forwarded_GET']+=1
            route.fulfill(status=code,headers=headers,body=raw)
        except BaseException:
            self.failed=True;self.record['blocked_requests']+=1
            route.abort('blockedbyclient')


def state(page):
    return page.evaluate("""() => ({checked:inspection!==null,pending:pending!==null,busy,hasResult:!!$('result').textContent,clear:['result','receipt','application','apply-receipt'].every(id=>$ (id).textContent===''),confirm:$('apply-confirm').checked,reason:$('apply-reason').value,target:$('target').value,targetCount:$('target').options.length,applyDisabled:$('apply').disabled,returnHidden:$('original-case').hidden,error:$('error').textContent.includes('无权'),width:innerWidth,scrollWidth:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})""")


def font_observed(page):
    session=page.context.new_cdp_session(page)
    try:
        session.send('DOM.enable');session.send('CSS.enable');root=session.send('DOM.getDocument')['root']['nodeId']
        node=session.send('DOM.querySelector',{'nodeId':root,'selector':'h1'})['nodeId']
        fonts=session.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
        if not any(f['postScriptName']=='NotoSansCJKsc-Regular' and f['glyphCount']>0 and not f['isCustomFont'] for f in fonts):raise Closed('visible heading font not observed')
    finally:session.detach()


def snapshot(page,private,name,clock,record):
    observed=state(page)
    if observed['scrollWidth']>observed['width'] or observed['height']>12000:raise Closed('page geometry overflow')
    page.wait_for_function("() => [...document.getAnimations()].every(a=>a.playState!=='running')",timeout=timeout(clock,15))
    font_observed(page)
    data=page.screenshot(full_page=True,mask=[page.locator('#token')],timeout=timeout(clock,15))
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)>PNG_LIMIT:raise Closed('PNG budget')
    dest=private/name
    with dest.open('xb') as stream:stream.write(data)
    record['images'].append({'name':name,'bytes':len(data),'sha256':sha256(data).hexdigest()})


def sandbox(browser,page,private,clock,record):
    session=browser.new_browser_cdp_session()
    try:args=session.send('Browser.getBrowserCommandLine')['arguments']
    finally:session.detach()
    forbidden={'--no-sandbox','--disable-setuid-sandbox','--disable-seccomp-filter-sandbox','--disable-namespace-sandbox','--disable-gpu-sandbox','--no-zygote','--disable-web-security'}
    if any(arg.split('=',1)[0] in forbidden for arg in args):raise Closed('sandbox switches refused')
    profiles=[Path(arg.split('=',1)[1]) for arg in args if arg.startswith('--user-data-dir=')]
    if len(profiles)!=1:raise Closed('single owned browser profile required')
    profile=profiles[0];st=profile.lstat()
    if profile.resolve()!=profile or not profile.is_relative_to(private/'tmp') or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o077:raise Closed('browser profile escaped private root')
    page.goto('chrome://sandbox',timeout=timeout(clock,30));text=page.locator('body').inner_text(timeout=timeout(clock,15))
    if 'You are adequately sandboxed.' not in text or re.search(r'Seccomp-BPF sandbox\s+Yes',text) is None or re.search(r'PID namespaces\s+Yes',text) is None:raise Closed('actual sandbox status required')
    record['sandbox_observed']=True;record['chrome_internal_navigations']=1


def run(http,owner,private,clock,report,business_snapshot,page_sha,checkpoint):
    from playwright.sync_api import sync_playwright
    record=report['browser']={'transport':'READ_ONLY_REAL_HTTP_RELAY_NOT_DIRECT_TCP','status':'RUNNING','browser_close':'NOT_CREATED','driver_stop':'NOT_CREATED','forwarded_GET':0,'favicon_GET':0,'blocked_requests':0,'pageerrors':0,'sandbox_observed':False,'chrome_internal_navigations':0,'checks':[],'images':[]}
    pw=None;browser=None;primary=None;errors=[];contexts=[];relays=[]
    before=business_snapshot(owner)
    try:
        with private_driver_environment(private):
            env=font_environment(private,clock)
            try:
                pw=sync_playwright().start();record['driver_stop']='UNKNOWN'
                browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run'],env=env,timeout=timeout(clock,15));record['browser_close']='UNKNOWN'
                pages=[]
                for width in (1200,390):
                    context=browser.new_context(viewport={'width':width,'height':1000},service_workers='block');contexts.append(context)
                    page=context.new_page();page.set_default_timeout(timeout(clock,15));page.set_default_navigation_timeout(timeout(clock,30))
                    page.on('pageerror',lambda error:record.__setitem__('pageerrors',record['pageerrors']+1))
                    if width==1200:sandbox(browser,page,private,clock,record)
                    relay=Relay(http,record,page_sha);relays.append(relay);context.route('**/*',relay.route)
                    response=page.goto(http.origin+'/template-upgrade',wait_until='load',timeout=timeout(clock,30))
                    if response is None or response.status!=200:raise Closed('original page response required')
                    page.evaluate("label=>{const p=document.createElement('p');p.dataset.testScope='true';p.textContent=label;p.style.cssText='padding:10px 14px;background:#fff0d9;color:#723d22;border:1px solid #a2562c;border-radius:8px;overflow-wrap:anywhere';document.querySelector('h1').after(p);}",LABEL)
                    page.locator('#token').fill('SYNTHETIC_HTTP_SESSION');page.locator('#instance').fill(http.instance)
                    page.locator('#catalog').click();page.wait_for_function("() => !busy&&$('target').options.length===1",timeout=timeout(clock,15))
                    if page.locator('#target').input_value()!=http.target:raise Closed('exact current target required')
                    page.locator('#check').click();page.wait_for_function('() => !busy&&inspection!==null',timeout=timeout(clock,15))
                    if not state(page)['hasResult'] or not state(page)['applyDisabled']:raise Closed('real inspection required without adoption')
                    page.locator('#apply-confirm').check();page.locator('#apply-reason').fill('SYNTHETIC old confirmation must clear on refresh')
                    index=0 if width==1200 else 2;snapshot(page,private,IMAGES[index],clock,record)
                    page.locator('#catalog').click();page.wait_for_function('() => !busy&&inspection===null',timeout=timeout(clock,15));current=state(page)
                    if not current['clear'] or current['confirm'] or current['reason'] or not current['returnHidden'] or current['target']!=http.target or not current['applyDisabled']:raise Closed('refresh must clear old inspection and confirmation')
                    snapshot(page,private,IMAGES[index+1],clock,record)
                    page.locator('#check').click();page.wait_for_function('() => !busy&&inspection!==null',timeout=timeout(clock,15))
                    record['checks'].append('WIDE_REFRESH_REAL_HTTP' if width==1200 else 'NARROW_REFRESH_REAL_HTTP');pages.append(page);checkpoint()
                if business_snapshot(owner)!=before:raise Closed('browser read changed business records')
                owner.revoke_capability('fixture-a','READ')
                for index,page in enumerate(pages):
                    page.locator('#check').click();page.wait_for_function("() => !busy&&$('error').textContent.includes('无权')",timeout=timeout(clock,15));current=state(page)
                    if current['checked'] or current['pending'] or not current['clear'] or current['targetCount'] or not current['applyDisabled']:raise Closed('403 must clear old page data')
                    record['checks'].append('WIDE_REAL_403_CLEAR' if index==0 else 'NARROW_REAL_403_CLEAR')
                if record['pageerrors'] or record['blocked_requests'] or any(r.failed for r in relays):raise Closed('browser invariants failed')
            except BaseException as error:primary=error
            finally:
                if browser is not None:
                    try:browser.close();record['browser_close']='CLOSED'
                    except BaseException as error:errors.append(small_fault(error))
                if pw is not None:
                    try:pw.stop();record['driver_stop']='STOPPED'
                    except BaseException as error:errors.append(small_fault(error))
    except BaseException as error:
        if primary is None:primary=error
        else:errors.append(small_fault(error))
    if primary is None and not errors:
        try:
            if business_snapshot(owner)!=before or record['pageerrors'] or record['blocked_requests'] or any(r.failed for r in relays):raise Closed('late browser invariants failed')
            if http.posts!=12 or http.gets!=3+record['forwarded_GET'] or record['forwarded_GET']!=12+record['favicon_GET'] or http.gets>20:raise Closed('exact shared HTTP count failed')
            if record['browser_close']!='CLOSED' or record['driver_stop']!='STOPPED':raise Closed('browser exit unknown')
        except BaseException as error:primary=error
    if primary is not None or errors:
        record['status']='FAIL';error=primary or Closed('browser cleanup unknown');error.http_cleanup_errors=errors;raise error
    record['status']='PASS';checkpoint()


def validate_report(record):
    keys={'transport','status','browser_close','driver_stop','forwarded_GET','favicon_GET','blocked_requests','pageerrors','sandbox_observed','chrome_internal_navigations','checks','images'}
    if type(record) is not dict or set(record)!=keys or record['transport']!='READ_ONLY_REAL_HTTP_RELAY_NOT_DIRECT_TCP' or record['status'] not in ('RUNNING','PASS','FAIL') or record['browser_close'] not in ('NOT_CREATED','UNKNOWN','CLOSED') or record['driver_stop'] not in ('NOT_CREATED','UNKNOWN','STOPPED'):raise Closed('browser report shape')
    for name,maximum in [('forwarded_GET',20),('favicon_GET',2),('blocked_requests',32),('pageerrors',32),('chrome_internal_navigations',1)]:
        if type(record[name]) is not int or not 0<=record[name]<=maximum:raise Closed('browser report count')
    if type(record['sandbox_observed']) is not bool or type(record['checks']) is not list or len(record['checks'])>4 or any(x not in ('WIDE_REFRESH_REAL_HTTP','NARROW_REFRESH_REAL_HTTP','WIDE_REAL_403_CLEAR','NARROW_REAL_403_CLEAR') for x in record['checks']):raise Closed('browser observation')
    images=record['images']
    if type(images) is not list or len(images)>4:raise Closed('image list')
    for index,item in enumerate(images):
        if type(item) is not dict or set(item)!={'name','bytes','sha256'} or item['name']!=IMAGES[index] or type(item['bytes']) is not int or not 0<item['bytes']<=PNG_LIMIT or type(item['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',item['sha256']) is None:raise Closed('image manifest')
    if sum(x['bytes'] for x in images)+2*1024*1024>BYTES_LIMIT:raise Closed('shared export bytes')


def publish_images(root,evidence,record,deadline):
    validate_report(record)
    if (record['status']!='PASS' or record['browser_close']!='CLOSED' or record['driver_stop']!='STOPPED' or not record['sandbox_observed'] or record['blocked_requests'] or record['pageerrors'] or len(record['images'])!=4 or len(set(record['checks']))!=4):raise Closed('confirmed browser export required')
    root.verify();evidence.verify();result=[]
    for item in record['images']:
        if time.monotonic()>=deadline:raise TimeoutError('same total export deadline')
        raw=bytes_file(root.path/item['name'],PNG_LIMIT)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)!=item['bytes'] or sha256(raw).hexdigest()!=item['sha256']:raise Closed('image bytes changed')
        with (evidence.path/item['name']).open('xb') as stream:stream.write(raw)
        if bytes_file(evidence.path/item['name'],PNG_LIMIT)!=raw:raise Closed('published image readback differs')
        result.append(item)
    if len(list(evidence.path.iterdir()))>FILE_LIMIT or sum(p.stat().st_size for p in evidence.path.iterdir())>BYTES_LIMIT:raise Closed('whole evidence budget')
    return result
