"""3–8 existing authorized holds; no new resource, grant, schema or fulfillment."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from . import resource_combinations as rc, resource_holds as rh
from .store import Conflict, digest

SCOPE='LOCAL_SYNTHETIC_BOUNDED_RESOURCE_BUNDLE_ONLY'
LIMIT=8

class Bundle(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    members:list[rc.Member]=Field(min_length=3,max_length=LIMIT)
    @model_validator(mode='after')
    def distinct(self):
        if len({m.hold_id for m in self.members})!=len(self.members):raise ValueError('distinct holds required')
        self.members.sort(key=lambda m:str(m.hold_id))
        return self

def manifest(holds):
    rows=[{k:str(h[k]) if k in ('id','resource_id') else h[k].isoformat() if k in ('starts_at','ends_at') else h[k]
           for k in ('id','resource_id','resource_revision','starts_at','ends_at','quantity')} for h in sorted(holds,key=lambda h:str(h['id']))]
    from .preparation import canonical
    return dict(manifest_version=1,manifest=rows,manifest_sha256=digest(canonical(rows)))

def validate_manifest(proof,holds):
    if not 3<=len(holds)<=LIMIT or len({h['id'] for h in holds})!=len(holds):raise Conflict('bounded bundle integrity conflict')
    expected=manifest(holds)
    if any(proof.get(k)!=v for k,v in expected.items()):raise Conflict('bundle immutable manifest mismatch')

def require_kind(c,id,bundle=True):
    rows=c.execute("SELECT payload FROM synthetic_resource_combination_receipts WHERE combination_id=%s AND action='CONFIRM'",(id,)).fetchall()
    if len(rows)!=1 or (rows[0]['payload'].get('scope')==SCOPE)!=bundle:raise Conflict('original resource combination contract required')

def confirm(store,token,key,data):return rc.confirm(store,token,key,data,bundle=True)
def cancel(store,token,id,key):return rc.cancel(store,token,id,key,bundle=True)

def read(store,token,id):
    with store.connect() as c:
        p=rh._auth(store,c,token);g=rc._group(c,p,id);require_kind(c,id)
        hs=rc._members(c,p,id);rc._scope_lock(c,p,hs)
        g=rc._group(c,p,id);hs=rc._members(c,p,id);now=rh._now(c)
        return rh._boundary(actor_id=p['id'],confirmation_scope=SCOPE,combination=rc._view(g,hs,now),server_time=now)

def recover(store,token,key):
    with store.connect() as c:
        p=rh._auth(store,c,token);rh._key(c,p,key)
        r=c.execute('SELECT * FROM synthetic_resource_combination_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
        if not r:
            other=c.execute('SELECT 1 FROM synthetic_resource_receipts WHERE actor_id=%s AND request_key=%s',(p['id'],key)).fetchone()
            if other:raise Conflict('original request contract mismatch')
            return rh._boundary(actor_id=p['id'],status='NOT_OBSERVED',historical_only=True,automatically_replayed=False,confirmation_scope=SCOPE)
        if r['payload'].get('scope')!=SCOPE:raise Conflict('original request contract mismatch')
        g=rc._group(c,p,r['combination_id']);require_kind(c,g['id']);hs=rc._members(c,p,g['id']);rc._scope_lock(c,p,hs)
        g=rc._group(c,p,g['id']);hs=rc._members(c,p,g['id']);now=rh._now(c)
        return rh._boundary(actor_id=p['id'],status='COMMITTED',historical_only=True,automatically_replayed=False,confirmation_scope=SCOPE,
                            receipt=r['payload'],combination=rc._view(g,hs,now),server_time=now)

def list_items(store,token):
    with store.connect() as c:
        p=rh._auth(store,c,token)
        groups=c.execute('''SELECT g.* FROM synthetic_resource_combinations g
            JOIN synthetic_resource_combination_receipts r ON r.combination_id=g.id AND r.action='CONFIRM'
            WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND r.payload->>'scope'=%s
            AND (SELECT count(*) FROM synthetic_resource_combination_members m WHERE m.combination_id=g.id) BETWEEN 3 AND 8
            AND NOT EXISTS(SELECT 1 FROM synthetic_resource_combination_members m JOIN synthetic_resource_holds h ON h.id=m.hold_id
              WHERE m.combination_id=g.id AND NOT EXISTS(SELECT 1 FROM synthetic_resource_grants a
                WHERE a.resource_id=h.resource_id AND a.principal_id=%s AND a.park_id=%s AND a.org_id=%s AND a.capability='READ' AND a.active))
            ORDER BY g.created_at DESC,g.id DESC LIMIT 101''',(p['id'],p['park_id'],p['org_id'],SCOPE,p['id'],p['park_id'],p['org_id'])).fetchall()
        hs={g['id']:rc._members(c,p,g['id']) for g in groups[:100]};rc._scope_lock(c,p,[h for rows in hs.values() for h in rows]);now=rh._now(c)
        items=[rc._view(rc._group(c,p,g['id']),rc._members(c,p,g['id']),now) for g in groups[:100]]
        return rh._boundary(actor_id=p['id'],confirmation_scope=SCOPE,items=items,has_older_records=len(groups)>100,server_time=now)
