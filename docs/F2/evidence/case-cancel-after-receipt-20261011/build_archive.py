"""Reproducibly export this slice's raw evidence; never rewrite private inputs."""
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
PRIVATE = ROOT / '.runtime/case-cancel-after-receipt'
OUTPUT = Path(__file__).resolve().parent
policy_path = OUTPUT.parent / 'case-cancel-before-accept-20261011/build_archive.py'
# Reading the previous accepted policy must not add even ignored cache files
# to its immutable evidence directory.
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('accepted_evidence_policy', policy_path)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metadata_scrub(value, counts):
    # Hashes and testcase IDs in JSON must remain literal, not be mistaken for
    # opaque authentication values by the stdout fixture-repr redaction rule.
    if isinstance(value, dict):
        return {k: metadata_scrub(v, counts) for k, v in value.items()}
    if isinstance(value, list):
        return [metadata_scrub(v, counts) for v in value]
    if isinstance(value, str):
        original = value
        value = value.replace('/workspace/ParkWeave', '@repo')
        value = re.sub(r'/tmp/[^\s\"<>\),]+', '@tmp/[REDACTED]/', value)
        value = re.sub(r'postgres(?:ql)?://[^\s\"<>]+', '[REDACTED local synthetic PG URI]', value)
        value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_.~+/=-]+', r'\1[REDACTED]', value)
        if value != original:
            counts['metadata_execution_path_or_credentials'] += 1
        return value
    return value


def main():
    final = json.loads((PRIVATE / 'full-final-run.json').read_text())
    assert final['exit_code']==0 and not final['source_drift'] and not final['uncommitted_source'] and not final['prior_test_ids_missing'], 'require actual frozen final full PASS'
    names = [n for n in ['first','second','third','fourth','fifth','sixth','schema-oracles','schema-oracles-corrected','full-attempt-1','full-final'] if (PRIVATE/(n+'.xml')).exists()]
    candidates = [(PRIVATE / (name + suffix), 'root')
                  for name in names for suffix in ['.xml', '.log']]
    candidates += [(p,'') for p in sorted(PRIVATE.glob('*.json')) if p.name.endswith('-run.json') or p.name.endswith('-source-manifest.json') or p.name in ['node-and-ast.json','final-source-manifest.json','final-node-and-ast.json','source-freeze-node-and-ast.json']]
    candidates += [(p,'root') for p in sorted(PRIVATE.glob('run_window*.py'))]
    candidates += [(p,'root/schema-oracle-before') for p in sorted((PRIVATE/'schema-oracle-before').glob('*')) if p.suffix in ['.py','.json']]
    review = PRIVATE / 'independent-review'
    candidates += [(p, str(Path('independent') / p.relative_to(review).parent))
                   for p in sorted(review.rglob('*'))
                   if p.is_file() and p.suffix in ['.xml', '.log', '.json', '.md', '.py', '.txt', '.js']
                   and '__pycache__' not in p.parts]
    prior_manifest=OUTPUT/'archive-manifest.json'
    if prior_manifest.exists():
        candidates=[(ROOT/e['original_local_path'],str(Path(e['exported_path']).parent)) for e in json.loads(prior_manifest.read_text())['artifacts']]
        candidates=[(p,'' if label=='.' else label) for p,label in candidates]
    entries = []
    for p, label in candidates:
        original = p.read_bytes()
        counts = Counter()
        outcomes = None
        if p.suffix == '.xml':
            tree = ET.fromstring(original)
            before = policy.identity_results(tree)
            for suite in tree.iter('testsuite'):
                if 'hostname' in suite.attrib:
                    suite.set('hostname', 'synthetic-fixture-host')
                    counts['hostname'] += 1
            for element in tree.iter():
                if element.tag in ['failure', 'error', 'system-out', 'system-err', 'skipped']:
                    if element.text:
                        element.text = policy.scrub(element.text, counts)
                    for k in list(element.attrib):
                        element.set(k, policy.scrub(element.attrib[k], counts))
            assert policy.identity_results(tree) == before, (p, 'test result changed')
            exported = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
            outcomes = dict(Counter(status for _, _, _, status in before[0]))
        elif p.suffix == '.json':
            exported = (json.dumps(metadata_scrub(json.loads(original), counts),
                                   indent=2, sort_keys=True) + '\n').encode()
        elif p.suffix in ['.py','.js'] or 'frozen-' in p.name or p.name.endswith('.py.txt'):
            # Static reviewer/helper code contains no runtime authentication
            # values. Preserve its original bytes, including long scope names.
            exported = original
        else:
            exported = policy.scrub(original.decode(), counts).encode()
        target = OUTPUT / label / (p.stem + '.sanitized' + p.suffix)
        if not label:
            target = OUTPUT / p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload_hash, payload_bytes = sha(exported), len(exported)
        compression = None
        if len(exported) > 512_000:
            target = target.with_suffix(target.suffix + '.gz')
            exported = gzip.compress(exported, mtime=0)
            compression = 'gzip'
        target.write_bytes(exported)
        entries.append(dict(original_local_path=str(p.relative_to(ROOT)),
                            original_sha256=sha(original), original_bytes=len(original),
                            exported_path=str(target.relative_to(OUTPUT)),
                            exported_sha256=sha(exported), exported_bytes=len(exported),
                            sanitized_payload_sha256=payload_hash,
                            sanitized_payload_bytes=payload_bytes, compression=compression,
                            redactions=dict(counts), test_results_preserved=outcomes))
    manifest = dict(format='SANITIZED_COPY_WITH_ORIGINAL_HASH',
                    raw_inputs_rewritten=False, source_sha=final['source_sha'],source_manifest_sha256=final['source_manifest_sha256'],
                    policy_source_sha256=sha(policy_path.read_bytes()),
                    policy='Previous accepted stdout/JUnit redaction policy; JSON retains literal hashes and test IDs while replacing execution paths and URI/Bearer credentials. Static helper/probe/source snapshot code is copied byte-for-byte and contains no runtime credentials. Testcase IDs, counts, outcomes and durations preserved. Failed windows remain failed.',
                    artifacts=entries)
    (OUTPUT / 'archive-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(files=len(entries), original_bytes=sum(e['original_bytes'] for e in entries),
                         exported_bytes=sum(e['exported_bytes'] for e in entries))))


if __name__ == '__main__':
    main()
