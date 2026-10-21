"""Actual global/four-piece collection on frozen source; no tests executed."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

root=Path('/workspace/ParkWeave');out=Path(__file__).parent
p=root/'docs/F2/evidence/eng057-job-shards.json';m=json.loads(p.read_text())
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert head=='de7c0add2011b8356e0a2aa4c9ab7b7323965644'
old={k:deepcopy(m[k]) for k in ['source_parent_head','collected_cases','collected_files','collection_evidence','shards']}
new='tests/test_ordinary_demo_startup_diagnostics.py'
assert new not in {f for s in m['shards'] for f in s['files']}
m['shards'][0]['files'].append(new)
m['source_file_sha256'][new]='PENDING'
index=json.loads((root/'scripts/windows_ci/diagnostic-test-ids.json').read_text())
for path in (root/'scripts/windows_ci/diagnostic-catalog-v2'/index['generation']).glob('*.jsonl'):
    m['implementation_source_sha256'][path.relative_to(root).as_posix()]='PENDING'
files={f for s in m['shards'] for f in s['files']}
assert files=={p.relative_to(root).as_posix() for p in (root/'tests').glob('test_*.py')}
sources=set(m['source_file_sha256'])|set(m['implementation_source_sha256'])
before={f:sha256((root/f).read_bytes()).hexdigest() for f in sources}
assert all(sha256(subprocess.check_output(['git','show',head+':'+f],cwd=root)).hexdigest()==h for f,h in before.items())
rows=[]
for name,selected in [('global',sorted(files))]+[(s['id'],s['files']) for s in m['shards']]:
    dest=out/(name+'-collection.json')
    argv=[sys.executable,'-m','pytest','--collect-only','-q','-p','scripts.windows_ci.regression_shards','--parkweave-shard-collection',str(dest),*selected]
    with (out/(name+'-collection.log')).open('wb') as stream:
        code=subprocess.run(argv,cwd=root,stdout=stream,stderr=subprocess.STDOUT,timeout=60).returncode
    assert code==0,(name,code)
    value=json.loads(dest.read_text());assert value['schema']==2
    rows.append((name,value,dest));print(name,len(value['nodeids']),flush=True)
assert before=={f:sha256((root/f).read_bytes()).hexdigest() for f in sources}
combined=Counter();global_counts=Counter(rows[0][1]['case_keys']);pieces=[]
for (name,value,dest),shard in zip(rows[1:],m['shards']):
    expected=Counter(k for n,k in zip(rows[0][1]['nodeids'],rows[0][1]['case_keys']) if n.split('::',1)[0] in shard['files'])
    assert Counter(value['case_keys'])==expected
    combined.update(value['case_keys']);shard['cases']=len(value['nodeids'])
    pieces.append(dict(shard=name,cases=shard['cases'],files=len(shard['files']),stable_identity_matches_global_exact_multiset=True,private_collection_sha256=sha256(dest.read_bytes()).hexdigest()))
assert combined==global_counts
m['historical_pre_startup_diagnostics_20261021']=old
m.update(source_parent_head=head,collected_cases=len(rows[0][1]['nodeids']),collected_files=len(files))
for group in ['source_file_sha256','implementation_source_sha256']:
    m[group]={f:before[f] for f in m[group]}
m['collection_evidence']=dict(current_cases=m['collected_cases'],current_files=len(files),
    actual_collection_source_sha=head,current_stable_collection_sha256=sha256(('\n'.join(sorted(rows[0][1]['case_keys']))+'\n').encode()).hexdigest(),
    global_private_collection_sha256=sha256(rows[0][2].read_bytes()).hexdigest(),exact_piece_stable_multiset_matches_global=True,
    shards=pieces,linux_collect_exit_codes=[0]*5,execution_claim='COLLECT_ONLY_NOT_PASS_NOT_WINDOWS_ACCEPTANCE',
    source_bytes_unchanged_during_collection=True,head_blob_raw_sha256_binding_verified=True,
    diagnostic_catalog_ast_completeness_claimed=True,diagnostic_catalog_ids=index['ids'],diagnostic_catalog_generation=index['generation'],
    windows_dependency_and_fixture_compatibility_claimed=False)
m['diagnostic_allowlist_sha256']=sha256((root/'scripts/windows_ci/diagnostic-test-ids.json').read_bytes()).hexdigest()
m['weight_source']='Prior395 file assignments retained; one startup diagnostics failure-injection test file added to S1. Counts refreshed by actual global and four-piece exact collection. Historical Linux weights unchanged, not current Windows costs.'
m['source_binding_note']=f'Actual global and four-piece collection at {head};{m["collected_cases"]} cases/{len(files)} files. All{len(m["source_file_sha256"])+len(m["implementation_source_sha256"])} raw fingerprint entries verified against frozen HEAD blobs, unchanged during collection. Targeted21PASS is separate from collection and does not establish hosted browser/cold recovery/Windows acceptance. No new CI or font use.'
p.write_text(json.dumps(m,indent=2)+'\n')
print('manifest refreshed',head,'fingerprint entries',len(m['source_file_sha256'])+len(m['implementation_source_sha256']),flush=True)
