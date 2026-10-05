"""Registered SYNTHETIC local holds, never formal reservations or fulfillment."""
from collections import defaultdict
from datetime import timedelta, timezone
import json
from uuid import UUID, uuid4
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from psycopg.errors import LockNotAvailable
from psycopg.types.json import Jsonb
from .store import Conflict, Denied, digest

RESOURCE_ID=UUID('fa161ea0-b665-4ec5-b345-a070bfec764d')
SCOPE='SYNTHETIC_LOCAL_RESOURCE_HOLD_ONLY'

class Preview(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    starts_at: AwareDatetime=Field(strict=False)
    ends_at: AwareDatetime=Field(strict=False)
    quantity: int=Field(ge=1,le=20)
    @field_validator('starts_at','ends_at')
    @classmethod
    def utc(cls,value):return value.astimezone(timezone.utc)
    @model_validator(mode='after')
    def window(self):
        if not timedelta(0)<self.ends_at-self.starts_at<=timedelta(hours=4):
            raise ValueError('positive window of at most four hours required')
        return self

class Hold(Preview):
    expected_revision: int=Field(ge=1)
    ttl_seconds: int=Field(default=120,ge=5,le=300)
    purpose: str=Field(min_length=1,max_length=200)

class Confirm(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    expected_revision: int=Field(ge=1)

class Release(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


def _auth(store,c,token,write=False):
    c.execute("SET LOCAL lock_timeout='3s'")
    try:p=store.auth(c,token,lock=True)
    except LockNotAvailable as e:raise Conflict('authorization busy; retry the same request key') from e
    if p['role']!='enterprise_operator':raise Denied('enterprise resource scope required')
    store.check_capability(c,p,'READ')
    if write:store.check_capability(c,p,'EXECUTE')
    return p


def _scope(c,p,id,write=False):
    r=c.execute('SELECT * FROM synthetic_resources WHERE id=%s AND park_id=%s',(id,p['park_id'])).fetchone()
    if not r:raise Denied('resource unavailable')
    for cap in ('READ','HOLD') if write else ('READ',):
        if not c.execute('SELECT 1 FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s AND park_id=%s AND org_id=%s AND capability=%s AND active',(p['id'],id,p['park_id'],p['org_id'],cap)).fetchone():
            raise Denied('current resource grant required')
    return r


def _lock(c,id,shared=False):
    fn='pg_advisory_xact_lock_shared' if shared else 'pg_advisory_xact_lock'
    try:c.execute(f'SELECT {fn}(hashtextextended(%s,0))',('synthetic-resource:'+str(id),))
    except LockNotAvailable as e:raise Conflict('resource busy; retry the same request key') from e


def _key(c,p,key):
    try:c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('synthetic-resource-key:'+p['id']+':'+key,))
    except LockNotAvailable as e:raise Conflict('request busy; retry the same request key') from e


def _now(c):return c.execute('SELECT clock_timestamp() AS now').fetchone()['now']


def _window(r,data,now):
    if not r['enabled']:raise Conflict('synthetic resource disabled')
    if r['namespace']!='SYNTHETIC' or r['authority']!='LOCAL_AUTHORITY':raise Conflict('unsupported authority')
    lo=data.starts_at-timedelta(seconds=r['buffer_seconds']);hi=data.ends_at+timedelta(seconds=r['buffer_seconds'])
    if data.starts_at<now or lo<r['open_from'] or hi>r['open_until']:
        raise Conflict('window outside current synthetic opening interval')
    return lo,hi


def _peak(c,id,lo,hi,now,exclude=None):
    rows=c.execute("""SELECT starts_at,ends_at,buffer_seconds,quantity FROM synthetic_resource_holds
        WHERE resource_id=%s AND ((state='HELD' AND expires_at>%s) OR state='CONFIRMED')
        AND (%s::uuid IS NULL OR id<>%s::uuid)
        AND starts_at-make_interval(secs=>buffer_seconds)<%s
        AND ends_at+make_interval(secs=>buffer_seconds)>%s""",(id,now,exclude,exclude,hi,lo)).fetchall()
    points=defaultdict(int)
    for h in rows:
        start=max(lo,h['starts_at']-timedelta(seconds=h['buffer_seconds']))
        end=min(hi,h['ends_at']+timedelta(seconds=h['buffer_seconds']))
        points[start]+=h['quantity'];points[end]-=h['quantity']
    used=peak=0
    for at in sorted(points):
        used+=points[at];peak=max(peak,used)
    return peak


def _public(h,now):
    result={k:h[k] for k in ('id','resource_id','resource_revision','starts_at','ends_at','quantity','purpose','created_at','expires_at')}
    result['state']=h['state'] if h['state'] in ('RELEASED','CONFIRMED') else 'EXPIRED' if h['expires_at']<=now else 'HELD'
    result['local_confirmation']='CONFIRMED' if h['state']=='CONFIRMED' else 'NOT_CONFIRMED'
    result['combination_id']=h.get('combination_id')
    result['resource_name']=h.get('resource_name','合成资源')
    return result


def _boundary(**extra):
    return dict(scope=SCOPE,namespace='SYNTHETIC',reservation='NOT_CONFIRMED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE',**extra)


def catalog(store,token):
    with store.connect() as c:
        p=_auth(store,c,token)
        rows=c.execute("""SELECT r.id,r.name,r.revision,r.capacity,r.buffer_seconds,r.open_from,r.open_until,
            r.enabled,r.timezone,r.namespace,r.authority,r.source FROM synthetic_resources r
            JOIN synthetic_resource_grants g ON g.resource_id=r.id AND g.park_id=r.park_id
            WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND g.capability='READ' AND g.active
            ORDER BY r.id LIMIT 100""",(p['id'],p['park_id'],p['org_id'])).fetchall()
        return _boundary(items=rows,server_time=_now(c))


def preview(store,token,id,data):
    with store.connect() as c:
        p=_auth(store,c,token);_scope(c,p,id);_lock(c,id,shared=True);r=_scope(c,p,id);now=_now(c)
        lo,hi=_window(r,data,now);peak=_peak(c,id,lo,hi,now)
        return _boundary(resource_id=id,resource_revision=r['revision'],server_time=now,
            starts_at=data.starts_at,ends_at=data.ends_at,quantity=data.quantity,capacity=r['capacity'],
            buffer_seconds=r['buffer_seconds'],occupied_peak=peak,available_quantity=max(0,r['capacity']-peak),
            available=peak+data.quantity<=r['capacity'],preview_only=True)


def _fingerprint(action,id,data):
    return digest(json.dumps({'action':action,'id':str(id),'input':data.model_dump(mode='json')},sort_keys=True,separators=(',',':'),ensure_ascii=False))


def _replay(c,p,key,fp):
    row=c.execute('SELECT payload,fingerprint FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s UNION ALL SELECT payload,fingerprint FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key,p['id'],key)).fetchone()
    if row:
        if row['fingerprint']!=fp:raise Conflict('request key fingerprint mismatch')
        return row['payload']


def _receipt(c,p,h,key,fp,action,now):
    payload={'hold_id':str(h['id']),'action':action,'observed_state':_public(h,now)['state'],
             'at':now.isoformat(),'expires_at':h['expires_at'].isoformat(),'scope':SCOPE}
    c.execute('INSERT INTO synthetic_resource_receipts VALUES(%s,%s,%s,%s,%s,%s,%s)',(uuid4(),h['id'],p['id'],key,fp,action,Jsonb(payload)))
    return payload


def _own(c,p,id,lock=False):
    row=c.execute('SELECT h.*,m.combination_id,r.name AS resource_name FROM synthetic_resource_holds h JOIN synthetic_resources r ON r.id=h.resource_id LEFT JOIN synthetic_resource_combination_members m ON m.hold_id=h.id WHERE h.id=%s AND h.principal_id=%s AND h.park_id=%s AND h.org_id=%s'+(' FOR UPDATE OF h' if lock else ''),(id,p['id'],p['park_id'],p['org_id'])).fetchone()
    if not row:raise Denied('hold unavailable')
    return row


def create(store,token,id,key,data):
    fp=_fingerprint('HOLD',id,data)
    with store.connect() as c:
        p=_auth(store,c,token,write=True);_scope(c,p,id,write=True);_key(c,p,key);_lock(c,id)
        r=_scope(c,p,id,write=True);now=_now(c);receipt=_replay(c,p,key,fp)
        if receipt:
            h=_own(c,p,UUID(receipt['hold_id']))
        else:
            if r['revision']!=data.expected_revision:raise Conflict('resource revision changed; preview again')
            lo,hi=_window(r,data,now)
            if _peak(c,id,lo,hi,now)+data.quantity>r['capacity']:raise Conflict('synthetic resource capacity conflict')
            h=c.execute("""INSERT INTO synthetic_resource_holds(id,resource_id,principal_id,park_id,org_id,
                resource_revision,starts_at,ends_at,quantity,buffer_seconds,purpose,state,created_at,expires_at,namespace)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'HELD',%s,%s,'SYNTHETIC') RETURNING *""",
                (uuid4(),id,p['id'],p['park_id'],p['org_id'],r['revision'],data.starts_at,data.ends_at,
                 data.quantity,r['buffer_seconds'],data.purpose,now,now+timedelta(seconds=data.ttl_seconds))).fetchone()
            receipt=_receipt(c,p,h,key,fp,'HOLD',now)
        h['resource_name']=r['name']
        return _boundary(receipt=receipt,hold=_public(h,now),server_time=now)


def read(store,token,id):
    with store.connect() as c:
        p=_auth(store,c,token);h=_own(c,p,id);_scope(c,p,h['resource_id']);_lock(c,h['resource_id'],shared=True);h=_own(c,p,id);now=_now(c)
        return _boundary(hold=_public(h,now),server_time=now)


def list_holds(store,token):
    with store.connect() as c:
        p=_auth(store,c,token);now=_now(c)
        rows=c.execute("""SELECT h.*,m.combination_id,r.name AS resource_name FROM synthetic_resource_holds h
            LEFT JOIN synthetic_resource_combination_members m ON m.hold_id=h.id
            JOIN synthetic_resources r ON r.id=h.resource_id AND r.park_id=h.park_id
            JOIN synthetic_resource_grants g ON g.resource_id=h.resource_id AND g.principal_id=h.principal_id
            AND g.park_id=h.park_id AND g.org_id=h.org_id AND g.capability='READ' AND g.active
            WHERE h.principal_id=%s AND h.park_id=%s AND h.org_id=%s ORDER BY h.created_at DESC,h.id DESC LIMIT 101""",(p['id'],p['park_id'],p['org_id'])).fetchall()
        return _boundary(items=[_public(h,now) for h in rows[:100]],has_older_records=len(rows)>100,server_time=now)


def release(store,token,id,key):
    fp=_fingerprint('RELEASE',id,Release())
    with store.connect() as c:
        p=_auth(store,c,token,write=True);h=_own(c,p,id);_scope(c,p,h['resource_id'],write=True)
        _key(c,p,key);_lock(c,h['resource_id']);r=_scope(c,p,h['resource_id'],write=True)
        h=_own(c,p,id,lock=True);now=_now(c);receipt=_replay(c,p,key,fp)
        if not receipt:
            if h.get('combination_id'):raise Conflict('release the complete combination')
            if h['state']=='CONFIRMED' or (h['state']=='HELD' and h['expires_at']>now):
                h=c.execute("UPDATE synthetic_resource_holds SET state='RELEASED' WHERE id=%s RETURNING *",(id,)).fetchone()
            receipt=_receipt(c,p,h,key,fp,'RELEASE',now)
        h['resource_name']=r['name']
        return _boundary(receipt=receipt,hold=_public(h,now),server_time=now)


def confirm(store,token,id,key,data):
    fp=_fingerprint('CONFIRM',id,data)
    with store.connect() as c:
        p=_auth(store,c,token,write=True);h=_own(c,p,id);_scope(c,p,h['resource_id'],write=True)
        _key(c,p,key);_lock(c,h['resource_id']);r=_scope(c,p,h['resource_id'],write=True)
        h=_own(c,p,id,lock=True);now=_now(c);receipt=_replay(c,p,key,fp)
        if not receipt:
            if h.get('combination_id'):raise Conflict('hold belongs to a complete combination')
            if h['state']!='HELD' or h['expires_at']<=now:raise Conflict('valid unconfirmed hold required')
            if data.expected_revision!=h['resource_revision'] or data.expected_revision!=r['revision']:
                raise Conflict('resource revision changed; release and preview again')
            window=Preview(starts_at=h['starts_at'],ends_at=h['ends_at'],quantity=h['quantity'])
            lo,hi=_window(r,window,now)
            if _peak(c,h['resource_id'],lo,hi,now,exclude=id)+h['quantity']>r['capacity']:
                raise Conflict('synthetic resource capacity conflict')
            h=c.execute("UPDATE synthetic_resource_holds SET state='CONFIRMED' WHERE id=%s RETURNING *",(id,)).fetchone()
            receipt=_receipt(c,p,h,key,fp,'CONFIRM',now)
        h['resource_name']=r['name']
        return _boundary(receipt=receipt,hold=_public(h,now),server_time=now,
                         confirmation_scope='LOCAL_SYNTHETIC_SINGLE_RESOURCE_ONLY')


def seed_synthetic(owner):
    """Explicit owner fixture only; no grant repair or production resource claim."""
    with owner.connect() as c:
        _lock(c,RESOURCE_ID)
        source={'kind':'SYNTHETIC','id':'ENG018-reviewed-resource-fixture','revision':'1','statement':'合成协作空间，容量2，前后缓冲各5分钟；不是真实园区资源。'}
        c.execute("""INSERT INTO synthetic_resources VALUES(%s,'park-a','合成协作空间',1,2,300,
            clock_timestamp()-interval '1 day',clock_timestamp()+interval '30 days',true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)
            ON CONFLICT(id) DO NOTHING""",(RESOURCE_ID,Jsonb(source)))
        for id in ('fixture-a','fixture-b'):
            p=c.execute('SELECT * FROM principals WHERE id=%s',(id,)).fetchone()
            if not p or p['park_id']!='park-a':raise ValueError('explicit synthetic enterprise required')
            for cap in ('READ','HOLD'):
                c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true) ON CONFLICT DO NOTHING',(id,RESOURCE_ID,p['park_id'],p['org_id'],cap))
