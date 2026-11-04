"""Real ordinary API adapters: bounded reads, actual bytes and server event time."""
from copy import deepcopy
from datetime import datetime, timedelta
import base64
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from parkweave.api import configured_app
from parkweave import resource_holds as rh
from test_resource_holds import resource_fixture, body, hold, counts, configure
from test_preparation import preparation_fixture, create, headers, read
from test_executor_receipts import receipt_fixture
from test_local_synthetic_demo import demo_inputs, prepared, ok
from test_service_case_steps import setup, adopt, command as step_command, read as step_read, GOALS
from service_release_acceptance_support import case_history, authority_snapshot


def resource_input(f,**changes):
    row=body(f,**changes)
    return {k:row[k] for k in ('starts_at','ends_at','quantity','expected_revision')}|{'resource_id':str(rh.RESOURCE_ID)}


def preview_all(f,items,user='fixture-a'):
    return f[3].post('/api/synthetic-resources/combination-preview',headers=headers(f[2],user),json={'items':items})


def test_combined_preview_counts_other_intentions_without_creating_holds(resource_fixture):
    f=resource_fixture;row=body(f);assert hold(f,row,user='fixture-b').status_code==201
    item=resource_input(f,starts_at=row['starts_at'],ends_at=row['ends_at'])
    before=counts(f);view=ok(preview_all(f,[item,item]))
    assert not view['available'] and view['holds_created']==0 and view['read_only']
    assert view['reservation']=='NOT_CONFIRMED' and view['external_availability']=='UNKNOWN'
    assert [r['combined_peak'] for r in view['items']]==[3,3]
    assert all(r['reasons']==['COMBINED_CAPACITY_CONFLICT'] for r in view['items'])
    assert counts(f)==before
    assert ok(preview_all(f,[item]))['available']


def test_combined_preview_half_open_buffers_stale_and_denied_are_distinct(resource_fixture):
    f=resource_fixture;configure(f,capacity=1,buffer_seconds=0)
    a=resource_input(f);start=datetime.fromisoformat(a['starts_at'])
    a['ends_at']=(start+timedelta(minutes=30)).isoformat()
    b={**a,'starts_at':a['ends_at'],'ends_at':(start+timedelta(minutes=60)).isoformat()}
    assert ok(preview_all(f,[a,b]))['available']
    configure(f,capacity=1,buffer_seconds=300)
    a['expected_revision']+=1;b['expected_revision']+=1
    assert not ok(preview_all(f,[a,b]))['available']
    a['expected_revision']-=1
    view=ok(preview_all(f,[a]));assert 'RESOURCE_REVISION_CHANGED' in view['items'][0]['reasons']
    assert preview_all(f,[a],user='fixture-c').status_code==403
    assert preview_all(f,[a,{**a,'resource_id':str(uuid4())}]).status_code==403
    assert counts(f)==(0,0)
    assert preview_all(f,[]).status_code==422
    assert preview_all(f,[a]*9).status_code==422


def test_saved_file_metadata_uses_server_parsed_bytes_not_editable_source(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);raw='SYNTHETIC 合成材料'.encode();encoded=base64.b64encode(raw).decode()
    data=dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',source_kind='DOCUMENT_EXCERPT',
        source_label='SYNTHETIC editable source text',source_file=dict(file_name='合成.txt',content_base64=encoded,data_classification='SYNTHETIC_SAMPLE'))
    path='/api/preparations/'+p['preparation_id']+'/commands';key=uuid4().hex
    saved=ok(f[3].post(path,headers=headers(f[2],key=key),json=data))
    file=saved['file_metadata'];assert file['file_name']=='合成.txt' and file['file_bytes']==len(raw) and file['format']=='TEXT'
    assert file['provenance']=='SERVER_PARSED_SUBMITTED_BYTES' and file['source_expires_at'] is None and file['authenticity']=='UNVERIFIED'
    assert f[3].post(path,headers=headers(f[2],key=key),json=data).json()==saved
    view=ok(read(f,p));assert view['material_files']==[file]
    assert view['current_materials'][0]['text']==raw.decode() and 'file_metadata' not in view['current_materials'][0]
    # The new display facts are outside the established material hash domain.
    from parkweave.preparation import snapshot
    assert snapshot(view['preparation'],view['current_materials'])==view['snapshot_sha256']
    assert 'content_base64' not in json.dumps(view) and encoded not in json.dumps(view)
    reviewer=ok(read(f,p,'prep-specialist-fixture-a'));assert reviewer['material_files']==[file]
    changed={**data,'text':'changed without matching bytes','expected_revision':saved['revision']}
    assert f[3].post(path,headers=headers(f[2],key=uuid4().hex),json=changed).status_code==422
    assert ok(read(f,p))['preparation']['revision']==saved['revision']
    bad=deepcopy(data);bad['source_file']['file_name']='\ud800.txt'
    invalid=f[3].post(path,content=json.dumps(bad),headers={**headers(f[2],key=uuid4().hex),'Content-Type':'application/json'})
    assert invalid.status_code==422 and invalid.json()=={'detail':'invalid bounded preparation command'}
    assert encoded not in invalid.text
    no_type=f[3].post(path,content=json.dumps(data),headers=headers(f[2],key=uuid4().hex))
    assert no_type.status_code==422 and encoded not in no_type.text
    bad=deepcopy(data);bad['source_file']['content_base64']='!!SYNTHETIC_PRIVATE_BYTES!!'
    invalid=f[3].post(path,headers=headers(f[2],key=uuid4().hex),json=bad)
    assert invalid.status_code==422 and 'SYNTHETIC_PRIVATE_BYTES' not in invalid.text

    assert f[3].post(path,headers=headers(f[2],'fixture-b',uuid4().hex),json={**data,'expected_revision':saved['revision']}).status_code==403



def test_max_file_metadata_submission_retains_original_body_cap(preparation_fixture):
    f=preparation_fixture;p,_,_=create(f);raw=b' '*(8192-9)+b'SYNTHETIC'
    data=dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',source_kind='DOCUMENT_EXCERPT',
        source_label='SYNTHETIC original file',source_file=dict(file_name='SYNTHETIC.txt',
        content_base64=base64.b64encode(raw).decode(),data_classification='SYNTHETIC_SAMPLE'))
    assert len(json.dumps(data).encode())<16384
    result=ok(f[3].post('/api/preparations/'+p['preparation_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=data))
    assert result['file_metadata']['file_bytes']==8192
    assert ok(read(f,p))['current_materials'][0]['text']=='SYNTHETIC'


def test_manual_service_preview_validates_actual_refs_goals_and_original_sources(demo_inputs):
    initial,_,_,_=demo_inputs
    with TestClient(configured_app()) as api:
        f=(*initial[:3],api);p=prepared(f);path='/api/preparations/'+p['preparation_id']
        view=ok(api.get(path+'/service-capabilities',headers=headers(f[2])))
        refs=view['selection_oracle']['minimal_solutions'][0]
        data=dict(expected_preparation_revision=p['revision'],expected_source_sha256=view['source_sha256'],
            expected_capability_catalog_sha256=view['capability_catalog_sha256'],selections=refs)
        before=case_history(f[1],p['preparation_id']);authority=authority_snapshot(f[1])
        result=ok(api.post(path+'/service-composition-preview',headers=headers(f[2]),json=data))
        assert result['state']=='VERIFIED_STRUCTURE_ONLY' and result['can_generate_original_candidate']
        assert result['selection']['selections']==refs and result['new_grants'] is False and result['executed'] is False
        incomplete=ok(api.post(path+'/service-composition-preview',headers=headers(f[2]),json={**data,'selections':refs[:-1]}))
        assert incomplete['state']=='BLOCKED' and incomplete['missing_goals'] and not incomplete['can_generate_original_candidate']
        bad=deepcopy(data);bad['selections'][0]['revision']+=1
        assert api.post(path+'/service-composition-preview',headers=headers(f[2]),json=bad).status_code==409
        assert api.post(path+'/service-composition-preview',headers=headers(f[2]),json={**data,'expected_source_sha256':'0'*64}).status_code==409
        assert api.post(path+'/service-composition-preview',headers=headers(f[2],'prep-specialist-fixture-a'),json=data).status_code==403
        assert case_history(f[1],p['preparation_id'])==before and authority_snapshot(f[1])==authority


def test_new_step_events_have_server_time_old_events_remain_unknown(receipt_fixture):
    f=receipt_fixture;p=setup(f,goal=GOALS[0]);view=ok(adopt(f,p),201)
    assert datetime.fromisoformat(view['events'][-1]['created_at']).utcoffset()==timedelta(0)
    key=uuid4().hex;verified=ok(step_command(f,p,'P1',row=view,key=key));event=verified['events'][-1]
    assert ok(step_command(f,p,'P1',row=view,key=key))['events'][-1]['created_at']==event['created_at']
    assert event['action']=='VERIFY' and datetime.fromisoformat(event['created_at'])>=datetime.fromisoformat(view['events'][-1]['created_at'])
    public=ok(step_read(f,p,'prep-specialist-fixture-a'))
    assert set(public['events'][-1])=={'id','revision','action','step_id'}
    # A legacy JSON event has no stored clock; reading must not invent one.
    with f[1].connect() as c:
        row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
        row['events'][-1].pop('created_at')
        from psycopg.types.json import Jsonb
        c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(row),p['preparation_id']))
    legacy=ok(step_read(f,p));assert 'created_at' not in legacy['events'][-1]
