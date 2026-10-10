"""Independent real-lock activation and original-projection effect oracles."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event
from queue import Queue
from pathlib import Path
from uuid import UUID,uuid4
import json,time,pytest,psycopg
from parkweave import catalog_publication as pub,case_resource_delivery as delivery
from parkweave.store import Conflict,Denied
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture,setup as original_setup,approved,ledger,read
from test_catalog_approval_coordination import setup,publish,catalog
from test_case_resource_delivery import effects,submit
from test_resource_bundles import states
from test_preparation import headers
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/probes')

def wait_for(f,pid,kind,granted=None):
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        with f[1].connect() as c:
            rows=c.execute('SELECT locktype,mode,granted FROM pg_locks WHERE pid=%s',(pid,)).fetchall()
        if any(r['locktype']==kind and (granted is None or r['granted']==granted) for r in rows):return rows
        time.sleep(.02)
    raise AssertionError('expected actual lock not observed')

@pytest.mark.parametrize('damage',['head-alone','null-head','null-journal','old-prefix','source-only','name-only','scope-only'])
def test_owner_single_side_catalog_corruption_rejected_or_transaction_preserved(link_fixture,damage):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);item,_=approved(f,p,data);before=catalog(f,p);book=deepcopy(ledger(f,p))
    query={'head-alone':"UPDATE preparation_catalog SET candidate_catalog_head=jsonb_set(candidate_catalog_head,'{sha256}',to_jsonb(%s::text)) WHERE park_id=%s AND service_id=%s AND version=%s",'null-head':'UPDATE preparation_catalog SET candidate_catalog_head=NULL WHERE park_id=%s AND service_id=%s AND version=%s','null-journal':'UPDATE preparation_catalog SET candidate_catalog_revisions=NULL WHERE park_id=%s AND service_id=%s AND version=%s','old-prefix':"UPDATE preparation_catalog SET candidate_catalog_revisions=jsonb_set(candidate_catalog_revisions,'{events,0,sha256}',to_jsonb(%s::text)) WHERE park_id=%s AND service_id=%s AND version=%s",'source-only':"UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"99\"') WHERE park_id=%s AND service_id=%s AND version=%s",'name-only':"UPDATE preparation_catalog SET name='SYNTHETIC substituted original name' WHERE park_id=%s AND service_id=%s AND version=%s",'scope-only':"UPDATE preparation_catalog SET namespace='OTHER' WHERE park_id=%s AND service_id=%s AND version=%s"}[damage]
    key=protocol.parents[p['preparation_id']];args=('0'*64,*key) if damage in ('head-alone','old-prefix') else key
    try:
        with f[1].connect() as c:c.execute(query,args)
    except psycopg.Error:
        assert catalog(f,p)==before
    else:
        assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409
        for suffix in ('planning-preview','service-case-plan'):
            assert f[3].get('/api/preparations/'+p['preparation_id']+'/'+suffix,headers=headers(f[2])).status_code==409
    assert ledger(f,p)==book and effects(f)==[0]*5 and states(f,hs)==['HELD']*3

def test_publication_scope_and_simultaneous_same_cas_one_event(link_fixture):
    f=link_fixture;p,hs,data,bridge,protocol=setup(f);before=catalog(f,p)
    with pytest.raises(Denied):protocol.publish(uuid4(),uuid4().hex,dict(action='PUBLISH',expected_revision=1,source_revision=2,reason='SYNTHETIC other scope'))
    assert catalog(f,p)==before
    def invoke(rev):
        try:return publish(protocol,p,source_revision=rev)['revision']
        except Conflict:return 'CAS_REJECTED'
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(invoke,[2,3]))
    assert sorted(str(x) for x in outcomes)==['2','CAS_REJECTED']
    assert pub.proof(catalog(f,p))['revision']==2 and effects(f)==[0]*5
