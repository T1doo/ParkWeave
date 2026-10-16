"""Read completed formal new window only; never trigger tests or edit product."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');formal=root/'.runtime/unified-propagation-final';out=root/'.runtime/unified-propagation-independent/final-62865b4'
sha='62865b43c470e2595cdb890b08f6b8e0d9113c9e'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=read(formal/'new.json');freeze=read(root/'.runtime/unified-propagation-root/freeze.json')
assert record['source_sha']==freeze['source_sha']==sha
assert record['exit_code']==0 and record['counts']==dict(PASS=88,FAIL=0,ERROR=0,SKIP=0)
assert record['collection_junit_exact_match'] and record['unique_junit_nodes']
assert not record['source_drift'] and not record['all_tracked_drift'] and not record['runner_drift']
assert read(formal/'new-before.json')==read(formal/'new-after.json')==freeze['source_paths']
cases=list(ET.parse(formal/'new.xml').iter('testcase'));assert len(cases)==88 and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
rows=[]
for path in (formal/'artifacts/new/test_unified_dependency_propagation_independent').glob('*.stdout.jsonl'):
    data=[json.loads(line) for line in path.read_text().splitlines()]
    if not data or not data[-1].get('scope','').startswith('FULL_ORIGINAL_HTML_UNIFIED'):continue
    result=data[-1];calls=result['calls'];traces=[v['trace'] for v in data if 'trace' in v];assert calls==traces
    adopt=[v for v in calls if v['method']=='POST' and v['path'].endswith('/service-case-plan')]
    verify=[v for v in calls if v['method']=='POST' and v.get('body',{}).get('action')=='VERIFY']
    cold=[v for v in calls if v['method']=='GET' and v['path'].endswith('/service-case-plan/command-recovery') and v.get('request_key')]
    row=dict(mode=result['mode'],raw_path=str(path.relative_to(root)),raw_sha256=digest(path),nativefetch_calls=len(calls),checks=result['checks'],adopt_commits=len([v for v in adopt if v['status']==201]),verify200=len([v for v in verify if v['status']==200]),distinct_verify_steps=len({v['body']['step_id'] for v in verify}),cold_get_key_matches_original=bool(cold) and len(adopt)==1 and all(v['request_key']==adopt[0]['request_key'] for v in cold),get_only=all(v['method']=='GET' for v in calls),actual403=len([v for v in calls if v['status']==403]),real_browser='NOT_RUN',python_control_http_total='NOT_RECORDED')
    assert result['fake_dto'] is False and result['real_browser']=='NOT_RUN'
    if result['mode'] in ('positive','lost_ack'):assert len(adopt)==row['adopt_commits']==1 and row['verify200']==row['distinct_verify_steps']==5
    else:assert row['get_only'] and row['actual403']==1
    if result['mode']=='lost_ack':assert row['cold_get_key_matches_original']
    rows.append(row)
assert len(rows)==4 and {r['mode'] for r in rows}=={'positive','lost_ack','current_403','late_403'}
out.mkdir(exist_ok=False)
value=dict(status='PASS',source_sha=sha,completed_formal_window='new',formal_passes=88,window_receipt_sha256=digest(formal/'new.json'),junit_sha256=digest(formal/'new.xml'),collection_sha256=digest(formal/'new-collection.json'),modes=rows,nativefetch_total=sum(r['nativefetch_calls'] for r in rows),mechanical_dom=True,actual_native_http=True,real_browser='NOT_RUN',python_control_http_total='NOT_RECORDED',old_preflight_scores_not_reused=True)
(out/'html.json').write_text(json.dumps(value,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(dict(status='LIMITED_PASS',source_sha=sha,checks=['completed88 formal collection/JUnit exact unique','allsource/tracked/runner hashes stable','4 original HTML actual fetch traces equal final calls','positive/lost each oneADOPT201 five distinctVERIFY200','lost original keyed coldGET','current/late actual403 read-only'],limitations=['MechanicalDOM not realbrowser','Python business-control API countNOT_RECORDED','No Windows/formalAT/realmodels/production']),indent=2)+'\n')
print(json.dumps(dict(status='PASS',source_sha=sha,nativefetch_total=value['nativefetch_total'],modes=[(r['mode'],r['nativefetch_calls']) for r in rows])))
