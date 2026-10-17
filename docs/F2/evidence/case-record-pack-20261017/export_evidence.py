"""Export closed windows; preserve original bytes and JSON/JUnit identities."""
from pathlib import Path
import collections, hashlib, json, re, xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/case-record-pack';OUT=ROOT/'docs/F2/evidence/case-record-pack-20261017'
def sha(b):return hashlib.sha256(b).hexdigest()
def strict(b):
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d:raise ValueError('duplicate JSON key')
   d[k]=v
  return d
 return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('non-JSON number')))
def shape(v):
 if isinstance(v,dict):return {k:shape(x) for k,x in v.items()}
 if isinstance(v,list):return [shape(x) for x in v]
 return type(v).__name__
def stats(b):
 r=ET.fromstring(b);cs=r.findall('.//testcase');ns=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cs]
 return dict(unique=len(set(ns)),testcases=len(cs),failures=len(r.findall('.//failure')),errors=len(r.findall('.//error')),skipped=len(r.findall('.//skipped')),seconds=sum(float(s.get('time')) for s in r.findall('.//testsuite'))),ns
def xml_identity(b):return [(e.tag,{k:v for k,v in e.attrib.items() if k!='message'}) for e in ET.fromstring(b).iter()]
assert not OUT.exists()
f=strict((R/'freeze.json').read_bytes());m=strict((R/'final-v2-invocation.json').read_bytes())
assert m['exit_code']==0 and m['source_sha']==f['source_sha'] and m['uncommitted_source_diff_sha256']==sha(b'')
assert all(sha((ROOT/p).read_bytes())==h for p,h in f['files'].items())
final,nodes=stats((R/'final-v2.xml').read_bytes());assert nodes==strict((R/'final-nodes.json').read_bytes())
assert final['unique']==final['testcases']==179 and final['failures']==final['errors']==final['skipped']==0
review=strict((R/'independent-review.json').read_bytes());assert review['source_sha']==f['source_sha'] and review['blockers_remaining']==0
old=strict((R/'inherited-evidence-blobs.json').read_bytes())
for p,blob in old.items():
 b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob
windows={w:stats((R/(w+'.xml')).read_bytes())[0] for w in ('dev-v1','dev-v2','edge-v3','dev-v4','final-v1','repair-v2','final-v2')}
names=['preflight.json','process-check.json','freeze.json','final-collection.txt','final-nodes.json','failure-ledger.json','remote-before.txt','remote-pre-delivery.txt','preservation-pre-delivery.json','inherited-evidence-blobs.json','independent-review.json','run-window.py','export_evidence.py','verify_delivery.py','independent-probes.js.txt','independent-backend-probe.py.txt','independent-probes.stdout.txt','verify_delivery-before-syntax-fix.py.txt','helper-compile-failure.json','repair-v2-nodes.json','repair-static-review.json','independent-prepost-command.txt','source.patch','independent-review-failure.json','independent-review-initial-failure.stdout.txt','source-ancestry.json','preservation-final-source-pre-delivery.json','remote-final-source-pre-delivery.txt','remote-final-source-pre-delivery.stderr']
sources=[(R/n,n) for n in names]
archive=R/'first-freeze-637'
sources += [(p,str(p.relative_to(R))) for p in sorted(archive.rglob('*')) if p.is_file()]
for w in windows:
 for suffix in ('.log','.xml','-invocation.json'):sources.append((R/(w+suffix),w+suffix))
 snap=R/(w+'-source')
 if snap.exists():sources += [(p,str(p.relative_to(R))) for p in sorted(snap.rglob('*')) if p.is_file()]
 tmp=Path('/tmp')/('parkweave-case-record-'+w)
 sources += [(p,'browser/'+w+'/'+str(p.relative_to(tmp))) for p in sorted(tmp.rglob('*')) if p.is_file() and not p.is_symlink() and (p.suffix=='.png' or p.name in ('ordinary-api.log','actual-0.txt','actual-1.txt','proof.json'))]
 extra=R/w
 if extra.exists():sources += [(p,'related-browser/'+w+'/'+str(p.relative_to(extra))) for p in sorted(extra.rglob('*')) if p.is_file()]
assert all(p.is_file() for p,_ in sources)
assert len(set(n for _,n in sources))==len(sources)
pattern=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');known=set()
for p in f['files']:
 known.update(pattern.findall(p))
 try:known.update(pattern.findall((ROOT/p).read_text()))
 except UnicodeDecodeError:pass
for p,_ in sources:
 if p.is_relative_to(R) and (p.suffix=='.py' or '-source/' in str(p.relative_to(R))):known.update(pattern.findall(p.read_text()))
 if p.suffix=='.xml':
  for c in ET.fromstring(p.read_bytes()).findall('.//testcase'):
   known.update(pattern.findall(c.get('classname','')));known.update(pattern.findall(c.get('name','')))
for n in ('remote-before.txt','remote-pre-delivery.txt','remote-final-source-pre-delivery.txt'):
 for line in (R/n).read_text().splitlines():
  digest,ref=line.split('\t');assert re.fullmatch('[a-f0-9]{40}',digest) and ref.startswith('refs/heads/');known.update(pattern.findall(ref))
redactions=0
def redact(s):
 def replace(m):
  global redactions
  if m[0] in known:return m[0]
  redactions+=1;return '[SYNTHETIC_SESSION_REDACTED]'
 return pattern.sub(replace,s)
def values(v):
 if isinstance(v,dict):return {k:values(x) for k,x in v.items()}
 if isinstance(v,list):return [values(x) for x in v]
 return redact(v) if isinstance(v,str) else v
OUT.mkdir(parents=True);pairs=[]
for p,name in sources:
 raw=p.read_bytes();data=raw;before=redactions
 if p.suffix=='.json':
  v=strict(raw);clean=values(v)
  if v!=clean:data=(json.dumps(clean,ensure_ascii=False,indent=2)+'\n').encode()
  assert shape(v)==shape(strict(data))
 elif p.suffix=='.xml':
  r=ET.fromstring(raw)
  for e in r.iter():
   if e.text:e.text=redact(e.text)
   if e.tail:e.tail=redact(e.tail)
   if 'message' in e.attrib:e.attrib['message']=redact(e.attrib['message'])
  if before!=redactions:data=ET.tostring(r,encoding='utf-8',xml_declaration=True)
  assert xml_identity(raw)==xml_identity(data)
 elif p.suffix!='.png':data=redact(raw.decode()).encode()
 if p.name in ('remote-before.txt','remote-pre-delivery.txt','remote-final-source-pre-delivery.txt'):assert data==raw
 if p.name=='final-collection.txt':
  get=lambda b:[s for s in b.decode().splitlines() if s.startswith('tests/') and '::' in s];assert get(raw)==get(data)
 dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);assert sha(p.read_bytes())==sha(raw)
 pairs.append(dict(original=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),exported=str(dest.relative_to(ROOT)),original_sha256=sha(raw),exported_sha256=sha(data),original_bytes=len(raw),exported_bytes=len(data),redacted_occurrences=redactions-before))
gate=dict(base_sha=f['base_sha'],source_sha=f['source_sha'],branch=f['branch'],result='CURRENT_OWNER_COMPLETE_EXPLICIT_GOAL_RECORD_TEXT_PACK',final=final,modules=f['modules'],module_unique=dict(collections.Counter(n.split('::')[0] for n in nodes)),new_unique=31,new_unique_included_in179=True,windows=windows,windows_never_added=True,source_inputs=len(f['files']),source_drift=0,inherited_archive_git_blobs_checked=len(old),inherited_archive_drift=0,independent_review=review,public_pairs=len(pairs),redacted_occurrences=redactions,JSON_keys_preserved=True,JUnit_identity_preserved=True,remote_refs_byte_preserved=True,raw_evidence_retained=True,actual_ordinary_entry_UI_download_restart=True,original_GET_goal_results_only=True,generation_and_download_each_two_fresh_GET=True,all_current_required_goals_preserved=True,not_all_source_atomicity_or_signature=True,original_row_trace_hashes_are_references=True,no_new_business_commands_schema_grants_approvals=True,case_goal_completed=False,real_model_called=False,real_source_access_attempted=False,source_specific_formal_reader_still_unimplemented=True,NativeRunAccess_default_denials_preserved=True,Actions_queries=0,unknown_lock_process_removed=False,main_changed=False,forced_push=False,deployed=False,complete_project=False,not_run=['Windows native formal AT','real business/source identities/catalog/approvals/fulfillment','real model','production host positive source integration','V4 service-selection pack actual ordinary-process download','isolated execution report pack actual download','full project acceptance'],delivery_verification='actual delivery/remote SHA and clean worktree recorded after normal push in private delivery-verification.json and final reply')
(OUT/'gate.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2)+'\n');(OUT/'public-pairs.json').write_text(json.dumps(pairs,indent=2)+'\n')
(R/'export-validation.json').write_text(json.dumps(dict(public_pairs=len(pairs),redacted_occurrences=redactions,source_drift=0,archive_drift=0,strict_JSON=True,JUnit_ids_preserved=True),indent=2)+'\n')
print(json.dumps(dict(final=final,new_unique=31,public_pairs=len(pairs),redacted_occurrences=redactions),ensure_ascii=False))
