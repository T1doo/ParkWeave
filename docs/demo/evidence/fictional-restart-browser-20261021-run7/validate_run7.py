"""Audit original run7 artifacts/logs; no execution of the business flow."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile
from scripts.fictional_park_restart_browser_once import unpack_font_diagnostics,charset_coverage

p=Path(__file__).parent
load=lambda n:json.loads((p/n).read_text())
r,run,job,check,meta=map(load,['result.json','run.json','job.json','check-run.json','artifact-metadata.json'])
source='cd42c06ecd2a1094ef48000afb302c47e5ebd77a'
assert r['source_sha']==run['head_sha']==source and run['run_number']==7 and run['run_attempt']==1
assert run['conclusion']==job['conclusion']==check['conclusion']=='failure'
assert r['status']=='FAIL' and r['stage']=='COLD_RESTART_SAME_STATE' and not r['cold_restart']
assert 'cold_processes' not in r and 'restart_read_only' not in r
assert r['error_type']=='AssertionError' and 'ORDINARY_SYNTHETIC_DEMO_BLOCKED: OSError' in r['error']
assert 'sha256:'+sha256((p/'artifact.zip').read_bytes()).hexdigest()==meta['digest']
with zipfile.ZipFile(p/'artifact.zip') as z:
    assert len(z.infolist())==6 and sum(i.file_size for i in z.infolist())<=8388608
    for i in z.infolist():assert z.read(i)==(p/i.filename).read_bytes()
    members=z.namelist();artifact_bytes=sum(i.file_size for i in z.infolist())
log=(p/'ci-job-original.log').read_text(encoding='utf-8')
assert '##[error]Process completed with exit code 1.' in log
pending=[json.loads(s[s.index('{'):]) for s in log.splitlines() if 'PENDING_FINALIZATION' in s and 'observation_outcome' in s]
assert len(pending)==1 and pending[0]['observation_outcome']=='FAIL'
a=dict(pending[0]);a['status']=a.pop('observation_outcome');a.pop('terminal_result')
b=dict(r)
for d in [a,b]:
    for key in ['seconds','seconds_scope']:d.pop(key,None)
assert a==b
stage=load('font-staging-report.json');assert stage['status']=='STAGED_VERIFIED'
assert stage['assets']==r['approved_official_font']['receipt']['assets']
assets=stage['assets'];font=assets['NotoSansCJKsc-Regular.otf'];license=assets['LICENSE']
assert font['size']==16437364 and font['git_blob_sha1']=='dc15562470b4f842321894787a0d066879ccff8b'
assert license['size']==4301 and license['git_blob_sha1']=='d952d62c065f3f35fb83a173496e90b21525aef3'
f=r['installed_CJK_font'];d=unpack_font_diagnostics(f)
assert d==load('font-diagnostics.json')
points=set(d['required_codepoints']);assert len(points)==683
for name in ['inventory','system-ui','sans-serif']:
    command=d['commands'][name];assert command['returncode']==0 and command['raw_public_complete']
    for stream in ['stdout','stderr']:
        raw=command[stream].encode('utf-8')
        assert len(raw)==command[stream+'_bytes'] and sha256(raw).hexdigest()==command[stream+'_sha256']
        (p/(name+'.'+stream)).write_bytes(raw)
    raw=command['stdout'];rows=[line.split('\t') for line in raw.splitlines()]
    union=set().union(*(charset_coverage(parts[4],points) for parts in rows))
    assert union==points
assert f['candidate_count']==54 and f['eligible_count']==54 and f['union_covered_count']==683 and not f['missing_codepoints']
assert f['rendering_observed'] and len(f['visible_node_font_usage'])==26
for node in f['visible_node_font_usage']:
    assert not node['missing_codepoints'] and not node['invalid_sources']
    assert any(face['postscript_name']=='NotoSansCJKsc-Regular' and face['sha256']==font['sha256'] for face in node['matched_faces'])
for shot in r['screenshots']:assert sha256((p/shot['file']).read_bytes()).hexdigest()==shot['sha256']
posts=[row for row in r['responses'] if row['method']=='POST'];assert len(posts)==34 and all(200<=x['status']<300 for x in posts)
refused=[x for x in r['responses'] if x['status']==403];assert len(refused)==18 and all(x['method']=='GET' and x['path'].endswith('/fact-clarifications') for x in refused)
assert r['first_history_unchanged'] and r['authority_unchanged'] and r['run_assignments']==0
assert not r['page_errors'] and not r['violations'] and r['owned_services_stopped'] and r['input_files_unchanged']
assert r['receipt']['step']['state']=='LOCAL_ACKNOWLEDGED'
txt=(p/'first-case-record-pack.txt').read_text()
for key in ['preparation_id','case_id','run_id','plan_id']:assert r['first'][key] in txt
assert check['output'].get('summary') is None
seconds=(datetime.fromisoformat(job['completed_at'].replace('Z','+00:00'))-datetime.fromisoformat(job['started_at'].replace('Z','+00:00'))).total_seconds()
fix_source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
output=dict(status='FAIL_PRESERVED_NO_RETRY_NOT_COLD_ACCEPTANCE',run_url=run['html_url'],source_sha=source,
    fix_source_sha=fix_source,run_number=7,run_attempt=1,job_id=job['id'],job_seconds=seconds,
    script_seconds=r['seconds'],first_stage_seconds=r['first_stage_seconds'],font_staging_seconds=stage['seconds'],
    actual_scope=['Fixed original font/license downloaded privately and size/Git blob/SHA256 checked; no system install',
        '683/683 actual fontconfig inventory and two resolved chains;26 real guide nodes font usage mapped',
        'Normal sandbox Chrome DOM first intake/review/confirm/ADOPT/P1-P5/resource association/dispatch/accept/manual receipt/ACK/TXT',
        'Second explicit reuse plus independent REVIEW/CONFIRM and cancellation before ADOPT/dispatch;390px first history retained',
        'First context closed and original services stopped; cold child CLI failed before ready; no recovery reads'],
    terminal=dict(artifact='FAIL',logged_exit=1,job='failure',stdout='PENDING_FINALIZATION observation only',summary_body_verified=False,summary_api_value=None,
        normalized_logged_business_report_equals_result=True),
    failure=dict(stage=r['stage'],outer_type=r['error_type'],child_type='OSError',errno=None,
        exact_cold_start_operation_unknown=True,cold_processes_observed=False,cold_cleanup_verified=False,
        owned_services_stopped_flag_scope='first initial server exit only'),
    font=dict(size=font['size'],git_blob=font['git_blob_sha1'],sha256=font['sha256'],license_sha256=license['sha256'],
        required=683,inventory_rows=54,two_resolved_chains_covered=[683,683],visible_guide_nodes=26,
        visual_scope='Original guide and390px screenshots legible at viewed viewport;not all683 per-glyph pixel acceptance',
        font_binary_in_archive=False,system_font_install=False),
    screenshots=dict(count=4,guide_and_mobile_CJK_legible=True,
        receipt03_caveat='Viewport mainly shows notices/progress/local run;only bottom RECEIPT heading, no ACK body/status. ACK is JSON evidence.'),
    business_POSTs_success=34,fact_clarifications_GET403=18,cancel_scope=r['cancel_scope'],
    original_artifact=dict(files=members,file_count=6,uncompressed_bytes=artifact_bytes,zip_bytes=(p/'artifact.zip').stat().st_size,
        zip_sha256=sha256((p/'artifact.zip').read_bytes()).hexdigest()),
    source_checks=dict(font_stage='9 fixture groups PASS fake bytes zero network;not product test count',
        port_fix='baseline exact check_port EADDRINUSE with no listener due TIME_WAIT;fixed passes;live REUSEADDR listener refused/preserved',
        occupied_port_pytest='1 passed 2 warnings in0.39s',run7_actual_errno_not_inferred=True),
    remaining=['Cold recovery after real API/PostgreSQL restart has not passed;new context/old deadline/full role views/TXT equality not reached',
        'Run7 child OSError exact errno/line and cold cleanup not observed;job ended so private instance cannot be recovered',
        'SO_REUSEADDR candidate source fix not executed in hosted browser CI;no automatic rerun',
        'Step summary body not retrieved;only result/log exit/job joint evidence available',
        'Formal sources/AT35/Windows owner-DACL/native migrations/real model/business fulfillment remain unverified'])
(p/'validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:output[k] for k in ['status','source_sha','fix_source_sha','job_seconds','script_seconds','first_stage_seconds','terminal','failure','font','original_artifact']},ensure_ascii=False,indent=2))
