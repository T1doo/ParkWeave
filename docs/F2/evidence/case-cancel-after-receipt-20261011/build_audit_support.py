"""Export later audit support separately from the frozen 249 evidence inputs."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PUBLIC = Path(__file__).resolve().parent
ROOT = PUBLIC.parents[3]
PRIVATE = ROOT / '.runtime/case-cancel-after-receipt'
spec = importlib.util.spec_from_file_location('slice_archive_policy', PUBLIC / 'build_archive.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def main():
    target_manifest = PUBLIC / 'audit-support-manifest.json'
    frozen = (PUBLIC / 'archive-manifest.json').read_bytes()
    if target_manifest.exists():
        inputs = json.loads(target_manifest.read_bytes())['artifacts']
    else:
        inputs = json.loads((PRIVATE / 'audit-support-inputs.json').read_bytes())
    entries = []
    for item in inputs:
        original_path = ROOT / item['original_local_path']
        assert original_path.resolve().is_relative_to(PRIVATE.resolve())
        original = original_path.read_bytes()
        assert policy.sha(original) == item['original_sha256']
        counts = Counter()
        if original_path.suffix == '.py':
            assert item['classification'] == 'STATIC_CODE_EXACT_CONTENT_REVIEW'
            exported = original
        elif original_path.suffix == '.json':
            value = json.loads(original)
            policy.check_json_credentials(value)
            exported = (json.dumps(policy.metadata_scrub(value, counts), indent=2, sort_keys=True) + '\n').encode()
        else:
            assert original_path.suffix in ['.md', '.log']
            exported = policy.policy.scrub(original.decode(), counts).encode()
        destination = PUBLIC / item['exported_path']
        assert destination.resolve().is_relative_to(PUBLIC.resolve())
        if target_manifest.exists():
            assert policy.sha(exported) == item['exported_sha256']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(exported)
        entries.append(dict(original_local_path=item['original_local_path'],
                            original_sha256=policy.sha(original), original_bytes=len(original),
                            exported_path=item['exported_path'], exported_sha256=policy.sha(exported),
                            exported_bytes=len(exported), classification=item['classification'],
                            redactions=dict(counts)))
    record = dict(scope='LATER_AUDIT_SUPPORT_OUTSIDE_FROZEN_249', raw_inputs_rewritten=False,
                  frozen_archive_manifest_sha256=policy.sha(frozen),
                  policy='Same accepted stdout/report policy and literal-hash-preserving JSON policy. Three audit programs independently inspected and pinned by exact input SHA; copied unchanged.',
                  artifacts=entries)
    target_manifest.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    assert (PUBLIC / 'archive-manifest.json').read_bytes() == frozen
    print(json.dumps(dict(support_artifacts=len(entries), frozen249_unchanged=True)))


if __name__ == '__main__':
    main()
