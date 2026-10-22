"""Preserve the failed run26 exactly; no product/browser execution."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json,shutil
raw=Path(__file__).parent/'official'
out=Path('/workspace/ParkWeave/docs/demo/evidence/workspace-visual-refinement-20261022/run26')
out.mkdir(parents=True,exist_ok=False)
read=lambda p:json.loads(p.read_text())
digest=lambda p:sha256(p.read_bytes()).hexdigest()
run=read(raw/'run-api.json');job=read(raw/'job-api.json')['jobs'][0]
a=read(raw/'artifact-metadata.json')['artifacts'][0];r=read(raw/'artifact/result.json')
source='4a1c52826059991df3586679745670077bb4cefc'
assert run['id']==39829147881 and run['run_number']==26 and run['run_attempt']==1
assert run['head_sha']==source and run['conclusion']=='failure'
assert job['id']==120000330770 and job['conclusion']=='failure'
assert [s['name'] for s in job['steps'] if s['conclusion']=='failure']==['Original pages visual refinement sandboxed browser verification']
assert r['source_sha']==source and r['status']=='FAIL' and r['stage']=='CHROME_SANDBOX'
assert r['error_type']=='TimeoutError' and 'BrowserType.launch: Timeout 15000ms exceeded.' in r['error']
assert '<launched> pid=2466' in r['error'] and '--no-sandbox' not in r['error']
assert not any(r[k] for k in ('requests','browser_requests','checks','font_observations','business_POSTs','real_model_calls','product_API','database'))
assert not r.get('browser_close') and r['cleanup_errors']==[] and r['listener_after_cleanup']=='REFUSED'
assert r['elapsed_seconds']<90 and r['seconds']<360
assert r['installed_CJK_font']['status']=='INSTALLED_CHARSET_COVERS_UI'
assert not r['installed_CJK_font'].get('rendering_observed')
assert all(v['outside_style_identical'] for v in r['source_binding'].values())
assert a['digest']=='sha256:'+digest(raw/'artifact.zip')
assert digest(raw/'artifact.zip')=='a130522fbe068ac8be8ae895761919749ef0ad3fcdb90e439b8dcac38c1fa616'
assert digest(raw/'ci-original.log')=='5dc79ec3cef9e02b1cc04a286fd73a4590d81c211547d12eb9073274108e5803'
with ZipFile(raw/'artifact.zip') as z:
    assert z.namelist()==['result.json'] and z.read('result.json')==(raw/'artifact/result.json').read_bytes()
    assert z.infolist()[0].file_size==119206
shutil.copyfile(raw/'artifact/result.json',out/'result.json')
log=(raw/'ci-original.log').read_text()
rows=[s.partition('Z ')[2] for s in log.splitlines() if s.partition('Z ')[2].startswith('{"scope": "REAL_CHROME_ORIGINAL_PAGES_PRESENTATION_NO_BACKEND"')]
assert len(rows)==1
v=json.loads(rows[0]);assert v['status']=='PENDING_FINALIZATION';v['status']=v.pop('observation_outcome');v.pop('terminal_result')
assert v=={k:v for k,v in r.items() if k not in ('seconds','seconds_scope')}
assert 'Process completed with exit code 1.' in log
for name in ('artifact.zip','ci-original.log','run-api.json','job-api.json','artifact-metadata.json'):
    shutil.copyfile(raw/name,out/name)
for name in ('archive_run26.py','source-binding.json','preflight.json'):
    shutil.copyfile(Path(__file__).parent/name,out/name)
validation=dict(status='FAIL_PRESERVED_NO_PAGE_EXECUTED',source_sha=source,run_id=run['id'],run_number=26,attempt=1,
    job_id=job['id'],artifact_id=a['id'],failure_stage='CHROME_LAUNCH_SANDBOX_REQUESTED_NOT_VERIFIED',failure='15s launch timeout',
    launch_reported_pid=2466,pages_opened=0,HTTP_GETs=0,business_POSTs=0,geometry_checks=0,font_rendering_checks=0,screenshots=0,
    static_font_preflight='PASS_NOT_RENDERING',outside_style_identical=True,
    cleanup='Owned replay listener REFUSED, cleanup_errors empty; no returned Browser object and no CLOSED proof, child exit not established',
    cause='UNKNOWN: only stable-channel warning; no explicit sandbox rejection, product request or CSS failure observed',
    UI_cleanup_seconds=r['elapsed_seconds'],publication_scan_seconds=r['seconds'],automatic_retries=0,
    summary='No summary body independently read; stdout PENDING is not final PASS',
    visual_acceptance='NOT_RUN',business_acceptance='NOT_RUN',model_calls=0)
(out/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(validation,ensure_ascii=False))
