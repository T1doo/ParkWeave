"""Issued owned-PG birth tracking; absence alone never means not started.

Only new preparations born after explicit installation qualify. Trusted owner
continuity is checked by original catalog identities/xmin, not promised against
an arbitrary superuser forging system catalogs. No role or privilege is added.
"""
from uuid import UUID,uuid4
from psycopg.sql import SQL,Literal
from . import case_fact_clarifications as facts,controlled_plans as cp
from .store import Conflict,Denied

SCOPE='OWNED_SYNTHETIC_BUSINESS_FRONTIER_V1'
TABLES=('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
        'service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events')
BIRTH='candidate_frontier_birth'
MARK='candidate_business_frontier'
ANCHORS='candidate_frontier_consumptions'
LIMIT=4096


def _birth_body(generation):
 return """
DECLARE anchor jsonb;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'frontier preparation deletion refused'; END IF;
 IF TG_OP='INSERT' THEN
  IF NEW.candidate_frontier_birth IS NOT NULL OR NEW.candidate_business_frontier IS NOT NULL OR NEW.candidate_frontier_consumptions IS NOT NULL THEN
   RAISE EXCEPTION 'only original frontier birth trigger may initialize'; END IF;
  NEW.candidate_frontier_birth:=jsonb_build_object('scope','OWNED_SYNTHETIC_BUSINESS_FRONTIER_V1','schema',1,
   'generation','%s','preparation_id',NEW.id::text,'case_id',NEW.case_id::text,'run_id',NEW.run_id::text,
   'owner_id',NEW.owner_id,'park_id',NEW.park_id,'org_id',NEW.org_id,'birth_xid',pg_current_xact_id()::text);
  NEW.candidate_business_frontier:=jsonb_build_object('schema',1,'generation','%s','epoch',0,'ever_started',false,'events','[]'::jsonb);
  NEW.candidate_frontier_consumptions:='[]'::jsonb;
  RETURN NEW;
 END IF;
 IF NEW.candidate_frontier_consumptions IS DISTINCT FROM OLD.candidate_frontier_consumptions THEN
  IF OLD.candidate_frontier_consumptions IS NULL OR NEW.candidate_frontier_consumptions IS NULL
   OR jsonb_typeof(NEW.candidate_frontier_consumptions) IS DISTINCT FROM 'array'
   OR jsonb_array_length(NEW.candidate_frontier_consumptions)<>jsonb_array_length(OLD.candidate_frontier_consumptions)+1
   OR jsonb_array_length(NEW.candidate_frontier_consumptions)>8
   OR (NEW.candidate_frontier_consumptions)-(jsonb_array_length(NEW.candidate_frontier_consumptions)-1) IS DISTINCT FROM OLD.candidate_frontier_consumptions
   OR NEW.candidate_business_frontier IS DISTINCT FROM OLD.candidate_business_frontier
   OR OLD.candidate_business_frontier->>'epoch' IS DISTINCT FROM '0'
   OR OLD.candidate_business_frontier->>'ever_started' IS DISTINCT FROM 'false' THEN
   RAISE EXCEPTION 'original zero-frontier immutable consumption required'; END IF;
  IF EXISTS(SELECT 1 FROM public.service_dispatches WHERE preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.service_dispatch_offers x JOIN public.service_dispatches d ON d.id=x.dispatch_id WHERE d.preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.service_dispatch_events x JOIN public.service_dispatches d ON d.id=x.dispatch_id WHERE d.preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.service_receipt_steps WHERE preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.service_step_receipts x JOIN public.service_receipt_steps d ON d.id=x.step_id WHERE d.preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.service_receipt_events x JOIN public.service_receipt_steps d ON d.id=x.step_id WHERE d.preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.case_local_lifecycles WHERE preparation_id=NEW.id)
   OR EXISTS(SELECT 1 FROM public.case_local_events WHERE preparation_id=NEW.id) THEN
   RAISE EXCEPTION 'actual complete empty eight-table frontier required'; END IF;
  anchor:=NEW.candidate_frontier_consumptions->-1;
  IF anchor->>'generation' IS DISTINCT FROM OLD.candidate_frontier_birth->>'generation'
   OR anchor->>'preparation_id' IS DISTINCT FROM NEW.id::text
   OR anchor->>'replacement_plan_id' IS DISTINCT FROM NEW.service_case_plan->>'id'
   OR anchor->'qualification'->'birth' IS DISTINCT FROM OLD.candidate_frontier_birth
   OR anchor->'qualification'->>'epoch' IS DISTINCT FROM '0'
   OR anchor->'qualification'->>'ever_started' IS DISTINCT FROM 'false' THEN
   RAISE EXCEPTION 'exact original zero qualification and current plan required'; END IF;
 END IF;
 IF NEW.candidate_frontier_birth IS DISTINCT FROM OLD.candidate_frontier_birth THEN
  RAISE EXCEPTION 'immutable original frontier birth'; END IF;
 IF NEW.candidate_business_frontier IS DISTINCT FROM OLD.candidate_business_frontier THEN
  IF OLD.candidate_business_frontier IS NULL OR NEW.candidate_business_frontier IS NULL
   OR jsonb_typeof(NEW.candidate_business_frontier) IS DISTINCT FROM 'object'
   OR NEW.candidate_business_frontier->>'schema' IS DISTINCT FROM '1'
   OR NEW.candidate_business_frontier->>'generation' IS DISTINCT FROM OLD.candidate_business_frontier->>'generation'
   OR (NEW.candidate_business_frontier->>'epoch')::integer IS DISTINCT FROM (OLD.candidate_business_frontier->>'epoch')::integer+1
   OR NEW.candidate_business_frontier->>'ever_started' IS DISTINCT FROM 'true'
   OR jsonb_typeof(NEW.candidate_business_frontier->'events') IS DISTINCT FROM 'array'
   OR jsonb_array_length(NEW.candidate_business_frontier->'events') IS DISTINCT FROM jsonb_array_length(OLD.candidate_business_frontier->'events')+1
   OR (NEW.candidate_business_frontier->'events')- (jsonb_array_length(NEW.candidate_business_frontier->'events')-1)
      IS DISTINCT FROM OLD.candidate_business_frontier->'events'
   OR jsonb_array_length(NEW.candidate_business_frontier->'events')>4096 THEN
   RAISE EXCEPTION 'irreversible append-only frontier required'; END IF;
 END IF;
 RETURN NEW;
END
"""%(generation,generation)


def _effect_body(oids):
 return """
DECLARE doc jsonb; parent_id uuid; ids uuid[]:='{}'; old_marker jsonb; n integer;
BEGIN
 IF NOT TG_RELID=ANY(ARRAY[%s]::oid[]) OR TG_TABLE_SCHEMA<>'public' OR TG_NAME<>'candidate_frontier_effect'
 THEN RAISE EXCEPTION 'original frontier effect origin required'; END IF;
 FOR doc IN SELECT value FROM jsonb_array_elements(CASE WHEN TG_OP='INSERT' THEN jsonb_build_array(to_jsonb(NEW))
  WHEN TG_OP='DELETE' THEN jsonb_build_array(to_jsonb(OLD)) ELSE jsonb_build_array(to_jsonb(OLD),to_jsonb(NEW)) END) LOOP
  IF TG_TABLE_NAME IN ('service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events') THEN
   parent_id:=(doc->>'preparation_id')::uuid;
  ELSIF TG_TABLE_NAME IN ('service_dispatch_offers','service_dispatch_events') THEN
   SELECT preparation_id INTO parent_id FROM public.service_dispatches WHERE id=(doc->>'dispatch_id')::uuid;
  ELSE
   SELECT preparation_id INTO parent_id FROM public.service_receipt_steps WHERE id=(doc->>'step_id')::uuid;
  END IF;
  IF parent_id IS NULL THEN RAISE EXCEPTION 'complete original frontier parent required'; END IF;
  ids:=array_append(ids,parent_id);
 END LOOP;
 FOR parent_id IN SELECT DISTINCT value FROM unnest(ids) value ORDER BY value LOOP
  SELECT candidate_business_frontier INTO old_marker FROM public.preparations WHERE id=parent_id FOR UPDATE;
  IF old_marker IS NULL THEN RAISE EXCEPTION 'original frontier birth missing'; END IF;
  n:=(old_marker->>'epoch')::integer;
  IF n>=4096 THEN RAISE EXCEPTION 'bounded frontier history exhausted'; END IF;
  UPDATE public.preparations SET candidate_business_frontier=jsonb_build_object('schema',1,
   'generation',old_marker->>'generation','epoch',n+1,'ever_started',true,
   'events',(old_marker->'events')||jsonb_build_array(jsonb_build_object('revision',n+1,'table',TG_TABLE_NAME,
    'operation',TG_OP,'record_id',coalesce(to_jsonb(NEW)->>'id',to_jsonb(OLD)->>'id',parent_id::text),
    'transaction',pg_current_xact_id()::text))) WHERE id=parent_id;
 END LOOP;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END
"""%(','.join(str(v) for v in oids))

TRUNCATE_BODY="BEGIN RAISE EXCEPTION 'frontier tracked relation TRUNCATE refused'; END"



CONSUMPTION_BODY="""
DECLARE anchor jsonb;
BEGIN
 anchor:=NEW.candidate_frontier_consumptions->-1;
 IF NOT EXISTS(SELECT 1 FROM public.case_resource_links l
  JOIN public.synthetic_resource_combination_receipts r ON r.request_key=l.request_key AND r.actor_id=l.actor_id AND r.combination_id=l.combination_id
  WHERE l.preparation_id=NEW.id AND l.owner_id=NEW.owner_id AND l.actor_id=NEW.owner_id
   AND l.request_key=anchor->>'request_key' AND l.fingerprint=anchor->>'fingerprint'
   AND l.combination_id::text=anchor->>'combination_id' AND l.revision=(anchor->>'link_revision')::integer
   AND r.fingerprint=l.fingerprint
   AND r.payload->'delivery_binding' IS NOT DISTINCT FROM l.snapshot->'delivery_binding'
   AND r.payload->'plan_approval' IS NOT DISTINCT FROM l.snapshot->'plan_approval'
   AND r.payload->'plan_approval'->>'id'=anchor->>'approval_id'
   AND r.payload->'delivery_binding'->'context'->'plan_replacement'->'compatibility'->'qualification'=anchor->'qualification'
   AND r.payload->'delivery_binding'->>'approved_plan_revision'=anchor->>'plan_revision') THEN
  RAISE EXCEPTION 'original frontier consumption must commit with actual approved delivery link and receipt'; END IF;
 RETURN NEW;
END
"""

class KnownNotStartedFrontier:
 def __init__(self,owner_store,fixture_proof,*,enabled_for_isolated_tests=False):
  if enabled_for_isolated_tests is not True or owner_store.mode!='LOCAL':raise Denied('explicit owned frontier installation required')
  self.owner,self.proof=owner_store,fixture_proof;self.generation=str(uuid4())
  with owner_store.connect() as c:
   self._owner(c)
   c.execute('LOCK TABLE preparations IN ACCESS EXCLUSIVE MODE')
   if c.execute('SELECT 1 FROM preparations LIMIT 1').fetchone():raise Denied('frontier installation must precede every preparation birth; no backfill')
   if c.execute("SELECT 1 FROM pg_attribute WHERE attrelid='preparations'::regclass AND attname=%s AND NOT attisdropped",(BIRTH,)).fetchone():raise Denied('frontier may be installed only once per issued generation')
   for table in TABLES:
    if c.execute(SQL('SELECT 1 FROM {} LIMIT 1').format(SQL(table))).fetchone():raise Denied('frontier installation requires original empty business relations')
   from .service_plan_approval import _install_schema
   _install_schema(c)
   self.endpoint=(c.info.host,c.info.port)
   self.oids=[c.execute('SELECT %s::regclass::oid value',('public.'+t,)).fetchone()['value'] for t in TABLES]
   c.execute('ALTER TABLE preparations ADD COLUMN candidate_frontier_birth jsonb, ADD COLUMN candidate_business_frontier jsonb, ADD COLUMN candidate_frontier_consumptions jsonb')
   for name,body in (('candidate_frontier_birth_guard',_birth_body(self.generation)),('candidate_frontier_effect_guard',_effect_body(self.oids)),('candidate_frontier_truncate_guard',TRUNCATE_BODY),('candidate_frontier_consumption_guard',CONSUMPTION_BODY)):
    c.execute(SQL('CREATE FUNCTION public.{}() RETURNS trigger LANGUAGE plpgsql AS {}').format(SQL(name),Literal(body)))
   c.execute('CREATE TRIGGER candidate_frontier_birth BEFORE INSERT OR UPDATE OR DELETE ON preparations FOR EACH ROW EXECUTE FUNCTION public.candidate_frontier_birth_guard()')
   c.execute('ALTER TABLE preparations ENABLE ALWAYS TRIGGER candidate_frontier_birth')
   for table in ('preparations',*TABLES):
    if table!='preparations':
     c.execute(SQL('CREATE TRIGGER candidate_frontier_effect BEFORE INSERT OR UPDATE OR DELETE ON {} FOR EACH ROW EXECUTE FUNCTION public.candidate_frontier_effect_guard()').format(SQL(table)))
     c.execute(SQL('ALTER TABLE {} ENABLE ALWAYS TRIGGER candidate_frontier_effect').format(SQL(table)))
    c.execute(SQL('CREATE TRIGGER candidate_frontier_truncate BEFORE TRUNCATE ON {} FOR EACH STATEMENT EXECUTE FUNCTION public.candidate_frontier_truncate_guard()').format(SQL(table)))
    c.execute(SQL('ALTER TABLE {} ENABLE ALWAYS TRIGGER candidate_frontier_truncate').format(SQL(table)))
   c.execute("CREATE CONSTRAINT TRIGGER candidate_frontier_consumption AFTER UPDATE ON preparations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (OLD.candidate_frontier_consumptions IS DISTINCT FROM NEW.candidate_frontier_consumptions) EXECUTE FUNCTION public.candidate_frontier_consumption_guard()")
   c.execute('ALTER TABLE preparations ENABLE ALWAYS TRIGGER candidate_frontier_consumption')
   self.schema=self._catalog(c);self.schema_sha256=cp._hash(self.schema)

 def _owner(self,c):
  p=self.proof
  if (type(p) is not facts.FixtureDatabaseEvidence or facts._fixture_databases.get(p.nonce) is not p
   or facts._fixture_clusters.get(p.cluster.nonce) is not p.cluster or getattr(self.owner,'_case_fact_fixture_receipt',None) is not p):raise Denied('issued original frontier fixture required')
  actual=facts._migration_identity(c);facts._same_cluster(p.cluster,actual)
  if (actual['database_oid']!=p.database_oid or actual['database_name']!=p.database_name
   or actual['session_name']!=p.cluster.owner or actual['owner_name']!=p.cluster.owner):raise Denied('original frontier fixture owner required')

 def _catalog(self,c):
  tables=['preparations',*TABLES]
  structures=c.execute("""SELECT r.oid,n.nspname,r.relname,r.relowner,r.relkind,r.relispartition,r.relhassubclass,
   EXISTS(SELECT 1 FROM pg_inherits i WHERE i.inhrelid=r.oid OR i.inhparent=r.oid) inheritance
   FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace
   WHERE r.oid=ANY(%s::regclass[]) ORDER BY r.oid""",(['public.'+t for t in tables],)).fetchall()
  if len(structures)!=9 or any(r['nspname']!='public' or r['relkind']!='r' or r['relispartition'] or r['relhassubclass'] or r['inheritance'] for r in structures):
   raise Denied('original plain noninherited frontier relations required')
  rows=c.execute("""SELECT t.oid,t.xmin::text epoch,t.tgisinternal,t.tgname,t.tgenabled,t.tgtype,t.tgrelid,t.tgfoid,
   pg_get_triggerdef(t.oid) definition,f.xmin::text function_epoch,f.proowner,f.prosrc,f.prosecdef,f.proconfig,
   n.nspname function_namespace,l.lanname,r.relowner,pg_get_userbyid(r.relowner) owner
   FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid JOIN pg_namespace n ON n.oid=f.pronamespace
   JOIN pg_language l ON l.oid=f.prolang JOIN pg_class r ON r.oid=t.tgrelid
   WHERE t.tgrelid=ANY(%s::regclass[]) ORDER BY t.tgrelid,t.tgname""",(['public.'+t for t in tables],)).fetchall()
  frontier=[r for r in rows if r['tgname'].startswith('candidate_frontier_')]
  if len(frontier)!=19 or any(r['tgenabled']!='A' or r['prosecdef'] or r['proconfig'] is not None
   or r['proowner']!=r['relowner'] or r['owner']!=self.proof.cluster.owner or r['function_namespace']!='public' or r['lanname']!='plpgsql' for r in frontier):raise Denied('complete original ALWAYS frontier trigger schema required')
  constraints=c.execute('SELECT oid,xmin::text epoch,conrelid,confrelid,conname,pg_get_constraintdef(oid) definition FROM pg_constraint WHERE conrelid=ANY(%s::regclass[]) ORDER BY oid',(['public.'+t for t in tables],)).fetchall()
  return cp._normal(dict(structures=structures,triggers=rows,constraints=constraints))

 def check(self,c):
  identity=c.execute('SELECT oid,datname,pg_postmaster_start_time() started FROM pg_database WHERE datname=current_database()').fetchone()
  if ((c.info.host,c.info.port)!=self.endpoint or identity['oid']!=self.proof.database_oid
   or identity['datname']!=self.proof.database_name or identity['started']!=self.proof.cluster.postmaster_start):raise Denied('same issued frontier connection required')
  if c.execute('SHOW session_replication_role').fetchone()['session_replication_role']!='origin':raise Denied('original frontier replication role required')
  if self._catalog(c)!=self.schema:raise Denied('frontier DDL epoch or definition changed; issued continuity lost')

 def birth(self,c,parent):
  self.check(c)
  row=c.execute('SELECT candidate_frontier_birth,candidate_business_frontier FROM preparations WHERE id=%s',(parent['id'],)).fetchone()
  birth=row[BIRTH];mark=row[MARK]
  keys={'scope','schema','generation','preparation_id','case_id','run_id','owner_id','park_id','org_id','birth_xid'}
  if (type(birth) is not dict or set(birth)!=keys or birth['scope']!=SCOPE or birth['schema']!=1 or birth['generation']!=self.generation
   or any(birth[a]!=str(parent[b]) for a,b in (('preparation_id','id'),('case_id','case_id'),('run_id','run_id'),('owner_id','owner_id'),('park_id','park_id'),('org_id','org_id')))
   or type(mark) is not dict or set(mark)!={'schema','generation','epoch','ever_started','events'}
   or mark['schema']!=1 or mark['generation']!=self.generation or type(mark['epoch']) is not int or not 0<=mark['epoch']<=LIMIT
   or type(mark['ever_started']) is not bool or type(mark['events']) is not list or len(mark['events'])!=mark['epoch']
   or mark['ever_started']!=(mark['epoch']>0)):
   raise Conflict('original tracked frontier birth and monotonic history required')
  return birth,mark

 def qualify(self,c,parent,previous,*,historical=False,consumption_key=None):
  birth,mark=self.birth(c,parent)
  if not historical and (mark['epoch']!=0 or mark['ever_started']):raise Conflict('original business frontier has already started')
  from .case_goal_results import verification
  proofs=[]
  for step in previous['steps'][:2]:
   event=verification(parent,previous,step)
   if step['coordination_state']!='VERIFIED' or not event:raise Conflict('original P1/P2 verified frontier required')
   proofs.append(dict(adapter_id=step['adapter_id'],step_id=step['id'],event_id=event['id'],event_revision=event['revision'],source_sha256=event['source_sha256'],event_sha256=cp._hash(event)))
  if any(e['action'] not in ('ADOPT',) and e.get('step_id') in {s['id'] for s in previous['steps'][2:]} for e in previous['events']):raise Conflict('old business tail has coordination activity')
  if historical:
   rows=c.execute('SELECT candidate_frontier_consumptions FROM preparations WHERE id=%s',(parent['id'],)).fetchone()[ANCHORS]
   matches=[row for row in rows if row.get('request_key')==consumption_key] if type(rows) is list else []
   if len(matches)!=1:raise Conflict('original immutable zero-frontier consumption anchor required')
   saved=matches[0];q=saved.get('qualification')
   if (saved.get('generation')!=self.generation or saved.get('previous_plan_id')!=previous['id']
    or type(q) is not dict or q.get('birth')!=birth or q.get('protocol_sha256')!=self.schema_sha256
    or q.get('verified_prefix')!=proofs or saved.get('qualification_sha256')!=cp._hash(q)):
    raise Conflict('original immutable frontier qualification changed')
   return q
  collections=[]
  for table in TABLES:
   if table in ('service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events'):query='SELECT 1 FROM '+table+' WHERE preparation_id=%s LIMIT 1'
   elif table in ('service_dispatch_offers','service_dispatch_events'):query='SELECT 1 FROM '+table+' x JOIN service_dispatches d ON d.id=x.dispatch_id WHERE d.preparation_id=%s LIMIT 1'
   else:query='SELECT 1 FROM '+table+' x JOIN service_receipt_steps s ON s.id=x.step_id WHERE s.preparation_id=%s LIMIT 1'
   found=c.execute(query,(parent['id'],)).fetchone()
   if not historical and found:raise Conflict('complete original empty business history required')
   collections.append(dict(table=table,count=0,complete=True,known=True,sha256=cp._hash([])))
  return dict(schema=1,profile='KNOWN_NOT_STARTED_V1',state='KNOWN_NOT_STARTED',preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
   previous_plan_id=previous['id'],birth=birth,birth_sha256=cp._hash(birth),protocol_sha256=self.schema_sha256,epoch=0,ever_started=False,
   collection_bound=1,collections=collections,verified_prefix=proofs,tail=dict(P3='NEVER_DISPATCHED_OR_ACCEPTED',P4='NO_RECEIPT_EFFECT',P5='NO_LOCAL_LIFECYCLE_EFFECT'))

 def attach_store(self,store):
  with store.connect() as c:self.check(c)
  store._known_not_started_frontier=self
  return store


def current(c,parent):
 store=getattr(c,'_access_store',None);protocol=getattr(store,'_known_not_started_frontier',None)
 if parent.get(BIRTH) is None:return None
 if type(protocol) is not KnownNotStartedFrontier:raise Denied('issued frontier protocol must remain attached')
 row=c.execute('SELECT * FROM preparations WHERE id=%s',(parent['id'],)).fetchone()
 _,mark=protocol.birth(c,row);plan=row.get('service_case_plan')
 if not plan:return None
 return dict(generation=protocol.generation,preparation_id=str(row['id']),plan_id=plan['id'],plan_revision=plan['revision'],epoch=mark['epoch'])


def view(c,parent):
 if parent is None:return {}
 value=current(c,parent)
 return {'business_frontier':value} if parent.get(BIRTH) is not None else {}


def check_fence(c,parent,data):
 expected=getattr(data,'expected_business_frontier',None)
 if parent.get(BIRTH) is None:
  if expected is not None:raise Conflict('untracked original Case cannot claim frontier fence')
  return
 actual=current(c,parent)
 if expected is None or expected.model_dump(mode='json')!=actual:raise Conflict('captured original business frontier changed; fresh original GET required')
 c._business_frontier_write_fence=expected.model_dump(mode='json')


def event_fence(c):
 value=getattr(c,'_business_frontier_write_fence',None)
 return {'expected_business_frontier':value} if value is not None else {}

QUALIFICATION_KEYS={'schema','profile','state','preparation_id','case_id','run_id','previous_plan_id','birth','birth_sha256',
 'protocol_sha256','epoch','ever_started','collection_bound','collections','verified_prefix','tail'}

def validate_qualification(q,data,context):
 import re
 if (type(q) is not dict or set(q)!=QUALIFICATION_KEYS or type(q['schema']) is not int or q['schema']!=1
  or q['profile']!='KNOWN_NOT_STARTED_V1' or q['state']!='KNOWN_NOT_STARTED'
  or q['previous_plan_id']!=str(data.expected_previous_plan_id) or type(q['epoch']) is not int or q['epoch']!=0
  or q['ever_started'] is not False or type(q['collection_bound']) is not int or q['collection_bound']!=1
  or any(q[k]!=context[k] for k in ('preparation_id','case_id','run_id'))):raise ValueError('strict known-not-started qualification required')
 b=q['birth'];keys={'scope','schema','generation','preparation_id','case_id','run_id','owner_id','park_id','org_id','birth_xid'}
 if (type(b) is not dict or set(b)!=keys or b['scope']!=SCOPE or type(b['schema']) is not int or b['schema']!=1
  or any(b[k]!=context[k] for k in ('preparation_id','case_id','run_id','owner_id','park_id','org_id'))
  or type(b['birth_xid']) is not str or re.fullmatch('[0-9]{1,24}',b['birth_xid']) is None or q['birth_sha256']!=cp._hash(b)):
  raise ValueError('original independent frontier birth required')
 UUID(b['generation'])
 for key in ('birth_sha256','protocol_sha256'):
  if type(q[key]) is not str or re.fullmatch('[a-f0-9]{64}',q[key]) is None:raise ValueError('frontier digest required')
 if type(q['collections']) is not list or len(q['collections'])!=8:raise ValueError('complete eight frontier collections required')
 for table,item in zip(TABLES,q['collections']):
  if (type(item) is not dict or set(item)!={'table','count','complete','known','sha256'} or item['table']!=table
   or type(item['count']) is not int or item['count']!=0 or item['complete'] is not True or item['known'] is not True
   or item['sha256']!=cp._hash([])):raise ValueError('complete original empty frontier collection required')
 if type(q['verified_prefix']) is not list or len(q['verified_prefix'])!=2:raise ValueError('original two verified steps required')
 for adapter,item in zip(('P1','P2'),q['verified_prefix']):
  if (type(item) is not dict or set(item)!={'adapter_id','step_id','event_id','event_revision','source_sha256','event_sha256'}
   or item['adapter_id']!=adapter or type(item['event_revision']) is not int or not 1<=item['event_revision']<=64):raise ValueError('original frontier event required')
  UUID(item['step_id']);UUID(item['event_id'])
  if any(type(item[k]) is not str or re.fullmatch('[a-f0-9]{64}',item[k]) is None for k in ('source_sha256','event_sha256')):raise ValueError('frontier original event digest required')
 if q['tail']!={'P3':'NEVER_DISPATCHED_OR_ACCEPTED','P4':'NO_RECEIPT_EFFECT','P5':'NO_LOCAL_LIFECYCLE_EFFECT'}:raise ValueError('finite unstarted frontier required')


def record_consumption(store,c,parent,data,key,fp,receipt,proof):
 if data.replacement_frontier_profile is None:return
 protocol=getattr(store,'_known_not_started_frontier',None)
 if type(protocol) is not KnownNotStartedFrontier:raise Denied('original frontier consumption protocol required')
 q=proof['context']['plan_replacement']['compatibility']['qualification']
 assert_live_qualification(protocol,c,parent,data,q)
 saved=dict(schema=1,generation=protocol.generation,preparation_id=str(parent['id']),previous_plan_id=str(data.expected_previous_plan_id),
  replacement_plan_id=proof['context']['plan_id'],plan_revision=data.expected_plan_revision,request_key=key,fingerprint=fp,
  combination_id=receipt['combination_id'],link_revision=data.expected_link_revision+1,approval_id=receipt['plan_approval']['id'],
  qualification=q,qualification_sha256=cp._hash(q))
 from psycopg.types.json import Jsonb
 c.execute('UPDATE preparations SET candidate_frontier_consumptions=candidate_frontier_consumptions||%s WHERE id=%s',
  (Jsonb([saved]),parent['id']))


def assert_live_qualification(protocol,c,parent,data,expected):
 # Parent UPDATE is already held by original delivery. Recheck after every
 # blocking comparison and immediately before the actual zero-time anchor.
 plans=[*parent['service_case_plan'].get('history',[]),parent['service_case_plan']]
 previous=[x for x in plans if x['id']==str(data.expected_previous_plan_id)]
 if len(previous)!=1 or protocol.qualify(c,parent,previous[0])!=expected:
  raise Conflict('original zero-frontier qualification changed before consumption')


def final_consumption_check(store,c,parent,data,proof):
 if data.replacement_frontier_profile is None:return
 protocol=getattr(store,'_known_not_started_frontier',None)
 if type(protocol) is not KnownNotStartedFrontier:raise Denied('original frontier consumption protocol required')
 assert_live_qualification(protocol,c,parent,data,proof['context']['plan_replacement']['compatibility']['qualification'])
