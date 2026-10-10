"""Default-off, exact first-Case resource Approval in issued synthetic PG only.

The original owner approves their existing local resource action. No role,
Grant, worker authority, publication or external execution is created here.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from psycopg.sql import SQL, Literal as SQLLiteral

from . import case_fact_clarifications as facts, case_resource_delivery as delivery
from . import case_resources as cr, controlled_plans as cp, preparation as prep
from . import resource_combinations as rc, resource_holds as rh
from .store import Conflict, Denied

SCOPE = 'ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1'
PURPOSE = 'CASE_RESOURCE_DELIVERY'
LIMIT = 64
OBJECT_LIMIT = 8
COL = 'candidate_plan_approvals'
TRIGGER_BODY = """
DECLARE previous jsonb; next_value jsonb; i integer; n integer;
BEGIN
 previous:=OLD.candidate_plan_approvals; next_value:=NEW.candidate_plan_approvals;
 IF next_value IS NOT DISTINCT FROM previous THEN
   IF NEW.candidate_plan_approval_head IS DISTINCT FROM OLD.candidate_plan_approval_head THEN
     RAISE EXCEPTION 'immutable candidate Approval head';
   END IF;
   RETURN NEW;
 END IF;
 IF next_value IS NULL OR next_value->>'namespace'<>'ISOLATED_SYNTHETIC_CASE_RESOURCE_APPROVAL_V1'
    OR next_value->>'version'<>'1' OR jsonb_typeof(next_value->'events')<>'array' THEN
   RAISE EXCEPTION 'candidate Approval history required';
 END IF;
 n:=jsonb_array_length(next_value->'events');
 IF n<1 OR n>64 OR (next_value->>'revision')::integer<>n THEN
   RAISE EXCEPTION 'bounded candidate Approval history required';
 END IF;
 IF previous IS NULL THEN
   IF n<>1 THEN RAISE EXCEPTION 'initial candidate Approval event required'; END IF;
 ELSE
   IF n<>jsonb_array_length(previous->'events')+1 THEN
     RAISE EXCEPTION 'candidate Approval append only';
   END IF;
   FOR i IN 0..n-2 LOOP
     IF next_value->'events'->i IS DISTINCT FROM previous->'events'->i THEN
       RAISE EXCEPTION 'immutable candidate Approval event';
     END IF;
   END LOOP;
 END IF;
 NEW.candidate_plan_approval_head:=jsonb_build_object('revision',n,'sha256',next_value->'events'->(n-1)->>'sha256');
 RETURN NEW;
END
"""


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: int = Field(ge=0, le=LIMIT)
    delivery: delivery.Deliver

    @model_validator(mode='after')
    def no_approval(self):
        if self.delivery.approval_id is not None:
            raise ValueError('proposal cannot claim an existing Approval')
        return self


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    action: Literal['APPROVE', 'REVOKE']
    approval_id: UUID = Field(strict=False)
    expected_revision: int = Field(ge=1, le=LIMIT)
    expected_binding_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def reason_required(self):
        if not self.reason.strip(): raise ValueError('explicit Approval decision required')
        return self


def body(data):
    return data.model_dump(mode='json', exclude_none=True)


def _fingerprint(id, request):
    return cp._hash(dict(preparation_id=str(id), request=request))


def _ledger(parent):
    value = parent.get(COL)
    head = parent.get('candidate_plan_approval_head')
    if value is None:
        if head is not None: raise Conflict('candidate Approval original head required')
        return dict(namespace=SCOPE, version=1, revision=0, events=[]), {}
    if (not isinstance(value, dict) or set(value) != {'namespace', 'version', 'revision', 'events'}
        or value['namespace'] != SCOPE or type(value['version']) is not int or value['version'] != 1
        or type(value['revision']) is not int or not 1 <= value['revision'] <= LIMIT
        or not isinstance(value['events'], list) or len(value['events']) != value['revision']):
        raise Conflict('candidate Approval ledger malformed')
    if (not isinstance(value['events'][-1],dict) or not isinstance(head,dict) or set(head)!={'revision','sha256'}
        or type(head['revision']) is not int or head['revision']!=value['revision']
        or head['sha256']!=value['events'][-1].get('sha256')):
        raise Conflict('candidate Approval original head mismatch')
    items = {}; keys = set(); ids = set(); previous = None
    for revision, e in enumerate(value['events'], 1):
        required = {'id', 'revision', 'approval_id', 'action', 'actor_id', 'key', 'fingerprint',
            'request', 'binding', 'receipt', 'at', 'previous_sha256', 'sha256'}
        try:
            if (not isinstance(e, dict) or set(e) != required or type(e['revision']) is not int
                or e['revision'] != revision or e['actor_id'] != parent['owner_id']
                or not isinstance(e['key'], str) or not 1 <= len(e['key']) <= 100
                or e['id'] in ids or e['key'] in keys or e['previous_sha256'] != previous
                or e['sha256'] != cp._hash({k:v for k,v in e.items() if k != 'sha256'})
                or e['fingerprint'] != _fingerprint(parent['id'], e['request'])): raise ValueError()
            UUID(e['id']); UUID(e['approval_id'])
            if datetime.fromisoformat(e['at']).tzinfo is None: raise ValueError()
            action = e['action']; request = e['request']; aid = e['approval_id']
            if action == 'PROPOSE':
                data = Proposal.model_validate({k:v for k,v in request.items() if k != 'action'})
                if (request.get('action') != action or data.expected_revision != revision-1
                    or aid in items or len(items) >= OBJECT_LIMIT or e['receipt'] is not None
                    or not isinstance(e['binding'], dict)): raise ValueError()
                b = e['binding']
                if (set(b) != {'scope','purpose','context','plan_revision','execution_identity','authority','authority_sha256','materials','members','resource_revisions','source_versions','valid_until','contract_scope_ids'}
                    or b.get('purpose') != PURPOSE or b.get('scope') != SCOPE
                    or b['authority_sha256'] != cp._hash(b['authority'])
                    or b['valid_until'] != data.delivery.valid_until.isoformat()
                    or b['plan_revision'] != data.delivery.expected_plan_revision
                    or b['context']['preparation_revision'] != data.delivery.expected_preparation_revision
                    or sorted((h['id'],h['resource_revision']) for h in b['members']) != sorted((str(m.hold_id),m.expected_revision) for m in data.delivery.members)
                    or any(str(parent[k]) != b['context'][v] for k,v in
                        [('id','preparation_id'),('case_id','case_id'),('run_id','run_id'),
                         ('owner_id','owner_id'),('park_id','park_id'),('org_id','org_id')])): raise ValueError()
                items[aid] = dict(id=aid, state='PROPOSED', proposal=e, approval=None, consumption=None)
            elif action in ('APPROVE', 'REVOKE'):
                data = Command.model_validate(request)
                item = items[aid]
                if (data.action != action or str(data.approval_id) != aid or data.expected_revision != revision-1
                    or data.expected_binding_sha256 != cp._hash(item['proposal']['binding'])
                    or e['binding'] is not None or e['receipt'] is not None
                    or item['state'] not in ('PROPOSED', 'APPROVED')): raise ValueError()
                if action == 'APPROVE':
                    if item['state'] != 'PROPOSED': raise ValueError()
                    item.update(state='APPROVED', approval=e)
                else: item['state'] = 'REVOKED'
            elif action == 'CONSUME':
                item = items[aid]
                data = delivery.Deliver.model_validate(request['delivery'])
                if (set(request) != {'action', 'delivery'} or request['action'] != action
                    or str(data.approval_id) != aid or item['state'] != 'APPROVED'
                    or e['binding'] is not None or not isinstance(e['receipt'], dict)
                    or {k:v for k,v in body(data).items() if k != 'approval_id'} != body(
                        Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k != 'action'}).delivery)):
                    raise ValueError()
                item.update(state='CONSUMED', consumption=e)
            else: raise ValueError()
        except (KeyError, ValueError, TypeError, AttributeError):
            raise Conflict('candidate Approval original proof mismatch')
        keys.add(e['key']); ids.add(e['id']); previous = e['sha256']
    return value, items


class IsolatedPlanApproval:
    def __init__(self, owner_store=None, fixture_proof=None, *, preparation_ids=(), enabled_for_isolated_tests=False):
        self.enabled = enabled_for_isolated_tests is True
        self.owner, self.proof = owner_store, fixture_proof
        self.ids = frozenset(str(UUID(str(id))) for id in preparation_ids)
        if not self.enabled: return
        if owner_store is None or owner_store.mode != 'LOCAL' or not 1 <= len(self.ids) <= 16:
            raise Denied('explicit original synthetic Approval scope required')
        self._issued()
        with owner_store.connect() as c:
            self._owner_proof(c)
            self.endpoint = (c.info.host, c.info.port)
            for id in sorted(self.ids):
                p = c.execute('SELECT p.* FROM principals p JOIN preparations r ON r.owner_id=p.id WHERE r.id=%s', (UUID(id),)).fetchone()
                if not p or p['role'] != 'enterprise_operator' or not p['active']:
                    raise Denied('existing synthetic resource owner required')
                owner_store.check_capability(c,p,'READ'); owner_store.check_capability(c,p,'EXECUTE')
                prep.grant(owner_store,c,p,'PREPARE')
            column = c.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='preparations' AND column_name=%s", (COL,)).fetchone()
            if column is None:
                c.execute('ALTER TABLE preparations ADD COLUMN candidate_plan_approvals jsonb CHECK(candidate_plan_approvals IS NULL OR jsonb_typeof(candidate_plan_approvals)=\'object\'), ADD COLUMN candidate_plan_approval_head jsonb CHECK(candidate_plan_approval_head IS NULL OR jsonb_typeof(candidate_plan_approval_head)=\'object\')')
                c.execute(SQL('CREATE FUNCTION candidate_plan_approval_prefix() RETURNS trigger LANGUAGE plpgsql AS {}').format(SQLLiteral(TRIGGER_BODY)))
                c.execute('CREATE TRIGGER candidate_plan_approval_prefix BEFORE UPDATE OF candidate_plan_approvals,candidate_plan_approval_head ON preparations FOR EACH ROW EXECUTE FUNCTION candidate_plan_approval_prefix()')
            elif column['data_type'] != 'jsonb': raise Denied('foreign candidate Approval column refused')
            self._schema(c)

    def _issued(self):
        p = self.proof
        if (not self.enabled or type(p) is not facts.FixtureDatabaseEvidence
            or facts._fixture_databases.get(p.nonce) is not p
            or facts._fixture_clusters.get(p.cluster.nonce) is not p.cluster
            or set(dict(p.cluster.initial_databases)) != {'postgres','template0','template1'}
            or p.database_name in dict(p.cluster.initial_databases)):
            raise Denied('issued owned temporary Approval fixture required')
        return p

    def _owner_proof(self,c):
        p = self._issued(); actual = facts._migration_identity(c); facts._same_cluster(p.cluster,actual)
        if (actual['database_oid'] != p.database_oid or actual['database_name'] != p.database_name
            or actual['owner_name'] != p.cluster.owner or actual['session_name'] != p.cluster.owner):
            raise Denied('Approval fixture owner mismatch')

    def _schema(self,c):
        row = c.execute("""SELECT f.prosrc,t.tgenabled,t.tgtype,
            t.tgattr::text=a.attnum::text||' '||h.attnum::text correct_column, f.proowner=r.relowner correct_owner,
            f.prosecdef, f.proconfig, l.lanname
            FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid JOIN pg_class r ON r.oid=t.tgrelid
            JOIN pg_attribute a ON a.attrelid=r.oid AND a.attname='candidate_plan_approvals'
            JOIN pg_attribute h ON h.attrelid=r.oid AND h.attname='candidate_plan_approval_head'
            JOIN pg_language l ON l.oid=f.prolang
            WHERE t.tgrelid='preparations'::regclass AND t.tgname='candidate_plan_approval_prefix' AND NOT t.tgisinternal""").fetchone()
        if (not row or row['prosrc'] != TRIGGER_BODY or row['tgenabled'] != 'O' or row['tgtype'] != 19
            or not row['correct_column'] or not row['correct_owner'] or row['prosecdef']
            or row['proconfig'] is not None or row['lanname']!='plpgsql'):
            raise Denied('immutable candidate Approval schema required')

    def _connection(self,c):
        p = self._issued()
        row = c.execute('SELECT oid,datname,pg_postmaster_start_time() started FROM pg_database WHERE datname=current_database()').fetchone()
        if ((c.info.host,c.info.port) != self.endpoint or row['oid'] != p.database_oid
            or row['datname'] != p.database_name or row['started'] != p.cluster.postmaster_start):
            raise Denied('Approval fixture connection mismatch')
        self._schema(c)

    def attach_store(self,store):
        if not self.enabled or store.mode != 'LOCAL': raise Denied('isolated plan Approval disabled')
        with self.owner.connect() as c: self._owner_proof(c)
        with store.connect() as c: self._connection(c)
        store._isolated_plan_approval = self
        return store

    def _scope(self,c,p,parent):
        self._connection(c)
        if (str(parent['id']) not in self.ids or p['role'] != 'enterprise_operator'
            or p['id'] != parent['owner_id'] or parent['namespace'] != 'SYNTHETIC'):
            raise Denied('original candidate Case owner required')

    def _authority(self,store,c,p,parent,hs):
        participant_ids=[p['id'],parent['reviewer_id']]
        principal = c.execute('SELECT id,park_id,org_id,role,active,xmin::text row_version FROM principals WHERE id=ANY(%s) ORDER BY id', (participant_ids,)).fetchall()
        capabilities = c.execute("SELECT principal_id,park_id,org_id,capability,active,revision FROM capability_grants WHERE principal_id=ANY(%s) AND capability IN ('READ','EXECUTE') ORDER BY principal_id,capability", (participant_ids,)).fetchall()
        prepares = c.execute("SELECT principal_id,park_id,org_id,capability,active,xmin::text row_version FROM preparation_grants WHERE principal_id=ANY(%s) ORDER BY principal_id,capability", ([p['id'],parent['reviewer_id']],)).fetchall()
        resources = c.execute('SELECT principal_id,resource_id,park_id,org_id,capability,active,xmin::text row_version FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=ANY(%s) ORDER BY resource_id,capability', (p['id'],[h['resource_id'] for h in hs])).fetchall()
        run = store.scoped_run(c,p,parent['run_id'])
        identity = {k:run[k] for k in ('id','principal_id','park_id','org_id','revision','state','fence','worker_id','namespace')}
        return cp._normal(dict(principal=principal,capabilities=capabilities,preparations=prepares,resources=resources)), cp._normal(dict(kind='ORIGINAL_OWNER_HTTP',actor_id=p['id'],role=p['role'],run=identity))

    def _source(self,store,c,p,parent,data,*,consumed=None):
        self._scope(c,p,parent)
        if consumed is None:
            context, candidate_sha, hs, now = delivery._candidate(store,c,p,parent,data,observe=False)
            if (parent['revision'] != data.expected_preparation_revision
                or parent['service_case_plan']['revision'] != data.expected_plan_revision
                or cp._hash(dict(source=candidate_sha,valid_until=data.valid_until.isoformat())) != data.expected_source_sha256):
                raise Conflict('Approval original preview changed')
        else:
            hs = [rh._own(c,p,m.hold_id) for m in data.members]
            rc._scope_lock(c,p,hs,write=True)
            hs = [rh._own(c,p,m.hold_id,lock=True) for m in data.members]
            if any(h['state'] != 'CONFIRMED' or str(h['combination_id']) != consumed for h in hs):
                raise Conflict('Approval actual delivery members mismatch')
            context, issues = delivery._context(store,c,p,parent)
            if issues: raise Conflict('Approval prerequisite changed before commit')
            hs = [dict(h,state='HELD',combination_id=None) for h in hs]
            if parent['service_case_plan']['revision'] != data.expected_plan_revision:
                raise Conflict('Approval plan changed before commit')
        rules = rc._scope_lock(c,p,hs,write=True)
        store.check_capability(c,p,'EXECUTE'); prep.grant(store,c,p,'PREPARE')
        authority, identity = self._authority(store,c,p,parent,hs)
        # Take the time after every possible source/authority lock wait.
        now = rh._now(c)
        if not now < data.valid_until <= now + timedelta(seconds=120):
            raise Conflict('Approval expired')
        if any(now >= h['expires_at'] or data.valid_until > h['expires_at'] for h in hs):
            raise Conflict('Approval original hold expired')
        slots = [{k:e[k] for k in ('id','slot','version','source_sha256')} for e in prep.latest(c,parent['id'])]
        versions=dict(catalog=c.execute('SELECT xmin::text row_version FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
            (parent['park_id'],parent['service_id'],parent['service_version'])).fetchone(),
            resources=c.execute('SELECT id,xmin::text row_version FROM synthetic_resources WHERE id=ANY(%s) ORDER BY id',
                ([h['resource_id'] for h in hs],)).fetchall(),
            run=c.execute('SELECT id,xmin::text row_version FROM runs WHERE id=%s',(parent['run_id'],)).fetchone())
        return cp._normal(dict(scope=SCOPE,purpose=PURPOSE,context=context,
            plan_revision=parent['service_case_plan']['revision'],execution_identity=identity,
            authority=authority,authority_sha256=cp._hash(authority),materials=slots,
            members=hs,resource_revisions=[rules[k] for k in sorted(rules,key=str)],source_versions=versions,
            valid_until=data.valid_until.isoformat(),contract_scope_ids=sorted(self.ids))), now

    def _append(self,c,p,parent,key,request,aid,*,binding=None,receipt=None,event_id=None):
        ledger, items = _ledger(parent); ledger=deepcopy(ledger)
        active = sum(i['state'] in ('PROPOSED','APPROVED') for i in items.values())
        remaining = active + (1 if request['action']=='PROPOSE' else -1 if request['action'] in ('REVOKE','CONSUME') else 0)
        if ledger['revision']+1+remaining > LIMIT: raise Conflict('Approval history reserves explicit withdrawal capacity')
        e = cp._normal(dict(id=event_id or uuid4(),revision=ledger['revision']+1,approval_id=aid,
            action=request['action'],actor_id=p['id'],key=key,fingerprint=_fingerprint(parent['id'],request),
            request=request,binding=binding,receipt=receipt,at=rh._now(c),
            previous_sha256=ledger['events'][-1]['sha256'] if ledger['events'] else None))
        e['sha256']=cp._hash(e); ledger['events'].append(e); ledger['revision']+=1
        old=parent.get(COL)
        row=c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s AND candidate_plan_approvals IS NOT DISTINCT FROM %s RETURNING *', (Jsonb(ledger),parent['id'],Jsonb(old) if old is not None else None)).fetchone()
        if row is None: raise Conflict('Approval CAS changed')
        _ledger(row)
        return row,e

    def _replay(self,parent,key,request):
        ledger,_=_ledger(parent)
        e=next((e for e in ledger['events'] if e['key']==key),None)
        if e and e['fingerprint'] != _fingerprint(parent['id'],request): raise Conflict('Approval original key fingerprint mismatch')
        return e

    def _key(self,c,p,parent,key):
        if not isinstance(key,str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):
            raise Conflict('bounded original Approval key required')
        rh._key(c,p,key)
        other=c.execute('SELECT id FROM preparations WHERE owner_id=%s AND park_id=%s AND org_id=%s AND id<>%s AND candidate_plan_approvals @> %s LIMIT 1',
            (p['id'],p['park_id'],p['org_id'],parent['id'],Jsonb({'events':[{'actor_id':p['id'],'key':key}]}))).fetchone()
        if other: raise Conflict('Approval original key belongs to another Case')

    def _guard(self,c,parent,aid,*,consumed=None,auth_only=False):
        if not hasattr(c,'_plan_approval_checks'): raise Denied('guarded Approval transaction required')
        check=dict(id=str(parent['id']),approval_id=str(aid),consumed=consumed,auth_only=auth_only)
        if check not in c._plan_approval_checks: c._plan_approval_checks.append(check)

    def recheck(self,store,c,check):
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(UUID(check['id']),)).fetchone()
        p=c.execute('SELECT * FROM principals WHERE id=%s',(parent['owner_id'],)).fetchone()
        if not p or not p['active']: raise Denied('current Approval owner required')
        self._scope(c,p,parent); store.check_capability(c,p,'READ'); prep.grant(store,c,p,'PREPARE')
        if check['auth_only']:
            _,items=_ledger(parent)
            for item in items.values():
                for h in item['proposal']['binding']['members']: rh._scope(c,p,UUID(h['resource_id']))
            return
        store.check_capability(c,p,'EXECUTE')
        _,items=_ledger(parent); item=items[check['approval_id']]
        data=Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
        actual,now=self._source(store,c,p,parent,data,consumed=check['consumed'])
        if actual != item['proposal']['binding']: raise Conflict('Approval source or authority changed before completion')

    def _view(self,store,c,p,parent,event=None,*,recovery=False):
        ledger,items=_ledger(parent); result=[]
        for item in items.values():
            e=item['proposal']; b=e['binding']; current=False; reason=item['state']
            for h in b['members']: rh._scope(c,p,UUID(h['resource_id']))
            if item['state']=='CONSUMED':
                r=c.execute('SELECT payload,fingerprint FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',
                    (p['id'],item['consumption']['key'])).fetchone()
                if not r or r['fingerprint']!=item['consumption']['receipt']['fingerprint']:
                    raise Conflict('Approval original consumption receipt required')
                verify_receipt(parent,r['payload'])
            if item['state'] in ('PROPOSED','APPROVED'):
                data=Proposal.model_validate({k:v for k,v in e['request'].items() if k!='action'}).delivery
                try:
                    actual,_=self._source(store,c,p,parent,data)
                    if actual != b: reason='SOURCE_OR_AUTHORITY_CHANGED'
                    else:
                        current=True; reason='CURRENT'
                        self._guard(c,parent,item['id'])
                except Denied: reason='CURRENT_AUTHORITY_REQUIRED'
                except Conflict: reason='SOURCE_OR_PREREQUISITE_CHANGED_OR_EXPIRED'
            result.append(dict(id=item['id'],state=item['state'],current=current,current_available=current and item['state']=='APPROVED',reason=reason,
                purpose=PURPOSE,plan_id=b['context']['plan_id'],plan_sha256=b['context']['plan_definition_sha256'],
                binding_sha256=cp._hash(b),authority_sha256=b['authority_sha256'],execution_identity=b['execution_identity'],
                service_id=b['context']['service_id'],service_version=b['context']['service_version'],catalog_sha256=b['context']['catalog_sha256'],
                materials=b['materials'],valid_until=b['valid_until'],members=[{k:h[k] for k in ('id','resource_id','resource_revision','starts_at','ends_at','quantity')} for h in b['members']],
                proposal_event_id=e['id'],approval_event_id=item['approval']['id'] if item['approval'] else None,
                consumption_event_id=item['consumption']['id'] if item['consumption'] else None))
            result[-1]['delivery']=body(Proposal.model_validate({k:v for k,v in e['request'].items() if k!='action'}).delivery) if current else None
            result[-1]['context']=b['context'] if current else None
        proof={k:event[k] for k in ('id','revision','approval_id','action','actor_id')} if event else None
        if proof: proof['request_key']=event['key']
        return dict(scope=SCOPE,purpose=PURPOSE,enabled=True,production_execution_enabled=False,formal_release=False,
            actor_id=p['id'],preparation_id=parent['id'],case_id=parent['case_id'],run_id=parent['run_id'],
            revision=ledger['revision'],items=result,event=proof,status='COMMITTED' if event else 'NOT_OBSERVED' if recovery else 'READ_ONLY',
            automatically_replayed=False,historical_only=recovery,server_time=rh._now(c))

    def read(self,store,token,id,key=None):
        with store.connect() as c:
            p,parent=cr._parent(store,c,token,id); self._scope(c,p,parent)
            if key is not None: self._key(c,p,parent,key)
            ledger,_=_ledger(parent)
            event=next((e for e in ledger['events'] if e['key']==key),None) if key else None
            self._guard(c,parent,event['approval_id'] if event else UUID(int=0),auth_only=True)
            return self._view(store,c,p,parent,event,recovery=key is not None)

    def propose(self,store,token,id,key,data):
        request=dict(action='PROPOSE',**body(data))
        with store.connect() as c:
            p,parent=cr._parent(store,c,token,id,write=True); self._scope(c,p,parent)
            self._key(c,p,parent,key)
            event=self._replay(parent,key,request)
            if event: return self._view(store,c,p,parent,event)
            ledger,items=_ledger(parent)
            if ledger['revision'] != data.expected_revision or len(items)>=OBJECT_LIMIT:
                raise Conflict('Approval revision or bounded object limit changed')
            snapshot,_=self._source(store,c,p,parent,data.delivery)
            parent,event=self._append(c,p,parent,key,request,uuid4(),binding=snapshot)
            self._guard(c,parent,event['approval_id'])
            return self._view(store,c,p,parent,event)

    def command(self,store,token,id,key,data):
        request=body(data)
        with store.connect() as c:
            p,parent=cr._parent(store,c,token,id,write=True); self._scope(c,p,parent)
            self._key(c,p,parent,key)
            event=self._replay(parent,key,request)
            if event: return self._view(store,c,p,parent,event)
            ledger,items=_ledger(parent); item=items.get(str(data.approval_id))
            if (ledger['revision'] != data.expected_revision or item is None
                or cp._hash(item['proposal']['binding']) != data.expected_binding_sha256
                or item['state'] not in ('PROPOSED','APPROVED')):
                raise Conflict('Approval current object or revision changed')
            if data.action=='APPROVE':
                if item['state']!='PROPOSED': raise Conflict('Approval already decided')
                original=Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
                snapshot,_=self._source(store,c,p,parent,original)
                if snapshot!=item['proposal']['binding']: raise Conflict('Approval original source or authority changed')
            parent,event=self._append(c,p,parent,key,request,data.approval_id)
            self._guard(c,parent,data.approval_id,auth_only=data.action=='REVOKE')
            return self._view(store,c,p,parent,event)

    def before_delivery(self,store,c,p,parent,key,data,fp):
        self._scope(c,p,parent); self._key(c,p,parent,key)
        if self._replay(parent,key,dict(action='CONSUME',delivery=body(data))):
            raise Conflict('Approval consumption requires its original delivery receipt')
        _,items=_ledger(parent)
        item=items.get(str(data.approval_id))
        if item is None or item['state']!='APPROVED': raise Conflict('current exact plan Approval required')
        original=Proposal.model_validate({k:v for k,v in item['proposal']['request'].items() if k!='action'}).delivery
        if {k:v for k,v in body(data).items() if k!='approval_id'} != body(original):
            raise Conflict('Approval exact delivery command changed')
        snapshot,_=self._source(store,c,p,parent,original)
        if snapshot!=item['proposal']['binding']: raise Conflict('Approval source or authority changed')
        return dict(scope=SCOPE,id=item['id'],approval_event_id=item['approval']['id'],
            consumption_event_id=str(uuid4()),binding_sha256=cp._hash(snapshot))

    def consume(self,store,c,p,parent,key,data,fp,proof,receipt):
        parent,event=self._append(c,p,parent,key,dict(action='CONSUME',delivery=body(data)),data.approval_id,
            receipt=dict(combination_id=receipt['combination_id'],request_key=key,fingerprint=fp,receipt_sha256=cp._hash(receipt)),
            event_id=UUID(proof['consumption_event_id']))
        self._guard(c,parent,data.approval_id,consumed=receipt['combination_id'])
        return parent


def verify_receipt(parent,receipt,expected=None):
    proof=receipt.get('plan_approval')
    if proof is None:
        if expected is not None: raise Conflict('original plan Approval receipt reference required')
        if parent.get(COL) is not None or parent.get('candidate_plan_approval_head') is not None:
            _,items=_ledger(parent)
            if any(i['consumption'] and i['consumption']['receipt']['combination_id']==receipt.get('combination_id') for i in items.values()):
                raise Conflict('original plan Approval receipt reference missing')
        return
    if expected is not None and proof!=expected: raise Conflict('original plan Approval link reference mismatch')
    _,items=_ledger(parent)
    try:
        item=items[proof['id']]; event=item['consumption']; approval=item['approval']
        if (set(proof)!={'scope','id','approval_event_id','consumption_event_id','binding_sha256'}
            or proof['scope']!=SCOPE or item['state']!='CONSUMED' or not event or not approval
            or proof['approval_event_id']!=approval['id'] or proof['consumption_event_id']!=event['id']
            or proof['binding_sha256']!=cp._hash(item['proposal']['binding'])
            or event['receipt']['combination_id']!=receipt['combination_id']
            or event['receipt']['receipt_sha256']!=cp._hash(receipt)
            or event['receipt']['request_key']!=receipt['delivery_binding']['request_key']
            or event['receipt']['fingerprint']!=receipt['delivery_binding']['fingerprint']): raise ValueError()
    except (KeyError,TypeError,ValueError): raise Conflict('original plan Approval consumption proof mismatch')
