"""Metadata-only exact-reference equivalence; no product assertions or PG."""
from pathlib import Path
import importlib.util,json,hashlib,random
root=Path('/workspace/ParkWeave');p=root/'.runtime/frontier-root/fast_known_redaction.py';spec=importlib.util.spec_from_file_location('new_metadata_redactor',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
values=set()
for n in ('frontier-root','frontier-ui','frontier-backend','frontier-oracle','frontier-review'):
 for q in (root/'.runtime'/n).rglob('*.private.json'):
  raw=json.loads(q.read_text());assert isinstance(raw,list);values.update(v for v in raw if len(v)>=16)
ordered=sorted(values,key=lambda v:(-len(v),v));cases=0
pools=[ordered,[],['A'*43],['A'*43,'TOKEN_SHORT_LITERAL'],['A'*43,'A'*19],['A'*43,'B'*43,'A'*19],['LONGER'+'A'*50,'A'*43,'A'*19]]
rng=random.Random(17)
for pool in pools:
 pool=sorted(pool,key=lambda v:(-len(v),v));red=m.KnownTokenRedactor(pool)
 samples=['','plain untouched metadata','A'*100,'['+'A'*43+']',m.PLACEHOLDER]
 if pool:samples+=['::'.join(pool),'prefix'+pool[0]+'suffix',pool[-1]*3]
 for _ in range(60):samples.append(''.join(rng.choice(pool+['nonprivate','::','x']) for _ in range(6)))
 for text in samples:
  actual,count=red.replace(text);expected,n=m.reference_replace(text,pool);assert actual==expected and count==n
  assert red.has_residual(actual)==any(v in actual for v in pool);cases+=1
result=dict(scope='METADATA_REDACTION_EXACT_REFERENCE_EQUIVALENCE_NOT_PRODUCT_TEST_COUNTS',status='PASS',cases=cases,actual_known_pool_count=len(ordered),actual_known_lengths=sorted({len(v) for v in ordered}),helper_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),no_private_values_or_input_text_exported=True)
(root/'.runtime/frontier-root/redaction-equivalence-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
