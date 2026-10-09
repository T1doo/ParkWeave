"""Exactly two local synthetic holds, confirmed/cancelled in one transaction."""
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.types.json import Jsonb
from . import resource_holds as rh
from .store import Conflict,Denied

SECOND_RESOURCE_ID=UUID('fb161ea0-b665-4ec5-b345-a070bfec764d')
SCOPE='LOCAL_SYNTHETIC_TWO_RESOURCE_COMBINATION_ONLY'

class Member(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    hold_id: UUID=Field(strict=False)
    expected_revision: int=Field(ge=1)

class Combination(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    members: list[Member]=Field(min_length=2,max_length=2)
    @model_validator(mode='after')
    def distinct(self):
        if len({x.hold_id for x in self.members})!=2:raise ValueError('two distinct holds required')
        self.members.sort(key=lambda x:str(x.hold_id))
        return self


def _group(c,p,id,lock=False):
    g=c.execute('SELECT * FROM synthetic_resource_combinations WHERE id=%s AND principal_id=%s AND park_id=%s AND org_id=%s'+(' FOR UPDATE' if lock else ''),(id,p['id'],p['park_id'],p['org_id'])).fetchone()
    if not g:raise Denied('combination unavailable')
    return g


def _members(c,p,id,lock=False):
    rows=c.execute('SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s ORDER BY hold_id',(id,)).fetchall()
    holds=[rh._own(c,p,row['hold_id'],lock=lock) for row in rows]
    from .resource_bundles import SCOPE as BUNDLE_SCOPE, validate_manifest
    receipt=c.execute("SELECT payload FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND action='CONFIRM'",(id,)).fetchall()
    bundle=bool(receipt and receipt[0]['payload'].get('scope')==BUNDLE_SCOPE)
    if bundle:
        if len(receipt)!=1:raise Conflict('bundle confirmation proof conflict')
        validate_manifest(receipt[0]['payload'],holds)
    elif len(holds)!=2 or len({h['resource_id'] for h in holds})!=2:raise Conflict('combination integrity conflict')
    return sorted(holds,key=lambda h:(str(h['resource_id']),str(h['id'])))


def _scope_lock(c,p,holds,write=False):
    ids=sorted({h['resource_id'] for h in holds},key=str)
    for id in ids:rh._scope(c,p,id,write=write)
    for id in ids:rh._lock(c,id,shared=not write)
    return {id:rh._scope(c,p,id,write=write) for id in ids}


def _view(g,holds,now):
    state='CONFIRMED' if g['state']=='CONFIRMED' else 'RELEASED'
    if any(h['state']!=state for h in holds):raise Conflict('combination integrity conflict')
    return {'id':g['id'],'state':g['state'],'created_at':g['created_at'],
            'members':[rh._public(h,now) for h in holds]}


def _receipt(c,p,g,key,fp,action,now,scope=SCOPE,**extra):
    payload={'combination_id':str(g['id']),'action':action,'observed_state':g['state'],'at':now.isoformat(),'scope':scope,**extra}
    c.execute('INSERT INTO synthetic_resource_combination_receipts VALUES(%s,%s,%s,%s,%s,%s,%s)',(uuid4(),g['id'],p['id'],key,fp,action,Jsonb(payload)))
    return payload


def confirm(store,token,key,data,*,bundle=False):
    from . import resource_bundles as rb
    scope=rb.SCOPE if bundle else SCOPE
    fp=rh._fingerprint('RESOURCE_BUNDLE_CONFIRM' if bundle else 'COMBINATION_CONFIRM',UUID(int=0),data)
    with store.connect() as c:
        p=rh._auth(store,c,token,write=True)
        holds=[rh._own(c,p,m.hold_id) for m in data.members]
        if not bundle and len({h['resource_id'] for h in holds})!=2:raise Conflict('two different resources required')
        for h in holds:rh._scope(c,p,h['resource_id'],write=True)
        rh._key(c,p,key);rules=_scope_lock(c,p,holds,write=True)
        holds=[rh._own(c,p,m.hold_id,lock=True) for m in data.members]
        now=rh._now(c);receipt=rh._replay(c,p,key,fp)
        if receipt:
            g=_group(c,p,UUID(receipt['combination_id']));holds=_members(c,p,g['id'])
        else:
            revisions={m.hold_id:m.expected_revision for m in data.members}
            # All checks precede every mutation; resource mutexes stay held to commit.
            for h in holds:
                r=rules[h['resource_id']]
                if h.get('combination_id') or h['state']!='HELD' or h['expires_at']<=now:
                    raise Conflict('combination requires valid unconfirmed holds')
                if revisions[h['id']]!=h['resource_revision'] or revisions[h['id']]!=r['revision']:
                    raise Conflict('combination resource revision changed; release and preview again')
                lo,hi=rh._window(r,rh.Preview(starts_at=h['starts_at'],ends_at=h['ends_at'],quantity=h['quantity']),now)
                if rh._peak(c,h['resource_id'],lo,hi,now,exclude=h['id'])+h['quantity']>r['capacity']:
                    raise Conflict('combination resource capacity conflict')
            g=c.execute("INSERT INTO synthetic_resource_combinations VALUES(%s,%s,%s,%s,'CONFIRMED',%s) RETURNING *",(uuid4(),p['id'],p['park_id'],p['org_id'],now)).fetchone()
            for h in holds:
                c.execute("UPDATE synthetic_resource_holds SET state='CONFIRMED' WHERE id=%s",(h['id'],))
                c.execute('INSERT INTO synthetic_resource_combination_members VALUES(%s,%s)',(g['id'],h['id']))
            proof=rb.manifest(holds) if bundle else {}
            receipt=_receipt(c,p,g,key,fp,'CONFIRM',now,scope=scope,**proof)
            holds=_members(c,p,g['id'])
        # The principal/resource mutex protocol is the existing authority boundary.
        for h in holds:rh._scope(c,p,h['resource_id'],write=True)
        return rh._boundary(confirmation_scope=scope,combination=_view(g,holds,now),receipt=receipt,server_time=now)


def read(store,token,id):
    with store.connect() as c:
        p=rh._auth(store,c,token);g=_group(c,p,id);holds=_members(c,p,id)
        from .resource_bundles import require_kind
        require_kind(c,id,False)
        _scope_lock(c,p,holds);g=_group(c,p,id);holds=_members(c,p,id);now=rh._now(c)
        return rh._boundary(confirmation_scope=SCOPE,combination=_view(g,holds,now),server_time=now)


def cancel(store,token,id,key,*,bundle=False):
    from . import resource_bundles as rb
    scope=rb.SCOPE if bundle else SCOPE
    fp=rh._fingerprint('RESOURCE_BUNDLE_CANCEL' if bundle else 'COMBINATION_CANCEL',id,rh.Release())
    with store.connect() as c:
        p=rh._auth(store,c,token,write=True);g=_group(c,p,id);holds=_members(c,p,id)
        rb.require_kind(c,id,bundle)
        for h in holds:rh._scope(c,p,h['resource_id'],write=True)
        rh._key(c,p,key);_scope_lock(c,p,holds,write=True)
        g=_group(c,p,id,lock=True);holds=_members(c,p,id,lock=True);now=rh._now(c)
        _view(g,holds,now);receipt=rh._replay(c,p,key,fp)
        if not receipt:
            if g['state']=='CONFIRMED':
                for h in holds:c.execute("UPDATE synthetic_resource_holds SET state='RELEASED' WHERE id=%s",(h['id'],))
                g=c.execute("UPDATE synthetic_resource_combinations SET state='CANCELLED' WHERE id=%s RETURNING *",(id,)).fetchone()
                holds=_members(c,p,id)
            receipt=_receipt(c,p,g,key,fp,'CANCEL',now,scope=scope)
        for h in holds:rh._scope(c,p,h['resource_id'],write=True)
        return rh._boundary(confirmation_scope=scope,combination=_view(g,holds,now),receipt=receipt,server_time=now)


def list_combinations(store,token):
    with store.connect() as c:
        p=rh._auth(store,c,token)
        groups=c.execute("""SELECT g.* FROM synthetic_resource_combinations g WHERE principal_id=%s AND park_id=%s AND org_id=%s
          AND (SELECT count(*) FROM synthetic_resource_combination_members m WHERE m.combination_id=g.id)=2
          AND (SELECT count(*) FROM synthetic_resource_combination_members m JOIN synthetic_resource_holds h ON h.id=m.hold_id
            JOIN synthetic_resources r ON r.id=h.resource_id AND r.park_id=h.park_id
            JOIN synthetic_resource_grants a ON a.resource_id=h.resource_id AND a.principal_id=h.principal_id AND a.park_id=h.park_id AND a.org_id=h.org_id
            WHERE m.combination_id=g.id AND a.capability='READ' AND a.active)=2
          ORDER BY created_at DESC,id DESC LIMIT 101""",(p['id'],p['park_id'],p['org_id'])).fetchall()
        members={g['id']:_members(c,p,g['id']) for g in groups[:100]}
        _scope_lock(c,p,[h for hs in members.values() for h in hs]);now=rh._now(c)
        return rh._boundary(confirmation_scope=SCOPE,items=[_view(_group(c,p,g['id']),_members(c,p,g['id']),now) for g in groups[:100]],has_older_records=len(groups)>100,server_time=now)


def seed_synthetic(owner):
    """Explicit additional fake registry; never repairs existing grants/rules."""
    rh.seed_synthetic(owner)
    with owner.connect() as c:
        rh._lock(c,SECOND_RESOURCE_ID)
        c.execute("""INSERT INTO synthetic_resources VALUES(%s,'park-a','合成研讨设备',1,2,300,
          clock_timestamp()-interval '1 day',clock_timestamp()+interval '30 days',true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)
          ON CONFLICT(id) DO NOTHING""",(SECOND_RESOURCE_ID,Jsonb({'kind':'SYNTHETIC','id':'ENG021-second-resource','revision':'1','statement':'合成设备份额，非真实设备或外部预订。'})))
        for id in ('fixture-a','fixture-b'):
            p=c.execute('SELECT * FROM principals WHERE id=%s',(id,)).fetchone()
            for cap in ('READ','HOLD'):c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true) ON CONFLICT DO NOTHING',(id,SECOND_RESOURCE_ID,p['park_id'],p['org_id'],cap))
