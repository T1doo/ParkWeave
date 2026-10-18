from pathlib import Path
import ast,hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018';dest=root/'docs/F2/evidence/resource-approval-host-read-20261018';assert not dest.exists()
a=json.loads((r/'accepted-tests.json').read_text());ind=json.loads((r/'independent-final-review.json').read_text());assert ind['source_sha']==a['source_sha']
for call in r.glob('*-invocation.json'):
 d=json.loads(call.read_text());base=Path(d['basetemp']);label=call.name.removesuffix('-invocation.json')
 if not base.is_dir():continue
 for p in sorted(base.rglob('*')):
  if not p.is_file() or p.suffix not in ('.json','.jsonl','.xml','.log','.png','.stdout','.stderr'):continue
  rel=p.relative_to(base)
  if any(x=='data' or x.startswith('parkweave-pg') for x in rel.parts):continue
  target=r/'retained-tmp'/label/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate key '+k)
  d[k]=v
 return d
invalid=[]
for p in (r/'retained-tmp').rglob('*.json'):
 try:json.loads(p.read_bytes(),object_pairs_hook=unique)
 except ValueError as exc:
  rel=str(p.relative_to(r));raw=p.read_bytes()
  assert rel=='retained-tmp/final/test_unverified_missing_or_wro1/SYNTHETIC-existing-approval.json',rel
  assert str(exc)=='duplicate key state' and raw.count(b'"state":')==2
  invalid.append(dict(relative_path=rel,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),artifact_kind='INTENTIONAL_DUPLICATE_KEY_SOURCE_INPUT',origin_test='tests/test_resource_plan_approval_read.py::test_unverified_missing_or_wrong_contract_source_never_approves[duplicate-key]'))
assert len(invalid)==1
(r/'intentional-input-classification.json').write_text(json.dumps(invalid,indent=2)+'\n')
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root);known=set(pattern.findall(tracked));identifiers=[]
for name in tracked.decode().split('\0'):
 if name.endswith('.py') and name.startswith(('src/','tests/','scripts/')):
  for node in ast.walk(ast.parse((root/name).read_text())):
   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and pattern.fullmatch(node.name.encode()):known.add(node.name.encode());identifiers.append(node.name)
records=[]
for p in sorted(r.rglob('*')):
 if not p.is_file() or p.suffix not in ('.json','.jsonl','.xml','.log','.png','.stdout','.stderr','.py','.js','.html','.txt','.md') or p.name=='inherited-evidence-blobs.txt':continue
 rel=p.relative_to(r);public=dest/'runtime'/rel;public.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes();count=[0]
 def redact_bytes(data):
  def sub(m):
   if m.group() in known:return m.group()
   count[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
  return pattern.sub(sub,data)
 def scrub(value):
  if isinstance(value,str):return redact_bytes(value.encode()).decode()
  if isinstance(value,list):return [scrub(x) for x in value]
  if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
  return value
 special=next((x for x in invalid if x['relative_path']==str(rel)),None)
 if special or p.suffix in ('.py','.js','.html','.png'):data=raw
 elif p.suffix=='.json':
  value=scrub(json.loads(raw,object_pairs_hook=unique));data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode() if count[0] else raw
 elif p.suffix=='.jsonl':
  values=[scrub(json.loads(line,object_pairs_hook=unique)) for line in raw.splitlines()];data=('\n'.join(json.dumps(x,ensure_ascii=False) for x in values)+'\n').encode() if count[0] else raw
 elif p.suffix=='.xml':
  tree=E.fromstring(raw)
  for node in tree.iter():
   if node.text:node.text=redact_bytes(node.text.encode()).decode()
   if node.tail:node.tail=redact_bytes(node.tail.encode()).decode()
   if 'message' in node.attrib:node.set('message',redact_bytes(node.get('message').encode()).decode())
  data=E.tostring(tree,encoding='utf-8',xml_declaration=True) if count[0] else raw
 else:data=redact_bytes(raw)
 public.write_bytes(data);entry=dict(raw_path=str(p),public_path=str(Path('runtime')/rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=count[0])
 if special:entry.update({k:v for k,v in special.items() if k in ('artifact_kind','origin_test')})
 records.append(entry)
manifest=dict(source_sha=a['source_sha'],records=records,redactions=sum(x['redactions'] for x in records),source_proven_identifiers=sorted(set(identifiers)),redaction='43-character URL-safe synthetic temporary session candidates; source-proven paths/AST identifiers excluded; JSON keys and JUnit test identifiers unchanged',excluded=['PG data','host.fixture-private contains only synthetic signing key and stays private','inherited raw Git index list'],limits=['SAME_UID_SYNTHETIC protection-boundary DI positives, no production installation proof','Only final190 and independent55 overlap count','No real source backend, formal approval/consumption, Windows or AT acceptance'])
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'],intentional_input_count=len(invalid))))
