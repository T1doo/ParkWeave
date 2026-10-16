"""Explicitly invoked pure frozen review; no DB/HTTP/browser suites."""
from pathlib import Path
import ast,hashlib,json,os,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OWN=Path(__file__).resolve().parent;BASE='a794a1802e15100d691a969f0813aa371d707c36'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def command(*a):return subprocess.check_output(a,cwd=ROOT)
def snapshot(f):
    assert command('git','rev-parse','HEAD').decode().strip()==f['source_sha']
    values={key:{p:sha((ROOT/p).read_bytes()) for p in f[key]} for key in ('source_paths','all_tracked_sha256','runner_paths')}
    assert all(values[k]==f[k] for k in values) and not command('git','status','--porcelain')
    return dict(source_sha=f['source_sha'],git_status='CLEAN',**values)
def funcs(raw):
    tree=ast.parse(raw);out={}
    for n in tree.body:
        if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
        elif isinstance(n,ast.ClassDef):
            for m in n.body:
                if isinstance(m,ast.FunctionDef):out[n.name+'.'+m.name]=ast.dump(m,include_attributes=False)
    return out

def static():
    unchanged=['controlled_plans','registered_dependencies','source_change_adoption','unified_dependency_propagation','case_fact_clarifications','resource_combinations','resource_holds','catalog_publication','service_case_steps','permissions']
    rows=[]
    for name in unchanged:
        p='src/parkweave/'+name+'.py';old=command('git','show',BASE+':'+p);now=(ROOT/p).read_bytes();assert old==now,p;rows.append(dict(path=p,baseline_bytes_unchanged=True,sha256=sha(now)))
    methods={'service_plan_approval':['body','_fingerprint',*['IsolatedPlanApproval.'+n for n in ('_issued','_owner_proof','_schema','_connection','attach_store','_scope','_authority','_append','_replay','_key','_guard','recheck','consume')]],'case_resource_delivery':['_definition','_context','recover'],'case_resources':['_parent','_history','_resource_locks','_reason','_view','bind']}
    kept=[]
    for name,names in methods.items():
        p='src/parkweave/'+name+'.py';old=funcs(command('git','show',BASE+':'+p));now=funcs((ROOT/p).read_bytes())
        for n in names:assert old[n]==now[n],(p,n);kept.append(dict(path=p,function=n,ast_unchanged=True))
    p='src/parkweave/service_plan_approval.py';old_tree=ast.parse(command('git','show',BASE+':'+p));new_tree=ast.parse((ROOT/p).read_bytes())
    def constants(tree):return {n.targets[0].id:ast.dump(n.value,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
    old_constants=constants(old_tree);new_constants=constants(new_tree)
    names=('SCOPE','PURPOSE','LIMIT','OBJECT_LIMIT','COL','TRIGGER_BODY');assert all(old_constants[n]==new_constants[n] for n in names)
    return dict(original_whole_modules=rows,original_critical_functions=kept,original_schema_and_scope_constants_unchanged=list(names))

def identity(c):
    v=c.get('classname','').split('.');i=next(i for i,n in enumerate(v) if n.startswith('test_'));return 'tests/'+v[i]+'.py::'+'::'.join(v[i+1:]+[c.get('name')])
def main():
    f=read(ROOT/'.runtime/plan-reapproval-root/freeze.json');out=OWN/('frozen-'+f['source_sha'][:12]);out.mkdir(exist_ok=False)
    before=snapshot(f);save(out/'before.json',before);save(out/'static-review.json',static())
    env=dict(os.environ,PLAN_REAPPROVAL_REVIEW_COLLECTION=str(out/'collection.json'));env['PYTHONPATH']=str(OWN)+os.pathsep+str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    args=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-p','review_capture','tests/test_plan_reapproval_client.py','--junitxml='+str(out/'junit.xml'),'--basetemp='+str(out/'tmp')]
    with (out/'pytest.log').open('w') as log:code=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    with (out/'protocol-probes.json').open('w') as stdout,(out/'protocol-probes.stderr.log').open('w') as stderr:
        pure_code=subprocess.run([str(ROOT/'.venv/bin/python'),str(OWN/'protocol_invariant_probes.py')],cwd=ROOT,env=env,stdout=stdout,stderr=stderr).returncode
    after=snapshot(f);save(out/'after.json',after);assert before==after
    collected=read(out/'collection.json');cases=list(ET.parse(out/'junit.xml').iter('testcase'));nodes=[identity(c) for c in cases];assert sorted(nodes)==sorted(collected) and len(nodes)==len(set(nodes))
    counts={s:sum(('ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS')==s for c in cases) for s in ('PASS','FAIL','ERROR','SKIP')}
    probes=read(out/'protocol-probes.json') if pure_code==0 else None
    result=dict(status='PASS' if code==pure_code==0 and counts['PASS']==len(nodes) and all(r['status']=='PASS' for r in probes['results']) else 'FAIL',source_sha=f['source_sha'],pytest_counts=counts,pure_protocol_probes=len(probes['results']) if probes else 0,pytest_collection_junit_exact=True,before_after_stable=True,product_logic_patched=False,source_paths=len(f['source_paths']),all_tracked_paths=len(f['all_tracked_sha256']),helpers=len(f['runner_paths']),boundaries=['Only original client functions and pure ledger/receipt validators; no DB/HTTP/browser tests by this reviewer','Independent pure probe scenarios are not new main pytest items or actual business closure count'])
    save(out/'review.json',result);print(json.dumps(result));assert result['status']=='PASS'
if __name__=='__main__':main()
