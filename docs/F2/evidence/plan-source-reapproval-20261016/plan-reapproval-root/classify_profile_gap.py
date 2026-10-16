"""Classify one unchanged original special-profile test without erasing FAIL."""
from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET
R=Path('.runtime/plan-reapproval-root');B=Path('.runtime/plan-reapproval-final');load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();f=load(R/'freeze.json');w=load(B/'extra-backend.json')
module='tests/test_case_pg_vertical_integration.py';identity=module+'::test_catalog_fix_and_case_cancellation_share_owned_database'
assert w['source_sha']==f['source_sha'] and w['counts']==dict(PASS=449,FAIL=1,ERROR=0,SKIP=0) and w['exit_code']==1
assert w['collection_junit_exact_match'] and w['unique_junit_nodes'] and not any(w[k] for k in ['source_drift','all_tracked_drift','runner_drift'])
failures=[c for c in ET.parse(B/'extra-backend.xml').iter('testcase') if c.find('failure') is not None];assert len(failures)==1
c=failures[0];assert c.attrib['classname']=='tests.test_case_pg_vertical_integration' and c.attrib['name']==identity.split('::')[1]
text=c.find('failure').text;assert 'psycopg.errors.UndefinedObject: role "pwci_writer" does not exist' in text and 'tests/test_case_pg_vertical_integration.py:24' in text
assert [n for n in w['collected_nodes'] if n.startswith(module+'::')]==[identity]
paths=[module,'tests/conftest.py','scripts/case_pg_vertical/probe.py','scripts/case_pg_vertical/owned_pg.py','scripts/case_pg_vertical/bootstrap.py','scripts/case_pg_vertical/selection.json','scripts/case_pg_vertical/approval.json']
sources={}
for p in paths:
 raw=Path(p).read_bytes();assert subprocess.check_output(['git','show','a794a1802e15100d691a969f0813aa371d707c36:'+p])==raw
 assert hashlib.sha256(raw).hexdigest()==f['source_paths'][p];sources[p]=sha(Path(p))
original=load(Path('scripts/case_pg_vertical/selection.json'));assert len(original)==27 and sum(x['nodeid']==identity for x in original)==1
v=dict(status='LIMITED_PASS_WITH_PROFILE_GAP',source_sha=f['source_sha'],excluded_modules=[module],ordinary_profile=dict(window='extra-backend',identity=identity,outcome='FAIL',failure='psycopg.errors.UndefinedObject: role "pwci_writer" does not exist',line=24,raw_failure_retained=True),specialized_profile=dict(outcome='NOT_RUN',complete_selection=27,reason='Original exact once hosted/branch/approval-only entry is inapplicable here. Normal pgserver fixture has no original OwnedPG writer role/root/socket identity. No role creation, gate override, approval edit or dedicated profile execution performed.'),original_protocol_sources_unchanged=sources,evidence_sha256={str(p):sha(p) for p in [B/'extra-backend.json',B/'extra-backend.xml',B/'extra-backend-collection.json']},scope='One complete single-test unchanged module excluded from passing denominator; never rewrite actual FAIL as SKIP/NOT_RUN. Initial frozen134/3643 plan remains. All remaining modules and new54 must independently pass.')
(R/'profile-gap.json').write_text(json.dumps(v,indent=2)+'\n');print(v['status'],identity)
