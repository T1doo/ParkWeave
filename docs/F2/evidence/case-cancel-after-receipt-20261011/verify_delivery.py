"""Read-only source/archive/remote verification, writing only a new runtime record."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT/'.runtime/case-cancel-after-receipt'
PUBLIC = Path(__file__).resolve().parent
PROTECTED = {
    'main':'31e7acb7e53bb1ab6465b9daae59de28757f7583',
    'dev/f1-foundation':'b58cf201de3d6ca4e249bec3e8544ea53163807a',
    'dev/f2-resource-alternative-times-20261011':'e40bd24329ec21bd881ee7521e63e32a8ee3c13a',
    'dev/f2-case-cancel-before-accept-20261011':'396602aa4e4889cb32d6af89a2b32cc3e45b5029',
    'dev/f2-case-cancel-before-receipt-20261011':'189379b7f7c94dfacfff697ad06a4ea1a5780048',
}
BRANCH = 'dev/f2-case-cancel-after-receipt-20261011'


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()


def identity(tree):
    cases = [(c.attrib.get('classname'),c.attrib.get('name'),c.attrib.get('time'),
        'FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None
        else 'SKIP' if c.find('skipped') is not None else 'PASS') for c in tree.iter('testcase')]
    assert len(cases)==len({(c[0],c[1]) for c in cases}),'duplicate testcase ID'
    suites = [{k:v for k,v in s.attrib.items() if k!='hostname'} for s in tree.iter('testsuite')]
    return cases,suites


def main():
    after = '--after-push' in sys.argv
    target = OUT/('delivery-after-push-verification.json' if after else 'delivery-before-push-verification.json')
    assert not target.exists(),'never overwrite a prior actual audit'
    final = json.loads((OUT/'full-final-run.json').read_text())
    assert final['exit_code']==0 and not final['source_drift'] and not final['uncommitted_source']
    assert not final['prior_test_ids_missing'] and final['complete_module_count']==38
    head = git('rev-parse','HEAD').decode().strip()
    source = final['source_sha']
    manifest_bytes = (OUT/'final-source-manifest.json').read_bytes()
    assert sha(manifest_bytes)==final['source_manifest_sha256']
    manifest = json.loads(manifest_bytes)
    contract='docs/F2/CaseCancellationReconciliationContract.md'
    contract_sha='a2302d0f69dd20932d78cd21aa64099ddb9a19a273641d715eab61343930c9b4'
    assert sha((ROOT/contract).read_bytes())==contract_sha
    assert sha(git('show',source+':'+contract))==contract_sha
    assert sha(git('show',head+':'+contract))==contract_sha
    source_drift = []
    for path,h in manifest.items():
        for label, data in [('workspace',(ROOT/path).read_bytes()),('source_commit',git('show',source+':'+path)),('delivery_commit',git('show',head+':'+path))]:
            if sha(data)!=h:source_drift.append(dict(path=path,where=label))
    archive = json.loads((PUBLIC/'archive-manifest.json').read_text())
    archive_drift = []
    for item in archive['artifacts']:
        original = ROOT/item['original_local_path'];exported = PUBLIC/item['exported_path']
        for label,data,wanted in [('raw',original.read_bytes(),item['original_sha256']),('export',exported.read_bytes(),item['exported_sha256']),('delivery_commit',git('show',head+':'+str(exported.relative_to(ROOT))),item['exported_sha256'])]:
            if sha(data)!=wanted:archive_drift.append(dict(path=item['exported_path'],where=label))
        payload = gzip.decompress(exported.read_bytes()) if item['compression']=='gzip' else exported.read_bytes()
        assert sha(payload)==item['sanitized_payload_sha256']
        if original.suffix=='.xml':assert identity(ET.fromstring(original.read_bytes()))==identity(ET.fromstring(payload))
    support_path = PUBLIC/'audit-support-manifest.json'
    support = json.loads(support_path.read_bytes())
    assert support['frozen_archive_manifest_sha256']==sha((PUBLIC/'archive-manifest.json').read_bytes())
    assert git('show',head+':'+str(support_path.relative_to(ROOT)))==support_path.read_bytes()
    support_drift = []
    for item in support['artifacts']:
        original = ROOT/item['original_local_path'];exported = PUBLIC/item['exported_path']
        for label,data,wanted in [('raw',original.read_bytes(),item['original_sha256']),('export',exported.read_bytes(),item['exported_sha256']),('delivery_commit',git('show',head+':'+str(exported.relative_to(ROOT))),item['exported_sha256'])]:
            if sha(data)!=wanted:support_drift.append(dict(path=item['exported_path'],where=label))
    old = json.loads((OUT/'accepted-archive-byte-baseline.json').read_text())
    old_prefixes = sorted({str(Path(p).parents[0]) for p in old['files'] if Path(p).name=='README.md'})
    actual_old_paths = {str(p.relative_to(ROOT)) for prefix in old_prefixes for p in (ROOT/prefix).rglob('*') if p.is_file()}
    committed_old_paths = set(git('ls-tree','-r','--name-only',head,'--',*old_prefixes).decode().splitlines())
    old_inventory_drift = dict(added=sorted(actual_old_paths-set(old['files'])),missing=sorted(set(old['files'])-actual_old_paths),commit_added=sorted(committed_old_paths-set(old['files'])),commit_missing=sorted(set(old['files'])-committed_old_paths))
    old_drift = [p for p,h in old['files'].items() if sha((ROOT/p).read_bytes())!=h or sha(git('show',head+':'+p))!=h]
    assert git('remote','get-url','origin').decode().strip()=='https://github.com/T1doo/ParkWeave.git'
    raw_remote = git('ls-remote','--heads','origin',*PROTECTED,BRANCH).decode()
    remote = {ref.removeprefix('refs/heads/'):h for h,ref in (line.split() for line in raw_remote.splitlines())}
    protected_drift = {b:remote.get(b) for b,h in PROTECTED.items() if remote.get(b)!=h}
    branch = git('branch','--show-current').decode().strip()
    status = git('status','--porcelain').decode()
    divergence = git('rev-list','--left-right','--count',head+'...'+remote[BRANCH]).decode().strip() if BRANCH in remote else None
    for ancestor in [PROTECTED['dev/f2-resource-alternative-times-20261011'],PROTECTED['dev/f2-case-cancel-before-receipt-20261011'],source]:
        assert subprocess.call(['git','merge-base','--is-ancestor',ancestor,head],cwd=ROOT)==0
    record = dict(observed_utc=datetime.now(timezone.utc).isoformat(),mode='AFTER_PUSH' if after else 'BEFORE_PUSH',
        source_sha=source,delivery_sha=head,branch=branch,remote_heads=remote,remote_stdout=raw_remote,
        frozen_contract_sha256=contract_sha,source_file_count=len(manifest),source_manifest_sha256=sha(manifest_bytes),source_drift=source_drift,
        archive_artifact_count=len(archive['artifacts']),archive_manifest_sha256=sha((PUBLIC/'archive-manifest.json').read_bytes()),archive_drift=archive_drift,
        later_audit_support_artifact_count=len(support['artifacts']),later_audit_support_manifest_sha256=sha(support_path.read_bytes()),later_audit_support_drift=support_drift,
        accepted_old_archive_file_count=old['file_count'],accepted_old_archive_drift=old_drift,accepted_old_archive_inventory_drift=old_inventory_drift,
        protected_remote_drift=protected_drift,git_status_porcelain=status,
        actual_head_remote_divergence=divergence,browser_attempts=0,
        verification='PASS' if not any([source_drift,archive_drift,support_drift,old_drift,any(old_inventory_drift.values()),protected_drift,status]) and branch==BRANCH and (not after or (remote.get(BRANCH)==head and divergence=='0\t0')) else 'FAIL')
    target.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(record,indent=2))
    assert record['verification']=='PASS'


if __name__=='__main__':main()
