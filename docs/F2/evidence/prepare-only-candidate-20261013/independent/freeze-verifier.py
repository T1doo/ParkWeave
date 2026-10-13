"""Read-only frozen-source and stored-result verification; no actual test run."""
import pathlib,json,hashlib,subprocess,xml.etree.ElementTree as ET
r=pathlib.Path('/workspace/ParkWeave');e=r/'.runtime/prepare-only-candidate-20261013';o=e/'independent';v=json.loads((o/'review-result.json').read_bytes());sha='b821729a79db4bb36c1bfd38fd79caf46eab2a25';h=lambda b:hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=r,stderr=subprocess.PIPE)
src=[]
for x in v['source_hashes']:
 b=git('show',sha+':'+x['path']);assert b==(r/x['path']).read_bytes()
 if h(b)!=x['sha256']:
  assert x['path']=='scripts/host_case_once/prepare_once.py'
  old=b.replace(b'# Gate may spawn read-only Git; no timer, claim, directory or effectful child before approval.',b'# No signal, claim, directory, subprocess or network effects before gate.')
  assert h(old)==x['sha256']
 src.append(dict(path=x['path'],bytes=len(b),sha256=h(b),git_blob=git('rev-parse',sha+':'+x['path']).decode().strip()))
doc='docs/F2/PrepareOnlyTrialApproval-20261013.md';b=git('show',sha+':'+doc);assert b==(r/doc).read_bytes();src.append(dict(path=doc,bytes=len(b),sha256=h(b),git_blob=git('rev-parse',sha+':'+doc).decode().strip()));t=b.decode();assert '最后timer复位失败' in t and 'FILES_REMOVED=PASS和cleanup=true' in t and '固定`PREPARE_IMPORTS_PASS`加一个LF换行字节' in t
for name in ['scripts/host_case_once/approval.json','scripts/host_case_once/prepare_approval.json']:assert json.loads(git('show',sha+':'+name))==dict(approved=False,source_sha=None,approval_ref=None)
xmls=[]
for file,passed,failed in [('root-reviewed.xml',255,0),('root-second.xml',246,1),('root-first.xml',0,0),('independent/reviewed-pure.xml',58,0)]:
 x=ET.parse(e/file).getroot();tests=list(x.iter('testcase'));fail=len(list(x.iter('failure')));err=len(list(x.iter('error')));skip=len(list(x.iter('skipped')));assert len(tests)==passed+failed and fail==failed and err==0 and skip==0;xmls.append(dict(file=file,PASS=passed,FAIL=fail,ERROR=err,SKIP=skip,qualification='Stored original XML only; first zero tests is command failure, not PASS.'))
refs={'refs/remotes/origin/main':'31e7acb7e53bb1ab6465b9daae59de28757f7583','dev/f2-host-case-security-once-20261013':'9a5808b01b807712d272c6180990cc2e3969b1d7','dev/f2-host-case-once-candidate-20261013':'6aa12c75461994bfff5e16dc6a169877808ad908','dev/f2-host-case-actual-report-20261013':'e06311dca0c6133fa807a6cbc8b40597a22202c9','dev/f2-host-case-bootstrap-diagnostics-20261013':'8de739c9c0505fee43d8766047e2653a4ad2361f'}
seen=[]
for name,expected in refs.items():
 actual=git('rev-parse',name).decode().strip();assert actual==expected;seen.append(dict(ref=name,sha=actual,scope='LOCAL_REF_READ_ONLY_NO_NETWORK'))
(o/'checklist-correction.json').write_text(json.dumps(dict(issue='All-failures-retain-T wording overlooked timer reset failure after confirmed deletion.',resolution='Checklist distinguishes pre-deletion failures and post-deletion timer failure: overall FAIL with truthful FILES_REMOVED PASS/cleanuptrue and logs UNAVAILABLE. Marker is text plus LF.',document_sha256=h(b),fixed_commit=sha),indent=2)+'\n')
f=o/'frozen-source-check.json';f.write_text(json.dumps(dict(conclusion='PASS_FROZEN_PREPARE_ONLY_CANDIDATE_AND_CORRECTED_CHECKLIST',source_sha=sha,prior_code_commit='b01f75d3b97b57687a75667c708598d8368fc88d',paths=src,checks='Seven paths current/Git bytes match; previous reviewed bindings match except verified comment-only run change; exact new checklist reviewed.',xml_windows=xmls,pending_both_approvals=True,local_refs=seen,unavailable_refs='F1/F2 have no local ref; remote NOT_CHECKED here because this audit prohibits network. Root must verify remote.',limited_pure=dict(root=255,independent=58,overlap=48,not_additive=True),limitations='No retest/network/CI/security action. New actual preparation NOT_RUN; old actual failure unchanged/private cause UNKNOWN; old authorization spent.'),ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in e.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.name not in ('final-safe-copy-list.json','archive-review.json'));s=o/'final-safe-copy-list.json';s.write_text(json.dumps(dict(conclusion='SAFE_PURE_SYNTHETIC_AND_READ_ONLY_REVIEW_ORIGINALS',files=[dict(path=p.relative_to(r).as_posix(),archive_path=p.relative_to(e).as_posix(),bytes=p.stat().st_size,sha256=h(p.read_bytes())) for p in files],self_rule='Copy separately; no recursive self hash. Includes root first zero-test command failure and second 246PASS/1FAIL allowlist error.'),indent=2)+'\n');print(json.dumps(dict(source_sha=sha,freeze_sha256=h(f.read_bytes()),safe_list_sha256=h(s.read_bytes()),files=len(files))))
