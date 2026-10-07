"""Assigned executor's local synthetic receipt, never physical fulfillment."""
from functools import wraps
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.errors import LockNotAvailable
from psycopg.types.json import Jsonb
from .store import Conflict,Denied,digest
from . import preparation as prep

SCOPE='SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY'

def bounded(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        from .controlled_plans import OBSERVATIONS,PlanBlocked,persist_rejected_observation
        context=OBSERVATIONS.set([])
        try:return fn(*args,**kwargs)
        except (Conflict,Denied,LockNotAvailable) as exc:
            observations=OBSERVATIONS.get()
            if isinstance(exc,PlanBlocked):observations.append(exc)
            seen=set()
            for observation in observations:
                stamp=(observation.plan_id,observation.revision,observation.index)
                if stamp in seen:continue
                seen.add(stamp)
                try:persist_rejected_observation(args[0],observation)
                except LockNotAvailable as busy:
                    raise Conflict('controlled plan observation busy; retry same key and explicitly recheck prerequisites') from busy
            if isinstance(exc,LockNotAvailable):raise Conflict('receipt authorization or record busy; retry same key') from exc
            raise
        finally:OBSERVATIONS.reset(context)
    return call
class Create(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    preparation_id: UUID=Field(strict=False)
    expected_preparation_revision: int=Field(ge=1)
    executor_id: str=Field(min_length=1,max_length=100)

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN']
    expected_revision: int=Field(ge=1)
    text: str|None=Field(default=None,min_length=1,max_length=4000)
    source_kind: Literal['SYNTHETIC']|None=None
    source_label: str|None=Field(default=None,min_length=1,max_length=200)
    receipt_sha256: str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    reason: str|None=Field(default=None,min_length=1,max_length=1000)
    @model_validator(mode='after')
    def shape(self):
        if self.action=='SUBMIT':
            if any(x is None for x in (self.text,self.source_kind,self.source_label)) or self.reason is not None or self.receipt_sha256 is not None:raise ValueError('complete synthetic receipt only')
        elif not self.reason or self.text is not None or self.source_kind is not None or self.source_label is not None or not self.receipt_sha256:
            raise ValueError('current receipt hash and explicit decision reason required')
        return self

def _auth(store,c,token):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True)
    if p['role'] not in ('enterprise_operator','service_executor'):raise Denied('receipt role required')
    store.check_capability(c,p,'READ')
    return p

def _key(c,p,key):c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('executor-receipt-key:'+p['id']+':'+key,))

def _executor(store,c,id,run):
    store.lock_principal(c,id)
    p=c.execute('SELECT * FROM principals WHERE id=%s AND active',(id,)).fetchone()
    if not p or p['role']!='service_executor':raise Denied('current assigned executor required')
    store.scoped_run(c,p,run)
    return p

def _base(store,c,p,id):
    row=c.execute('SELECT * FROM service_receipt_steps WHERE id=%s AND park_id=%s AND org_id=%s',(id,p['park_id'],p['org_id'])).fetchone()
    if not row or p['id']!=row['owner_id' if p['role']=='enterprise_operator' else 'executor_id']:raise Denied('receipt step unavailable')
    store.scoped_run(c,p,row['run_id'])
    return row

def _parent(c,row):
    return c.execute('SELECT * FROM preparations WHERE id=%s FOR SHARE',(row['preparation_id'],)).fetchone()

def current_step(c,parent):
    """The current accepted offer selects its receipt generation; history never does."""
    root=c.execute('SELECT current_offer_id FROM service_dispatches WHERE preparation_id=%s',(parent['id'],)).fetchone()
    if root:
        selected=c.execute("""SELECT s.* FROM service_dispatch_offers o JOIN service_receipt_steps s
          ON s.id=o.receipt_step_id AND s.executor_id=o.executor_id
          AND s.preparation_revision=o.preparation_revision AND s.preparation_sha256=o.preparation_sha256
          WHERE o.id=%s AND o.state='ACCEPTED' AND s.preparation_id=%s""",(root['current_offer_id'],parent['id'])).fetchone()
    else:
        rows=c.execute('SELECT * FROM service_receipt_steps WHERE preparation_id=%s LIMIT 2',(parent['id'],)).fetchall()
        selected=rows[0] if len(rows)==1 else None
    fields=('run_id','case_id','owner_id','park_id','org_id','service_id','service_version')
    return selected if selected and all(selected[k]==parent[k] for k in fields) else None

def material_current(c,parent):
    if not parent or parent['state']!='LOCAL_CONFIRMED':return False
    items=prep.latest(c,parent['id'])
    return ({i['slot'] for i in items}==set(prep.SLOTS) and
            all(digest(i['text'])==i['source_sha256'] for i in items) and
            prep.snapshot(parent,items)==parent['review_sha256'])

def _fresh(row,parent,c=None):
    return bool(parent and parent['state']=='LOCAL_CONFIRMED' and parent['revision']==row['preparation_revision'] and parent['review_sha256']==row['preparation_sha256'] and (c is None or material_current(c,parent)))

def _locked(c,id,write=False):
    return c.execute('SELECT * FROM service_receipt_steps WHERE id=%s '+('FOR UPDATE' if write else 'FOR SHARE'),(id,)).fetchone()

def _current(c,row):
    return c.execute('SELECT * FROM service_step_receipts WHERE step_id=%s AND id=%s',(row['id'],row['current_receipt_id'])).fetchone() if row['current_receipt_id'] else None

def _replay(c,p,key,fp):
    e=c.execute('SELECT fingerprint,payload FROM service_receipt_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
    if e:
        if e['fingerprint']!=fp:raise Conflict('receipt request key fingerprint mismatch')
        return e['payload']

def _event(c,p,row,key,fp,action,**extra):
    payload={'step_id':str(row['id']),'revision':row['revision'],'state':row['state'],'action':action,'actor_id':p['id'],'scope':SCOPE,**extra}
    c.execute('INSERT INTO service_receipt_events(id,step_id,actor_id,request_key,fingerprint,revision,action,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(uuid4(),row['id'],p['id'],key,fp,row['revision'],action,Jsonb(payload)))
    return payload

def _view(c,p,row,parent,event=None):
    current=current_step(c,parent) if parent else None
    is_current=bool(current and current['id']==row['id'])
    return dict(scope=SCOPE,role=p['role'],step=row,current_receipt=_current(c,row),
        history=c.execute('SELECT revision,action,payload,created_at FROM service_receipt_events WHERE step_id=%s ORDER BY revision',(row['id'],)).fetchall(),
        receipt_history=c.execute('SELECT * FROM service_step_receipts WHERE step_id=%s ORDER BY version',(row['id'],)).fetchall(),
        dependency='CURRENT' if is_current and _fresh(row,parent,c) else 'DEPENDENCY_CHANGED',event=event,
        is_current_step=is_current,record_mode='CURRENT_GENERATION' if is_current else 'HISTORICAL_GENERATION',
        replay_mode=('CURRENT_COMMITTED_EVENT' if is_current else 'HISTORICAL_COMMITTED_EVENT') if event else None,
        qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)

@bounded
def catalog(store,token,id):
    with store.connect() as c:
        p=_auth(store,c,token)
        if p['role']!='enterprise_operator':raise Denied('enterprise owner required')
        row=prep.scoped(store,c,p,id);store.check_capability(c,p,'EXECUTE')
        rows=c.execute("""SELECT e.id FROM principals e JOIN run_assignments a ON a.principal_id=e.id
          AND a.park_id=e.park_id AND a.org_id=e.org_id JOIN capability_grants g ON g.principal_id=e.id
          AND g.park_id=e.park_id AND g.org_id=e.org_id AND g.capability='READ' AND g.active
          WHERE a.run_id=%s AND a.active AND e.active AND e.role='service_executor'
          AND e.park_id=%s AND e.org_id=%s ORDER BY e.id LIMIT 100""",(row['run_id'],p['park_id'],p['org_id'])).fetchall()
        return dict(scope=SCOPE,preparation_revision=row['revision'],ready=row['state']=='LOCAL_CONFIRMED',executors=rows)

def _insert_step(c,parent,executor_id):
    return c.execute("""INSERT INTO service_receipt_steps(id,preparation_id,run_id,case_id,owner_id,executor_id,park_id,org_id,service_id,service_version,
          preparation_revision,preparation_sha256,goal,state,revision,namespace)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'AWAITING_RECEIPT',1,'SYNTHETIC') RETURNING *""",(uuid4(),parent['id'],parent['run_id'],parent['case_id'],parent['owner_id'],executor_id,parent['park_id'],parent['org_id'],parent['service_id'],parent['service_version'],parent['revision'],parent['review_sha256'],parent['goal'])).fetchone()

@bounded
def create(store,token,key,data):
    fp=digest(prep.canonical({'action':'CREATE',**data.model_dump(mode='json')}))
    with store.connect() as c:
        p=_auth(store,c,token)
        if p['role']!='enterprise_operator':raise Denied('enterprise owner required')
        store.check_capability(c,p,'EXECUTE');_key(c,p,key)
        parent=prep.scoped(store,c,p,data.preparation_id,write=True)
        _executor(store,c,data.executor_id,parent['run_id'])
        old=_replay(c,p,key,fp)
        if old:
            row=_base(store,c,p,UUID(old['step_id']));row=_locked(c,row['id'])
            return _view(c,p,row,parent,old)
        from .controlled_plans import gate
        gate(store,c,parent,3)
        if parent['revision']!=data.expected_preparation_revision or not material_current(c,parent):raise Conflict('current locally confirmed preparation required')
        if c.execute('SELECT 1 FROM service_receipt_steps WHERE preparation_id=%s',(parent['id'],)).fetchone():raise Conflict('preparation already has receipt step')
        if c.execute('SELECT 1 FROM service_dispatches WHERE preparation_id=%s',(parent['id'],)).fetchone():raise Conflict('internal dispatch requires executor acceptance')
        row=_insert_step(c,parent,data.executor_id)
        return _view(c,p,row,parent,_event(c,p,row,key,fp,'CREATE'))

@bounded
def read(store,token,id):
    with store.connect() as c:
        p=_auth(store,c,token);row=_base(store,c,p,id);parent=_parent(c,row);row=_locked(c,id)
        return _view(c,p,row,parent)

@bounded
def command(store,token,id,key,data):
    fp=digest(prep.canonical({'step_id':str(id),**data.model_dump(mode='json')}))
    with store.connect() as c:
        p=_auth(store,c,token)
        if data.action=='SUBMIT':
            if p['role']!='service_executor':raise Denied('assigned executor receipt only')
        else:
            if p['role']!='enterprise_operator':raise Denied('enterprise owner decision only')
            store.check_capability(c,p,'EXECUTE')
        _key(c,p,key);row=_base(store,c,p,id)
        if p['role']=='enterprise_operator':_executor(store,c,row['executor_id'],row['run_id'])
        parent=_parent(c,row);row=_locked(c,id,write=True);old=_replay(c,p,key,fp)
        if old:return _view(c,p,row,parent,old)
        selected=current_step(c,parent)
        if not selected or selected['id']!=row['id']:raise Conflict('historical receipt generation is read-only; current executor acceptance required')
        from .controlled_plans import gate
        if data.action in ('SUBMIT','ACKNOWLEDGE'):
            full_parent=c.execute('SELECT * FROM preparations WHERE id=%s',(row['preparation_id'],)).fetchone()
            gate(store,c,full_parent,3)
        if not _fresh(row,parent,c):raise Conflict('receipt preparation dependency changed; explicit replanning required')
        if row['revision']!=data.expected_revision:raise Conflict('stale receipt step revision; refresh required')
        if row['revision']>=64:raise Conflict('receipt history limit reached')
        current=_current(c,row);current_id=row['current_receipt_id']
        if data.action=='SUBMIT':
            if row['state'] not in ('AWAITING_RECEIPT','CHANGES_REQUESTED'):raise Conflict('receipt step not awaiting executor')
            version=(current['version'] if current else 0)+1;sha=digest(data.text)
            receipt=c.execute("INSERT INTO service_step_receipts(id,step_id,version,text,source_kind,source_label,source_sha256,actor_id) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,%s) RETURNING *",(uuid4(),id,version,data.text,data.source_label,sha,p['id'])).fetchone()
            current_id=receipt['id'];state='RECEIPT_RECORDED'
        else:
            if not current or data.receipt_sha256!=current['source_sha256']:raise Conflict('current receipt hash required')
            if data.action=='ACKNOWLEDGE':
                if row['state']!='RECEIPT_RECORDED':raise Conflict('recorded receipt required for local acknowledgement')
                state='LOCAL_ACKNOWLEDGED'
            elif data.action=='REQUEST_CHANGES':
                if row['state']!='RECEIPT_RECORDED':raise Conflict('recorded receipt required for correction')
                state='CHANGES_REQUESTED'
            else:
                if row['state'] not in ('RECEIPT_RECORDED','LOCAL_ACKNOWLEDGED'):raise Conflict('recorded receipt required for reopen')
                state='AWAITING_RECEIPT'
        row=c.execute('UPDATE service_receipt_steps SET state=%s,revision=revision+1,current_receipt_id=%s WHERE id=%s RETURNING *',(state,current_id,id)).fetchone()
        from .controlled_plans import invalidate
        invalidate(c,row['preparation_id'],4)
        e=_event(c,p,row,key,fp,data.action,receipt_id=str(current_id),receipt_sha256=_current(c,row)['source_sha256'],reason=data.reason)
        return _view(c,p,row,parent,e)

@bounded
def list_steps(store,token):
    with store.connect() as c:
        p=_auth(store,c,token);owner=p['role']=='enterprise_operator'
        rows=c.execute("""SELECT s.id,s.goal,s.state,s.revision FROM service_receipt_steps s
          WHERE s.park_id=%s AND s.org_id=%s AND s."""+('owner_id' if owner else 'executor_id')+"""=%s
          AND (SELECT principal_id FROM runs WHERE id=s.run_id) = s.owner_id
          """+('' if owner else "AND EXISTS(SELECT 1 FROM run_assignments a WHERE a.run_id=s.run_id AND a.principal_id=%s AND a.park_id=s.park_id AND a.org_id=s.org_id AND a.active)")+" ORDER BY s.created_at DESC,s.id DESC LIMIT 101",(p['park_id'],p['org_id'],p['id'],*(() if owner else (p['id'],)))).fetchall()
        return dict(items=rows[:100],has_older_records=len(rows)>100,role=p['role'],scope=SCOPE)
