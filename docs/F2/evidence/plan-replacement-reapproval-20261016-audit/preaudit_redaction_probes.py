"""Pure synthetic exporter/redaction invariants; never print private values."""
from pathlib import Path
import sys,json,hashlib,importlib.util
sys.dont_write_bytecode=True
root=Path('/workspace/ParkWeave');sys.path.insert(0,str(root/'.runtime/plan-replacement-root'))
spec=importlib.util.spec_from_file_location('audit_exporter',root/'.runtime/plan-replacement-root/export_archive.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from fast_known_redaction import KnownTokenRedactor,reference_replace
results=[]
def check(name,condition):
 assert condition,name
 results.append(dict(name=name,status='PASS'))
fakes=['A'*43,'B'*43,'Z'*43];values=sorted(fakes,key=lambda s:(-len(s),s))
texts=['plain no value','A'*43,'x'+'A'*43+'y','A'*44,'A'*43+'B'*43,'[A'+('B'*43)+']',('A'*43)+' '+('Z'*43)]
for i,t in enumerate(texts):
 r=KnownTokenRedactor(values);actual=r.replace(t);expect=reference_replace(t,values)
 check('fast_vs_reference_'+str(i),actual==expect and not r.has_residual(actual[0]))
fallback=['short-value','x'*44]
r=KnownTokenRedactor(fallback);check('non43_reference_fallback',r.replace('short-value '+('x'*44))==reference_replace('short-value '+('x'*44),fallback))
samples={'.json':json.dumps({'nested':[fakes[0],{'value':fakes[1]}],'unicode':'合成'}).encode(),'.jsonl':(json.dumps({'value':fakes[0]})+'\n'+json.dumps([fakes[1]])+'\n').encode(),'.xml':('<root attr="'+fakes[0]+'"><a>'+fakes[1]+'</a>'+fakes[2]+'</root>').encode(),'.log':('f = (<parkweave.store.Store object at 0x000>, {"token": "truncated..."})\n'+'value='+fakes[0]+'\n').encode()}
for suffix,raw in samples.items():
 before=hashlib.sha256(raw).hexdigest();out,counts=m.export_bytes(raw,suffix,values)
 check('structured_redaction_'+suffix,out!=raw and counts['exact_private_value']>=1 and not any(v.encode() in out for v in values) and before==hashlib.sha256(raw).hexdigest())
 if suffix=='.log':check('fixture_repr_masked',b'[REDACTED_SYNTHETIC_FIXTURE_REPR]' in out)
for suffix in ('.json','.xml','.log'):
 raw={'.json':b'{"a":1}\r\n','.xml':b'<root a="plain"/>\r\n','.log':b'plain\r\n'}[suffix]
 out,counts=m.export_bytes(raw,suffix,values);check('no_redactions_byte_identical_'+suffix,out==raw and not any(counts.values()))
try:m.export_bytes(json.dumps({fakes[0]:'unsafe-key'}).encode(),'.json',values)
except AssertionError:check('known_token_in_json_key_fails_closed',True)
else:raise AssertionError('unsafe key accepted')
registries=m.PRIVATE_SETS;before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in registries if p.is_file()};pool=m.private_values();after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in registries if p.is_file()}
check('private_registry_read_only',before==after)
check('private_pool_fast_shape',all(len(v)==43 and KnownTokenRedactor([v]).fast_pool for v in pool))
result=dict(scope='PURE_SYNTHETIC_EXPORTER_REDACTION_PREAUDIT_NO_PUBLIC_EXPORT',results=results,count=len(results),private_registry_count=len(before),private_pool_count=len(pool),exporter_sha256=hashlib.sha256((root/'.runtime/plan-replacement-root/export_archive.py').read_bytes()).hexdigest(),redactor_sha256=hashlib.sha256((root/'.runtime/plan-replacement-root/fast_known_redaction.py').read_bytes()).hexdigest())
print(json.dumps(result,sort_keys=True,indent=2))
