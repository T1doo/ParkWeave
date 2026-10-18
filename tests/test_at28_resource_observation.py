"""AT28 current observation only; original local resource/confirmation algorithms."""
from datetime import datetime
from pathlib import Path
import json,subprocess,threading
import pytest
from psycopg.types.json import Jsonb
from parkweave import resource_holds as rh
from test_resource_holds import resource_fixture,body,preview,counts
from test_preparation import headers
from ordinary_case_step_support import ordinary_api
from service_release_acceptance_support import authority_snapshot,table_snapshot

SOURCE_V2=dict(kind='SYNTHETIC',id='AT28-current-resource-source',revision='2',
    statement='SYNTHETIC current v2 <note>& source; external availability unverified')


def advance_source(f):
    with f[1].connect() as c:
        rh._lock(c,rh.RESOURCE_ID)
        c.execute('UPDATE synthetic_resources SET source=%s,revision=revision+1,capacity=3,name=%s WHERE id=%s',
            (Jsonb(SOURCE_V2),'SYNTHETIC current resource v2',rh.RESOURCE_ID))


def test_current_preview_source_is_not_prior_catalog_and_writes_nothing(resource_fixture,tmp_path):
    f=resource_fixture;authority=authority_snapshot(f[1]);catalog=f[3].get('/api/synthetic-resources',headers=headers(f[2])).json()
    assert catalog['items'][0]['revision']==1 and catalog['items'][0]['source']['revision']=='1'
    data=body(f);advance_source(f)
    tables=('runs','cases','preparations','model_steps','synthetic_resource_holds','synthetic_resource_receipts')
    before=table_snapshot(f[1],tables)
    result=preview(f,data);assert result.status_code==200,result.text;x=result.json()
    assert x['resource_revision']==2 and x['resource_name']=='SYNTHETIC current resource v2' and x['source']==SOURCE_V2
    assert x['authority']=='LOCAL_AUTHORITY' and x['timezone']=='UTC'
    assert x['available'] is True and (x['capacity'],x['occupied_peak'],x['available_quantity'])==(3,0,3)
    assert x['confirmation_required'] is True and x['external_availability']=='UNKNOWN'
    assert x['preview_only'] and x['reservation']=='NOT_CONFIRMED' and x['external_acceptance']=='NOT_SUBMITTED' and x['offline_fulfillment']=='NO_EVIDENCE'
    assert datetime.fromisoformat(x['server_time']).utcoffset().total_seconds()==0
    assert catalog['items'][0]['source']!=x['source'] and catalog['items'][0]['revision']==1
    assert table_snapshot(f[1],tables)==before and authority_snapshot(f[1])==authority
    (tmp_path/'current-observation.json').write_text(json.dumps(dict(prior_catalog=catalog,current_preview=x,selected_business_tables_unchanged=True,authority_unchanged=True,preview_read_only=True),indent=2)+'\n')


@pytest.mark.parametrize('mode',['current-source','missing-source','invalid-observation-time'])
def test_original_page_discloses_current_source_before_explicit_local_confirmation(resource_fixture,tmp_path,mode):
    f=resource_fixture;authority=authority_snapshot(f[1])
    with ordinary_api(f,tmp_path/'ordinary-api') as api:
        config=dict(base=str(api.base_url).rstrip('/'),token=f[2]['fixture-a'],resource_id=str(rh.RESOURCE_ID),mode=mode)
        with (tmp_path/'html.stdout').open('w') as out,(tmp_path/'html.stderr').open('w') as err:
            child=subprocess.Popen(['node','tests/at28_resource_observation_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
            timer=threading.Timer(45,child.terminate);timer.start()
            try:
                child.stdin.write(json.dumps(config)+'\n');child.stdin.flush()
                for line in child.stdout:
                    out.write(line);out.flush();row=json.loads(line)
                    if row.get('control')=='advance':advance_source(f);child.stdin.write('{}\n');child.stdin.flush()
                code=child.wait(timeout=5)
            finally:
                timer.cancel()
                if child.poll() is None:child.terminate();child.wait(timeout=5)
        assert code==0,(tmp_path/'html.stderr').read_text()
        summary=json.loads((tmp_path/'html.stdout').read_text().splitlines()[-1]);assert summary['real_browser'] is False
    assert authority_snapshot(f[1])==authority
    assert counts(f)==((1,2) if mode=='current-source' else (0,0))
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM model_steps').fetchone()['n']==0
