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
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .planning_constraints import Constraints
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

    required_goals: list[Annotated[str, Field(min_length=1, max_length=160)]] | None = Field(default=None, min_length=1, max_length=8)
    planning_constraints: Constraints | None = None

    @field_validator('required_goals', 'planning_constraints', mode='before')
    @classmethod
    def explicit_null(cls, value):
        if value is None: raise ValueError('omit optional planning declarations rather than null')
        return value

    @model_validator(mode='after')
    def fresh(self):
        if {m.slot for m in self.materials} != set(prep.SLOTS):
            raise ValueError('each registered material slot requires explicit new source text')
        if self.required_goals is not None and len(set(self.required_goals + (self.planning_constraints.additional_requirements if self.planning_constraints else []))) > 8:
            raise ValueError('all mandatory goals and conditions must fit the eight-goal contract')
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

    @staticmethod
    def _stage_key(instance_id, name):
        key = 'tc_' + UUID(instance_id).hex + '_' + name
        # Existing dependency journals accept at most 100 ASCII characters.
        # Retain all old stage keys; hash only the new long per-request names.
        return key if len(key) <= 100 else 'tc_' + UUID(instance_id).hex + '_' + digest(name)

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
                key = self._stage_key(instance['id'], name)
                c.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)',
                          (instance['id'], name, key, digest(canonical(body)), canonical(body), 'STARTED'))
                stage = dict(instance_id=instance['id'], name=name, request_key=key, body_sha256=digest(canonical(body)), body=canonical(body), state='STARTED', result=None, fresh_attempt=True)
            else:
                stage = dict(stage)
                stage['fresh_attempt'] = stage['state'] == 'ADMITTED'
                if stage['state'] == 'ADMITTED':
                    c.execute("UPDATE consumer_stages SET state='STARTED' WHERE instance_id=? AND name=? AND state='ADMITTED'", (instance['id'], name))
                    stage['state'] = 'STARTED'
                elif stage['state'] == 'REFUSED' and name.startswith(('EDIT_REQUEST_', 'CONFIRM_PLAN_')):
                    raise Conflict('planning admission was definitely refused; explicitly retry its original key')
            if digest(stage['body']) != stage['body_sha256']:
                raise Conflict('immutable stage body fingerprint changed')
        if stage['state'] == 'CONFIRMED':
            return json.loads(stage['result'])
        try:
            result = normal(send(stage['request_key'], json.loads(stage['body'])))
        except (Denied, Conflict) as error:
            if name.startswith(('EDIT_REQUEST_', 'CONFIRM_PLAN_')) and not stage['fresh_attempt']:
                self._unknown(instance, name)
                raise  # Current refusal cannot disprove an earlier unknown commit.
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
        if data.required_goals is not None and not set(snapshot['definition']['required_goals']) <= set(data.required_goals):
            raise Conflict('template mandatory goals cannot be removed')
        declared = data.required_goals if data.required_goals is not None else snapshot['definition']['required_goals']
        if len(set(declared + (data.planning_constraints.additional_requirements if data.planning_constraints else []))) > 8:
            raise Conflict('all template goals and declared conditions must fit the eight-goal contract')
        fp = digest(canonical(dict(action='CONSUME', **data.model_dump(mode='json', exclude_none=True))))
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
                c.execute('INSERT INTO consumer_instances VALUES(?,?,?,?,?,?,?,?)', (id, p['id'], p['park_id'], p['org_id'], database, canonical(binding), canonical(data.model_dump(mode='json', exclude_none=True)), 'PENDING_RUN'))
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
        journal_plan_id = results.get('ADOPT_PLAN', {}).get('plan_id') or next((s['result']['plan_id'] for s in reversed(stages) if s['name'].startswith('CONFIRM_PLAN_') and s['state']=='CONFIRMED'), None)
        service_plan=None
        if preparation_id:
            with self.store.connect() as c:
                actor,parent=case_steps._context(self.store,c,token,UUID(preparation_id))
                if str(parent['run_id'])!=run_id:raise Conflict('original consumer preparation Run binding changed')
                service_plan=case_steps._view(self.store,c,actor,parent,deepcopy(parent.get('service_case_plan')),observe=False)
        plan_id=service_plan['plan_id'] if service_plan else None
        state = 'PLAN_ADOPTED' if plan_id else 'BLOCKED' if any(s['state'] == 'REFUSED' for s in stages) else 'UNKNOWN' if any(s['state'] in ('ADMITTED', 'STARTED', 'UNKNOWN') for s in stages) else 'PENDING_RUN' if not run or run['state'] != 'SUCCEEDED' else 'PLAN_CONFIRMATION_REQUIRED' if preparation_id else 'PENDING_PREPARATION'
        if run and run['state'] in ('FAILED', 'CANCELLED'):
            state = 'RUN_BLOCKED'
        return dict(instance_id=instance['id'], actor_ref=case_steps.cp._hash(dict(actor_id=p['id'])), state=state, run_id=run_id,
                    case_id=str(run['case']['id']) if run and run.get('case') else None,
                    preparation_id=preparation_id, plan_id=plan_id, journal_plan_id=journal_plan_id, run_state=run['state'] if run else None,
                    binding=instance['binding'], release_available=available, stages=stages,
                    issues=[dict(stage=s['name'], code=s['error']) for s in stages if s['state'] == 'REFUSED'],
                    preparation=prep.read(self.store, token, UUID(preparation_id)) if preparation_id else None,
                    service_case_plan=service_plan if plan_id else None,
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
            lambda: dict(expected_preparation_revision=current_revision(), request_text=source['goal'], required_goals=source.get('required_goals', definition['required_goals']), **({'planning_constraints': source['planning_constraints']} if 'planning_constraints' in source else {})),
            lambda stage_key, body: intents.save(self.store, token, preparation_id, stage_key, intents.Save.model_validate(body)))
        for material in sorted(source['materials'], key=lambda m: prep.SLOTS.index(m['slot'])):
            self._perform(token, instance, 'ADD_' + material['slot'],
                lambda material=material: dict(action='ADD_EVIDENCE', expected_revision=current_revision(), **material),
                lambda stage_key, body: prep.command(self.store, token, preparation_id, stage_key, prep.PreparationCommand.model_validate(body)))
        self.reconcile_adoption(token, id, persist=True)
        # Preparing materials never authorizes adoption. Historical confirmed
        # ADOPT_PLAN stages remain readable, but new and incomplete instances
        # require a separately submitted exact preview confirmation.
        return self.read(token, id)

    def reconcile_adoption(self, token, id, *, persist=False):
        p,database=self._auth(token)
        instance=self._instance(p,database,id)
        self._available(p,instance)
        self._reviewer(p,instance['input']['reviewer_id'])
        with self.repository.connect() as c:
            raw=c.execute("SELECT * FROM consumer_stages WHERE instance_id=? AND name='ADOPT_PLAN'",(instance['id'],)).fetchone()
            created=c.execute("SELECT result FROM consumer_stages WHERE instance_id=? AND name='CREATE_PREPARATION' AND state='CONFIRMED'",(instance['id'],)).fetchone()
            created_run=c.execute("SELECT result FROM consumer_stages WHERE instance_id=? AND name='CREATE_RUN' AND state='CONFIRMED'",(instance['id'],)).fetchone()
        if raw is None:return dict(status='NO_REQUEST',automatically_replayed=False,product_read_only=True)
        stage=dict(raw)
        if not created or not created_run or digest(stage['body'])!=stage['body_sha256']:raise Conflict('original legacy adoption journal proof invalid')
        preparation_id=UUID(json.loads(created['result'])['preparation_id'])
        try:data=case_steps.Adopt.model_validate(json.loads(stage['body']))
        except (ValueError,TypeError):raise Conflict('original legacy adoption request body invalid')
        proof=case_steps.recover(self.store,token,preparation_id,stage['request_key'],expected_request=data)
        if proof['run_id']!=json.loads(created_run['result'])['run_id'] or proof['preparation_id']!=str(preparation_id):raise Conflict('legacy original preparation Run receipt binding changed')
        if not proof.get('saved_request_verified'):raise Conflict('original legacy adoption request proof unavailable')
        state=None;result=None
        if proof['status']=='COMMITTED':
            status='COMMITTED';state='CONFIRMED';result=dict(plan_id=proof['event']['plan_id'],original_adoption_receipt=proof['event'])
        elif proof.get('not_committed_final'):
            status='NOT_COMMITTED_STALE';state='REFUSED';result=dict(original_request_not_committed=True,proof=proof)
        elif stage['state']=='REFUSED':status='REFUSED'
        else:status='NOT_OBSERVED'
        if persist and state and stage['state'] in ('STARTED','UNKNOWN'):
            # Recheck current authorities before changing only this journal.
            current,current_database=self._auth(token)
            self._instance(current,current_database,id);self._available(current,instance)
            self._reviewer(current,instance['input']['reviewer_id'])
            with self.repository.connect(write=True) as c:
                c.execute("UPDATE consumer_stages SET state=?,result=?,error=? WHERE instance_id=? AND name='ADOPT_PLAN' AND request_key=? AND body_sha256=? AND state IN ('STARTED','UNKNOWN')",
                          (state,canonical(result),None if state=='CONFIRMED' else 'LEGACY_NOT_COMMITTED_STALE',instance['id'],stage['request_key'],stage['body_sha256']))
        return dict(status=status,original_request_key=stage['request_key'],receipt=proof,
                    automatically_replayed=False,product_read_only=True)

    def planning(self, token, id):
        p, database = self._auth(token)
        instance = self._instance(p, database, id)
        self._available(p, instance)
        self._reviewer(p, instance['input']['reviewer_id'])
        results = {s['name']: s['result'] for s in self._stages(instance['id']) if s['state']=='CONFIRMED'}
        preparation_id = results.get('CREATE_PREPARATION', {}).get('preparation_id')
        if not preparation_id or not {'SAVE_REQUEST','ADD_need_summary','ADD_material_outline'} <= set(results): raise Conflict('resume and verify all original materials before planning')
        # One original parent/dispatch/Case locking context. Request, preview and
        # confirmation sources come from the same read, without observing writes.
        with self.store.connect() as c:
            actor, parent = case_steps._context(self.store, c, token, UUID(preparation_id))
            if str(parent['run_id']) != results.get('CREATE_RUN', {}).get('run_id'):
                raise Conflict('original consumer preparation Run binding changed')
            view = case_steps._view(self.store, c, actor, parent, deepcopy(parent.get('service_case_plan')), observe=False)
            return dict(instance_id=instance['id'], actor_ref=view['actor_ref'], run_id=str(parent['run_id']), case_id=str(parent['case_id']),
                        preparation_id=str(parent['id']), plan_id=view['plan_id'],
                        request_intent=intents.view(parent), current=view['current_preview'], service_case_plan=view,
                        model_inference=False, automatic_adoption=False)

    def _planning_command(self, token, id, key, data, adopt=False):
        p, database = self._auth(token)
        self._key(key)
        instance = self._instance(p, database, id)
        self._available(p, instance)
        self._reviewer(p, instance['input']['reviewer_id'])
        row = self.read(token, id)
        if not row['preparation_id']: raise Conflict('original preparation required')
        body = data.model_dump(exclude_none=True)
        action = 'CONFIRM_PLAN' if adopt else 'EDIT_REQUEST'
        stage_name = action + '_' + digest(key)
        fp = digest(canonical(dict(action=action, instance_id=instance['id'], body=body)))
        with self.repository.connect(write=True) as c:
            old = c.execute('SELECT * FROM consumer_requests WHERE actor=? AND key=?', (p['id'], key)).fetchone()
            if old and (old['fp'] != fp or old['instance_id'] != instance['id']):
                raise Conflict('planning request key arguments changed')
            existing=c.execute('SELECT state FROM consumer_stages WHERE instance_id=? AND name=?',(instance['id'],stage_name)).fetchone()
            if adopt and existing and existing['state'] in ('ADMITTED','STARTED','UNKNOWN'):
                raise Conflict('original adoption outcome is unresolved; GET its original consumer key without resending ADOPT')
            completed = {r['name'] for r in c.execute("SELECT name FROM consumer_stages WHERE instance_id=? AND state='CONFIRMED'", (instance['id'],)).fetchall()}
            if not {'SAVE_REQUEST','ADD_need_summary','ADD_material_outline'} <= completed:
                raise Conflict('verify all original material stage outcomes before planning commands')
            if c.execute("SELECT 1 FROM consumer_stages WHERE instance_id=? AND state IN ('ADMITTED','STARTED','UNKNOWN') AND name<>?", (instance['id'], stage_name)).fetchone():
                raise Conflict('resolve the original pending stage key and body before another planning command')
            if not old:
                if row['plan_id'] or c.execute("SELECT 1 FROM consumer_stages WHERE instance_id=? AND state='CONFIRMED' AND (name='ADOPT_PLAN' OR name LIKE 'CONFIRM_PLAN_%')", (instance['id'],)).fetchone(): raise Conflict('adopted instance is historical; use original plan entry')
                mandatory = instance['binding']['release_snapshot']['definition']['required_goals']
                if not set(mandatory) <= set(data.required_goals): raise Conflict('template mandatory goals cannot be removed')
                c.execute('INSERT INTO consumer_requests VALUES(?,?,?,?)', (p['id'], key, fp, instance['id']))
            if not c.execute('SELECT 1 FROM consumer_stages WHERE instance_id=? AND name=?', (instance['id'], stage_name)).fetchone():
                saved = canonical(normal(body))
                c.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)',
                          (instance['id'], stage_name, self._stage_key(instance['id'], stage_name), digest(saved), saved, 'ADMITTED'))
            else:
                c.execute("UPDATE consumer_stages SET state='ADMITTED',error=NULL WHERE instance_id=? AND name=? AND state='REFUSED'", (instance['id'], stage_name))
        preparation_id = UUID(row['preparation_id'])
        try:
            self._perform(token, instance, stage_name, lambda: body,
                          lambda stage_key, saved: case_steps.adopt(self.store, token, preparation_id, stage_key, case_steps.Adopt.model_validate(saved), unadopted_only=True) if adopt
                          else intents.save(self.store, token, preparation_id, stage_key, intents.Save.model_validate(saved), unadopted_only=True))
        except (Denied, Conflict):
            # A definite current-authority refusal can occur between admission
            # and _perform's recheck, before it reaches its product-send handler.
            try:
                with self.repository.connect(write=True) as c:
                    c.execute("UPDATE consumer_stages SET state='REFUSED',error='CURRENT_OPERATION_REFUSED' WHERE instance_id=? AND name=? AND state='ADMITTED'", (instance['id'], stage_name))
            except Exception:
                pass  # Preserve the original refusal; an unresolved journal stays blocking.
            raise
        return self.read(token, id)

    def planning_recovery(self,token,id,key):
        """Read an exact consumer-to-original receipt proof; never send or repair."""
        p,database=self._auth(token);self._key(key)
        instance=self._instance(p,database,id)
        self._available(p,instance);self._reviewer(p,instance['input']['reviewer_id'])
        name='CONFIRM_PLAN_'+digest(key)
        with self.repository.connect() as c:
            request=c.execute('SELECT * FROM consumer_requests WHERE actor=? AND key=?',(p['id'],key)).fetchone()
            raw=c.execute('SELECT * FROM consumer_stages WHERE instance_id=? AND name=?',(instance['id'],name)).fetchone()
            created=c.execute("SELECT result FROM consumer_stages WHERE instance_id=? AND name='CREATE_PREPARATION' AND state='CONFIRMED'",(instance['id'],)).fetchone()
            run=c.execute("SELECT result FROM consumer_stages WHERE instance_id=? AND name='CREATE_RUN' AND state='CONFIRMED'",(instance['id'],)).fetchone()
        if not request or not raw or not created or not run:raise Conflict('exact original consumer adoption admission required')
        stage=dict(raw)
        if (request['instance_id']!=instance['id'] or stage['request_key']!=self._stage_key(instance['id'],name) or
            digest(stage['body'])!=stage['body_sha256']):raise Conflict('immutable consumer adoption scope or body proof changed')
        try:data=case_steps.Adopt.model_validate(json.loads(stage['body']))
        except (ValueError,TypeError):raise Conflict('original consumer adoption body invalid')
        body=data.model_dump(exclude_none=True)
        if request['fp']!=digest(canonical(dict(action='CONFIRM_PLAN',instance_id=instance['id'],body=body))):
            raise Conflict('original consumer adoption request fingerprint changed')
        mandatory=instance['binding']['release_snapshot']['definition']['required_goals']
        if not set(mandatory)<=set(data.required_goals):raise Conflict('original template mandatory goals missing')
        preparation_id=UUID(json.loads(created['result'])['preparation_id'])
        proof=case_steps.recover(self.store,token,preparation_id,stage['request_key'],expected_request=data)
        if (proof['preparation_id']!=str(preparation_id) or proof['run_id']!=json.loads(run['result'])['run_id'] or
            not proof.get('saved_request_verified')):raise Conflict('original consumer preparation Run receipt binding changed')
        # Recheck the live candidate and actor after any original source wait.
        current,current_database=self._auth(token);self._instance(current,current_database,id)
        self._available(current,instance);self._reviewer(current,instance['input']['reviewer_id'])
        status='COMMITTED' if proof['status']=='COMMITTED' else 'NOT_COMMITTED_STALE' if proof.get('not_committed_final') else 'REFUSED' if stage['state']=='REFUSED' else 'NOT_OBSERVED'
        return dict(instance_id=instance['id'],actor_ref=case_steps.cp._hash(dict(actor_id=p['id'])),
            consumer_request_key=key,original_request_key=stage['request_key'],body_sha256=stage['body_sha256'],
            original_request=dict(expected_preparation_revision=data.expected_preparation_revision,
                expected_request_revision=data.expected_request_revision,expected_source_sha256=data.expected_source_sha256,
                partial_adoption=data.partial_adoption is True,required_goals=list(data.required_goals)),
            status=status,receipt=proof,instance=self.read(token,id),
            automatically_replayed=False,product_read_only=True,journal_read_only=True,case_goal_completed=False)

    @contextmanager
    def _planning_key_lock(self, token, id, key):
        # Serialize only identical consumer request keys across engine/process
        # instances. Different keys still compete at the durable admission gate.
        self._key(key)
        p, database = self._auth(token)
        instance = self._instance(p, database, id)
        path = self.repository.path.with_name(self.repository.path.name + '.' + instance['id'] + '.' + digest(key) + '.planning.lock')
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0: os.write(fd, b'0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == 'nt':
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def edit_planning(self, token, id, key, data):
        with self._planning_key_lock(token, id, key):
            return self._planning_command(token, id, key, data)

    def confirm_plan(self, token, id, key, data):
        with self._planning_key_lock(token, id, key):
            return self._planning_command(token, id, key, data, adopt=True)



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

    @app.get('/api/template-consumer/instances/{instance_id}/adoption-reconciliation')
    def adoption_proof(instance_id: UUID, authorization: str | None = Header(default=None)):
        return consumer.reconcile_adoption(bearer(authorization),instance_id)

    @app.post('/api/template-consumer/instances/{instance_id}/adoption-reconciliation')
    def reconcile_adoption(instance_id: UUID, data: Resume, authorization: str | None = Header(default=None)):
        proof=consumer.reconcile_adoption(bearer(authorization),instance_id,persist=True)
        return dict(**consumer.read(bearer(authorization),instance_id),adoption_reconciliation=proof)

    @app.get('/api/template-consumer/instances/{instance_id}/planning')
    def planning_read(instance_id: UUID, authorization: str | None = Header(default=None)):
        return consumer.planning(bearer(authorization), instance_id)

    @app.post('/api/template-consumer/instances/{instance_id}/planning')
    def planning_edit(instance_id: UUID, data: intents.Save, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return consumer.edit_planning(bearer(authorization), instance_id, idempotency_key, data)

    @app.post('/api/template-consumer/instances/{instance_id}/adopt')
    def planning_adopt(instance_id: UUID, data: case_steps.Adopt, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return consumer.confirm_plan(bearer(authorization), instance_id, idempotency_key, data)

    @app.get('/api/template-consumer/instances/{instance_id}/planning-recovery')
    def planning_recovery(instance_id: UUID, authorization: str | None = Header(default=None), idempotency_key: str = Header()):
        return consumer.planning_recovery(bearer(authorization),instance_id,idempotency_key)


