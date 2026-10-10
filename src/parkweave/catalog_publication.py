"""Owner-only isolated catalogue revision protocol; no app publishing authority."""
from copy import deepcopy
from uuid import UUID,uuid4
import re
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from psycopg.types.json import Jsonb
from psycopg.sql import SQL,Literal as SQLLiteral
from .store import Conflict,Denied

SCOPE='ISOLATED_CATALOG_APPROVAL_COORDINATION_V1'
COL='candidate_catalog_revisions'
HEAD='candidate_catalog_head'
LIMIT=32
FIELDS=('park_id','service_id','version','name','source','namespace','qualification')
TRIGGER_BODY="""
DECLARE before_value jsonb; after_value jsonb; n integer; i integer; last_event jsonb;
BEGIN
 before_value:=OLD.candidate_catalog_revisions; after_value:=NEW.candidate_catalog_revisions;
 IF after_value IS NOT DISTINCT FROM before_value THEN
  IF NEW.candidate_catalog_head IS DISTINCT FROM OLD.candidate_catalog_head
     OR (before_value IS NOT NULL AND NEW.source IS DISTINCT FROM OLD.source) THEN
   RAISE EXCEPTION 'immutable cooperative catalog source and head';
  END IF;
  RETURN NEW;
 END IF;
 IF jsonb_typeof(after_value) IS DISTINCT FROM 'object'
    OR after_value->>'scope' IS DISTINCT FROM 'ISOLATED_CATALOG_APPROVAL_COORDINATION_V1'
    OR jsonb_typeof(after_value->'events') IS DISTINCT FROM 'array' THEN
  RAISE EXCEPTION 'cooperative catalog history required';
 END IF;
 n:=jsonb_array_length(after_value->'events');
 IF n<1 OR n>32 OR (after_value->>'revision')::integer IS DISTINCT FROM n THEN
  RAISE EXCEPTION 'bounded cooperative catalog history required';
 END IF;
 IF before_value IS NULL THEN
  IF n<>1 THEN RAISE EXCEPTION 'initial catalog revision required'; END IF;
 ELSE
  IF n<>jsonb_array_length(before_value->'events')+1 THEN
   RAISE EXCEPTION 'catalog revision append only';
  END IF;
  FOR i IN 0..n-2 LOOP
   IF after_value->'events'->i IS DISTINCT FROM before_value->'events'->i THEN
    RAISE EXCEPTION 'immutable catalog revision';
   END IF;
  END LOOP;
 END IF;
 last_event:=after_value->'events'->(n-1);
 IF last_event->'catalog'->'source' IS DISTINCT FROM NEW.source
    OR last_event->'catalog'->>'park_id' IS DISTINCT FROM NEW.park_id
    OR last_event->'catalog'->>'service_id' IS DISTINCT FROM NEW.service_id
    OR (last_event->'catalog'->>'version')::integer IS DISTINCT FROM NEW.version
    OR (NEW.park_id,NEW.service_id,NEW.version,NEW.name,NEW.namespace,NEW.qualification)
       IS DISTINCT FROM (OLD.park_id,OLD.service_id,OLD.version,OLD.name,OLD.namespace,OLD.qualification) THEN
  RAISE EXCEPTION 'catalog publication source scope mismatch';
 END IF;
 NEW.candidate_catalog_head:=jsonb_build_object('scope',after_value->>'scope','id',last_event->>'id',
   'revision',n,'sha256',last_event->>'sha256','state',last_event->>'state');
 RETURN NEW;
END
"""

def normal(value):
    from .controlled_plans import _normal
    return _normal(value)

def digest(value):
    from .controlled_plans import _hash
    return _hash(value)

def key_of(parent):return (parent['park_id'],parent['service_id'],parent.get('service_version',parent.get('version')))

def lock_name(key):return 'candidate-catalog-approval:'+__import__('json').dumps(list(key),ensure_ascii=False,separators=(',',':'))

def lock(c,key,exclusive=False):
    function='pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
    c.execute('SELECT '+function+'(hashtextextended(%s,0))',(lock_name(key),))

def row(c,key,write=False):
    return c.execute('SELECT * FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s'+(' FOR UPDATE' if write else ''),key).fetchone()

def proof(value):
    """Strict independent head, immutable source snapshots, hash chain and key."""
    if value is None:raise Conflict('catalog source unavailable')
    journal=value.get(COL);head=value.get(HEAD)
    if journal is None:
        if head is not None:raise Conflict('cooperative catalog head has no history')
        return None
    try:
        if (not isinstance(journal,dict) or set(journal)!={'scope','revision','events'}
            or journal['scope']!=SCOPE or type(journal['revision']) is not int
            or not 1<=journal['revision']<=LIMIT or not isinstance(journal['events'],list)
            or len(journal['events'])!=journal['revision']):raise ValueError()
        previous=None;ids=set();keys=set();initial=None
        for n,e in enumerate(journal['events'],1):
            required={'id','revision','action','state','key','request','fingerprint','actor','catalog','catalog_sha256','previous_sha256','sha256'}
            if (not isinstance(e,dict) or set(e)!=required or type(e['revision']) is not int or e['revision']!=n
                or e['id'] in ids or e['key'] in keys or e['previous_sha256']!=previous
                or e['sha256']!=digest({k:v for k,v in e.items() if k!='sha256'})
                or e['fingerprint']!=digest(e['request']) or set(e['catalog'])!=set(FIELDS)
                or e['catalog_sha256']!=digest(e['catalog']) or e['catalog']['namespace']!='SYNTHETIC'
                or e['catalog']['qualification']!='NOT_EVALUATED'
                or not isinstance(e['catalog']['source'],dict) or e['catalog']['source'].get('kind')!='SYNTHETIC'
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',e['key']) or not isinstance(e['actor'],str)):
                raise ValueError()
            UUID(e['id'])
            if n==1:
                if e['action']!='INIT' or e['state']!='ACTIVE' or e['request']!={'action':'INIT'}:raise ValueError()
                initial=e
            else:
                command=Publication.model_validate(e['request'])
                if (command.expected_revision!=n-1 or command.action!=e['action']
                    or e['state']!=('WITHDRAWN' if command.action=='WITHDRAW' else 'ACTIVE')
                    or e['actor']!=initial['actor']
                    or {k:v for k,v in e['catalog'].items() if k!='source'}!={k:v for k,v in initial['catalog'].items() if k!='source'}):raise ValueError()
                source=deepcopy(initial['catalog']['source'])
                if command.action=='PUBLISH':source['revision']=str(command.source_revision)
                else:source=journal['events'][n-2]['catalog']['source']
                if source!=e['catalog']['source']:raise ValueError()
            ids.add(e['id']);keys.add(e['key']);previous=e['sha256']
        last=journal['events'][-1]
        expected=dict(scope=SCOPE,id=last['id'],revision=last['revision'],sha256=last['sha256'],state=last['state'])
        if (not isinstance(head,dict) or type(head.get('revision')) is not int
            or head!=expected or any(normal(value[k])!=last['catalog'][k] for k in FIELDS)
            or tuple(last['catalog'][k] for k in ('park_id','service_id','version'))!=key_of(value)):raise ValueError()
        return deepcopy(head)
    except (ValueError,KeyError,TypeError,AttributeError):raise Conflict('cooperative catalog original proof mismatch')

def snapshot(c,parent):
    value=row(c,key_of(parent))
    if value is None:return None
    result={k:value[k] for k in ('service_id','version','source','namespace','qualification')}
    descriptor=proof(value)
    if descriptor is not None:result['cooperative_catalog']=descriptor
    return normal(result)

class Publication(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action:Literal['PUBLISH','WITHDRAW']
    expected_revision:int=Field(ge=1,le=LIMIT)
    source_revision:int|None=Field(default=None,ge=1,le=9999)
    reason:str=Field(min_length=1,max_length=1000)
    @model_validator(mode='after')
    def exact(self):
        if (self.action=='PUBLISH')!=(self.source_revision is not None) or not self.reason.strip():raise ValueError('explicit bounded synthetic publication required')
        return self

class IsolatedCatalogPublication:
    def __init__(self,approval,*,enabled_for_isolated_tests=False):
        from .service_plan_approval import IsolatedPlanApproval
        if enabled_for_isolated_tests is not True or type(approval) is not IsolatedPlanApproval:
            raise Denied('explicit issued isolated Approval required')
        approval._issued();self.approval=approval;self.owner=approval.owner
        with self.owner.connect() as c:
            approval._owner_proof(c)
            parents=c.execute('SELECT * FROM preparations WHERE id=ANY(%s)',([UUID(i) for i in approval.ids],)).fetchall()
            self.parents={str(p['id']):key_of(p) for p in parents}
            if len(self.parents)!=len(approval.ids):raise Denied('original catalog Case scope required')
            exists=c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='preparation_catalog' AND column_name=%s",(COL,)).fetchone()
            if not exists:
                c.execute('ALTER TABLE preparation_catalog ADD COLUMN candidate_catalog_revisions jsonb, ADD COLUMN candidate_catalog_head jsonb')
                c.execute(SQL('CREATE FUNCTION candidate_catalog_prefix() RETURNS trigger LANGUAGE plpgsql AS {}').format(SQLLiteral(TRIGGER_BODY)))
                c.execute('CREATE TRIGGER candidate_catalog_prefix BEFORE UPDATE ON preparation_catalog FOR EACH ROW EXECUTE FUNCTION candidate_catalog_prefix()')
            self._schema(c)
            for key in sorted(set(self.parents.values())):
                lock(c,key,exclusive=True);value=row(c,key,write=True)
                if (not value or value['namespace']!='SYNTHETIC' or not isinstance(value['source'],dict) or value['source'].get('kind')!='SYNTHETIC'
                    or value['service_id']!='synthetic-material-preparation' or value['version']!=1):raise Denied('original synthetic catalog only')
                if proof(value) is None:self._append(c,value,'INIT',{'action':'INIT'},'init-'+uuid4().hex)
        approval._catalog_publication=self

    def _schema(self,c):
        r=c.execute("""SELECT f.prosrc,t.tgenabled,t.tgtype,f.proowner=r.relowner correct_owner,f.prosecdef,f.proconfig,l.lanname
            FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid JOIN pg_class r ON r.oid=t.tgrelid
            JOIN pg_language l ON l.oid=f.prolang WHERE t.tgrelid='preparation_catalog'::regclass
            AND t.tgname='candidate_catalog_prefix' AND t.tgattr::text='' AND NOT t.tgisinternal""").fetchone()
        if (not r or r['prosrc']!=TRIGGER_BODY or r['tgenabled']!='O' or r['tgtype']!=19
            or not r['correct_owner'] or r['prosecdef'] or r['proconfig'] is not None or r['lanname']!='plpgsql'):
            raise Denied('cooperative catalog immutable schema required')

    def acquire(self,c,parent):
        if self.parents.get(str(parent['id']))!=key_of(parent):raise Denied('original cooperative catalog scope required')
        self._schema(c);lock(c,key_of(parent));descriptor=proof(row(c,key_of(parent)))
        if descriptor is None or descriptor['state']!='ACTIVE':raise Conflict('current active catalog publication required')
        return descriptor

    def _append(self,c,value,action,request,key):
        journal=deepcopy(value.get(COL)) or dict(scope=SCOPE,revision=0,events=[])
        previous=journal['events'][-1] if journal['events'] else None
        catalog=normal({k:value[k] for k in FIELDS})
        if action=='PUBLISH':
            catalog['source']=deepcopy(journal['events'][0]['catalog']['source']);catalog['source']['revision']=str(request['source_revision'])
        e=dict(id=str(uuid4()),revision=journal['revision']+1,action=action,state='WITHDRAWN' if action=='WITHDRAW' else 'ACTIVE',
            key=key,request=request,fingerprint=digest(request),actor=self.approval.proof.cluster.owner,catalog=catalog,
            catalog_sha256=digest(catalog),previous_sha256=previous['sha256'] if previous else None)
        e['sha256']=digest(e);journal['events'].append(e);journal['revision']+=1
        updated=c.execute('UPDATE preparation_catalog SET source=%s,candidate_catalog_revisions=%s WHERE park_id=%s AND service_id=%s AND version=%s AND candidate_catalog_revisions IS NOT DISTINCT FROM %s RETURNING *',
            (Jsonb(catalog['source']),Jsonb(journal),*key_of(value),Jsonb(value[COL]) if value.get(COL) is not None else None)).fetchone()
        if not updated:raise Conflict('catalog CAS changed')
        proof(updated);return e

    def publish(self,parent_id,key,data):
        """Synthetic fixture owner only; never called from an application route."""
        data=Publication.model_validate(data);request=data.model_dump(mode='json');request={k:v for k,v in request.items() if v is not None}
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key):raise Conflict('bounded publication key required')
        target=self.parents.get(str(parent_id))
        if target is None:raise Denied('original fixture catalog scope required')
        with self.owner.connect() as c:
            self.approval._owner_proof(c);self._schema(c);lock(c,target,exclusive=True);value=row(c,target,write=True);current=proof(value)
            if current is None:raise Conflict('catalog publication proof required')
            event=next((e for e in value[COL]['events'] if e['key']==key),None)
            if event:
                if event['request']!=request:raise Conflict('publication key command changed')
                return deepcopy(event)
            if current['revision']!=data.expected_revision or current['revision']>=LIMIT or (data.action=='PUBLISH' and current['revision']>=LIMIT-1):
                raise Conflict('publication revision changed or withdrawal capacity reserved')
            return self._append(c,value,data.action,request,key)
