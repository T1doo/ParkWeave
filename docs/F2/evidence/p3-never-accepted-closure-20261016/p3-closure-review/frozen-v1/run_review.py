from pathlib import Path
import sys,os,json,hashlib,subprocess,datetime,ast,importlib,xml.etree.ElementTree as ET
R=Path.cwd();O=R/'.runtime/p3-closure-review/frozen-v1';F=R/'.runtime/p3-closure-root/v1/freeze.json';freeze=json.loads(F.read_text());SOURCE='c91bbea1e996c6608665bb76dd65218f2ba542c2';assert freeze['source_sha']==SOURCE
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(R/'src'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names=['p3_never_accepted_closure','business_frontier','business_frontier_types','plan_replacement_compatibility','case_resource_delivery','service_plan_approval','service_dispatches','executor_receipts','case_lifecycle','case_cancellation','case_cancellation_before_receipt','case_cancellation_reconciliation']
def snapshot():
 v={k:{p:sha(R/p) for p in freeze[k]} for k in ('source_paths','all_tracked_sha256','runner_paths')};v['head']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();v['status']=subprocess.check_output(['git','status','--porcelain'],text=True);v['imports']={}
 for name in names:
  m=importlib.import_module('parkweave.'+name);p=Path(m.__file__).resolve();assert p==R/'src/parkweave'/(name+'.py');v['imports'][name]=dict(path=str(p),sha256=sha(p))
 return v
before=snapshot();(O/'before.json').write_text(json.dumps(before,indent=2)+'\n');assert before['head']==SOURCE and not before['status'] and all(before[k]==freeze[k] for k in ('source_paths','all_tracked_sha256','runner_paths'))
expected={};manifests=[]
for name in ('p3-closure-backend/source-v2','p3-closure-backend/source-v3','p3-closure-ui/source-v1'):
 p=R/'.runtime'/name/'manifest.json';m=json.loads(p.read_text());manifests.append(dict(path=str(p.relative_to(R)),sha256=sha(p)))
 for item in m['files']:
  if item['path'].startswith('src/'):expected[item['path']]=item['sha256']
for name,h in expected.items():assert sha(R/name)==h,name
old=ast.parse(subprocess.check_output(['git','show','c6f0771:src/parkweave/business_frontier.py'],text=True));new=ast.parse((R/'src/parkweave/business_frontier.py').read_text())
def method(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
old_install=next(n for n in method(old,'__init__').body if isinstance(n,ast.With)).body
assert ast.dump(ast.Module(body=old_install,type_ignores=[]),include_attributes=False)==ast.dump(ast.Module(body=method(new,'_install').body,type_ignores=[]),include_attributes=False)
(O/'static-checks.json').write_text(json.dumps(dict(manifests=manifests,product_paths=expected,base_install_body_ast_identical=True,canonical_uuid_before_membership=True,review_scope=['dedicated positive-epoch closure profile/schema3, original zero and full-five branches retain independent gates','native full snapshots and independent closed/noACCEPT/terminal/currentpointer/SQLxmin DML trace then actual link/receipt deferred binding','historical immutable anchor replay and current marker prefix; current outputs never rewrite old closure proof','all P3-P5 and cancellation original plan/epoch fences and parent UPDATE serialization retained','original auth/sourcelease/currenttarget/resourcecapacity/approval transaction remains; no grants or production migration','new strict UUID only validator; normal None compatibility retained; outer ledger catches invalid saved proof to Conflict'],blocking_findings=[]),indent=2)+'\n')
prior_clients=json.loads((R/'.runtime/frontier-review-v3/frozen-v1/review-result.json').read_text())['tests']['client']['modules']
selections={'pure':['tests/test_p3_closure_review_pure.py'],'client':['tests/test_p3_closure_client.py',*prior_clients],'notice':['tests/test_dispatch_notice_page_offline.py']};results={};env=dict(os.environ,PYTHONPATH=str(R/'src'),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
for name,mods in selections.items():
 collect=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','--collect-only','-q',*mods];c=subprocess.run(collect,env=env,capture_output=True,text=True);(O/(name+'-collection.log')).write_text(c.stdout+c.stderr);assert c.returncode==0
 argv=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','-q','--junitxml='+str(O/(name+'.xml')),*mods];start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (O/(name+'.log')).open('wb') as log:p=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT)
 end=datetime.datetime.now(datetime.timezone.utc).isoformat();cases=list(ET.parse(O/(name+'.xml')).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);actual=[]
 for case in cases:
  tags={c.tag for c in case};counts['ERROR' if 'error' in tags else 'FAIL' if 'failure' in tags else 'SKIP' if 'skipped' in tags else 'PASS']+=1;t=case.attrib['classname'].split('.');i=next(i for i,x in enumerate(t) if x.startswith('test_'));actual.append('tests/'+t[i]+'.py::'+'::'.join(t[i+1:]+[case.attrib['name']]))
 nodes=[s.strip() for s in c.stdout.splitlines() if s.startswith('tests/') and '::' in s];exact=sorted(nodes)==sorted(actual) and len(actual)==len(set(actual));results[name]=dict(argv=argv,collection_argv=collect,exit_code=p.returncode,counts=counts,collected_nodes=nodes,collection_junit_exact_match=exact,started_utc=start,finished_utc=end,modules=mods,log_sha256=sha(O/(name+'.log')),junit_sha256=sha(O/(name+'.xml')));(O/(name+'-result.json')).write_text(json.dumps(results[name],indent=2)+'\n')
after=snapshot();(O/'after.json').write_text(json.dumps(after,indent=2)+'\n');drift={k:[p for p,h in before[k].items() if after[k].get(p)!=h] for k in ('source_paths','all_tracked_sha256','runner_paths')};blocking=[]
if any(drift.values()) or before['imports']!=after['imports'] or before['head']!=after['head'] or after['status']:blocking.append('freeze/import/head drift')
if any(x['exit_code'] or x['counts']['FAIL'] or x['counts']['ERROR'] or x['counts']['SKIP'] or not x['collection_junit_exact_match'] for x in results.values()):blocking.append('pure/client execution failed or collection differs')
v=dict(status='LIMITED_PASS' if not blocking else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_sha=SOURCE,freeze_manifest_sha256=sha(F),blocking_findings=blocking,before_matches_freeze=True,zero_drift=not any(drift.values()),drift=drift,manifest_counts={k:len(before[k]) for k in drift},actual_imports_before=before['imports'],actual_imports_after=after['imports'],pure_exit_code=results['pure']['exit_code'],client_exit_code=results['client']['exit_code'],tests=results,counts={k:x['counts'] for k,x in results.items()},scope='independent static proof review + actual source pure strict qualification and controlled JS clients; parent main modules overlap, never additive to regression union',not_run=['PG/native SQL/concurrency in this independent review','actual network HTTP/browser in this review','original special PG27 role gate','native Windows/browser/formalAT/realmodel/production','general old-prep backfill/migration/restart/backup restore','arbitrary superuser or unregistered invisible owner DDL protection','tracked schema33 after-accept cancellation remains original gate refusal'])
(O/'review-result.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps({k:x for k,x in v.items() if k not in ('tests','actual_imports_before','actual_imports_after','drift')}));assert not blocking
