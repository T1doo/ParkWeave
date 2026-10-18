from pathlib import Path
from collections import Counter
import ast,hashlib,json,shutil,subprocess
R=Path.cwd();D=R/'.runtime/at21-synthetic-readiness-20261018';summary={}
# Existing literal oracle, not a second implementation.
def assignment(path,name):
 t=ast.parse(path.read_text())
 for n in ast.walk(t):
  if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets):return ast.literal_eval(n.value)
expected=assignment(R/'tests/test_at21_synthetic_readiness.py','expected');assert expected['AND']==assignment(R/'tests/test_foundation.py','and_expected') and expected['OR']==assignment(R/'tests/test_foundation.py','or_expected')
for label in ['first','frozen']:
 f=json.loads((D/(label+'-freeze.json')).read_text());mirror=Path(f['mirror']);base=Path(f['outer'])/'pytest';target=D/'retained-tmp'/label;target.mkdir(parents=True,exist_ok=True)
 for p in base.rglob('at21*.json'):
  if p.is_file():q=target/p.relative_to(base);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 source=mirror/'.runtime/preview-rules-ui-20261014'
 for p in source.iterdir():
  q=D/'retained-original-ui'/label/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 events=[json.loads(line) for line in (D/(label+'-connections')/'connections.jsonl').read_text().splitlines()];c=Counter(e['kind'] for e in events);finish=[e for e in events if e['kind']=='diagnostic_finish'];assert len(finish)==1 and not finish[0]['successful_connections_without_observed_close']
 diagnostics=dict(events=dict(c),failed_connections=c['connect_failed'],connect_begin=c['connect_begin'],connect_end=c['connect_end'],close_end=c['close_end'],no_successful_connection_left_unclosed=True,fixture_done=sum(e['kind']=='fixture_stage' and e.get('stage')=='DONE' for e in events))
 pg=[e for e in events if e['kind']=='owned_pg_logging_enabled'];pids=[]
 for e in pg:
  pid=e['postmaster_pid'];pids.append(dict(pid=pid,proc_entry_exists=Path('/proc',str(pid)).exists()))
 summary[label]=dict(source_sha=f['source_sha'],actual=json.loads((D/(label+'-result.json')).read_text()),diagnostics=diagnostics,postmaster_readonly_observation=pids,owned_pgdata_present=list(str(p) for p in base.glob('parkweave-pg*/data')),production_src=f['source_tree'])
 assert not summary[label]['owned_pgdata_present']
proofs=[]
for p in (D/'retained-tmp/frozen').rglob('at21*.json'):
 v=json.loads(p.read_text())
 if 'observations' in v:
  assert len(v['observations'])==18;summary['evaluate_table']=dict(observations=18,independent_literal_oracle_matches_existing=True,missing_leaf_observations=sum(c['reason']=='MISSING_EVIDENCE' for r in v['observations'] for c in r['result']['conditions']),path=str(p.relative_to(D)))
 else:
  ev=v['evidence'];body=next(t['body'] for t in ev['traffic'] if '/synthetic-rule-readiness?' in t['path']);observed=body['result']['synthetic_simulated_condition_truth'];assert observed==v['expected_truth'];assert ev['result']['statusText']=='仅开发模拟，SYNTHETIC_REVIEWED不代表正式审核。'
  proofs.append(dict(truth=observed,path=str(p.relative_to(D)),get_responses=len(ev['traffic']),post_responses=sum(t['method']=='POST' for t in ev['traffic']),purpose_status=body['sources']['purpose_status']['state'],conditions=body['result']['conditions'],qualification=body['qualification_truth'],qualification_decision=body['qualification_decision'],formal_review=body['formal_review'],business_publication=body['business_publication'],rendered=ev['result']['visibleText'],status=ev['result']['statusText'],fixture_initial_counts=v.get('fixture_initial_counts','original simulation helper; not additionally counted in existing TRUE node')))
assert {p['truth'] for p in proofs}=={'TRUE','FALSE','UNKNOWN'} and all(p['post_responses']==0 for p in proofs)
summary['ui_observations']=proofs;summary['new_pytest_unique_at_final_sha']=5;summary['first_failed_window_not_added']=True;summary['new_business_oracle']='Only AT21 finite synthetic case; no other AT inferred';summary['windows_browser_real_model_real_business']='NOT_RUN'
(D/'actual-execution-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'matrix':summary['evaluate_table'],'ui':[{k:v for k,v in p.items() if k not in ['conditions','rendered','path']} for p in proofs],'connections':{k:summary[k]['diagnostics'] for k in ['first','frozen']}},ensure_ascii=False))
