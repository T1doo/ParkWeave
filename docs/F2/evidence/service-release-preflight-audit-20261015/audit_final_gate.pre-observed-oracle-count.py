"""New same-SHA coverage/oracle gate; run only after explicit archive-ready."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,subprocess,xml.etree.ElementTree as ET
from audit_archive_pairs import frozen
R=Path('/workspace/ParkWeave');O=R/'.runtime/service-release-preflight-audit';S='0de44714499ff3ead538dd8dc1436e783ab8f944'
FORM='.runtime/service-release-preflight-independent/freeze-0de4471-formal'
def read(p):return json.loads((R/p).read_text())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def key(node):
 prefix,br,tail=node.partition('[');parts=prefix.split('::')
 return parts[0][:-3].replace('/','.')+''.join('.'+x for x in parts[1:-1]),parts[-1]+(br+tail if br else '')
def state(t):return 'ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
def window(prefix,kind,expected_count):
 result=read(prefix+('.json' if kind=='root' else '-result.json'));c=read(prefix+'-collection.json');nodes=c if isinstance(c,list) else [r['nodeid'] for r in c['items']]
 xml=prefix+('-junit.xml' if kind=='ind' else '.xml');ts=list(ET.parse(R/xml).iter('testcase'));wanted=Counter(key(n) for n in nodes);actual=Counter((t.get('classname'),t.get('name')) for t in ts)
 assert wanted==actual and len(wanted)==len(nodes)==expected_count and all(v==1 for v in wanted.values()) and Counter(state(t) for t in ts)=={'PASS':expected_count}
 assert result['source_sha']==S and result['exit_code']==0
 f=read('.runtime/service-release-preflight/final-freeze.json')['hashes']
 if kind=='root':assert read(prefix+'-before.json')==read(prefix+'-after.json')==f
 elif kind=='review':
  a=read(prefix+'-source-before.json');b=read(prefix+'-source-after.json');assert a==b and len(a)==604 and {p:a[p] for p in f}==f
  fulla=read(prefix+'-alltracked-before.json');fullb=read(prefix+'-alltracked-after.json');assert fulla==fullb and fulla['count']==12078 and not fullb['frozen_git_blob_mismatches']
 else:
  a=read(prefix+'-before.json');b=read(prefix+'-after.json');assert a['head']==b['head']==S and a['files']==b['files'] and len(a['files'])==12078 and {p:a['files'][p] for p in f}==f
 return {'execution_sha':S,'modules':result['modules'],'nodes':nodes,'counts':{'PASS':expected_count,'FAIL':0,'ERROR':0,'SKIP':0},'collection_junit_exact_unique':True,'result_path':prefix+('.json' if kind=='root' else '-result.json'),'junit_seconds':result.get('junit_seconds'),'runner_seconds':result.get('elapsed_seconds'),'xml_path':xml}
def traces():
 inherited=read(FORM+'-inherited-traces.json');own=read(FORM+'-own-new-traces.json');assert inherited['historical_files_not_copied'];files=[]
 for r in inherited['records']:
  assert r['source_sha']==S and sha(r['raw_path'])==sha(r['copied_path'])==r['sha256']
  group='typed' if '/typed-source-impact-independent/' in r['raw_path'] else 'shared' if '/shared-source-cases-independent/' in r['raw_path'] else None;assert group
  files.append((group,r['copied_path']))
 for r in own['records']:
  assert sha(r['path'])==r['sha256'];files.append(('preflight',r['path']))
 assert len(files)==len({p for _,p in files});oracles=[];html=[]
 for group,p in files:
  if p.endswith('.stderr.log'):assert not (R/p).read_bytes();continue
  if not p.endswith('.jsonl'):continue
  rows=[json.loads(x) for x in (R/p).read_text().splitlines() if x.strip()]
  if Path(p).name.startswith('oracle-'):
   for row in rows:
    assert row['head']==S
    ea,aa=set(row['expected_affected']),set(row['actual_affected']);ep,ap=set(row['expected_preserved']),set(row['actual_preserved'])
    assert not ea&ep and not aa&ap and ea==aa and ep==ap and row['missed_count']==row['wrong_count']==row['wrong_preserved_count']==0
    if group=='preflight':assert row['expected_classification']==row['actual_classification'] and set(row['expected_locked'])==set(row['actual_locked']) and row['wrong_locked_count']==0
    elif group=='shared':assert row['expected_state']==row['actual_state'] and row['expected_relationship']==row['actual_relationship']
    oracles.append({'group':group,'scenario':row['scenario'],'head':S,'affected_pairs':len(ea),'preserved_pairs':len(ep),'intentional_unknown_or_expansion':row.get('intentional_unknown',row.get('intentional_unknown_expansion',False)),'unknown_scope':row.get('unknown_scope'),'state':row.get('actual_state',row.get('actual_classification'))})
  elif p.endswith('.stdout.jsonl'):
   results=[r for r in rows if 'scope' in r];assert len(results)==1 and results[0]['checks']>0;r=results[0]
   scope='FULL_ORIGINAL_HTML_'+{'preflight':'SERVICE_RELEASE_PREFLIGHT','typed':'TYPED_SOURCE','shared':'SHARED_SOURCE'}[group]+'_REAL_HTTP_ASGI_OWNED_PG';assert r['scope']==scope
   negative=r.get('negative_transport_fixture',False)
   if group=='preflight':assert negative==(r['mode'] in ('pending','unknown_dto'))
   html.append({'group':group,'path':p,'mode':r['mode'],'scope':scope,'checks':r['checks'],'negative_transport_fixture':negative})
 expected={'preflight':{'record','lost','lost_withdrawn','source','lock','breaking','pending','repeat','tampered','current_403','late_aba','late_403','target_aba','unknown_dto'},'shared':{'positive','lost','current_403','late_aba','late_403','kind_switch','overflow','pagination','pagination_stale'},'typed':{'positive','lost','late_read_aba','late_read_403','open_current_403','open_late_403'}}
 for group,modes in expected.items():assert {r['mode'] for r in html if r['group']==group}==modes and sum(r['group']==group for r in html)==len(modes)
 assert len(html)==29 and sum(r['negative_transport_fixture'] for r in html)==2
 assert Counter(r['group'] for r in oracles)=={'preflight':16,'shared':12,'typed':11}
 assert {g:sum(r['affected_pairs'] for r in oracles if r['group']==g) for g in expected}=={'preflight':67,'shared':24,'typed':38}
 return {'status':'PASS','source_sha':S,'literal_oracles':oracles,'literal_oracle_count':39,'missed':0,'wrong':0,'wrong_preserved':0,'wrong_locked_preflight':0,'html':html,'full_original_html_modes':29,'negative_transport_modes':2,'actual_service_modes_excluding_designated_negative_transport':27,'real_browser':'NOT_RUN','raw_copy_identity':True}
def main():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==S
 assert not subprocess.check_output(['git','ls-files','--others','--exclude-standard','src','tests','scripts','pyproject.toml'],cwd=R).strip()
 pairs=read('.runtime/service-release-preflight-audit/archive-independent-pairs.json');assert pairs['source_sha']==S and pairs['status']=='PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING'
 before=frozen(S);review=read('.runtime/service-release-preflight-review/review-0de44714.json');assert not review['new_blockers'] and review['source_sha']==S
 wins=[window('.runtime/service-release-preflight/root-1-v1','root',900),window('.runtime/service-release-preflight/root-2-v1','root',789),window('.runtime/service-release-preflight-review/extra-v2-0de44714','review',300),window(FORM,'ind',198)]
 nodes=[n for w in wins for n in w['nodes']];mods=[m for w in wins for m in w['modules']]
 assert len(nodes)==len(set(nodes))==2187 and len(mods)==len(set(mods))==67
 union={'source_sha':S,'modules':mods,'nodes':nodes,'unique_modules':67,'unique_nodes':2187,'node_set_sha256':hashlib.sha256('\n'.join(sorted(nodes)).encode()).hexdigest()};save('independent-coverage-union.json',union)
 coverage=read('.runtime/service-release-preflight/final-coverage.json');assert coverage['source_sha']==S and coverage['complete_modules']==67 and coverage['unique_tests']==2187 and not coverage['whole_repository_run'] and not coverage['source_drift']
 comparisons=[]
 for w in wins:
  choices=[r for r in coverage['windows'] if set(r['modules'])==set(w['modules'])];assert len(choices)==1;r=choices[0]
  assert r['source_sha']==S and Counter(r['nodeids'])==Counter(w['nodes']) and r['counts']==w['counts']
  seconds=w['junit_seconds'] if r['seconds']['kind'].lower()=='junit' else w['runner_seconds'];assert abs(seconds-r['seconds']['value'])<0.001
  comparisons.append({'window':r['name'],'items':len(w['nodes']),'counts_nodes_time_exact':True,'source_sha':S})
 save('root-coverage-independent-comparison.json',{'status':'PASS','windows':comparisons,'same_actual_execution_sha':True,'unique_nodes':2187,'unique_modules':67})
 pr=read('.runtime/service-release-preflight-review/probes-v2-0de44714-result.json');assert pr['source_sha']==S and pr['counts']=={'PASS':3,'FAIL':0,'ERROR':0,'SKIP':0} and pr['exit_code']==0 and pr['probe_unchanged'] and pr['alltracked_before_after_equal']
 for phase in ['source','alltracked']:assert read('.runtime/service-release-preflight-review/probes-v2-0de44714-'+phase+'-before.json')==read('.runtime/service-release-preflight-review/probes-v2-0de44714-'+phase+'-after.json')
 receipt=read('.runtime/service-release-preflight-review/reviewer-v1-setup-isolation-receipts.json');assert receipt['first_probe']['counts']['ERROR']==3 and receipt['first_extra_partial']['counts']['PASS']==64 and receipt['first_extra_partial']['exit_code']==2
 index=read('docs/F2/evidence/service-release-preflight-20261015/index.json');indexed={r['raw_path'] for r in index['entries']}
 required={'.runtime/service-release-preflight-review/extra-0de44714.xml','.runtime/service-release-preflight-review/probes-0de44714.xml','.runtime/service-release-preflight-review/extra-0de44714-first-setup-key-error.log','.runtime/service-release-preflight-review/probes-0de44714-first-setup-key-error.log','.runtime/service-release-preflight-review/reviewer-v1-setup-isolation-receipts.json',FORM+'-junit.xml'};assert required<=indexed
 oracle=traces();save('independent-oracle-and-html.json',oracle)
 assert before==frozen(S) and not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R).strip()
 result={'status':'PASS','source_sha':S,'utc':datetime.now(timezone.utc).isoformat(),'source599_and_alltracked12078_before_after_equal':True,'windows':[{k:v for k,v in w.items() if k!='nodes'} for w in wins],'coverage':{'complete_modules':67,'unique_tests':2187,'all_pass':True,'all_windows_execute_same_exact_sha':True,'whole_repository_run':False},'separate_runtime_negative_probes':{'pass':3,'runner_seconds':pr['elapsed_seconds'],'junit_seconds':pr['junit_seconds'],'not_in_formal_module_union':True},'oracles':{'records':39,'new_preflight16_affected_pairs':67,'old_shared12_affected_pairs':24,'old_typed11_affected_pairs':38,'missed':0,'wrong':0,'wrong_preserved':0,'wrong_locked_preflight':0,'unknown_expansion_not_precision':True},'html':{'full_original_modes':29,'new_preflight_modes':14,'old_shared_modes':9,'old_typed_modes':6,'two_negative_transport_fixtures':['pending','unknown_dto'],'actual_service_modes_excluding_designated_negative_transport':27,'Node_VM_DOM_not_actual_browser':True},'reviewer_nonproduct_receipts_retained':receipt,'new_blockers':[],'pair_rebuild':pairs['status'],'scope':['Finite synthetic samefamily/latesthead single-Case compatibility/recheck evidence only','Only separate private ConsumerRepository journal append; business PG read-only, existing authorization_audit retained','No publication/migration/rollback/Approval/ADOPT/VERIFY/execution grant','READ revocation denies historical log; PREPARE-only revocation may retain current-READ history with current_available=false','Windows, actual browser, formal AT27/F3/F5, real models, production, remoteCI NOT_RUN'],'public_report_review':'PENDING_SEPARATE_CONTENT_LINK_AND_SCOPE_CHECK'}
 save('final-gate-mechanical.json',result);print(json.dumps({'status':'PASS','source_sha':S,'coverage':result['coverage'],'oracles':result['oracles'],'html':result['html']}))
if __name__=='__main__':main()
