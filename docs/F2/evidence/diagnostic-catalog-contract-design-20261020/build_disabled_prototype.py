"""Offline design bytes only. Never writes the active catalog or any consumer."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from scripts.windows_ci.diagnostic_catalog import _source


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))+'\n').encode('ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    ownership = json.loads((HERE/'domain-ownership-and-source.json').read_bytes())
    proposal = json.loads((HERE/'proposal.json').read_bytes())
    ids, snapshot = _source(ROOT)
    if snapshot != ownership['source_sha256'] or set(snapshot) != set(ownership['file_to_domain']):
        raise ValueError('design source snapshot changed')
    grouped = defaultdict(list)
    for identity in ids:
        grouped[ownership['file_to_domain'][identity.split('::', 1)[0]]].append(identity)
    payloads, records = {}, []
    for domain, identities in sorted(grouped.items()):
        files = sorted(f for f in snapshot if ownership['file_to_domain'][f] == domain)
        chunks = []
        for name in files:
            chunks.append(encoded({'file': name, 'sha256': snapshot[name]}))
            chunks.extend(encoded({'id': i}) for i in identities if i.split('::', 1)[0] == name)
        raw = b''.join(chunks)
        records.append(dict(domain=domain, test_ids=len(identities), file_records=len(files),
                            record_budget=len(identities)+len(files), bytes=len(raw),
                            sha256=hashlib.sha256(raw).hexdigest()))
        payloads[domain+'.jsonl'] = raw
    if records != proposal['minimal_candidate_not_enabled']['stable_domains']:
        raise ValueError('prototype byte accounting differs from reviewed proposal')
    index = dict(schema=2, status='DISABLED_DESIGN_PROTOTYPE', routing_version=1,
                 source_files=len(snapshot),
                 source_binding_sha256=hashlib.sha256(encoded(ownership)).hexdigest(),
                 domains=records)
    payloads['index.json'] = encoded(index)
    if len(payloads['index.json']) > 8192:
        raise ValueError('prototype index byte allowance exceeded')
    args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, raw in payloads.items():
        with (args.out/name).open('xb') as stream:
            stream.write(raw)
    print(json.dumps(dict(status='DISABLED_DESIGN_PROTOTYPE_ONLY', domains=len(records),
                          index_bytes=len(payloads['index.json']),
                          total_catalog_bytes=sum(map(len, payloads.values())),
                          index_sha256=hashlib.sha256(payloads['index.json']).hexdigest()), sort_keys=True))


if __name__ == '__main__':
    main()
