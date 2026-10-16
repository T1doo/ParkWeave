from pathlib import Path
import json,hashlib,subprocess,sys,os,datetime,ast,importlib,xml.etree.ElementTree as ET
ROOT=Path.cwd();OUT=ROOT/'.runtime/frontier-review-v2/frozen-v1';os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(ROOT/'src'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
fp=ROOT/'.runtime/frontier-root/v2/freeze.json';freeze=json.loads(fp.read_text());expected='a5c6cd5c8bc609f31ec9c1895e0fd51adea995c2';assert freeze['source_sha']==expected
modules=['business_frontier','business_frontier_types','plan_replacement_compatibility','service_dispatches','executor_receipts','case_lifecycle','case_cancellation','case_cancellation_before_receipt','case_cancellation_reconciliation','lifecycle_execution_preview','service_plan_approval','case_resource_delivery']
def snap():
 result={key:{p:sha(ROOT/p) for p in freeze[key]} for key in ('source_paths','all_tracked_sha256','runner_paths')}
 result['head']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();result['git_status']=subprocess.check_output(['git','status','--porcelain'],text=True)
 result['actual_imports']={}
 for name in modules:
  m=importlib.import_module('parkweave.'+name);p=Path(m.__file__).resolve();assert p==ROOT/'src/parkweave'/(name+'.py');result['actual_imports'][name]=dict(path=str(p),sha256=sha(p))
 return result
before=snap();(OUT/'before.json').write_text(json.dumps(before,indent=2)+'\n');assert before['head']==expected and not before['git_status'];assert all(before[k]==freeze[k] for k in ('source_paths','all_tracked_sha256','runner_paths'))
checks=[]
for manifest in (ROOT/'.runtime/frontier-backend/source-v2/manifest.json',ROOT/'.runtime/frontier-repair-ui/source-v2/manifest.json'):
 obj=json.loads(manifest.read_text());rows=[]
 for f in obj['files']:
  actual=sha(ROOT/f['path']);assert actual==f['sha256'];rows.append(dict(path=f['path'],sha256=actual))
 checks.append(dict(manifest=str(manifest.relative_to(ROOT)),sha256=sha(manifest),files=rows))
browser='tests/test_lifecycle_execution_preview_browser.py';old=subprocess.check_output(['git','show','c2263edd:'+browser],text=True);new=(ROOT/browser).read_text()
def test_functions(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
assert test_functions(old)==test_functions(new);assert "page.unroute_all(behavior='wait');context.unroute_all(behavior='wait')" in new;assert 'assert not errors,errors' in new

repair_files=['tests/test_dispatch_execution_preview_browser.py','tests/test_receipt_execution_preview_browser.py','tests/test_isolated_execution_preview_browser.py','tests/test_receipt_history_recovery_browser.py']
repair_checks=[]
for path in repair_files:
 old_source=subprocess.check_output(['git','show','b1b3824:'+path],text=True);new_source=(ROOT/path).read_text()
 def assertions(text):
  tree=ast.parse(text);return {n.name:[ast.dump(x,include_attributes=False) for x in ast.walk(n) if isinstance(x,ast.Assert)] for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
 assert assertions(old_source)==assertions(new_source)
 def waits(text):return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('wait_for_timeout','wait_for_function') and n.lineno<180]
 # Existing tests' exact asserts above plus unchanged literal timeout budgets.
 import re
 assert re.findall(r'timeout\s*=\s*\d+|wait_for_timeout\(\d+',old_source)==re.findall(r'timeout\s*=\s*\d+|wait_for_timeout\(\d+',new_source)
 repair_checks.append(dict(path=path,original_test_assertions_ast_equal=True,literal_timeout_budgets_equal=True))
(OUT/'repair-static-checks.json').write_text(json.dumps(dict(files=repair_checks,guard='UNKNOWN bounded planning read stays denied; helper checks same flow/storage, no network requests and exact original rejection; current403 still clears private views then reports refusal; late identity current() guard unchanged',not_run='root complete browser/PG modules not repeated'),indent=2)+'\n')
(OUT/'static-checks.json').write_text(json.dumps(dict(manifest_checks=checks,browser_test_functions_ast_equal=True,route_wait_cleanup_only=True,blocking_findings=[],scope='static read of all14 unchanged backend product and five-file repair-v2; prior cancellation/fingerprint/preview fixes; tracked P4 UPDATE-first; birth/catalog/19trigger/native-anchor; original full5 branch retained'),indent=2)+'\n')
clients=['tests/test_frontier_client.py','tests/test_frontier_business_client.py','tests/test_frontier_cancel_client.py','tests/test_frontier_qualification_client.py','tests/test_frontier_cancel_nullguard.py','tests/test_plan_replacement_client.py','tests/test_plan_reapproval_client.py','tests/test_pending_receipt_handoff_offline.py']
selections={'pure':['tests/test_frontier_review_pure.py'],'client':clients,'repair_client':['tests/test_dispatch_notice_page_offline.py']};results={};env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
for name,selected in selections.items():
 collection=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','--collect-only','-q',*selected]
 c=subprocess.run(collection,env=env,capture_output=True,text=True);(OUT/(name+'-collection.log')).write_text(c.stdout+c.stderr);assert c.returncode==0
 argv=[sys.executable,'-B','-m','pytest','-p','no:cacheprovider','-q','--junitxml='+str(OUT/(name+'.xml')),*selected]
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (OUT/(name+'.log')).open('wb') as log:r=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT)
 end=datetime.datetime.now(datetime.timezone.utc).isoformat();cases=list(ET.parse(OUT/(name+'.xml')).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
 for case in cases:
  tags={x.tag for x in case};counts['ERROR' if 'error' in tags else 'FAIL' if 'failure' in tags else 'SKIP' if 'skipped' in tags else 'PASS']+=1
 results[name]=dict(argv=argv,collection_argv=collection,started_utc=start,finished_utc=end,exit_code=r.returncode,counts=counts,log_sha256=sha(OUT/(name+'.log')),junit_sha256=sha(OUT/(name+'.xml')),modules=selected)
 (OUT/(name+'-result.json')).write_text(json.dumps(results[name],indent=2)+'\n')
after=snap();(OUT/'after.json').write_text(json.dumps(after,indent=2)+'\n');drift={k:[p for p,h in before[k].items() if after[k].get(p)!=h] for k in ('source_paths','all_tracked_sha256','runner_paths')};blocking=[]
if any(drift.values()) or before['head']!=after['head'] or after['git_status'] or before['actual_imports']!=after['actual_imports']:blocking.append('frozen files/head/imports drift')
if any(v['exit_code'] or v['counts']['FAIL'] or v['counts']['ERROR'] or v['counts']['SKIP'] for v in results.values()):blocking.append('pure/client execution not clean PASS')
result=dict(status='LIMITED_PASS' if not blocking else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_sha=expected,freeze_manifest_sha256=sha(fp),blocking_findings=blocking,before_matches_freeze=all(before[k]==freeze[k] for k in drift),zero_drift=not any(drift.values()),drift=drift,actual_imports_before=before['actual_imports'],actual_imports_after=after['actual_imports'],pure_exit_code=results['pure']['exit_code'],client_exit_code=results['client']['exit_code'],tests=results,counts={k:v['counts'] for k,v in results.items()},scope='independent static review plus pure protocol and controlled JS client probes; overlaps parent main modules, never additive to regression union',not_run=['PG/native trigger SQL and concurrency in this review','actual HTTP/browser in this review; full four affected browser modules delegated to root complete170 regression','original special PG27 role profile','Windows/browser/formal AT/real model/production','general enrollment migration/backfill/restart','unregistered owner invisible DDL or superuser catalog fabrication','tracked schema33 after-accept cancellation remains original refusal'])
(OUT/'review-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('actual_imports_before','actual_imports_after','tests','drift')}));assert not blocking
