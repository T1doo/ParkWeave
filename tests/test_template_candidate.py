"""Independent template authority, graph closure and immutable release tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import sqlite3
import uuid

import pytest
from pydantic import ValidationError

from parkweave import preparation
from parkweave.template_candidate import (
    Scope, TemplatePrincipal, TemplatePermit, TemplateConfig,
    TemplateRepository, TemplateEngine, TemplateDraft, Command,
    draft_for_goals, Denied, Conflict,
)
from template_candidate_support import PARK

VALID = {'valid_from': '2020-01-01T00:00:00+00:00',
         'valid_until': '2099-01-01T00:00:00+00:00', 'timezone': 'UTC'}
SCOPE = Scope(park_id=PARK, template_id='new-enterprise-material-template')
SOURCE_SCOPE = Scope(park_id=PARK, template_id='independent-source-head-template')
ACTORS = {'template-author': 'template_author', 'template-reviewer': 'template_reviewer',
          'template-publisher': 'template_publisher', 'template-reader': 'template_reader'}
PERMISSIONS = {'template-author': ['READ', 'SAVE_DRAFT', 'SUBMIT', 'RETURN_DRAFT'],
               'template-reviewer': ['READ', 'REVIEW', 'REJECT'],
               'template-publisher': ['READ', 'CANDIDATE_PUBLISH', 'WITHDRAW'],
               'template-reader': ['READ']}


def template_config():
    return TemplateConfig(enabled_for_isolated_tests=True,
        principals=[TemplatePrincipal(id=actor, role=role) for actor, role in ACTORS.items()],
        permits=[TemplatePermit(id='permit-' + actor, principal_id=actor, scope=SCOPE,
                                actions=actions, validity=VALID)
                 for actor, actions in PERMISSIONS.items()] +
        [TemplatePermit(id='permit-independent-source-author', principal_id='template-author',
                        scope=SOURCE_SCOPE, actions=['READ', 'SAVE_DRAFT'], validity=VALID)])


def definition(goals=None, revision='1'):
    return draft_for_goals(name='New enterprise material template',
        description='Synthetic registered local preparation, no prior enterprise data.',
        goals=goals or ['LOCAL_MATERIAL_PREPARATION'],
        source={'kind': 'SYNTHETIC', 'id': 'ENG098-template-source', 'revision': revision,
                'statement': 'Synthetic reusable steps, no identities or filled materials.',
                'validity': VALID})


@pytest.fixture
def template_candidate(tmp_path):
    now = [datetime(2026, 10, 7, tzinfo=timezone.utc)]
    repository = TemplateRepository(tmp_path / 'eng098.template.candidate.sqlite3')
    engine = TemplateEngine(template_config(), repository, lambda: now[0])
    return engine, repository, now


def template_command(engine, action, *, actor=None, view=None, key=None, **fields):
    actor = actor or ('template-reviewer' if action in ('REVIEW', 'REJECT') else
                     'template-publisher' if action in ('CANDIDATE_PUBLISH', 'WITHDRAW') else
                     'template-author')
    view = view or engine.read(actor, SCOPE)
    body = {'action': action, 'expected_revision': view['revision'],
            'expected_definition_sha256': view['definition_sha256'],
            'reason': 'Explicit synthetic ' + action, **fields}
    if action == 'CANDIDATE_PUBLISH': body.setdefault('validity', VALID)
    return engine.command(actor, SCOPE, key or uuid.uuid4().hex, Command.model_validate(body))


def publish_template(engine):
    template_command(engine, 'SAVE_DRAFT', draft=definition())
    template_command(engine, 'SUBMIT')
    template_command(engine, 'REVIEW')
    return template_command(engine, 'CANDIDATE_PUBLISH')


def repository_snapshot(repository):
    with repository.transaction() as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: [tuple(row) for row in c.execute('SELECT * FROM ' + name + ' ORDER BY rowid')]
                for name in names}


def test_disabled_factory_is_not_mounted_in_product(fixture, tmp_path):
    from fastapi.testclient import TestClient
    from parkweave.template_candidate_api import create_template_candidate_app
    engine = TemplateEngine()
    assert not engine.config.enabled_for_isolated_tests
    with pytest.raises(Denied): engine.read('template-author', SCOPE)
    app = create_template_candidate_app()
    assert not any(route.path.startswith(('/api/template-candidate', '/api/template-consumer'))
                   or route.path == '/template' for route in fixture[3].app.routes)
    client = TestClient(app)
    assert not client.get('/api/template-candidate/status').json()['candidate_demo']
    assert client.get(f'/api/template-candidate/{PARK}/{SCOPE.template_id}',
                      headers={'X-Isolated-Template-Actor': 'template-author'}).status_code == 403
    assert list(tmp_path.iterdir()) == []


def test_review_is_independent_from_publish_and_release_is_immutable(template_candidate):
    engine, repository, _ = template_candidate
    template_command(engine, 'SAVE_DRAFT', draft=definition())
    template_command(engine, 'SUBMIT')
    before = repository_snapshot(repository)
    with pytest.raises(Conflict): template_command(engine, 'CANDIDATE_PUBLISH')
    assert repository_snapshot(repository) == before
    template_command(engine, 'REVIEW')
    assert not engine.public_catalog(PARK)['items']
    template_command(engine, 'CANDIDATE_PUBLISH')
    catalog = engine.public_catalog(PARK)['items']
    assert len(catalog) == 1
    release = catalog[0]
    assert release['release_sha256'] and release['snapshot']
    saved = deepcopy(release['snapshot'])
    template_command(engine, 'WITHDRAW')
    assert not engine.public_catalog(PARK)['items']
    view = engine.read('template-author', SCOPE)
    assert view['releases'][0]['snapshot'] == saved


@pytest.mark.parametrize('actor,action', [
    ('template-author', 'REVIEW'), ('template-author', 'CANDIDATE_PUBLISH'),
    ('template-reviewer', 'CANDIDATE_PUBLISH'), ('template-publisher', 'REVIEW'),
    ('template-reader', 'SAVE_DRAFT'), ('unknown', 'SAVE_DRAFT')])
def test_wrong_role_is_denied_without_candidate_write(template_candidate, actor, action):
    engine, repository, _ = template_candidate
    template_command(engine, 'SAVE_DRAFT', draft=definition())
    before = repository_snapshot(repository)
    view = engine.read('template-author', SCOPE)
    fields = {'draft': definition()} if action == 'SAVE_DRAFT' else {}
    with pytest.raises(Denied): template_command(engine, action, actor=actor, view=view, **fields)
    assert repository_snapshot(repository) == before


@pytest.mark.parametrize('field,value', [
    ('owner_id', 'fixture-a'), ('case_id', str(uuid.uuid4())),
    ('org_id', 'org-a'), ('material_values', {'need_summary': 'old case text'}),
    ('grants', [{'capability': 'EXECUTE'}]), ('result', {'qualified': True})])
def test_old_identity_material_and_result_fields_are_forbidden(field, value):
    data = definition().model_dump(mode='json')
    data[field] = value
    with pytest.raises(ValidationError): TemplateDraft.model_validate(data)


@pytest.mark.parametrize('mutation', ['unknown_goal', 'missing_dependency', 'extra_step', 'adapter_revision', 'material_default'])
def test_registered_closure_is_exact(mutation):
    data = definition(['LOCAL_INTERNAL_ACCEPTANCE']).model_dump(mode='json')
    if mutation == 'unknown_goal': data['required_goals'] = ['UNREGISTERED_GOAL']
    elif mutation == 'missing_dependency': data['steps'][-1]['depends_on'] = []
    elif mutation == 'extra_step': data['steps'].append({'id': 'P5', 'adapter_revision': 1, 'depends_on': ['P4']})
    elif mutation == 'adapter_revision': data['steps'][0]['adapter_revision'] = 999
    else: data['parameter_schema']['request_text']['default'] = 'prior enterprise goal'
    with pytest.raises((ValidationError, ValueError)): TemplateDraft.model_validate(data)


def test_same_key_concurrent_replay_and_changed_body_conflict(template_candidate):
    engine, repository, _ = template_candidate
    initial = engine.read('template-author', SCOPE)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: template_command(engine, 'SAVE_DRAFT', view=initial,
                                   key='lost-reply', draft=definition()), range(2)))
    assert results[0] == results[1]
    assert len(engine.read('template-author', SCOPE)['history']) == 1
    before = repository_snapshot(repository)
    with pytest.raises(Conflict): template_command(engine, 'SAVE_DRAFT', view=initial,
                                                   key='lost-reply', draft=definition(revision='2'))
    assert repository_snapshot(repository) == before


def test_changed_definition_cas_and_current_permit_before_replay(template_candidate):
    engine, repository, _ = template_candidate
    initial = engine.read('template-author', SCOPE)
    first = template_command(engine, 'SAVE_DRAFT', view=initial, key='first', draft=definition())
    before = repository_snapshot(repository)
    with pytest.raises(Conflict): template_command(engine, 'SAVE_DRAFT', view=initial, draft=definition(revision='2'))
    assert repository_snapshot(repository) == before
    contract = template_config().model_dump(mode='json')
    contract['revision'] += 1
    contract['permits'][0]['active'] = False
    engine.replace_contract(TemplateConfig.model_validate(contract))
    after_contract = repository_snapshot(repository)
    assert {k: v for k, v in after_contract.items() if k != 'template_contracts'} == {
        k: v for k, v in before.items() if k != 'template_contracts'}
    before = after_contract
    with pytest.raises(Denied): template_command(engine, 'SAVE_DRAFT', view=initial, key='first', draft=definition())
    assert repository_snapshot(repository) == before


def test_expired_source_cannot_be_published_or_consumed(template_candidate):
    engine, repository, now = template_candidate
    publish_template(engine)
    release = engine.public_catalog(PARK)['items'][0]
    before = repository_snapshot(repository)
    now[0] = datetime(2100, 1, 1, tzinfo=timezone.utc)
    assert not engine.public_catalog(PARK)['items']
    with pytest.raises((Denied, Conflict)): engine.published(SCOPE, release['release_id'], release['release_sha256'])
    assert repository_snapshot(repository) == before


def test_source_revision_is_immutable_and_new_version_requires_new_review(template_candidate):
    engine, repository, _ = template_candidate
    publish_template(engine)
    old = deepcopy(engine.public_catalog(PARK)['items'][0])
    template_command(engine, 'RETURN_DRAFT')
    changed = definition().model_dump(mode='json')
    changed['source']['statement'] = 'A changed source must not masquerade as the original revision'
    before = repository_snapshot(repository)
    with pytest.raises(Conflict): template_command(engine, 'SAVE_DRAFT', draft=TemplateDraft.model_validate(changed))
    assert repository_snapshot(repository) == before
    template_command(engine, 'SAVE_DRAFT', draft=definition(revision='2'))
    with pytest.raises(Conflict): template_command(engine, 'CANDIDATE_PUBLISH')
    template_command(engine, 'SUBMIT')
    template_command(engine, 'REVIEW')
    template_command(engine, 'CANDIDATE_PUBLISH')
    current = engine.public_catalog(PARK)['items'][0]
    assert current['release_id'] != old['release_id']
    assert current['snapshot']['definition']['source']['revision'] == '2'
    historical = engine.read('template-author', SCOPE)['releases'][0]
    assert historical['snapshot'] == old['snapshot']
    assert not historical['candidate_available']


def test_different_scope_and_current_publisher_revocation_cannot_consume_release(template_candidate):
    engine, repository, _ = template_candidate
    publish_template(engine)
    release = engine.public_catalog(PARK)['items'][0]
    other = Scope(park_id='unapproved-park', template_id=SCOPE.template_id)
    before = repository_snapshot(repository)
    with pytest.raises(Denied): engine.read('template-author', other)
    with pytest.raises(Denied): engine.published(other, release['release_id'], release['release_sha256'])
    config = template_config()
    config.revision += 1
    config.permits[2].active = False
    engine.replace_contract(config)
    after_contract = repository_snapshot(repository)
    assert {k: v for k, v in after_contract.items() if k != 'template_contracts'} == {
        k: v for k, v in before.items() if k != 'template_contracts'}
    before = after_contract
    assert not engine.public_catalog(PARK)['items']
    with pytest.raises(Denied): engine.published(SCOPE, release['release_id'], release['release_sha256'])
    assert repository_snapshot(repository) == before


def test_release_and_event_payloads_cannot_be_mutated_in_candidate_repository(template_candidate):
    engine, repository, _ = template_candidate
    publish_template(engine)
    before = repository_snapshot(repository)
    for sql in ("UPDATE template_releases SET payload='{}'", 'DELETE FROM template_releases',
                "UPDATE template_events SET payload='{}'", 'DELETE FROM template_events',
                "UPDATE template_contracts SET payload='{}'", 'DELETE FROM template_contracts'):
        with pytest.raises(sqlite3.IntegrityError):
            with repository.transaction() as c: c.execute(sql)
    assert repository_snapshot(repository) == before


@pytest.mark.parametrize('kind', ['empty', 'foreign', 'trigger_tampered'])
def test_existing_candidate_file_requires_exact_owned_schema(tmp_path, kind):
    path = tmp_path / 'existing.template.candidate.sqlite3'
    if kind == 'trigger_tampered':
        repository = TemplateRepository(path)
        with repository.transaction() as c: c.execute('DROP TRIGGER immutable_template_events_delete')
    else:
        with sqlite3.connect(path) as c:
            if kind == 'foreign': c.execute('CREATE TABLE foreign_records(id TEXT)')
    before = path.read_bytes()
    with pytest.raises(Conflict): TemplateRepository(path)
    assert path.read_bytes() == before


def test_candidate_reopen_is_stable_and_symlink_is_refused(template_candidate, tmp_path):
    engine, repository, _ = template_candidate
    publish_template(engine)
    before = repository_snapshot(repository)
    reopened = TemplateRepository(repository.path)
    assert repository_snapshot(reopened) == before
    linked = tmp_path / 'linked.template.candidate.sqlite3'
    linked.symlink_to(repository.path)
    with pytest.raises(ValueError): TemplateRepository(linked)
    assert repository_snapshot(repository) == before


def test_candidate_api_body_limit_and_no_cache_headers(template_candidate):
    from fastapi.testclient import TestClient
    from parkweave.template_candidate_api import create_template_candidate_app
    engine, repository, _ = template_candidate
    client = TestClient(create_template_candidate_app(engine))
    before = repository_snapshot(repository)
    response = client.post(f'/api/template-candidate/{PARK}/{SCOPE.template_id}/commands',
        headers={'X-Isolated-Template-Actor': 'template-author', 'Idempotency-Key': 'oversized',
                 'Content-Type': 'application/json'}, content=' ' * 16385)
    assert response.status_code == 413
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert repository_snapshot(repository) == before


def test_release_validity_must_fit_source_window(template_candidate):
    engine, repository, _ = template_candidate
    template_command(engine, 'SAVE_DRAFT', draft=definition())
    template_command(engine, 'SUBMIT')
    template_command(engine, 'REVIEW')
    before = repository_snapshot(repository)
    for field, value in [('valid_from', '2019-01-01T00:00:00+00:00'),
                         ('valid_until', '2100-01-01T00:00:00+00:00')]:
        validity = dict(VALID, **{field: value})
        with pytest.raises(Conflict): template_command(engine, 'CANDIDATE_PUBLISH', validity=validity)
    assert repository_snapshot(repository) == before


def advance_source_head(engine):
    return engine.command('template-author', SOURCE_SCOPE, 'source-head-revision-two',
        Command(action='SAVE_DRAFT', expected_revision=0, reason='Explicit newer synthetic source revision',
                draft=definition(revision='2')))


def test_source_head_invalidates_other_scope_release_and_cannot_be_rolled_back(template_candidate):
    engine, repository, _ = template_candidate
    publish_template(engine)
    release = deepcopy(engine.public_catalog(PARK)['items'][0])
    advance_source_head(engine)
    view = engine.read('template-author', SCOPE)
    assert view['state'] == 'PUBLISHED'
    assert not view['candidate_available']
    assert view['availability_reason'] == 'SOURCE_SUPERSEDED'
    assert view['releases'][0]['snapshot'] == release['snapshot']
    with pytest.raises(Denied): engine.published(SCOPE, release['release_id'], release['release_sha256'])
    template_command(engine, 'RETURN_DRAFT')
    before = repository_snapshot(repository)
    with pytest.raises(Conflict): template_command(engine, 'SAVE_DRAFT', draft=definition())
    with pytest.raises(Conflict): template_command(engine, 'SUBMIT')
    assert repository_snapshot(repository) == before


def test_contract_rollback_cannot_reactivate_old_release(template_candidate):
    engine, repository, _ = template_candidate
    publish_template(engine)
    old = template_config()
    revoked = old.model_copy(deep=True)
    revoked.revision = 2
    revoked.permits[2].active = False
    engine.replace_contract(revoked)
    assert not engine.public_catalog(PARK)['items']
    with pytest.raises(Conflict): engine.replace_contract(old)
    restored = old.model_copy(deep=True)
    restored.revision = 3
    engine.replace_contract(restored)
    assert not engine.public_catalog(PARK)['items']
    template_command(engine, 'RETURN_DRAFT')
    template_command(engine, 'SUBMIT')
    template_command(engine, 'REVIEW')
    template_command(engine, 'CANDIDATE_PUBLISH')
    assert len(engine.public_catalog(PARK)['items']) == 1
    assert len(engine.read('template-author', SCOPE)['releases']) == 2


def test_durable_contract_head_rejects_restart_with_previous_configuration(template_candidate):
    engine, repository, now = template_candidate
    publish_template(engine)
    release = deepcopy(engine.public_catalog(PARK)['items'][0])
    original = template_config()
    revoked = original.model_copy(deep=True)
    revoked.revision = 2
    revoked.permits[2].active = False
    engine.replace_contract(revoked)
    before = repository_snapshot(repository)
    with pytest.raises(Conflict):
        TemplateEngine(original, TemplateRepository(repository.path), lambda: now[0])
    assert repository_snapshot(repository) == before
    same_revision_changed = revoked.model_copy(deep=True)
    same_revision_changed.permits[2].active = True
    with pytest.raises(Conflict):
        TemplateEngine(same_revision_changed, TemplateRepository(repository.path), lambda: now[0])
    assert repository_snapshot(repository) == before
    restarted = TemplateEngine(revoked, TemplateRepository(repository.path), lambda: now[0])
    assert not restarted.public_catalog(PARK)['items']
    assert repository_snapshot(repository) == before
    restored = original.model_copy(deep=True)
    restored.revision = 3
    current = TemplateEngine(restored, TemplateRepository(repository.path), lambda: now[0])
    assert not current.public_catalog(PARK)['items']
    assert current.read('template-author', SCOPE)['releases'][0]['snapshot'] == release['snapshot']
    with pytest.raises(Denied): current.published(SCOPE, release['release_id'], release['release_sha256'])
    stable = repository_snapshot(repository)
    reopened = TemplateEngine(restored, TemplateRepository(repository.path), lambda: now[0])
    assert not reopened.public_catalog(PARK)['items']
    assert repository_snapshot(repository) == stable


def test_schema_one_candidate_is_refused_without_automatic_upgrade(tmp_path):
    path = tmp_path / 'legacy.template.candidate.sqlite3'
    repository = TemplateRepository(path)
    with repository.transaction() as c:
        c.execute('DROP TABLE template_contracts')
        c.execute('UPDATE template_meta SET version=1')
    before = path.read_bytes()
    with pytest.raises(Conflict): TemplateRepository(path)
    assert path.read_bytes() == before


def test_another_engine_advancing_contract_head_disables_old_live_engine_without_writes(template_candidate):
    old_engine, repository, now = template_candidate
    publish_template(old_engine)
    release = deepcopy(old_engine.public_catalog(PARK)['items'][0])
    stale_view = old_engine.read('template-author', SCOPE)
    newer = template_config()
    newer.revision = 2
    newer.permits[2].active = False
    current = TemplateEngine(newer, TemplateRepository(repository.path), lambda: now[0])
    assert not current.public_catalog(PARK)['items']
    before = repository_snapshot(repository)
    unauthorized_upgrade = template_config()
    unauthorized_upgrade.revision = 3
    for operation in (
        lambda: old_engine.read('template-author', SCOPE),
        lambda: old_engine.public_catalog(PARK),
        lambda: old_engine.published(SCOPE, release['release_id'], release['release_sha256']),
        lambda: template_command(old_engine, 'RETURN_DRAFT', view=stale_view),
        lambda: old_engine.replace_contract(template_config()),
        lambda: old_engine.replace_contract(unauthorized_upgrade),
    ):
        with pytest.raises(Denied): operation()
        assert repository_snapshot(repository) == before
