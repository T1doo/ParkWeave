from pathlib import Path
import hashlib,json
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018'
count=0
for line in (r/'inherited-evidence-blobs.txt').read_text().splitlines():
 meta,name=line.split('\t',1);expected=meta.split()[2];raw=(root/name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert actual==expected,name;count+=1
assert count==30651
(r/'inherited-evidence-verification.json').write_text(json.dumps(dict(baseline='2e3cc3023c42fcbacae1e8bef5a34e8061644d82',inherited_blobs=count,all_current_bytes_equal_baseline=True,changed=0,previous774_private_pairs_not_reaudited=True),indent=2)+'\n');print('30651 inherited evidence Git blobs match actual bytes')
