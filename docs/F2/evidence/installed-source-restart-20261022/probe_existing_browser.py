from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright
from scripts.fictional_park_restart_browser_once import installed_font_environment
from scripts import local_approval_installed_browser_once as old
p=Path('/workspace/scratch/installed-source-restart-20261022/existing-browser-probe');p.mkdir(mode=0o700)
r=dict(scope='EXISTING_BROWSER_SANDBOX_FONT_PREFLIGHT_NO_BUSINESS',status='NOT_RUN')
env=old.minimal_env()
for k,name in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
 q=p/name;q.mkdir(mode=0o700);env[k]=str(q)
try:
 env=installed_font_environment(env,p/'fontconfig',r)
 with sync_playwright() as pw:
  with pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=env) as browser:
   r['version']=browser.version;old.base.resource.verify_sandbox(browser,r)
 r['status']='PASS_NO_BUSINESS_NO_DOWNLOAD'
except BaseException as e:r.update(status='FAIL',error_type=type(e).__name__,error=str(e));raise
finally:(p/'probe.json').write_text(json.dumps(r,indent=2)+'\n')
print(r['status'])
