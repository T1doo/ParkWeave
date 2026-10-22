"""Preserve run24 originals and verify its limited, failed execution; no browser."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json, shutil

raw = Path(__file__).parent / 'official'
out = Path('/workspace/ParkWeave/docs/F2/evidence/receipt-status-css-20261022/run24')
out.mkdir(parents=True, exist_ok=False)
read = lambda p: json.loads(p.read_text())
hashfile = lambda p: sha256(p.read_bytes()).hexdigest()
run = read(raw/'run-api.json')
job = read(raw/'job-api.json')['jobs'][0]
artifact = read(raw/'artifact-metadata.json')['artifacts'][0]
r = read(raw/'artifact/result.json')
source = '773bde665de4883953329d05b4f5c8dc82f7e2bf'
assert run['head_sha'] == source and run['id'] == 39802376995
assert run['run_number'] == 24 and run['run_attempt'] == 1 and run['conclusion'] == 'failure'
assert job['id'] == 119906296876 and job['head_sha'] == source and job['conclusion'] == 'failure'
assert [s['name'] for s in job['steps'] if s['conclusion']=='failure'] == ['Receipt status CSS four states sandboxed browser verification']
assert r['source_sha'] == source and r['status'] == 'FAIL' and r['stage'] == 'AFTER_1200'
assert r['real_browser'] and r['browser_version'] == '155.0.8059.84'
assert 'You are adequately sandboxed.' in r['sandbox_status']
assert not any(a in r['chrome_arguments'] for a in ('--no-sandbox','--disable-setuid-sandbox'))
assert 'Page.wait_for_function: EvalError:' in r['error'] and 'unsafe-eval' in r['error']
assert r['business_POSTs'] == 0 and not r['database'] and not r['business_API'] and r['real_model_calls'] == 0
assert len(r['requests']) == len(r['browser_requests']) == 7 and all(x['method']=='GET' for x in r['requests'])
assert r['unexpected_GET'] == ['/api/run-access/status']*2 and not r['browser_errors']
assert r['cleanup_errors'] == ['browser:Error'] and r['failure_screenshot_error'] == 'Error'
assert r['listener_after_cleanup']=='REFUSED' and r['elapsed_seconds'] < 90
before, after = r['checks']
assert before['label']=='before-empty' and before['height']==28 and before['borderLeft']=='3px'
assert after['label']=='after-empty' and after['height']==0 and after['viewport']['width']==1200
assert after['exists'] and after['ariaLive']=='polite' and after['display']=='block'
assert all(after[k]=='0px' for k in ('paddingTop','paddingBottom','marginTop','marginBottom','borderLeft'))
assert after['background']=='rgba(0, 0, 0, 0)' and not after['pageOverflow']
assert r['source_binding']['outside_style_identical']
assert r['source_binding']['before_sha256']=='1a009ce52a31e463643cf5768ae474fcbeb78c15e9fe3443e1976f6155745bb4'
assert r['source_binding']['after_sha256']=='1174b0f0d835cd46f6562db9360fb8e4d680701c43300c2cefe7042077b02d33'
assert artifact['digest']=='sha256:'+hashfile(raw/'artifact.zip')
assert hashfile(raw/'artifact.zip')=='7525e5b2040f4aeca75aa28a68126821cbe8e2993b92957eb6af0191e6c59fa8'
assert hashfile(raw/'ci-original.log')=='e26823e4541f6ae2254a664fd80e6f5dadc2baedbac77c21efc2a71e26ee784b'
with ZipFile(raw/'artifact.zip') as z:
    assert set(z.namelist())=={'result.json','01-before-empty-desktop.png','02-after-empty-desktop.png'}
    assert sum(i.file_size for i in z.infolist())==304506
    for name in z.namelist():
        assert z.read(name)==(raw/'artifact'/name).read_bytes()
        shutil.copyfile(raw/'artifact'/name,out/name)
log=(raw/'ci-original.log').read_text()
lines=[line for line in log.splitlines() if line.partition('Z ')[2].startswith('{"kind": "REAL_BROWSER_UI_CSS_WITH_SYNTHETIC_GET_REPLAY"')]
assert len(lines)==1
v=json.loads(lines[0].partition('Z ')[2]);v['status']=v.pop('observation_outcome');v.pop('terminal_result')
assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert 'Process completed with exit code 1.' in log
assert '$GITHUB_STEP_SUMMARY upload aborted' not in log
for name in ('artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json'):
    shutil.copyfile(raw/name,out/name)
shutil.copyfile(Path(__file__),out/'archive_run24.py')
validation=dict(status='FAIL_PRESERVED',source_sha=source,run_id=run['id'],run_number=24,attempt=1,
    job_id=job['id'],artifact_id=artifact['id'],actual_browser=r['browser_version'],normal_sandbox=True,
    actual_checks=2,actual_original_screenshots=2,GETs=7,POSTs=0,
    empty_before_px=28,empty_after_px=0,DOM_aria_live_preserved=True,
    scope='Full original HTML CSS with synthetic GET replay; no business API/database/model',
    failure='Driver string wait_for_function rejected by original-style CSP; not a product CSS failure',
    additional_diagnostics='Two original token-change GET run-access/status requests were unmodelled404; not successes',
    cleanup='Replay listener REFUSED; browser.close reported Error after Playwright scope exit; not clean-browser-exit proof',
    pending=['nonempty unknown message','nonempty recovery success','clearing','390px','actual visible glyph-source inspection'],
    summary='No upload-aborted warning in full log; summary body not independently read',
    screen_reader_announcement='NOT_TESTED',automatic_reruns=0)
(out/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False))
