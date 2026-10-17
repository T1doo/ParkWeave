"""Export only closed evidence files. Preserve JSON schema and JUnit identity."""
from pathlib import Path
import collections,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/formal-preparation-entry'
OUT=ROOT/'docs/F2/evidence/formal-preparation-entry-20261017'
def sha(data):return hashlib.sha256(data).hexdigest()
def strict(data):
    def keys(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):raise ValueError('non-JSON constant')
    return json.loads(data,object_pairs_hook=keys,parse_constant=invalid)
def shape(value):
    if isinstance(value,dict):return {k:shape(v) for k,v in value.items()}
    if isinstance(value,list):return [shape(v) for v in value]
    return type(value).__name__
def junit(path):
    root=ET.parse(path).getroot();cases=root.findall('.//testcase')
    nodes=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases]
    return dict(unique=len(set(nodes)),testcase_elements=len(cases),failure=len(root.findall('.//failure')),
        errors=len(root.findall('.//error')),skipped=len(root.findall('.//skipped')),
        seconds=sum(float(s.get('time','0')) for s in root.findall('.//testsuite'))),nodes
def xml_identity(data):
    return [(i.tag,{k:v for k,v in i.attrib.items() if k!='message'}) for i in ET.fromstring(data).iter()]

assert not OUT.exists()
try:strict(b'{"ordinary_key":1,"ordinary_key":2}')
except ValueError:pass
else:raise AssertionError('duplicate key refusal guard failed')
freeze=strict((R/'freeze.json').read_bytes());meta=strict((R/'final-v1-invocation.json').read_bytes())
assert meta['exit_code']==0 and meta['source_sha']==freeze['source_sha'] and meta['uncommitted_source_diff_sha256']==sha(b'')
assert all(sha((ROOT/p).read_bytes())==h for p,h in freeze['files'].items())
final,nodes=junit(R/'final-v1.xml');expected=strict((R/'final-nodes.json').read_bytes())
assert nodes==expected and final['unique']==final['testcase_elements']==186
assert final['failure']==final['errors']==final['skipped']==0
windows={name:junit(R/(name+'.xml'))[0] for name in ('dev-v1','edge-v1','final-v1')}
preserved=strict((R/'preservation-pre-delivery.json').read_bytes())
old=strict((R/'inherited-archive-blobs.json').read_bytes())
for p,blob in old.items():
    data=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
for p in preserved['existing_product_files_byte_unchanged_except_api_web']:
    assert subprocess.check_output(['git','show',freeze['base_sha']+':'+p],cwd=ROOT)==(ROOT/p).read_bytes()

names=['preflight.json','freeze.json','final-collection.txt','final-nodes.json','action-failures.json',
       'dev-v1-source-manifest.json','dev-v1-tracked-source.diff','remote-before.txt','remote-pre-delivery.txt',
       'inherited-archive-blobs.json','preservation-pre-delivery.json','run-window.py','export_evidence.py',
       'finalize_report.py','verify_delivery.py']
for name in windows:names += [name+'.log',name+'.xml',name+'-invocation.json']
sources=[(R/name,name) for name in names]
for path in sorted((R/'dev-v1-source').glob('*.txt')):sources.append((path,'dev-v1-source/'+path.name))
for name in windows:
    tmp=Path('/tmp')/('parkweave-formal-entry-'+name)
    for p in sorted(tmp.rglob('*')):
        if p.is_file() and not p.is_symlink() and (p.suffix=='.png' or p.name=='ordinary-api.log'):
            sources.append((p,'browser/'+name+'/'+str(p.relative_to(tmp))))
assert all(p.is_file() for p,_ in sources)
token=re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');known=set()
for name in freeze['files']:
    known.update(token.findall(name))
    try:known.update(token.findall((ROOT/name).read_text()))
    except UnicodeDecodeError:pass
for original,relative in sources:
    if original.suffix=='.py':known.update(token.findall(original.read_text()))
    if original.suffix=='.xml':
        for case in ET.fromstring(original.read_bytes()).findall('.//testcase'):
            known.update(token.findall(case.get('classname','')));known.update(token.findall(case.get('name','')))
redactions=0
def redact(value):
    def replace(match):
        global redactions
        if match[0] in known:return match[0]
        redactions+=1;return '[SYNTHETIC_SESSION_REDACTED]'
    return token.sub(replace,value)
def values_only(value):
    if isinstance(value,dict):return {k:values_only(v) for k,v in value.items()}
    if isinstance(value,list):return [values_only(v) for v in value]
    return redact(value) if isinstance(value,str) else value
OUT.mkdir(parents=True);pairs=[]
for original,relative in sources:
    raw=original.read_bytes();before=redactions;data=raw
    if original.suffix=='.json':
        parsed=strict(raw);cleaned=values_only(parsed)
        if cleaned!=parsed:data=(json.dumps(cleaned,indent=2,ensure_ascii=False)+'\n').encode()
        assert shape(parsed)==shape(strict(data))
    elif original.suffix=='.xml':
        tree=ET.fromstring(raw)
        for item in tree.iter():
            if item.text:item.text=redact(item.text)
            if item.tail:item.tail=redact(item.tail)
            if 'message' in item.attrib:item.attrib['message']=redact(item.attrib['message'])
        if before!=redactions:data=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
        assert xml_identity(raw)==xml_identity(data)
    elif original.suffix!='.png':data=redact(raw.decode()).encode()
    if original.name=='final-collection.txt':
        get=lambda b:[v for v in b.decode().splitlines() if v.startswith('tests/') and '::' in v]
        assert get(raw)==get(data)
    dest=OUT/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    assert sha(original.read_bytes())==sha(raw)
    pairs.append(dict(original=str(original.relative_to(ROOT)) if original.is_relative_to(ROOT) else str(original),
        exported=str(dest.relative_to(ROOT)),original_sha256=sha(raw),exported_sha256=sha(data),
        original_bytes=len(raw),exported_bytes=len(data),redacted_occurrences=redactions-before))
for p in OUT.rglob('*.json'):strict(p.read_bytes())
gate=dict(base_sha=freeze['base_sha'],source_sha=freeze['source_sha'],branch='dev/f3-formal-preparation-entry-20261017',
    result='CLOSED_FORMAL_PREFLIGHT_CONTRACT_PASSED_FORMAL_READ_NOT_IMPLEMENTED',final=final,
    modules=freeze['modules'],module_unique=dict(collections.Counter(n.split('::')[0] for n in nodes)),
    new_API_and_pure=40,new_browser_negative=3,new43_included_in186=True,windows=windows,windows_never_added=True,
    source_inputs=len(freeze['files']),source_drift=0,existing_product_files_unchanged_except_api_web=preserved['existing_product_files_byte_unchanged_except_api_web'],
    inherited_archive_git_blobs_checked=len(old),inherited_archive_drift=0,old_remote_heads_checked=preserved['old_heads_checked'],old_remote_heads_drift=0,
    base_review_branch_preserved_at=preserved['frozen_review_branch_sha'],public_pairs=len(pairs),redacted_occurrences=redactions,
    strict_JSON_duplicate_validation=True,JSON_values_only_redacted_keys_preserved=True,JUnit_identity_preserved=True,raw_evidence_retained=True,
    formal_business_read_success_implemented=False,source_specific_provenance_adapter_implemented=False,
    formal_plan_source_binding_and_resource_approval_mapping_implemented=False,
    source_reader_or_verifier_callbacks_invoked=False,real_source_access_attempted=False,
    self_reported_REAL_or_verified_cannot_open_entry=True,source_domain_or_object_type_IDs_never_alias=True,
    source_specific_proofs_required=['EXISTING_PREPARATION','EXISTING_CASE','EXISTING_RUN','EXISTING_ADOPTED_PLAN','CURRENT_SOURCE_SUBJECT_AUTHORITY'],
    independent_provenance_lookup='domain-qualified selection plus current subject metadata and READ purpose; not authority proof; no credential fields',
    implemented='public narrowing config and host interface types; authenticated GET preflight and exact reference binding; always closed for unknown real provenance; UI distinguishes missing implementation and external inputs',
    external_inputs_missing=['authorized source structure and existing record references/revisions','current source subject authority contract','existing trust and current head/revocation protocol','approved read-only host composition'],
    negative_process_restart_only=True,positive_real_process_installation_or_source_acceptance=False,
    browser_fault_injection='late200 reason damage and late403 response injection after real server200; not real source head change',
    execution_approval_writes_or_provisioning_added=False,prior427_or_diagnostic_SIGINT_smoke_reexecuted=False,Actions_queries=0,
    unknown_locks_processes_removed=False,new_credentials_security_permissions_costs=False,main_changed=False,deployed=False,
    transport_disconnect_preserved=True,transport_recovered_no_pytest_restart=True,independent_review='new slice pending parent review',
    not_run=['Windows native','formalAT/AT35','real business/source authority/trust','production positive host installation','resource execution/approval consumption'],
    complete_project=False,delivery_verification='actual SHA and remote/worktree recorded after docs commit in private delivery-verification.json and final reply')
(OUT/'gate.json').write_text(json.dumps(gate,indent=2,ensure_ascii=False)+'\n')
(OUT/'public-pairs.json').write_text(json.dumps(pairs,indent=2)+'\n')
(R/'export-validation.json').write_text(json.dumps(dict(public_pairs=len(pairs),redactions=redactions,JSON_keys_preserved=True,JUnit_ids_preserved=True,source_drift=0,inherited_drift=0),indent=2)+'\n')
print(json.dumps({k:gate[k] for k in ('result','source_sha','final','public_pairs','redacted_occurrences')},ensure_ascii=False))
