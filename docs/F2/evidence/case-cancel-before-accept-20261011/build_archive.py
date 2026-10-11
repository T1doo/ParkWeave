"""Export synthetic test evidence with explicit, reproducible redactions.

Private inputs remain byte-for-byte unchanged. JUnit testcase identities, counts,
outcomes and durations remain intact. Exported copies are labelled sanitized,
and the manifest records both original and exported hashes.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT / '.runtime/case-cancel'
OUTPUT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scrub(text, counts):
    def replace(kind, pattern, value, flags=0):
        nonlocal text
        text, n = re.subn(pattern, value, text, flags=flags)
        counts[kind] += n
    # Pytest local fixture repr includes session tokens, sometimes truncated.
    # Remove those local value lines, preserving source frames and exceptions.
    replace('fixture_auth_locals', r"(?m)^([^\n]*\b(?:fixture|f|tokens|auth|session|sessions|headers)\s*=\s*[^\n]*['\"]fixture-[abc]['\"]\s*:[^\n]*)$",
            '[REDACTED synthetic fixture authentication locals]')
    replace('fixture_token_dict_values', r"(['\"][^'\"\n]*(?:fixture|executor|specialist)[^'\"\n]*['\"]\s*:\s*)['\"][^'\"\n]*['\"]",
            r'\1"[REDACTED synthetic auth value]"')
    replace('opaque_quoted_fixture_values', r"(['\"])[A-Za-z0-9_-]{40,}\1",
            '"[REDACTED opaque fixture value]"')
    replace('bearer_credentials', r'(?i)(Bearer\s+)[A-Za-z0-9_.~+/=-]+', r'\1[REDACTED]')
    replace('password_values', r'(?i)(\bpassword\s*[=:]\s*)[^\s,;\'\"<>]+', r'\1[REDACTED]')
    replace('connection_uri', r'postgres(?:ql)?://[^\s\'\"<>]+', '[REDACTED local synthetic PG URI]')
    # Replace absolute execution paths with symbolic locations. They are not
    # claims that the exported file originally contained these symbolic paths.
    replace('repo_path', r'/workspace/ParkWeave/', '@repo/')
    replace('python_runtime_path', r'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/', '@python/')
    replace('temporary_path', r'/tmp/[^\s\'\"<>\)\],]+', '@tmp/[REDACTED]/')
    replace('other_absolute_execution_path', r'/(?:workspace|opt|home|root|usr|var)/[^\s\'\"<>\)\],]+', '@execution/[REDACTED]/')
    return text


def identity_results(tree):
    values=[]
    for t in tree.iter('testcase'):
        status = 'FAIL' if t.find('failure') is not None else 'ERROR' if t.find('error') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS'
        values.append((t.attrib.get('classname'),t.attrib.get('name'),t.attrib.get('time'),status))
    suites=[dict(s.attrib) for s in tree.iter('testsuite')]
    for s in suites:s.pop('hostname',None)
    return values,suites


def main():
    entries=[]
    # Include each raw JUnit and paired full stdout, including failed windows.
    # Collection stdout has no JUnit and is separately included.
    candidates=[]
    initial=OUTPUT/'archive-manifest-before-full.json'
    completed='exit_code' in json.loads((PRIVATE/'full-final-recheck-run.json').read_text())
    if initial.exists():
        # Freeze the exact original inputs: later reviewer diagnostics must not
        # silently become part of the already independently reviewed 59 files.
        for item in json.loads(initial.read_text())['artifacts']:
            p=ROOT/item['original_local_path']
            if p.suffix in ['.xml','.log']:
                candidates.append((p,'independent' if p.parent.name=='independent-review' else 'root'))
        if completed:
            candidates.extend((PRIVATE/('full-final-recheck.'+suffix),'root') for suffix in ['xml','log'])
    else:
        for directory,label in [(PRIVATE,'root'),(PRIVATE/'independent-review','independent')]:
            candidates.extend((p,label) for p in sorted(directory.glob('*.xml')))
            candidates.extend((p,label) for p in sorted(directory.glob('*.log'))
                              if p.name != 'full-final-recheck.log' or completed)
    for p,label in candidates:
        if p.name == 'full-final-recheck.xml' and 'exit_code' not in json.loads((PRIVATE/'full-final-recheck-run.json').read_text()):
            continue
        original=p.read_bytes();counts=Counter()
        target=OUTPUT/label/(p.stem+'.sanitized'+p.suffix)
        target.parent.mkdir(parents=True,exist_ok=True)
        if p.suffix=='.xml':
            tree=ET.fromstring(original);before=identity_results(tree)
            for s in tree.iter('testsuite'):
                if 'hostname' in s.attrib:s.set('hostname','synthetic-fixture-host');counts['hostname']+=1
            for element in tree.iter():
                if element.tag in ['failure','error','system-out','system-err','skipped']:
                    if element.text:element.text=scrub(element.text,counts)
                    for k in list(element.attrib):element.set(k,scrub(element.attrib[k],counts))
            assert identity_results(tree)==before,(p,'test identities/results altered')
            exported=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
            passed=Counter(status for _,_,_,status in before[0])
            outcomes=dict(passed)
        else:
            exported=scrub(original.decode(),counts).encode();outcomes=None
        payload_hash=sha(exported)
        payload_bytes=len(exported)
        compression=None
        if len(exported)>512_000:
            # Deterministic lossless gzip keeps large repetitive prior failure
            # windows reviewable without duplicating megabytes in the checkout.
            if target.exists():target.unlink()  # Only this script's prior export.
            target=target.with_suffix(target.suffix+'.gz')
            exported=gzip.compress(exported,mtime=0)
            compression='gzip'
        target.write_bytes(exported)
        entries.append(dict(original_local_path=str(p.relative_to(ROOT)),original_sha256=sha(original),
                            original_bytes=len(original),exported_path=str(target.relative_to(OUTPUT)),
                            exported_sha256=sha(exported),exported_bytes=len(exported),
                            compression=compression,sanitized_payload_sha256=payload_hash,
                            sanitized_payload_bytes=payload_bytes,
                            redactions=dict(counts),test_results_preserved=outcomes))
    # Both original and final source freezes are public, contain paths/hashes
    # only, and bind the old loaded tests separately from production bytes.
    for name in ['final-source-manifest.json','corrected-test-manifest.json','final-delivery-source-manifest.json']:
        data=(PRIVATE/name).read_bytes();(OUTPUT/name).write_bytes(data)
        entries.append(dict(original_local_path='.runtime/case-cancel/'+name,original_sha256=sha(data),
                            exported_path=name,exported_sha256=sha(data),redactions={}))
    manifest=dict(format='SANITIZED_COPY_WITH_ORIGINAL_HASH',raw_inputs_rewritten=False,
                  policy='Only execution paths, synthetic auth locals/values, opaque quoted fixture values, URI/password/Bearer values and hostnames are redacted. All testcase IDs/counts/status/durations retained. No failure converted to PASS.',
                  artifacts=entries)
    (OUTPUT/'archive-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'files':len(entries),'original_bytes':sum(e.get('original_bytes',0) for e in entries),
                      'exported_bytes':sum(e.get('exported_bytes',0) for e in entries)}))


if __name__=='__main__':main()
