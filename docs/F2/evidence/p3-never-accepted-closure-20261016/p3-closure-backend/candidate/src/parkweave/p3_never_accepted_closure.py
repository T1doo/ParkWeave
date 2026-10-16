"""Finite original never-accepted dispatch closure; no reset or new authority."""
import re
from uuid import UUID,uuid4
from psycopg.sql import SQL,Literal
from psycopg.types.json import Jsonb
from . import business_frontier as bf,controlled_plans as cp
from .business_frontier_types import historical_fields,request
from .store import Conflict,Denied

PROFILE='P3_NEVER_ACCEPTED_CLOSED_V1'
COMPATIBILITY='ORIGINAL_V4_SERVICE_RELEASE_P3_NEVER_ACCEPTED_CLOSED_V1'
COLUMN='candidate_p3_closure_consumptions'
QUALIFICATION_KEYS=bf.QUALIFICATION_KEYS|{'closure_state','dispatch','marker_sha256'}
DISPATCH_KEYS={'id','revision','current_offer_id','state','offers_count','events_count','history_sha256','events'}
EVENT_KEYS={'id','revision','action','offer_id','actor_id','request_key','fingerprint','payload_sha256','transaction','business_frontier'}


def _select(table):
 if table in ('service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events'):
  source='public.'+table+' t WHERE t.preparation_id=$1'
 elif table in ('service_dispatch_offers','service_dispatch_events'):
  source='public.'+table+' t JOIN public.service_dispatches d ON d.id=t.dispatch_id WHERE d.preparation_id=$1'
 else:source='public.'+table+' t JOIN public.service_receipt_steps d ON d.id=t.step_id WHERE d.preparation_id=$1'
 value="to_jsonb(t)||jsonb_build_object('_transaction',t.xmin::text)" if table=='service_dispatch_events' else 'to_jsonb(t)'
 order='t.revision,t.id' if table=='service_dispatch_events' else ('t.preparation_id' if table=='case_local_lifecycles' else 't.id')
 return 'SELECT coalesce(jsonb_agg(value),\'[]\'::jsonb) FROM (SELECT '+value+' value FROM '+source+' ORDER BY '+order+' LIMIT 65) records'


def _guard():
 checks='\n'.join("EXECUTE %s INTO actual USING NEW.id; IF jsonb_array_length(actual)>64 OR anchor->'snapshot'->%s IS DISTINCT FROM actual THEN RAISE EXCEPTION 'complete original closure collection changed'; END IF;"%(Literal(_select(t)).as_string(),Literal(t).as_string()) for t in bf.TABLES)
 return """
DECLARE anchor jsonb; actual jsonb; roots jsonb; offers jsonb; events jsonb; root jsonb; offer jsonb; event jsonb; mark jsonb; expected_mark jsonb:='[]'::jsonb; item jsonb; payload jsonb; previous_offer text; action text; state text; actor text; tx text; op text; n integer; rev integer; count_offers integer;
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.candidate_p3_closure_consumptions IS NOT NULL THEN RAISE EXCEPTION 'original closure birth only'; END IF;
  NEW.candidate_p3_closure_consumptions:='[]'::jsonb; RETURN NEW;
 END IF;
 IF NEW.candidate_p3_closure_consumptions IS NOT DISTINCT FROM OLD.candidate_p3_closure_consumptions THEN RETURN NEW; END IF;
 IF OLD.candidate_p3_closure_consumptions IS NULL OR NEW.candidate_p3_closure_consumptions IS NULL
  OR jsonb_typeof(NEW.candidate_p3_closure_consumptions) IS DISTINCT FROM 'array'
  OR jsonb_array_length(NEW.candidate_p3_closure_consumptions)<>jsonb_array_length(OLD.candidate_p3_closure_consumptions)+1
  OR jsonb_array_length(NEW.candidate_p3_closure_consumptions)>8
  OR NEW.candidate_p3_closure_consumptions-(jsonb_array_length(NEW.candidate_p3_closure_consumptions)-1) IS DISTINCT FROM OLD.candidate_p3_closure_consumptions
  OR NEW.candidate_business_frontier IS DISTINCT FROM OLD.candidate_business_frontier
  OR (OLD.candidate_business_frontier->>'epoch')::int<=0 THEN RAISE EXCEPTION 'original append-only closure consumption required'; END IF;
 anchor:=NEW.candidate_p3_closure_consumptions->-1;
 IF anchor->>'generation' IS DISTINCT FROM OLD.candidate_frontier_birth->>'generation'
  OR anchor->>'preparation_id' IS DISTINCT FROM NEW.id::text
  OR anchor->>'replacement_plan_id' IS DISTINCT FROM NEW.service_case_plan->>'id'
  OR anchor->'snapshot'->'marker' IS DISTINCT FROM OLD.candidate_business_frontier
  OR anchor->'qualification'->'birth' IS DISTINCT FROM OLD.candidate_frontier_birth
  OR anchor->'qualification'->>'epoch' IS DISTINCT FROM OLD.candidate_business_frontier->>'epoch'
  OR anchor->'qualification'->>'ever_started' IS DISTINCT FROM 'true' THEN RAISE EXCEPTION 'actual original closed frontier required'; END IF;
 %s
 roots:=anchor->'snapshot'->'service_dispatches'; offers:=anchor->'snapshot'->'service_dispatch_offers'; events:=anchor->'snapshot'->'service_dispatch_events'; mark:=anchor->'snapshot'->'marker';
 IF jsonb_array_length(roots)<>1 THEN RAISE EXCEPTION 'one actual closed dispatch required'; END IF;
 root:=roots->0; rev:=(root->>'revision')::int; count_offers:=jsonb_array_length(offers);
 IF rev<2 OR rev>62 OR rev%%2<>0 OR count_offers<>rev/2 OR jsonb_array_length(events)<>rev
  OR (mark->>'epoch')::int<>3*rev OR mark->>'ever_started' IS DISTINCT FROM 'true'
  OR root->>'preparation_id' IS DISTINCT FROM NEW.id::text
  OR anchor->'qualification'->>'profile' IS DISTINCT FROM 'P3_NEVER_ACCEPTED_CLOSED_V1'
  OR anchor->'qualification'->>'state' IS DISTINCT FROM 'CLOSED_WITHOUT_ACCEPTANCE' THEN RAISE EXCEPTION 'bounded original closed dispatch required'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(offers) x WHERE x->>'dispatch_id' IS DISTINCT FROM root->>'id' OR x->>'state' NOT IN ('DECLINED','WITHDRAWN') OR x->'receipt_step_id' IS DISTINCT FROM 'null'::jsonb)
 THEN RAISE EXCEPTION 'no historical acceptance or receipt pointer required'; END IF;
 FOR n IN 1..rev LOOP
  event:=events->(n-1); action:=event->>'action'; payload:=event->'payload'; tx:=event->>'_transaction';
  SELECT x INTO offer FROM jsonb_array_elements(offers) x WHERE x->>'id'=event->>'offer_id';
  IF offer IS NULL OR (event->>'revision')::int<>n OR event->>'dispatch_id' IS DISTINCT FROM root->>'id' OR action='ACCEPT'
   OR tx IS NULL OR tx !~ '^[0-9]{1,24}$' THEN RAISE EXCEPTION 'complete native original event sequence required'; END IF;
  IF n%%2=1 THEN
   IF action IS DISTINCT FROM (CASE WHEN n=1 THEN 'OFFER' ELSE 'REOFFER' END)
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(events) WITH ORDINALITY x(value,ord) WHERE ord<n AND (value->>'revision')::int%%2=1 AND value->>'offer_id'=offer->>'id')
   THEN RAISE EXCEPTION 'unique original offer sequence required'; END IF;
   state:='OFFERED'; actor:=NEW.reviewer_id; previous_offer:=offer->>'id';
   expected_mark:=expected_mark||jsonb_build_array(jsonb_build_object('revision',jsonb_array_length(expected_mark)+1,'table','service_dispatches','operation',CASE WHEN n=1 THEN 'INSERT' ELSE 'UPDATE' END,'record_id',root->>'id','transaction',tx));
   expected_mark:=expected_mark||jsonb_build_array(jsonb_build_object('revision',jsonb_array_length(expected_mark)+1,'table','service_dispatch_offers','operation','INSERT','record_id',offer->>'id','transaction',tx));
   IF payload->>'reason' IS DISTINCT FROM offer->>'reason' THEN RAISE EXCEPTION 'original offer reason required'; END IF;
  ELSE
   IF action NOT IN ('DECLINE','WITHDRAW') OR offer->>'id' IS DISTINCT FROM previous_offer THEN RAISE EXCEPTION 'explicit original terminal decision required'; END IF;
   state:=CASE WHEN action='DECLINE' THEN 'DECLINED' ELSE 'WITHDRAWN' END;
   actor:=CASE WHEN action='DECLINE' THEN offer->>'executor_id' ELSE NEW.reviewer_id END;
   IF offer->>'state' IS DISTINCT FROM state THEN RAISE EXCEPTION 'exact terminal offer state required'; END IF;
   expected_mark:=expected_mark||jsonb_build_array(jsonb_build_object('revision',jsonb_array_length(expected_mark)+1,'table','service_dispatch_offers','operation','UPDATE','record_id',offer->>'id','transaction',tx));
   expected_mark:=expected_mark||jsonb_build_array(jsonb_build_object('revision',jsonb_array_length(expected_mark)+1,'table','service_dispatches','operation','UPDATE','record_id',root->>'id','transaction',tx));
  END IF;
  expected_mark:=expected_mark||jsonb_build_array(jsonb_build_object('revision',jsonb_array_length(expected_mark)+1,'table','service_dispatch_events','operation','INSERT','record_id',event->>'id','transaction',tx));
  item:=jsonb_build_object('dispatch_id',root->>'id','offer_id',offer->>'id','revision',n,'action',action,'state',state,'actor_id',actor,'executor_id',offer->>'executor_id','reason',payload->>'reason','receipt_step_id',NULL,'expected_business_frontier',jsonb_build_object('generation',OLD.candidate_frontier_birth->>'generation','preparation_id',NEW.id::text,'plan_id',anchor->>'previous_plan_id','plan_revision',(anchor->'qualification'->'verified_prefix'->1->>'event_revision')::int,'epoch',3*(n-1)));
  IF event->>'actor_id' IS DISTINCT FROM actor OR payload IS DISTINCT FROM item THEN RAISE EXCEPTION 'exact native event actor payload and captured fence required'; END IF;
 END LOOP;
 IF root->>'current_offer_id' IS DISTINCT FROM previous_offer OR mark->'events' IS DISTINCT FROM expected_mark
  OR anchor->'qualification'->>'closure_state' IS DISTINCT FROM state
  OR anchor->'qualification'->'dispatch'->>'state' IS DISTINCT FROM state
  OR anchor->'qualification'->'dispatch'->>'id' IS DISTINCT FROM root->>'id'
  OR anchor->'qualification'->'dispatch'->>'revision' IS DISTINCT FROM root->>'revision' THEN RAISE EXCEPTION 'independent native closed history and marker required'; END IF;
 IF EXISTS(SELECT 1 FROM public.service_receipt_steps WHERE preparation_id=NEW.id)
  OR EXISTS(SELECT 1 FROM public.case_local_lifecycles WHERE preparation_id=NEW.id)
  OR EXISTS(SELECT 1 FROM public.case_local_events WHERE preparation_id=NEW.id) THEN RAISE EXCEPTION 'no original P4/P5 effect required'; END IF;
 RETURN NEW;
END
"""%checks


class P3NeverAcceptedClosure:
 def __init__(self,owner_store,fixture_proof,*,enabled_for_isolated_tests=False):
  if enabled_for_isolated_tests is not True or owner_store.mode!='LOCAL':raise Denied('explicit owned closure installation required')
  frontier=bf.KnownNotStartedFrontier.__new__(bf.KnownNotStartedFrontier)
  frontier.owner,frontier.proof,frontier.generation=owner_store,fixture_proof,str(uuid4())
  self.frontier=frontier
  with owner_store.connect() as c:
   # Both schemas are issued once, atomically before every preparation birth.
   frontier._install(c)
   c.execute('ALTER TABLE preparations ADD COLUMN candidate_p3_closure_consumptions jsonb')
   for name,body in (('candidate_p3closure_guard',_guard()),('candidate_p3closure_consumption_guard',bf.CONSUMPTION_BODY.replace('candidate_frontier_consumptions',COLUMN))):
    c.execute(SQL('CREATE FUNCTION public.{}() RETURNS trigger LANGUAGE plpgsql AS {}').format(SQL(name),Literal(body)))
   c.execute('CREATE TRIGGER candidate_p3closure_anchor BEFORE INSERT OR UPDATE ON preparations FOR EACH ROW EXECUTE FUNCTION public.candidate_p3closure_guard()')
   c.execute('ALTER TABLE preparations ENABLE ALWAYS TRIGGER candidate_p3closure_anchor')
   c.execute('CREATE CONSTRAINT TRIGGER candidate_p3closure_consumption AFTER UPDATE ON preparations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (OLD.candidate_p3_closure_consumptions IS DISTINCT FROM NEW.candidate_p3_closure_consumptions) EXECUTE FUNCTION public.candidate_p3closure_consumption_guard()')
   c.execute('ALTER TABLE preparations ENABLE ALWAYS TRIGGER candidate_p3closure_consumption')
   frontier.schema=frontier._catalog(c);frontier.schema_sha256=cp._hash(frontier.schema)

 def attach_store(self,store):
  self.frontier.attach_store(store);store._p3_closure_frontier=self;return store

 def _snapshot(self,c,parent):
  result={}
  for t in bf.TABLES:
   query=_select(t).replace('$1','%s')
   result[t]=next(iter(c.execute(query,(parent['id'],)).fetchone().values()))
   if len(result[t])>64:raise Conflict('complete bounded original closure history required')
  _,result['marker']=self.frontier.birth(c,parent)
  return result

 def _prefix(self,parent,previous):
  from .case_goal_results import verification
  result=[]
  for step in previous['steps'][:2]:
   event=verification(parent,previous,step)
   if step['coordination_state']!='VERIFIED' or not event:raise Conflict('original verified P1/P2 closure prefix required')
   result.append(dict(adapter_id=step['adapter_id'],step_id=step['id'],event_id=event['id'],event_revision=event['revision'],source_sha256=event['source_sha256'],event_sha256=cp._hash(event)))
  if any(e['action']!='ADOPT' and e.get('step_id') in {s['id'] for s in previous['steps'][2:]} for e in previous['events']):raise Conflict('old tail coordination activity is unsupported')
  return result

 def _replay(self,parent,previous,birth,snapshot,prefix):
  from . import service_dispatches as sd
  try:
   mark=snapshot['marker'];roots=snapshot[bf.TABLES[0]];offers=snapshot[bf.TABLES[1]];events=snapshot[bf.TABLES[2]]
   if (len(roots)!=1 or any(snapshot[t] for t in bf.TABLES[3:]) or not mark['ever_started']):raise ValueError()
   root=roots[0];rev=root['revision']
   if (type(rev) is not int or not 2<=rev<=62 or rev%2 or len(events)!=rev or len(offers)!=rev//2
    or mark['epoch']!=3*rev or len(mark['events'])!=mark['epoch'] or root['preparation_id']!=str(parent['id'])):raise ValueError()
   by_offer={o['id']:o for o in offers};seen=set();summary=[];expected_marker=[];last=None
   material=previous['steps'][1]['verified_sources']
   for index,e in enumerate(events):
    n=index+1;action=e['action'];offer=by_offer[e['offer_id']];payload=e['payload'];terminal=n%2==0
    if (e['revision']!=n or e['dispatch_id']!=root['id'] or offer['dispatch_id']!=root['id']
     or offer['receipt_step_id'] is not None or offer['preparation_revision']!=material['preparation_revision']
     or offer['preparation_sha256']!=material['preparation_sha256'] or not re.fullmatch('[A-Za-z0-9_-]{1,100}',e['request_key'])):raise ValueError()
    fence=historical_fields(payload)['expected_business_frontier']
    expected_fence=dict(generation=birth['generation'],preparation_id=str(parent['id']),plan_id=previous['id'],plan_revision=prefix[1]['event_revision'],epoch=3*index)
    if fence!=expected_fence:raise ValueError()
    if terminal:
     if action not in ('DECLINE','WITHDRAW') or last!=offer['id']:raise ValueError()
     state={'DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[action]
     actor=offer['executor_id'] if action=='DECLINE' else parent['reviewer_id']
     body=sd.Command(action=action,expected_revision=n-1,reason=payload['reason'],expected_business_frontier=fence)
     fp=cp._hash(dict(dispatch_id=root['id'],**request(body)))
     operations=[('service_dispatch_offers','UPDATE',offer['id']),('service_dispatches','UPDATE',root['id'])]
     if offer['state']!=state:raise ValueError()
    else:
     if action!=('OFFER' if n==1 else 'REOFFER') or offer['id'] in seen:raise ValueError()
     seen.add(offer['id']);last=offer['id'];state='OFFERED';actor=parent['reviewer_id']
     body=sd.Offer(expected_preparation_revision=offer['preparation_revision'],expected_dispatch_revision=n-1,executor_id=offer['executor_id'],reason=offer['reason'],expected_business_frontier=fence)
     raw=request(body);raw.pop('recovery_receipt_step_id')
     fp=cp._hash(dict(preparation_id=str(parent['id']),**raw))
     if payload['reason']!=offer['reason']:raise ValueError()
     operations=[('service_dispatches','INSERT' if n==1 else 'UPDATE',root['id']),('service_dispatch_offers','INSERT',offer['id'])]
    want=dict(dispatch_id=root['id'],offer_id=offer['id'],revision=n,action=action,state=state,actor_id=actor,executor_id=offer['executor_id'],reason=body.reason,receipt_step_id=None,expected_business_frontier=fence)
    if payload!=want or e['actor_id']!=actor or e['fingerprint']!=fp:raise ValueError()
    tx=e['_transaction']
    if not re.fullmatch('[0-9]{1,24}',tx):raise ValueError()
    operations.append(('service_dispatch_events','INSERT',e['id']))
    for table,op,record_id in operations:expected_marker.append(dict(revision=len(expected_marker)+1,table=table,operation=op,record_id=record_id,transaction=tx))
    summary.append(dict(id=e['id'],revision=n,action=action,offer_id=offer['id'],actor_id=actor,request_key=e['request_key'],fingerprint=fp,payload_sha256=cp._hash(payload),transaction=tx,business_frontier=fence))
   if (seen!=set(by_offer) or root['current_offer_id']!=last or mark['events']!=expected_marker
    or len({e['id'] for e in events})!=rev):raise ValueError()
   closed=by_offer[last]['state']
   return dict(id=root['id'],revision=rev,current_offer_id=last,state=closed,offers_count=len(offers),events_count=len(events),history_sha256=cp._hash(snapshot),events=summary)
  except (KeyError,TypeError,ValueError):raise Conflict('UNKNOWN: exact original never-accepted closed P3 history required') from None

 def qualify(self,c,parent,previous,*,historical=False,consumption_key=None):
  birth,mark=self.frontier.birth(c,parent);prefix=self._prefix(parent,previous)
  if historical:
   rows=c.execute('SELECT candidate_p3_closure_consumptions FROM preparations WHERE id=%s',(parent['id'],)).fetchone()[COLUMN]
   matches=[x for x in rows if x.get('request_key')==consumption_key] if type(rows) is list else []
   if len(matches)!=1:raise Conflict('original immutable P3 closure consumption required')
   saved=matches[0];snapshot=saved.get('snapshot');q=saved.get('qualification')
   if (type(snapshot) is not dict or set(snapshot)!=set(bf.TABLES)|{'marker'} or type(q) is not dict
    or saved.get('previous_plan_id')!=previous['id'] or saved.get('generation')!=birth['generation']
    or saved.get('qualification_sha256')!=cp._hash(q) or q.get('protocol_sha256')!=self.frontier.schema_sha256
    or mark['events'][:snapshot['marker']['epoch']]!=snapshot['marker']['events']):raise Conflict('original closure prefix anchor changed')
  else:snapshot=self._snapshot(c,parent)
  dispatch=self._replay(parent,previous,birth,snapshot,prefix)
  collections=[dict(table=t,count=len(snapshot[t]),complete=True,known=True,sha256=cp._hash(snapshot[t])) for t in bf.TABLES]
  result=dict(schema=1,profile=PROFILE,state='CLOSED_WITHOUT_ACCEPTANCE',preparation_id=str(parent['id']),case_id=str(parent['case_id']),run_id=str(parent['run_id']),previous_plan_id=previous['id'],birth=birth,birth_sha256=cp._hash(birth),protocol_sha256=self.frontier.schema_sha256,epoch=snapshot['marker']['epoch'],ever_started=True,collection_bound=64,collections=collections,verified_prefix=prefix,tail=dict(P3='CLOSED_WITHOUT_ACCEPTANCE',P4='NO_RECEIPT_EFFECT',P5='NO_LOCAL_LIFECYCLE_EFFECT'),closure_state=dispatch['state'],dispatch=dispatch,marker_sha256=cp._hash(snapshot['marker']))
  if historical and result!=q:raise Conflict('original native closure qualification changed')
  return result


def _protocol(store):
 value=getattr(store,'_p3_closure_frontier',None)
 if type(value) is not P3NeverAcceptedClosure or getattr(store,'_known_not_started_frontier',None) is not value.frontier:raise Denied('explicit original P3 closure scope required')
 return value


def assert_live(store,c,parent,data,expected):
 protocol=_protocol(store);plans=[*parent['service_case_plan'].get('history',[]),parent['service_case_plan']]
 old=[p for p in plans if p['id']==str(data.expected_previous_plan_id)]
 if len(old)!=1 or protocol.qualify(c,parent,old[0])!=expected:raise Conflict('original P3 closure changed before consumption')
 return protocol


def record_consumption(store,c,parent,data,key,fp,receipt,proof):
 q=proof['context']['plan_replacement']['compatibility']['qualification'];protocol=assert_live(store,c,parent,data,q)
 snapshot=protocol._snapshot(c,parent)
 if cp._hash(snapshot)!=q['dispatch']['history_sha256']:raise Conflict('actual closure history changed')
 saved=dict(schema=1,generation=protocol.frontier.generation,preparation_id=str(parent['id']),previous_plan_id=str(data.expected_previous_plan_id),replacement_plan_id=proof['context']['plan_id'],plan_revision=data.expected_plan_revision,request_key=key,fingerprint=fp,combination_id=receipt['combination_id'],link_revision=data.expected_link_revision+1,approval_id=receipt['plan_approval']['id'],qualification=q,qualification_sha256=cp._hash(q),snapshot=snapshot)
 c.execute('UPDATE preparations SET candidate_p3_closure_consumptions=candidate_p3_closure_consumptions||%s WHERE id=%s',(Jsonb([saved]),parent['id']))


def validate_qualification(q,data,context):
 if (type(q) is not dict or set(q)!=QUALIFICATION_KEYS or type(q['schema']) is not int or q['schema']!=1
  or q['profile']!=PROFILE or q['state']!='CLOSED_WITHOUT_ACCEPTANCE' or q['closure_state'] not in ('DECLINED','WITHDRAWN')
  or type(q['epoch']) is not int or not 6<=q['epoch']<=186 or q['ever_started'] is not True
  or type(q['collection_bound']) is not int or q['collection_bound']!=64):raise ValueError('strict closed P3 qualification required')
 # Independent profile: share literal identity structure, never a zero DTO.
 if (q['previous_plan_id']!=str(data.expected_previous_plan_id)
  or any(q[k]!=context[k] for k in ('preparation_id','case_id','run_id'))):raise ValueError('exact closure Case and predecessor required')
 b=q['birth'];birthkeys={'scope','schema','generation','preparation_id','case_id','run_id','owner_id','park_id','org_id','birth_xid'}
 if (type(b) is not dict or set(b)!=birthkeys or b['scope']!=bf.SCOPE or type(b['schema']) is not int or b['schema']!=1
  or any(b[k]!=context[k] for k in ('preparation_id','case_id','run_id','owner_id','park_id','org_id'))
  or type(b['birth_xid']) is not str or re.fullmatch('[0-9]{1,24}',b['birth_xid']) is None or q['birth_sha256']!=cp._hash(b)):
  raise ValueError('original independent closure birth required')
 UUID(b['generation'])
 for k in ('birth_sha256','protocol_sha256'):
  if type(q[k]) is not str or re.fullmatch('[a-f0-9]{64}',q[k]) is None:raise ValueError('closure identity digest required')
 if type(q['verified_prefix']) is not list or len(q['verified_prefix'])!=2:raise ValueError('original P1/P2 verified closure prefix required')
 for adapter,item in zip(('P1','P2'),q['verified_prefix']):
  if (type(item) is not dict or set(item)!={'adapter_id','step_id','event_id','event_revision','source_sha256','event_sha256'}
   or item['adapter_id']!=adapter or type(item['event_revision']) is not int or not 1<=item['event_revision']<=64):raise ValueError('original closure prefix event required')
  UUID(item['step_id']);UUID(item['event_id'])
  if any(type(item[k]) is not str or re.fullmatch('[a-f0-9]{64}',item[k]) is None for k in ('source_sha256','event_sha256')):raise ValueError('closure prefix event digest required')
 if type(q['collections']) is not list or len(q['collections'])!=8:raise ValueError('complete original closure collections required')
 if q['tail']!={'P3':'CLOSED_WITHOUT_ACCEPTANCE','P4':'NO_RECEIPT_EFFECT','P5':'NO_LOCAL_LIFECYCLE_EFFECT'}:raise ValueError('strict closed tail required')
 d=q['dispatch']
 if (type(d) is not dict or set(d)!=DISPATCH_KEYS or type(d['revision']) is not int or not 2<=d['revision']<=62 or d['revision']%2
  or d['state']!=q['closure_state'] or type(d['offers_count']) is not int or d['offers_count']!=d['revision']//2
  or type(d['events_count']) is not int or d['events_count']!=d['revision'] or q['epoch']!=3*d['revision']
  or type(d['events']) is not list or len(d['events'])!=d['revision']):raise ValueError('complete bounded closed dispatch required')
 UUID(d['id']);UUID(d['current_offer_id'])
 for digest in (q['marker_sha256'],d['history_sha256']):
  if type(digest) is not str or re.fullmatch('[a-f0-9]{64}',digest) is None:raise ValueError('closure digest required')
 counts=[1,d['offers_count'],d['events_count'],0,0,0,0,0]
 for table,item,count in zip(bf.TABLES,q['collections'],counts):
  if (type(item) is not dict or set(item)!={'table','count','complete','known','sha256'} or item['table']!=table
   or type(item['count']) is not int or item['count']!=count or item['complete'] is not True or item['known'] is not True
   or type(item['sha256']) is not str or re.fullmatch('[a-f0-9]{64}',item['sha256']) is None
   or (not count and item['sha256']!=cp._hash([]))):raise ValueError('strict complete closure collection required')
 ids=set();pairs=set();last=None
 for n,e in enumerate(d['events'],1):
  if (type(e) is not dict or set(e)!=EVENT_KEYS or type(e['revision']) is not int or e['revision']!=n
   or e['id'] in ids or type(e['actor_id']) is not str or not 1<=len(e['actor_id'])<=100
   or type(e['request_key']) is not str or re.fullmatch('[A-Za-z0-9_-]{1,100}',e['request_key']) is None
   or type(e['transaction']) is not str or re.fullmatch('[0-9]{1,24}',e['transaction']) is None):raise ValueError('strict original closure event required')
  UUID(e['id']);UUID(e['offer_id']);ids.add(e['id'])
  for k in ('fingerprint','payload_sha256'):
   if type(e[k]) is not str or re.fullmatch('[a-f0-9]{64}',e[k]) is None:raise ValueError('closure event digest required')
  if n%2:
   if e['action']!=('OFFER' if n==1 else 'REOFFER') or e['offer_id'] in pairs:raise ValueError('original offer sequence required')
   pairs.add(e['offer_id']);last=e['offer_id']
  elif e['action'] not in ('DECLINE','WITHDRAW') or e['offer_id']!=last:raise ValueError('explicit terminal original decision required')
  f=historical_fields({'expected_business_frontier':e['business_frontier']})['expected_business_frontier']
  expected=dict(generation=q['birth']['generation'],preparation_id=q['preparation_id'],plan_id=q['previous_plan_id'],plan_revision=q['verified_prefix'][1]['event_revision'],epoch=3*(n-1))
  if f!=expected:raise ValueError('exact original captured closure fence required')
 if last!=d['current_offer_id'] or d['events'][-1]['action']!={'DECLINED':'DECLINE','WITHDRAWN':'WITHDRAW'}[q['closure_state']]:raise ValueError('latest explicit closure required')
