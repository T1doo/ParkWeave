"""Read original run9 evidence only; never execute a browser or business flow."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import struct
import zipfile

from scripts.fictional_park_narrow_browser_once import NEW_INPUT, PUBLIC_FILES, validate_probe
from scripts.fictional_park_restart_browser_once import unpack_font_diagnostics, charset_coverage

p=Path(__file__).parent
load=lambda name:json.loads((p/name).read_text())
r,run,job,check,meta=map(load,['result.json','run.json','job.json','check-run.json','artifact-metadata.json'])
source='d2028100c5df86ad25384d693e6ab0e5f91ebcbe'
assert r['source_sha']==run['head_sha']==source and run['run_number']==9 and run['run_attempt']==1
assert run['id']==39582035154 and job['id']==119161704779
assert run['conclusion']==job['conclusion']==check['conclusion']=='success'
assert r['status']=='PASS' and r['scope']=='FICTIONAL_PARK_NARROW_NEW_INPUT'
assert not r['cold_restart'] and r['cancel_scope']=='NOT_EXERCISED'
assert 'error' not in r and 'finalization_errors' not in r
steps={s['name']:s for s in job['steps']}
step=steps['Actual390px new-input fictional flow without cold replay']
assert step['conclusion']=='success'
assert 'sha256:'+sha256((p/'artifact.zip').read_bytes()).hexdigest()==meta['digest']
with zipfile.ZipFile(p/'artifact.zip') as z:
    assert set(z.namelist())==PUBLIC_FILES and len(z.infolist())==8
    assert sum(i.file_size for i in z.infolist())<=8388608
    for i in z.infolist():assert z.read(i)==(p/i.filename).read_bytes()
    members=z.namelist();artifact_bytes=sum(i.file_size for i in z.infolist())
log=(p/'ci-job-original.log').read_text(encoding='utf-8')
assert 'Process completed with exit code 1' not in log
pending=[json.loads(s[s.index('{'):]) for s in log.splitlines() if 'PENDING_FINALIZATION' in s and 'observation_outcome' in s]
assert len(pending)==1 and pending[0]['observation_outcome']=='PASS'
a=dict(pending[0]);a['status']=a.pop('observation_outcome');a.pop('terminal_result');b=dict(r)
for value in [a,b]:
    for key in ['seconds','seconds_scope']:value.pop(key,None)
assert a==b
stage=[json.loads(s[s.index('{'):]) for s in log.splitlines() if 'STAGED_VERIFIED' in s]
assert len(stage)==1;stage=stage[0]
(p/'font-staging-report.json').write_text(json.dumps(stage,indent=2)+'\n')
assert stage['assets']==r['approved_official_font']['receipt']['assets']
font=stage['assets']['NotoSansCJKsc-Regular.otf'];license=stage['assets']['LICENSE']
assert font['size']==16437364 and font['git_blob_sha1']=='dc15562470b4f842321894787a0d066879ccff8b'
assert font['sha256']=='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
assert license['size']==4301 and license['sha256']=='6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2'
f=r['installed_CJK_font'];d=unpack_font_diagnostics(f)
(p/'font-diagnostics.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
points=set(d['required_codepoints']);assert len(points)==687
for name in ['inventory','system-ui','sans-serif']:
    command=d['commands'][name];assert command['returncode']==0 and command['raw_public_complete']
    for stream in ['stdout','stderr']:
        raw=command[stream].encode()
        assert len(raw)==command[stream+'_bytes'] and sha256(raw).hexdigest()==command[stream+'_sha256']
        (p/(name+'.'+stream)).write_bytes(raw)
    union=set().union(*(charset_coverage(s.split('\t')[4],points) for s in command['stdout'].splitlines()))
    assert union==points
assert f['union_covered_count']==687 and f['rendering_observed']
n=r['narrow'];assert n['inputs']==NEW_INPUT and n['full_new_flow_complete']
assert len(n['font_observations'])==3
for observation,count in zip(n['font_observations'],[17,14,7]):
    assert observation['complete'] and len(observation['nodes'])==count
    for node in observation['nodes']:
        assert not node['missing_codepoints'] and not node['invalid_sources']
        assert any(face['postscript_name']=='NotoSansCJKsc-Regular' and face['sha256']==font['sha256'] for face in node['matched_faces'])
assert len(n['checkpoints'])==54 and len(n['controls'])==42 and len(n['trusted_clicks'])==20
for row in n['checkpoints']+n['controls']+n['trusted_clicks']:validate_probe(row)
assert all(row['trusted'] for row in n['trusted_clicks'])
assert len(r['screenshots'])==6
for shot in r['screenshots']:
    raw=(p/shot['file']).read_bytes();assert sha256(raw).hexdigest()==shot['sha256']
    assert raw[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',raw[16:24])==(390,1000)
separation=n['separation'];old,new=separation['old'],separation['new']
assert new==r['first'] and old==n['baseline']
for key in ['preparation_id','case_id','run_id']:assert old[key]!=new[key]
assert separation['old_history_before_sha256']==separation['old_history_after_sha256']
assert all(separation[key] for key in ['new_materials_exact','new_request_exact','receipt_exact','TXT_exact_ids'])
assert not separation['old_ADOPT_or_plan_created'] and r['old_baseline_history_unchanged']
txt=(p/'first-case-record-pack.txt').read_text()
for key in ['preparation_id','case_id','run_id','plan_id']:
    assert new[key] in txt and old.get(key,'NOT_AN_ID') not in txt
assert NEW_INPUT['goal'] in txt and NEW_INPUT['request'] in txt
assert r['results']['original_request']==NEW_INPUT['goal'] and r['results']['current_request']==NEW_INPUT['request']
for obj in [r['results'],r['receipt']['step'],r['resources']]:
    for key in ['preparation_id','case_id','run_id']:assert obj[key]==new[key]
assert r['receipt']['current_receipt']['text']==NEW_INPUT['receipt']
assert r['receipt']['current_receipt']['source_label']==NEW_INPUT['receipt_source']
assert r['receipt']['step']['state']=='LOCAL_ACKNOWLEDGED'
assert [(x['adapter_id'],x['state']) for x in r['results']['results']]==[(f'P{i}','LOCAL_OUTPUT_VERIFIED') for i in range(1,6)]
assert len(r['resources']['hold_ids'])==2
posts=[x for x in r['responses'] if x['method']=='POST']
assert len(posts)==33 and all(200<=x['status']<300 for x in posts)
refused=[x for x in r['responses'] if x['status']==403]
assert len(refused)==18 and all(x['method']=='GET' and x['path'].endswith('/fact-clarifications') for x in refused)
assert not r['violations'] and not r['page_errors']
assert r['authority_unchanged'] and r['run_assignments']==0 and r['owned_services_stopped'] and r['input_files_unchanged']
assert r['JS_business_calls']==r['API_business_writes']==r['real_model_calls']==0
assert r['real_browser'] and not any(r[k] for k in ['formal_source','formal_AT35','Windows'])
assert n['work_completion_seconds']<270 and r['seconds']<360
assert check['output'].get('summary') is None
seconds=lambda start,end:(datetime.fromisoformat(end.replace('Z','+00:00'))-datetime.fromisoformat(start.replace('Z','+00:00'))).total_seconds()
validation=dict(status='PASS_LIMITED_DESKTOP_CHROME_390_NEW_INPUT',source_sha=source,
    run_id=run['id'],job_id=job['id'],run_url=run['html_url'],run_number=9,run_attempt=1,
    job_seconds=seconds(job['started_at'],job['completed_at']),browser_step_seconds=seconds(step['started_at'],step['completed_at']),
    browser_seconds=r['seconds'],browser_seconds_scope=r['seconds_scope'],work_completion_seconds=n['work_completion_seconds'],
    terminal=dict(result='PASS',browser_step='success',process_exit_zero_inferred_from_step_success=True,job='success',
        stdout='PENDING_FINALIZATION observation,not terminal PASS',normalized_log_observation_equals_result=True,step_summary_body_verified=False,check_run_summary=None),
    actual_scope=['Same390x1000 viewport from guide/setup through new-input intake,independent REVIEW/CONFIRM,NO_MODEL selection/ADOPT',
        'New9-instrument monthly goal/request/two materials,two resource holds/combination,dispatch/accept/manual receipt/ACK,P1-P5,TXT',
        'Old6-device baseline only independently reviewed/confirmed,no ADOPT;declared case_history projection equal before/after,new UUIDs/materials/receipt/TXT exact',
        'Normal Playwright DOM actions,zero direct JS/API business writes,no force click;owned services stopped'],
    geometry=dict(viewport=[390,1000],root_checkpoints=54,explicit_pre_control_probes=42,trusted_click_events=20,
        trusted_click_scope='Guide controls only in actual artifact;no workspace trusted-click records',
        proof_limit='Workspace normal Playwright DOM clicks and root/pre-control probes passed;no event-time workspace VERIFY geometry was recorded'),
    old=old,new=new,old_history_projection_sha256=separation['old_history_before_sha256'],business_POSTs=33,refused_fact_clarification_GET403=18,
    font=dict(codepoints=687,original683_retained=True,new_points='仪月温湿',actual_resolved_chains=[687,687],
        visible_node_parents=[17,14,7],phases=[x['stage'] for x in n['font_observations']],
        font_sha256=font['sha256'],license_sha256=license['sha256'],system_install=False,binary_in_public_archive=False,
        scope='Actual named viewport node-level fonts/charset union and six original screenshots;not all687 per-glyph pixel acceptance'),
    screenshot_captions={'01':'Guide/session input masked;initial390px viewport',
        '02':'New9-instrument monthly materials,full supplied text visible',
        '03':'NewCase adopted service plan header/current predecessor block;not final P1-P5 state',
        '04':'Acknowledged manual synthetic receipt body/source/deadline visible',
        '05':'Revalidated TXT download confirmation and newCase/Run IDs;not a screenshot of allP1-P5 cards',
        '06':'Old6-device materials retained;new monthly material absent'},
    original_artifact=dict(files=members,uncompressed_bytes=artifact_bytes,zip_bytes=(p/'artifact.zip').stat().st_size,zip_sha256=sha256((p/'artifact.zip').read_bytes()).hexdigest()),
    original_log=dict(bytes=(p/'ci-job-original.log').stat().st_size,sha256=sha256((p/'ci-job-original.log').read_bytes()).hexdigest(),source='GitHub authorized decoded full job log API,not CLI filtered output'),
    TXT=dict(bytes=(p/'first-case-record-pack.txt').stat().st_size,sha256=sha256((p/'first-case-record-pack.txt').read_bytes()).hexdigest()),
    actual_business_status={k:r['results'][k] for k in ['case_goal_completed','qualification','external_acceptance','offline_fulfillment']},
    limits=dict(job_seconds=600,browser_seconds=360,dependency_seconds=180,attempt=1,new_runs=1,reruns=0,files=10,bytes=8388608),
    tests=dict(targeted20='Pure fixtures only,not browser acceptance',collection9406='Actual five collect-only runs,not testsPASS',cold_run8='Previously reviewed,not reexecuted'),
    remaining=['Step summary body not independently retrieved;check-run API output null;terminal judged by canonical result and successful actual step/job',
        'No workspace trusted-click event records;pre-control/root geometry plus actual normal DOM actions only',
        'Not physical phone/touch/browser matrix,not all687 per-glyph pixel acceptance',
        'Old history full projection pairs not separately serialized;source equality assertion and matching fingerprints,not whole DB invariant',
        'No cold restart/reuse/cancellation revalidation this run;run8 limited facts retained separately',
        'Formal source/AT35/Windows owner-DACL/native installation/real models/business fulfillment remain unverified'])
(p/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:validation[k] for k in ['status','source_sha','job_seconds','browser_seconds','geometry','original_artifact','original_log','TXT']},ensure_ascii=False,indent=2))
