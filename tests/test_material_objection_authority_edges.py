from conftest import pg, fixture
from test_preparation import preparation_fixture
from test_material_objections import ready, act, get, checked, body, post, SPECIALIST
import pytest

@pytest.mark.parametrize('user,kind',[('fixture-a','preparation'),(SPECIALIST,'preparation'),('fixture-a','principal'),(SPECIALIST,'principal')])
def test_restored_original_authority_does_not_revive_old_response(preparation_fixture,user,kind):
    f=preparation_fixture;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST)
    prior=checked(get(f,p));old_sha=prior['binding']['sha256'];old_response=prior['items'][0]['response_id']
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        if kind=='preparation':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(user,))
        else:c.execute('UPDATE principals SET active=false WHERE id=%s',(user,))
    with f[1].connect() as c:
        f[1].lock_principal(c,user,exclusive=True)
        if kind=='preparation':c.execute('UPDATE preparation_grants SET active=true WHERE principal_id=%s',(user,))
        else:c.execute('UPDATE principals SET active=true WHERE id=%s',(user,))
    restored=checked(get(f,p))
    result=post(f,p,body(restored,'ACCEPT_RESPONSE',restored['items'][0]))
    print({'user':user,'kind':kind,'binding_same':old_sha==restored['binding']['sha256'],'old_response_same':old_response==restored['items'][0]['response_id'],'state':restored['items'][0]['state'],'accept_status':result.status_code})
    assert restored['items'][0]['state']=='STALE'
    assert result.status_code==409


def test_catalog_change_requires_a_new_material_review(preparation_fixture):
    f=preparation_fixture;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST)
    prior=checked(get(f,p));old_review=prior['binding']['review_event_id']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        c.execute("UPDATE preparation_catalog SET source=source||'{\"review_revision\":\"new-source\"}'::jsonb WHERE park_id='park-a'")
    stale=checked(get(f,p));r=post(f,p,body(stale,'REBIND',stale['items'][0]))
    print({'catalog_changed':True,'same_review':stale['binding']['review_event_id']==old_review,'current_review_valid':stale['current_review_valid'],'rebind_without_review_status':r.status_code})
    assert r.status_code==409
from test_material_text_pack_browser import browser_page
@pytest.mark.parametrize('edge',['restored-reviewer-preparation-grant','changed-catalog-without-review'])
def test_real_http_contract_edges(browser_page,edge):
    f,page,_=browser_page;p=ready(f);act(f,p);act(f,p,'RESPOND',SPECIALIST)
    base=page.url.rstrip('/')
    hdr={'Authorization':'Bearer '+f[2]['fixture-a']}
    old=page.request.get(base+'/api/preparations/'+p['preparation_id']+'/material-objections',headers=hdr).json()
    with f[1].connect() as c:
        f[1].lock_principal(c,SPECIALIST if edge.startswith('restored') else 'fixture-a',exclusive=True)
        if edge.startswith('restored'):c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(SPECIALIST,))
        else:
            c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
            c.execute("UPDATE preparation_catalog SET source=source||'{\"review_revision\":\"new-source\"}'::jsonb WHERE park_id='park-a'")
    if edge.startswith('restored'):
        with f[1].connect() as c:
            f[1].lock_principal(c,SPECIALIST,exclusive=True)
            c.execute('UPDATE preparation_grants SET active=true WHERE principal_id=%s',(SPECIALIST,))
    current=page.request.get(base+'/api/preparations/'+p['preparation_id']+'/material-objections',headers=hdr).json()
    action='ACCEPT_RESPONSE' if edge.startswith('restored') else 'REBIND'
    response=page.request.post(base+'/api/preparations/'+p['preparation_id']+'/material-objections',headers={**hdr,'Idempotency-Key':__import__('uuid').uuid4().hex},data=body(current,action,current['items'][0]))
    print({'real_http':True,'edge':edge,'same_review':old['binding']['review_event_id']==current['binding']['review_event_id'],'observed_status':response.status,'expected_status':409})
    assert response.status==409


def test_catalog_aba_same_json_requires_new_review_and_explicit_rebind(preparation_fixture):
    from test_preparation import command
    f=preparation_fixture;p=ready(f);act(f,p);responded=act(f,p,'RESPOND',SPECIALIST)
    old=checked(get(f,p));old_source=old['binding']['catalog_sha256']
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        original=c.execute("SELECT source FROM preparation_catalog WHERE park_id='park-a' AND version=1").fetchone()['source']
        c.execute("UPDATE preparation_catalog SET source=source||'{\"temporary\":true}'::jsonb WHERE park_id='park-a'")
    from psycopg.types.json import Jsonb
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
        c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a' AND version=1",(Jsonb(original),))
    current=checked(get(f,p));assert current['binding']['catalog_sha256']==old_source
    assert current['binding']['catalog_epoch_sha256']!=old['binding']['catalog_epoch_sha256']
    assert current['items'][0]['state']=='STALE' and not current['current_review_valid']
    assert post(f,p,body(current,'REBIND',current['items'][0])).status_code==409
    reopened=checked(command(f,responded,'REOPEN',reason='SYNTHETIC catalog ABA source recheck'))
    checked(command(f,reopened,'REVIEW',SPECIALIST,reason='SYNTHETIC actual current catalog review'))
    act(f,p,'REBIND');act(f,p,'RESPOND',SPECIALIST);act(f,p,'ACCEPT_RESPONSE')
    assert not checked(get(f,p))['unresolved']


def test_legacy_review_without_source_proof_cannot_silently_enable_delivery_review(preparation_fixture):
    f=preparation_fixture;p=ready(f)
    with f[1].connect() as c:c.execute("UPDATE preparation_events SET payload=payload-'delivery_review_source' WHERE preparation_id=%s AND action='REVIEW'",(p['preparation_id'],))
    v=checked(get(f,p));assert not v['current_review_valid'] and not v['can_raise']
    assert post(f,p,body(v)).status_code==409
