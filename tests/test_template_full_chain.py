"""Original template and product page handlers connected through owned ASGI."""
import json,selectors,subprocess
import pytest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from parkweave.template_candidate import TemplateConfig,TemplateEngine,TemplateRepository
from parkweave.template_consumer import ConsumerConfig,ConsumerRepository,TemplateConsumer
from parkweave.template_isolated_app import create_isolated_template_app
from test_preparation import preparation_fixture,headers
from test_template_candidate import template_config,definition,VALID
from test_isolated_run_access import permission_snapshot
from parkweave.isolated_run_access import IsolatedRunAccessBridge
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture


@pytest.mark.parametrize("mode",["full_chain","withdraw","source_head"])
def test_template_new_input_full_original_local_chain_and_changed_source_rejections(link_fixture,tmp_path,mode):
    f=link_fixture;permissions=permission_snapshot(f[1]);cfg=template_config().model_dump()
    for permit in cfg['permits']:permit['scope']['park_id']='park-a'
    engine=TemplateEngine(TemplateConfig.model_validate(cfg),TemplateRepository(tmp_path/'continuity.template.candidate.sqlite3'))
    consumer=TemplateConsumer(f[0],engine,ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(f[0].dsn)['dbname']],allowed_orgs=[{'park_id':'park-a','org_id':'org-a'}]),
        ConsumerRepository(tmp_path/'continuity.consumer.candidate.sqlite3'))
    bridge=IsolatedRunAccessBridge(f[1],f[1]._case_fact_fixture_receipt,tmp_path/'template-full.run-access.candidate.sqlite3',approver_ids={'prep-specialist-fixture-a'},enabled_for_isolated_tests=True);bridge.attach_store(f[0]);assert permission_snapshot(f[1])==permissions
    with TestClient(create_isolated_template_app(f[0],engine,consumer)) as client:
        # Existing approved synthetic release, prepared through original commands.
        path='/api/template-candidate/park-a/new-enterprise-material-template'
        for action,actor in [('SAVE_DRAFT','template-author'),('SUBMIT','template-author'),('REVIEW','template-reviewer'),('CANDIDATE_PUBLISH','template-publisher')]:
            h={'X-Isolated-Template-Actor':actor,'Idempotency-Key':uuid4().hex};view=client.get(path,headers=h).json()
            body={'action':action,'expected_revision':view['revision'],'expected_definition_sha256':view['definition_sha256'],'reason':'SYNTHETIC existing reviewed release '+action}
            if action=='SAVE_DRAFT':body['draft']=definition(goals=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK']).model_dump(mode='json');body['draft']['source']['id']='isolated-template-materials-source'
            if action=='CANDIDATE_PUBLISH':body['validity']=VALID
            r=client.post(path+'/commands',headers=h,json=body);assert r.status_code==200,r.text
        proc=subprocess.Popen(['node',str(Path(__file__).with_name('template_full_chain.js' if mode=='full_chain' else 'template_source_rejections.js')),mode],
            cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None;invalid_seen=False;denials=0;product_before=None
        try:
            while True:
                assert selector.select(timeout=15),'Template continuity bridge made no progress within15 seconds'
                line=proc.stdout.readline()
                if not line:break
                message=json.loads(line)
                if 'request' not in message:summary=message;break
                r=message['request'];o=r['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None
                actor=o.get('headers',{}).get('Authorization','Bearer SYNTHETIC_fixture-a').removeprefix('Bearer SYNTHETIC_')
                response=client.request(method,r['path'],headers={**headers(f[2],actor,key=o.get('headers',{}).get('Idempotency-Key')),**({'X-Isolated-Template-Actor':o['headers']['X-Isolated-Template-Actor']} if 'X-Isolated-Template-Actor' in o.get('headers',{}) else {})},json=body)
                requests.append({'method':method,'path':r['path'],'status':response.status_code,'actor':o.get('headers',{}).get('X-Isolated-Template-Actor',actor),'action':body.get('action') if body else None})
                if response.status_code==422:
                    assert r['path']=='/api/template-consumer/instances' and body['materials'][0]['text']=='';invalid_seen=True
                    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==0
                elif response.status_code==403 and mode!='full_chain':
                    assert method=='POST' and r['path'].startswith('/api/template-consumer/instances');denials+=1
                    with f[1].connect() as c:assert {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in product_before}==product_before
                else:assert response.status_code<400,(method,r['path'],response.status_code,response.json())
                if method=='POST' and r['path']=='/api/template-consumer/instances' and response.status_code==201:
                    f[0].finish(f[0].claim('template-full-original-worker'))
                    if mode!='full_chain':
                        with f[1].connect() as c:product_before={t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ['runs','cases','preparations','preparation_events','preparation_evidence','service_receipt_steps','case_local_events','case_resource_links']}
                proc.stdin.write((json.dumps({'status':response.status_code,'body':response.json()})+'\n').encode());proc.stdin.flush()
            assert proc.wait(timeout=15)==0,proc.stderr.read().decode()
            assert summary and summary['checks']>=20;assert invalid_seen if mode=='full_chain' else denials==2
            assert permission_snapshot(f[1])==permissions
            with f[1].connect() as c:
                assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==1
                assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==1
                if mode=='full_chain':
                    item=summary['instance'];step=c.execute('SELECT case_id,run_id,preparation_id,state FROM service_receipt_steps WHERE id=%s',(item['receipt'],)).fetchone();assert str(step['case_id'])==item['case'] and str(step['run_id'])==item['run'] and str(step['preparation_id'])==item['preparation'] and step['state']=='LOCAL_ACKNOWLEDGED'
                    assert c.execute('SELECT count(*) n FROM case_local_events WHERE preparation_id=%s',(item['preparation'],)).fetchone()['n']==3
                    assert c.execute('SELECT state FROM synthetic_resource_combinations WHERE id=%s',(item['combination'],)).fetchone()['state']=='CONFIRMED'
                    assert c.execute('SELECT count(*) n FROM synthetic_resource_combination_members m JOIN synthetic_resource_holds h ON h.id=m.hold_id WHERE m.combination_id=%s AND h.state=%s',(item['combination'],'CONFIRMED')).fetchone()['n']==2
                    parent=c.execute('SELECT case_id,run_id,service_case_plan FROM preparations WHERE id=%s',(item['preparation'],)).fetchone();assert str(parent['case_id'])==item['case'] and str(parent['run_id'])==item['run'];assert parent['service_case_plan']['id']==item['plan']
                else:assert c.execute('SELECT count(*) n FROM preparations').fetchone()['n']==0
            out=Path('.runtime/template-full-chain-20261013');out.mkdir(parents=True,exist_ok=True)
            (out/('actual-'+mode+'.json')).write_text(json.dumps({'summary':summary,'requests':requests,'permission_snapshot_unchanged':True},indent=2)+'\n')
        finally:
            out=Path('.runtime/template-full-chain-20261013');out.mkdir(parents=True,exist_ok=True);(out/('partial-'+mode+'.json')).write_text(json.dumps({'summary':summary,'requests':requests,'denials':denials},indent=2)+'\n')
            selector.close()
            if proc.poll() is None:proc.terminate();proc.wait(timeout=5)


