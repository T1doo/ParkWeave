"""Bounded synthetic delivery feedback, projected only from append-only events."""
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from . import preparation as prep
from .store import Conflict, Denied, digest
from .executor_receipts import bounded

ACTION='MATERIAL_OBJECTION'
SCOPE='SYNTHETIC_MATERIAL_DELIVERY_OBJECTION'

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['RAISE','RESPOND','ACCEPT_RESPONSE','KEEP_OPEN','REBIND']
    expected_preparation_revision: int=Field(ge=1,le=63)
    expected_version: int=Field(ge=0,le=32)
    binding_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    objection_id: UUID|None=Field(default=None,strict=False)
    response_id: UUID|None=Field(default=None,strict=False)
    reason: str=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def shape(self):
        if self.action=='RAISE':
            if self.objection_id is not None or self.expected_version!=0:raise ValueError('new objection only')
        elif self.objection_id is None or self.expected_version==0:raise ValueError('existing objection version required')
        if (self.action in ('ACCEPT_RESPONSE','KEEP_OPEN'))!=(self.response_id is not None):raise ValueError('explicit current response only')
        return self

def binding(store,c,row):
    items=prep.latest(c,row['id'])
    intent=row.get('request_intent')
    base=dict(preparation_id=str(row['id']),case_id=str(row['case_id']),run_id=str(row['run_id']),
              owner_id=row['owner_id'],reviewer_id=row['reviewer_id'],service_id=row['service_id'],service_version=row['service_version'],
              request_revision=intent['revision'] if intent else 0,
              request_sha256=digest(prep.canonical(intent if intent else {'original_goal':row['goal']})),
              materials=[dict(slot=i['slot'],evidence_id=str(i['id']),version=i['version'],source_sha256=i['source_sha256']) for i in items])
    catalog=c.execute('SELECT source FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
                      (row['park_id'],row['service_id'],row['service_version'])).fetchone()
    review=c.execute("SELECT id,revision FROM preparation_events WHERE preparation_id=%s AND action='REVIEW' ORDER BY revision DESC LIMIT 1",(row['id'],)).fetchone()
    base['review_event_id']=str(review['id']) if review else None
    base['review_revision']=review['revision'] if review else 0
    store.lock_principal(c,row['reviewer_id'])
    reviewer=c.execute("SELECT 1 FROM principals p JOIN preparation_grants g ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id JOIN capability_grants cg ON cg.principal_id=p.id AND cg.park_id=p.park_id AND cg.org_id=p.org_id WHERE p.id=%s AND p.active AND p.role='park_specialist' AND p.park_id=%s AND p.org_id=%s AND g.capability='REVIEW_ASSIGNED' AND g.active AND cg.capability='READ' AND cg.active",(row['reviewer_id'],row['park_id'],row['org_id'])).fetchone()
    # Current capability revisions prevent a restored READ/EXECUTE generation
    # from silently reviving a previous response. No credentials enter binding.
    store.lock_principal(c,row['owner_id'])
    grants=c.execute("SELECT principal_id,capability,active,revision FROM capability_grants WHERE principal_id=ANY(%s) AND park_id=%s AND org_id=%s AND capability IN ('READ','EXECUTE') ORDER BY principal_id,capability",([row['owner_id'],row['reviewer_id']],row['park_id'],row['org_id'])).fetchall()
    preparation_grants=c.execute('SELECT principal_id,capability,active FROM preparation_grants WHERE principal_id=ANY(%s) AND park_id=%s AND org_id=%s ORDER BY principal_id,capability',([row['owner_id'],row['reviewer_id']],row['park_id'],row['org_id'])).fetchall()
    base['authority_sha256']=digest(prep.canonical({'capabilities':grants,'preparation':preparation_grants}))
    base['original_goal_sha256']=digest(row['goal'])
    base['catalog_sha256']=digest(prep.canonical(catalog['source'])) if catalog else None
    facts=prep.fact_descriptor(store,c,row)
    base['fact_source_sha256']=facts.get('descriptor_sha256') if facts else None
    sha=digest(prep.canonical(base))
    current=bool({i['slot'] for i in items}==set(prep.SLOTS) and
                 all(digest(i['text'])==i['source_sha256'] for i in items) and
                 row['state'] in ('REVIEWED','LOCAL_CONFIRMED') and row['review_sha256']==prep.snapshot(row,items) and
                 catalog and reviewer and (facts is None or facts.get('satisfied') is True))
    return {**base,'preparation_revision':row['revision'],'sha256':sha},current

def records(c,id):
    return c.execute('SELECT id,payload,created_at FROM preparation_events WHERE preparation_id=%s AND action=%s ORDER BY revision',(id,ACTION)).fetchall()

def project(store,c,row):
    current,review_valid=binding(store,c,row)
    tickets={};events=records(c,row['id'])
    for record in events:
        entry=record['payload']['objection'];id=entry['id'];action=entry['action']
        if action=='RAISE':tickets[id]=dict(id=id,history=[],response_id=None)
        ticket=tickets[id];ticket['history'].append({**entry,'created_at':record['created_at']})
        ticket.update(version=entry['version'],state=entry['state'],binding=entry['binding'])
        if action=='RESPOND':ticket['response_id']=entry['event_id']
        elif action in ('RAISE','REBIND','KEEP_OPEN'):ticket['response_id']=None
    for ticket in tickets.values():
        same=ticket['binding']['sha256']==current['sha256'] and review_valid
        ticket['source_current']=same
        ticket['state']=ticket['state'] if same else 'STALE'
    return current,review_valid,list(tickets.values()),events

def unresolved(store,c,row):
    # Fast legacy path avoids new source locks on unrelated Cases.
    if not records(c,row['id']):return False
    return any(t['state']!='RESOLVED' for t in project(store,c,row)[2])

def gate(store,c,row):
    if unresolved(store,c,row):raise Conflict('material delivery objection requires explicit current owner review')

def view(store,c,p,row):
    current,valid,tickets,events=project(store,c,row)
    return dict(scope=SCOPE,role=p['role'],preparation_id=str(row['id']),case_id=str(row['case_id']),
                preparation_revision=row['revision'],binding=current,current_review_valid=valid,
                items=tickets,unresolved=any(t['state']!='RESOLVED' for t in tickets),
                can_raise=p['role']=='enterprise_operator' and valid and len(tickets)<8 and len(events)+3<=32 and row['revision']+3<=64,
                history_limit=32,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',
                offline_fulfillment='NO_EVIDENCE',case_goal_completed=False)

def auth(store,c,token,id,write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    p=store.auth(c,token,lock=True)
    if p['role'] not in ('enterprise_operator','park_specialist'):raise Denied('original owner or assigned reviewer required')
    row=prep.scoped(store,c,p,id,write=write)
    if row['namespace']!='SYNTHETIC':raise Denied('synthetic delivery required')
    schema=c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
    if schema<26:raise Conflict('isolated synthetic objection storage is not installed')
    return p,row

@bounded
def read(store,token,id):
    with store.connect() as c:
        p,row=auth(store,c,token,id)
        return view(store,c,p,row)

@bounded
def recover(store,token,id,key):
    with store.connect() as c:
        p=store.auth(c,token,lock=True);prep.key_lock(c,p,key)
        p,row=auth(store,c,token,id)
        record=c.execute('SELECT preparation_id,action,payload FROM preparation_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if record and (record['preparation_id']!=id or record['action']!=ACTION):raise Conflict('original objection recovery scope mismatch')
        return dict(preparation_id=str(id),case_id=str(row['case_id']),status='COMMITTED' if record else 'NOT_OBSERVED',
                    event=record['payload'] if record else None,historical_only=True,automatically_replayed=False)

@bounded
def command(store,token,id,key,data):
    fp=digest(prep.canonical({'preparation_id':str(id),'type':ACTION,**data.model_dump(mode='json')}))
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p=store.auth(c,token,lock=True);prep.key_lock(c,p,key)
        p,row=auth(store,c,token,id,write=True)
        owner=data.action!='RESPOND'
        if p['role']!=('enterprise_operator' if owner else 'park_specialist'):raise Denied('original actor role required')
        old=prep.replay(c,p,key,fp,id)
        if old:return old
        if row['revision']!=data.expected_preparation_revision or row['revision']>=64:raise Conflict('current preparation revision required')
        current,valid,tickets,events=project(store,c,row)
        remaining=1 if data.action=='ACCEPT_RESPONSE' else 2 if data.action=='RESPOND' else 3
        if len(events)+remaining>32 or row['revision']+remaining>64:raise Conflict('objection history capacity required for explicit review')
        if not valid or current['sha256']!=data.binding_sha256:raise Conflict('current reviewed material binding required')
        ticket=next((t for t in tickets if t['id']==str(data.objection_id)),None)
        if data.action=='RAISE':
            if len(tickets)>=8:raise Conflict('objection limit reached')
            id=str(uuid4());version=1;state='OPEN';bound=current
        else:
            if not ticket or ticket['version']!=data.expected_version:raise Conflict('current objection version required')
            if ticket['binding']['reviewer_id']!=row['reviewer_id'] or ticket['binding']['owner_id']!=row['owner_id']:raise Denied('original delivery actors required')
            id=ticket['id'];version=ticket['version']+1;bound=ticket['binding']
            if data.action=='REBIND':
                if ticket['state']!='STALE':raise Conflict('explicit changed source rebind required')
                bound=current;state='OPEN'
            else:
                if not ticket['source_current'] or ticket['state']=='RESOLVED':raise Conflict('current unresolved objection required')
                if data.action=='RESPOND':
                    if ticket['state']!='OPEN':raise Conflict('owner review required before another response')
                    state='AWAITING_OWNER_REVIEW'
                else:
                    if ticket['state']!='AWAITING_OWNER_REVIEW' or ticket['response_id']!=str(data.response_id):raise Conflict('exact current specialist response required')
                    state='RESOLVED' if data.action=='ACCEPT_RESPONSE' else 'OPEN'
        event_id=uuid4()
        entry=dict(id=id,version=version,action=data.action,state=state,binding=bound,event_id=str(event_id),
                   actor_id=p['id'],reason=data.reason,response_id=str(data.response_id) if data.response_id else None)
        updated=c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s RETURNING *',(row['id'],)).fetchone()
        from .controlled_plans import invalidate
        invalidate(c,row['id'],1)
        return prep.event(c,p,updated,key,fp,ACTION,event_id=event_id,objection=entry)
