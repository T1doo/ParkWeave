"""Explicit isolated-PG bridge from a published candidate to fresh product records.

The durable SQLite journal records separate ordinary product transactions. A
pending or unknown stage is not completion; retry uses its original key/body.
No principal, Grant, assignment, source Case, or deployment schema is changed.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.conninfo import conninfo_to_dict

from . import preparation as prep, request_intents as intents
from . import bounded_planning as planning, service_case_steps as case_steps
from .domain import Intake
from .store import Conflict, Denied, digest

NAMESPACE = 'ISOLATED_SYNTHETIC_TEMPLATE_CONSUMER'
DB_PATTERN = r'^fixture_[0-9a-f]{32}$'


class ConsumerUnknown(RuntimeError):
    """The original operation may have committed; replay its saved key/body."""



def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def normal(value):
    return json.loads(canonical(value))


class OrgScope(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    park_id: str = Field(min_length=1, max_length=100)
    org_id: str = Field(min_length=1, max_length=100)


class ConsumerConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled_for_isolated_tests: bool = False
    allowed_database_names: list[str] = Field(default_factory=list, max_length=16)
    allowed_orgs: list[OrgScope] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def isolated(self):
        if any(not re.fullmatch(DB_PATTERN, name) for name in self.allowed_database_names):
            raise ValueError('exact isolated fixture UUID database names required')
        if len(set(self.allowed_database_names)) != len(self.allowed_database_names):
            raise ValueError('duplicate fixture database')
        scopes = [(s.park_id, s.org_id) for s in self.allowed_orgs]
        if len(set(scopes)) != len(scopes):
            raise ValueError('duplicate approved organization')
        if self.enabled_for_isolated_tests and (not scopes or not self.allowed_database_names):
            raise ValueError('explicit isolated database and organization allowlists required')
        return self


class Material(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    slot: Literal['need_summary', 'material_outline']
    text: str = Field(min_length=1, max_length=4000)
    source_kind: Literal['USER_STATEMENT', 'DOCUMENT_EXCERPT']
    source_label: str = Field(min_length=1, max_length=200)


class Consume(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    release_id: UUID = Field(strict=False)
    expected_release_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    goal: str = Field(min_length=1, max_length=2000)
    reviewer_id: str = Field(min_length=1, max_length=100)
    materials: list[Material] = Field(min_length=2, max_length=2)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def fresh(self):
        if {m.slot for m in self.materials} != set(prep.SLOTS):
            raise ValueError('each registered material slot requires explicit new source text')
        return self


class Resume(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ConsumerRepository:
    """A separate, schema-checked, exclusively created isolated journal file."""
    COLUMNS = {
        'consumer_meta': ['namespace', 'version'],
        'consumer_instances': ['id', 'actor', 'park', 'org', 'database_name', 'binding', 'input', 'state'],
        'consumer_requests': ['actor', 'key', 'fp', 'instance_id'],
        'consumer_stages': ['instance_id', 'name', 'request_key', 'body_sha256', 'body', 'state', 'result', 'error'],
    }

    TRIGGERS = {
        'consumer_binding_immutable': "CREATE TRIGGER consumer_binding_immutable BEFORE UPDATE OF id,actor,park,org,database_name,binding,input ON consumer_instances BEGIN SELECT RAISE(ABORT,'immutable consumer binding'); END",
        'consumer_request_update': "CREATE TRIGGER consumer_request_update BEFORE UPDATE ON consumer_requests BEGIN SELECT RAISE(ABORT,'immutable consumer request'); END",
        'consumer_request_delete': "CREATE TRIGGER consumer_request_delete BEFORE DELETE ON consumer_requests BEGIN SELECT RAISE(ABORT,'immutable consumer request'); END",
        'consumer_stage_body_immutable': "CREATE TRIGGER consumer_stage_body_immutable BEFORE UPDATE OF instance_id,name,request_key,body_sha256,body ON consumer_stages BEGIN SELECT RAISE(ABORT,'immutable consumer stage body'); END",
    }

    def __init__(self, path):
        self.path = Path(path).absolute()
        if not self.path.name.endswith('.consumer.candidate.sqlite3') or any(p.is_symlink() for p in [self.path, *self.path.parents]):
            raise ValueError('dedicated nonsymlink consumer journal required')
        new = False
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            os.close(fd)
            new = True
        except FileExistsError:
            if not self.path.is_file():
                raise ValueError('ordinary consumer journal file required')
        with sqlite3.connect(self.path) as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not new and (tables != set(self.COLUMNS) or any([r[1] for r in c.execute('PRAGMA table_info(' + t + ')')] != cols for t, cols in self.COLUMNS.items())):
                raise Conflict('foreign or partial consumer journal refused')
            if not new:
                triggers = {r[0]: ' '.join(r[1].split()) for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")}
                if triggers != {name: ' '.join(sql.split()) for name, sql in self.TRIGGERS.items()}:
                    raise Conflict('consumer journal immutable schema mismatch')
            if not new and c.execute('SELECT namespace,version FROM consumer_meta').fetchall() != [(NAMESPACE, 1)]:
                raise Conflict('consumer journal namespace mismatch')
            if new:
                c.executescript('''
                CREATE TABLE consumer_meta(namespace TEXT PRIMARY KEY,version INTEGER NOT NULL);
                CREATE TABLE consumer_instances(id TEXT PRIMARY KEY,actor TEXT NOT NULL,park TEXT NOT NULL,org TEXT NOT NULL,database_name TEXT NOT NULL,binding TEXT NOT NULL,input TEXT NOT NULL,state TEXT NOT NULL);
                CREATE TABLE consumer_requests(actor TEXT NOT NULL,key TEXT NOT NULL,fp TEXT NOT NULL,instance_id TEXT NOT NULL,PRIMARY KEY(actor,key));
                CREATE TABLE consumer_stages(instance_id TEXT NOT NULL,name TEXT NOT NULL,request_key TEXT NOT NULL,body_sha256 TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,result TEXT,error TEXT,PRIMARY KEY(instance_id,name));
                CREATE TRIGGER consumer_binding_immutable BEFORE UPDATE OF id,actor,park,org,database_name,binding,input ON consumer_instances BEGIN SELECT RAISE(ABORT,'immutable consumer binding'); END;
                CREATE TRIGGER consumer_request_update BEFORE UPDATE ON consumer_requests BEGIN SELECT RAISE(ABORT,'immutable consumer request'); END;
                CREATE TRIGGER consumer_request_delete BEFORE DELETE ON consumer_requests BEGIN SELECT RAISE(ABORT,'immutable consumer request'); END;
                CREATE TRIGGER consumer_stage_body_immutable BEFORE UPDATE OF instance_id,name,request_key,body_sha256,body ON consumer_stages BEGIN SELECT RAISE(ABORT,'immutable consumer stage body'); END;
                ''')
                c.execute('INSERT INTO consumer_meta VALUES(?,1)', (NAMESPACE,))

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=3)
        c.row_factory = sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield c
            c.commit()
        except sqlite3.OperationalError as error:
            c.rollback()
            raise Conflict('consumer journal busy; retry original key') from error
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()


class TemplateConsumer:
    def __init__(self, store, template_engine, config=None, repository=None):
        self.store = store
        self.template_engine = template_engine
        self.config = ConsumerConfig.model_validate((config or ConsumerConfig()).model_dump())
        self.repository = repository
        if self.config.enabled_for_isolated_tests:
            if repository is None:
                raise ValueError('explicit isolated consumer journal required')
            self.validate_fixture()

    def validate_fixture(self):
        if not self.config.enabled_for_isolated_tests:
            raise Denied('isolated template consumer disabled')
        options = conninfo_to_dict(self.store.dsn)
        host = options.get('host', '')
        if options.get('service') or options.get('hostaddr') not in (None, '127.0.0.1', '::1') or ',' in host or (host and host not in ('localhost', '127.0.0.1', '::1') and not host.startswith('/')):
            raise Denied('explicit local isolated PostgreSQL fixture required')
        if options.get('dbname') not in self.config.allowed_database_names:
            raise Denied('database is outside the explicit fixture allowlist')
        with self.store.connect() as c:
            row = c.execute('SELECT current_database() AS database_name,inet_server_addr()::text AS address').fetchone()
            if row['database_name'] != options['dbname'] or row['database_name'] not in self.config.allowed_database_names or not re.fullmatch(DB_PATTERN, row['database_name']) or row['address'] not in (None, '127.0.0.1', '::1'):
                raise Denied('actual PostgreSQL database is not the approved isolated fixture')
            return row['database_name']

    def _auth(self, token):
        database = self.validate_fixture()
        with self.store.connect() as c:
            p = self.store.auth(c, token, lock=True)
            prep.grant(self.store, c, p, 'PREPARE')
            self.store.check_capability(c, p, 'EXECUTE')
            if (p['park_id'], p['org_id']) not in {(s.park_id, s.org_id) for s in self.config.allowed_orgs}:
                raise Denied('organization is outside the explicit isolated consumer allowlist')
            if not c.execute('SELECT 1 FROM action_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND action=%s AND active', (p['id'], p['park_id'], p['org_id'], 'case.create')).fetchone():
                raise Denied('current original Case creation grant required')
            return p, database

    def _reviewer(self, p, reviewer_id):
        with self.store.connect() as c:
            self.store.lock_principal(c, reviewer_id)
            reviewer = c.execute('SELECT * FROM principals WHERE id=%s AND active', (reviewer_id,)).fetchone()
            if not reviewer or (reviewer['park_id'], reviewer['org_id']) != (p['park_id'], p['org_id']):
                raise Denied('current original reviewer scope required')
            prep.grant(self.store, c, reviewer, 'REVIEW_ASSIGNED')

    def _published(self, p, release_id, sha, scope=None):
        from .template_candidate import Scope
        if scope is None:
            catalog = self.template_engine.public_catalog(p['park_id'])
            entry = next((r for r in catalog['items'] if r['release_id'] == str(release_id)), None)
            if entry is None:
                raise Denied('published template unavailable')
            scope = entry['snapshot']['scope']
        if scope['park_id'] != p['park_id']:
            raise Denied('template park scope required')
        return self.template_engine.published(Scope.model_validate(scope), str(release_id), sha)

    def catalog(self, token):
        p, _ = self._auth(token)
        current = self.template_engine.public_catalog(p['park_id'])
        original = prep.catalog(self.store, token)
        templates = []
        for item in current['items']:
            snapshot = item['snapshot']
            definition = snapshot['definition']
            templates.append(dict(scope=snapshot['scope'], release_id=item['release_id'], release_sha256=item['release_sha256'],
                                  name=definition.get('name', definition.get('title', snapshot['scope']['template_id'])),
                                  definition=definition, required_goals=definition['required_goals'], state=item['state']))
        return dict(enabled=True, park_id=p['park_id'], org_id=p['org_id'], reviewers=original['reviewers'], templates=templates,
                    business_publication=False, new_grants=False, case_goal_completed=False)

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not key.strip() or len(key) > 128:
            raise Conflict('explicit bounded original request key required')
        return key

    def _instance(self, p, database, id):
        with self.repository.connect() as c:
            row = c.execute('SELECT * FROM consumer_instances WHERE id=? AND actor=? AND park=? AND org=? AND database_name=?',
                            (str(id), p['id'], p['park_id'], p['org_id'], database)).fetchone()
        if row is None:
            raise Denied('own isolated consumer instance unavailable')
        instance = dict(row)
        instance['binding'] = json.loads(instance['binding'])
        instance['input'] = json.loads(instance['input'])
        return instance

    def _available(self, p, instance):
        binding = instance['binding']
        release = self._published(p, binding['release_id'], binding['release_sha256'], binding['release_snapshot']['scope'])
        if normal(release['snapshot']) != binding['release_snapshot'] or release['snapshot']['definition_sha256'] != binding['definition_sha256']:
            raise Conflict('immutable published release binding changed')
        return release

    def _perform(self, token, instance, name, build, send):
        # Recheck both live authorities before every original product operation,
        # including a retry after an unknown response.
        p, database = self._auth(token)
        self._instance(p, database, instance['id'])
        self._available(p, instance)
        self._reviewer(p, instance['input']['reviewer_id'])
        with self.repository.connect(write=True) as c:
            stage = c.execute('SELECT * FROM consumer_stages WHERE instance_id=? AND name=?', (instance['id'], name)).fetchone()
            if stage is None:
                body = normal(build())
                key = 'tc:' + instance['id'] + ':' + name
                c.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)',
                          (instance['id'], name, key, digest(canonical(body)), canonical(body), 'STARTED'))
                stage = dict(instance_id=instance['id'], name=name, request_key=key, body_sha256=digest(canonical(body)), body=canonical(body), state='STARTED', result=None)
            else:
                stage = dict(stage)
            if digest(stage['body']) != stage['body_sha256']:
                raise Conflict('immutable stage body fingerprint changed')
        if stage['state'] == 'CONFIRMED':
            return json.loads(stage['result'])
        try:
            result = normal(send(stage['request_key'], json.loads(stage['body'])))
        except (Denied, Conflict) as error:
            code = 'PRODUCT_AUTHORIZATION_REFUSED' if isinstance(error, Denied) else 'PRODUCT_CONFLICT'
            try:
                with self.repository.connect(write=True) as c:
                    c.execute("UPDATE consumer_stages SET state='REFUSED',error=? WHERE instance_id=? AND name=? AND state<>'CONFIRMED'", (code, instance['id'], name))
                    c.execute("UPDATE consumer_instances SET state='BLOCKED' WHERE id=?", (instance['id'],))
            except Exception:
                # The product refusal is definite even if its journal update is busy.
                pass
            raise
        except Exception as error:
            self._unknown(instance, name)
            raise ConsumerUnknown('consumer operation reply is unknown; retry the original request') from error
        try:
            with self.repository.connect(write=True) as c:
                c.execute("UPDATE consumer_stages SET state='CONFIRMED',result=?,error=NULL WHERE instance_id=? AND name=?", (canonical(result), instance['id'], name))
        except Exception as error:
            self._unknown(instance, name)
            raise ConsumerUnknown('consumer confirmation reply is unknown; retry the original request') from error
        return result

    def _unknown(self, instance, name):
        try:
            with self.repository.connect(write=True) as c:
                c.execute("UPDATE consumer_stages SET state='UNKNOWN',error='REPLY_UNKNOWN' WHERE instance_id=? AND name=? AND state<>'CONFIRMED'", (instance['id'], name))
                c.execute("UPDATE consumer_instances SET state='UNKNOWN' WHERE id=?", (instance['id'],))
        except Exception:
            # STARTED already records an unresolved call if the journal is busy.
            pass

    def consume(self, token, key, data):
        p, database = self._auth(token)
        self._key(key)
        self._reviewer(p, data.reviewer_id)
        release = self._published(p, data.release_id, data.expected_release_sha256)
        snapshot = release['snapshot']
        fp = digest(canonical(dict(action='CONSUME', **data.model_dump(mode='json'))))
        with self.repository.connect(write=True) as c:
            old = c.execute('SELECT * FROM consumer_requests WHERE actor=? AND key=?', (p['id'], key)).fetchone()
            if old:
                if old['fp'] != fp:
                    raise Conflict('consumer request key fingerprint changed')
                id = old['instance_id']
            else:
                id = str(uuid4())
                binding = dict(actor_id=p['id'], park_id=p['park_id'], org_id=p['org_id'], database_name=database,
                               release_id=str(data.release_id), release_sha256=data.expected_release_sha256,
                               definition_sha256=snapshot['definition_sha256'], release_snapshot=snapshot)
                c.execute('INSERT INTO consumer_instances VALUES(?,?,?,?,?,?,?,?)', (id, p['id'], p['park_id'], p['org_id'], database, canonical(binding), canonical(data.model_dump(mode='json')), 'PENDING_RUN'))
                c.execute('INSERT INTO consumer_requests VALUES(?,?,?,?)', (p['id'], key, fp, id))
        instance = self._instance(p, database, id)
        self._perform(token, instance, 'CREATE_RUN', lambda: Intake(goal=data.goal).snapshot(),
                      lambda stage_key, body: dict(run_id=self.store.submit(token, stage_key, Intake.model_validate(body))))
        return self.read(token, id)

    def _stages(self, id):
        with self.repository.connect() as c:
            rows = c.execute('SELECT * FROM consumer_stages WHERE instance_id=? ORDER BY rowid', (id,)).fetchall()
        return [dict(name=r['name'], request_key=r['request_key'], body_sha256=r['body_sha256'], state=r['state'],
                     result=json.loads(r['result']) if r['result'] else None, error=r['error']) for r in rows]

    def read(self, token, id):
        p, database = self._auth(token)
        instance = self._instance(p, database, id)
        try:
            self._available(p, instance)
            available = True
        except (Denied, Conflict):
            available = False
        stages = self._stages(instance['id'])
        results = {s['name']: s['result'] for s in stages if s['state'] == 'CONFIRMED'}
        run_id = results.get('CREATE_RUN', {}).get('run_id')
        run = self.store.read(token, UUID(run_id)) if run_id else None
        preparation_id = results.get('CREATE_PREPARATION', {}).get('preparation_id')
        plan_id = results.get('ADOPT_PLAN', {}).get('plan_id')
        state = 'BLOCKED' if any(s['state'] == 'REFUSED' for s in stages) else 'UNKNOWN' if any(s['state'] in ('STARTED', 'UNKNOWN') for s in stages) else 'PLAN_ADOPTED' if plan_id else 'PENDING_RUN' if not run or run['state'] != 'SUCCEEDED' else 'PENDING_PREPARATION'
        if run and run['state'] in ('FAILED', 'CANCELLED'):
            state = 'RUN_BLOCKED'
        return dict(instance_id=instance['id'], state=state, run_id=run_id,
                    case_id=str(run['case']['id']) if run and run.get('case') else None,
                    preparation_id=preparation_id, plan_id=plan_id, run_state=run['state'] if run else None,
                    binding=instance['binding'], release_available=available, stages=stages,
                    issues=[dict(stage=s['name'], code=s['error']) for s in stages if s['state'] == 'REFUSED'],
                    preparation=prep.read(self.store, token, UUID(preparation_id)) if preparation_id else None,
                    service_case_plan=case_steps.read(self.store, token, UUID(preparation_id)) if plan_id else None,
                    new_grants=False, automatic_execution=False, business_publication=False, case_goal_completed=False)

    def instances(self, token):
        p, database = self._auth(token)
        with self.repository.connect() as c:
            rows = c.execute('SELECT id FROM consumer_instances WHERE actor=? AND park=? AND org=? AND database_name=? ORDER BY rowid DESC LIMIT 101', (p['id'], p['park_id'], p['org_id'], database)).fetchall()
        return dict(items=[self.read(token, row['id']) for row in rows[:100]], has_older_records=len(rows) > 100, new_grants=False, case_goal_completed=False)

    def resume(self, token, id, key):
        p, database = self._auth(token)
        self._key(key)
        instance = self._instance(p, database, id)
        self._available(p, instance)
        self._reviewer(p, instance['input']['reviewer_id'])
        fp = digest(canonical(dict(action='RESUME', instance_id=instance['id'])))
        with self.repository.connect(write=True) as c:
            old = c.execute('SELECT * FROM consumer_requests WHERE actor=? AND key=?', (p['id'], key)).fetchone()
            if old and (old['fp'] != fp or old['instance_id'] != instance['id']):
                raise Conflict('consumer resume request key scope changed')
            if not old:
                c.execute('INSERT INTO consumer_requests VALUES(?,?,?,?)', (p['id'], key, fp, instance['id']))
        source = instance['input']
        run = self._perform(token, instance, 'CREATE_RUN', lambda: Intake(goal=source['goal']).snapshot(),
                            lambda stage_key, body: dict(run_id=self.store.submit(token, stage_key, Intake.model_validate(body))))
        current = self.store.read(token, UUID(run['run_id']))
        if current['state'] != 'SUCCEEDED':
            return self.read(token, id)
        definition = instance['binding']['release_snapshot']['definition']
        preparation = self._perform(token, instance, 'CREATE_PREPARATION',
            lambda: dict(run_id=run['run_id'], service_id=definition['service_id'], service_version=definition['service_version'], reviewer_id=source['reviewer_id']),
            lambda stage_key, body: prep.create(self.store, token, stage_key, prep.CreatePreparation.model_validate(body)))
        preparation_id = UUID(preparation['preparation_id'])
        def current_revision():
            return prep.read(self.store, token, preparation_id)['preparation']['revision']
        self._perform(token, instance, 'SAVE_REQUEST',
            lambda: dict(expected_preparation_revision=current_revision(), request_text=source['goal'], required_goals=definition['required_goals']),
            lambda stage_key, body: intents.save(self.store, token, preparation_id, stage_key, intents.Save.model_validate(body)))
        for material in sorted(source['materials'], key=lambda m: prep.SLOTS.index(m['slot'])):
            self._perform(token, instance, 'ADD_' + material['slot'],
                lambda material=material: dict(action='ADD_EVIDENCE', expected_revision=current_revision(), **material),
                lambda stage_key, body: prep.command(self.store, token, preparation_id, stage_key, prep.PreparationCommand.model_validate(body)))
        def adoption():
            parent = prep.read(self.store, token, preparation_id)['preparation']
            preview = planning.read(self.store, token, preparation_id)['current']
            return dict(expected_preparation_revision=parent['revision'], expected_request_revision=parent['request_intent']['revision'],
                        expected_source_sha256=preview['source_sha256'], expected_plan_revision=0,
                        required_goals=definition['required_goals'], reason=source['reason'])
        self._perform(token, instance, 'ADOPT_PLAN', adoption,
            lambda stage_key, body: case_steps.adopt(self.store, token, preparation_id, stage_key, case_steps.Adopt.model_validate(body)))
        with self.repository.connect(write=True) as c:
            c.execute("UPDATE consumer_instances SET state='PLAN_ADOPTED' WHERE id=?", (instance['id'],))
        return self.read(token, id)


ConsumerEngine = TemplateConsumer


def install_routes(app, consumer):
    from fastapi import Header
    from fastapi.responses import JSONResponse

    @app.exception_handler(ConsumerUnknown)
    async def unknown(request, error):
        return JSONResponse(dict(detail='Original product reply is unknown; retry the original request key and body.', state='UNKNOWN', retry_original_request=True), status_code=503)

    def bearer(authorization):
        if not authorization or not authorization.startswith('Bearer ') or not authorization[7:].strip():
            raise Denied('original Bearer authentication required')
        return authorization[7:]

    @app.get('/api/template-consumer/catalog')
    def catalog(authorization: str | None = Header(default=None)):
        return consumer.catalog(bearer(authorization))

    @app.post('/api/template-consumer/catalog')
    def catalog_post(data: Resume, authorization: str | None = Header(default=None)):
        return consumer.catalog(bearer(authorization))

    @app.get('/api/template-consumer/instances')
    def instances(authorization: str | None = Header(default=None)):
        return consumer.instances(bearer(authorization))

    @app.post('/api/template-consumer/instances', status_code=201)
    def consume(data: Consume, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return consumer.consume(bearer(authorization), idempotency_key, data)

    @app.get('/api/template-consumer/instances/{instance_id}')
    def read(instance_id: UUID, authorization: str | None = Header(default=None)):
        return consumer.read(bearer(authorization), instance_id)

    @app.post('/api/template-consumer/instances/{instance_id}/resume')
    def resume(instance_id: UUID, data: Resume, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return consumer.resume(bearer(authorization), instance_id, idempotency_key)
