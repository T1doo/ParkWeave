"""Explicitly invoked independent pure source review. Never runs HTTP/PG tests."""
from pathlib import Path
import ast,hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OWN=Path(__file__).resolve().parent;BASELINE='e0ffc81f2d29dbfd498c1a9a93206e689bd0b310'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def cmd(*a):return subprocess.check_output(a,cwd=ROOT,text=True).strip()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def snapshot(f):
    assert cmd('git','rev-parse','HEAD')==f['source_sha']
    src={p:sha((ROOT/p).read_bytes()) for p in f['source_paths']}
    tracked={p:sha((ROOT/p).read_bytes()) for p in f['all_tracked_sha256']}
    helpers={p:sha((ROOT/p).read_bytes()) for p in f['runner_paths']}
    assert src==f['source_paths'] and tracked==f['all_tracked_sha256'] and helpers==f['runner_paths']
    assert not cmd('git','status','--porcelain')
    return dict(source_sha=f['source_sha'],source_sha256=src,all_tracked_sha256=tracked,runner_sha256=helpers,git_status='CLEAN')
def funcs(data):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(data).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
def static():
    files=['typed_source_impact.py','registered_dependencies.py','employees_fact_provenance.py','controlled_plans.py','plan_source_conflicts.py','case_opportunities.py','case_fact_clarifications.py']
    rows=[]
    for name in files:
        p='src/parkweave/'+name;old=subprocess.check_output(['git','show',BASELINE+':'+p],cwd=ROOT);new=(ROOT/p).read_bytes();assert old==new,p
        rows.append(dict(path=p,sha256=sha(new),baseline_bytes_unchanged=True))
    retained={'service_case_steps.py':['_adopt_request','dependency_impact','current_sources','_recovery_proofs','_context','_manual_lock'], 'source_change_adoption.py':['source_impact','evidence_sources','epochs','current_card','unavailable_sources']}
    kept=[]
    for name,names in retained.items():
        p='src/parkweave/'+name;old=funcs(subprocess.check_output(['git','show',BASELINE+':'+p],cwd=ROOT,text=True));new=funcs((ROOT/p).read_text())
        for name in names:assert old[name]==new[name],name;kept.append(dict(path=p,function=name,ast_unchanged=True))
    return dict(whole_modules=rows,original_critical_functions=kept)
def identity(case):
    parts=case.get('classname','').split('.');i=next(i for i,v in enumerate(parts) if v.startswith('test_'))
    return 'tests/'+parts[i]+'.py::'+'::'.join(parts[i+1:]+[case.get('name')])
def main():
    f=read('.runtime/unified-propagation-root/freeze.json');out=OWN/('frozen-'+f['source_sha'][:12]);out.mkdir(exist_ok=False)
    before=snapshot(f);save(out/'before.json',before);save(out/'static-review.json',static())
    modules=['tests/test_unified_dependency_propagation.py','tests/test_unified_dependency_propagation_literal.py','tests/test_unified_dependency_client_probes.py']
    env=dict(os.environ,UNIFIED_REVIEW_COLLECTION=str(out/'collection.json'));env['PYTHONPATH']=str(OWN)+os.pathsep+env.get('PYTHONPATH','')
    args=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-p','review_capture',*modules,'--junitxml='+str(out/'junit.xml'),'--basetemp='+str(out/'tmp')]
    with (out/'pytest.log').open('w') as log:code=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    after=snapshot(f);save(out/'after.json',after);assert before==after
    collected=read(str((out/'collection.json').relative_to(ROOT)));cases=list(ET.parse(out/'junit.xml').iter('testcase'));nodes=[identity(c) for c in cases]
    assert sorted(collected)==sorted(nodes) and len(nodes)==len(set(nodes))
    counts={s:sum((('ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS')==s) for c in cases) for s in ('PASS','FAIL','SKIP','ERROR')}
    result=dict(status='PASS' if code==0 and counts['PASS']==len(nodes) else 'FAIL',source_sha=f['source_sha'],modules=modules,counts=counts,collection_junit_exact=True,unique_nodes=True,before_after_stable=True,capture_plugin_sha256=sha((OWN/'review_capture.py').read_bytes()),product_logic_patched=False,source_paths=len(f['source_paths']),tracked_paths=len(f['all_tracked_sha256']),runner_paths=len(f['runner_paths']),boundaries=['Pure/controlled client checker only; no PostgreSQL, HTTP or real browser','Full relevant regression and archive gate require independent separate actual receipts'])
    save(out/'review.json',result);print(json.dumps(result));assert result['status']=='PASS'
if __name__=='__main__':main()
