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


@pytest.mark.parametrize('version',['baseline','current'])
def test_reproduce_bridge_cleanup_failure(preparation_fixture,tmp_path,version):
    f=preparation_fixture;permissions=permission_snapshot(f[1]);cfg=template_config().model_dump()
    for permit in cfg['permits']:permit['scope']['park_id']='park-a'
    engine=TemplateEngine(TemplateConfig.model_validate(cfg),TemplateRepository(tmp_path/'continuity.template.candidate.sqlite3'))
    consumer=TemplateConsumer(f[0],engine,ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(f[0].dsn)['dbname']],allowed_orgs=[{'park_id':'park-a','org_id':'org-a'}]),
        ConsumerRepository(tmp_path/'continuity.consumer.candidate.sqlite3'))
    with TestClient(create_isolated_template_app(f[0],engine,consumer)) as client:
        # Existing approved synthetic release, prepared through original commands.
        path='/api/template-candidate/park-a/new-enterprise-material-template'
        for action,actor in [('SAVE_DRAFT','template-author'),('SUBMIT','template-author'),('REVIEW','template-reviewer'),('CANDIDATE_PUBLISH','template-publisher')]:
            h={'X-Isolated-Template-Actor':actor,'Idempotency-Key':uuid4().hex};view=client.get(path,headers=h).json()
            body={'action':action,'expected_revision':view['revision'],'expected_definition_sha256':view['definition_sha256'],'reason':'SYNTHETIC existing reviewed release '+action}
            if action=='SAVE_DRAFT':body['draft']=definition().model_dump(mode='json')
            if action=='CANDIDATE_PUBLISH':body['validity']=VALID
            r=client.post(path+'/commands',headers=h,json=body);assert r.status_code==200,r.text
        proc=subprocess.Popen(['node','/workspace/ParkWeave/.runtime/ttl-template-repair-20261017/template-bridge-diagnostic.js','template_plan_continuity','/workspace/ParkWeave/src/parkweave/template_candidate_web.html','/workspace/ParkWeave/.runtime/ttl-template-repair-20261017/'+version+'-web.html'],
            cwd=Path('/workspace/ParkWeave'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ);requests=[];summary=None;invalid_seen=False
        try:
            while True:
                assert selector.select(timeout=15),'Template continuity bridge made no progress within15 seconds'
                line=proc.stdout.readline()
                if not line:break
                message=json.loads(line)
                if 'request' not in message:summary=message;break
                r=message['request'];o=r['options'];method=o.get('method','GET');body=json.loads(o['body']) if o.get('body') else None
                actor=o.get('headers',{}).get('Authorization','Bearer SYNTHETIC_fixture-a').removeprefix('Bearer SYNTHETIC_')
                response=client.request(method,r['path'],headers=headers(f[2],actor,key=o.get('headers',{}).get('Idempotency-Key')),json=body)
                requests.append({'method':method,'path':r['path'],'status':response.status_code,'actor':actor})
                if response.status_code==422:
                    assert r['path']=='/api/template-consumer/instances' and body['materials'][0]['text']=='';invalid_seen=True
                    with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==0
                else:assert response.status_code<400,(method,r['path'],response.status_code,response.json())
                if method=='POST' and r['path']=='/api/template-consumer/instances' and response.status_code==201:
                    f[0].finish(f[0].claim('template-continuity-original-worker'))
                proc.stdin.write((json.dumps({'status':response.status_code,'body':response.json()})+'\n').encode());proc.stdin.flush()
            rc=proc.wait(timeout=15);stderr=proc.stderr.read().decode()
            out=Path('/workspace/ParkWeave/.runtime/ttl-template-repair-20261017')
            (out/(version+'-bridge.stderr')).write_text(stderr)
            (out/(version+'-bridge-requests.json')).write_text(json.dumps(requests,indent=2)+'\n')
            diagnostic=json.loads(next(line.removeprefix('DIAGNOSTIC ') for line in stderr.splitlines() if line.startswith('DIAGNOSTIC ')))
            assert rc==1 and diagnostic['classListPresent'] is False and "reading 'remove'" in diagnostic['status']
            assert diagnostic['productPlanPresent'] is False and invalid_seen and permission_snapshot(f[1])==permissions
            (out/(version+'-bridge-proof.json')).write_text(json.dumps(dict(source=version,diagnostic=diagnostic,fixture_contract='original exact synthetic definition and original isolated ASGI bridge; two fresh owned databases',defect_reproduced=True),indent=2)+'\n')
        finally:
            selector.close()
            if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
