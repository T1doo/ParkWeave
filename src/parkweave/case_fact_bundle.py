"""Actual synthetic Case document excerpts and explicit assumptions/field locks.

All values stay in the owner's private bundle; existing business gates consume
only the current purpose descriptor. No model, truth verification or new grant.
"""
from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID,uuid4
import re
from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.types.json import Jsonb
from . import preparation as prep,executor_receipts as er
from .domain import Validity
from .store import Conflict,Denied,digest

SCOPE='SYNTHETIC_CASE_FACT_BUNDLE_ONLY'
FIELDS=('region','employees','service_need')
MAX_EVENTS=32
ACTIONS=('REGISTER_DOCUMENT','REGISTER_ASSUMPTION','WITHDRAW','LOCK','UNLOCK')
class Period(Validity):
    timezone: Literal['UTC']='UTC'
class Source(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid')
    field: Literal['region','employees','service_need']
    value: str|int
    unit: Literal['text','people']
    validity: Period
    material_id: UUID|None=Field(default=None,strict=False)
    material_version: int|None=Field(default=None,ge=1)
    material_sha256: str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    start: int|None=Field(default=None,ge=0,le=3999)
    end: int|None=Field(default=None,ge=1,le=4000)
    note: str|None=Field(default=None,min_length=1,max_length=1000)
    @model_validator(mode='after')
    def typed_value(self):
        if self.field=='employees':
            if type(self.value) is not int or not 0<=self.value<=2147483647 or self.unit!='people':raise ValueError('bounded integer people required')
        elif type(self.value) is not str or not self.value.strip() or len(self.value)>2000 or self.unit!='text':raise ValueError('bounded text required')
        return self
class Command(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',str_strip_whitespace=True)
    action: Literal['REGISTER_DOCUMENT','REGISTER_ASSUMPTION','WITHDRAW','LOCK','UNLOCK']
    expected_preparation_revision: int=Field(ge=1,le=63)
    expected_bundle_revision: int=Field(ge=0,le=MAX_EVENTS)
    expected_source_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    reason: str=Field(min_length=1,max_length=1000)
    source: Source|None=None
    source_id: UUID|None=Field(default=None,strict=False)
    field: Literal['region','employees','service_need']|None=None
    assertion_id: UUID|None=Field(default=None,strict=False)
    assertion_revision: int|None=Field(default=None,ge=1)
    assertion_fingerprint: str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    @model_validator(mode='after')
    def shape(self):
        lock=(self.assertion_id,self.assertion_revision,self.assertion_fingerprint)
        if self.action.startswith('REGISTER_'):
            if self.source is None or self.source_id is not None or self.field is not None or any(x is not None for x in lock):raise ValueError('source only')
            refs=(self.source.material_id,self.source.material_version,self.source.material_sha256,self.source.start,self.source.end)
            if self.action=='REGISTER_DOCUMENT':
                if any(x is None for x in refs) or self.source.end<=self.source.start or self.source.note is not None:raise ValueError('exact document span only')
            elif any(x is not None for x in refs) or not self.source.note:raise ValueError('explicit assumption without document refs required')
        elif self.action=='WITHDRAW':
            if self.source_id is None or self.source is not None or self.field is not None or any(x is not None for x in lock):raise ValueError('exact source only')
        elif self.field is None or self.source is not None or self.source_id is not None:raise ValueError('field lock only')
        elif self.action=='LOCK' and any(x is None for x in lock):raise ValueError('exact selected assertion required')
        elif self.action=='UNLOCK' and any(x is not None for x in lock):raise ValueError('field unlock only')
        return self

def normal(x):
    if isinstance(x,(UUID,datetime)):return str(x) if isinstance(x,UUID) else x.isoformat()
    if isinstance(x,dict):return {k:normal(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [normal(v) for v in x]
    return x

def sha(x):return digest(prep.canonical(normal(x)))
def binding(parent):return normal({k:parent[k] for k in ('id','case_id','run_id','owner_id','park_id','org_id','service_id','namespace')})
def scope(store,c,token,id,write=False,key=None):
    from . import case_fact_clarifications as facts
    c.execute("SET LOCAL lock_timeout='3s'");p=store.auth(c,token,lock=True)
    if key is not None:prep.key_lock(c,p,key)
    parent=prep.scoped(store,c,p,id,write=write);facts._field_locks(c,p['id']);facts._scope(store,c,p,parent,require_write=write)
    if 'fact_bundle' not in parent:raise Conflict('Case fact bundle fixture increment not enabled')
    if facts._stored_ledger(c,parent) is None:raise Conflict('explicit Case fact purpose declaration required')
    return p,parent

def ledger(c,parent):
    value=parent.get('fact_bundle')
    if value is None:
        if c.execute("SELECT 1 FROM preparation_events WHERE preparation_id=%s AND action='FACT_BUNDLE_COMMAND' LIMIT 1",(parent['id'],)).fetchone():raise Conflict('Case fact source bundle cannot be removed')
        return dict(version=1,scope=SCOPE,binding=binding(parent),purpose='SERVICE_PREPARATION',share_scope='OWNER_CASE_USE_ONLY',revision=0,events=[])
    try:
        if (type(value['version']) is not int or value['version']!=1 or value['scope']!=SCOPE or value['binding']!=binding(parent) or value['purpose']!='SERVICE_PREPARATION' or value['share_scope']!='OWNER_CASE_USE_ONLY' or
            type(value['revision']) is not int or not 0<=value['revision']<=MAX_EVENTS or len(value['events'])!=value['revision']):raise ValueError()
        previous=None;keys=set();ids=set();last_parent=0
        for i,e in enumerate(value['events'],1):
            if (type(e['revision']) is not int or e['revision']!=i or e['scope']!=SCOPE or e['actor_id']!=parent['owner_id'] or e['action'] not in ACTIONS or e['binding']!=binding(parent) or
                e['previous_sha256']!=previous or e['sha256']!=sha({k:v for k,v in e.items() if k!='sha256'}) or e['request_key'] in keys or e['id'] in ids or
                type(e['preparation_revision']) is not int or not last_parent<e['preparation_revision']<=64 or e['source_basis']['binding']!=binding(parent) or e['source_basis']['preparation_revision']!=e['preparation_revision']-1 or e['source_sha256']!=sha(e['source_basis']) or type(e['source_basis']['request_revision']) is not int or not 0<=e['source_basis']['request_revision']<e['preparation_revision'] or not re.fullmatch('[a-f0-9]{64}',e['source_basis']['request_sha256']) or not isinstance(e['reason'],str) or not 1<=len(e['reason'])<=1000 or
                not re.fullmatch('[a-f0-9]{64}',e['fingerprint']) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',e['request_key'])):raise ValueError()
            UUID(e['id']);keys.add(e['request_key']);ids.add(e['id']);previous=e['sha256'];last_parent=e['preparation_revision']
        project(value)
    except (KeyError,ValueError,TypeError,AttributeError):raise Conflict('Case fact bundle history proof invalid')
    return deepcopy(value)

def project(value):
    entries={};locks={}
    for e in value['events']:
        a=e['action'];payload=e['payload']
        if a.startswith('REGISTER_'):
            entry=deepcopy(payload['entry']);UUID(entry['id']);s=Source.model_validate(entry['source'])
            if entry['id'] in entries or entry['actor_id']!=e['actor_id'] or entry['kind']!=('DOCUMENT_EXTRACT_SYNTHETIC' if a=='REGISTER_DOCUMENT' else 'ASSUMPTION_SYNTHETIC') or entry['fingerprint']!=sha({k:v for k,v in entry.items() if k!='fingerprint'}):raise ValueError()
            # Reuse request-shape validation for reconstructed entries, without
            # accepting fields a client could use to relabel an assumption.
            Command(action=a,expected_preparation_revision=1,expected_bundle_revision=0,expected_source_sha256='0'*64,reason='proof',source=s)
            if a=='REGISTER_DOCUMENT':
                b=entry['material'];UUID(b['id'])
                if b['slot'] not in prep.SLOTS or b['id']!=str(s.material_id) or b['version']!=s.material_version or b['source_sha256']!=s.material_sha256 or b['source_kind']!='DOCUMENT_EXCERPT' or not isinstance(b['excerpt'],str) or len(b['excerpt'])!=s.end-s.start:raise ValueError()
                exact_value(s,b['excerpt'])
            elif entry['material'] is not None:raise ValueError()
            entries[entry['id']]=dict(**entry,active=True)
        elif a=='WITHDRAW':
            x=entries[payload['source_id']]
            if not x['active'] or any(z['assertion_id']==x['id'] for z in locks.values()):raise ValueError()
            x['active']=False
        elif a=='LOCK':
            lock=payload['lock'];UUID(lock['assertion_id'])
            if lock['field'] not in FIELDS or lock['field'] in locks or type(lock['assertion_revision']) is not int or lock['assertion_revision']<1 or not re.fullmatch('[a-f0-9]{64}',lock['assertion_fingerprint']) or lock['source_sha256']!=sha(lock['source']):raise ValueError()
            row=lock['source']
            if row['id']!=lock['assertion_id'] or row['field_name']!=lock['field'] or row['revision']!=lock['assertion_revision'] or row['fingerprint']!=lock['assertion_fingerprint']:raise ValueError()
            locks[lock['field']]=deepcopy(lock)
        elif a=='UNLOCK':
            if payload['field'] not in locks:raise ValueError()
            del locks[payload['field']]
    if len(entries)>12:raise ValueError()
    return entries,locks

def exact_value(s,excerpt):
    if s.field=='employees':
        if not re.fullmatch('0|[1-9][0-9]{0,9}',excerpt) or int(excerpt)!=s.value:raise Conflict('value must equal actual document integer excerpt')
    elif s.value!=excerpt:raise Conflict('value must equal actual document text excerpt')

def material_current(entry,items):
    s=entry['source'];b=entry['material']
    row=next((m for m in items if str(m['id'])==b['id']),None)
    return bool(row and row['slot']==b['slot'] and row['version']==b['version'] and row['source_kind']=='DOCUMENT_EXCERPT' and row['source_sha256']==b['source_sha256']==digest(row['text']) and row['text'][s['start']:s['end']]==b['excerpt'])

def source_state(c,parent):
    """Private current candidates for original Case source selection, never globals."""
    value=ledger(c,parent);entries,locks=project(value);items=prep.latest(c,parent['id']);rows=[];applicable={}
    now=c.execute('SELECT clock_timestamp() now').fetchone()['now']
    for e in entries.values():
        if e['kind']!='DOCUMENT_EXTRACT_SYNTHETIC':continue
        s=e['source'];rows.append(dict(id=e['id'],evidence_id=e['material']['id'],field_name=s['field'],value=s['value'],unit=s['unit'],source_ref=dict(id=e['material']['id'],kind='SYNTHETIC',revision=str(e['material']['version'])),source_kind=e['kind'],source_excerpt=e['material']['excerpt'],valid_from=s['validity']['valid_from'],valid_until=s['validity']['valid_until'],revision=1,fingerprint=e['fingerprint'],confirmed_by=e['actor_id']))
        applicable[e['id']]=bool(e['active'] and material_current(e,items) and datetime.fromisoformat(s['validity']['valid_from'])<=now<datetime.fromisoformat(s['validity']['valid_until']))
    descriptor=dict(revision=value['revision'],sha256=sha(value)) if value['revision'] else None
    return rows,applicable,descriptor

def enforce_locks(c,parent,choices,rows):
    _,locks=project(ledger(c,parent));by_id={x['id']:x for x in rows}
    for choice in choices:
        lock=locks.get(choice['field'])
        if lock:
            row=by_id.get(choice['assertion_id'])
            if not row or (choice['assertion_id'],choice['expected_assertion_revision'],choice['expected_assertion_fingerprint'],sha(row))!=(lock['assertion_id'],lock['assertion_revision'],lock['assertion_fingerprint'],lock['source_sha256']):raise Conflict('LOCK_CONFLICT: explicitly unlock the original field first')

def basis(store,c,parent,p):
    from . import case_fact_clarifications as facts
    snapshot,source_sha,applicable=facts._sources(store,c,parent,p)
    materials=[normal({k:x[k] for k in ('id','slot','version','source_kind','source_sha256')}) for x in prep.latest(c,parent['id'])]
    x=dict(binding=binding(parent),purpose='SERVICE_PREPARATION',share_scope='OWNER_CASE_USE_ONLY',preparation_revision=parent['revision'],request_revision=(parent.get('request_intent') or {}).get('revision',0),request_sha256=sha(dict(original_request=parent['goal'],request_intent=parent.get('request_intent'))),fact_source_sha256=source_sha,materials=materials)
    return x,sha(x),snapshot,applicable

def view(store,c,p,parent,value=None):
    from . import case_fact_clarifications as facts
    value=ledger(c,parent) if value is None else value;entries,locks=project(value);b,hash,snapshot,applicable=basis(store,c,parent,p)
    docs,doc_applicable,_=source_state(c,parent)
    for x in entries.values():
        x['eligible_for_case_selection']=doc_applicable.get(x['id'],False);x['verification']='UNVERIFIED';x['state']='WITHDRAWN' if not x['active'] else 'CURRENT_EXCERPT' if x['eligible_for_case_selection'] else 'UNKNOWN'
    status=facts.public_status(facts.gate(store,c,parent))
    choices=facts._stored_ledger(c,parent)['events'][-1]['choices'] if status['state']=='CURRENT' else []
    try:facts._scope(store,c,p,parent);can_write=parent['revision']<64 and value['revision']<MAX_EVENTS
    except Denied:can_write=False
    return dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),preparation_revision=parent['revision'],revision=value['revision'],source_sha256=hash,current_basis=b,source_classes=['USER_ASSERTED_SYNTHETIC','DOCUMENT_EXTRACT_SYNTHETIC','ASSUMPTION_SYNTHETIC'],purpose='SERVICE_PREPARATION',share_scope='OWNER_CASE_USE_ONLY',entries=list(entries.values()),locks=locks,asserted_sources=[x for x in snapshot['sources'] if x['source_kind']=='USER_ASSERTED_SYNTHETIC'],documents=normal([x for x in prep.latest(c,parent['id']) if x['source_kind']=='DOCUMENT_EXCERPT']),selected_sources=choices,selectable_sources=snapshot['sources'],history=value['events'],fact_status=status,can_write=can_write,qualification_decision='NOT_EVALUATED',business_publication=False,case_goal_completed=False)

@er.bounded
def read(store,token,id):
    with store.connect() as c:p,parent=scope(store,c,token,id);return view(store,c,p,parent)

def original(c,p,parent,key):
    old=c.execute('SELECT * FROM preparation_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
    if old and (old['preparation_id']!=parent['id'] or old['action']!='FACT_BUNDLE_COMMAND'):raise Conflict('original fact bundle Case or action mismatch')
    if not old:return None
    value=ledger(c,parent);matches=[e for e in value['events'] if e['request_key']==key]
    if len(matches)!=1 or matches[0]['fingerprint']!=old['fingerprint'] or old['payload'].get('bundle_receipt_sha256')!=matches[0]['sha256']:raise Conflict('original fact bundle event proof mismatch')
    return matches[0]

@er.bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p,parent=scope(store,c,token,id,key=key);old=original(c,p,parent,key);out=dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(id),case_id=str(parent['case_id']),historical_only=True,automatically_replayed=False)
        if old is None:return dict(**out,status='NOT_OBSERVED')
        return dict(**out,status='COMMITTED',receipt=deepcopy(old),current=view(store,c,p,parent))

@er.bounded
def command(store,token,id,key,data):
    from . import case_fact_clarifications as facts
    fp=sha(dict(preparation_id=str(id),**data.model_dump(mode='json')))
    with store.connect() as c:
        p,parent=scope(store,c,token,id,True,key);value=ledger(c,parent);old=original(c,p,parent,key)
        if old:
            if old['fingerprint']!=fp:raise Conflict('fact bundle idempotency fingerprint mismatch')
            return dict(receipt=old,current=view(store,c,p,parent),historical_only=True)
        b,current_sha,snapshot,applicable=basis(store,c,parent,p)
        if parent['revision']!=data.expected_preparation_revision or value['revision']!=data.expected_bundle_revision or current_sha!=data.expected_source_sha256:raise Conflict('Case fact bundle revision or source changed')
        if parent['revision']>=64 or value['revision']>=MAX_EVENTS:raise Conflict('bounded Case fact history exhausted')
        entries,locks=project(value);payload={}
        if data.action.startswith('REGISTER_'):
            if len(entries)>=12:raise Conflict('bounded Case source limit12 reached')
            s=data.source;material=None
            if data.action=='REGISTER_DOCUMENT':
                row=next((m for m in prep.latest(c,parent['id']) if m['id']==s.material_id),None)
                if not row or row['version']!=s.material_version or row['source_kind']!='DOCUMENT_EXCERPT' or row['source_sha256']!=s.material_sha256 or digest(row['text'])!=s.material_sha256 or s.end>len(row['text']):raise Conflict('actual current Case document source required')
                excerpt=row['text'][s.start:s.end];exact_value(s,excerpt)
                material=normal({k:row[k] for k in ('id','slot','version','source_kind','source_sha256')})|dict(excerpt=excerpt)
                if any(x['kind']=='DOCUMENT_EXTRACT_SYNTHETIC' and x['source']==s.model_dump(mode='json') for x in entries.values()):raise Conflict('same document source already registered')
            e=dict(id=str(uuid4()),actor_id=p['id'],kind='DOCUMENT_EXTRACT_SYNTHETIC' if material else 'ASSUMPTION_SYNTHETIC',source=s.model_dump(mode='json'),material=material);e['fingerprint']=sha(e);payload=dict(entry=e)
        elif data.action=='WITHDRAW':
            entry=entries.get(str(data.source_id))
            if not entry or not entry['active']:raise Conflict('active Case source required')
            if any(x['assertion_id']==entry['id'] for x in locks.values()):raise Conflict('LOCK_CONFLICT: explicitly unlock before source withdrawal')
            payload=dict(source_id=entry['id'])
        elif data.action=='LOCK':
            if data.field in locks:raise Conflict('field already explicitly locked')
            if facts.gate(store,c,parent)['state']!='CURRENT':raise Conflict('current explicit Case source selection required before lock')
            selected=next((x for x in facts._stored_ledger(c,parent)['events'][-1]['choices'] if x['field']==data.field),None)
            row=next((x for x in snapshot['sources'] if x['id']==str(data.assertion_id)),None)
            if not row or not selected or not applicable[row['id']] or (selected['assertion_id'],selected['expected_assertion_revision'],selected['expected_assertion_fingerprint'])!=(str(data.assertion_id),data.assertion_revision,data.assertion_fingerprint):raise Conflict('exact currently selected source required')
            payload=dict(lock=dict(field=data.field,assertion_id=str(data.assertion_id),assertion_revision=data.assertion_revision,assertion_fingerprint=data.assertion_fingerprint,source_sha256=sha(row),source=row))
        else:
            if data.field not in locks:raise Conflict('explicit existing lock required')
            payload=dict(field=data.field)
        event=dict(id=str(uuid4()),scope=SCOPE,binding=binding(parent),revision=value['revision']+1,preparation_revision=parent['revision']+1,actor_id=p['id'],request_key=key,fingerprint=fp,action=data.action,reason=data.reason,source_basis=b,source_sha256=current_sha,created_at=c.execute('SELECT clock_timestamp() now').fetchone()['now'].isoformat(),payload=payload,previous_sha256=value['events'][-1]['sha256'] if value['events'] else None);event['sha256']=sha(event);value['events'].append(event);value['revision']+=1
        updated=c.execute("UPDATE preparations SET fact_bundle=%s,revision=revision+1,state='IN_PREPARATION',review_sha256=NULL WHERE id=%s AND revision=%s RETURNING *",(Jsonb(value),id,data.expected_preparation_revision)).fetchone()
        if not updated:raise Conflict('Case fact bundle CAS changed')
        from .controlled_plans import invalidate
        invalidate(c,id,1);facts._scope(store,c,p,updated)
        if data.action=='LOCK':
            _,late_sha,late_applicable=facts._sources(store,c,parent,p)
            if late_sha!=b['fact_source_sha256'] or not late_applicable.get(str(data.assertion_id),False):raise Conflict('selected source expired or changed before lock commit')
        prep.event(c,p,updated,key,fp,'FACT_BUNDLE_COMMAND',bundle_revision=value['revision'],bundle_receipt_sha256=event['sha256'],bundle_action=data.action)
        return dict(receipt=event,current=view(store,c,p,updated,value),historical_only=False)
