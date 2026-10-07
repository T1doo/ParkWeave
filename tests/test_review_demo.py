"""Sealed review evidence and owned local clean-start lifecycle."""
from pathlib import Path
import hashlib,json,os,socket,subprocess,sys
import pytest
from fastapi.testclient import TestClient
from parkweave.review_demo import ReviewEvidence,create_review_app,SOURCE_FILES
from parkweave.process_env import minimal_environment
from scripts.review_demo import initialize_state,reserve_report,ROOT,OBJECTS
from scripts.review_demo_factories import NAMESPACE,rules_app,access_app

def test_review_path_is_readonly_distinct_historical_synthetic_sources():
    api=TestClient(create_review_app(ROOT));x=api.get('/api/review/path').json()
    assert len(x['stages'])==6 and all(s['state']=='VERIFIED_COMMITTED_EVIDENCE' for s in x['stages'])
    cases={s['case_id'] for s in x['stages'] if s['case_id']!='NOT_RECORDED'};assert len(cases)>=3
    assert all(not s['same_case_chain'] and s['current_product_state']=='NOT_READ' for s in x['stages'])
    assert not x['isolated_mock_enabled'] and not x['product_state_written'] and not x['current_product_database_connected']
    assert len(x['original_plan_gaps'])==7 and 'Mock' in api.get('/').text
    assert api.post('/api/review/path',json={'approved':True}).status_code==405
    assert api.get('/api/review/source/not-registered').status_code==404

def test_unavailable_changed_symlink_and_extra_payload_never_become_evidence(tmp_path):
    evidence=ReviewEvidence(tmp_path);assert evidence.source('request')['state']=='UNAVAILABLE'
    folder=tmp_path/'docs/F2/evidence';folder.mkdir(parents=True);source=folder/SOURCE_FILES['request'];original=(ROOT/'docs/F2/evidence'/SOURCE_FILES['request']).read_bytes();source.write_bytes(original)
    assert evidence.source('request')['state']=='VERIFIED_COMMITTED_EVIDENCE'
    payload=json.loads(original);payload['token']='SECRET_MUST_NOT_BE_EXPOSED';payload['browser']['case_id']='SECRET_MUST_NOT_BE_EXPOSED';source.write_text(json.dumps(payload))
    assert evidence.source('request')['state']=='SOURCE_CHANGED_REVALIDATION_REQUIRED'
    # Even a trusted test override of the seal cannot expose unprojected raw fields.
    evidence.seals['request']=hashlib.sha256(source.read_bytes()).hexdigest();x=evidence.source('request');assert x['case_id']=='NOT_RECORDED' and 'SECRET_MUST_NOT_BE_EXPOSED' not in json.dumps(x)
    source.unlink();source.symlink_to(ROOT/'docs/F2/evidence'/SOURCE_FILES['request']);assert evidence.source('request')['state']=='UNAVAILABLE'
    with pytest.raises(KeyError):evidence.source('../../private')

def test_mock_factories_default_closed_and_exact_one_run(tmp_path,monkeypatch):
    monkeypatch.delenv('PARKWEAVE_REVIEW_MODE',raising=False);monkeypatch.setenv('PARKWEAVE_REVIEW_INSTANCE','non-secret-test-instance');monkeypatch.setenv('PARKWEAVE_REVIEW_STATE',str(tmp_path))
    assert not TestClient(rules_app()).get('/api/candidate/status').json()['candidate_demo']
    assert not TestClient(access_app()).get('/api/run-access/status').json()['candidate_demo'];assert list(tmp_path.iterdir())==[]
    monkeypatch.setenv('PARKWEAVE_REVIEW_MODE',NAMESPACE)
    rule=TestClient(rules_app());access=TestClient(access_app());assert rule.get('/api/candidate/status').json()['candidate_demo'] and access.get('/api/run-access/status').json()['candidate_demo']
    assert access.get('/api/run-access/park-a/org-a/mock-run-b',headers={'X-Mock-Actor':'mock-run-owner'}).status_code==403
    assert sorted(p.name for p in tmp_path.iterdir())==['access.run-access.candidate.sqlite3','rules.candidate.sqlite3']

def test_dedicated_state_resume_foreign_directory_and_symlink_are_safe(tmp_path):
    state=tmp_path/'owned';initialize_state(state);marker=json.loads((state/'review-demo.json').read_text());assert marker['objects']==OBJECTS and not marker['actual_permissions_enabled'];assert initialize_state(state)==state
    foreign=tmp_path/'foreign';foreign.mkdir();keep=foreign/'legacy';keep.write_bytes(b'KEEP')
    with pytest.raises(ValueError):initialize_state(foreign)
    assert keep.read_bytes()==b'KEEP' and list(foreign.iterdir())==[keep]
    symlink=tmp_path/'link';symlink.symlink_to(state,target_is_directory=True)
    with pytest.raises(ValueError):initialize_state(symlink)

def ports():
    for base in range(19100,19300,3):
        bound=[]
        try:
            for p in range(base,base+3):
                s=socket.socket();s.bind(('127.0.0.1',p));bound.append(s)
            return base
        except OSError:continue
        finally:
            for s in bound:s.close()
    raise RuntimeError('test ports unavailable')

@pytest.mark.parametrize('mock',[False,True])
def test_clean_start_repeat_resume_and_owned_cleanup_without_product_credentials(tmp_path,mock):
    port=ports();report=tmp_path/'report.json';state=tmp_path/'candidate-state';env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src')+':'+str(ROOT));command=[sys.executable,str(ROOT/'scripts/review_demo.py'),'--check-startup','--base-port',str(port),'--report',str(report)]
    if mock:command+=['--isolated-mock','--state-dir',str(state)]
    for _ in range(2):
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=35);assert result.returncode==0,result.stderr
        x=json.loads(report.read_text());assert x['ready'] and len(x['cleanup'])==3 and not x['credentials_created'] and not x['actual_permissions_enabled']
        assert not x['current_product_database_connected'] and x['isolated_mock_enabled']==mock
        for p in range(port,port+3):
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',p))
    if mock:assert sorted(p.name for p in state.iterdir())==['access.run-access.candidate.sqlite3','review-demo.json','rules.candidate.sqlite3']
    else:assert not state.exists()

def test_busy_port_does_not_kill_or_reuse_unowned_server(tmp_path):
    port=ports();report=tmp_path/'busy.json'
    with socket.socket() as owned:
        owned.bind(('127.0.0.1',port));owned.listen()
        result=subprocess.run([sys.executable,str(ROOT/'scripts/review_demo.py'),'--check-startup','--base-port',str(port),'--report',str(report)],cwd=ROOT,env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src')+':'+str(ROOT)),capture_output=True,text=True,timeout=10)
        assert result.returncode==1 and owned.fileno()!=-1
    x=json.loads(report.read_text());assert not x['ready'] and x['owned_children']==[] and x['cleanup']==[]

def test_report_destination_refuses_foreign_and_symlink_without_overwrite(tmp_path):
    foreign=tmp_path/'foreign.json';foreign.write_bytes(b'KEEP')
    with pytest.raises(ValueError):reserve_report(foreign)
    assert foreign.read_bytes()==b'KEEP'
    owned=tmp_path/'owned.json';reserve_report(owned);assert reserve_report(owned)==owned
    link=tmp_path/'link.json';link.symlink_to(owned)
    with pytest.raises(ValueError):reserve_report(link)
