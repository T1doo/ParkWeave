"""Local SYNTHETIC material preparation; manual review is not eligibility or fulfillment."""
import json
from typing import Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb
from .store import Denied, Conflict, digest

SLOTS=('need_summary','material_outline')
SERVICE='synthetic-material-preparation'

class CreatePreparation(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    run_id: UUID=Field(strict=False)
    service_id: Literal['synthetic-material-preparation']
    service_version: int=Field(ge=1)
    reviewer_id: str=Field(min_length=1,max_length=100)

class PreparationCommand(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['ADD_EVIDENCE','REQUEST_CHANGES','REVIEW','CONFIRM','REOPEN']
    expected_revision: int=Field(ge=1)
    slot: Literal['need_summary','material_outline']|None=None
    text: str|None=Field(default=None,min_length=1,max_length=4000)
    source_kind: Literal['USER_STATEMENT','DOCUMENT_EXCERPT']|None=None
    source_label: str|None=Field(default=None,min_length=1,max_length=200)
    reason: str|None=Field(default=None,min_length=1,max_length=1000)
    correction_slots: list[Literal['need_summary','material_outline']]|None=Field(default=None,min_length=1,max_length=2)
    @model_validator(mode='after')
    def shape(self):
        evidence=(self.slot,self.text,self.source_kind,self.source_label)
        if 'correction_slots' in self.model_fields_set and self.action!='REQUEST_CHANGES':raise ValueError('correction slots apply only to REQUEST_CHANGES')
        if self.correction_slots is not None and len(set(self.correction_slots))!=len(self.correction_slots):raise ValueError('distinct correction slots required')
        if self.action=='ADD_EVIDENCE':
            if any(x is None for x in evidence) or self.reason is not None:raise ValueError('complete evidence only')
        elif any(x is not None for x in evidence) or not self.reason:raise ValueError('explicit reason only')
        return self

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def grant(store,c,p,capability):
    required='enterprise_operator' if capability=='PREPARE' else 'park_specialist'
    if p['role']!=required:raise Denied('preparation role required')
    store.check_capability(c,p,'READ')
    if not c.execute('SELECT 1 FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability=%s AND active',(p['id'],p['park_id'],p['org_id'],capability)).fetchone():raise Denied('current preparation grant required')

def scoped(store,c,p,id,write=False):
    capability='PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED'
    grant(store,c,p,capability)
    if write and capability=='PREPARE':store.check_capability(c,p,'EXECUTE')
    q='SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s'
    q+=' FOR UPDATE' if write else ' FOR SHARE'
    row=c.execute(q,(id,p['park_id'],p['org_id'])).fetchone()
    if row is None or p['id']!=(row['owner_id'] if capability=='PREPARE' else row['reviewer_id']):raise Denied('assigned preparation scope required')
    return row

def catalog(store,token):
    with store.connect() as c:
        p=store.auth(c,token,lock=True);grant(store,c,p,'PREPARE')
        services=c.execute('SELECT service_id,version,name,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s ORDER BY service_id,version',(p['park_id'],)).fetchall()
        reviewers=c.execute("SELECT p.id FROM principals p JOIN preparation_grants g ON g.principal_id=p.id AND g.park_id=p.park_id AND g.org_id=p.org_id JOIN capability_grants cg ON cg.principal_id=p.id AND cg.park_id=p.park_id AND cg.org_id=p.org_id AND cg.capability='READ' AND cg.active WHERE p.park_id=%s AND p.org_id=%s AND p.role='park_specialist' AND p.active AND g.capability='REVIEW_ASSIGNED' AND g.active ORDER BY p.id",(p['park_id'],p['org_id'])).fetchall()
        return {'services':services,'reviewers':reviewers,'required_slots':list(SLOTS),'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY'}

def key_lock(c,p,key):c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('preparation-key:'+p['id']+':'+key,))

def replay(c,p,key,fingerprint,preparation_id=None):
    event=c.execute('SELECT * FROM preparation_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
    if event:
        if event['fingerprint']!=fingerprint or (preparation_id and event['preparation_id']!=preparation_id):raise Conflict('idempotency key fingerprint mismatch')
        return event['payload']

def event(c,p,row,key,fp,action,event_id=None,**extra):
    payload={'preparation_id':str(row['id']),'case_id':str(row['case_id']),'run_id':str(row['run_id']),
             'revision':row['revision'],'state':row['state'],'action':action,'actor_id':p['id'],
             'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY','qualification':'NOT_EVALUATED',
             'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE',**extra}
    c.execute('INSERT INTO preparation_events(id,preparation_id,actor_id,request_key,fingerprint,revision,action,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(event_id or uuid4(),row['id'],p['id'],key,fp,row['revision'],action,Jsonb(payload)))
    return payload

def recover_evidence_command(store,token,id,key):
    """Read an owner's exact original evidence event; a handle grants no access.

    No command replay/body retention or grants: current auth and preparation READ
    scope are required, and the event is selected by the authenticated actor.
    Absence is an observation, never proof that a delayed request cannot arrive.
    """
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p=store.auth(c,token,lock=True)
        if p['role']!='enterprise_operator':raise Denied('original enterprise owner required')
        key_lock(c,p,key)
        row=scoped(store,c,p,id)
        record=c.execute('SELECT preparation_id,action,payload FROM preparation_events WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if record and (record['preparation_id']!=id or record['action']!='ADD_EVIDENCE'):
            raise Conflict('original evidence recovery scope mismatch')
        return dict(preparation_id=str(id),status='COMMITTED' if record else 'NOT_OBSERVED',
                    event=record['payload'] if record else None,current_revision=row['revision'],
                    historical_only=True,automatically_replayed=False,
                    qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')

def create(store,token,key,data):
    fp=digest(canonical(data.model_dump(mode='json')))
    with store.connect() as c:
        p=store.auth(c,token,lock=True);grant(store,c,p,'PREPARE');store.check_capability(c,p,'EXECUTE')
        key_lock(c,p,key)
        run=store.scoped_run(c,p,data.run_id,lock=True)
        if run['principal_id']!=p['id'] or run['state']!='SUCCEEDED' or run['input'].get('action','case.create')!='case.create':raise Conflict('successful local case.create required')
        case=c.execute('SELECT * FROM cases WHERE run_id=%s',(run['id'],)).fetchone()
        if not case:raise Conflict('local Case required')
        if not c.execute('SELECT 1 FROM action_grants WHERE principal_id=%s AND action=%s AND park_id=%s AND org_id=%s AND active',(p['id'],'case.create',p['park_id'],p['org_id'])).fetchone():raise Denied('current case action grant required')
        previous=replay(c,p,key,fp)
        if previous:
            scoped(store,c,p,UUID(previous['preparation_id']))
            return previous
        if not c.execute('SELECT 1 FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',(p['park_id'],data.service_id,data.service_version)).fetchone():raise Conflict('explicit service version unavailable')
        # Serialize reviewer revocation against creation using the same identity lock.
        store.lock_principal(c,data.reviewer_id)
        reviewer=c.execute('SELECT * FROM principals WHERE id=%s AND active',(data.reviewer_id,)).fetchone()
        if not reviewer or (reviewer['park_id'],reviewer['org_id'])!=(p['park_id'],p['org_id']):raise Denied('reviewer scope required')
        grant(store,c,reviewer,'REVIEW_ASSIGNED')
        if c.execute('SELECT 1 FROM preparations WHERE run_id=%s',(run['id'],)).fetchone():raise Conflict('Case already has preparation')
        row=c.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'SYNTHETIC',%s,'IN_PREPARATION') RETURNING *",(uuid4(),run['id'],case['id'],p['id'],reviewer['id'],p['park_id'],p['org_id'],data.service_id,data.service_version,case['goal'])).fetchone()
        return event(c,p,row,key,fp,'CREATE')

def latest(c,id):
    return c.execute('SELECT DISTINCT ON(slot) id,slot,version,text,source_kind,source_label,source_sha256,authenticity FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version DESC',(id,)).fetchall()

def snapshot(row,items):
    data={'preparation_id':str(row['id']),'service_id':row['service_id'],'service_version':row['service_version'],
          'materials':[{k:(str(v) if isinstance(v,UUID) else v) for k,v in item.items()} for item in items]}
    return digest(canonical(data))

def fact_enabled(c,row):
    """A committed declaration cannot be downgraded by removing its ledger."""
    return row.get('fact_clarifications') is not None or bool(c.execute(
        "SELECT 1 FROM preparation_events WHERE preparation_id=%s AND action='DECLARE_FACT_PURPOSE' LIMIT 1",
        (row['id'],)).fetchone())

def fact_descriptor(store,c,row):
    if not fact_enabled(c,row):return None
    from .case_fact_clarifications import source_descriptor
    source=source_descriptor(store,c,row)
    from .material_preparation_drafts import source_status
    draft_status=source_status(c,row,source)
    if draft_status is not None:
        source['material_draft_sources']=draft_status
        if not draft_status['satisfied']:
            source.update(satisfied=False,state='STALE',issues=sorted(set(source['issues']+['CURRENT_GENERATED_MATERIAL_SOURCE_REQUIRED'])))
        source['descriptor_sha256']=digest(canonical({k:v for k,v in source.items() if k!='descriptor_sha256'}))
    # Private field values and source identities remain in the dedicated owner API.
    public=('enabled','state','satisfied','issues','revision','decision_ref','decision_sha256',
            'source_sha256','profile','purpose','required_fields','qualification','authenticity','descriptor_sha256','material_draft_sources')
    return {k:source[k] for k in public if k in source}

def fact_gate(store,c,row):
    if fact_enabled(c,row):
        if fact_descriptor(store,c,row).get('satisfied') is not True:
            raise Conflict('current fact purpose confirmation required')

def _insert_evidence(c,p,row,slot,text,source_kind,source_label):
    old=next((i for i in latest(c,row['id']) if i['slot']==slot),None)
    version=old['version']+1 if old else 1
    return c.execute("INSERT INTO preparation_evidence(id,preparation_id,slot,version,text,source_kind,source_label,source_sha256,actor_id,authenticity) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'UNVERIFIED') RETURNING *",(uuid4(),row['id'],slot,version,text,source_kind,source_label,digest(text),p['id'])).fetchone()

def command(store,token,id,key,data):
    # Keep fingerprints of commands created before slot correction support.
    body=data.model_dump(mode='json',exclude={'correction_slots'} if data.correction_slots is None else set())
    fp=digest(canonical({'preparation_id':str(id),**body}))
    with store.connect() as c:
        p=store.auth(c,token,lock=True);key_lock(c,p,key);row=scoped(store,c,p,id,write=True)
        if data.action in ('REQUEST_CHANGES','REVIEW'):
            if p['role']!='park_specialist':raise Denied('assigned reviewer required')
        elif p['role']!='enterprise_operator':raise Denied('enterprise owner required')
        previous=replay(c,p,key,fp,id)
        if previous:return previous
        if row['revision']!=data.expected_revision:raise Conflict('stale preparation revision; refresh required')
        if row['revision']>=64:raise Conflict('bounded preparation history limit reached')
        if data.action in ('REVIEW','CONFIRM'):fact_gate(store,c,row)
        items=latest(c,id);current_hash=snapshot(row,items);review_hash=None;review_source=None
        from . import material_corrections as corrections
        ledger=row.get('material_corrections')
        if data.action=='ADD_EVIDENCE':
            added=_insert_evidence(c,p,row,data.slot,data.text,data.source_kind,data.source_label)
            state='IN_PREPARATION';current_hash=snapshot(row,latest(c,id))
            if ledger:
                ledger=corrections.submit(row,p,added)
                material_by_slot={i['slot']:i for i in corrections.materials(c,id)}
                if any(not corrections.submitted(target,material_by_slot.get(target['slot']),row['owner_id']) for target in corrections.active(ledger)):state='CHANGES_REQUESTED'
        elif data.action=='REQUEST_CHANGES':
            if row['state'] not in ('IN_PREPARATION','CHANGES_REQUESTED'):raise Conflict('reopen reviewed preparation before correction')
            state='CHANGES_REQUESTED'
            if data.correction_slots is not None:ledger=corrections.request(row,p,data.correction_slots,data.reason,corrections.materials(c,id))
        elif data.action=='REVIEW':
            if row['state'] not in ('IN_PREPARATION','CHANGES_REQUESTED'):raise Conflict('preparation already reviewed')
            if {i['slot'] for i in items}!=set(SLOTS):raise Conflict('required material slots missing')
            if ledger:ledger=corrections.resolve(row,p,corrections.materials(c,id),current_hash,data.reason)
            from .material_objections import review_source as delivery_review_source
            review_source=delivery_review_source(store,c,row)
            state='REVIEWED';review_hash=current_hash
        elif data.action=='CONFIRM':
            from .material_objections import gate
            gate(store,c,row)
            if corrections.active(ledger):raise Conflict('requested material corrections require actual reviewer resolution before confirmation')
            if row['state']!='REVIEWED' or row['review_sha256']!=current_hash:raise Conflict('current manual material review required')
            state='LOCAL_CONFIRMED';review_hash=current_hash
        else:
            if row['state'] not in ('REVIEWED','LOCAL_CONFIRMED'):raise Conflict('reviewed preparation required for reopen')
            state='IN_PREPARATION'
        updated=c.execute('UPDATE preparations SET state=%s,revision=revision+1,review_sha256=%s,material_corrections=%s WHERE id=%s RETURNING *',(state,review_hash,Jsonb(ledger) if ledger is not None else None,id)).fetchone()
        from .controlled_plans import invalidate
        invalidate(c,id,1)
        extra={'delivery_review_source':review_source} if review_source is not None else {}
        return event(c,p,updated,key,fp,data.action,snapshot_sha256=current_hash,reason=data.reason,**extra)

def read(store,token,id):
    with store.connect() as c:
        p=store.auth(c,token,lock=True);row=scoped(store,c,p,id)
        row.pop('readiness_assessments',None)
        # Dedicated endpoints apply role-specific projections to these private ledgers.
        row.pop('planning_previews',None)
        row.pop('service_case_plan',None)
        row.pop('material_corrections',None)
        facts=fact_descriptor(store,c,row)
        row.pop('fact_clarifications',None)
        items=latest(c,id)
        history=c.execute('SELECT revision,action,payload,created_at FROM preparation_events WHERE preparation_id=%s ORDER BY revision',(id,)).fetchall()
        for record in history:
            record['payload'].pop('objection',None)
            if record['action'] in ('DECLARE_FACT_PURPOSE','CONFIRM_FACT_PURPOSE'):
                public=('preparation_id','case_id','run_id','revision','state','action','actor_id','scope',
                        'qualification','external_acceptance','offline_fulfillment','reason','fact_clarification_id',
                        'clarification_revision','source_sha256','selection_sha256','profile','purpose','status',
                        'decision_ref','decision_sha256','required_fields')
                record['payload']={k:record['payload'][k] for k in public if k in record['payload']}
        if p['role']!='enterprise_operator':
            row.pop('request_intent',None)
            for record in history:
                record['payload'].pop('request_intent',None)
                reuse=record['payload'].get('material_reuse')
                if reuse:
                    record['payload']['material_reuse']={k:reuse[k] for k in ('target_evidence_id','target_version','target_sha256','purpose','requires_independent_review','snapshot_mode')}
        result={'preparation':row,'current_materials':items,'snapshot_sha256':snapshot(row,items),
                'material_history':c.execute('SELECT slot,version,text,source_kind,source_label,source_sha256,authenticity,created_at FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version',(id,)).fetchall(),
                'history':history,
                'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY','qualification':'NOT_EVALUATED',
                'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}
        from .material_preparation_drafts import decorate_materials
        decorate_materials(c,row,items,history,facts)
        if facts is not None:result['fact_clarification']=facts
        return result

def list_items(store,token):
    with store.connect() as c:
        p=store.auth(c,token,lock=True)
        capability='PREPARE' if p['role']=='enterprise_operator' else 'REVIEW_ASSIGNED';grant(store,c,p,capability)
        column='owner_id' if capability=='PREPARE' else 'reviewer_id'
        rows=c.execute(f'SELECT id,case_id,goal,state,revision FROM preparations WHERE {column}=%s AND park_id=%s AND org_id=%s ORDER BY created_at DESC LIMIT 100',(p['id'],p['park_id'],p['org_id'])).fetchall()
        return {'items':rows,'role':p['role'],'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY'}

def personal_tasks(store,token):
    """Read-only current work, not notices, eligibility, or a write authorization."""
    with store.connect() as c:
        p=store.auth(c,token,lock=True)
        owner=p['role']=='enterprise_operator'
        grant(store,c,p,'PREPARE' if owner else 'REVIEW_ASSIGNED')
        column='owner_id' if owner else 'reviewer_id'
        # One statement snapshot covers state, material presence and correction.
        # Fetch one extra scoped row to report truncation, never claim completeness.
        rows=c.execute(f"""SELECT p.id,p.case_id,p.goal,p.state,p.revision,
            p.service_id,p.service_version,
            ARRAY(SELECT DISTINCT e.slot FROM preparation_evidence e
                  WHERE e.preparation_id=p.id) AS present_slots,
            (SELECT e.payload->>'reason' FROM preparation_events e
             WHERE e.preparation_id=p.id AND e.action='REQUEST_CHANGES'
             ORDER BY e.revision DESC LIMIT 1) AS correction_reason
            FROM preparations p WHERE p.{column}=%s AND p.park_id=%s AND p.org_id=%s
            AND p.state<>'LOCAL_CONFIRMED' ORDER BY p.created_at DESC,p.id DESC LIMIT 101
            """,(p['id'],p['park_id'],p['org_id'])).fetchall()
        tasks=[]
        for row in rows[:100]:
            missing=[slot for slot in SLOTS if slot not in row['present_slots']]
            kind=None
            if owner:
                if row['state']=='CHANGES_REQUESTED':kind='RESPOND_TO_CORRECTION'
                elif row['state']=='IN_PREPARATION' and missing:kind='SUPPLY_MATERIALS'
                elif row['state']=='REVIEWED':kind='CONFIRM_PREPARATION'
            elif row['state']=='IN_PREPARATION' and not missing:kind='REVIEW_MATERIALS'
            if kind:
                tasks.append({key:row[key] for key in ('id','case_id','goal','state','revision','service_id','service_version')})
                tasks[-1].update(kind=kind,missing_slots=missing,
                    correction_reason=row['correction_reason'] if row['state']=='CHANGES_REQUESTED' else None,
                    blocked_reason='HISTORY_LIMIT_REACHED' if row['revision']>=64 else None)
        return {'items':tasks,'role':p['role'],'checked_count':min(len(rows),100),
                'check_limit':100,'has_older_records':len(rows)>100,
                'scope':'SYNTHETIC_LOCAL_PREPARATION_ONLY','qualification':'NOT_EVALUATED',
                'external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}

def seed_synthetic(owner,tokens):
    """Explicit fixture owner setup; never production identity/automatic Grant repair."""
    with owner.connect() as c:
        for enterprise in ('fixture-a','fixture-b','fixture-c'):
            p=c.execute('SELECT * FROM principals WHERE id=%s',(enterprise,)).fetchone()
            if not p:raise ValueError('explicit synthetic enterprise required')
            reviewer='prep-specialist-'+enterprise
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true) ON CONFLICT(id) DO NOTHING',(reviewer,digest(tokens[reviewer]),p['park_id'],p['org_id'],'park_specialist'))
            c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,'READ',%s,%s) ON CONFLICT DO NOTHING",(reviewer,p['park_id'],p['org_id']))
            for principal,cap in ((enterprise,'PREPARE'),(reviewer,'REVIEW_ASSIGNED')):
                c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(principal,p['park_id'],p['org_id'],cap))
            source={'kind':'SYNTHETIC','id':'ENG014-reviewed-fixture','revision':'1','statement':'合成资料整理服务，无资格条件；诉求摘要与材料目录由测试规格定义。'}
            c.execute("INSERT INTO preparation_catalog VALUES(%s,%s,1,'企业资料整理（合成）',%s,'SYNTHETIC','NOT_EVALUATED') ON CONFLICT DO NOTHING",(p['park_id'],SERVICE,Jsonb(source)))
