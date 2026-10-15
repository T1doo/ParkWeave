"""Read-only reviewer runner; invoke only after root supplies exact frozen SHA."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/service-release-preflight-review'
SHA=sys.argv[1];assert re.fullmatch('[a-f0-9]{40}',SHA)
FREEZE=ROOT/(sys.argv[2] if len(sys.argv)>2 else '.runtime/service-release-preflight/freeze.json')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
freeze=json.loads(FREEZE.read_text());assert freeze['source_sha']==SHA
freeze_hashes=freeze['hashes'];assert isinstance(freeze_hashes,dict) and len(freeze_hashes)==freeze.get('tracked_source_paths',freeze.get('source_paths'))
modules=['.runtime/service-release-preflight-review/test_readonly_boundary_probes.py'];probe_path=ROOT/modules[0];probe_hash=hashlib.sha256(probe_path.read_bytes()).hexdigest()
prefix='probes-v2-'+SHA[:8];assert not (OUT/(prefix+'-result.json')).exists(),'frozen reviewer window cannot be overwritten'
tracked=[p for p in subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml'],cwd=ROOT).decode().split('\0') if p]
eggs=[str(p.relative_to(ROOT)) for p in (ROOT/'src/parkweave.egg-info').glob('*') if p.is_file()];paths=tracked+eggs

def source_manifest():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
def all_tracked():
    result={};mismatches=[]
    for row in subprocess.check_output(['git','ls-tree','-rz','--full-tree',SHA],cwd=ROOT).split(b'\0'):
        if not row:continue
        meta,path=row.split(b'\t',1);mode,kind,oid=meta.decode().split();path=path.decode();assert kind=='blob'
        data=(ROOT/path).read_bytes();result[path]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'git_blob':oid}
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=oid:mismatches.append(path)
    return {'source_sha':SHA,'count':len(result),'bytes':sum(p['bytes'] for p in result.values()),'frozen_git_blob_mismatches':mismatches,'files':result}
def save(suffix,value):(OUT/(prefix+'-'+suffix+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
before=source_manifest();assert {p:before[p] for p in tracked}==freeze_hashes;save('source-before',before)
full_before=all_tracked();assert not full_before['frozen_git_blob_mismatches'];save('alltracked-before',full_before)
collection=OUT/(prefix+'-collection.json');args=[sys.executable,'-m','pytest','-q','-p','conftest','-p','preflight_review_capture',*modules,'--basetemp=/tmp/pw-release-preflight-probes-v2-'+SHA[:8],'--junitxml='+str(OUT/(prefix+'.xml'))]
env=os.environ.copy();env['PYTHONPATH']='.:src:tests:'+str(OUT)+os.pathsep+env.get('PYTHONPATH','');env['PREFLIGHT_REVIEW_COLLECTION']=str(collection);env['PREFLIGHT_REVIEW_PRIVATE']=str(OUT/(prefix+'-redaction-values.private.json'));env['XDG_CACHE_HOME']=str(ROOT/'.runtime/xdg-cache')
started=time.monotonic()
with (OUT/(prefix+'.log')).open('w') as log:code=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
elapsed=time.monotonic()-started;after=source_manifest();save('source-after',after);full_after=all_tracked();save('alltracked-after',full_after)
counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);nodes=[];skips=[];seconds=None
if (OUT/(prefix+'.xml')).exists():
    tree=ET.parse(OUT/(prefix+'.xml')).getroot();suite=tree.find('testsuite') if tree.tag=='testsuites' else tree;seconds=float(suite.get('time'))
    for t in tree.iter('testcase'):
        parts=t.get('classname','').split('.');matches=[(i,m) for i,v in enumerate(parts) for m in modules if Path(m).stem==v];assert len(matches)==1
        i,module=matches[0];node=module+'::'+'::'.join(parts[i+1:]+[t.get('name')]);nodes.append(node)
        state='ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS';counts[state]+=1
        if state=='SKIP':skips.append({'node':node,'reason':t.find('skipped').get('message')})
collected=json.loads(collection.read_text()) if collection.exists() else []
head_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
result={'source_sha':SHA,'head_after':head_after,'modules':modules,'argv':args,'exit_code':code,'elapsed_seconds':elapsed,'junit_seconds':seconds,'counts':counts,'collected':len(collected),'executed':len(nodes),'collection_junit_exact':sorted(collected)==sorted(nodes),'duplicates':len(nodes)-len(set(nodes)),'tracked_source_paths':len(tracked),'editable_metadata_paths':len(eggs),'source_manifest_paths':len(paths),'source_changes':[p for p in paths if before[p]!=after[p]],'alltracked_count':full_before['count'],'alltracked_bytes':full_before['bytes'],'alltracked_before_after_equal':full_before==full_after,'alltracked_blob_mismatches_after':full_after['frozen_git_blob_mismatches'],'skips':skips,'probe_sha256':probe_hash,'probe_unchanged':probe_hash==hashlib.sha256(probe_path.read_bytes()).hexdigest(),'separate_from_formal67_modules':True,'scope':'Linux synthetic actual original HTTP/ASGI/owned PG and read-only validator seams; not current admission/compiler compatibility proof, real browser, Windows, formal AT, model, production or CI'}
save('result',result);print(json.dumps(result,ensure_ascii=False));sys.exit(code or int(head_after!=SHA or bool(result['source_changes']) or not result['collection_junit_exact'] or result['duplicates'] or not result['probe_unchanged'] or full_before!=full_after))
