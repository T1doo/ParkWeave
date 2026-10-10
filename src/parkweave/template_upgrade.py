"""Default-off per-instance inspection and decisions; never migrate business data."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from . import preparation as prep, service_case_steps as plans
from .template_candidate import TemplateDraft, sha
from .template_consumer import canonical, normal
from .store import Conflict, Denied

NAMESPACE = 'ISOLATED_TEMPLATE_UPGRADE_INSPECTION'
FLAGS = dict(namespace=NAMESPACE, migration_performed=False, automatic_execution=False,
             new_grants=False, business_publication=False, case_goal_completed=False)


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    target_release_id: UUID = Field(strict=False)
    expected_target_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_check_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expected_revision: int = Field(ge=0, le=63)
    choice: Literal['KEEP_CURRENT', 'REQUEST_RECHECK', 'ACK_COMPATIBLE']
    reason: str = Field(min_length=1, max_length=1000)


class UpgradeRepository:
    """Separate immutable journal, with no migration of existing journals."""
    COLUMNS = {'upgrade_meta': ['namespace', 'version'],
               'upgrade_events': ['actor', 'key', 'fp', 'instance', 'revision', 'payload', 'hash']}
    TRIGGERS = {action: f"CREATE TRIGGER upgrade_no_{action.lower()} BEFORE {action} ON upgrade_events BEGIN SELECT RAISE(ABORT,'immutable upgrade event'); END"
                for action in ('UPDATE', 'DELETE')}

    def __init__(self, path):
        self.path = Path(path).absolute()
        if not self.path.name.endswith('.upgrade.candidate.sqlite3') or any(p.is_symlink() for p in [self.path, *self.path.parents]):
            raise ValueError('dedicated nonsymlink upgrade journal required')
        new = False
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            os.close(fd); new = True
        except FileExistsError:
            if not self.path.is_file():
                raise ValueError('ordinary upgrade journal required')
        with sqlite3.connect(self.path) as c:
            if new:
                c.executescript('CREATE TABLE upgrade_meta(namespace TEXT PRIMARY KEY,version INTEGER NOT NULL);'
                    'CREATE TABLE upgrade_events(actor TEXT NOT NULL,key TEXT NOT NULL,fp TEXT NOT NULL,instance TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,hash TEXT NOT NULL,PRIMARY KEY(actor,key),UNIQUE(actor,instance,revision));')
                for sql in self.TRIGGERS.values(): c.execute(sql)
                c.execute('INSERT INTO upgrade_meta VALUES(?,1)', (NAMESPACE,))
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            triggers = {r[0]: ' '.join(r[1].split()) for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")}
            if (tables != set(self.COLUMNS) or
                any([r[1] for r in c.execute('PRAGMA table_info(' + t + ')')] != cols for t, cols in self.COLUMNS.items()) or
                triggers != {f'upgrade_no_{a.lower()}': ' '.join(s.split()) for a, s in self.TRIGGERS.items()} or
                c.execute('SELECT namespace,version FROM upgrade_meta').fetchall() != [(NAMESPACE, 1)]):
                raise Conflict('foreign or incomplete upgrade journal refused')

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=3); c.row_factory = sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE' if write else 'BEGIN'); yield c; c.commit()
        except sqlite3.OperationalError as error:
            c.rollback(); raise Conflict('upgrade journal busy; recover original key') from error
        except BaseException:
            c.rollback(); raise
        finally: c.close()


class TemplateUpgradeChecker:
    def __init__(self, consumer, repository, *, enabled_for_isolated_tests=False):
        if not enabled_for_isolated_tests or not consumer.config.enabled_for_isolated_tests or not consumer.template_engine.config.enabled_for_isolated_tests:
            raise Denied('explicit original isolated consumer required')
        consumer.validate_fixture()
        self.consumer = consumer; self.engine = consumer.template_engine; self.repository = repository

    @contextmanager
    def _context(self, token, instance_id):
        consumer = self.consumer
        database = consumer.validate_fixture()
        with consumer.store.connect() as c:
            c.execute("SET LOCAL lock_timeout='3s'")
            p = consumer.store.auth(c, token, lock=True)
            prep.grant(consumer.store, c, p, 'PREPARE')
            consumer.store.check_capability(c, p, 'EXECUTE')
            if (p['park_id'], p['org_id']) not in {(s.park_id, s.org_id) for s in consumer.config.allowed_orgs}:
                raise Denied('original consumer organization required')
            if not c.execute("SELECT 1 FROM action_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND action='case.create' AND active", (p['id'], p['park_id'], p['org_id'])).fetchone():
                raise Denied('current original Case grant required')
            instance = consumer._instance(p, database, instance_id)
            stages = consumer._stages(instance['id'])
            preparation_id = next((s['result']['preparation_id'] for s in stages if s['name'] == 'CREATE_PREPARATION' and s['state'] == 'CONFIRMED'), None)
            if not preparation_id: raise Conflict('existing Case preparation required; unresolved consumption is not completion')
            parent = prep.scoped(consumer.store, c, p, UUID(preparation_id))
            case = c.execute('SELECT * FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s', (parent['case_id'], parent['run_id'], p['park_id'], p['org_id'])).fetchone()
            run_id = next((s['result']['run_id'] for s in stages if s['name'] == 'CREATE_RUN' and s['state'] == 'CONFIRMED'), None)
            if not case or str(parent['run_id']) != run_id: raise Conflict('original consumer Case binding changed')
            binding = instance['binding']
            if any(binding.get(k) != v for k, v in dict(actor_id=p['id'], park_id=p['park_id'], org_id=p['org_id'], database_name=database).items()):
                raise Conflict('original consumer scope proof changed')
            scope = dict(actor_id=p['id'], park_id=p['park_id'], org_id=p['org_id'], database_name=database,
                         instance_id=instance['id'], case_id=str(parent['case_id']), preparation_id=str(parent['id']))
            yield c, p, parent, case, stages, instance, scope

    def _history(self, c, scope):
        rows = c.execute('SELECT * FROM upgrade_events WHERE actor=? AND instance=? ORDER BY revision', (scope['actor_id'], scope['instance_id'])).fetchall()
        previous = None; events = []
        if len(rows) > 64: raise Conflict('upgrade journal bound changed')
        for revision, row in enumerate(rows, 1):
            try:
                event = json.loads(row['payload']); UUID(event['id'])
                valid = (event['scope'] == scope and row['revision'] == event['revision'] == revision and
                         event['previous_sha256'] == previous and event['request_key'] == row['key'] and
                         event['request_sha256'] == row['fp'] and sha(event) == row['hash'] and
                         event['check_sha256'] == sha(event['check']) and event['choice'] in event['check']['allowed_choices'])
            except (ValueError, TypeError, KeyError): valid = False
            if not valid: raise Conflict('immutable upgrade history proof changed')
            events.append(dict(**event, event_sha256=row['hash'])); previous = row['hash']
        return events

    def _check(self, context, release_id, target_sha, t):
        c, p, parent, case, stages, instance, scope = context
        self.engine._enabled(t)
        binding = instance['binding']; old = binding['release_snapshot']
        row = t.execute('SELECT * FROM template_releases WHERE id=?', (binding['release_id'],)).fetchone()
        if (not row or row['payload_sha'] != binding['release_sha256'] or sha(old) != row['payload_sha'] or
            json.loads(row['payload']) != old or old['definition_sha256'] != sha(old['definition']) or
            old['definition_sha256'] != binding['definition_sha256']):
            raise Conflict('original immutable template proof changed')
        TemplateDraft.model_validate(old['definition'])
        target = t.execute('SELECT * FROM template_releases WHERE id=? AND scope=?', (str(release_id), row['scope'])).fetchone()
        if not target: raise Denied('same original template target required')
        view = self.engine._available(t, target)
        if not view['candidate_available']: raise Denied('current reviewed target required')
        new = view['snapshot']
        current = t.execute('SELECT current_release FROM template_drafts WHERE scope=?', (row['scope'],)).fetchone()
        if current is None or current[0] != str(release_id): raise Conflict('target template head changed')
        if target['payload_sha'] != target_sha: raise Conflict('target release hash changed')
        if new['scope'] != old['scope'] or old['scope']['park_id'] != p['park_id']: raise Denied('same template park required')
        if str(release_id) == binding['release_id']: raise Conflict('distinct target revision required')
        TemplateDraft.model_validate(new['definition'])
        a, b = old['definition'], new['definition']
        breaking = (new['content_version'] <= old['content_version'] or
                    any(a[k] != b[k] for k in ('service_id', 'service_version', 'parameter_schema')) or
                    not set(a['required_goals']) <= set(b['required_goals']) or
                    any(step not in b['steps'] for step in a['steps']) or
                    old['registry_sha256'] != new['registry_sha256'] or old['contract_sha256'] != new['contract_sha256'])
        plan = deepcopy(parent.get('service_case_plan'))
        if plan:
            plans._recovery_proofs(parent)
            adoption_key = plan['events'][0]['request_key']
            if adoption_key.startswith('tc:') and adoption_key != 'tc:' + instance['id'] + ':ADOPT_PLAN':
                raise Conflict('legacy adoption key belongs to another template instance')
            binding_issues, issues, sources, actual, states, _ = plans._inspect(self.consumer.store, c, parent, plan, observe=False)
            locked = any(s.get('manual_lock') for s in plan['steps'])
        else:
            binding_issues, issues, sources, actual, states, locked = ['PLAN_REQUIRED'], {}, {}, {}, {}, False
        structure_changed = any(a[k] != b[k] for k in ('required_goals', 'steps', 'source'))
        unresolved = any(s['state'] != 'CONFIRMED' for s in stages)
        stale = bool(binding_issues or any(s.get('invalidated') for s in plan['steps']) if plan else True)
        # Issues on verified decisions need recheck; unfinished steps stay unfinished.
        stale = stale or bool(plan and any(s.get('verified_sha256') and issues[s['adapter_id']] for s in plan['steps']))
        needs = structure_changed or unresolved or stale
        changes = []
        if breaking: changes.append('DESTRUCTIVE_DEFINITION_OR_ROLLBACK')
        if a['source'] != b['source']: changes.append('TEMPLATE_SOURCE_CHANGED')
        if a['required_goals'] != b['required_goals'] or a['steps'] != b['steps']: changes.append('REGISTERED_GOALS_OR_STEPS_CHANGED')
        if stale: changes.append('CURRENT_CASE_DEPENDENCIES_REQUIRE_RECHECK')
        if unresolved: changes.append('UNRESOLVED_CONSUMER_STAGE')
        classification = 'BREAKING_REJECTED' if breaking else 'LOCK_CONFLICT' if any(s == 'LOCK_CONFLICT' for s in states.values()) or (locked and needs) else 'NEEDS_RECHECK' if needs else 'COMPATIBLE'
        allowed = ['KEEP_CURRENT']
        if classification in ('COMPATIBLE', 'NEEDS_RECHECK'): allowed.append('REQUEST_RECHECK')
        if classification == 'COMPATIBLE': allowed.append('ACK_COMPATIBLE')
        state_hash = sha(normal(dict(parent=parent, case=case, stages=stages, sources=sources, issues=issues, binding_issues=binding_issues)))
        # PostgreSQL inspection may have waited across an expiry boundary.
        if not self.engine._available(t, target)['candidate_available']:
            raise Denied('target expired during current Case inspection')
        return dict(**FLAGS, scope=scope, original_release_id=binding['release_id'], original_release_sha256=binding['release_sha256'],
                    target_release_id=str(release_id), target_release_sha256=target_sha,
                    original_definition_sha256=old['definition_sha256'], target_definition_sha256=new['definition_sha256'],
                    original_content_version=old['content_version'], target_content_version=new['content_version'],
                    original_source_revision=a['source']['revision'], target_source_revision=b['source']['revision'], changes=changes,
                    case_state_sha256=state_hash, classification=classification, allowed_choices=allowed,
                    locked_steps=[s['id'] for s in plan['steps'] if s.get('manual_lock')] if plan else [],
                    unresolved_stages=[s['name'] for s in stages if s['state'] != 'CONFIRMED'],
                    observed_step_states=states, future_validity_guaranteed=False)

    def inspect(self, token, instance_id, release_id, target_sha):
        with self._context(token, instance_id) as context, self.engine.lock, self.engine.repository.transaction() as t:
            check = self._check(context, release_id, target_sha, t)
            with self.repository.connect() as c: events = self._history(c, context[-1])
            return dict(check=check, check_sha256=sha(check), revision=len(events), history=events)

    def select(self, token, instance_id, key, data):
        self.consumer._key(key)
        fp = sha(dict(instance_id=str(instance_id), **data.model_dump(mode='json')))
        with self._context(token, instance_id) as context, self.engine.lock, self.engine.repository.transaction() as t, self.repository.connect(write=True) as c:
            events = self._history(c, context[-1])
            old = c.execute('SELECT * FROM upgrade_events WHERE actor=? AND key=?', (context[1]['id'], key)).fetchone()
            if old:
                if old['instance'] != str(instance_id) or old['fp'] != fp: raise Conflict('upgrade key body or instance changed')
                return dict(event=next(e for e in events if e['request_key'] == key), historical_only=True, **FLAGS)
            check = self._check(context, data.target_release_id, data.expected_target_sha256, t)
            if len(events) != data.expected_revision or sha(check) != data.expected_check_sha256:
                raise Conflict('upgrade check or audit revision changed')
            if data.choice not in check['allowed_choices']: raise Conflict('upgrade choice refused for this classification')
            event = dict(id=str(uuid4()), scope=context[-1], revision=len(events)+1, request_key=key, request_sha256=fp,
                         previous_sha256=events[-1]['event_sha256'] if events else None, check=check, check_sha256=sha(check),
                         choice=data.choice, reason=data.reason, **FLAGS)
            event_hash = sha(event)
            c.execute('INSERT INTO upgrade_events VALUES(?,?,?,?,?,?,?)', (context[1]['id'], key, fp, str(instance_id), event['revision'], canonical(event), event_hash))
            return dict(event=dict(**event, event_sha256=event_hash), historical_only=False, **FLAGS)

    def recover(self, token, instance_id, key):
        self.consumer._key(key)
        with self._context(token, instance_id) as context, self.repository.connect() as c:
            events = self._history(c, context[-1])
            row = c.execute('SELECT * FROM upgrade_events WHERE actor=? AND key=?', (context[1]['id'], key)).fetchone()
            if row and row['instance'] != str(instance_id): raise Conflict('upgrade recovery instance changed')
            return dict(event=next((e for e in events if e['request_key'] == key), None),
                        status='COMMITTED' if row else 'NOT_OBSERVED', historical_only=True, **FLAGS)


def install_routes(app, checker):
    from fastapi import Header

    def token(authorization):
        if not authorization or not authorization.startswith('Bearer '): raise Denied('original Bearer required')
        return authorization[7:]

    @app.get('/api/template-upgrade/{instance_id}/check')
    def inspect(instance_id: UUID, target_release_id: UUID, target_sha256: str, authorization: str | None = Header(default=None)):
        return checker.inspect(token(authorization), instance_id, target_release_id, target_sha256)

    @app.post('/api/template-upgrade/{instance_id}/choices')
    def select(instance_id: UUID, data: Selection, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return checker.select(token(authorization), instance_id, idempotency_key, data)

    @app.get('/api/template-upgrade/{instance_id}/requests/{key}')
    def recover(instance_id: UUID, key: str, authorization: str | None = Header(default=None)):
        return checker.recover(token(authorization), instance_id, key)
