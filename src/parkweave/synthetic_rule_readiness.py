"""Owned-fixture mechanical rule simulation; never formal review or eligibility.

Rules come only from the original isolated candidate workflow. Facts remain
owner asserted/unverified. PostgreSQL supplies current authority and facts;
only the dedicated simulation journal receives new records.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sqlite3
from uuid import UUID, uuid4
from pydantic import Field, field_validator
from .domain import Contract, ISODate, PlanID, Rule, Truth, conjunction, disjunction
from . import preparation as prep, case_fact_clarifications as facts
from .rule_publication_candidate import CandidateEngine, CandidateRepository, Scope, Command, canonical, sha, active
from .store import Conflict, Denied

SCOPE = 'OWNED_SYNTHETIC_RULE_SIMULATION_V1'
FLAGS = dict(scope=SCOPE, governance='DEVELOPMENT_SIMULATION', formal_review=False,
    business_publication=False, deployment_enabled=False, qualification_truth='UNKNOWN',
    qualification_decision='NOT_EVALUATED', fact_authenticity='USER_ASSERTED_UNVERIFIED',
    case_goal_completed=False)

class RuleBinding(Contract):
    binding_id: PlanID
    scope: Scope
    release_id: PlanID
    content_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    region: str = Field(min_length=1, max_length=200)
    epoch: int = Field(ge=1, le=1000000)

class Context(Contract):
    binding_id: PlanID
    as_of: ISODate
    @field_validator('as_of')
    @classmethod
    def aware(cls, value):
        if datetime.fromisoformat(value).utcoffset() is None: raise ValueError('aware applicability time required')
        return value

class Assess(Contract):
    context: Context
    expected_preparation_revision: int = Field(ge=1, le=64)
    expected_source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator('reason')
    @classmethod
    def explicit_reason(cls, value):
        if not value.strip(): raise ValueError('explicit nonblank assessment reason required')
        return value

class SimulationJournal:
    """Separate append-only development journal, with no business DB migration."""
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.name.endswith('.synthetic-readiness.sqlite3') or self.path.is_symlink():
            raise ValueError('dedicated simulation journal path required')
        definitions={
            'simulation_meta': 'CREATE TABLE simulation_meta(namespace TEXT PRIMARY KEY,version INTEGER)',
            'simulation_assessments': 'CREATE TABLE simulation_assessments(actor TEXT,key TEXT,preparation TEXT,fp TEXT,payload TEXT,PRIMARY KEY(actor,key))',
            'simulation_immutable_update': "CREATE TRIGGER simulation_immutable_update BEFORE UPDATE ON simulation_assessments BEGIN SELECT RAISE(ABORT,'immutable simulation assessment'); END",
            'simulation_immutable_delete': "CREATE TRIGGER simulation_immutable_delete BEFORE DELETE ON simulation_assessments BEGIN SELECT RAISE(ABORT,'immutable simulation assessment'); END",
        }
        with sqlite3.connect(self.path) as c:
            objects={r[0]:(r[1],r[2]) for r in c.execute("SELECT name,type,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
            if objects:
                # Existing storage is validated before any DDL or DML. Never
                # repair a partial journal or trust a forged same-name trigger.
                if set(objects)!=set(definitions) or any(objects[name] != ('table' if name in ('simulation_meta','simulation_assessments') else 'trigger',sql) for name,sql in definitions.items()):
                    raise Conflict('foreign or partial simulation schema refused')
                expected={'simulation_meta':['namespace','version'],'simulation_assessments':['actor','key','preparation','fp','payload']}
                if any([x[1] for x in c.execute('PRAGMA table_info('+name+')')]!=columns for name,columns in expected.items()) or c.execute('SELECT namespace,version FROM simulation_meta').fetchall()!=[(SCOPE,1)]:
                    raise Conflict('simulation schema mismatch')
            else:
                for sql in definitions.values(): c.execute(sql)
                c.execute('INSERT INTO simulation_meta VALUES(?,1)',(SCOPE,))
    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=3); c.row_factory = sqlite3.Row
        try:
            if write: c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except sqlite3.OperationalError as e:
            c.rollback(); raise Conflict('simulation journal busy; recover original key') from e
        except BaseException:
            c.rollback(); raise
        finally: c.close()


def evaluate(rule, snapshot, choices, applicable, as_of, *, purpose_current=True, blocked=None):
    """Finite three-valued AST, including every currently authorized conflict."""
    selected = {v['field']: str(v['assertion_id']) for v in choices}
    leaves = []
    def visit(node):
        if node.kind in ('AND', 'OR'):
            children = [visit(x) for x in node.children]
            return (conjunction if node.kind == 'AND' else disjunction)(children)
        truth = Truth.UNKNOWN; reason = blocked
        rows = [x for x in snapshot['sources'] if x['field_name'] == node.field]
        current = [x for x in rows if applicable.get(x['id'], False) and datetime.fromisoformat(x['valid_from']) <= as_of < datetime.fromisoformat(x['valid_until'])]
        chosen = next((x for x in current if x['id'] == selected.get(node.field)), None)
        if reason: pass
        elif node.kind == 'MANUAL': reason = 'HUMAN_JUDGMENT_REQUIRED'
        elif node.field not in facts.FIELDS: reason = 'UNSUPPORTED_PURPOSE_FIELD'
        elif not rows: reason = 'MISSING_EVIDENCE'
        elif not current: reason = 'EXPIRED_OR_NOT_YET_VALID_EVIDENCE'
        elif len({sha([x['value'], x['unit']]) for x in current}) > 1: reason = 'CONFLICTING_EVIDENCE'
        elif not purpose_current or chosen is None: reason = 'CURRENT_FACT_PURPOSE_CONFIRMATION_REQUIRED'
        else:
            truth = Truth.TRUE if node.kind == 'EXISTS' or type(chosen['value']) is type(node.expected) and chosen['value'] == node.expected else Truth.FALSE
            reason = 'SYNTHETIC_MECHANICAL_MATCH' if truth == Truth.TRUE else 'SYNTHETIC_MECHANICAL_MISMATCH'
        leaves.append(dict(kind=node.kind, field=node.field, truth=truth.value, reason=reason,
            evidence=[dict(id=x['id'], revision=x['revision'], fingerprint=x['fingerprint'], source_ref=x['source_ref']) for x in current],
            selected_assertion_id=selected.get(node.field)))
        return truth
    result = visit(rule)
    return dict(synthetic_simulated_condition_truth=result.value, conditions=leaves,
        material_requirements_status='SIMULATION_ONLY', next_action='SPECIALIST_REVIEW_REQUIRED', **FLAGS)


class SyntheticRuleReadiness:
    def __init__(self, store, owner, candidate_engine=None, journal=None, *, bindings=(), enabled_for_isolated_tests=False):
        from .case_fact_clarifications import FixtureDatabaseEvidence
        if enabled_for_isolated_tests is not True or type(getattr(owner, '_case_fact_fixture_receipt', None)) is not FixtureDatabaseEvidence:
            raise Denied('explicit owned Linux simulation fixture required')
        if type(candidate_engine) is not CandidateEngine or type(candidate_engine.repository) is not CandidateRepository or type(journal) is not SimulationJournal:
            raise Denied('original isolated candidate source and separate simulation journal required')
        self.store, self.owner, self.engine, self.journal = store, owner, candidate_engine, journal
        self.bindings = tuple(RuleBinding.model_validate(x.model_dump()) for x in bindings)
        if not 1 <= len(self.bindings) <= 16 or len({x.binding_id for x in self.bindings}) != len(self.bindings): raise ValueError('bounded unique trusted rule bindings required')
        with owner.connect() as c:
            owner._case_fact_fixture_receipt.authorize_migration(c)
            self.identity = c.execute('SELECT current_database() name,(SELECT oid FROM pg_database WHERE datname=current_database()) oid,inet_server_addr() address,inet_server_port() port,pg_postmaster_start_time() started').fetchone()
        with store.connect() as c: self._fixture(c)

    def _fixture(self, c):
        actual = c.execute('SELECT current_database() name,(SELECT oid FROM pg_database WHERE datname=current_database()) oid,inet_server_addr() address,inet_server_port() port,pg_postmaster_start_time() started').fetchone()
        if actual != self.identity: raise Denied('simulation PostgreSQL fixture identity changed')

    def _parent(self, c, token, id):
        self._fixture(c)
        c.execute("SET LOCAL lock_timeout='3s'")
        p = self.store.auth(c, token, lock=True)
        row = prep.scoped(self.store, c, p, id)
        if row['owner_id'] != p['id'] or row['namespace'] != 'SYNTHETIC': raise Denied('own synthetic preparation required')
        facts._field_locks(c, p['id'])
        self.store.check_fields(c, p, list(facts.FIELDS), 'READ')
        return p, row

    def _source_read_authority(self,p,row,context):
        binding=next((x for x in self.bindings if x.binding_id==context.binding_id),None)
        if binding is None or (binding.scope.park_id,binding.scope.org_id,binding.scope.service_id)!=(p['park_id'],p['org_id'],row['service_id']): raise Denied('trusted rule binding scope required')
        self.engine._authorize(p['id'],'READ',binding.scope,self.engine.clock())
        return binding

    def _source(self, c, p, row, context, source_connection):
        binding=self._source_read_authority(p,row,context)
        now=self.engine.clock()
        candidate_row = self.engine._get(source_connection, binding.scope)
        try:
            view = self.engine._view(source_connection, binding.scope, candidate_row, now)
        except (KeyError, ValueError, TypeError, StopIteration):
            raise Conflict('original synthetic rule source unavailable')
        release = next((x for x in view['releases'] if x['id'] == binding.release_id), None)
        self._proof(source_connection, binding.scope, candidate_row, release)
        reason = None
        if release is None or not view['candidate_available'] or candidate_row['current_release'] != binding.release_id: reason = 'CURRENT_SYNTHETIC_REVIEWED_RELEASE_REQUIRED'
        elif release['content_sha256'] != binding.content_sha256: raise Conflict('trusted release content binding changed')
        elif not active(release['validity'], datetime.fromisoformat(context.as_of)) or not all(active(x['validity'], datetime.fromisoformat(context.as_of)) for x in [release['draft']['spec']] + release['draft']['sources']): reason = 'EXPIRED_OR_NOT_YET_VALID_SOURCE'
        purpose_current = False; choices = []; snapshot = {'sources': []}; applicable = {}; status = {}
        try:
            facts._scope(self.store, c, p, row, require_write=True)
            snapshot, fact_sha, applicable = facts._sources(self.store, c, row, p)
            ledger = facts._stored_ledger(c, row)
            if ledger is not None:
                status = facts._evaluate(row, ledger, snapshot, fact_sha, applicable)
                purpose_current = status['state'] == 'CURRENT'
                choices = ledger['events'][-1]['choices']
            else: status = {'state': 'NOT_DECLARED'}
        except (Denied, Conflict):
            status = {'state': 'CURRENT_FACT_AUTHORITY_UNAVAILABLE'}
            reason = reason or 'CURRENT_FACT_AUTHORITY_UNAVAILABLE'
        as_of=datetime.fromisoformat(context.as_of)
        for field in facts.FIELDS:
            rows=[x for x in snapshot['sources'] if x['field_name']==field]
            current=[x for x in rows if applicable.get(x['id'],False) and datetime.fromisoformat(x['valid_from'])<=as_of<datetime.fromisoformat(x['valid_until'])]
            if len({sha([x['value'],x['unit']]) for x in current})>1: reason=reason or 'CONFLICTING_EVIDENCE'
            elif purpose_current and not current: reason=reason or 'EXPIRED_OR_NOT_YET_VALID_EVIDENCE'
        region_condition=evaluate(Rule(kind='EQ',field='region',expected=binding.region),snapshot,choices,applicable,as_of,purpose_current=purpose_current)
        if region_condition['synthetic_simulated_condition_truth']=='FALSE': reason=reason or 'REGION_NOT_APPLICABLE'
        elif region_condition['synthetic_simulated_condition_truth']=='UNKNOWN': reason=reason or region_condition['conditions'][0]['reason']
        local = c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s', (row['id'],)).fetchone()
        if prep.case_write_blocked(c, row) or local and local['state']=='LOCAL_RECORD_CLOSED': reason = reason or 'CASE_NOT_CURRENTLY_ACTIONABLE'
        source = dict(binding=binding.model_dump(mode='json'), context=context.model_dump(), preparation_id=str(row['id']), case_id=str(row['case_id']), preparation_revision=row['revision'],
            candidate_source_sha256=view['source_sha256'], candidate_revision=view['revision'], release=release,
            contract_sha256=sha(self.engine._config.model_dump()), trusted_bindings_sha256=sha([x.model_dump(mode='json') for x in self.bindings]),
            facts=snapshot, applicable=applicable, region_condition=region_condition['conditions'][0], purpose_status=status, selected_facts=choices, current_block=reason)
        expression = release['draft']['spec']['eligibility'] if release else {'kind': 'MANUAL'}
        rule = Rule.model_validate(expression if isinstance(expression, dict) else {'kind': 'MANUAL'})
        result = evaluate(rule, snapshot, choices, applicable, datetime.fromisoformat(context.as_of), purpose_current=purpose_current, blocked=reason)
        return source, sha(source), result

    def _proof(self, c, scope, row, release):
        if not row: return
        events = c.execute('SELECT * FROM candidate_events WHERE scope=? ORDER BY revision', (canonical(scope.model_dump()),)).fetchall()
        previous_sha = None; previous_draft = None
        state=None; review=None; author=None; content_version=0; release_id=None; object_id=None
        releases = {x['id']: json.loads(x['payload']) for x in c.execute('SELECT * FROM candidate_releases WHERE scope=?', (canonical(scope.model_dump()),))}
        try:
            if len(events) != row['revision']: raise ValueError()
            for n, e in enumerate(events, 1):
                h = json.loads(e['payload'])
                if any(h[k] != v for k, v in [('actor_id', e['actor']), ('revision', n), ('action', e['action']), ('scope', scope.model_dump())]) or e['revision'] != n: raise ValueError()
                valid = releases[h['current_release_id']]['validity'] if h['action'] == 'PUBLISH' else None
                data = Command(action=h['action'], expected_revision=n-1, expected_content_sha256=previous_sha,
                    draft=h['draft'] if h['action']=='SAVE' else None, publish_validity=valid, reason=h['reason'])
                if e['fp'] != sha({'scope':scope.model_dump(), **data.model_dump(mode='json')}) or h['content_sha256'] != sha(h['draft']): raise ValueError()
                if h['action'] != 'SAVE' and h['draft'] != previous_draft: raise ValueError()
                if object_id is not None and h['object_id'] != object_id: raise ValueError()
                object_id=h['object_id']; UUID(object_id)
                action=h['action']
                if action=='SAVE':
                    if state=='REVIEW_REQUESTED': raise ValueError()
                    content_version+=1; author=h['actor_id']; state='DRAFT'; review=None; release_id=None
                elif action=='SUBMIT':
                    if state!='DRAFT': raise ValueError()
                    state='REVIEW_REQUESTED'; review=None
                elif action=='RETURN_DRAFT':
                    if state!='REVIEW_REQUESTED': raise ValueError()
                    state='DRAFT'; review=None
                elif action in ('REVIEW','REJECT'):
                    if state!='REVIEW_REQUESTED' or h['actor_id']==author: raise ValueError()
                    state='REVIEWED' if action=='REVIEW' else 'REJECTED'
                    review=dict(reviewer_id=h['actor_id'],content_sha256=h['content_sha256'],reason=h['reason'],reviewed_at=h['created_at'],decision=action)
                elif action=='PUBLISH':
                    if state!='REVIEWED' or not review or h['actor_id']==review['reviewer_id']: raise ValueError()
                    state='PUBLISHED'; release_id=h['current_release_id']; UUID(release_id)
                elif action=='WITHDRAW':
                    if state!='PUBLISHED': raise ValueError()
                    state='WITHDRAWN'; release_id=None
                if (h['state'],h['review'],h['content_version'],h['current_release_id'])!=(state,review,content_version,release_id): raise ValueError()
                previous_sha, previous_draft = h['content_sha256'], h['draft']
            last = json.loads(events[-1]['payload'])
            if (last['draft'], last['content_sha256'], last['content_version'], last['state'], last['current_release_id']) != (json.loads(row['draft']), row['content_sha'], row['content_version'], row['state'], row['current_release']) or last['review'] != (json.loads(row['review']) if row['review'] else None): raise ValueError()
            if release is not None:
                publish = next(json.loads(e['payload']) for e in reversed(events) if e['action']=='PUBLISH' and json.loads(e['payload'])['current_release_id']==release['id'])
                review = publish['review']
                if release['draft'] != publish['draft'] or release['content_sha256'] != publish['content_sha256'] or release['content_version'] != publish['content_version'] or release['scope'] != scope.model_dump() or release['reviewer_id'] != review['reviewer_id'] or release['publisher_id'] != publish['actor_id'] or release['published_at'] != publish['created_at']: raise ValueError()
                review_event = next(json.loads(e['payload']) for e in reversed(events[:publish['revision']-1]) if e['action']=='REVIEW')
                if review != review_event['review'] or review_event['actor_id'] != review['reviewer_id']: raise ValueError()
                if any(datetime.fromisoformat(release['validity']['valid_from']) < datetime.fromisoformat(v['valid_from']) or datetime.fromisoformat(release['validity']['valid_until']) > datetime.fromisoformat(v['valid_until']) for v in [release['draft']['spec']['validity']]+[x['validity'] for x in release['draft']['sources']]): raise ValueError()
        except (KeyError, ValueError, TypeError, StopIteration, IndexError): raise Conflict('original synthetic rule workflow proof invalid')

    def _records(self, j, p, row):
        records=[]
        for r in j.execute('SELECT * FROM simulation_assessments WHERE actor=? AND preparation=? ORDER BY rowid', (p['id'],str(row['id']))):
            v=json.loads(r['payload'])
            if v.get('receipt_sha256') != sha({k:x for k,x in v.items() if k!='receipt_sha256'}) or (v['actor_id'],v['request_key'],v['preparation_id'],v['fingerprint']) != (r['actor'],r['key'],r['preparation'],r['fp']): raise Conflict('simulation history proof invalid')
            records.append(v)
        return records

    def read(self, token, id, context):
        with self.engine._mutex:
            # Current owner/source READ and journal proof precede optional
            # current-source lookup. Historical GET never rents a writer lease.
            with self.store.connect() as c, self.journal.connect() as j:
                p,row=self._parent(c,token,id)
                binding=self._source_read_authority(p,row,context)
                records=self._records(j,p,row); unavailable=False
                try:
                    with self.engine.repository.connect() as src:
                        source,hash,result=self._source(c,p,row,context,src)
                except (Conflict,sqlite3.OperationalError) as error:
                    if not records: raise
                    unavailable=True
                    source=dict(binding=binding.model_dump(mode='json'),context=context.model_dump(),preparation_id=str(id),case_id=str(row['case_id']),preparation_revision=row['revision'],current_block='CURRENT_RULE_SOURCE_UNAVAILABLE',release=None,facts={'sources':[]},selected_facts=[],purpose_status={'state':'CURRENT_SOURCE_UNAVAILABLE'})
                    hash=sha(source)
                    result=evaluate(Rule(kind='MANUAL'),{'sources':[]},[],{},datetime.fromisoformat(context.as_of),blocked='CURRENT_RULE_SOURCE_UNAVAILABLE')
                return dict(**FLAGS, actor_ref=p['id'], case_id=str(row['case_id']), preparation_id=str(id), preparation_revision=row['revision'], source_sha256=hash, sources=source,
                    result=result,current_source_unavailable=unavailable,rule_review_status='SYNTHETIC_REVIEWED' if source['current_block'] is None else 'NOT_CURRENT',
                    history=[dict(**x,current_truth=x['result']['synthetic_simulated_condition_truth'] if not unavailable and x['source_sha256']==hash else 'UNKNOWN',state='CURRENT' if not unavailable and x['source_sha256']==hash else 'STALE') for x in records])

    def assess(self, token, id, key, data):
        if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key): raise ValueError('bounded original request key required')
        fp=sha(dict(preparation_id=str(id),**data.model_dump(mode='json')))
        with self.engine._mutex:
            with self.engine.repository.connect(write=True) as src, self.store.connect() as c, self.journal.connect(write=True) as j:
                p,row=self._parent(c,token,id); prep.case_write_guard(c,row)
                local=c.execute('SELECT state FROM case_local_lifecycles WHERE preparation_id=%s',(row['id'],)).fetchone()
                if local and local['state']=='LOCAL_RECORD_CLOSED': raise Conflict('closed local record; simulation history only')
                facts._scope(self.store,c,p,row,require_write=False)
                old=j.execute('SELECT * FROM simulation_assessments WHERE actor=? AND key=?',(p['id'],key)).fetchone()
                records=self._records(j,p,row)
                source,hash,result=self._source(c,p,row,data.context,src)
                if old:
                    if old['preparation']!=str(id) or old['fp']!=fp: raise Conflict('simulation key fingerprint mismatch')
                    return next(x for x in records if x['request_key']==key)
                if (row['revision'],hash)!=(data.expected_preparation_revision,data.expected_source_sha256): raise Conflict('simulation source changed; read current binding')
                if len(records)>=32: raise Conflict('bounded simulation history reached')
                record=dict(**FLAGS,id=str(uuid4()),actor_id=p['id'],request_key=key,fingerprint=fp,preparation_id=str(id),case_id=str(row['case_id']),created_at=datetime.now(timezone.utc).isoformat(),reason=data.reason,source_sha256=hash,sources=source,result=result)
                record['receipt_sha256']=sha(record)
                j.execute('INSERT INTO simulation_assessments VALUES(?,?,?,?,?)',(p['id'],key,str(id),fp,canonical(record)))
                return record

    def recover(self, token, id, key, context):
        view=self.read(token,id,context)
        old=next((x for x in view['history'] if x['request_key']==key),None)
        return dict(**FLAGS,status='COMMITTED' if old else 'NOT_OBSERVED',receipt=old,historical_only=True,automatically_replayed=False,current=view)
