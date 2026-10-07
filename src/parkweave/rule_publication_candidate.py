"""Isolated SYNTHETIC candidate contract. Never touches deployment PG or grants."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, sqlite3, threading
from typing import Literal
from uuid import uuid4
from pydantic import Field, model_validator
from .domain import Contract, PlanID, SourceRef, Validity, V1ServiceSpec, Truth
from .store import Denied, Conflict

NAMESPACE='ISOLATED_SYNTHETIC_CANDIDATE'
ROLE_ACTIONS={'enterprise_operator':{'READ','SAVE','SUBMIT','RETURN_DRAFT'},'park_specialist':{'READ','REVIEW','REJECT'},'resource_admin':{'READ','PUBLISH','WITHDRAW'},'service_executor':{'READ'}}
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def active(validity,now):return datetime.fromisoformat(validity['valid_from'])<=now<datetime.fromisoformat(validity['valid_until'])

class Scope(Contract):
    park_id: PlanID
    org_id: PlanID
    service_id: PlanID

class MockPrincipal(Contract):
    id: PlanID
    role: Literal['enterprise_operator','park_specialist','resource_admin','service_executor']
    active: bool=True

class CandidatePermit(Contract):
    id: PlanID
    principal_id: PlanID
    scope: Scope
    actions: list[Literal['READ','SAVE','SUBMIT','RETURN_DRAFT','REVIEW','REJECT','PUBLISH','WITHDRAW']]=Field(min_length=1,max_length=8)
    validity: Validity
    active: bool=True

class CandidateConfig(Contract):
    enabled_for_isolated_tests: bool=False
    namespace: Literal['ISOLATED_SYNTHETIC_CANDIDATE']=NAMESPACE
    revision: int=Field(default=1,ge=1)
    principals: list[MockPrincipal]=Field(default_factory=list,max_length=16)
    permits: list[CandidatePermit]=Field(default_factory=list,max_length=64)
    @model_validator(mode='after')
    def explicit(self):
        if len({p.id for p in self.principals})!=len(self.principals) or len({p.id for p in self.permits})!=len(self.permits):raise ValueError('duplicate mock contract identities')
        if any(p.principal_id not in {i.id for i in self.principals} for p in self.permits):raise ValueError('permit principal missing')
        if self.enabled_for_isolated_tests and (not self.principals or not self.permits):raise ValueError('explicit isolated contract required')
        return self

class SourceDocument(Contract):
    ref: SourceRef
    text: str=Field(min_length=1,max_length=4000)
    validity: Validity
    @model_validator(mode='after')
    def synthetic(self):
        if self.ref.kind!='SYNTHETIC' or not self.text.strip():raise ValueError('isolated synthetic source only')
        return self

class Draft(Contract):
    spec: V1ServiceSpec
    sources: list[SourceDocument]=Field(min_length=1,max_length=10)
    @model_validator(mode='after')
    def binding(self):
        refs=[s.ref.model_dump() for s in self.sources]
        if self.spec.publication!='DRAFT' or self.spec.reviewer_id is not None:raise ValueError('client cannot assert approval')
        if len({(s.ref.id,s.ref.revision) for s in self.sources})!=len(refs) or sorted(canonical(r) for r in refs)!=sorted(canonical(s.model_dump()) for s in self.spec.source_refs):raise ValueError('exact source version binding required')
        return self

class Command(Contract):
    action: Literal['SAVE','SUBMIT','RETURN_DRAFT','REVIEW','REJECT','PUBLISH','WITHDRAW']
    expected_revision: int=Field(ge=0,le=64)
    expected_content_sha256: str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
    draft: Draft|None=None
    publish_validity: Validity|None=None
    reason: str=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def shape(self):
        if not self.reason.strip() or (self.action=='SAVE')!=(self.draft is not None) or (self.action=='PUBLISH')!=(self.publish_validity is not None):raise ValueError('explicit action payload required')
        if self.expected_revision>0 and self.expected_content_sha256 is None:raise ValueError('content binding required')
        return self

class CandidateRepository:
    """Dedicated candidate SQLite only; refuses an existing foreign/legacy DB."""
    def __init__(self,path: Path):
        self.path=Path(path)
        if self.path.suffixes[-2:]!=['.candidate','.sqlite3'] or self.path.is_symlink():raise ValueError('dedicated candidate path required')
        with sqlite3.connect(self.path) as c:
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            expected={'candidate_meta','candidate_rules','candidate_releases','candidate_events','candidate_assessments'}
            if tables and tables!=expected:raise Conflict('foreign or partial database refused without migration')
            if tables and c.execute('SELECT namespace,version FROM candidate_meta').fetchall()!=[(NAMESPACE,1)]:raise Conflict('candidate schema mismatch')
            columns={'candidate_meta':['namespace','version'],'candidate_rules':['scope','id','revision','content_version','state','draft','content_sha','review','current_release'],'candidate_releases':['id','scope','state','payload'],'candidate_events':['actor','key','fp','scope','revision','action','payload'],'candidate_assessments':['id','scope','payload']}
            if tables and any([r[1] for r in c.execute('PRAGMA table_info('+name+')')]!=names for name,names in columns.items()):raise Conflict('unknown candidate schema refused without migration')

            c.executescript('''CREATE TABLE IF NOT EXISTS candidate_meta(namespace TEXT PRIMARY KEY,version INTEGER);
                CREATE TABLE IF NOT EXISTS candidate_rules(scope TEXT PRIMARY KEY,id TEXT,revision INTEGER,content_version INTEGER,state TEXT,draft TEXT,content_sha TEXT,review TEXT,current_release TEXT);
                CREATE TABLE IF NOT EXISTS candidate_releases(id TEXT PRIMARY KEY,scope TEXT,state TEXT,payload TEXT);
                CREATE TABLE IF NOT EXISTS candidate_events(actor TEXT,key TEXT,fp TEXT,scope TEXT,revision INTEGER,action TEXT,payload TEXT,PRIMARY KEY(actor,key));
                CREATE TRIGGER IF NOT EXISTS immutable_candidate_events_update BEFORE UPDATE ON candidate_events BEGIN SELECT RAISE(ABORT,'immutable candidate audit'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_candidate_events_delete BEFORE DELETE ON candidate_events BEGIN SELECT RAISE(ABORT,'immutable candidate audit'); END;
                CREATE TABLE IF NOT EXISTS candidate_assessments(id TEXT PRIMARY KEY,scope TEXT,payload TEXT);''')
            c.execute('INSERT OR IGNORE INTO candidate_meta VALUES(?,1)',(NAMESPACE,))
    @contextmanager
    def connect(self,write=False):
        c=sqlite3.connect(self.path,timeout=3);c.row_factory=sqlite3.Row
        try:
            if write:c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except sqlite3.OperationalError as e:
            c.rollback();raise Conflict('candidate storage busy; retry original key') from e
        except BaseException:c.rollback();raise
        finally:c.close()

class CandidateEngine:
    def __init__(self,config=None,repository=None,clock=None):
        self._config=CandidateConfig.model_validate((config or CandidateConfig()).model_dump())
        self.repository=repository;self.clock=clock or (lambda:datetime.now(timezone.utc));self._mutex=threading.RLock()
        if self._config.enabled_for_isolated_tests and repository is None:raise ValueError('isolated storage required')
    def replace_test_contract(self,config):
        # Test harness only; never exposed through HTTP or persisted as an identity/grant.
        with self._mutex:self._config=CandidateConfig.model_validate(config.model_dump())
    def status(self):
        return {'scope':NAMESPACE,'candidate_demo':self._config.enabled_for_isolated_tests,'deployment_enabled':False,'business_publication':False,'mock_personas':[p.model_dump() for p in self._config.principals]}
    def _authorize(self,actor,action,scope,now):
        cfg=self._config
        if not cfg.enabled_for_isolated_tests or self.repository is None:raise Denied('candidate workflow disabled')
        person=next((p for p in cfg.principals if p.id==actor and p.active),None)
        if not person or action not in ROLE_ACTIONS[person.role]:raise Denied('candidate role denied')
        permit=next((p for p in cfg.permits if p.principal_id==actor and p.scope==scope and p.active and action in p.actions and active(p.validity.model_dump(),now)),None)
        if not permit:raise Denied('explicit current candidate scope permit required')
        return permit.id
    def _sources_current(self,draft,now):
        return active(draft['spec']['validity'],now) and all(active(s['validity'],now) for s in draft['sources'])
    def _get(self,c,scope):
        r=c.execute('SELECT * FROM candidate_rules WHERE scope=?',(canonical(scope.model_dump()),)).fetchone()
        return dict(r) if r else None
    def _view(self,c,scope,row,now):
        key=canonical(scope.model_dump());history=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM candidate_events WHERE scope=? ORDER BY revision',(key,))]
        releases=[{'state':r['state'],**json.loads(r['payload'])} for r in c.execute('SELECT * FROM candidate_releases WHERE scope=? ORDER BY rowid',(key,))]
        available=False;reason='NOT_CREATED';draft=json.loads(row['draft']) if row else None
        if row:
            reason='UNREVIEWED_OR_UNPUBLISHED'
            if not self._sources_current(draft,now):reason='EXPIRED_SOURCE'
            elif row['state']=='PUBLISHED' and row['current_release']:
                release=next(r for r in releases if r['id']==row['current_release'])
                if release['state']!='PUBLISHED':reason='WITHDRAWN_OR_SUPERSEDED'
                elif not active(release['validity'],now):reason='OUTSIDE_RELEASE_VALIDITY'
                else:
                    try:
                        self._authorize(release['reviewer_id'],'REVIEW',scope,now);self._authorize(release['publisher_id'],'PUBLISH',scope,now)
                        available=True;reason='ACTIVE_ISOLATED_CANDIDATE'
                    except Denied:reason='CURRENT_REVIEW_OR_PUBLISH_AUTHORITY_MISSING'
            elif row['state']=='WITHDRAWN':reason='WITHDRAWN'
        source_sha=sha({'scope':scope.model_dump(),'revision':row['revision'] if row else 0,'content_sha':row['content_sha'] if row else None,'release':row['current_release'] if row else None,'availability':reason,'contract':sha(self._config.model_dump())})
        assessments=[]
        for a in c.execute('SELECT payload FROM candidate_assessments WHERE scope=? ORDER BY rowid',(key,)):
            a=json.loads(a['payload']);a['state']='CURRENT' if a['source_sha256']==source_sha else 'STALE';a['current_truth']=Truth.UNKNOWN.value;assessments.append(a)
        return {'scope':scope.model_dump(),'namespace':NAMESPACE,'revision':row['revision'] if row else 0,'content_version':row['content_version'] if row else 0,'content_sha256':row['content_sha'] if row else None,'state':row['state'] if row else 'NOT_CREATED','draft':draft,'review':json.loads(row['review']) if row and row['review'] else None,'candidate_available':available,'availability_reason':reason,'source_sha256':source_sha,'history':history,'releases':releases,'assessments':assessments,'qualification_truth':'UNKNOWN','qualification_decision':'NOT_EVALUATED','deployment_enabled':False,'business_publication':False,'case_goal_completed':False}
    def read(self,actor,scope):
        with self._mutex:
            now=self.clock();self._authorize(actor,'READ',scope,now)
            with self.repository.connect() as c:return self._view(c,scope,self._get(c,scope),now)
    def command(self,actor,scope,key,data):
        if not 1<=len(key)<=100:raise ValueError('bounded candidate request key required')
        fp=sha({'scope':scope.model_dump(),**data.model_dump(mode='json')})
        with self._mutex:
            now=self.clock();permit=self._authorize(actor,data.action,scope,now)
            with self.repository.connect(write=True) as c:
                old=c.execute('SELECT * FROM candidate_events WHERE actor=? AND key=?',(actor,key)).fetchone()
                if old:
                    if old['fp']!=fp:raise Conflict('candidate key fingerprint mismatch')
                    return json.loads(old['payload'])
                row=self._get(c,scope);revision=row['revision'] if row else 0
                if revision!=data.expected_revision or (row and row['content_sha']!=data.expected_content_sha256):raise Conflict('candidate version changed; refresh required')
                if revision>=64:raise Conflict('bounded candidate history limit')
                draft=json.loads(row['draft']) if row else None;review=json.loads(row['review']) if row and row['review'] else None
                state=row['state'] if row else None;release_id=row['current_release'] if row else None;content_version=row['content_version'] if row else 0;content_sha=row['content_sha'] if row else None;object_id=row['id'] if row else str(uuid4())
                if data.action=='SAVE':
                    draft=data.draft.model_dump(mode='json')
                    if draft['spec']['service_id']!=scope.service_id or draft['spec']['owner_org_id']!=scope.org_id or draft['spec']['revision']!=str(content_version+1):raise Conflict('candidate draft scope/content version mismatch')
                    if state=='REVIEW_REQUESTED':raise Conflict('return submitted draft before modification')
                    previous=json.loads(row['draft']) if row else None
                    if state=='REJECTED':
                        old_semantic=json.loads(canonical(previous));new_semantic=json.loads(canonical(draft))
                        for semantic in (old_semantic,new_semantic):
                            semantic['spec'].pop('revision')
                            for ref in semantic['spec']['source_refs']:ref.pop('revision')
                            for source in semantic['sources']:source['ref'].pop('revision')
                            semantic['spec']['source_refs'].sort(key=canonical)
                            semantic['sources'].sort(key=canonical)
                        if old_semantic==new_semantic:raise Conflict('rejected draft requires an actual content/source change')
                    # A named source version cannot acquire different bytes or validity.
                    for event in c.execute("SELECT payload FROM candidate_events WHERE scope=? AND action='SAVE'",(canonical(scope.model_dump()),)):
                        for old_source in json.loads(event['payload'])['draft']['sources']:
                            for source in draft['sources']:
                                if source['ref']==old_source['ref'] and source!=old_source:raise Conflict('immutable source version; provide a new source revision')

                    if release_id:c.execute("UPDATE candidate_releases SET state='SUPERSEDED' WHERE id=?",(release_id,))
                    release_id=None;review=None;state='DRAFT';content_version+=1;content_sha=sha(draft)
                else:
                    if row is None:raise Conflict('candidate draft required')
                    if data.action=='SUBMIT':
                        if state!='DRAFT':raise Conflict('candidate draft state required; rejected content must be revised')
                        if not self._sources_current(draft,now):raise Conflict('current source versions required')
                        state='REVIEW_REQUESTED';review=None
                    elif data.action=='RETURN_DRAFT':
                        if state!='REVIEW_REQUESTED':raise Conflict('candidate submission required')
                        state='DRAFT';review=None
                    elif data.action in ('REVIEW','REJECT'):
                        if state!='REVIEW_REQUESTED':raise Conflict('explicit submission required')
                        author=next(h['actor_id'] for h in reversed(self._view(c,scope,row,now)['history']) if h['action']=='SAVE')
                        if actor==author:raise Denied('independent candidate reviewer required')
                        if not self._sources_current(draft,now):raise Conflict('current source versions required')
                        state='REVIEWED' if data.action=='REVIEW' else 'REJECTED';review={'reviewer_id':actor,'content_sha256':content_sha,'reason':data.reason,'reviewed_at':now.isoformat(),'decision':data.action}
                    elif data.action=='PUBLISH':
                        if state!='REVIEWED' or not review or review['content_sha256']!=content_sha:raise Conflict('current explicit candidate review required')
                        if actor==review['reviewer_id']:raise Denied('separate candidate publisher required')
                        self._authorize(review['reviewer_id'],'REVIEW',scope,now)
                        validity=data.publish_validity.model_dump()
                        if not self._sources_current(draft,now) or not active(validity,now):raise Conflict('current source/release validity required')
                        if any(datetime.fromisoformat(validity['valid_from'])<datetime.fromisoformat(v['valid_from']) or datetime.fromisoformat(validity['valid_until'])>datetime.fromisoformat(v['valid_until']) for v in [draft['spec']['validity']]+[s['validity'] for s in draft['sources']]):raise Conflict('release cannot broaden source/spec validity')
                        state='PUBLISHED';release_id=str(uuid4());release={'id':release_id,'namespace':NAMESPACE,'scope':scope.model_dump(),'content_version':content_version,'content_sha256':content_sha,'draft':draft,'reviewer_id':review['reviewer_id'],'publisher_id':actor,'published_at':now.isoformat(),'validity':validity,'deployment_enabled':False,'business_publication':False}
                        c.execute('INSERT INTO candidate_releases VALUES(?,?,?,?)',(release_id,canonical(scope.model_dump()),state,canonical(release)))
                    else:
                        if state!='PUBLISHED' or not release_id:raise Conflict('candidate release required')
                        c.execute("UPDATE candidate_releases SET state='WITHDRAWN' WHERE id=?",(release_id,));state='WITHDRAWN';release_id=None
                payload={'object_id':object_id,'scope':scope.model_dump(),'namespace':NAMESPACE,'revision':revision+1,'content_version':content_version,'content_sha256':content_sha,'action':data.action,'state':state,'actor_id':actor,'candidate_permit_id':permit,'contract_revision':self._config.revision,'reason':data.reason,'created_at':now.isoformat(),'draft':draft,'review':review,'current_release_id':release_id,'deployment_enabled':False,'business_publication':False,'qualification_truth':'UNKNOWN'}
                c.execute('INSERT INTO candidate_rules VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET revision=excluded.revision,content_version=excluded.content_version,state=excluded.state,draft=excluded.draft,content_sha=excluded.content_sha,review=excluded.review,current_release=excluded.current_release',(canonical(scope.model_dump()),object_id,revision+1,content_version,state,canonical(draft),content_sha,canonical(review) if review else None,release_id))
                c.execute('INSERT INTO candidate_events VALUES(?,?,?,?,?,?,?)',(actor,key,fp,canonical(scope.model_dump()),revision+1,data.action,canonical(payload)))
                return payload
    def assess(self,actor,scope,expected_revision,expected_source_sha256):
        with self._mutex:
            now=self.clock();self._authorize(actor,'READ',scope,now)
            with self.repository.connect(write=True) as c:
                view=self._view(c,scope,self._get(c,scope),now)
                if view['revision']!=expected_revision or view['source_sha256']!=expected_source_sha256:raise Conflict('candidate assessment source changed')
                if len(view['assessments'])>=32:raise Conflict('bounded candidate assessments')
                a={'id':str(uuid4()),'actor_id':actor,'created_at':now.isoformat(),'source_sha256':view['source_sha256'],'revision':view['revision'],'candidate_available':view['candidate_available'],'qualification_truth':'UNKNOWN','business_publication':False,'deployment_enabled':False}
                c.execute('INSERT INTO candidate_assessments VALUES(?,?,?)',(a['id'],canonical(scope.model_dump()),canonical(a)))
                return a
