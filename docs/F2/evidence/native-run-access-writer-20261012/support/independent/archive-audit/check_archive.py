"""Read-only independent verification of the explicitly frozen writer archive."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True
ROOT=Path('/workspace/ParkWeave')
PRIVATE=ROOT/'.runtime/native-run-access-writer-20261012'
OWN=ROOT/'.runtime/native-run-access-writer-review-20261012'
PUBLIC=ROOT/'docs/F2/evidence/native-run-access-writer-20261012'
OUT=OWN/'archive-audit'
SOURCE='b1f241182ec8d44f64a8e7ea5d782472590c0b00'
BASE='9ea666620bdf9b88bca395e7ccf471ec7901a038'
SHA=lambda b:hashlib.sha256(b).hexdigest()

def load(relative,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

policy=load('docs/F2/evidence/case-cancel-before-accept-20261011/build_archive.py','independent_accepted_scrub')
metadata=load('docs/F2/evidence/case-cancel-after-receipt-20261011/build_archive.py','independent_accepted_metadata')

def identity(data):
    tree=ET.fromstring(data);rows=[]
    for case in tree.iter('testcase'):
        status='ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        rows.append((case.get('classname'),case.get('name'),case.get('time'),status))
    assert len(rows)==len({row[:2] for row in rows}), 'duplicate testcase identity'
    suites=[]
    for element in tree.iter('testsuite'):
        attrs=dict(element.attrib);attrs.pop('hostname',None);suites.append(attrs)
    return rows,suites

CREDENTIAL_KEYS={'writer_dsn','app_dsn','dsn','database_uri','database_url','connection_uri','connection_url',
    'private_key','signing_key','key','secret','password','token','tokens','id_token','access_token',
    'refresh_token','session','session_key','session_token','auth','authorization','credentials'}

def check_json(value,path=()):
    if isinstance(value,dict):
        for name,child in value.items():
            if name.lower() in CREDENTIAL_KEYS:
                assert child is None or isinstance(child,(bool,int)) or child=='', 'credential field at '+repr(path+(name,))
            check_json(child,path+(name,))
    elif isinstance(value,list):
        for index,child in enumerate(value):check_json(child,path+(index,))
    elif isinstance(value,str):
        assert not re.search(r'postgres(?:ql)?://[^\s]+',value), 'PG URI in exported metadata at '+repr(path)
        assert not re.search(r'(?i)\bBearer\s+(?!\[REDACTED)[A-Za-z0-9_.~+/=-]+',value), 'Bearer credential at '+repr(path)

def main():
    started=datetime.now(timezone.utc).isoformat()
    manifest_bytes=(PUBLIC/'archive-manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
    frozen_bytes=(PRIVATE/'archive-inputs.json').read_bytes();frozen=json.loads(frozen_bytes)
    static_bytes=(PRIVATE/'archive-static-whitelist.json').read_bytes();static=json.loads(static_bytes)
    approval=json.loads((OWN/'STATIC_EXPORT_REVIEW.json').read_text())
    assert static==approval['approved_paths'] and len(static)==31
    assert manifest['input_set_sha256']==SHA(frozen_bytes)
    assert manifest['static_allowlist_sha256']==SHA(static_bytes)
    assert manifest['source_sha']==SOURCE and manifest['raw_inputs_rewritten'] is False
    artifacts=manifest['artifacts'];assert len(artifacts)==1989==len(frozen)
    originals=[item['original_local_path'] for item in artifacts]
    exports=[item['exported_path'] for item in artifacts]
    assert len(originals)==len(set(originals)) and len(exports)==len(set(exports))
    assert set(originals)=={item['original_local_path'] for item in frozen}
    frozen_by_path={item['original_local_path']:item for item in frozen}
    categories=Counter();redactions=Counter();junit=[];static_seen={};total_raw=total_export=total_payload=0;gzip_count=0
    original_failures=[]
    for item in artifacts:
        original=ROOT/item['original_local_path'];target=PUBLIC/item['exported_path']
        assert original.is_relative_to(PRIVATE) or original.is_relative_to(OWN)
        assert original.is_file() and target.is_file(), 'missing original/export '+item['original_local_path']
        raw=original.read_bytes();export=target.read_bytes()
        assert SHA(raw)==item['original_sha256']==frozen_by_path[item['original_local_path']]['sha256'], 'original hash '+item['original_local_path']
        assert len(raw)==item['original_bytes'] and len(export)==item['exported_bytes']
        assert SHA(export)==item['exported_sha256'], 'export hash '+item['exported_path']
        payload=gzip.decompress(export) if item['compression']=='gzip' else export
        if item['compression']=='gzip':
            gzip_count+=1;assert gzip.compress(payload,mtime=0)==export
        else:assert item['compression'] is None
        assert SHA(payload)==item['sanitized_payload_sha256'] and len(payload)==item['sanitized_payload_bytes']
        frozen_name=frozen_by_path[item['original_local_path']]['exported_path']
        expected_name=frozen_name+'.gz' if item['compression']=='gzip' else frozen_name
        assert item['exported_path']==expected_name
        counts=Counter();classification=item['classification']
        if classification=='JUNIT':
            prior=identity(raw);current=identity(payload);assert prior==current, 'JUnit identity/outcome/time '+item['exported_path']
            tree=ET.fromstring(raw)
            for suite in tree.iter('testsuite'):
                if 'hostname' in suite.attrib:suite.set('hostname','synthetic-fixture-host');counts['hostname']+=1
            for element in tree.iter():
                if element.tag in ('failure','error','system-out','system-err','skipped'):
                    if element.text:element.text=policy.scrub(element.text,counts)
                    for key in list(element.attrib):element.set(key,policy.scrub(element.get(key),counts))
            expected=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
            outcomes=dict(Counter(row[3] for row in prior[0]));assert item['test_results_preserved']==outcomes
            junit.append(dict(path=item['original_local_path'],count=len(prior[0]),counts=outcomes,suites=prior[1]))
            for row in prior[0]:
                if row[3] in ('FAIL','ERROR'):original_failures.append(dict(window=str(original.parent.relative_to(ROOT)),classname=row[0],name=row[1],status=row[3]))
        elif classification=='JSON_METADATA':
            value=json.loads(raw);check_json_fields_only(value)
            expected=(json.dumps(metadata.metadata_scrub(value,counts),indent=2,sort_keys=True)+'\n').encode()
            check_json(json.loads(payload))
        elif classification=='STATIC_CODE_EXACT_SHA_ALLOWLIST':
            assert static.get(item['original_local_path'])==SHA(raw)
            static_seen[item['original_local_path']]=SHA(raw);expected=raw
        else:
            assert classification=='STDOUT_OR_REPORT'
            expected=policy.scrub(raw.decode(),counts).encode()
        assert expected==payload, 'accepted policy byte reproduction '+item['exported_path']
        assert dict(counts)==item['redactions'], 'redaction counters '+item['exported_path']
        if classification not in ('STATIC_CODE_EXACT_SHA_ALLOWLIST','JSON_METADATA'):
            text=payload.decode()
            assert not re.search(r'postgres(?:ql)?://[^\s]+',text), 'URI in exported text '+item['exported_path']
            assert not re.search(r'(?i)\bBearer\s+(?!\[REDACTED)[A-Za-z0-9_.~+/=-]+',text), 'Bearer in exported text '+item['exported_path']
        categories[classification]+=1;redactions.update(counts);total_raw+=len(raw);total_export+=len(export);total_payload+=len(payload)
    assert static_seen==static, 'exact approved static set not preserved'
    root_run=json.loads((PRIVATE/'frozen-final-actor-guard/run.json').read_text())
    own_run=json.loads((OWN/'delivery-frozen-complete/run.json').read_text())
    root_rows,_=identity((PRIVATE/'frozen-final-actor-guard/results.xml').read_bytes())
    own_rows,_=identity((OWN/'delivery-frozen-complete/results.xml').read_bytes())
    assert root_run['exit_code']==own_run['exit_code']==0
    assert len(root_rows)==1070 and len(own_rows)==78 and all(row[3]=='PASS' for row in root_rows+own_rows)
    assert root_run['source_head']==own_run['source_head']==SOURCE
    assert not root_run['source_drift'] and not own_run['source_changed'] and not own_run['probe_changed']
    root_ids={row[:2] for row in root_rows};own_ids={row[:2] for row in own_rows}
    overlap=len(root_ids & own_ids);additional=len(own_ids-root_ids)
    assert overlap==68 and additional==10
    root_modules={name for name,_ in root_ids};assert len(root_modules)==25
    all_final=root_ids|own_ids;unmatched=[];mapped=[]
    for failure in original_failures:
        if (failure['classname'],failure['name']) in all_final:mapped.append(failure)
        else:unmatched.append(failure)
    assert all(not f['window'].startswith('.runtime/native-run-access-writer-20261012/') for f in unmatched), 'unmapped original root failure'
    summary=json.loads((PRIVATE/'delivery-result-summary.json').read_text())
    assert summary['overlap']==overlap and summary['independent_additional']==additional
    assert not summary['unresolved_original_root_ids']
    mapping=summary['original_root_to_final'] if 'original_root_to_final' in summary else next(v for k,v in summary.items() if isinstance(v,list) and v and isinstance(v[0],dict) and 'final' in v[0])
    expected_root={(Path(f['window']).name,f['classname'],f['name'],f['status']) for f in original_failures if f['window'].startswith('.runtime/native-run-access-writer-20261012/')}
    reported={(m['window'],m['classname'],m['name'],m['original']) for m in mapping}
    assert expected_root==reported and all(m['final']=='PASS' for m in mapping)
    binding=json.loads((OWN/'delivery-source-binding.json').read_text())
    for name,expected in binding['previous_signed_report_hashes'].items():assert SHA((OWN/name).read_bytes())==expected
    for name,expected in binding['raw_record_hashes'].items():assert SHA((OWN/'delivery-frozen-complete'/name).read_bytes())==expected
    source=json.loads((OWN/'delivery-frozen-complete/source-before.json').read_text())['files']
    tree=subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)',SOURCE],cwd=ROOT,text=True)
    blobs={line.split(' ',1)[1]:line.split(' ',1)[0] for line in tree.splitlines()}
    for name,expected in source.items():
        data=(ROOT/name).read_bytes();assert SHA(data)==expected, 'source hash '+name
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name], 'source commit blob '+name
    assert len(source)==420
    old=json.loads((PRIVATE/'accepted-evidence-before.json').read_text());assert len(old)==3022
    old_tree=subprocess.check_output(['git','ls-tree','-r','--format=%(objectname) %(path)',BASE,'docs/F2/evidence'],cwd=ROOT,text=True)
    old_blobs={line.split(' ',1)[1]:line.split(' ',1)[0] for line in old_tree.splitlines()}
    assert set(old)==set(old_blobs), 'old3022 tracked set'
    old_directories={str(Path(p).parts[3]) for p in old}
    actual_old={str(p.relative_to(ROOT)) for label in old_directories for p in (ROOT/'docs/F2/evidence'/label).rglob('*') if p.is_file()}
    assert actual_old==set(old), 'old archive file additions/deletions'
    for name,expected in old.items():
        data=(ROOT/name).read_bytes();assert SHA(data)==expected, 'old archive bytes '+name
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==old_blobs[name]
    assert SHA((PUBLIC/'archive-manifest.json').read_bytes())==SHA(manifest_bytes)
    result=dict(conclusion='LIMITED_PASS',source_sha=SOURCE,manifest_sha256=SHA(manifest_bytes),input_set_sha256=SHA(frozen_bytes),static_allowlist_sha256=SHA(static_bytes),
        started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),artifacts=len(artifacts),categories=dict(categories),raw_bytes=total_raw,exported_bytes=total_export,payload_bytes=total_payload,gzip_artifacts=gzip_count,
        exact_policy_byte_reproduction=True,all_original_export_payload_hashes_match=True,all_JUnit_identity_result_time_and_suite_attrs_equal=True,junit_windows=junit,
        original_failed_occurrences=len(original_failures),original_sameID_finalPASS_occurrences=len(mapped),unmatched_original_independent_oracles=unmatched,
        root_actual=dict(PASS=1070,FAIL=0,ERROR=0,SKIP=0,exit_code=0,unique_ids=1070,module_count=25,process_seconds=root_run['elapsed_seconds'],started_utc=root_run['start_utc'],ended_utc=root_run['end_utc']),
        independent_actual=dict(PASS=78,FAIL=0,ERROR=0,SKIP=0,exit_code=0,unique_ids=78,module_overlap=68,additional_ids=10),combined_unique_ids=len(all_final),
        source_files=420,source_worktree_commit_drift=[],old_archives_count=3022,old_archive_set_or_byte_drift=[],signed_old_reports_unchanged=True,
        credentials='All selected JSON recursively checked for credential fields; exported nonstatic text/JSON no live PG URI or Bearer value. Public HMAC receipt proofs/key_id are signatures/fingerprints, not signing-key values. Static31 exact previously read/approved copies only.',
        production_installation='NOT_RUN',restricted_production_role='NOT_VERIFIED',production_permissions='NOT_RUN',formal_AT35='NOT_RUN',browser_attempts=0,Windows_native_IPC='NOT_RUN',remaining_blockers=[],
        audit_did_not_modify_public_files=True,core_not_expanded=True)
    (OUT/'audit-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['conclusion','manifest_sha256','artifacts','categories','gzip_artifacts','original_failed_occurrences','original_sameID_finalPASS_occurrences','combined_unique_ids','unmatched_original_independent_oracles']}))

def check_json_fields_only(value,path=()):
    if isinstance(value,dict):
        for name,child in value.items():
            if name.lower() in CREDENTIAL_KEYS:assert child is None or isinstance(child,(bool,int)) or child=='', 'raw credential metadata field at '+repr(path+(name,))
            check_json_fields_only(child,path+(name,))
    elif isinstance(value,list):
        for index,child in enumerate(value):check_json_fields_only(child,path+(index,))

if __name__=='__main__':main()
