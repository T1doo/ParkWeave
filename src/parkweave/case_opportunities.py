"""Owner-imported synthetic Case opportunities; no qualification or execution."""
from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from . import preparation as prep, executor_receipts as er
from .store import Conflict, Denied, digest

SCOPE='SYNTHETIC_CASE_OPPORTUNITY_ONLY'
MAX_EVENTS=128

class Entry(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    family_id: UUID=Field(strict=False)
    generation: int=Field(ge=1,le=64)
    kind: Literal['LOCAL_SERVICE_VERSION','LOCAL_CASE_DATA']
    catalog_version: int=Field(ge=1,le=100000)
    title: str=Field(min_length=1,max_length=200)
    note: str=Field(min_length=1,max_length=1000)

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['IMPORT','REFRESH','IGNORE','WITHDRAW']
    expected_revision: int=Field(ge=0,le=MAX_EVENTS)
    expected_source_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    reason: str=Field(min_length=1,max_length=1000)
    entry: Entry|None=None
    card_id: UUID|None=Field(default=None,strict=False)
    expected_card_version: int|None=Field(default=None,ge=1,le=MAX_EVENTS)
    @model_validator(mode='after')
    def shape(self):
        if self.action=='IMPORT':
            if self.entry is None or self.card_id is not None or self.expected_card_version is not None:raise ValueError('import entry only')
        elif self.action=='REFRESH':
            if any(v is not None for v in (self.entry,self.card_id,self.expected_card_version)):raise ValueError('refresh current sources only')
        elif self.entry is not None or self.card_id is None or self.expected_card_version is None:raise ValueError('exact card version required')
        return self

def normal(x):
    if isinstance(x,(UUID,datetime)):return x.isoformat() if isinstance(x,datetime) else str(x)
    if isinstance(x,dict):return {k:normal(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [normal(v) for v in x]
    return x

def sha(x):return digest(prep.canonical(normal(x)))

def binding(row):
    return normal({k:row[k] for k in ('id','case_id','run_id','owner_id','park_id','org_id','service_id','namespace')})

def valid_basis(basis,scope):
    if (not isinstance(basis,dict) or set(basis)!={'binding','preparation_revision','preparation_service_version','materials','catalog'} or
        basis['binding']!=scope or type(basis['preparation_revision']) is not int or basis['preparation_revision']<1 or
        type(basis['preparation_service_version']) is not int or basis['preparation_service_version']<1 or
        not isinstance(basis['materials'],list) or len(basis['materials'])>2 or not isinstance(basis['catalog'],list) or len(basis['catalog'])>32):raise ValueError()
    slots=set();versions=set()
    for m in basis['materials']:
        if set(m)!={'slot','id','version','source_sha256'} or m['slot'] not in prep.SLOTS or m['slot'] in slots or type(m['version']) is not int or m['version']<1 or not re.fullmatch('[a-f0-9]{64}',m['source_sha256']):raise ValueError()
        UUID(m['id']);slots.add(m['slot'])
    for r in basis['catalog']:
        if (set(r)!={'service_id','version','name','source_sha256'} or r['service_id']!=scope['service_id'] or type(r['version']) is not int or r['version']<1 or r['version'] in versions or
            not isinstance(r['name'],str) or not 1<=len(r['name'])<=200 or not re.fullmatch('[a-f0-9]{64}',r['source_sha256'])):raise ValueError()
        versions.add(r['version'])

def auth(store,c,token,id,write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True)
    if p['role']!='enterprise_operator':raise Denied('original Case owner required')
    row=prep.scoped(store,c,p,id,write=write)
    if row['namespace']!='SYNTHETIC' or row['service_id']!=prep.SERVICE:raise Denied('existing synthetic preparation Case required')
    case=c.execute('SELECT id FROM cases WHERE id=%s AND run_id=%s AND park_id=%s AND org_id=%s AND source=%s',(row['case_id'],row['run_id'],p['park_id'],p['org_id'],'SYNTHETIC')).fetchone()
    if not case:raise Denied('bound synthetic Case required')
    if 'opportunities' not in row:raise Conflict('synthetic opportunity fixture increment not enabled')
    return p,row

def ledger(row):
    value=row['opportunities']
    if value is None:return dict(version=1,scope=SCOPE,binding=binding(row),revision=0,events=[])
    try:
        if (type(value['version']) is not int or value['version']!=1 or value['scope']!=SCOPE or value['binding']!=binding(row) or
            type(value['revision']) is not int or not 0<=value['revision']<=MAX_EVENTS or
            not isinstance(value['events'],list) or len(value['events'])!=value['revision']):raise ValueError()
        previous=None;keys=set();ids=set()
        for index,e in enumerate(value['events'],1):
            if (not isinstance(e,dict) or type(e['revision']) is not int or e['revision']!=index or e['actor_id']!=row['owner_id'] or
                e['previous_sha256']!=previous or e['scope']!=SCOPE or e['action'] not in ('IMPORT','REFRESH','IGNORE','WITHDRAW') or
                e['request_key'] in keys or e['sha256']!=sha({k:v for k,v in e.items() if k!='sha256'})):
                raise ValueError()
            if not re.fullmatch('[a-f0-9]{64}',e['fingerprint']) or not re.fullmatch('[A-Za-z0-9_-]{1,100}',e['request_key']):raise ValueError()
            if (e['id'] in ids or not isinstance(e['reason'],str) or not 1<=len(e['reason'])<=1000 or
                e['outcome'] not in {'IMPORT':('IMPORTED','DUPLICATE'),'REFRESH':('REFRESHED','NO_CHANGE'),'IGNORE':('IGNORE',),'WITHDRAW':('WITHDRAW',)}[e['action']]):raise ValueError()
            UUID(e['id']);ids.add(e['id']);keys.add(e['request_key']);previous=e['sha256']
        project(value)
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('opportunity history proof invalid')
    return deepcopy(value)

def project(value):
    cards={};heads={}
    for e in value['events']:
        payload=e['payload'];action=e['action']
        if action=='IMPORT' and e['outcome']=='IMPORTED':
            card=deepcopy(payload['card']);entry=Entry.model_validate(card['entry']);id=card['id'];UUID(id)
            valid_basis(card['basis'],value['binding'])
            if (id in cards or card['version']!=1 or card['state']!='PENDING_REVIEW' or
                card['entry_sha256']!=sha(card['entry']) or card['basis_sha256']!=sha(card['basis'])):raise ValueError()
            family=str(entry.family_id)
            if family in heads and (entry.generation<=heads[family][0] or cards[heads[family][1]]['entry']['kind']!=entry.kind):raise ValueError()
            cards[id]=card;heads[family]=(entry.generation,id)
        elif action=='REFRESH':
            if not isinstance(payload['changes'],list) or len(payload['changes'])>8 or len({x['id'] for x in payload['changes']})!=len(payload['changes']):raise ValueError()
            for change in payload['changes']:
                card=cards[change['id']]
                valid_basis(change['basis'],value['binding'])
                if card['state']!='PENDING_REVIEW' or heads[card['entry']['family_id']][1]!=card['id'] or change['version']!=card['version']+1 or change['basis_sha256']!=sha(change['basis']):raise ValueError()
                card.update(deepcopy(change))
        elif action in ('IGNORE','WITHDRAW'):
            card=cards[payload['card_id']]
            if card['state']=='WITHDRAWN' or payload['version']!=card['version']+1:raise ValueError()
            if action=='IGNORE' and card['state']!='PENDING_REVIEW':raise ValueError()
            card['version']=payload['version'];card['state']='IGNORED' if action=='IGNORE' else 'WITHDRAWN'
        elif e['outcome']=='DUPLICATE':
            if payload['card_id'] not in cards:raise ValueError()
        else:raise ValueError()
    if len(heads)>8 or len(cards)>16:raise ValueError()
    return cards,heads

def sources(c,row):
    # Read actual scoped catalog and material references, never imported policy
    # expressions, fact values or semantic matching supplied by the client.
    catalog=c.execute('SELECT service_id,version,name,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s ORDER BY version LIMIT 33',(row['park_id'],row['service_id'])).fetchall()
    if len(catalog)>32:raise Conflict('bounded synthetic catalog exceeded')
    catalog=[dict(service_id=r['service_id'],version=r['version'],name=r['name'],source_sha256=sha(r['source'])) for r in catalog
             if r['namespace']=='SYNTHETIC' and r['qualification']=='NOT_EVALUATED' and isinstance(r['source'],dict) and r['source'].get('kind')=='SYNTHETIC']
    if len(catalog)>32:raise Conflict('bounded synthetic catalog exceeded')
    materials=[{k:normal(i[k]) for k in ('slot','id','version','source_sha256')} for i in prep.latest(c,row['id'])]
    basis=dict(binding=binding(row),preparation_revision=row['revision'],preparation_service_version=row['service_version'],materials=materials,catalog=catalog)
    try:valid_basis(basis,binding(row))
    except (ValueError,KeyError,TypeError):raise Conflict('bounded synthetic source proof unavailable')
    return basis,sha(basis)

def view(store,c,p,row,value=None):
    value=ledger(row) if value is None else value;cards,heads=project(value);basis,source_sha=sources(c,row)
    result=[]
    for card in cards.values():
        x=deepcopy(card);entry=x['entry'];x['is_latest_generation']=heads[entry['family_id']][1]==x['id']
        x['current_catalog_available']=any(r['version']==entry['catalog_version'] for r in basis['catalog'])
        x['source_binding_current']=x['basis_sha256']==source_sha and x['current_catalog_available']
        x['requires_human_review']=x['state']=='PENDING_REVIEW';x['qualification_decision']='NOT_EVALUATED';result.append(x)
    try:store.check_capability(c,p,'EXECUTE');can_write=value['revision']<MAX_EVENTS
    except Denied:can_write=False
    return dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(row['id']),case_id=str(row['case_id']),run_id=str(row['run_id']),
        revision=value['revision'],source_sha256=source_sha,current_basis=basis,cards=result,history=value['events'],can_write=can_write,
        source_kind='USER_IMPORTED_SYNTHETIC',qualification_decision='NOT_EVALUATED',business_publication=False,case_goal_completed=False,external_notifications=0)

@er.bounded
def read(store,token,id):
    with store.connect() as c:
        p,row=auth(store,c,token,id);return view(store,c,p,row)

def original(c,p,id,key):
    matches=c.execute("SELECT id,opportunities FROM preparations WHERE owner_id=%s AND opportunities->'events' @> %s",(p['id'],Jsonb([{'actor_id':p['id'],'request_key':key}]))).fetchall()
    if not matches:return None
    if len(matches)!=1 or matches[0]['id']!=id:raise Conflict('original opportunity request Case mismatch')
    events=[e for e in matches[0]['opportunities']['events'] if e.get('actor_id')==p['id'] and e.get('request_key')==key]
    if len(events)!=1:raise Conflict('original opportunity key proof invalid')
    return events[0]

@er.bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p,row=auth(store,c,token,id);c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('opportunity-key:'+p['id']+':'+key,))
        old=original(c,p,id,key);value=ledger(row)
        boundary=dict(scope=SCOPE,actor_id=p['id'],preparation_id=str(id),case_id=str(row['case_id']),historical_only=True,automatically_replayed=False)
        if old is None:return dict(**boundary,status='NOT_OBSERVED')
        matches=[e for e in value['events'] if e['id']==old['id']]
        if len(matches)!=1 or matches[0]!=old:raise Conflict('original opportunity history changed')
        return dict(**boundary,status='COMMITTED',receipt=deepcopy(old),current=view(store,c,p,row,value))

@er.bounded
def command(store,token,id,key,data):
    fp=sha(dict(preparation_id=str(id),**data.model_dump(mode='json')))
    with store.connect() as c:
        p,row=auth(store,c,token,id,write=True);c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('opportunity-key:'+p['id']+':'+key,))
        value=ledger(row);old=original(c,p,id,key)
        if old:
            if old['fingerprint']!=fp:raise Conflict('opportunity request fingerprint mismatch')
            return dict(receipt=old,current=view(store,c,p,row,value),historical_only=True)
        basis,current_sha=sources(c,row)
        if value['revision']!=data.expected_revision or current_sha!=data.expected_source_sha256:raise Conflict('opportunity revision or source changed; refresh required')
        if value['revision']>=MAX_EVENTS:raise Conflict('bounded opportunity history exhausted')
        cards,heads=project(value);payload={};outcome=data.action
        if data.action=='IMPORT':
            entry=data.entry.model_dump(mode='json');family=entry['family_id'];generation=entry['generation']
            if not any(r['version']==entry['catalog_version'] for r in basis['catalog']):raise Conflict('existing synthetic catalog version required')
            existing=next((x for x in cards.values() if x['entry']['family_id']==family and x['entry']['generation']==generation),None)
            if existing:
                if existing['entry_sha256']!=sha(entry):raise Conflict('same opportunity source generation changed content')
                payload=dict(card_id=existing['id']);outcome='DUPLICATE'
            else:
                if family in heads and generation<=heads[family][0]:raise Conflict('older opportunity generation cannot replace latest')
                if family in heads and cards[heads[family][1]]['entry']['kind']!=entry['kind']:raise Conflict('opportunity source family kind cannot change')
                if len(cards)>=16 or family not in heads and len(heads)>=8:raise Conflict('bounded opportunity cards or families exhausted')
                card=dict(id=str(uuid4()),entry=entry,entry_sha256=sha(entry),basis=basis,basis_sha256=current_sha,version=1,state='PENDING_REVIEW')
                payload=dict(card=card);outcome='IMPORTED'
        elif data.action=='REFRESH':
            changes=[dict(id=x['id'],version=x['version']+1,basis=basis,basis_sha256=current_sha) for x in cards.values()
                if x['state']=='PENDING_REVIEW' and heads[x['entry']['family_id']][1]==x['id'] and x['basis_sha256']!=current_sha]
            payload=dict(changes=changes);outcome='REFRESHED' if changes else 'NO_CHANGE'
        else:
            card=cards.get(str(data.card_id))
            if not card or card['version']!=data.expected_card_version:raise Conflict('exact opportunity card version required')
            if card['state']=='WITHDRAWN' or data.action=='IGNORE' and card['state']!='PENDING_REVIEW':raise Conflict('opportunity already suppressed')
            payload=dict(card_id=card['id'],version=card['version']+1)
        e=dict(id=str(uuid4()),scope=SCOPE,revision=value['revision']+1,actor_id=p['id'],request_key=key,fingerprint=fp,
            action=data.action,outcome=outcome,reason=data.reason,created_at=c.execute('SELECT clock_timestamp() now').fetchone()['now'].isoformat(),
            previous_sha256=value['events'][-1]['sha256'] if value['events'] else None,payload=payload)
        e['sha256']=sha(e);value['events'].append(e);value['revision']+=1
        updated=c.execute("UPDATE preparations SET opportunities=%s WHERE id=%s AND COALESCE((opportunities->>'revision')::int,0)=%s RETURNING *",(Jsonb(value),id,data.expected_revision)).fetchone()
        if not updated:raise Conflict('opportunity CAS changed')
        # The original actor lock prevents supported revocations; timed global
        # capability rows are rechecked after every possible ledger lock wait.
        prep.grant(store,c,p,'PREPARE');store.check_capability(c,p,'EXECUTE')
        return dict(receipt=e,current=view(store,c,p,updated,value),historical_only=False)
