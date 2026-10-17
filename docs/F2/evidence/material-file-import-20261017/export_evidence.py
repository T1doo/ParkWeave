"""Closed-window evidence export. Raw failures remain in .runtime and /tmp."""
from pathlib import Path
import collections,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/material-file-import';OUT=ROOT/'docs/F2/evidence/material-file-import-20261017'
def sha(b):return hashlib.sha256(b).hexdigest()
def strict(b):
    def keys(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    return json.loads(b,object_pairs_hook=keys,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('constant')))
def shape(v):
    if isinstance(v,dict):return {k:shape(x) for k,x in v.items()}
    if isinstance(v,list):return [shape(x) for x in v]
    return type(v).__name__
def junit(b):
    root=ET.fromstring(b);cases=root.findall('.//testcase');nodes=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases]
    return dict(unique=len(set(nodes)),testcases=len(cases),failures=len(root.findall('.//failure')),errors=len(root.findall('.//error')),skipped=len(root.findall('.//skipped')),seconds=sum(float(s.get('time','0')) for s in root.findall('.//testsuite'))),nodes
def identity(b):return [(e.tag,{k:v for k,v in e.attrib.items() if k!='message'}) for e in ET.fromstring(b).iter()]
assert not OUT.exists()
f=strict((R/'freeze.json').read_bytes());meta=strict((R/'final-v1-invocation.json').read_bytes())
assert meta['exit_code']==0 and meta['source_sha']==f['source_sha'] and meta['uncommitted_source_diff_sha256']==sha(b'')
assert all(sha((ROOT/p).read_bytes())==h for p,h in f['files'].items())
final,nodes=junit((R/'final-v1.xml').read_bytes());assert nodes==strict((R/'final-nodes.json').read_bytes()) and final['unique']==final['testcases']==197 and final['failures']==final['errors']==final['skipped']==0
windows={w:junit((R/(w+'.xml')).read_bytes())[0] for w in ('dev-v1','dev-v2','dev-v3','final-v1')}
old=strict((R/'inherited-archive-blobs.json').read_bytes())
for p,blob in old.items():
    b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob
names=['preflight.json','selection.json','freeze.json','final-collection.txt','final-nodes.json','failure-ledger.json','remote-before.txt','remote-pre-delivery.txt','preservation-pre-delivery.json','inherited-archive-blobs.json','independent-review.json','dev-v1-test-source.py.txt','run-window.py','export_evidence.py','verify_delivery.py','independent-probes.py.txt','independent-probes.stdout.txt','independent-route-probes.js.txt']
sources=[(R/n,n) for n in names]
for w in windows:
    for suffix in ('.log','.xml','-invocation.json'):sources.append((R/(w+suffix),w+suffix))
    d=R/(w+'-source')
    if d.exists():
        sources += [(p,str(p.relative_to(R))) for p in sorted(d.rglob('*')) if p.is_file()]
    tmp=Path('/tmp')/('parkweave-material-file-'+w)
    sources += [(p,'browser/'+w+'/'+str(p.relative_to(tmp))) for p in sorted(tmp.rglob('*')) if p.is_file() and not p.is_symlink() and (p.suffix=='.png' or p.name in ('ordinary-api.log','actual-downloaded-material-pack.txt'))]
assert all(p.is_file() for p,_ in sources)
pattern=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');known=set()
for p in f['files']:
    known.update(pattern.findall(p))
    try:known.update(pattern.findall((ROOT/p).read_text()))
    except UnicodeDecodeError:pass
for p,_ in sources:
    if p.is_relative_to(R) and (p.suffix=='.py' or 'source' in str(p.relative_to(R))):known.update(pattern.findall(p.read_text()))
    if p.suffix=='.xml':
        for c in ET.fromstring(p.read_bytes()).findall('.//testcase'):
            known.update(pattern.findall(c.get('classname','')));known.update(pattern.findall(c.get('name','')))
for n in ('remote-before.txt','remote-pre-delivery.txt'):
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
for p,n in sources:
    raw=p.read_bytes();data=raw;before=redactions
    if p.suffix=='.json':
        v=strict(raw);clean=values(v)
        if v!=clean:data=(json.dumps(clean,indent=2,ensure_ascii=False)+'\n').encode()
        assert shape(v)==shape(strict(data))
    elif p.suffix=='.xml':
        root=ET.fromstring(raw)
        for e in root.iter():
            if e.text:e.text=redact(e.text)
            if e.tail:e.tail=redact(e.tail)
            if 'message' in e.attrib:e.attrib['message']=redact(e.attrib['message'])
        if before!=redactions:data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        assert identity(raw)==identity(data)
    elif p.suffix!='.png':data=redact(raw.decode()).encode()
    if p.name in ('remote-before.txt','remote-pre-delivery.txt'):assert data==raw
    if p.name=='final-collection.txt':
        get=lambda b:[s for s in b.decode().splitlines() if s.startswith('tests/') and '::' in s];assert get(raw)==get(data)
    dest=OUT/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    assert sha(p.read_bytes())==sha(raw)
    pairs.append(dict(original=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),exported=str(dest.relative_to(ROOT)),original_sha256=sha(raw),exported_sha256=sha(data),original_bytes=len(raw),exported_bytes=len(data),redacted_occurrences=redactions-before))
review=strict((R/'independent-review.json').read_bytes());assert review['source_sha']==f['source_sha'] and review['blockers_remaining']==0
counts=dict(collections.Counter(n.split('::')[0] for n in nodes))
gate=dict(base_sha=f['base_sha'],source_sha=f['source_sha'],branch=f['branch'],result='SYNTHETIC_FILE_TO_ORIGINAL_MATERIAL_FLOW_PASSED',final=final,modules=f['modules'],module_unique=counts,new_unique=74,new_unique_included_in197=True,windows=windows,windows_never_added=True,source_inputs=len(f['files']),source_drift=0,inherited_archive_git_blobs_checked=len(old),inherited_archive_drift=0,independent_review=review,public_pairs=len(pairs),redacted_occurrences=redactions,JSON_keys_preserved=True,JUnit_identity_preserved=True,remote_ref_lines_byte_preserved=True,raw_evidence_retained=True,parser_read_only=True,actual_browser_file_chooser=True,original_ADD_REVIEW_CONFIRM=True,actual_download_and_ordinary_process_restart=True,saved_evidence_UNVERIFIED=True,case_goal_completed=False,new_identity_grant_assignment_catalog_approval_credentials=False,test_preconditions='existing isolated synthetic fixtures only; no business provisioning',provider_fixture_injected_into_ordinary_server=False,real_source_access_attempted=False,real_model_called=False,formal_entry_still_closed=True,NativeRunAccess_default_permit_writer_denial_preserved=True,main_changed=False,forced_push=False,deployed=False,Actions_queries=0,prior427_diagnostics_rerun=False,unknown_lock_process_removed=False,complete_project=False,not_run=['Windows native formal AT','real business/source authority/trust and approvals','real model','deployment/full contest acceptance'],delivery_verification='actual delivery SHA/remote/worktree recorded after docs commit in private delivery-verification.json and final reply')
(OUT/'gate.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n');(OUT/'public-pairs.json').write_text(json.dumps(pairs,indent=2)+'\n')
(R/'export-validation.json').write_text(json.dumps(dict(pairs=len(pairs),redactions=redactions,source_drift=0,archive_drift=0,strict_JSON=True,JUnit_ids_preserved=True),indent=2)+'\n')
print(json.dumps(dict(final=final,new_unique=74,public_pairs=len(pairs),redacted_occurrences=redactions,module_unique=counts),ensure_ascii=False))
