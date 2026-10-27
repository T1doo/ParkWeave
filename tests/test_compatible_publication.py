"""Exact existing candidate commands plus opt-in atomic compatible revision gate."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import json
import pytest
from fastapi.testclient import TestClient
from parkweave.template_candidate import TemplateEngine, Command, sha
from parkweave.template_candidate_api import create_template_candidate_app
from parkweave.store import Conflict, Denied
from test_template_candidate import template_candidate, definition, VALID, SCOPE


def act(engine, action, actor='template-author', **extra):
    row = engine.read(actor, SCOPE)
    return engine.command(actor, SCOPE, uuid4().hex, Command.model_validate(dict(action=action,
        expected_revision=row['revision'], expected_definition_sha256=row['definition_sha256'],
        reason='SYNTHETIC explicit compatible revision '+action, **extra)))


def reviewed(engine, draft):
    row=engine.read('template-author',SCOPE)
    if row['state']!='NOT_CREATED':act(engine,'RETURN_DRAFT')
    act(engine,'SAVE_DRAFT',draft=draft)
    act(engine,'SUBMIT')
    act(engine,'REVIEW','template-reviewer')


@pytest.fixture
def compatible(template_candidate):
    old,repo,now=template_candidate
    reviewed(old,definition())
    first=act(old,'CANDIDATE_PUBLISH','template-publisher',validity=VALID)['event']['release_id']
    prior=old.published(SCOPE,first)
    engine=TemplateEngine(old.config,repo,lambda:now[0],compatible_publication_only=True)
    draft=definition();draft.name='SYNTHETIC compatible title revision'
    reviewed(engine,draft)
    return engine,repo,now,prior


def envelope(engine, check=None):
    row=engine.read('template-publisher',SCOPE)
    check=check or engine.publication_preflight('template-publisher',SCOPE)
    return dict(command=dict(action='CANDIDATE_PUBLISH',expected_revision=row['revision'],
        expected_definition_sha256=row['definition_sha256'],reason='SYNTHETIC explicit confirmed new Release',validity=VALID),
        expected_preflight_sha256=check['preflight_sha256'],confirmed=True)


def test_compatible_revision_original_publish_immutable_old_and_get_only_recovery(compatible):
    e,repo,now,old=compatible
    check=e.publication_preflight('template-publisher',SCOPE)
    assert check['can_publish'] and check['preflight']['classification']=='COMPATIBLE'
    body=envelope(e,check);key=uuid4().hex;path=f'/api/template-candidate/{SCOPE.park_id}/{SCOPE.template_id}'
    with TestClient(create_template_candidate_app(e)) as client:
        h={'X-Isolated-Template-Actor':'template-publisher','Idempotency-Key':key}
        reply=client.post(path+'/compatible-publications',headers=h,json=body)
        assert reply.status_code==200,reply.text
        new=reply.json()['event']['release_id'];assert new!=old['release_id']
        del reply
        # Actual cold engine/app reopening, only GET of original request.
        cold=TemplateEngine(e.config,repo,lambda:now[0],compatible_publication_only=True)
        with TestClient(create_template_candidate_app(cold)) as recovered:
            result=recovered.get(path+'/compatible-publications/'+key,headers=h)
            assert result.status_code==200,result.text
            result=result.json();assert result['status']=='COMMITTED' and not result['automatically_replayed']
            assert result['event']['release_id']==new
        assert client.post(path+'/compatible-publications',headers=h,json=body).json()['event']['release_id']==new
        conflict=deepcopy(body);conflict['expected_preflight_sha256']='0'*64
        assert client.post(path+'/compatible-publications',headers=h,json=conflict).status_code==409
    with repo.transaction() as c:
        rows=c.execute('SELECT * FROM template_releases ORDER BY rowid').fetchall()
        assert len(rows)==2 and json.loads(rows[0]['payload'])==old['snapshot']
        assert rows[0]['payload_sha']==old['release_sha256']
        with pytest.raises(Exception):c.execute('UPDATE template_releases SET payload=? WHERE id=?',('{}',new))


@pytest.mark.parametrize('change',['goals','source','registry','contract','withdrawn','expired','draft_aba','stale_hash'])
def test_breaking_unknown_or_stale_revisions_refused_without_new_release(compatible,change,monkeypatch):
    e,repo,now,old=compatible
    check=e.publication_preflight('template-publisher',SCOPE)
    body=envelope(e,check)
    if change in ('goals','source','draft_aba'):
        draft=definition(['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION'] if change=='goals' else None,
                         '2' if change=='source' else '1')
        draft.name='SYNTHETIC compatible title revision'
        reviewed(e,draft)
    elif change=='registry':
        from parkweave import bounded_planning as bp
        registry=deepcopy(bp.REGISTRY);registry[0]['acceptance']='SYNTHETIC changed registry'
        monkeypatch.setattr(bp,'REGISTRY',registry)
    elif change=='contract':
        config=e.config;config.revision+=1;e.replace_contract(config)
    elif change=='expired':now[0]=datetime(2100,1,1,tzinfo=timezone.utc)
    elif change=='withdrawn':
        with repo.transaction() as c:c.execute("UPDATE template_releases SET state='WITHDRAWN' WHERE id=?",(old['release_id'],))
    elif change=='stale_hash':body['expected_preflight_sha256']='0'*64
    if change in ('goals','source'):
        refused=e.publication_preflight('template-publisher',SCOPE)
        assert not refused['can_publish'] and refused['preflight']['classification']=='BREAKING_REJECTED'
        body=envelope(e,refused)
    with pytest.raises((Conflict,Denied)):
        e.command('template-publisher',SCOPE,uuid4().hex,Command.model_validate(body['command']),
                  publication_preflight_sha256=body['expected_preflight_sha256'],publication_confirmed=True)
    with repo.transaction() as c:assert c.execute('SELECT count(*) FROM template_releases').fetchone()[0]==1


@pytest.mark.parametrize('actor',['template-author','template-reviewer','template-reader','missing'])
def test_current_publisher_only_and_exact_scope(compatible,actor):
    e,_,_,_=compatible
    with pytest.raises((Denied,Conflict)):e.publication_preflight(actor,SCOPE)


def test_strict_mode_no_legacy_publish_bypass_or_missing_confirmation(compatible):
    e,_,_,_=compatible;body=envelope(e)
    with pytest.raises(Conflict):e.command('template-publisher',SCOPE,uuid4().hex,Command.model_validate(body['command']))
    with TestClient(create_template_candidate_app(e)) as client:
        path=f'/api/template-candidate/{SCOPE.park_id}/{SCOPE.template_id}'
        h={'X-Isolated-Template-Actor':'template-publisher','Idempotency-Key':uuid4().hex}
        assert client.post(path+'/commands',headers=h,json=body['command']).status_code==409
        assert client.post(path+'/compatible-publications',headers=h,json={**body,'confirmed':False}).status_code==422
        assert client.get(path+'/compatible-publications/'+uuid4().hex,headers=h).json()['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('capability',['CANDIDATE_PUBLISH','READ','REVIEW'])
def test_revocation_after_preview_enforced_and_original_get_authorized(compatible,capability):
    e,_,_,_=compatible;body=envelope(e);key=uuid4().hex
    actor='template-reviewer' if capability=='REVIEW' else 'template-publisher'
    config=e.config;config.revision+=1
    for permit in config.permits:
        if permit.principal_id==actor and capability in permit.actions:permit.actions.remove(capability)
    e.replace_contract(config)
    with pytest.raises((Denied,Conflict)):
        e.command('template-publisher',SCOPE,key,Command.model_validate(body['command']),publication_preflight_sha256=body['expected_preflight_sha256'],publication_confirmed=True)
    if capability=='READ':
        with pytest.raises(Denied):e.publication_recover('template-publisher',SCOPE,key)
    else:assert e.publication_recover('template-publisher',SCOPE,key)['status']=='NOT_OBSERVED'


@pytest.mark.parametrize('value',[False,1,1.0,'true',None])
def test_confirmation_requires_exact_json_boolean(compatible,value):
    e,_,_,_=compatible;body=envelope(e)
    with TestClient(create_template_candidate_app(e)) as api:
        path=f'/api/template-candidate/{SCOPE.park_id}/{SCOPE.template_id}'
        assert api.post(path+'/compatible-publications',headers={'X-Isolated-Template-Actor':'template-publisher',
            'Idempotency-Key':uuid4().hex},json={**body,'confirmed':value}).status_code==422
    with pytest.raises(Conflict):e.command('template-publisher',SCOPE,uuid4().hex,
        Command.model_validate(body['command']),publication_preflight_sha256=body['expected_preflight_sha256'],publication_confirmed=value)


def test_default_mode_unchanged_and_current_scope_denial(compatible):
    e,repo,now,_=compatible
    from parkweave.template_candidate import Scope
    with pytest.raises(Denied):e.publication_preflight('template-publisher',Scope(park_id='other-park',template_id=SCOPE.template_id))
    original=TemplateEngine(e.config,repo,lambda:now[0])
    body=envelope(e)['command'];key=uuid4().hex
    # The opt-in mode is process scoped, deliberately not retroactive repository governance.
    result=original.command('template-publisher',SCOPE,key,Command.model_validate(body))
    assert 'publication_preflight' not in result['event'] and 'publication_confirmed' not in result['event']
    assert original.command('template-publisher',SCOPE,key,Command.model_validate(body))['event']==result['event']
    with TestClient(create_template_candidate_app(original)) as api:
        assert api.get(f'/api/template-candidate/{SCOPE.park_id}/{SCOPE.template_id}/publication-preflight').status_code==404


def test_explicit_mode_without_enabled_contract_still_denies():
    e=TemplateEngine(compatible_publication_only=True)
    with pytest.raises(Denied):e.publication_preflight('template-publisher',SCOPE)
