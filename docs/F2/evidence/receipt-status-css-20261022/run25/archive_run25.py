"""Validate and preserve exact official run25 originals; no browser execution."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json, shutil

raw=Path(__file__).parent/'official'
out=Path('/workspace/ParkWeave/docs/F2/evidence/receipt-status-css-20261022/run25')
out.mkdir(parents=True,exist_ok=False)
read=lambda p:json.loads(p.read_text())
hashfile=lambda p:sha256(p.read_bytes()).hexdigest()
run=read(raw/'run-api.json');job=read(raw/'job-api.json')['jobs'][0]
artifact=read(raw/'artifact-metadata.json')['artifacts'][0];r=read(raw/'artifact/result.json')
source='257341af6b3e57bbb1bb278e4834e7e525e70b22'
assert run['id']==39805195077 and run['run_number']==25 and run['run_attempt']==1
assert run['head_sha']==source and run['conclusion']=='success'
assert job['id']==119916438725 and job['head_sha']==source and job['conclusion']=='success'
assert all(s['conclusion']=='success' for s in job['steps'])
assert r['source_sha']==source and r['status']=='PASS' and r['stage']=='COMPLETE'
assert not any(r.get(k) for k in ('error','finalization_errors','browser_errors','unexpected_GET','violations','cleanup_errors'))
assert r['real_browser'] and r['browser_version']=='155.0.8059.39'
assert 'You are adequately sandboxed.' in r['sandbox_status']
assert not any(x in r['chrome_arguments'] for x in ('--no-sandbox','--disable-setuid-sandbox'))
assert r['browser_close']=='CLOSED' and r['listener_after_cleanup']=='REFUSED'
assert r['elapsed_seconds']<90 and r['seconds']<360
assert len(r['requests'])==len(r['browser_requests'])==17
assert all(x['method']=='GET' for x in r['requests']) and all(x['allowed'] for x in r['browser_requests'])
assert r['business_POSTs']==0 and not r['business_API'] and not r['database'] and r['real_model_calls']==0
assert r['screen_reader_announcement']=='NOT_TESTED'
assert len(r['checks'])==9 and r['checks'][0]['height']==28 and r['checks'][0]['borderLeft']=='3px'
expected=[(width,label) for width in (1200,390) for label in ('after-empty','after-unknown','after-recovered','after-cleared')]
assert [(m['viewport']['width'],m['label']) for m in r['checks'][1:]]==expected
for m in r['checks'][1:]:
    assert m['exists'] and m['ariaLive']=='polite' and m['display']=='block'
    assert m['withinViewport'] and m['verticallyVisible'] and not m['pageOverflow']
    if m['label'] in ('after-empty','after-cleared'):
        assert not m['text'] and m['height']==0 and m['background']=='rgba(0, 0, 0, 0)'
        assert all(m[k]=='0px' for k in ('paddingTop','paddingBottom','marginTop','marginBottom','borderLeft'))
    else:
        assert m['text'] and m['borderLeft']=='3px' and m['paddingTop']=='14px'
        assert m['scrollHeight']<=m['clientHeight']+1
assert r['source_binding']['outside_style_identical']
assert r['source_binding']['before_sha256']=='1a009ce52a31e463643cf5768ae474fcbeb78c15e9fe3443e1976f6155745bb4'
assert r['source_binding']['after_sha256']=='1174b0f0d835cd46f6562db9360fb8e4d680701c43300c2cefe7042077b02d33'
assert [(x['width'],x['label']) for x in r['font_observations']]==[(w,l) for w in (1200,390) for l in ('after-unknown','after-recovered')]
for observed in r['font_observations']:
    m=next(m for m in r['checks'][1:] if (m['viewport']['width'],m['label'])==(observed['width'],observed['label']))
    target=[n for n in observed['nodes'] if n['selector']=='#receipt-submit-status'];assert len(target)==1
    target=target[0];assert target['text_sha256']==sha256(m['text'].encode()).hexdigest()
    points=sorted({ord(c) for c in m['text'] if 0x3400<=ord(c)<=0x9fff or 0x3000<=ord(c)<=0x303f or 0xff00<=ord(c)<=0xffef})
    assert target['required_codepoints']==points and not target['missing_codepoints'] and not target['invalid_sources']
    assert set(points)<=set().union(*(set(f['covered_visible_codepoints']) for f in target['matched_faces']))
assert artifact['digest']=='sha256:'+hashfile(raw/'artifact.zip')
assert hashfile(raw/'artifact.zip')=='defe51b1af218e2c7b245916ff19c59f274c6d2915eebb84027b93aabb96cef8'
assert hashfile(raw/'ci-original.log')=='05937a05cb97f893af07e70b4ee5c9bdfd1453495d8a359eb64d8e3af1283146'
with ZipFile(raw/'artifact.zip') as z:
    assert len(z.namelist())==6 and sum(i.file_size for i in z.infolist())==598023
    for name in z.namelist():
        assert '/' not in name and z.read(name)==(raw/'artifact'/name).read_bytes()
        shutil.copyfile(raw/'artifact'/name,out/name)
log=(raw/'ci-original.log').read_text()
lines=[line.partition('Z ')[2] for line in log.splitlines() if line.partition('Z ')[2].startswith('{"kind": "REAL_BROWSER_UI_CSS_WITH_SYNTHETIC_GET_REPLAY"')]
assert len(lines)==1
v=json.loads(lines[0]);assert v['status']=='PENDING_FINALIZATION';v['status']=v.pop('observation_outcome');v.pop('terminal_result')
assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert '$GITHUB_STEP_SUMMARY upload aborted' not in log and 'Process completed with exit code 1.' not in log
for name in ('artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json'):
    shutil.copyfile(raw/name,out/name)
for name in ('archive_run25.py','font_target_checks.py','font-target-checks.log'):
    shutil.copyfile(Path(__file__).parent/name,out/name)
validation=dict(status='LIMITED_CSS_BROWSER_PASS',source_sha=source,run_id=run['id'],run_number=25,attempt=1,
    job_id=job['id'],artifact_id=artifact['id'],real_browser=r['browser_version'],normal_sandbox=True,
    viewport_widths=[1200,390],after_states_per_width=4,geometry_observations=9,original_PNGs=5,
    empty_before_height=28,empty_after_and_cleared_height=0,DOM_aria_live_preserved=True,
    nonempty_heights_px={'1200':[52.5,52.5],'390':[77,77]},nonempty_visible_unclipped=True,
    exact_target_font_observations=4,visible_CJK_parents_per_observation=[len(x['nodes']) for x in r['font_observations']],
    font_scope='Exact target text node and visible CDP parents with original charset union; not glyph-to-codepoint attribution or whole-page pixel acceptance',
    browser_same_origin_GETs=17,server_exact_GETs=17,business_POSTs=0,unexpected_GETs=0,page_errors=0,violations=0,
    boundary='Browser enforces same scheme/host/port GET and request count; server exact paths only, other paths404 then terminal failure',
    browser_close='CLOSED',cleanup_errors=[],listener_after_cleanup='REFUSED',UI_cleanup_seconds=r['elapsed_seconds'],publication_scan_seconds=r['seconds'],
    terminal='result.json PASS plus official job and browser step success/zero shell exit; stdout PENDING_FINALIZATION is not final PASS',
    summary='No upload-aborted log; summary body not independently read',
    scope='Full original HTML/JS with controlled synthetic GET replay; no product API, database or actual business recovery',
    screen_reader_announcement='NOT_TESTED',formal_AT35=False,installed_wheel=False,cold_restart=False,Windows=False,real_model_calls=0,
    run24='FAIL_ORIGINALS_PRESERVED',local_sandbox_failure='ORIGINALS_PRESERVED_NO_RETRY',automatic_reruns=0)
(out/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False))
