"""Owned composition: governance, catalog admission and independent cold input.

Catalog owner admission, new Run assignment, local worker and approval bridge
are explicit fixtures. No product endpoint grants catalog administration.
"""
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4
import pytest
from fastapi.responses import HTMLResponse
from parkweave.api import create_app
from parkweave.template_candidate import TemplateEngine, Command
from parkweave.template_candidate_api import create_template_candidate_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_plan_approval import IsolatedPlanApproval
from parkweave.service_capability_contract import hash_instance
from cancel33_fixture_support import cancel33_case
from test_preparation import preparation_fixture, headers, command as material
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog, register
from test_service_selection_candidates import planner
from test_plan_replacement_reapproval import bind_all, generate
from test_cancelled_case_independent_new_case import fresh_cold_case, ok
from test_service_case_steps import verified
from test_service_plan_approval import approved
from test_case_resource_delivery import quoted
from service_release_acceptance_support import case_history


@pytest.fixture
def release_case(cancel33_case, capability_resource_catalog, tmp_path):
    x=cancel33_case;a=capability_resource_catalog
    assert a["f"] is x["f"]
    f=x['f'];old=case_history(f[1],x['p']['preparation_id'])
    engine=a['engine']
    engine=TemplateEngine(engine.config,engine.repository,engine.clock,compatible_publication_only=True)
    a['engine']=engine;a['consumer'].template_engine=engine;a['catalog'].engine=engine
    facade=ParkInstanceConsumer(a['catalog'],ConsumerRepository(tmp_path/'release-new.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
    calls=[]
    app=create_app(f[0],capability_catalog=a['catalog'],instance_consumer=facade,selection_planner=planner(calls,mode='all'))
    candidate=create_template_candidate_app(engine)
    for route in candidate.router.routes:
        if getattr(route,'path','/') not in ('/','/openapi.json','/docs','/docs/oauth2-redirect','/redoc'):
            app.router.routes.append(route)
    @app.get('/template',response_class=HTMLResponse)
    def page():return Path(__file__).resolve().parents[1].joinpath('src/parkweave/template_candidate_web.html').read_text()
    return dict(x=x,a=a,f=f,old=old,engine=engine,facade=facade,app=app,calls=calls)


def path(t):
    s=t['a']['scope'];return '/api/template-candidate/'+s.park_id+'/'+s.template_id


def candidate_act(api,t,action,actor='template-author',**extra):
    h={'X-Isolated-Template-Actor':actor}
    current=ok(api.get(path(t),headers=h))
    return ok(api.post(path(t)+'/commands',headers={**h,'Idempotency-Key':uuid4().hex},json=dict(action=action,
        expected_revision=current['revision'],expected_definition_sha256=current['definition_sha256'],
        reason='SYNTHETIC explicit new Release '+action,**extra)))


def reviewed_revision(api,t):
    current=candidate_act(api,t,'RETURN_DRAFT')
    draft=deepcopy(current['draft']);draft['name']='SYNTHETIC compatible new Release for independent new input'
    candidate_act(api,t,'SAVE_DRAFT',draft=draft)
    candidate_act(api,t,'SUBMIT')
    return candidate_act(api,t,'REVIEW','template-reviewer')


def publish_revision(api,t):
    row=reviewed_revision(api,t);h={'X-Isolated-Template-Actor':'template-publisher'}
    preflight=ok(api.get(path(t)+'/publication-preflight',headers=h));assert preflight['can_publish']
    body=dict(command=dict(action='CANDIDATE_PUBLISH',expected_revision=row['revision'],
        expected_definition_sha256=row['definition_sha256'],reason='SYNTHETIC explicitly confirm compatible new Release',validity=row['draft']['source']['validity']),
        expected_preflight_sha256=preflight['preflight_sha256'],confirmed=True)
    key=uuid4().hex
    ok(api.post(path(t)+'/compatible-publications',headers={**h,'Idempotency-Key':key},json=body))
    result=ok(api.get(path(t)+'/compatible-publications/'+key,headers=h))
    assert result['status']=='COMMITTED' and not result['automatically_replayed']
    return result['event']['release_id']


def admit_new(t,release_id):
    """Original issued fixture-owner catalog register/bind; no HTTP privilege."""
    a=t['a'];s=a['scope'];published=a['engine'].published(s,release_id)
    # Original explicit retirement of old active catalog entries; immutable
    # releases and old Case history remain. No UNKNOWN source is ignored.
    from parkweave.service_capability_catalog import row, proof, fold
    with a['catalog'].owner_connection() as c:
        value=row(c,'park-a');old_ids=list(fold(proof(value))[0])
    for old_id in old_ids:
        with a['catalog'].owner_connection() as c:revision=proof(row(c,'park-a'))['revision']
        a['catalog'].withdraw_release('park-a',uuid4().hex,old_id,revision,
            'SYNTHETIC explicit catalog retirement of superseded release; preserve old Case history')
    a['published']=published
    values=bind_all(a,revision=2)
    assert len(values)==3 and all(r['source_review']['template_release_id']==release_id for r,i in values)
    return values


def new_planned_case(t,api):
    f=t['f'][:3]+(api,)
    p=fresh_cold_case(f,t['facade'])
    f[1].assign_status('executor-a',UUID(p['run_id']),active=True)
    for action,actor in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
        p=ok(material(f,p,action,actor,reason='SYNTHETIC independently reviewed new Release inputs'))
    generate({**t['a'],'f':f},p);verified(f,p,'P1')
    return f,p


def new_holds(t,f):
    """Use the remaining one unit; old confirmed units are never released."""
    result=[]
    for old in t['x']['holds']:
        data=dict(starts_at=old['starts_at'],ends_at=old['ends_at'],quantity=1,
            expected_revision=old['resource_revision'],ttl_seconds=300,purpose='SYNTHETIC independent new Release capacity')
        result.append(ok(f[3].post('/api/synthetic-resources/'+old['resource_id']+'/holds',
            headers=headers(f[2],key=uuid4().hex),json=data),201)['hold'])
    return result


def approval(t,f,p,holds):
    bridge=IsolatedPlanApproval(f[1],f[1]._case_fact_fixture_receipt,
        preparation_ids=[t['x']['p']['preparation_id'],p['preparation_id']],enabled_for_isolated_tests=True)
    bridge.attach_store(f[0])
    data=quoted(f,p,dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds]))
    item,_=approved(f,p,data)
    return item,data
