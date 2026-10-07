"""Default-off, isolated template governance; never deployment publication.

Templates contain registered contracts and parameter shapes, not enterprise
materials, identities, Cases, grants, executable expressions, or results.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import threading
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from pydantic import Field, model_validator
from .domain import Contract, PlanID, Validity
from . import bounded_planning as planning, preparation as prep
from .store import Conflict, Denied
from .rule_publication_candidate import canonical, sha, active

NAMESPACE='ISOLATED_SYNTHETIC_TEMPLATE_CANDIDATE'
FLAGS=dict(namespace=NAMESPACE,business_publication=False,deployment_enabled=False,
           new_grants=False,automatic_execution=False,case_goal_completed=False)
PARAMETER_SCHEMA={
    'request_text':{'type':'string','required':True,'min_length':1,'max_length':2000},
    'need_summary':{'type':'new_evidence','required':True,'slots':['need_summary'],'source_kinds':['USER_STATEMENT','DOCUMENT_EXCERPT'],'max_length':4000},
    'material_outline':{'type':'new_evidence','required':True,'slots':['material_outline'],'source_kinds':['USER_STATEMENT','DOCUMENT_EXCERPT'],'max_length':4000}}
Goal=Literal['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE',
             'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK']
Action=Literal['READ','SAVE_DRAFT','SUBMIT','RETURN_DRAFT','REVIEW','REJECT','CANDIDATE_PUBLISH','WITHDRAW']
ROLE_ACTIONS={'template_author':{'READ','SAVE_DRAFT','SUBMIT','RETURN_DRAFT'},
              'template_reviewer':{'READ','REVIEW','REJECT'},
              'template_publisher':{'READ','CANDIDATE_PUBLISH','WITHDRAW'},'template_reader':{'READ'}}


class Scope(Contract):
    park_id:PlanID
    template_id:PlanID


class TemplatePrincipal(Contract):
    id:PlanID
    role:Literal['template_author','template_reviewer','template_publisher','template_reader']
    active:bool=True


class TemplatePermit(Contract):
    id:PlanID
    principal_id:PlanID
    scope:Scope
    actions:list[Action]=Field(min_length=1,max_length=8)
    validity:Validity
    active:bool=True


class TemplateConfig(Contract):
    enabled_for_isolated_tests:bool=False
    namespace:Literal['ISOLATED_SYNTHETIC_TEMPLATE_CANDIDATE']=NAMESPACE
    revision:int=Field(default=1,ge=1)
    principals:list[TemplatePrincipal]=Field(default_factory=list,max_length=16)
    permits:list[TemplatePermit]=Field(default_factory=list,max_length=64)

    @model_validator(mode='after')
    def subjects(self):
        ids={p.id for p in self.principals}
        if len(ids)!=len(self.principals) or len({p.id for p in self.permits})!=len(self.permits):raise ValueError('duplicate isolated template subjects or permits')
        if any(p.principal_id not in ids for p in self.permits):raise ValueError('explicit template permit subject required')
        if self.enabled_for_isolated_tests and (not self.principals or not self.permits):raise ValueError('explicit isolated template contract required')
        return self


class TemplateSource(Contract):
    kind:Literal['SYNTHETIC']='SYNTHETIC'
    id:PlanID
    revision:str=Field(pattern='^[1-9][0-9]{0,5}$')
    statement:str=Field(min_length=1,max_length=2000)
    validity:Validity


class RegisteredStep(Contract):
    id:Literal['P1','P2','P3','P4','P5']
    adapter_revision:Literal[1]=1
    depends_on:list[Literal['P1','P2','P3','P4','P5']]=Field(max_length=4)


class TemplateDraft(Contract):
    name:str=Field(min_length=1,max_length=160)
    description:str=Field(min_length=1,max_length=1000)
    service_id:Literal['synthetic-material-preparation']=prep.SERVICE
    service_version:Literal[1]=1
    required_goals:list[Goal]=Field(min_length=1,max_length=6)
    steps:list[RegisteredStep]=Field(min_length=1,max_length=5)
    parameter_schema:dict
    source:TemplateSource
    business_publication:Literal[False]=False

    @model_validator(mode='after')
    def registered(self):
        if not self.name.strip() or not self.description.strip() or not self.source.statement.strip():raise ValueError('nonblank template description and source required')
        if len(set(self.required_goals))!=len(self.required_goals):raise ValueError('distinct registered goals required')
        coverage,nodes=planning.compile(self.required_goals)
        expected=[dict(id=s['id'],adapter_revision=s['revision'],depends_on=s['depends_on']) for s in nodes]
        if type(self.service_version) is not int or any(type(s.adapter_revision) is not int for s in self.steps) or [s.model_dump() for s in self.steps]!=expected or canonical(self.parameter_schema)!=canonical(PARAMETER_SCHEMA):raise ValueError('exact registered dependency closure and fixed parameter schema required')
        return self


def draft_for_goals(name,description,goals,source):
    _,nodes=planning.compile(goals)
    return TemplateDraft(name=name,description=description,required_goals=goals,source=source,
                         steps=[RegisteredStep(id=s['id'],adapter_revision=s['revision'],depends_on=s['depends_on']) for s in nodes],
                         parameter_schema=deepcopy(PARAMETER_SCHEMA))


class Command(Contract):
    action:Literal['SAVE_DRAFT','SUBMIT','RETURN_DRAFT','REVIEW','REJECT','CANDIDATE_PUBLISH','WITHDRAW']
    expected_revision:int=Field(ge=0,le=64)
    expected_definition_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=1,max_length=1000)
    draft:TemplateDraft|None=None
    validity:Validity|None=None

    @model_validator(mode='after')
    def shape(self):
        if not self.reason.strip() or (self.action=='SAVE_DRAFT')!=(self.draft is not None) or (self.action=='CANDIDATE_PUBLISH')!=(self.validity is not None):raise ValueError('action-specific template payload required')
        if self.expected_revision>0 and self.expected_definition_sha256 is None:raise ValueError('current definition hash required')
        return self


class TemplateRepository:
    TRIGGERS={
        'immutable_template_events_update':"CREATE TRIGGER immutable_template_events_update BEFORE UPDATE ON template_events BEGIN SELECT RAISE(ABORT,'immutable template event'); END",
        'immutable_template_events_delete':"CREATE TRIGGER immutable_template_events_delete BEFORE DELETE ON template_events BEGIN SELECT RAISE(ABORT,'immutable template event'); END",
        'immutable_template_release_payload':"CREATE TRIGGER immutable_template_release_payload BEFORE UPDATE OF payload,payload_sha ON template_releases BEGIN SELECT RAISE(ABORT,'immutable template release'); END",
        'immutable_template_release_delete':"CREATE TRIGGER immutable_template_release_delete BEFORE DELETE ON template_releases BEGIN SELECT RAISE(ABORT,'immutable template release'); END",
        'immutable_template_sources_update':"CREATE TRIGGER immutable_template_sources_update BEFORE UPDATE ON template_sources BEGIN SELECT RAISE(ABORT,'immutable template source'); END",
        'immutable_template_sources_delete':"CREATE TRIGGER immutable_template_sources_delete BEFORE DELETE ON template_sources BEGIN SELECT RAISE(ABORT,'immutable template source'); END",
        'immutable_template_contracts_update':"CREATE TRIGGER immutable_template_contracts_update BEFORE UPDATE ON template_contracts BEGIN SELECT RAISE(ABORT,'immutable template contract'); END",
        'immutable_template_contracts_delete':"CREATE TRIGGER immutable_template_contracts_delete BEFORE DELETE ON template_contracts BEGIN SELECT RAISE(ABORT,'immutable template contract'); END"}

    def __init__(self,path):
        self.path=Path(path).absolute()
        if not self.path.name.endswith('.template.candidate.sqlite3') or any(p.is_symlink() for p in [self.path,*self.path.parents]):raise ValueError('dedicated nonsymlink isolated template database required')
        new=False
        try:
            fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            os.close(fd);new=True
        except FileExistsError:
            if not self.path.is_file():raise ValueError('ordinary isolated template database required')
        columns={'template_meta':['namespace','version'],
                 'template_drafts':['scope','id','revision','content_version','state','definition','definition_sha','author_id','review','current_release'],
                 'template_releases':['id','scope','state','payload','payload_sha'],
                 'template_events':['actor','key','fp','scope','revision','action','payload'],
                 'template_sources':['park_id','source_id','source_revision','payload','payload_sha'],
                 'template_contracts':['revision','payload_sha','payload']}
        with sqlite3.connect(self.path) as c:
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not new and tables!=set(columns):raise Conflict('foreign or partial template candidate database refused')
            if not new and (any([r[1] for r in c.execute('PRAGMA table_info('+t+')')]!=names for t,names in columns.items()) or c.execute('SELECT namespace,version FROM template_meta').fetchall()!=[(NAMESPACE,2)]):raise Conflict('template candidate schema mismatch')
            if not new:
                triggers={r[0]:' '.join(r[1].split()) for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger'")}
                if triggers!={name:' '.join(sql.split()) for name,sql in self.TRIGGERS.items()}:raise Conflict('template immutable schema mismatch')
                return
            c.executescript('''CREATE TABLE IF NOT EXISTS template_meta(namespace TEXT PRIMARY KEY,version INTEGER);
              CREATE TABLE IF NOT EXISTS template_drafts(scope TEXT PRIMARY KEY,id TEXT,revision INTEGER,content_version INTEGER,state TEXT,definition TEXT,definition_sha TEXT,author_id TEXT,review TEXT,current_release TEXT);
              CREATE TABLE IF NOT EXISTS template_releases(id TEXT PRIMARY KEY,scope TEXT,state TEXT,payload TEXT,payload_sha TEXT);
              CREATE TABLE IF NOT EXISTS template_events(actor TEXT,key TEXT,fp TEXT,scope TEXT,revision INTEGER,action TEXT,payload TEXT,PRIMARY KEY(actor,key));
              CREATE TABLE IF NOT EXISTS template_sources(park_id TEXT,source_id TEXT,source_revision TEXT,payload TEXT,payload_sha TEXT,PRIMARY KEY(park_id,source_id,source_revision));
              CREATE TABLE IF NOT EXISTS template_contracts(revision INTEGER PRIMARY KEY,payload_sha TEXT NOT NULL,payload TEXT NOT NULL);''')
            for sql in self.TRIGGERS.values():c.execute(sql)
            c.execute('INSERT OR IGNORE INTO template_meta VALUES(?,2)',(NAMESPACE,))

    @contextmanager
    def transaction(self):
        c=sqlite3.connect(self.path,timeout=3);c.row_factory=sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE');yield c;c.commit()
        except sqlite3.OperationalError as e:c.rollback();raise Conflict('template candidate database busy; retry original key') from e
        except BaseException:c.rollback();raise
        finally:c.close()


class TemplateEngine:
    def __init__(self,config=None,repository=None,clock=None):
        self._config=TemplateConfig.model_validate((config or TemplateConfig()).model_dump())
        self.repository=repository;self.clock=clock or (lambda:datetime.now(timezone.utc));self.lock=threading.RLock()
        if repository is not None:self._bind_contract(self._config)

    @property
    def config(self):return self._config.model_copy(deep=True)

    def replace_contract(self,config):
        updated=TemplateConfig.model_validate(config.model_dump())
        with self.lock:
            if self.repository is not None:self._check_head()
            if updated.model_dump()==self._config.model_dump():
                if self.repository is not None:self._bind_contract(updated,self._config)
                return
            if updated.revision<=self._config.revision:raise Conflict('changed isolated template contract requires a newer revision')
            if self.repository is not None:self._bind_contract(updated,self._config)
            self._config=updated

    def _bind_contract(self,config,expected_config=None):
        document=config.model_dump(mode='json');fingerprint=sha(document)
        with self.repository.transaction() as c:
            head=c.execute('SELECT revision,payload_sha FROM template_contracts ORDER BY revision DESC LIMIT 1').fetchone()
            if expected_config is not None and (not head or head['revision']!=expected_config.revision or head['payload_sha']!=sha(expected_config.model_dump(mode='json'))):raise Denied('stale live template engine cannot replace the durable authority head')
            if head:
                if head['revision']==config.revision and head['payload_sha']==fingerprint:return
                if config.revision<=head['revision']:raise Conflict('isolated template contract is older than the durable authority head')
            c.execute('INSERT INTO template_contracts VALUES(?,?,?)',(config.revision,fingerprint,canonical(document)))

    def _enabled(self,c=None):
        if not self._config.enabled_for_isolated_tests or self.repository is None:raise Denied('isolated template candidate disabled')
        self._check_head(c)

    def _check_head(self,c=None):
        fingerprint=sha(self._config.model_dump(mode='json'))
        if c is None:
            try:
                with sqlite3.connect('file:'+quote(str(self.repository.path),safe='/')+'?mode=ro',uri=True,timeout=3) as read:
                    head=read.execute('SELECT revision,payload_sha FROM template_contracts ORDER BY revision DESC LIMIT 1').fetchone()
            except sqlite3.Error as e:raise Denied('current isolated template authority unavailable') from e
        else:head=c.execute('SELECT revision,payload_sha FROM template_contracts ORDER BY revision DESC LIMIT 1').fetchone()
        if not head or head[0]!=self._config.revision or head[1]!=fingerprint:raise Denied('current durable isolated template contract required')

    def _authorize(self,actor,action,scope,now):
        self._enabled()
        principal=next((p for p in self._config.principals if p.id==actor and p.active),None)
        if not principal or action not in ROLE_ACTIONS[principal.role]:raise Denied('isolated template role denied')
        if not any(p.principal_id==actor and p.scope==scope and p.active and action in p.actions and active(p.validity.model_dump(mode='json'),now) for p in self._config.permits):raise Denied('explicit current isolated template scope permit required')
        return principal

    def status(self):
        if self._config.enabled_for_isolated_tests:self._enabled()
        now=self.clock()
        source=TemplateSource(id='isolated-template-materials-source',revision='1',statement='合成材料整理模板规格；不含企业材料或资格结论。',
                              validity=Validity(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=7)).isoformat()))
        personas=[p.model_dump() for p in self._config.principals] if self._config.enabled_for_isolated_tests else []
        return dict(**FLAGS,candidate_demo=self._config.enabled_for_isolated_tests,
                    enabled_for_isolated_tests=self._config.enabled_for_isolated_tests,
                    contract_revision=self._config.revision,isolated_principals=personas,isolated_personas=personas,
                    example_definition=draft_for_goals('合成材料准备模板','新企业以自己的新资料办理材料准备。',['LOCAL_MATERIAL_PREPARATION'],source).model_dump(mode='json'),
                    parameter_schema=deepcopy(PARAMETER_SCHEMA),registered_goals=list(planning.GOALS),
                    registered_steps=[dict(id=s['id'],adapter_revision=s['revision'],depends_on=s['depends_on']) for s in planning.REGISTRY])

    def _row(self,c,scope):return c.execute('SELECT * FROM template_drafts WHERE scope=?',(canonical(scope.model_dump()),)).fetchone()

    def _source_current(self,c,scope,source):
        head=c.execute('SELECT max(CAST(source_revision AS INTEGER)) AS revision FROM template_sources WHERE park_id=? AND source_id=?',(scope.park_id,source['id'])).fetchone()
        return bool(head and head['revision']==int(source['revision']))

    def _available(self,c,release):
        payload=json.loads(release['payload']);scope=Scope.model_validate(payload['scope']);now=self.clock()
        reason=None
        try:
            self._enabled(c)
            if release['state']!='PUBLISHED':reason='RELEASE_'+release['state']
            elif sha(payload)!=release['payload_sha']:reason='RELEASE_HASH_CHANGED'
            elif payload['contract_sha256']!=sha(self._config.model_dump(mode='json')):reason='CONTRACT_CHANGED'
            elif payload['registry_sha256']!=sha(dict(steps=planning.REGISTRY,actions=planning.ACTIONS)):reason='REGISTRY_CHANGED'
            elif not active(payload['validity'],now) or not active(payload['definition']['source']['validity'],now):reason='RELEASE_OR_SOURCE_EXPIRED'
            elif sha(payload['definition'])!=payload['definition_sha256']:reason='DEFINITION_CHANGED'
            else:
                self._authorize(payload['author_id'],'SUBMIT',scope,now)
                self._authorize(payload['review']['reviewer_id'],'REVIEW',scope,now)
                self._authorize(payload['publisher_id'],'CANDIDATE_PUBLISH',scope,now)
                source=payload['definition']['source']
                recorded=c.execute('SELECT payload_sha FROM template_sources WHERE park_id=? AND source_id=? AND source_revision=?',(scope.park_id,source['id'],source['revision'])).fetchone()
                if not recorded or recorded['payload_sha']!=sha(source):reason='SOURCE_VERSION_CHANGED'
                elif not self._source_current(c,scope,source):reason='SOURCE_SUPERSEDED'
        except Denied:reason='CURRENT_TEMPLATE_CONTRACT_REQUIRED'
        return dict(**FLAGS,release_id=release['id'],release_sha256=release['payload_sha'],state=release['state'],snapshot=payload,
                    candidate_available=reason is None,availability_reason=reason)

    def _view(self,c,actor,scope,event=None):
        row=self._row(c,scope);key=canonical(scope.model_dump())
        releases=[self._available(c,r) for r in c.execute('SELECT * FROM template_releases WHERE scope=? ORDER BY rowid',(key,))]
        current=next((r for r in releases if row and r['release_id']==row['current_release']),None)
        reader=next(p for p in self._config.principals if p.id==actor).role=='template_reader'
        return dict(**FLAGS,scope=scope.model_dump(),revision=row['revision'] if row else 0,content_version=row['content_version'] if row else 0,
                    state=row['state'] if row else 'NOT_CREATED',definition_sha256=row['definition_sha'] if row else None,
                    draft=json.loads(row['definition']) if row and not reader else None,
                    review=json.loads(row['review']) if row and row['review'] and not reader else None,
                    candidate_available=bool(current and current['candidate_available']),availability_reason=current['availability_reason'] if current else 'NO_PUBLISHED_RELEASE',
                    releases=releases if not reader else [r for r in releases if r['candidate_available']],
                    history=[json.loads(r[0]) for r in c.execute('SELECT payload FROM template_events WHERE scope=? ORDER BY revision',(key,))] if not reader else [],event=event if not reader else None)

    def read(self,actor,scope):
        with self.lock:
            self._authorize(actor,'READ',scope,self.clock())
            with self.repository.transaction() as c:
                self._enabled(c);return self._view(c,actor,scope)

    def public_catalog(self,park_id):
        with self.lock:
            self._enabled()
            with self.repository.transaction() as c:
                self._enabled(c)
                items=[self._available(c,r) for r in c.execute('SELECT * FROM template_releases ORDER BY rowid') if json.loads(r['payload'])['scope']['park_id']==park_id]
                return dict(**FLAGS,items=[r for r in items if r['candidate_available']])

    def published(self,scope,release_id,expected_release_sha256=None):
        with self.lock:
            self._enabled()
            with self.repository.transaction() as c:
                self._enabled(c)
                row=c.execute('SELECT * FROM template_releases WHERE id=? AND scope=?',(str(release_id),canonical(scope.model_dump()))).fetchone()
                if not row:raise Denied('isolated template release unavailable')
                release=self._available(c,row)
                if not release['candidate_available']:raise Denied('isolated template release unavailable: '+release['availability_reason'])
                if expected_release_sha256 is not None and release['release_sha256']!=expected_release_sha256:raise Conflict('template release hash changed')
                return release

    def command(self,actor,scope,key,data):
        if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('bounded template request key required')
        with self.lock:
            self._authorize(actor,data.action,scope,self.clock())
            fp=sha(dict(scope=scope.model_dump(),**data.model_dump(mode='json')))
            with self.repository.transaction() as c:
                self._enabled(c)
                row=self._row(c,scope);old=c.execute('SELECT * FROM template_events WHERE actor=? AND key=?',(actor,key)).fetchone()
                if old:
                    if old['fp']!=fp or old['scope']!=canonical(scope.model_dump()):raise Conflict('template request key fingerprint or scope changed')
                    return self._view(c,actor,scope,json.loads(old['payload']))
                revision=row['revision'] if row else 0
                if data.expected_revision!=revision or (row and data.expected_definition_sha256!=row['definition_sha']):raise Conflict('template revision or definition changed')
                if revision>=64:raise Conflict('template event history limit reached')
                definition=json.loads(row['definition']) if row else None
                review=json.loads(row['review']) if row and row['review'] else None
                state=row['state'] if row else 'NOT_CREATED';version=row['content_version'] if row else 0
                author=row['author_id'] if row else actor;release_id=row['current_release'] if row else None
                if data.action=='SAVE_DRAFT':
                    if state not in ('NOT_CREATED','DRAFT','REJECTED'):raise Conflict('return template to draft before editing')
                    definition=data.draft.model_dump(mode='json');source=definition['source']
                    if not active(source['validity'],self.clock()):raise Conflict('current synthetic template source required')
                    previous=c.execute('SELECT payload_sha FROM template_sources WHERE park_id=? AND source_id=? AND source_revision=?',(scope.park_id,source['id'],source['revision'])).fetchone()
                    if previous and previous['payload_sha']!=sha(source):raise Conflict('immutable template source revision changed')
                    head=c.execute('SELECT max(CAST(source_revision AS INTEGER)) FROM template_sources WHERE park_id=? AND source_id=?',(scope.park_id,source['id'])).fetchone()[0]
                    if head is not None and int(source['revision'])<head:raise Conflict('historical template source cannot become current again')
                    c.execute('INSERT OR IGNORE INTO template_sources VALUES(?,?,?,?,?)',(scope.park_id,source['id'],source['revision'],canonical(source),sha(source)))
                    version+=1;author=actor;state='DRAFT';review=None
                else:
                    if not row:raise Conflict('saved template draft required')
                    if data.action=='WITHDRAW':
                        if state!='PUBLISHED' or not release_id:raise Conflict('published candidate required for withdrawal')
                        c.execute("UPDATE template_releases SET state='WITHDRAWN' WHERE id=?",(release_id,));state='WITHDRAWN'
                    elif data.action=='RETURN_DRAFT':
                        if state not in ('SUBMITTED','REVIEWED','REJECTED','PUBLISHED','WITHDRAWN'):raise Conflict('submitted or reviewed template required')
                        if actor!=author:raise Denied('original template author required')
                        if release_id:c.execute("UPDATE template_releases SET state='SUPERSEDED' WHERE id=? AND state='PUBLISHED'",(release_id,))
                        state='DRAFT';review=None;release_id=None
                    else:
                        TemplateDraft.model_validate(definition)
                        if not active(definition['source']['validity'],self.clock()):raise Conflict('template source expired')
                        if not self._source_current(c,scope,definition['source']):raise Conflict('template source superseded; save a current source and review again')
                        if data.action=='SUBMIT':
                            if state!='DRAFT' or actor!=author:raise Conflict('current author draft required')
                            state='SUBMITTED';review=None
                        elif data.action in ('REVIEW','REJECT'):
                            if state!='SUBMITTED':raise Conflict('submitted template required')
                            if actor==author:raise Denied('independent template reviewer required')
                            self._authorize(author,'SUBMIT',scope,self.clock())
                            state='REVIEWED' if data.action=='REVIEW' else 'REJECTED'
                            review=dict(reviewer_id=actor,definition_sha256=sha(definition),content_version=version,
                                        contract_sha256=sha(self._config.model_dump(mode='json')),registry_sha256=sha(dict(steps=planning.REGISTRY,actions=planning.ACTIONS)),revision=revision+1,reason=data.reason,action=data.action)
                        else:
                            if state!='REVIEWED' or not review or review['action']!='REVIEW':raise Conflict('independently reviewed template required')
                            if actor in (author,review['reviewer_id']):raise Denied('independent template publisher required')
                            self._authorize(author,'SUBMIT',scope,self.clock());self._authorize(review['reviewer_id'],'REVIEW',scope,self.clock())
                            if review['definition_sha256']!=sha(definition) or review['contract_sha256']!=sha(self._config.model_dump(mode='json')) or review['registry_sha256']!=sha(dict(steps=planning.REGISTRY,actions=planning.ACTIONS)):raise Conflict('template review, registry or contract changed')
                            validity=data.validity.model_dump(mode='json')
                            if not active(validity,self.clock()):raise Conflict('currently effective candidate validity required')
                            if datetime.fromisoformat(validity['valid_until'])>datetime.fromisoformat(definition['source']['validity']['valid_until']) or datetime.fromisoformat(validity['valid_from'])<datetime.fromisoformat(definition['source']['validity']['valid_from']):raise Conflict('candidate release validity must be within its source validity')
                            release_id=str(uuid4())
                            payload=dict(release_id=release_id,scope=scope.model_dump(),definition=definition,
                                         definition_sha256=sha(definition),registry_sha256=sha(dict(steps=planning.REGISTRY,actions=planning.ACTIONS)),
                                         content_version=version,review=review,author_id=author,publisher_id=actor,
                                         contract_sha256=sha(self._config.model_dump(mode='json')),validity=validity,**FLAGS)
                            c.execute('INSERT INTO template_releases VALUES(?,?,?,?,?)',(release_id,canonical(scope.model_dump()),'PUBLISHED',canonical(payload),sha(payload)))
                            state='PUBLISHED'
                revision+=1
                c.execute('INSERT INTO template_drafts VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision,content_version=excluded.content_version,state=excluded.state,definition=excluded.definition,definition_sha=excluded.definition_sha,author_id=excluded.author_id,review=excluded.review,current_release=excluded.current_release',
                          (canonical(scope.model_dump()),row['id'] if row else str(uuid4()),revision,version,state,canonical(definition),sha(definition),author,canonical(review) if review else None,release_id))
                event=dict(id=str(uuid4()),scope=scope.model_dump(),revision=revision,content_version=version,action=data.action,
                           actor_id=actor,definition_sha256=sha(definition),release_id=release_id,reason=data.reason,**FLAGS)
                c.execute('INSERT INTO template_events VALUES(?,?,?,?,?,?,?)',(actor,key,fp,canonical(scope.model_dump()),revision,data.action,canonical(event)))
                return self._view(c,actor,scope,event)
