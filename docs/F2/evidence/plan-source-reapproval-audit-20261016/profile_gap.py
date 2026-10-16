"""One explicit original dedicated-profile gap; never infer other exclusions."""
from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave')
OWN=Path(__file__).resolve().parent
MODULE='tests/test_case_pg_vertical_integration.py'
NODE=MODULE+'::test_catalog_fix_and_case_cancellation_share_owned_database'
SPEC=dict(module=MODULE,original_window='extra-backend',ordinary_outcome='FAIL',special_profile_outcome='NOT_RUN',special_profile_items=27)
STATUS='LIMITED_PASS_WITH_PROFILE_GAP'
V1_SOURCE='929d4f7a13c0b074e8340dad21f4460c7ddacd23'
TEST_FIXES={'tests/test_case_resource_delivery_browser.py','tests/test_new_enterprise_local_chain_browser.py'}
PRODUCT_FILES={'src/parkweave/'+n for n in ('api.py','case_resource_delivery.py','case_resources.py','resource_plan_binding.py','service_plan_approval.py','web.html')}

def check(config,ready,freeze,window):
    assert config['profile_gap']==ready['profile_gap']==SPEC
    assert len(config['original_profile_evidence_sha256'])==11
    for p,h in config['original_profile_evidence_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    assert ready['regression_status']==STATUS
    original_freeze=json.loads((ROOT/config['original_freeze']).read_text())
    assert original_freeze['source_sha']==V1_SOURCE
    assert original_freeze['expected_main_modules']==134 and original_freeze['expected_main_tests']==3643
    assert freeze['source_sha']!=V1_SOURCE and freeze['expected_main_modules']==133 and freeze['expected_main_tests']==3642
    before=json.loads((ROOT/config['original_selection']).read_text())
    after=json.loads((ROOT/config['selection']).read_text())
    old_modules=[m for row in before['main_windows'].values() for m in row]
    new_modules=[m for row in after['main_windows'].values() for m in row]
    assert len(old_modules)==len(set(old_modules))==134 and len(new_modules)==len(set(new_modules))==133
    assert set(old_modules)-set(new_modules)=={MODULE} and not set(new_modules)-set(old_modules)
    assert before['separate_ci_window']==after['separate_ci_window']
    diff=subprocess.check_output(['git','diff','--name-only',V1_SOURCE,freeze['source_sha']],cwd=ROOT,timeout=10).decode().splitlines()
    assert len(diff)==2 and set(diff)==TEST_FIXES
    for p in PRODUCT_FILES:assert original_freeze['source_paths'][p]==freeze['source_paths'][p]
    record,nodes=window(Path(config['original_formal_base']),'extra-backend',original_freeze)
    assert record['exit_code']==1 and record['counts']==dict(PASS=449,FAIL=1,ERROR=0,SKIP=0)
    assert len(record['modules'])==len(set(record['modules']))==19
    assert len(nodes)==450 and nodes.get(NODE)=='FAIL'
    assert {n:s for n,s in nodes.items() if s!='PASS'}=={NODE:'FAIL'}
    assert {n for n in nodes if n.split('::',1)[0]==MODULE}=={NODE}
    xml=ROOT/config['original_formal_base']/'extra-backend.xml'
    failures=[c for c in ET.parse(xml).iter('testcase') if c.find('failure') is not None]
    assert len(failures)==1 and failures[0].get('name')==NODE.split('::')[1]
    text=''.join(failures[0].find('failure').itertext())
    log=(ROOT/config['original_formal_base']/'extra-backend.log').read_text()
    for s in ('psycopg.errors.UndefinedObject: role "pwci_writer" does not exist',"GRANT USAGE ON SCHEMA public TO pwci_writer"):
        assert s in text and s in log
    assert 'tests/test_case_pg_vertical_integration.py:24' in text
    assert 'pgserver.postgres_server.PostgresServer' in log
    original=json.loads((OWN/'profile-applicability/static-applicability-v1.json').read_text())
    assert len(original['source_sha256'])==7
    for path,h in original['source_sha256'].items():
        raw=(ROOT/path).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==h==freeze['source_paths'][path]==original_freeze['source_paths'][path]
        old=subprocess.check_output(['git','show','a794a1802e15100d691a969f0813aa371d707c36:'+path],cwd=ROOT,timeout=10)
        assert raw==old
    selection=json.loads((ROOT/'scripts/case_pg_vertical/selection.json').read_text())
    assert len(selection)==27 and sum(row['nodeid']==NODE for row in selection)==1
    return dict(status=STATUS,initial_modules=134,initial_items=3643,qualified_modules=133,qualified_passes=3642,current_source_sha=freeze['source_sha'],plan_revision=config['plan_revision'],source_diff_exact=sorted(TEST_FIXES),product_source_unchanged=sorted(PRODUCT_FILES),ordinary_profile_failure=dict(source_sha=V1_SOURCE,node=NODE,window='extra-backend',outcome='FAIL',reason='UndefinedObject: role "pwci_writer" does not exist',full_window_counts=record['counts']),dedicated_profile=dict(outcome='NOT_RUN',original_selection_items=27),unchanged_original_sources=original['source_sha256'],initial_freeze_preserved=True,other_failures_allowed=False)
