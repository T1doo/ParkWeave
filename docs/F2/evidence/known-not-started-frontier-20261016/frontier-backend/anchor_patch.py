from pathlib import Path
p=Path('/workspace/ParkWeave/.runtime/frontier-backend/candidate/src/parkweave/business_frontier.py');s=p.read_text()
s=s.replace("MARK='candidate_business_frontier'", "MARK='candidate_business_frontier'\nANCHORS='candidate_frontier_consumptions'")
s=s.replace('BEGIN\n IF TG_OP=', 'DECLARE anchor jsonb;\nBEGIN\n IF TG_OP=',1)
s=s.replace('IF NEW.candidate_frontier_birth IS NOT NULL OR NEW.candidate_business_frontier IS NOT NULL THEN','IF NEW.candidate_frontier_birth IS NOT NULL OR NEW.candidate_business_frontier IS NOT NULL OR NEW.candidate_frontier_consumptions IS NOT NULL THEN',1)
s=s.replace('  RETURN NEW;\n END IF;', "  NEW.candidate_frontier_consumptions:='[]'::jsonb;\n  RETURN NEW;\n END IF;",1)
needle=' IF NEW.candidate_frontier_birth IS DISTINCT FROM OLD.candidate_frontier_birth THEN'
block=''' IF NEW.candidate_frontier_consumptions IS DISTINCT FROM OLD.candidate_frontier_consumptions THEN
  IF OLD.candidate_frontier_consumptions IS NULL OR NEW.candidate_frontier_consumptions IS NULL
   OR jsonb_typeof(NEW.candidate_frontier_consumptions) IS DISTINCT FROM 'array'
   OR jsonb_array_length(NEW.candidate_frontier_consumptions)<>jsonb_array_length(OLD.candidate_frontier_consumptions)+1
   OR jsonb_array_length(NEW.candidate_frontier_consumptions)>8
   OR (NEW.candidate_frontier_consumptions)-(jsonb_array_length(NEW.candidate_frontier_consumptions)-1) IS DISTINCT FROM OLD.candidate_frontier_consumptions
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
'''
assert needle in s;s=s.replace(needle,block+needle,1)
insert='''
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

'''
pos=s.index('class KnownNotStartedFrontier:');s=s[:pos]+insert+s[pos:]
s=s.replace("   self.endpoint=(c.info.host,c.info.port)","   from .service_plan_approval import _install_schema\n   _install_schema(c)\n   self.endpoint=(c.info.host,c.info.port)",1)
s=s.replace('ADD COLUMN candidate_business_frontier jsonb', 'ADD COLUMN candidate_business_frontier jsonb, ADD COLUMN candidate_frontier_consumptions jsonb',1)
s=s.replace("('candidate_frontier_truncate_guard',TRUNCATE_BODY)","('candidate_frontier_truncate_guard',TRUNCATE_BODY),('candidate_frontier_consumption_guard',CONSUMPTION_BODY)",1)
needle="   self.schema=self._catalog(c);self.schema_sha256=cp._hash(self.schema)"
s=s.replace(needle,"   c.execute(\"CREATE CONSTRAINT TRIGGER candidate_frontier_consumption AFTER UPDATE ON preparations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (OLD.candidate_frontier_consumptions IS DISTINCT FROM NEW.candidate_frontier_consumptions) EXECUTE FUNCTION public.candidate_frontier_consumption_guard()\")\n   c.execute('ALTER TABLE preparations ENABLE ALWAYS TRIGGER candidate_frontier_consumption')\n"+needle,1)
s=s.replace('if len(frontier)!=18','if len(frontier)!=19').replace("triggers=[r for r in rows if r['tgname'].startswith('candidate_frontier_') or r['tgisinternal']]",'triggers=rows')
s=s.replace('def qualify(self,c,parent,previous,*,historical=False):','def qualify(self,c,parent,previous,*,historical=False,consumption_key=None):',1)
needle='  collections=[]\n  for table in TABLES:'
s=s.replace(needle,"""  if historical:
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
  for table in TABLES:""",1)
p.write_text(s)
