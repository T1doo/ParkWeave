"""Read only completed WIP-window sources; emit independent evidence index."""
from collections import Counter
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parent
NAME='full-v1'
ART=BASE/'artifacts'/NAME
COL=json.loads((BASE/(NAME+'-collection.json')).read_text())
RESULT=json.loads((BASE/(NAME+'.json')).read_text())
BEFORE=json.loads((BASE/(NAME+'-before.json')).read_text())
AFTER=json.loads((BASE/(NAME+'-after.json')).read_text())
classes={}
for case in ET.parse(BASE/(NAME+'.xml')).iter('testcase'):
    if not case.get('name') or not case.get('classname'):continue
    status='FAIL' if case.find('failure') is not None else 'ERROR' if case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
    node=case.get('classname').replace('.','/')+'.py::'+case.get('name')
    assert node not in classes,node
    classes[node]=dict(status=status,seconds=float(case.get('time','0')))
records={}
for source in ART.rglob('*.jsonl'):
    if source.name.endswith('.stdout.jsonl') or source.name.startswith('baseline-') and source.parent.name=='baseline':continue
    kind=source.name.rsplit('-',1)[0]
    for line_number,line in enumerate(source.read_text().splitlines(),1):
        row=json.loads(line)
        if 'run_id' not in row:continue
        records.setdefault(kind,[]).append(dict(row,artifact=str(source.relative_to(BASE)),line=line_number))

precision={}
for label,unknown in [('known',False),('intentional_UNKNOWN',True)]:
    rows=[r for r in records.get('oracle',[]) if r['intentional_unknown']==unknown]
    precision[label]=dict(rows=len(rows),expected_affected=sum(len(r['expected_affected']) for r in rows),
        actual_affected=sum(len(r['actual_affected']) for r in rows),expected_preserved=sum(len(r['expected_preserved']) for r in rows),
        actual_preserved=sum(len(r['actual_preserved']) for r in rows),missed=sum(r['missed_count'] for r in rows),
        wrong=sum(r['wrong_count'] for r in rows),wrong_preserved=sum(r['wrong_preserved_count'] for r in rows),
        scenarios=dict(Counter(r['scenario'] for r in rows)),
        precision_claim='CONSERVATIVE_ENVELOPE_ONLY' if unknown else 'LITERAL_ADAPTER_SET_COMPARISON')
html=[]
for row in records.get('html-results',[]):
    source=BASE/row['artifact'];trace=source.parent/row['trace']
    values=[json.loads(line) for line in trace.read_text().splitlines()]
    output=[v for v in values if v.get('scope')=='FULL_ORIGINAL_HTML_MULTIFIELD_PACKAGE_ACTUAL_HTTP_ASGI_OWNED_PG']
    assert len(output)==1,trace
    data=output[0];calls=data['calls'];mode=data['mode']
    statuses=Counter(str(c['status']) for c in calls)
    package_posts=[c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-material-package/commands')]
    recovery=[c for c in calls if c['method']=='GET' and '/plan-material-package/recovery/' in c['path']]
    html.append(dict(mode=mode,trace=str(trace.relative_to(BASE)),trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
        checks=data['checks'],calls=len(calls),methods=dict(Counter(c['method'] for c in calls)),statuses=dict(statuses),
        actual_loopback_http=True,full_original_script=True,ASGI_and_owned_PG=True,
        browser='NOT_RUN_NODE_VM_WITH_DOM_MECHANICS_DOUBLE',fake_DTO=data['fake_dto'],
        package_POSTs=len(package_posts),original_key_recovery_GETs=len(recovery),
        controlled_client_transport_failure=mode=='dual_merge_lost_ack',
        actual_backend_committed_before_response_discard=mode=='dual_merge_lost_ack',
        actual_backend_403=any(c['status']==403 for c in calls),
        six_goals_worklist_closure=mode in ('summary_keep','dual_merge_lost_ack')))

http=json.loads((BASE/(NAME+'-http-traffic.json')).read_text())
phase_free=lambda value:value.rsplit(' (',1)[0]
baselines={phase_free(r['test']):r for r in records.get('baseline',[]) if 'cases' in r}
unknown_packages=[]
for row in records.get('package-previews',[]):
    view=row['view']
    if view.get('unknown_scope')!='THIS_CASE':continue
    baseline=baselines[phase_free(row['test'])]['cases'][row['label']]
    expected=set(baseline['step_ids'].values())
    actual=set(view['affected']);preserved=set(view['preserved'])
    unknown_packages.append(dict(test=phase_free(row['test']),artifact=row['artifact'],line=row['line'],
        expected_affected=sorted(expected),actual_affected=sorted(actual),actual_preserved=sorted(preserved),
        missed=len(expected-actual),wrong=len(actual-expected),wrong_preserved=len(preserved),
        new_action_templates=len(view['action_requests']),conservative_envelope_only=True))
private_paths=list(BASE.glob('redaction-'+NAME+'.private.json'))+list(ART.rglob('*.private.json'))
private_values=set()
for source in private_paths:
    value=json.loads(source.read_text())
    if isinstance(value,list):private_values.update(v for v in value if isinstance(v,str))
    elif isinstance(value,dict):private_values.update(v for v in value.get('values',[]) if isinstance(v,str))
scan=[]
# Public structured evidence is scanned, raw failed logs deliberately remain private originals.
for source in [BASE/(NAME+'-collection.json'),BASE/(NAME+'-http-traffic.json'),*(p for p in ART.rglob('*') if p.is_file() and not p.name.endswith('.private.json'))]:
    data=source.read_text(errors='replace')
    exact=sum(v in data for v in private_values)
    prefix=sum(v[:16] in data for v in private_values if len(v)>=16)
    if exact or prefix:scan.append(dict(path=str(source.relative_to(BASE)),full=exact,prefix16=prefix))

report=dict(kind='INDEPENDENT_DEVELOPMENT_WINDOW_VALIDATION_NOT_FORMAL_GATE',window=NAME,
    observed_git_HEAD=RESULT['source_sha'],implementation_uncommitted_WIP=True,exit_code=RESULT['exit_code'],
    collected=len(COL),named_executed=len(classes),status_counts=dict(Counter(v['status'] for v in classes.values())),
    collection_junit_missing=sorted(set(COL)-set(classes)),junit_uncollected=sorted(set(classes)-set(COL)),
    paths_compared=len(BEFORE),source_and_private_driver_drift=[p for p in set(BEFORE)|set(AFTER) if BEFORE.get(p)!=AFTER.get(p)],
    head_unchanged=RESULT['source_sha']==RESULT['head_after'],precision=precision,
    independent_saved_UNKNOWN_package_envelope_checks=unknown_packages,
    closures=len(records.get('closures',[])),closure_six_goals_current=sum(bool(r.get('six_goals_current')) for r in records.get('closures',[])),
    closures_unaffected_B_exact=sum(bool(r.get('unaffected_B_exact')) for r in records.get('closures',[])),
    actual_HTTP_Python_test_call_count=http['count'],actual_HTTP_Python_methods=dict(Counter(r['method'] for r in http['requests'])),
    HTTP_scope='Python fixture clients during test-call phase only; Node fetch traffic counted separately; no fixture setup request total claim',
    html=html,refusal_records=len(records.get('refusals',[])),ABA_records=len(records.get('aba',[])),
    union_records=len(records.get('union-results',[])),private_registries=len(private_paths),
    private_synthetic_values=len(private_values),public_structured_full_or_prefix16_matches=scan,
    all_named_results=classes,record_artifacts={k:len(v) for k,v in records.items()},
    NOT_RUN=['real browser','Windows','formal AT','real model','production','deployment'])
(BASE/(NAME+'-validation.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in {'all_named_results','html'}},ensure_ascii=False,indent=2))
assert len(COL)==24
assert set(COL)==set(classes)
assert not report['source_and_private_driver_drift'] and report['head_unchanged']
assert not scan
assert RESULT['exit_code']==0 and report['status_counts']=={'PASS':24}
assert {h['mode'] for h in html}=={'summary_keep','dual_merge_lost_ack','current_403','late_403'}
assert all(not h['fake_DTO'] for h in html)
assert all(not p['missed'] and not p['wrong'] and not p['wrong_preserved'] for p in precision.values())
assert all(not p['missed'] and not p['wrong'] and not p['wrong_preserved'] and not p['new_action_templates'] for p in unknown_packages)
