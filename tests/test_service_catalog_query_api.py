"""Existing HTTP/ASGI/owned PG ADOPT and VERIFY, not new authority."""
from copy import deepcopy
import json
import os
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import registered_dependencies as deps,preparation as prep
from parkweave.api import create_app
from parkweave.store import Store
from test_registered_local_revision import http_f,link_fixture,receipt_fixture,preparation_fixture,patch,patch_body,expected_impact
from test_case_goal_results import complete,get
from test_service_case_steps import read,command,verified,adopt,setup,GOALS,business
from test_service_plan_manual_lock import stored,lock
from test_service_plan_recovery import recover
from test_typed_dependency_opportunity_preview import database_state
from test_new_enterprise_local_chain import actual_http
from test_preparation import headers

OUT=Path(os.environ.get('PARKWEAVE_CATALOG_QUERY_EVIDENCE','.runtime/service-catalog-query-20261018/development'))
def record(name,v):OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'-'+uuid4().hex[:8]+'.json')).write_text(json.dumps(v,indent=2)+'\n')
def add_version(f,version=2,service=None,park=None):
    with f[1].connect() as c:
        c.execute('INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) '
            'SELECT %s,%s,%s,name,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=1',
            (park or 'park-a',service or prep.SERVICE,version,'park-a',prep.SERVICE))
def remove_version(f,version=2):
    with f[1].connect() as c:c.execute('DELETE FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',('park-a',prep.SERVICE,version))
def verify_all(f,p):
    for a in ('P1','P2','P3','P4','P5'):verified(f,p,a)

@pytest.mark.parametrize('change',['insert','remove','source'])
def test_actual_unselected_catalog_change_requires_explicit_adopt_and_all_original_verify(http_f,change):
    f=http_f
    if change!='insert':add_version(f)
    p,*_=complete(f,local=True);old=stored(f,p);assert old['dependency_manifest']['version']==2
    if change=='insert':add_version(f)
    elif change=='remove':remove_version(f)
    else:
        with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','\"2\"') WHERE park_id='park-a' AND service_id=%s AND version=2",(prep.SERVICE,))
    before=business(f);x=read(f,p).json();expected_impact(x,('P1','P2','P3','P4','P5'),());assert x['local_revision_required'] and x['can_adopt']
    assert command(f,p,'P1').status_code==409
    body=patch_body(f,p);key=uuid4().hex;r=patch(f,p,body,key);assert r.status_code==201,r.text
    current=stored(f,p);assert current['events'][:-1]==old['events'] and current['history']==old['history']
    assert current['id']==old['id'] and [s['id'] for s in current['steps']]==[s['id'] for s in old['steps']]
    assert [s['verified_sources'] for s in current['steps']]==[s['verified_sources'] for s in old['steps']]
    assert business(f)==before and get(f,p).json()['state']=='UNVERIFIED'
    verify_all(f,p);assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED' and business(f)==before
    before_read=database_state(f)
    with actual_http(create_app(Store(f[0].dsn))) as (api,traffic):
        cold=(*f[:3],api);q=recover(cold,p,key);assert q.status_code==200,q.text;assert q.json()['status']=='COMMITTED'
        assert read(cold,p).json()['state']=='VERIFIED' and all(t['method']=='GET' for t in traffic)
    assert database_state(f)==before_read and stored(f,p)['events'][:len(old['events'])]==old['events']
    assert patch(f,p,body,key).status_code==201 and stored(f,p)['revision']==current['revision']+5
    record(change,dict(plan_id=old['id'],old_manifest=old['dependency_manifest'],current_manifest=current['dependency_manifest'],changed=['P1','P2','P3','P4','P5'],preserved=[],cold_get_only=True,old_events_preserved=True))

def test_unrelated_service_and_park_preserve_all_checks_and_sources(http_f):
    f=http_f;p,*_=complete(f,local=True);old=stored(f,p);before=read(f,p).json()
    add_version(f,service='different-service');add_version(f,park='park-b')
    state=database_state(f);x=read(f,p).json();expected_impact(x,(),('P1','P2','P3','P4','P5'))
    assert x==before and stored(f,p)==old and database_state(f)==state

def test_legacy_v1_unknown_then_original_explicit_local_adopt_registers_current_query(http_f,monkeypatch):
    f=http_f;original=deps.collections
    def old_values(*args):v=original(*args);v.pop('service_catalog');return v
    # Emit the original V1 manifest grammar, never retrofit today's query into it.
    with monkeypatch.context() as m:
        m.setattr(deps,'collections',old_values);p,*_=complete(f,local=True);old=stored(f,p)
        assert old['dependency_manifest']['version']==1 and 'service_catalog' not in old['dependency_manifest']['collections']
        # Keep an actual old V1 source-change graph/ADOPT in the historical
        # prefix, so today's compiler must reproduce its original graph hash.
        from test_source_change_adoption import changed,preview
        card=changed(f,p);v=preview(f,p,card).json();assert v['can_adopt']
        r=adopt(f,p,v['adoption']);assert r.status_code==201,r.text
        for a in ('P2','P3','P4','P5'):verified(f,p,a)
        old=stored(f,p);assert old['events'][-5]['local_revision']['source_change']['source_impact']['schema']==1
    x=read(f,p).json();expected_impact(x,('P1','P2','P3','P4','P5'),())
    assert x['change_impact']['unknown_scope']=='THIS_CASE' and x['can_adopt']
    assert stored(f,p)['events']==old['events'] and command(f,p,'P1').status_code==409
    r=patch(f,p);assert r.status_code==201,r.text;now=stored(f,p)
    assert now['dependency_manifest']['version']==2 and now['events'][:-1]==old['events']
    assert 'service_catalog' not in now['events'][0]['dependencies']['collections']
    verify_all(f,p);assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
    record('legacy-v1',dict(old_manifest=old['dependency_manifest'],new_manifest=now['dependency_manifest'],unknown_before_explicit_adopt=True,history_not_backfilled=True))

def test_current_lock_stale_body_and_revocation_keep_original_write_gates(http_f):
    f=http_f;p,*_=complete(f,local=True);assert lock(f,p,'P1').status_code==200;add_version(f)
    x=read(f,p).json();assert not x['can_adopt'];before=database_state(f);assert patch(f,p).status_code==409 and database_state(f)==before
    assert command(f,p,'P1','UNLOCK').status_code==200;body=patch_body(f,p)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET name=name||' changed' WHERE park_id='park-a' AND service_id=%s AND version=2",(prep.SERVICE,))
    before=database_state(f);assert patch(f,p,body).status_code==409 and database_state(f)==before
    for cap,table in [('PREPARE','preparation_grants'),('READ','capability_grants')]:
        with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
        before=database_state(f)
        assert read(f,p).status_code==403 and patch(f,p,body).status_code==403
        assert read(f,p,user='fixture-b').status_code==403 and database_state(f)==before
        with f[1].connect() as c:c.execute('UPDATE '+table+' SET active=true WHERE principal_id=%s AND capability=%s',('fixture-a',cap))


def test_unselected_original_publication_withdrawal_changes_query_without_selected_source_change(http_f):
    from parkweave import catalog_publication as pub,case_opportunities as opportunities
    from test_service_plan_approval import enable
    f=http_f;p=setup(f,GOALS[0]);protocol=pub.IsolatedCatalogPublication(enable(f,p),enabled_for_isolated_tests=True)
    add_version(f)
    # Only owned synthetic setup: the original append/proof/trigger contract
    # creates a version-2 test source history. This is not ordinary approval.
    def version(c):return c.execute('SELECT * FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=2',('park-a',prep.SERVICE)).fetchone()
    with f[1].connect() as c:protocol._append(c,version(c),'INIT',{'action':'INIT'},'init-'+uuid4().hex)
    assert adopt(f,p).status_code==201;verified(f,p,'P1');old=stored(f,p)
    with f[1].connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        selected=pub.snapshot(c,parent);basis=opportunities.sources(c,parent)
        protocol._append(c,version(c),'WITHDRAW',{'action':'WITHDRAW','expected_revision':1,'reason':'SYNTHETIC unselected v2 withdrawn'},uuid4().hex)
    with f[1].connect() as c:
        assert pub.snapshot(c,parent)==selected and opportunities.sources(c,parent)==basis
        assert pub.proof(version(c))['state']=='WITHDRAWN'
    before=business(f);x=read(f,p).json();expected_impact(x,('P1',),());assert x['local_revision_required']
    assert command(f,p,'P1').status_code==409
    assert patch(f,p).status_code==201;verified(f,p,'P1')
    assert stored(f,p)['events'][:len(old['events'])]==old['events'] and business(f)==before
    record('unselected-withdrawal',dict(selected_source_unchanged=True,original_opportunity_basis_unchanged=True,
        catalog_query_changed=True,changed=['P1'],original_isolated_catalog_fixture_only=True,ordinary_approval_enabled=False))


def test_original_full_html_explicit_catalog_adopt_and_five_verify_buttons(http_f):
    import queue,subprocess,threading
    f=http_f;p,*_=complete(f,local=True);old=stored(f,p);unchanged=business(f);base=str(f[3].base_url).rstrip('/')
    OUT.mkdir(parents=True,exist_ok=True);name='catalog-html-'+uuid4().hex[:8]
    errpath=OUT/(name+'.stderr');lines=[];messages=queue.Queue()
    with errpath.open('w') as err:
        proc=subprocess.Popen(['node','tests/service_catalog_query_real_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
        def consume():
            for line in proc.stdout:messages.put(line)
            messages.put(None)
        threading.Thread(target=consume,daemon=True).start()
        proc.stdin.write(json.dumps(dict(base=base,token=f[2]['fixture-a'],A={'preparation_id':p['preparation_id']}))+'\n');proc.stdin.flush()
        try:
            while True:
                line=messages.get(timeout=60)
                if line is None:break
                lines.append(line);item=json.loads(line)
                if item.get('control')=='insert_catalog_version':add_version(f);proc.stdin.write('{}\n');proc.stdin.flush()
                elif item.get('control')=='assert_final':
                    now=stored(f,p);assert now['events'][:len(old['events'])]==old['events'] and now['revision']==old['revision']+6
                    assert now['id']==old['id'] and business(f)==unchanged
                    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED'
                    proc.stdin.write('{}\n');proc.stdin.flush()
            code=proc.wait(timeout=5)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
            (OUT/(name+'.jsonl')).write_text(''.join(lines))
    assert code==0,errpath.read_text()
    result=json.loads(lines[-1]);assert result['scope']=='ORIGINAL_CATALOG_QUERY_ADOPT_VERIFY_FULL_HTML' and result['checks']>=8
    assert sum(c['method']=='POST' for c in result['calls'])==6
