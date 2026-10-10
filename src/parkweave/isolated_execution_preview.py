"""Actual registered preparation commands in a closed, rollback-only pg_temp.

Only independent SQLite preview artifacts persist. No business namespace writer,
production Grant, worker, model or resource executor is given to the adapter.
"""
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4
import json
import os
import re
import secrets
import sqlite3

from pydantic import BaseModel, ConfigDict, Field
from psycopg import sql
from psycopg.types.json import Jsonb

from . import bounded_planning as planning, preparation as prep, controlled_plans as cp, catalog_publication as catalogs
from .store import Store, Conflict, Denied, digest

SCOPE = 'ISOLATED_REGISTERED_P1_EXECUTION_PREVIEW'
TABLES = ('principals', 'capability_grants', 'preparation_grants', 'preparation_catalog',
          'preparations', 'preparation_evidence', 'preparation_events', 'controlled_plans')
VERSION = 2
IDENTITY_SQL = "SELECT current_database() name, oid::text oid, (SELECT system_identifier::text FROM pg_control_system()) system_identifier FROM pg_database WHERE datname=current_database()"
REGISTERED_SQL = frozenset((
    'INSERT INTO preparation_events(id,preparation_id,actor_id,request_key,fingerprint,revision,action,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
    "INSERT INTO preparation_evidence(id,preparation_id,slot,version,text,source_kind,source_label,source_sha256,actor_id,authenticity) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'UNVERIFIED') RETURNING *",
    'SELECT * FROM controlled_plans WHERE preparation_id=%s FOR UPDATE',
    'SELECT * FROM preparation_events WHERE actor_id=%s AND request_key=%s',
    'SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s FOR UPDATE',
    'SELECT * FROM principals WHERE token_hash=%s AND active',
    'SELECT 1 FROM capability_grants WHERE principal_id=%s AND capability=%s AND park_id=%s AND org_id=%s AND active',
    "SELECT 1 FROM preparation_events WHERE preparation_id=%s AND action='DECLARE_FACT_PURPOSE' LIMIT 1",
    'SELECT 1 FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability=%s AND active',
    'SELECT DISTINCT ON(slot) id,slot,version,text,source_kind,source_label,source_sha256,authenticity FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC',
    'SELECT id,park_id,org_id,role,active,xmin::text AS generation FROM principals WHERE id=ANY(%s) AND park_id=%s AND org_id=%s ORDER BY id',
    'SELECT id,payload,created_at FROM preparation_events WHERE preparation_id=%s AND action=%s ORDER BY revision',
    'SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
    'SELECT pg_advisory_xact_lock_shared(hashtextextended(%s,0))',
    "SELECT principal_id,capability,active,revision,xmin::text AS generation FROM capability_grants WHERE principal_id=ANY(%s) AND park_id=%s AND org_id=%s AND capability IN ('READ','EXECUTE') ORDER BY principal_id,capability",
    'SELECT principal_id,capability,active,xmin::text AS generation FROM preparation_grants WHERE principal_id=ANY(%s) AND park_id=%s AND org_id=%s ORDER BY principal_id,capability',
    'SELECT source,xmin::text AS generation FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
    'UPDATE preparations SET state=%s,revision=revision+1,review_sha256=%s,material_corrections=%s WHERE id=%s RETURNING *',
))

P1_ACTIONS = [
    {'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'enterprise_operator','commands':['ADD_EVIDENCE','CONFIRM']},
    {'method':'POST','path':'/api/preparations/{preparation_id}/commands','role':'park_specialist','commands':['REQUEST_CHANGES','REVIEW']},
]
P1_ACTIONS_SHA256 = digest(prep.canonical(P1_ACTIONS))
PROOF_FIELDS = ('binding','required_goals','goal_coverage','not_previewed','coverage_state','execution_contract_sha256')
EXECUTION_CONTRACT_SHA256 = digest(prep.canonical({'storage_version':VERSION,'adapter':'preparation','adapter_revision':1,
    'service_id':prep.SERVICE,'service_version':1,'actions':P1_ACTIONS,'sql_templates':sorted(REGISTERED_SQL)}))


def _registered(current):
    selected = [step for step in current['steps'] if step['id']=='P1']
    return (len(selected)==1 and not current['source_unknowns'] and selected[0]['adapter_ref']=='preparation' and
            type(selected[0]['adapter_revision']) is int and selected[0]['adapter_revision']==1 and selected[0]['depends_on']==[] and digest(prep.canonical(selected[0]['actions']))==P1_ACTIONS_SHA256 and
            selected[0]['request_service_ref']==prep.SERVICE and type(selected[0]['request_service_version']) is int and selected[0]['request_service_version']==1)


class Execute(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_preparation_revision: int = Field(ge=1, le=64)
    expected_request_revision: int = Field(ge=1, le=64)
    expected_source_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class Unavailable(Exception):
    """An outcome was not committed; callers must read, never auto-replay."""


class _ClosedConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        # The registered adapter has no arbitrary client SQL. Fail closed if a
        # future implementation reaches new tables, explicit schemas or commits.
        if not isinstance(query,str) or query not in REGISTERED_SQL:
            raise Denied('unregistered preview adapter SQL template')
        return self.connection.execute(query, params)


class _PreviewStore(Store):
    def __init__(self, connection):
        self.connection = _ClosedConnection(connection)

    @contextmanager
    def connect(self):
        # The command's original transaction context does not own the PG
        # connection and cannot commit it. The outer executor always rolls back.
        yield self.connection


def _identity(store):
    with store.connect() as c:
        return c.execute(IDENTITY_SQL).fetchone()


def _normal(value):
    return cp._normal(value)


def _sha(value):
    return digest(prep.canonical(value))


class IsolatedExecutionPreview:
    storage_scope = SCOPE
    attachment_attribute = '_isolated_execution_preview'

    def __init__(self, store, root, *, enabled_for_synthetic_preview=False):
        if enabled_for_synthetic_preview is not True:
            raise Denied('explicit synthetic execution preview required')
        if os.name != 'posix':
            raise Denied('isolated preview storage platform not validated')
        self.root = Path(root)
        if not self.root.is_absolute():
            raise Denied('absolute private preview directory required')
        for path in (self.root, *self.root.parents):
            if path.is_symlink():
                raise Denied('preview symlink directory refused')
        self.database_identity = _identity(store)
        self.path = self.root / 'preview.sqlite3'
        if not self.root.exists():
            self.root.mkdir(mode=0o700)
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            with sqlite3.connect(self.path) as db:
                db.executescript('''CREATE TABLE meta(value TEXT NOT NULL);
CREATE TABLE previews(owner TEXT NOT NULL, preparation TEXT NOT NULL, request_key TEXT NOT NULL,
 fingerprint TEXT NOT NULL, document TEXT NOT NULL, proof TEXT NOT NULL, PRIMARY KEY(owner,request_key));
CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END;
CREATE TRIGGER immutable_delete BEFORE DELETE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END;''')
                db.execute('INSERT INTO meta VALUES(?)', (prep.canonical(dict(scope=self.storage_scope, version=VERSION, id=str(uuid4()), database=self.database_identity)),))
        self._check_files()
        with self._database() as db:
            meta = json.loads(db.execute('SELECT value FROM meta').fetchone()[0])
            if (set(meta) != {'scope','version','id','database'} or meta['scope'] != self.storage_scope or
                    meta['version'] != VERSION or meta['database'] != self.database_identity):
                raise Denied('preview storage identity unavailable')
            UUID(meta['id'])
            self.namespace = meta['id']
        self._root_identity = (self.root.stat().st_dev,self.root.stat().st_ino)

    def _check_files(self):
        if any(path.is_symlink() for path in (self.root,*self.root.parents)):
            raise Denied('preview symlink directory refused')
        if not self.root.is_dir() or self.root.is_symlink():
            raise Denied('private preview directory unavailable')
        st = self.root.stat()
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise Denied('private preview directory required')
        if getattr(self,'_root_identity',(st.st_dev,st.st_ino)) != (st.st_dev,st.st_ino):
            raise Denied('preview directory identity changed')
        if set(p.name for p in self.root.iterdir()) - {'preview.sqlite3','preview.sqlite3-journal'}:
            raise Denied('foreign preview directory refused')
        if self.path.is_symlink() or not self.path.is_file():
            raise Denied('preview database unavailable')
        st = self.path.stat()
        if st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
            raise Denied('private single-link preview database required')
        journal = self.root / 'preview.sqlite3-journal'
        if journal.is_symlink() or (journal.exists() and not journal.is_file()):
            raise Denied('foreign preview journal refused')
        if journal.exists():
            st=journal.stat()
            if st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
                raise Denied('private single-link preview journal required')

    @contextmanager
    def _database(self):
        self._check_files()
        db = sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, timeout=3)
        db.row_factory = sqlite3.Row
        try:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if names != {'meta','previews','immutable_update','immutable_delete'} or db.execute('SELECT count(*) FROM meta').fetchone()[0] != 1:
                raise Denied('foreign preview schema refused')
            columns={name:[(r['name'],r['type'],r['notnull'],r['pk']) for r in db.execute('PRAGMA table_info('+name+')')] for name in ('meta','previews')}
            if columns != {'meta':[('value','TEXT',1,0)],'previews':[('owner','TEXT',1,1),('preparation','TEXT',1,0),('request_key','TEXT',1,2),('fingerprint','TEXT',1,0),('document','TEXT',1,0),('proof','TEXT',1,0)]}:
                raise Denied('preview storage columns unavailable')
            for action in ('update','delete'):
                trigger=db.execute("SELECT sql FROM sqlite_master WHERE name=?",('immutable_'+action,)).fetchone()[0]
                expected="CREATE TRIGGER immutable_"+action+" BEFORE "+action.upper()+" ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END"
                if ' '.join(trigger.split()) != expected:
                    raise Denied('preview immutable storage unavailable')
            try:
                raw=db.execute('SELECT value FROM meta').fetchone()[0]
                if len(raw.encode())>4096:raise ValueError()
                meta=json.loads(raw)
                if (set(meta)!={'scope','version','id','database'} or meta['scope']!=self.storage_scope or
                        type(meta['version']) is not int or meta['version']!=VERSION or meta['database']!=self.database_identity or
                        (getattr(self,'namespace',meta['id'])!=meta['id'])):
                    raise ValueError()
                UUID(meta['id'])
            except (ValueError,KeyError,TypeError):
                raise Denied('preview storage identity unavailable') from None
            if db.execute('SELECT count(*) FROM previews').fetchone()[0]>128 or db.execute('SELECT 1 FROM previews GROUP BY preparation HAVING count(*)>16 LIMIT 1').fetchone():
                raise Denied('bounded preview storage unavailable')
            if db.execute('SELECT 1 FROM previews WHERE length(CAST(document AS BLOB))>65536 OR length(CAST(proof AS BLOB))>65536 LIMIT 1').fetchone():
                raise Denied('bounded preview storage bytes unavailable')
            yield db
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def attach_store(self, store):
        if _identity(store) != self.database_identity:
            raise Denied('preview original database required')
        setattr(store, self.attachment_attribute, self)
        return store

    def _source(self, store, c, token, id):
        identity=c.execute(IDENTITY_SQL).fetchone()
        if getattr(store,self.attachment_attribute,None) is not self or identity != self.database_identity:
            raise Denied('attached original preview database required')
        p, parent = planning._context(store, c, token, id, True)
        # Cooperating catalogue writers take this exact key exclusively before
        # their row/DDL locks. Acquire it before _proposal first reads catalogues
        # and retain it through SQLite commit. Direct owner SQL is a snapshot.
        catalogs.lock(c, catalogs.key_of(parent))
        current = planning._proposal(store, c, p, parent)
        if not parent.get('request_intent'):
            raise Conflict('saved explicit request required')
        return p, parent, current

    def _guard(self, store, c, token, p):
        # PG locks cannot freeze wall-clock leases. Recheck after SQLite waits
        # and immediately before its irreversible commit, rather than leaving
        # the first managed recheck to the outer PG context's later commit.
        actor = store.auth(c, token)
        if actor['id'] != p['id']:
            raise Denied('original preview actor required')
        prep.grant(store, c, actor, 'PREPARE')
        store.check_capability(c, actor, 'EXECUTE')
        for principal_id, run_id in sorted(getattr(c, '_managed_checks', ())):
            principal = c.execute('SELECT * FROM principals WHERE id=%s', (principal_id,)).fetchone()
            if not principal or not principal['active']:
                raise Denied('current preview dependency access required')
            store.check_capability(c, principal, 'READ')
            if not store.assignment_allowed(c, principal, run_id, track=False):
                raise Denied('preview dependency access expired or changed before commit')

    def _document(self, row):
        try:
            if len(row['document'].encode())>65536 or len(row['proof'].encode())>65536:
                raise ValueError()
            doc = json.loads(row['document'])
            proof = json.loads(row['proof'])
            if prep.canonical(proof) != prep.canonical({k:doc[k] for k in PROOF_FIELDS}) or doc['execution_contract_sha256'] != EXECUTION_CONTRACT_SHA256:
                raise ValueError()
            if (doc['scope'] != SCOPE or type(doc['version']) is not int or doc['version'] != VERSION or doc['namespace'] != self.namespace or
                    doc['binding']['preparation_id'] != row['preparation'] or doc['actor_id'] != row['owner'] or
                    doc['request_key'] != row['request_key'] or doc['fingerprint'] != row['fingerprint'] or
                    doc['sha256'] != _sha({k:v for k,v in doc.items() if k != 'sha256'})):
                raise ValueError()
            UUID(doc['id'])
            binding=doc['binding']
            request={'preparation_id':binding['preparation_id'],'expected_preparation_revision':binding['preparation_revision'],
                     'expected_request_revision':binding['request_revision'],'expected_source_sha256':binding['source_sha256']}
            if _sha(request) != doc['fingerprint'] or type(doc['formal_writes']) is not int or doc['formal_writes'] != 0 or doc['new_grants'] is not False or doc['case_goal_completed'] is not False or doc['qualification'] != 'NOT_EVALUATED' or doc['external_acceptance'] != 'NOT_SUBMITTED' or doc['offline_fulfillment'] != 'NO_EVIDENCE':
                raise ValueError()
            artifact = doc['artifact']
            UUID(artifact['preparation_id'])
            UUID(artifact['case_id']); UUID(artifact['run_id'])
            owner,reviewer=artifact['owner_id'],artifact['reviewer_id']
            if (not re.fullmatch('preview-owner-[a-f0-9]{32}',owner) or reviewer != owner.replace('preview-owner-','preview-reviewer-') or
                    artifact['roles'] != 'SIMULATED_ROLES_ONLY' or artifact['registered_adapter'] != 'preparation' or type(artifact['adapter_revision']) is not int or artifact['adapter_revision'] != 1 or
                    artifact['preparation_id'] == binding['preparation_id'] or artifact['case_id'] == binding['case_id'] or artifact['run_id'] == binding['run_id'] or
                    artifact['namespace'] != 'PREVIEW_EXECUTION'):
                raise ValueError()
            if doc['state'] not in ('SUCCEEDED','FAILED') or len(artifact['events']) > 4:
                raise ValueError()
            for material in artifact['materials']:
                UUID(material['id'])
                if type(material['version']) is not int or material['version'] != 1 or material['slot'] not in prep.SLOTS:
                    raise ValueError()
                if material['source_sha256'] != digest(material['text']) or material['authenticity'] != 'UNVERIFIED':
                    raise ValueError()
            if ({m['slot']:m['source_sha256'] for m in artifact['materials']} != {m['slot']:m['source_sha256'] for m in binding['slots']} or
                    len(artifact['materials']) != len(binding['slots']) or len({m['slot'] for m in artifact['materials']}) != len(artifact['materials'])):
                raise ValueError()
            actions = [e['action'] for e in artifact['events']]
            expected = ['ADD_EVIDENCE'] * len(artifact['materials'])
            if doc['state'] == 'SUCCEEDED':
                expected += ['REVIEW','CONFIRM']
                if (set(m['slot'] for m in artifact['materials']) != set(prep.SLOTS) or
                        artifact['state'] != 'LOCAL_CONFIRMED' or artifact['review_sha256'] != artifact['snapshot_sha256']):
                    raise ValueError()
            elif artifact['state'] != 'IN_PREPARATION':
                raise ValueError()
            if actions != expected or type(artifact['revision']) is not int or artifact['revision'] != len(actions)+1:
                raise ValueError()
            if len({e['id'] for e in artifact['events']}) != len(actions) or len({e['request_key'] for e in artifact['events']}) != len(actions):
                raise ValueError()
            for i,e in enumerate(artifact['events'],2):
                UUID(e['id'])
                actor=reviewer if e['action']=='REVIEW' else owner
                payload=e['payload']
                if (type(e['revision']) is not int or e['revision'] != i or type(payload['revision']) is not int or payload['revision'] != i or
                        e['actor_id'] != actor or payload['actor_id'] != actor or payload['action'] != e['action'] or payload['state'] != ('IN_PREPARATION' if e['action']=='ADD_EVIDENCE' else 'REVIEWED' if e['action']=='REVIEW' else 'LOCAL_CONFIRMED') or
                        any(payload[k] != artifact[k] for k in ('preparation_id','case_id','run_id'))):
                    raise ValueError()
                if e['action']=='ADD_EVIDENCE':
                    material=artifact['materials'][i-2]
                    command=prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=i-1,**{k:material[k] for k in ('slot','text','source_kind','source_label')})
                    previous_items=artifact['materials'][:i-1]
                else:
                    command=prep.PreparationCommand(action=e['action'],expected_revision=i-1,reason='SYNTHETIC PREVIEW simulated role only')
                    previous_items=artifact['materials']
                command_body=command.model_dump(mode='json',exclude={'correction_slots'})
                if e['fingerprint'] != _sha({'preparation_id':artifact['preparation_id'],**command_body}):
                    raise ValueError()
                if payload['snapshot_sha256'] != prep.snapshot({'id':artifact['preparation_id'],'service_id':prep.SERVICE,'service_version':1},previous_items):
                    raise ValueError()
            if prep.snapshot({'id':artifact['preparation_id'],'service_id':prep.SERVICE,'service_version':1}, artifact['materials']) != artifact['snapshot_sha256']:
                raise ValueError()
            return doc
        except (KeyError,TypeError,ValueError):
            raise Conflict('isolated preview artifact proof unavailable') from None

    def _view(self, db, p, parent, current):
        rows = db.execute('SELECT * FROM previews WHERE owner=? AND preparation=? ORDER BY rowid', (p['id'],str(parent['id']))).fetchall()
        history = [dict(document=self._document(r), source_state='SNAPSHOT_MATCH' if self._document(r)['binding']['source_sha256'] == current['source_sha256'] else 'STALE') for r in rows]
        return dict(scope=SCOPE, enabled=True, preparation_id=str(parent['id']), history=history,
                    current_source_sha256=current['source_sha256'], preparation_revision=parent['revision'],
                    request_revision=parent['request_intent']['revision'], namespace=self.namespace,
                    isolated_steps=['P1'], formal_writes=0, new_grants=False, case_goal_completed=False,
                    execution_available=_registered(current), source_atomicity=False,
                    source_consistency='COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON')

    def read(self, store, token, id, key=None):
        with store.connect() as c:
            p, parent, current = self._source(store,c,token,id)
            with self._database() as db:
                self._guard(store,c,token,p)
                view = self._view(db,p,parent,current)
                if key is not None:
                    old = db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone()
                    if old and old['preparation'] != str(id):
                        raise Conflict('preview key scope mismatch')
                    view.update(status='COMMITTED' if old else 'NOT_OBSERVED', result=self._document(old) if old else None, automatically_replayed=False)
                return view

    def _execute(self, store, parent, current, materials):
        # No public data/Grant is copied into these shadows. Only table structure
        # and synthetic service source are read; every adapter lookup is pg_temp.
        connection = Store(store.dsn).connect()
        artifact = None
        try:
            if connection.execute(IDENTITY_SQL).fetchone() != self.database_identity:
                raise Denied('preview original cluster database required')
            for table in TABLES:
                connection.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE public.{} INCLUDING DEFAULTS) ON COMMIT DROP').format(sql.Identifier(table),sql.Identifier(table)))
            connection.execute('SET LOCAL search_path TO pg_temp')
            connection.execute("SET LOCAL statement_timeout='3s'")
            connection.execute("SET LOCAL lock_timeout='3s'")
            namespace = uuid4().hex
            owner, reviewer = 'preview-owner-'+namespace, 'preview-reviewer-'+namespace
            park, org = 'preview-park-'+namespace, 'preview-org-'+namespace
            private_id, case_id, run_id = uuid4(),uuid4(),uuid4()
            tokens = {owner:secrets.token_urlsafe(32), reviewer:secrets.token_urlsafe(32)}
            for actor, role in ((owner,'enterprise_operator'),(reviewer,'park_specialist')):
                connection.execute('INSERT INTO principals(id,token_hash,park_id,org_id,role,active) VALUES(%s,%s,%s,%s,%s,true)',(actor,digest(tokens[actor]),park,org,role))
                for cap in (('READ','EXECUTE') if actor==owner else ('READ',)):
                    connection.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(actor,cap,park,org))
                connection.execute('INSERT INTO preparation_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(actor,'PREPARE' if actor==owner else 'REVIEW_ASSIGNED',park,org))
            connection.execute("INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) VALUES(%s,%s,1,'Synthetic isolated material preview',%s,'SYNTHETIC','NOT_EVALUATED')",(park,prep.SERVICE,Jsonb({'kind':'SYNTHETIC','id':'isolated-preview','revision':'1'})))
            connection.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,1,'PREVIEW_EXECUTION','SYNTHETIC isolated material chain','IN_PREPARATION')",(private_id,run_id,case_id,owner,reviewer,park,org,prep.SERVICE))
            private = _PreviewStore(connection)
            revision = 1
            error = None
            for material in materials:
                data = prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=revision, **{k:material[k] for k in ('slot','text','source_kind','source_label')})
                result = prep.command(private,tokens[owner],private_id,uuid4().hex,data)
                revision = result['revision']
            try:
                for actor,action in ((reviewer,'REVIEW'),(owner,'CONFIRM')):
                    result = prep.command(private,tokens[actor],private_id,uuid4().hex,prep.PreparationCommand(action=action,expected_revision=revision,reason='SYNTHETIC PREVIEW simulated role only'))
                    revision = result['revision']
            except Conflict:
                error = 'REQUIRED_MATERIAL_REVIEW_FAILED'
            row = connection.execute('SELECT * FROM preparations WHERE id=%s',(private_id,)).fetchone()
            items = prep.latest(connection,private_id)
            events = connection.execute('SELECT id,revision,action,actor_id,request_key,fingerprint,payload FROM preparation_events WHERE preparation_id=%s ORDER BY revision',(private_id,)).fetchall()
            artifact = _normal(dict(preparation_id=str(private_id),case_id=str(case_id),run_id=str(run_id),namespace='PREVIEW_EXECUTION',revision=row['revision'],state=row['state'],review_sha256=row['review_sha256'],snapshot_sha256=prep.snapshot(row,items),owner_id=owner,reviewer_id=reviewer,materials=items,events=events,error=error,roles='SIMULATED_ROLES_ONLY', registered_adapter='preparation',adapter_revision=1, temporary_tables=True))
            return artifact
        finally:
            connection.rollback()
            connection.close()

    def execute(self, store, token, id, key, data):
        with store.connect() as c:
            p,parent,current = self._source(store,c,token,id)
            fp = _sha({'preparation_id':str(id),**data.model_dump()})
            with self._database() as db:
                # Obtain the rollback-journal reader exclusion before _guard:
                # IMMEDIATE permits a reader to stall COMMIT after its last
                # lease check, allowing a 403 with an expired committed result.
                db.execute('BEGIN EXCLUSIVE')
                self._guard(store,c,token,p)
                old = db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone()
                if old:
                    if old['preparation'] != str(id) or old['fingerprint'] != fp:
                        raise Conflict('preview idempotency key body or scope mismatch')
                    result=self._document(old)
                    return {**self._view(db,p,parent,current),'result':result}
                if (parent['revision'] != data.expected_preparation_revision or parent['request_intent']['revision'] != data.expected_request_revision or current['source_sha256'] != data.expected_source_sha256):
                    raise Conflict('preview source changed; explicitly read current proposal')
                if not _registered(current):
                    raise Conflict('exact registered P1 version1 action and service contract required')
                if db.execute('SELECT count(*) FROM previews').fetchone()[0]>=128 or db.execute('SELECT count(*) FROM previews WHERE preparation=?',(str(id),)).fetchone()[0]>=16:
                    raise Conflict('bounded isolated preview history limit reached')
                materials = prep.latest(c,id)
                artifact = self._execute(store,parent,current,materials)
                self._guard(store,c,token,p)
                latest=planning._proposal(store,c,p,parent)
                if latest['source_sha256'] != current['source_sha256']:
                    raise Conflict('preview sources changed during execution; read current proposal')
                result = dict(scope=SCOPE,version=VERSION,id=str(uuid4()),namespace=self.namespace,actor_id=p['id'],request_key=key,fingerprint=fp,
                    binding=dict(preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),service_id=parent['service_id'],service_version=parent['service_version'],preparation_revision=parent['revision'],request_revision=parent['request_intent']['revision'],source_sha256=current['source_sha256'],slots=[{k:str(m[k]) if isinstance(m[k],UUID) else m[k] for k in ('id','slot','version','source_sha256')} for m in materials]),
                    execution_contract_sha256=EXECUTION_CONTRACT_SHA256,state='FAILED' if artifact['error'] else 'SUCCEEDED',coverage_state='P1_PREVIEW_ONLY' if all(g=='LOCAL_MATERIAL_PREPARATION' for g in current['required_goals']) else 'PARTIAL_PREVIEW',required_goals=current['required_goals'],not_previewed=[s['id'] for s in current['steps'] if s['id']!='P1'],goal_coverage=current['goal_coverage'],artifact=artifact,formal_writes=0,new_grants=False,case_goal_completed=False,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')
                result['sha256'] = _sha(result)
                document=prep.canonical(result)
                if len(document.encode())>65536:
                    raise Conflict('bounded preview artifact size exceeded')
                proof=prep.canonical({k:result[k] for k in PROOF_FIELDS})
                if len(proof.encode())>65536:
                    raise Conflict('bounded preview proof size exceeded')
                db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',(p['id'],str(id),key,fp,document,proof))
                self._document(db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone())
                self._guard(store,c,token,p)
                db.commit()
                # Informational comparison only: uncooperative writers, absent
                # rows, collections, time and runtime declarations have no
                # shared atomic transaction with SQLite. Never label CURRENT.
                comparison = planning._proposal(store,c,p,parent)
                return {**self._view(db,p,parent,comparison),'result':result}
