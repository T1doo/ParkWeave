"""Read final evidence only; this program performs no business/test action."""
from collections import Counter
from pathlib import Path
import ast
import hashlib
import json
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
NAME,SOURCE=sys.argv[1:3]
def load(suffix):return json.loads((BASE/(NAME+suffix)).read_text())
def save(suffix,value):(BASE/(NAME+suffix)).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
r=load('.json')
assert r['source_sha']==r['head_after']==SOURCE
assert r['exit_code']==0 and r['counts']==dict(PASS=28,FAIL=0,ERROR=0,SKIP=0)
assert not r['source_drift'] and not r['all_tracked_drift'] and not r['source_status_after']
assert all(r[k] for k in ('runner_unchanged','plugin_unchanged','legacy_plugin_unchanged','legacy_roots_unchanged'))
assert load('-before.json')==load('-after.json') and load('-all-tracked-before.json')==load('-all-tracked-after.json')
assert len(load('-before.json'))==r['tracked_source_paths'] and len(load('-all-tracked-before.json'))==r['all_tracked_paths']
collection=load('-collection.json');assert len(collection)==len(set(collection))==28
passed=set()
for c in ET.parse(BASE/(NAME+'.xml')).iter('testcase'):
 assert all(c.find(k) is None for k in ('failure','error','skipped'))
 p=c.get('classname').split('.');i=next(i for i,s in enumerate(p) if s.startswith('test_'))
 passed.add('tests/'+p[i]+'.py::'+'::'.join(p[i+1:]+[c.get('name')]))
assert set(collection)==passed and r['collection_junit_exact_match'] and r['unique_junit_nodes']
source=ROOT/'tests/test_note_template_carry_independent.py'
manual=next(ast.literal_eval(n.value) for n in ast.parse(source.read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MANUAL' for t in n.targets))
records=load('-related-traces.json')['records']+load('-own-traces.json')['records'];assert len({x['path'] for x in records})==len(records)
baselines=[];oracles=[];closures=[];flows=[];refusals=[];abas=[]
for item in records:
 p=ROOT/item['path'];assert '.private.' not in p.name and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'] and item['source_sha']==SOURCE
 if p.suffix!='.jsonl':continue
 rows=[json.loads(line) for line in p.read_text().splitlines() if line]
 if p.name.startswith('baseline-'):baselines+=rows
 elif p.name.startswith('oracle-'):oracles+=rows
 elif p.name.startswith('closures-'):closures+=rows
 elif p.name.startswith('refusals-'):refusals+=rows
 elif p.name.startswith('aba-'):abas+=rows
 elif p.name.endswith('.stdout.jsonl'):
  values=[x for x in rows if x.get('scope')=='FULL_ORIGINAL_HTML_NOTE_TEMPLATE_CARRY_ACTUAL_HTTP_ASGI_OWNED_PG'];assert len(values)==1
  value=values[0];value['trace']=item['path'];value['trace_sha256']=item['sha256'];flows.append(value)
assert len(baselines)==28 and all(x['source_sha']==SOURCE and len(x['required_goals'])==len(set(x['required_goals']))==6 and len(x['step_ids'])==5 and x['note']['origin']=='MANUAL' and x['note']['text']==manual for x in baselines)
stats=dict(records=len(oracles),expected_affected_pairs=0,actual_affected_pairs=0,missed_count=0,wrong_count=0,wrong_preserved_count=0)
for x in oracles:
 assert x['source_sha']==SOURCE and not x['intentional_unknown']
 e=set(x['expected_affected']);a=set(x['actual_affected']);stats['expected_affected_pairs']+=len(e);stats['actual_affected_pairs']+=len(a);stats['missed_count']+=len(e-a);stats['wrong_count']+=len(a-e);stats['wrong_preserved_count']+=len(set(x['expected_preserved'])^set(x['actual_preserved']))
assert len(oracles)==2 and stats['expected_affected_pairs']==stats['actual_affected_pairs']==5 and not any(stats[k] for k in ('missed_count','wrong_count','wrong_preserved_count'))
assert len(closures)==4 and all(x['source_sha']==SOURCE and x['six_goals_current'] and x['actual_outputs_preserved'] and x['manual_note_exact'] and x['stable_ids_contract_history'] for x in closures)
assert len(flows)==2 and {x['mode'] for x in flows}=={'title_locked','source_changed'}
expected_fields={'expected_instance_id','target_release_id','expected_target_sha256','expected_check_sha256','expected_choice_revision','expected_choice_event_sha256','expected_plan_id','expected_plan_revision','expected_preparation_revision','expected_source_sha256','reason','expected_note_carry_sha256','confirm_note_carry'}
for flow in flows:
 assert flow['six_goals_current'] and flow['manual_preserved'] and flow['stable_plan_and_history'] and flow['real_browser']=='NOT_RUN' and flow['fake_dto'] is False
 posts=[c for c in flow['calls'] if c['method']=='POST' and c['path'].endswith('/apply-note-carry')];assert len(posts)==1
 assert set(posts[0]['body'])==expected_fields and type(posts[0]['body']['confirm_note_carry']) is bool and posts[0]['body']['confirm_note_carry'] is True
 assert all(c['status']<400 for c in flow['calls'])
 verifies=[c for c in flow['calls'] if c['method']=='POST' and c.get('body',{}).get('action')=='VERIFY']
 assert len(verifies)==(5 if flow['mode']=='source_changed' else 0)
 assert flow['controlled_committed_response_loss']==(flow['mode']=='source_changed')
assert all(x['source_sha']==SOURCE and x['no_business_write'] for x in refusals)
assert len(abas)==4 and {x['kind'] for x in abas}=={'material','note','parent','action_grant'} and all(x['fixture_fault_injection'] and x['visible_original_restored'] for x in abas)
private=BASE/('redaction-'+NAME+'.private.json');assert stat.S_IMODE(private.stat().st_mode)==0o600
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SOURCE and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
summary=dict(source_sha=SOURCE,counts=r['counts'],elapsed_seconds=r['elapsed_seconds'],source_paths=r['tracked_source_paths'],all_tracked_paths=r['all_tracked_paths'],drift=[],collection_junit_exact=True,api_items=26,full_html_flows=2,actual_html_http_requests=sum(len(x['calls']) for x in flows),captured_python_test_body_http=load('-http-traffic.json')['count'],successful_six_goal_closures=4,known_template_impact_oracle=stats,unknown_impact_precision='NOT_MEASURED_IN_THIS_MODULE',actual_unknown_refusal_nodes=[n for n in collection if 'test_actual_catalog_unknown' in n],exact_preserved_lock_check='title_locked full after.steps == before.steps, including original P1/P3 lock objects; zero original UNLOCK/VERIFY calls',old_verified_evidence='Both HTML modes compare original verified SHA and sources before recheck',aba_scope='4 owned-PG fault injections; target legal publish/withdraw tests are partial variants, not arbitrary SQLite restoration detection',cold_get='Actual committed source_changed carry response dropped, fresh VM only GETs original key then verifies typed carry proof',original_readonly_auth='READ/PREPARE/case.create required; EXECUTE revocation alone preserves legitimate historical GET and refuses POST',private_mode='0600',private_values_exported=False,real_browser='NOT_RUN',Windows='NOT_RUN',formal_AT_signoff='NOT_RUN',real_model_calls=0,production='NOT_RUN',validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
save('-validation.json',summary);save('-oracle-statistics.json',dict(source_sha=SOURCE,known=stats,unknown_precision='NOT_MEASURED'))
save('-html-summary.json',dict(source_sha=SOURCE,flows=[{k:v for k,v in x.items() if k!='calls'}|dict(requests=len(x['calls']),posts=sum(c['method']=='POST' for c in x['calls'])) for x in flows]))
print(json.dumps(summary,sort_keys=True))
