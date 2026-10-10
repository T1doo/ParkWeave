"""Independent narrow real-HTTP proof and executable-registration oracles."""
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import hashlib,json,sqlite3
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture
from test_isolated_execution_preview import setup,body,execute,read,snapshot
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import preparation as prep,bounded_planning as planning

PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-isolated-execution-preview-v2-review')
@pytest.fixture
def actual(preparation_fixture):
    f=preparation_fixture
    with actual_http(create_app(f[0])) as (client,requests):
        yield f[:3]+(client,)

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def record(name,value):
    (PRIVATE_EVIDENCE/(name+'-safe-evidence.json')).write_text(json.dumps(value,indent=2)+'\n')

@pytest.mark.parametrize('damage',['required_goals','coverage_omission','coherent_omission'])
def test_independent_original_goal_anchor(actual,tmp_path,damage):
    f=actual;goals=['LOCAL_MATERIAL_PREPARATION','SYNTHETIC unsupported original mandatory goal']
    p,engine=setup(f,tmp_path,goals=goals);b=body(f,p);key=uuid4().hex
    first=execute(f,p,b,key);assert first.status_code==201
    original=first.json()['result'];altered=deepcopy(original)
    assert original['required_goals']==goals and len(original['goal_coverage'])==2
    if damage=='required_goals':altered['required_goals']=[]
    elif damage=='coverage_omission':altered['goal_coverage']=altered['goal_coverage'][:1]
    else:
        altered['required_goals']=goals[:1];altered['goal_coverage']=altered['goal_coverage'][:1]
        altered['coverage_state']='P1_PREVIEW_ONLY'
    altered['sha256']=digest({k:v for k,v in altered.items() if k!='sha256'})
    with sqlite3.connect(engine.path) as c:
        anchor=c.execute('SELECT owner,preparation,request_key,fingerprint FROM previews').fetchone()
        trigger=c.execute("SELECT sql FROM sqlite_master WHERE name='immutable_update'").fetchone()[0]
        c.execute('DROP TRIGGER immutable_update');c.execute('UPDATE previews SET document=?',(prep.canonical(altered),));c.execute(trigger);c.commit()
        assert anchor==c.execute('SELECT owner,preparation,request_key,fingerprint FROM previews').fetchone()
    before=snapshot(f);bytes_before=engine.path.read_bytes()
    responses=[read(f,p),read(f,p,key),execute(f,p,b,key)]
    codes=[r.status_code for r in responses]
    evidence=dict(oracle='original_complete_goal_binding_requires_rejection',damage=damage,status_codes=codes,
        original_goals_count=len(goals),altered_goals_count=len(altered['required_goals']),original_body_anchor_unchanged=True,
        original_row_anchors_unchanged=True,schema_triggers_restored=True,
        source_sha256=original['binding']['source_sha256'],original_document_sha256=original['sha256'],altered_document_sha256=altered['sha256'],
        public_values_unchanged=snapshot(f)==before,sqlite_bytes_unchanged=engine.path.read_bytes()==bytes_before,
        actual_http=True,model_calls=0)
    if codes[0]==200:evidence['source_state_returned']=responses[0].json()['history'][0]['source_state']
    record('goal-'+damage,evidence)
    assert evidence['public_values_unchanged'] and evidence['sqlite_bytes_unchanged']
    assert codes==[409,409,409]

@pytest.mark.parametrize('change',['method','path','commands'])
def test_independent_executable_registration_identity(actual,tmp_path,monkeypatch,change):
    f=actual;p,engine=setup(f,tmp_path);registry_before=deepcopy(planning.REGISTRY);trusted_before=deepcopy(planning.TRUSTED)
    actions=deepcopy(planning.ACTIONS)
    actions['P1'][0][change]={'method':'DELETE','path':'/api/preparations/{preparation_id}/unregistered-command','commands':['REOPEN']}[change]
    monkeypatch.setattr(planning,'ACTIONS',actions)
    b=body(f,p);before=snapshot(f);calls=[];command=prep.command
    def observed(store,token,id,key,data):
        calls.append(data.action);return command(store,token,id,key,data)
    monkeypatch.setattr(prep,'command',observed)
    view=read(f,p);response=execute(f,p,b)
    with sqlite3.connect(engine.path) as c:count=c.execute('SELECT count(*) FROM previews').fetchone()[0]
    evidence=dict(oracle='drifted_executable_actions_must_not_execute_original_adapter',change=change,
        get_status=view.status_code,post_status=response.status_code,preview_rows=count,executed_actions=calls,
        original_registry_unchanged=planning.REGISTRY==registry_before,original_trusted_unchanged=planning.TRUSTED==trusted_before,
        public_values_unchanged=snapshot(f)==before,actual_http=True,model_calls=0,technical_runtime_configuration_probe=True)
    if view.status_code==200:evidence['execution_available']=view.json()['execution_available']
    if response.status_code==201:evidence['actual_result_state']=response.json()['result']['state']
    record('action-'+change,evidence)
    assert evidence['public_values_unchanged'] and evidence['original_registry_unchanged'] and evidence['original_trusted_unchanged']
    assert response.status_code in (403,409) and count==0 and calls==[]
