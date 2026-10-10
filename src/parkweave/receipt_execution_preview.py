"""Original bounded local software report and simulated enterprise review in shadows."""
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from uuid import UUID,uuid4
import json,secrets,tempfile
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from . import isolated_execution_preview as ep,resource_execution_preview as rp,dispatch_execution_preview as dp
from . import service_dispatches as sd,executor_receipts as er,preparation as prep,isolated_local_execution as local
from .isolated_run_access import IsolatedRunAccessBridge,ProjectionPending
from .receipt_preview_sql import RECEIPT_SQL
from .store import Store,Denied,Conflict,digest,_AccessConnection

SCOPE='ISOLATED_REGISTERED_P4_RECEIPT_EXECUTION_PREVIEW'
TABLES=(*dp.TABLES,'service_step_receipts')
P4_ACTIONS=[{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'service_executor','commands':['SUBMIT']},{'method':'POST','path':'/api/executor-receipts/{step_id}/commands','role':'enterprise_operator','commands':['ACKNOWLEDGE','REQUEST_CHANGES','REOPEN']}]
CONTRACT=ep._sha(dict(storage_version=2,adapter='executor-receipts',revision=1,actions=P4_ACTIONS,sql=sorted(RECEIPT_SQL),tables=TABLES,p3=dp.CONTRACT,local_adapter=local.ADAPTER_ID,local_effect=local.EFFECT,shadow_assignment_indexes=True,proof_scope='ORIGINAL_ISSUED_PROCESS_ONLY'))
PROOF_FIELDS=(*dp.PROOF_FIELDS,'review_decision')
class Execute(ep.Execute):
    review_decision:Literal['ACKNOWLEDGE','REQUEST_CHANGES']='ACKNOWLEDGE'
def registered(current):
    rows=[s for s in current['steps'] if s['id']=='P4']
    return (dp.registered(current) and len(rows)==1 and rows[0]['depends_on']==['P3'] and rows[0]['adapter_ref']=='executor-receipts' and type(rows[0]['adapter_revision']) is int and rows[0]['adapter_revision']==1 and rows[0]['request_service_ref']==prep.SERVICE and type(rows[0]['request_service_version']) is int and rows[0]['request_service_version']==1 and ep._sha(rows[0]['actions'])==ep._sha(P4_ACTIONS))
class _Result:
    def __init__(self,cursor):self._cursor=cursor
    def fetchone(self):return self._cursor.fetchone()
    def fetchall(self):return self._cursor.fetchall()
class _Cursor:
    def __init__(self,connection):self.connection=connection;self.result=None
    def execute(self,query,params=None):self.result=self.connection.execute(query,params);return self
    def fetchone(self):return self.result.fetchone()
class _Connection(_AccessConnection):
    def __init__(self,raw):self._raw=raw;self._managed_checks=set()
    @property
    def autocommit(self):return self._raw.autocommit
    @property
    def info(self):return SimpleNamespace(host=self._raw.info.host,port=self._raw.info.port)
    def cursor(self,*,row_factory):
        if row_factory is not dict_row:raise Denied('registered proof cursor only')
        return _Cursor(self)
    def execute(self,query,params=None):
        if type(query) is not str or query not in RECEIPT_SQL:raise Denied('unregistered P4 preview SQL template')
        return _Result(self._raw.execute(query,params))
    def commit(self):raise Denied('shadow commit unavailable')
    def rollback(self):raise Denied('shadow rollback owned by preview executor')
    def close(self):raise Denied('shadow close owned by preview executor')
class _Store(Store):
    mode='LOCAL'
    def __init__(self,raw):self.connection=_Connection(raw)
    @contextmanager
    def connect(self):yield self.connection
class ReceiptExecutionPreview(dp.DispatchExecutionPreview):
    storage_scope=SCOPE
    attachment_attribute='_isolated_receipt_execution_preview'
    def _participants(self,store,c,parent):
        result=super()._participants(store,c,parent)
        bridge=getattr(store,'_isolated_run_access',None);adapter=local.provider(store)
        if type(bridge) is not IsolatedRunAccessBridge or not adapter or adapter.bridge is not bridge or not isinstance(result['assignment'].get('managed_access'),dict):raise Denied('existing issued local adapter and current managed exact Run executor required')
        bridge._issued_proof();bridge._connection(c)
        return result
    def _p4_document(self,doc):
        a=doc['artifact']
        if doc['decision']!='ACCEPT' or doc['review_decision'] not in ('ACKNOWLEDGE','REQUEST_CHANGES') or a['p4_state'] not in ('NOT_EXECUTED','FAILED','LOCAL_ACKNOWLEDGED','CHANGES_REQUESTED') or len(a['p4_steps'])>1 or len(a['p4_receipts'])>1 or len(a['p4_events'])>3 or len(a['access_events'])>2:raise ValueError()
        if doc['state']!='SUCCEEDED':return
        expected='LOCAL_ACKNOWLEDGED' if doc['review_decision']=='ACKNOWLEDGE' else 'CHANGES_REQUESTED'
        if a['p4_state']!=expected or len(a['p4_receipts'])!=1 or len(a['p4_steps'])!=1 or len(a['p4_events'])!=3 or len(a['access_events'])!=2:raise ValueError()
        receipt=a['p4_receipts'][0];step=a['p4_steps'][0];events=a['p4_events'];metadata=receipt['adapter_execution'];report=metadata['report'];binding=report['binding'];UUID(report['execution_id'])
        if (step['id']!=a['steps'][0]['id'] or step['state']!=expected or step['revision']!=3 or step['current_receipt_id']!=receipt['id'] or receipt['version']!=1 or receipt['step_id']!=step['id'] or receipt['actor_id']!=a['executor_id'] or receipt['text']!=prep.canonical(report) or digest(receipt['text'])!=receipt['source_sha256'] or report['adapter_id']!=local.ADAPTER_ID or report['adapter_version']!=1 or report['effect']!=local.EFFECT or report['case_goal_completed'] is not False or report['external_acceptance']!='NOT_SUBMITTED' or report['offline_fulfillment']!='NO_EVIDENCE' or metadata['submit_revision']!=2 or [e['action'] for e in events]!=['CREATE','SUBMIT',doc['review_decision']] or [e['revision'] for e in events]!=[1,2,3] or [e['actor_id'] for e in events]!=[a['executor_id'],a['executor_id'],a['p1']['owner_id']]):raise ValueError()
        if report['checks']!=['CURRENT_ACCEPTED_HANDOFF','CURRENT_PREPARATION_BINDING','CURRENT_MANAGED_EXECUTOR_LEASE'] or a['local_current_at_execution'] is not (doc['review_decision']=='ACKNOWLEDGE'):raise ValueError()
        if binding['step_id']!=step['id'] or any(binding[k]!=str(step[k]) for k in ('case_id','run_id','preparation_id')) or binding['offer_id']!=a['offers'][0]['id'] or binding['executor_id']!=a['executor_id'] or binding['preparation_revision']!=step['preparation_revision'] or binding['preparation_sha256']!=step['preparation_sha256'] or any(binding[k]!=step[k] for k in ('park_id','org_id','service_id','service_version')):raise ValueError()
        for e in events[1:]:
            if e['step_id']!=step['id'] or e['payload']['receipt_id']!=receipt['id'] or e['payload']['receipt_sha256']!=receipt['source_sha256']:raise ValueError()
        if events[1]['payload']['adapter_execution']!=metadata or [e['action'] for e in a['access_events']]!=['REQUEST','APPROVE']:raise ValueError()
    def _view(self,db,p,parent,current):
        rows=db.execute('SELECT * FROM previews WHERE owner=? AND preparation=? ORDER BY rowid',(p['id'],str(parent['id']))).fetchall()
        history=[dict(document=self._document(row),source_state='SNAPSHOT_MATCH' if self._document(row)['binding']['source_sha256']==current['source_sha256'] else 'STALE') for row in rows]
        return dict(scope=SCOPE,enabled=True,preparation_id=str(parent['id']),namespace=self.namespace,history=history,
                    preparation_revision=parent['revision'],request_revision=parent['request_intent']['revision'],current_source_sha256=current['source_sha256'],execution_available=registered(current),isolated_steps=['P1','P2','P3','P4'],
                    formal_writes=0,new_grants=False,case_goal_completed=False,source_atomicity=False,source_consistency='COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON',capacity_scope='EMPTY_ISOLATED_SPACE_ONLY')

    def _document(self, row):
        try:
            if len(row['document'].encode())>65536 or len(row['proof'].encode())>65536: raise ValueError()
            doc=json.loads(row['document']);proof=json.loads(row['proof'])
            if prep.canonical(proof)!=prep.canonical({k:doc[k] for k in PROOF_FIELDS}): raise ValueError()
            if (doc['scope']!=SCOPE or type(doc['version']) is not int or doc['version']!=2 or doc['namespace']!=self.namespace or
                    doc['execution_contract_sha256']!=CONTRACT or doc['actor_id']!=row['owner'] or
                    doc['request_key']!=row['request_key'] or doc['fingerprint']!=row['fingerprint'] or
                    doc['binding']['preparation_id']!=row['preparation'] or doc['sha256']!=ep._sha({k:v for k,v in doc.items() if k!='sha256'})):
                raise ValueError()
            UUID(doc['id'])
            b=doc['binding'];a=doc['artifact']
            fp=ep._sha(dict(preparation_id=b['preparation_id'],expected_preparation_revision=b['preparation_revision'],
                           expected_request_revision=b['request_revision'],expected_source_sha256=b['source_sha256'],review_decision=doc['review_decision']))
            if (fp!=doc['fingerprint'] or type(doc['formal_writes']) is not int or doc['formal_writes']!=0 or
                    doc['new_grants'] is not False or doc['case_goal_completed'] is not False or
                    doc['qualification']!='NOT_EVALUATED' or doc['external_acceptance']!='NOT_SUBMITTED' or
                    doc['offline_fulfillment']!='NO_EVIDENCE' or
                    doc['state'] not in ('SUCCEEDED','FAILED') or a['roles']!='SIMULATED_ROLES_ONLY' or
                    a['capacity_scope']!='EMPTY_ISOLATED_SPACE_ONLY' or a['namespace']!='PREVIEW_EXECUTION' or
                    a['p1']['preparation_id']==b['preparation_id'] or a['p1']['case_id']==b['case_id'] or a['p1']['run_id']==b['run_id'] or
                    len(a['holds'])>2 or len(a['prechecks'])>2 or len(a['receipts'])>2 or len(a['links'])>1): raise ValueError()
            if (doc['state']=='SUCCEEDED')!=(a['error'] is None): raise ValueError()
            if doc['state']=='SUCCEEDED' and (a['p1']['state']!='LOCAL_CONFIRMED' or a['combination']['state']!='CONFIRMED' or
                    len(a['holds'])!=2 or len(a['receipts'])!=2 or len(a['links'])!=1 or len(a['claims'])!=1): raise ValueError()
            if doc['decision'] not in ('ACCEPT','DECLINE') or len(a['offers'])>1 or len(a['dispatch_events'])>2 or len(a['steps'])>1 or len(a['receipt_events'])>1 or len(a['outbox'])>4 or a['notices']:
                raise ValueError()
            if any(o['state']!='PENDING' or o['consumed_at'] is not None for o in a['outbox']): raise ValueError()
            if doc['state']=='SUCCEEDED':
                if a['p3_state']!=('ACCEPTED' if doc['decision']=='ACCEPT' else 'DECLINED'): raise ValueError()
                if len(a['offers'])!=1 or [e['action'] for e in a['dispatch_events']]!=['OFFER',doc['decision']]: raise ValueError()
                offer=a['offers'][0];events=a['dispatch_events'];reviewer=a['p1']['reviewer_id'];executor=a['executor_id']
                if events[0]['actor_id']!=reviewer or events[1]['actor_id']!=executor or offer['executor_id']!=executor or offer['state']!=a['p3_state']: raise ValueError()
                if [e['revision'] for e in events]!=[1,2]: raise ValueError()
                if any(e['offer_id']!=offer['id'] or e['dispatch_id']!=offer['dispatch_id'] for e in events): raise ValueError()
                recipients={events[0]['id']:{a['p1']['owner_id'],executor},events[1]['id']:{a['p1']['owner_id'],reviewer}}
                if {(o['event_id'],o['recipient_id']) for o in a['outbox']}!={(e,r) for e,rs in recipients.items() for r in rs}: raise ValueError()
                if doc['decision']=='ACCEPT':
                    if len(a['steps'])!=len(a['receipt_events']) or len(a['steps'])!=1: raise ValueError()
                    step=a['steps'][0];event=a['receipt_events'][0]
                    if (step['id']!=offer['receipt_step_id'] or step['state']!='AWAITING_RECEIPT' or step['current_receipt_id'] is not None or
                        step['preparation_id']!=a['p1']['preparation_id'] or step['case_id']!=a['p1']['case_id'] or step['run_id']!=a['p1']['run_id'] or
                        step['executor_id']!=executor or event['actor_id']!=executor or event['step_id']!=step['id'] or event['action']!='CREATE'): raise ValueError()
                elif a['steps'] or a['receipt_events'] or offer['receipt_step_id'] is not None: raise ValueError()
            self._p4_document(doc)
            return doc
        except (ValueError,KeyError,TypeError):
            raise Conflict('isolated P4 artifact proof unavailable') from None

    def _execute(self,store,parent,current,materials,review_decision):
        artifact=rp.ResourceExecutionPreview._execute(self,store,parent,current,materials)
        artifact.update(p4_state='NOT_EXECUTED',p4_steps=[],p4_receipts=[],p4_events=[],access_events=[],local_current_at_execution=False,p3_state='NOT_EXECUTED',executor_id=None,offers=[],dispatch_events=[],steps=[],receipt_events=[],outbox=[],notices=[])
        if artifact['error']:return artifact
        p1=artifact['p1'];source_bridge=store._isolated_run_access;c=source_bridge.owner.connect();journal=tempfile.TemporaryDirectory(prefix='pw-p4-shadow-')
        try:
            if c.execute(ep.IDENTITY_SQL).fetchone()!=self.database_identity:raise Denied('original preview cluster required')
            for table in TABLES:c.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE public.{} INCLUDING DEFAULTS'+(' INCLUDING INDEXES' if table=='run_assignments' else '')+') ON COMMIT DROP').format(sql.Identifier(table),sql.Identifier(table)))
            c.execute('SET LOCAL search_path TO pg_temp');c.execute("SET LOCAL statement_timeout='3s'");c.execute("SET LOCAL lock_timeout='3s'")
            owner,reviewer=p1['owner_id'],p1['reviewer_id'];executor='preview-executor-'+uuid4().hex;artifact['executor_id']=executor
            park=artifact['links'][0]['park_id'];org=artifact['links'][0]['org_id']
            tokens={a:secrets.token_urlsafe(32) for a in (owner,reviewer,executor)}
            for actor,role in ((owner,'enterprise_operator'),(reviewer,'park_specialist'),(executor,'service_executor')):
                c.execute('INSERT INTO principals(id,token_hash,park_id,org_id,role,active) VALUES(%s,%s,%s,%s,%s,true)',(actor,digest(tokens[actor]),park,org,role))
                for cap in (('READ','EXECUTE') if actor==owner else ('READ',)):c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(actor,cap,park,org))
                if actor!=executor:c.execute('INSERT INTO preparation_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(actor,'PREPARE' if actor==owner else 'REVIEW_ASSIGNED',park,org))
            id=UUID(p1['preparation_id']);run=UUID(p1['run_id']);case=UUID(p1['case_id'])
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,'{}','SUCCEEDED')",(run,owner,park,org,uuid4().hex,ep._sha(p1)))
            c.execute("INSERT INTO cases VALUES(%s,%s,%s,%s,'SYNTHETIC isolated P3','NEEDS_INPUT','SYNTHETIC','NOT_SUBMITTED','NO_EVIDENCE')",(case,run,park,org))
            c.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state,revision,review_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,1,'SYNTHETIC','SYNTHETIC isolated P3','LOCAL_CONFIRMED',%s,%s)",(id,run,case,owner,reviewer,park,org,prep.SERVICE,p1['revision'],p1['review_sha256']))
            c.execute("INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) VALUES(%s,%s,1,'Synthetic P4 preview',%s,'SYNTHETIC','NOT_EVALUATED')",(park,prep.SERVICE,Jsonb(dict(kind='SYNTHETIC',id='P3-preview',revision='1'))))
            for m in p1['materials']:c.execute("INSERT INTO preparation_evidence(id,preparation_id,slot,version,text,source_kind,source_label,source_sha256,actor_id,authenticity) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'UNVERIFIED')",(UUID(m['id']),id,m['slot'],m['version'],m['text'],m['source_kind'],m['source_label'],m['source_sha256'],owner))
            for table,rows in (('case_resource_links',artifact['links']),('synthetic_resource_combination_receipts',artifact['combination_receipts'])):
                for row in rows:
                    values=dict(row)
                    c.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),tuple(Jsonb(v) if isinstance(v,(dict,list)) else v for v in values.values()))
            private=_Store(c)
            bridge=IsolatedRunAccessBridge(private,source_bridge.proof,Path(journal.name)/'shadow.run-access.candidate.sqlite3',approver_ids={reviewer},enabled_for_isolated_tests=True,clock=source_bridge.clock)
            bridge.attach_store(private)
            local.IsolatedLocalExecutor(bridge,enabled_for_isolated_tests=True).attach_store(private)
            state=bridge.read(tokens[owner],run)
            now=bridge.clock();validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=5)).isoformat(),timezone='UTC')
            def authority(action,actor,**extra):
                nonlocal state
                state=bridge.command(tokens[actor],run,uuid4().hex,dict(action=action,expected_revision=state['revision'],expected_run_revision=state['run_revision'],expected_authority_sha256=state['authority_sha256'],reason='SYNTHETIC P4 shadow authority '+action,**extra))
            authority('REQUEST',owner,target_id=executor,target_role='service_executor',capability='READ',requested_validity=validity)
            authority('APPROVE',reviewer,approved_validity=validity)
            artifact['access_events']=ep._normal(state['history'])
            try:
                offered=sd.offer(private,tokens[reviewer],id,uuid4().hex,sd.Offer(expected_preparation_revision=p1['revision'],expected_dispatch_revision=0,executor_id=executor,reason='SYNTHETIC PREVIEW simulated reviewer only'))
                result=sd.command(private,tokens[executor],offered['dispatch_id'],uuid4().hex,sd.Command(action='ACCEPT',expected_revision=offered['revision'],reason='SYNTHETIC PREVIEW executor own simulated token'))
                artifact['p3_state']=result['current_offer']['state']
            except Conflict:
                artifact['error']='DISPATCH_PREREQUISITE_FAILED';artifact['p3_state']='FAILED'
            for name,table,order in (('offers','service_dispatch_offers','created_at,id'),('dispatch_events','service_dispatch_events','revision'),('steps','service_receipt_steps','id'),('receipt_events','service_receipt_events','revision'),('outbox','dispatch_notice_outbox','event_id,recipient_id'),('notices','dispatch_notices','event_id,recipient_id')):
                artifact[name]=ep._normal(c.execute(sql.SQL('SELECT * FROM {} ORDER BY '+order).format(sql.Identifier(table))).fetchall())
            if artifact['p3_state']!='ACCEPTED':return artifact
            try:
                step=artifact['steps'][0]
                submitted=er.command(private,tokens[executor],UUID(step['id']),uuid4().hex,local.ExecuteLocal(expected_revision=step['revision'],reason='SYNTHETIC P4 actual original local adapter execution'))
                receipt=submitted['current_receipt']
                reviewed=er.command(private,tokens[owner],UUID(step['id']),uuid4().hex,er.Command(action=review_decision,expected_revision=submitted['step']['revision'],receipt_sha256=receipt['source_sha256'],reason='SYNTHETIC simulated enterprise explicit '+review_decision))
                artifact['p4_state']=reviewed['step']['state'];artifact['local_current_at_execution']=reviewed['local_execution']['current']
            except Conflict:
                artifact['error']='RECEIPT_PREREQUISITE_FAILED';artifact['p4_state']='FAILED'
            for name,table,order in (('p4_steps','service_receipt_steps','id'),('p4_receipts','service_step_receipts','version'),('p4_events','service_receipt_events','revision')):
                artifact[name]=ep._normal(c.execute(sql.SQL('SELECT * FROM {} ORDER BY '+order).format(sql.Identifier(table))).fetchall())
            for actor,run_id in private.connection._managed_checks:
                principal=private.connection.execute('SELECT * FROM principals WHERE id=%s',(actor,)).fetchone()
                private.check_capability(private.connection,principal,'READ')
                if not private.assignment_allowed(private.connection,principal,run_id,track=False):raise Denied('shadow lease expired before completion')
            return artifact
        except ProjectionPending:raise ep.Unavailable('discarded shadow projection unavailable; read original P4 key only') from None
        finally:c.rollback();c.close();journal.cleanup()

    def execute(self, store, token, id, key, data):
        with store.connect() as c:
            p,parent,current=self._source(store,c,token,id);fp=ep._sha({'preparation_id':str(id),**data.model_dump()})
            with self._database() as db:
                db.execute('BEGIN EXCLUSIVE');self._guard(store,c,token,p)
                old=db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone()
                if old:
                    if old['preparation']!=str(id) or old['fingerprint']!=fp: raise Conflict('P4 preview key body or scope mismatch')
                    return {**self._view(db,p,parent,current),'result':self._document(old)}
                if (parent['revision']!=data.expected_preparation_revision or parent['request_intent']['revision']!=data.expected_request_revision or current['source_sha256']!=data.expected_source_sha256): raise Conflict('P4 preview sources changed; explicitly read current proposal')
                if not registered(current): raise Conflict('exact registered P1/P2/P3/P4 action and service contract required')
                if db.execute('SELECT count(*) FROM previews').fetchone()[0]>=128 or db.execute('SELECT count(*) FROM previews WHERE preparation=?',(str(id),)).fetchone()[0]>=16: raise Conflict('bounded P4 preview history limit reached')
                materials=prep.latest(c,id);artifact=self._execute(store,parent,current,materials,data.review_decision);self._guard(store,c,token,p)
                if self._comparison(store,c,p,parent)!=current['source_sha256']: raise Conflict('P4 preview sources changed during execution')
                result=dict(scope=SCOPE,version=2,id=str(uuid4()),namespace=self.namespace,actor_id=p['id'],request_key=key,fingerprint=fp,
                            binding=dict(preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),service_id=parent['service_id'],service_version=parent['service_version'],preparation_revision=parent['revision'],request_revision=parent['request_intent']['revision'],source_sha256=current['source_sha256'],resource_rules=current['resource_rules'],participants=current['participants'],slots=[{k:str(m[k]) if isinstance(m[k],UUID) else m[k] for k in ('id','slot','version','source_sha256')} for m in materials]),
                            execution_contract_sha256=CONTRACT,decision='ACCEPT',review_decision=data.review_decision,state='FAILED' if artifact['error'] else 'SUCCEEDED',coverage_state='P1_P2_P3_P4_PREVIEW_ONLY' if data.review_decision=='ACKNOWLEDGE' and not artifact['error'] and all(g in ('LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS') for g in current['required_goals']) else 'PARTIAL_PREVIEW',required_goals=current['required_goals'],not_previewed=[s['id'] for s in current['steps'] if s['id'] not in ('P1','P2','P3','P4') or (s['id']=='P2' and artifact['p2_state']=='NOT_EXECUTED') or (s['id']=='P3' and artifact['p3_state']=='NOT_EXECUTED') or (s['id']=='P4' and artifact['p4_state']=='NOT_EXECUTED')],goal_coverage=current['goal_coverage'],artifact=artifact,formal_writes=0,new_grants=False,case_goal_completed=False,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')
                result['sha256']=ep._sha(result);document=prep.canonical(result);proof=prep.canonical({k:result[k] for k in PROOF_FIELDS})
                if max(len(document.encode()),len(proof.encode()))>65536: raise Conflict('bounded P3 artifact bytes exceeded')
                db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',(p['id'],str(id),key,fp,document,proof))
                self._document(db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone());self._guard(store,c,token,p);db.commit()
                current['source_sha256']=self._comparison(store,c,p,parent)
                return {**self._view(db,p,parent,current),'result':result}
