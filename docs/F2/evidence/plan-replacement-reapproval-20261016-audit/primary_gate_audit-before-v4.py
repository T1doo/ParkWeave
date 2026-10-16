"""Read-only independent seal/gate/receipt audit; no tests or subprocesses."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,datetime,collections,re

def verify_primary(root,require,index_entries,raw_eligible):
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 phase=root/'.runtime/plan-replacement-root/v3';freeze=json.loads((phase/'freeze.json').read_text());source=freeze['source_sha']
 gate_path=phase/'final-gate.json';gate=json.loads(gate_path.read_text())
 require(gate['source_sha']==source and gate['status']=='LIMITED_PASS_WITH_PROFILE_GAP','final gate scope/source/status mismatch')
 selection=json.loads((phase/'final-selection.json').read_text());planned=json.loads((phase/'final-windows.json').read_text())
 def time(value):
  t=datetime.datetime.fromisoformat(value);require(t.tzinfo is not None,'naive receipt timestamp');return t
 def receipt(name,expected_modules):
  require(re.fullmatch('[A-Za-z0-9_-]{1,90}',name) is not None,'unsafe window name')
  p=phase/'final'/(name+'.json');v=json.loads(p.read_text())
  require(v['source_sha']==source,'receipt source mismatch '+name)
  require(v['modules']==expected_modules,'receipt module selection mismatch '+name)
  require(v['exit_code']==0,'receipt exit not zero '+name)
  for k in ('source_drift','all_tracked_drift','runner_drift'):require(type(v[k]) is list and v[k]==[],'receipt drift '+name+' '+k)
  require(v['tracked_source_paths']==len(freeze['source_paths']) and v['all_tracked_paths']==len(freeze['all_tracked_sha256']),'receipt file counts differ '+name)
  for label,expected in (('before',freeze['source_paths']),('after',freeze['source_paths']),('all-tracked-before',freeze['all_tracked_sha256']),('all-tracked-after',freeze['all_tracked_sha256'])):
   actual=json.loads((phase/'final'/(name+'-'+label+'.json')).read_text());require(actual==expected,'raw manifest mismatch '+name+' '+label)
  xml_args=[a.split('=',1)[1] for a in v['argv'] if a.startswith('--junitxml=')]
  require(len(xml_args)==1,'one original JUnit destination required '+name)
  xml_path=(root/xml_args[0]).resolve();require(xml_path.is_relative_to(phase.resolve()),'JUnit path outside final phase '+name)
  cases=list(ET.parse(xml_path).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);nodes=[];keys=[]
  for c in cases:
   child_tags={x.tag for x in c};state='ERROR' if 'error' in child_tags else 'FAIL' if 'failure' in child_tags else 'SKIP' if 'skipped' in child_tags else 'PASS';counts[state]+=1
   classname=c.get('classname','');tokens=classname.split('.');bases=[(i,t) for i,t in enumerate(tokens) if t.startswith('test_')]
   require(bool(bases),'unsupported JUnit classname '+name)
   i,base=bases[0];node='tests/'+base+'.py::'+'::'.join(tokens[i+1:]+[c.get('name','')]);nodes.append(node);keys.append(dict(classname=classname,name=c.get('name')))
  collected=json.loads((phase/'final'/(name+'-collection.json')).read_text())
  require(counts==v['counts'] and keys==v['testcase_keys'],'raw JUnit counts/keys mismatch '+name)
  require(collected==v['collected_nodes'] and sorted(nodes)==sorted(collected),'raw collection/JUnit mismatch '+name)
  require(len(nodes)==len(set(nodes)),'duplicate JUnit nodes '+name)
  require(v['collection_junit_exact_match'] is True and v['unique_junit_nodes'] is True,'receipt matching flags not true '+name)
  require(not counts['FAIL'] and not counts['ERROR'],'raw JUnit failing cases '+name)
  start,end=time(v['started_utc']),time(v['finished_utc']);require(start<=end,'invalid receipt interval '+name)
  return dict(name=name,sha256=sha(p),counts=counts,nodes=nodes,modules=v['modules'],start=start,end=end,record=v)
 selected=[receipt(w['window'],w['modules']) for w in selection]
 all_nodes=[n for w in selected for n in w['nodes']];all_modules=[m for w in selected for m in w['modules']]
 require(len(all_modules)==len(set(all_modules))==140,'main module union not exact140')
 require(sorted(all_modules)==sorted(m for w in planned for m in w['modules']),'planned full module union differs')
 require(len(all_nodes)==len(set(all_nodes)),'main union contains duplicate test identifiers')
 require(all(w['counts']['SKIP']==0 for w in selected),'main raw JUnit contains skip')
 passes=sum(w['counts']['PASS'] for w in selected)
 require(gate['complete_unique_modules']==140 and gate['unique_main_nodes']==len(all_nodes) and gate['main_pass']==passes and gate['main_skip']==0,'gate aggregate differs from raw JUnit union')
 gate_windows={w['window']:w for w in gate['windows']}
 require(set(gate_windows)=={w['name'] for w in selected},'gate receipt window set differs')
 for w in selected:require(gate_windows[w['name']]['sha256']==w['sha256'] and gate_windows[w['name']]['counts']==w['counts'],'gate receipt hash/count mismatch '+w['name'])
 ci_modules=json.loads((phase/'final/ci-metadata-solo-modules.json').read_text());ci=receipt('ci-metadata-solo',ci_modules)
 require(gate['ci_separate']==ci['counts'],'separate CI counts differ from raw JUnit')
 recovery=[w for w in selected if w['name']=='recovery-solo'];require(len(recovery)==1,'one selected original strict recovery required');recovery=recovery[0]
 require(recovery['modules']==['tests/test_service_plan_recovery.py'] and recovery['counts']==dict(PASS=30,FAIL=0,ERROR=0,SKIP=0),'strict recovery original module/count changed')
 others=[w for w in selected if w['name']!='recovery-solo']
 require(all(w['end']<=ci['start'] for w in others),'CI not solo after all selected tests')
 require(recovery['start']>=ci['end'] and all(w['end']<=recovery['start'] for w in others),'strict recovery not solo after tests/CI')
 review=json.loads((phase/'frozen-review/review-result.json').read_text());require(time(review['utc'])<=recovery['start'],'strict recovery began before review execution finished')
 external=[]
 for raw_name in raw_eligible:
  p=root/raw_name
  if p.suffix!='.json':continue
  v=json.loads(p.read_text())
  if isinstance(v,dict) and {'source_sha','started_utc','finished_utc','counts','exit_code','modules'}<=set(v) and v['source_sha']==source:
   if p.resolve()!=(phase/'final/recovery-solo.json').resolve():
    require(time(v['finished_utc'])<=recovery['start'],'strict recovery overlaps another final-source test window '+raw_name)
    external.append(dict(path=raw_name,sha256=sha(p)))
 prior=json.loads((root/'.runtime/plan-replacement-root/preserved-evidence-union.json').read_text())
 for path,h in prior.items():require(sha(root/path)==h,'prior raw evidence changed '+path)
 require(gate['prior_raw_paths_unchanged']==len(prior),'gate prior raw preservation count differs')
 primary_path=root/'.runtime/plan-replacement-root/seal.json';primary=json.loads(primary_path.read_text());name=str(primary_path.relative_to(root))
 require(primary['status']=='SEALED_NO_FURTHER_PRIMARY_WRITES' and primary['source_sha']==source,'primary seal status/source mismatch')
 require(primary['all_test_processes_finished'] is True and primary['raw_producers_stopped'] is True,'primary producers not sealed stopped')
 require(primary['seal_self_hash_included'] is False,'primary seal self-hash contract changed')
 roots={'plan-replacement-'+n for n in ('root','oracle','backend','ui','review')};require(set(primary['primary_roots'])==roots,'primary seal root scope differs')
 sealed=primary['eligible_raw_sha256'];require(set(sealed)==set(raw_eligible)-{name},'primary raw seal inventory mismatch')
 for path,h in sealed.items():require(sha(root/path)==h,'primary sealed raw changed '+path)
 indexed={e['raw_path']:e['raw_sha256'] for e in index_entries};require(indexed.get(name)==sha(primary_path),'primary seal public raw pairing missing')
 for path,h in sealed.items():require(indexed.get(path)==h,'index not paired to primary sealed raw '+path)
 for path,h in primary['producer_seals'].items():require(sha(root/path)==h,'producer seal bytes changed '+path)
 require(primary['selected_complete_modules']==140 and primary['selected_unique_passes']==passes and primary['regression_status']==gate['status'],'primary seal result aggregate differs')
 return dict(primary_seal_sha256=sha(primary_path),primary_sealed_raw_count=len(sealed),prior_raw_count=len(prior),final_gate_sha256=sha(gate_path),source_sha=source,selected_complete_modules=140,selected_unique_passes=passes,selected_unique_nodes=len(all_nodes),separate_ci_counts=ci['counts'],strict_recovery_counts=recovery['counts'],final_source_window_receipts_checked=len(external)+1,strict_recovery_after_ci_and_review=True)
