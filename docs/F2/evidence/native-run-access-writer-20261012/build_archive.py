"""Export exact failed and passed windows without changing private inputs."""
from collections import Counter
import gzip,hashlib,importlib.util,json,re,sys
from pathlib import Path
import xml.etree.ElementTree as E
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
PRIVATE=ROOT/'.runtime/native-run-access-writer-20261012'
REVIEW=ROOT/'.runtime/native-run-access-writer-review-20261012'
SPEC=importlib.util.spec_from_file_location('accepted_scrub',OUTPUT.parent/'case-cancel-before-accept-20261011/build_archive.py')
policy=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(policy)
SPEC2=importlib.util.spec_from_file_location('accepted_metadata',OUTPUT.parent/'case-cancel-after-receipt-20261011/build_archive.py')
metadata=importlib.util.module_from_spec(SPEC2);SPEC2.loader.exec_module(metadata)
sha=lambda value:hashlib.sha256(value).hexdigest()
ALLOWED={'.xml','.log','.json','.md','.py','.js','.txt','.diff'}

def candidates():
    values=[]
    for directory,label in ((PRIVATE,'root'),(REVIEW,'independent')):
        for path in sorted(directory.rglob('*')):
            if (not path.is_file() or path.suffix not in ALLOWED or '__pycache__' in path.parts
                    or path.name in ('running.json','archive-static-whitelist.json','archive-inputs.json')
                    or path.name.startswith('archive-export-')):continue
            values.append((path,Path(label)/path.relative_to(directory)))
    return values

def credential_free(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if k.lower() in {'writer_dsn','app_dsn','private_key','signing_key','token','tokens','secret',
                             'password','session_token','credentials','dsn','authorization','key','id_token',
                             'access_token','refresh_token','session','session_key','auth','database_uri',
                             'database_url','connection_uri','connection_url'}:
                assert v is None or isinstance(v,(bool,int)) or v=='','credential-bearing metadata field: '+k
            credential_free(v)
    elif isinstance(value,list):
        for v in value:credential_free(v)

def main():
    final=json.loads((PRIVATE/'frozen-final-actor-guard/run.json').read_text())
    assert final['exit_code']==0 and not final['source_drift'],'require actual frozen PASS'
    allow=json.loads((PRIVATE/'archive-static-whitelist.json').read_text())
    frozen=json.loads((PRIVATE/'archive-inputs.json').read_text())
    assert frozen and len(frozen)==len({x['original_local_path'] for x in frozen})
    entries=[]
    for item in frozen:
        path=ROOT/item['original_local_path'];name=Path(item['exported_path'])
        assert sha(path.read_bytes())==item['sha256'],'frozen archive input changed: '+str(path)
        raw=path.read_bytes();counts=Counter();outcomes=None
        if path.suffix=='.xml':
            tree=E.fromstring(raw);before=policy.identity_results(tree)
            assert len(before[0])==len({(x[0],x[1]) for x in before[0]}),'duplicate JUnit IDs'
            for suite in tree.iter('testsuite'):
                if 'hostname' in suite.attrib:suite.set('hostname','synthetic-fixture-host');counts['hostname']+=1
            for element in tree.iter():
                if element.tag in ('failure','error','system-out','system-err','skipped'):
                    if element.text:element.text=policy.scrub(element.text,counts)
                    for k in list(element.attrib):element.set(k,policy.scrub(element.get(k),counts))
            assert policy.identity_results(tree)==before,'JUnit identities/statuses/durations changed'
            exported=E.tostring(tree,encoding='utf-8',xml_declaration=True)
            classification='JUNIT';outcomes=dict(Counter(v[-1] for v in before[0]))
        elif path.suffix=='.json':
            value=json.loads(raw);credential_free(value)
            exported=(json.dumps(metadata.metadata_scrub(value,counts),indent=2,sort_keys=True)+'\n').encode()
            classification='JSON_METADATA'
        elif metadata.static_code(path):
            assert allow.get(str(path.relative_to(ROOT)))==sha(raw),'unreviewed static artifact: '+str(path)
            exported=raw;classification='STATIC_CODE_EXACT_SHA_ALLOWLIST'
        else:
            exported=policy.scrub(raw.decode(),counts).encode();classification='STDOUT_OR_REPORT'
        payload=exported;compression=None
        target=OUTPUT/name
        if len(exported)>512000:compression='gzip';target=target.with_suffix(target.suffix+'.gz');exported=gzip.compress(exported,mtime=0)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==exported,'immutable export differs: '+str(target)
        else:target.write_bytes(exported)
        entries.append(dict(original_local_path=str(path.relative_to(ROOT)),original_sha256=sha(raw),original_bytes=len(raw),
            exported_path=str(target.relative_to(OUTPUT)),exported_sha256=sha(exported),exported_bytes=len(exported),
            sanitized_payload_sha256=sha(payload),sanitized_payload_bytes=len(payload),compression=compression,
            classification=classification,redactions=dict(counts),test_results_preserved=outcomes))
    manifest=dict(format='SANITIZED_COPY_WITH_ORIGINAL_HASH',raw_inputs_rewritten=False,
        source_sha=final['source_head'],source_manifest_sha256=final['source_manifest_sha256'],
        policy_source_sha256=sha(Path(SPEC.origin).read_bytes()),
        input_set_sha256=sha((PRIVATE/'archive-inputs.json').read_bytes()),
        static_allowlist_sha256=sha((PRIVATE/'archive-static-whitelist.json').read_bytes()),
        policy='Accepted stdout/JUnit scrub; JSON retains literal hashes/IDs. Exact allowlisted static code only. Failed windows remain failed; no old results transferred.',
        artifacts=entries)
    (OUTPUT/'archive-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(files=len(entries),original_bytes=sum(x['original_bytes'] for x in entries),
                         exported_bytes=sum(x['exported_bytes'] for x in entries))))
if __name__=='__main__':main()

