"""Independent final gate. Run only after explicit archive-ready and pair audit."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,subprocess,xml.etree.ElementTree as ET
from audit_archive_pairs import frozen
R=Path('/workspace/ParkWeave');O=R/'.runtime/shared-source-cases-audit'
OLD='bc4f384fa32817ddf3b332f898d59b5b994bfe2f';FINAL='731529bc409041f255742e11756ebc4084bb9319'
FORM='.runtime/shared-source-cases-independent/freeze-731529b-formal'
def read(p):return json.loads((R/p).read_text())
def h(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def save(name,v):(O/name).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def identity(n):
 prefix,bracket,tail=n.partition('[');parts=prefix.split('::')
 return (parts[0][:-3].replace('/','.')+''.join('.'+x for x in parts[1:-1]),parts[-1]+(bracket+tail if bracket else ''))
def state(t):return 'ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
def full_window(prefix,sha,kind):
 result=read(prefix+('-result.json' if kind!='root' else '.json'))
 c=read(prefix+'-collection.json');nodes=c if isinstance(c,list) else [r['nodeid'] for r in c['items']]
 xml=prefix+('-junit.xml' if kind=='ind' else '.xml');ts=list(ET.parse(R/xml).iter('testcase'))
 expected=Counter(identity(n) for n in nodes);actual=Counter((t.get('classname'),t.get('name')) for t in ts)
 assert expected==actual and all(n==1 for n in expected.values())
 counts=dict(Counter(state(t) for t in ts));assert counts=={'PASS':len(nodes)} and result['exit_code']==0 and result['source_sha']==sha
 old=read('.runtime/shared-source-cases/freeze.json')['hashes'];final=read('.runtime/shared-source-cases/final-freeze.json')['hashes']
 if kind=='root':assert read(prefix+'-before.json')==read(prefix+'-after.json')==old
 elif kind=='review':
  a=read(prefix+'-source-before.json');b=read(prefix+'-source-after.json');assert a==b and len(a)==600 and {p:a[p] for p in old}==old
 else:
  a=read(prefix+'-before.json');b=read(prefix+'-after.json');assert a['head']==b['head']==sha and a['files']==b['files']
  assert {p:a['files'][p] for p in final}==final and len(a['files'])==11771
 return {'execution_sha':sha,'modules':result['modules'],'nodes':nodes,'counts':counts,'xml':xml,'collection_junit_exact_unique':True,'result_path':prefix+('-result.json' if kind!='root' else '.json'),'junit_seconds':result.get('junit_seconds'),'runner_seconds':result.get('elapsed_seconds')}
def traces():
 inherited=read(FORM+'-inherited-typed-traces.json');own=read(FORM+'-own-new-traces.json');assert inherited['historical_files_not_copied']
 out=[]
 for row in inherited['records']:
  assert row['source_sha']==FINAL and h(row['raw_path'])==h(row['copied_path'])==row['sha256'];out.append(('typed',row['copied_path']))
 for row in own['records']:
  assert h(row['path'])==row['sha256'];out.append(('shared',row['path']))
 assert len(out)==len({p for _,p in out})
 oracle_rows=[];html=[]
 for group,path in out:
  if path.endswith('.stderr.log'):assert not (R/path).read_bytes();continue
  if not path.endswith('.jsonl'):continue
  rows=[json.loads(x) for x in (R/path).read_text().splitlines() if x.strip()]
  if Path(path).name.startswith('oracle-'):
   for row in rows:
    assert row['head']==FINAL
    ea,aa=set(row['expected_affected']),set(row['actual_affected']);ep,ap=set(row['expected_preserved']),set(row['actual_preserved'])
    assert not ea&ep and not aa&ap
    assert len(ea-aa)==row['missed_count']==0 and len(aa-ea)==row['wrong_count']==0 and len(ep^ap)==row['wrong_preserved_count']==0
    if group=='shared':assert row['actual_state']==row['expected_state'] and row['actual_relationship']==row['expected_relationship']
    oracle_rows.append({'group':group,'scenario':row['scenario'],'expected_affected':len(ea),'expected_preserved':len(ep),'unknown':row.get('intentional_unknown',row.get('intentional_unknown_expansion',False)),'head':FINAL})
  elif path.endswith('.stdout.jsonl'):
   result=[r for r in rows if 'scope' in r];assert len(result)==1 and result[0]['checks']>0
   r=result[0];expected_scope='FULL_ORIGINAL_HTML_'+('TYPED_SOURCE' if group=='typed' else 'SHARED_SOURCE')+'_REAL_HTTP_ASGI_OWNED_PG'
   assert r['scope']==expected_scope
   html.append({'group':group,'path':path,'mode':r['mode'],'scope':r['scope'],'checks':r['checks']})
 expected_shared={'positive','lost','current_403','late_aba','late_403','kind_switch','overflow','pagination','pagination_stale'}
 expected_typed={'positive','lost','late_read_aba','late_read_403','open_current_403','open_late_403'}
 assert {r['mode'] for r in html if r['group']=='shared'}==expected_shared and {r['mode'] for r in html if r['group']=='typed'}==expected_typed and len(html)==15
 assert Counter(r['group'] for r in oracle_rows)=={'shared':12,'typed':11}
 return {'literal_oracles':oracle_rows,'literal_oracle_count':len(oracle_rows),'missed':0,'wrong':0,'wrong_preserved':0,'html':html,'actual_html_mode_count':len(html),'trace_raw_copy_identity':True}
def main():
 pairs=read('.runtime/shared-source-cases-audit/archive-independent-pairs.json');assert pairs['source_sha']==FINAL and pairs['status']=='PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING'
 source_before=frozen(FINAL);source=read('.runtime/shared-source-cases-review/final-source-review-731529bc.json');assert not source['new_blockers'] and source['final_source_sha']==FINAL
 wins=[full_window('.runtime/shared-source-cases/root-1-v1',OLD,'root'),full_window('.runtime/shared-source-cases/root-2-v1',OLD,'root'),full_window('.runtime/shared-source-cases-review/extra-bc4f384f',OLD,'review'),full_window(FORM,FINAL,'ind')]
 modules=[p for w in wins for p in w['modules']];nodes=[p for w in wins for p in w['nodes']]
 assert len(modules)==len(set(modules))==64 and len(nodes)==len(set(nodes))==2074
 union={'modules':modules,'nodes':nodes,'unique_modules':64,'unique_nodes':2074,'node_set_sha256':hashlib.sha256('\n'.join(sorted(nodes)).encode()).hexdigest()};save('independent-coverage-union.json',union)
 schema=read('.runtime/shared-source-cases-review/schema-bc4f384f-result.json');assert schema['source_sha']==OLD and schema['counts']=={'PASS':3,'FAIL':0,'ERROR':0,'SKIP':0}
 oldformal=read('.runtime/shared-source-cases-independent/freeze-bc4f384-formal-result.json');assert oldformal['source_sha']==OLD and oldformal['junit_tests']==123 and oldformal['failures']==1 and oldformal['errors']==oldformal['skipped']==0
 archival=read('docs/F2/evidence/shared-source-cases-20261015/index.json');indexed={r['raw_path'] for r in archival['entries']}
 required={'.runtime/shared-source-cases-independent/freeze-bc4f384-formal-junit.xml','.runtime/shared-source-cases-review/admin-observation.xml','.runtime/shared-source-cases-review/final-source-review-731529bc-first-setup-error.log',FORM+'-junit.xml'}
 assert required<=indexed,'historical or final evidence missing'
 oracle=traces();save('independent-oracle-and-html.json',oracle)
 admin=read('.runtime/shared-source-cases-review/admin-corruption-boundary-assessment.json');assert admin['http_status']==500 and not admin['items_or_plan_contents_exposed'] and admin['business_snapshot_unchanged'] and admin['not_a_product_positive_validation']
 assert source_before==frozen(FINAL)
 windows=[{k:v for k,v in w.items() if k!='nodes'} for w in wins]
 result={'status':'PASS','source_sha':FINAL,'utc':datetime.now(timezone.utc).isoformat(),'source595_unchanged_during_gate':True,'alltracked_paths':len(source_before),'source_transition_review':'.runtime/shared-source-cases-review/final-source-review-731529bc.json','windows':windows,'coverage':{'complete_modules':64,'unique_tests':2074,'all_pass':True,'counts_are_union_across_two_execution_shas_not_one_run':True,'execution_sha_counts':{OLD:1951,FINAL:123}},'runtime_schema_negative_probes':{'execution_sha':OLD,'pass':3,'separate':True},'historical_failed_formal_window':{'execution_sha':OLD,'pass':122,'fail':1,'retained':True,'cause':'Original HTML test harness assumed anchor on first worklist page; final JS uses bounded original next-page navigation.'},'admin_corruption_observation':{'http500':True,'positive_product_validation':False,'scope':'Trusted direct DB structural damage outside supported commands; malformed-plan UNKNOWN claims limited to handled bad headers/conflicts.'},'oracle_count':oracle['literal_oracle_count'],'oracle_missed_wrong_wrong_preserved':[0,0,0],'actual_html_modes':oracle['actual_html_mode_count'],'pair_rebuild':pairs['status'],'root_coverage_path':'.runtime/shared-source-cases/final-coverage.json','root_coverage_not_trusted_without_separate_manual_comparison':True,'new_blockers':[],'limitations':['Linux synthetic HTTP/ASGI/owned PostgreSQL scope','Two finite source identities and current owner authority; bounded UNKNOWN, no arbitrary graph','Windows, actual browser, formal AT, real models, production and remote CI NOT_RUN'],'raw_and_exports_not_modified':True}
 save('final-gate-mechanical.json',result);print(json.dumps({'status':result['status'],'source_sha':FINAL,'coverage':result['coverage'],'oracle_count':result['oracle_count'],'actual_html_modes':result['actual_html_modes']}))
if __name__=='__main__':main()
