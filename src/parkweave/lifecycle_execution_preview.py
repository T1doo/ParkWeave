"""Explicit original local Case commands on the existing discarded P4 shadow."""
from typing import Literal
from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from . import receipt_execution_preview as p4,isolated_execution_preview as ep,preparation as prep,case_lifecycle as lc
from .lifecycle_preview_sql import LIFECYCLE_SQL
from .store import Conflict,Denied,digest

SCOPE='ISOLATED_REGISTERED_P5_LOCAL_CASE_EXECUTION_PREVIEW'
TABLES=(*p4.TABLES,'case_local_lifecycles','case_local_events')
SEQUENCES={'REVALIDATE':('REVALIDATE',),'REVALIDATE_CLOSE':('REVALIDATE','CLOSE_LOCAL_RECORD'),'REVALIDATE_CLOSE_REOPEN':('REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN')}
ACTIONS=[{'method':'POST','path':'/api/preparations/{preparation_id}/local-case/commands','role':'enterprise_operator','commands':['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN']}]
CONTRACT=ep._sha(dict(storage_version=3,adapter='case-lifecycle',revision=1,actions=ACTIONS,sql=sorted(LIFECYCLE_SQL),tables=TABLES,p4=p4.CONTRACT,sequences=SEQUENCES,sequence_required=True,proof_scope='ORIGINAL_ISSUED_PROCESS_ONLY'))
PROOF_FIELDS=(*p4.PROOF_FIELDS,'lifecycle_sequence')
RESOURCE_TABLES=('synthetic_resources','synthetic_resource_grants','synthetic_resource_combinations','synthetic_resource_combination_members')
COPY_TABLES=(*RESOURCE_TABLES,'synthetic_resource_holds','synthetic_resource_receipts','resource_case_claims')

class Execute(p4.Execute):
    lifecycle_sequence:Literal['REVALIDATE','REVALIDATE_CLOSE','REVALIDATE_CLOSE_REOPEN']

def registered(current):
    rows=[s for s in current['steps'] if s['id']=='P5']
    return (p4.registered(current) and len(rows)==1 and rows[0]['depends_on']==['P4'] and rows[0]['adapter_ref']=='case-lifecycle' and type(rows[0]['adapter_revision']) is int and rows[0]['adapter_revision']==1 and rows[0]['request_service_ref']==prep.SERVICE and type(rows[0]['request_service_version']) is int and rows[0]['request_service_version']==1 and ep._sha(rows[0]['actions'])==ep._sha(ACTIONS))

def _insert(connection,table,rows):
    if table not in COPY_TABLES:raise Denied('unregistered P5 seed table')
    for row in rows:
        connection.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(Jsonb(v) if isinstance(v,(dict,list)) else v for v in row.values()))

class LifecycleExecutionPreview(p4.ReceiptExecutionPreview):
    storage_scope=SCOPE
    attachment_attribute='_isolated_lifecycle_execution_preview'
    execution_contract=CONTRACT
    document_version=3
    proof_fields=PROOF_FIELDS
    shadow_tables=TABLES
    shadow_sql=LIFECYCLE_SQL
    indexed_shadow_tables=('run_assignments','case_local_lifecycles','case_local_events')
    isolated_steps=('P1','P2','P3','P4','P5')
    registered=staticmethod(registered)
    def _request_body(self,doc):return {**super()._request_body(doc),'lifecycle_sequence':doc['lifecycle_sequence']}
    def _upstream_complete(self,doc):return doc['artifact']['p4_state'] in ('LOCAL_ACKNOWLEDGED','CHANGES_REQUESTED')
    def _capture_resources(self,connection,artifact,current,resource_ids):
        if artifact['p2_state']!='LOCAL_ASSOCIATION_PREVIEWED':return
        artifact['p2_records']={t:ep._normal(connection.execute(sql.SQL('SELECT * FROM {} ORDER BY 1').format(sql.Identifier(t))).fetchall()) for t in RESOURCE_TABLES}
        artifact['p2_resource_mapping']=[dict(source_id=r['id'],shadow_id=str(id)) for r,id in zip(current['resource_rules'],resource_ids,strict=True)]
    def _check_resources(self,artifact,rules):
        records=artifact['p2_records'];mapping=artifact['p2_resource_mapping'];resources={r['id']:r for r in records['synthetic_resources']}
        if len(mapping)!=2 or len(resources)!=2 or len(records['synthetic_resource_combinations'])!=1 or len(records['synthetic_resource_combination_members'])!=2:raise ValueError()
        if [m['source_id'] for m in mapping]!=[r['id'] for r in rules] or {m['shadow_id'] for m in mapping}!=set(resources):raise ValueError()
        for m,rule in zip(mapping,rules,strict=True):
            resource=resources[m['shadow_id']]
            if any(resource[k]!=rule[k] for k in ('revision','capacity','buffer_seconds','open_from','open_until','enabled','timezone','namespace','authority','source')):raise ValueError()
            if resource['park_id']!=artifact['links'][0]['park_id']:raise ValueError()
        group=records['synthetic_resource_combinations'][0];members=records['synthetic_resource_combination_members'];holds=artifact['holds'];owner=artifact['p1']['owner_id'];link=artifact['links'][0]
        if group['id']!=artifact['combination']['id'] or group['id']!=link['combination_id'] or group['state']!='CONFIRMED' or group['principal_id']!=owner:raise ValueError()
        if {(m['combination_id'],m['hold_id']) for m in members}!={(group['id'],h['id']) for h in holds} or {h['resource_id'] for h in holds}!=set(resources):raise ValueError()
        grants=records['synthetic_resource_grants']
        if len(grants)!=4 or {(g['principal_id'],g['resource_id'],g['capability'],g['active']) for g in grants}!={(owner,r,cap,True) for r in resources for cap in ('READ','HOLD')}:raise ValueError()
        if any((g['park_id'],g['org_id'])!=(link['park_id'],link['org_id']) for g in grants):raise ValueError()
        if len(artifact['claims'])!=1 or artifact['claims'][0]['combination_id']!=group['id'] or artifact['claims'][0]['case_id']!=artifact['p1']['case_id']:raise ValueError()
    def _seed_resources(self,connection,artifact,current):
        try:self._check_resources(artifact,current['resource_rules'])
        except (ValueError,KeyError,TypeError):raise Conflict('P5 original P2 resource mapping unavailable') from None
        records=artifact['p2_records']
        for table in RESOURCE_TABLES:_insert(connection,table,records[table])
        for table,name in (('synthetic_resource_holds','holds'),('synthetic_resource_receipts','receipts'),('resource_case_claims','claims')):_insert(connection,table,artifact[name])
    def _run_artifact(self,store,parent,current,materials,data):
        artifact=self._execute(store,parent,current,materials,data.review_decision,data.lifecycle_sequence)
        artifact.setdefault('p5_state','NOT_EXECUTED');artifact.setdefault('lifecycle_attempts',[]);artifact.setdefault('lifecycle_events',[]);artifact.setdefault('lifecycle_ledger',[]);artifact.setdefault('lifecycle_final',None)
        return artifact
    def _after_receipt(self,private,tokens,id,artifact,sequence):
        artifact.update(p5_state='NOT_EXECUTED',lifecycle_attempts=[],lifecycle_events=[],lifecycle_ledger=[],lifecycle_final=None)
        if artifact['error']:return
        token=tokens[artifact['p1']['owner_id']]
        for action in SEQUENCES[sequence]:
            before=lc.read(private,token,id)
            body=lc.Command(action=action,expected_revision=before['revision'],expected_cycle=before['cycle'],expected_snapshot_sha256=before['current_snapshot_sha256'] if action!='REOPEN' else None,reason='SYNTHETIC simulated enterprise explicit '+action)
            key=uuid4().hex;attempt=dict(request_key=key,body=body.model_dump(mode='json'),fingerprint=digest(prep.canonical({'preparation_id':str(id),**body.model_dump(mode='json')})),before=ep._normal(before))
            artifact['lifecycle_attempts'].append(attempt)
            try:attempt['result']=ep._normal(lc.command(private,token,id,key,body))
            except Conflict:
                artifact['error']='LIFECYCLE_PREREQUISITE_FAILED';artifact['p5_state']='FAILED';break
            artifact['p5_state']=attempt['result']['local_record_state']
        artifact['lifecycle_final']=ep._normal(lc.read(private,token,id))
        raw=private.connection._raw
        artifact['lifecycle_events']=ep._normal(raw.execute('SELECT * FROM case_local_events WHERE preparation_id=%s ORDER BY revision',(id,)).fetchall())
        artifact['lifecycle_ledger']=ep._normal(raw.execute('SELECT * FROM case_local_lifecycles WHERE preparation_id=%s',(id,)).fetchall())
    def _result_metadata(self,result,data,current):
        result['lifecycle_sequence']=data.lifecycle_sequence
        a=result['artifact'];final=a['lifecycle_final']
        result['not_previewed']=[s['id'] for s in current['steps'] if (s['id'] in result['not_previewed'] and s['id']!='P5') or s['id'] not in self.isolated_steps or (s['id']=='P5' and a['p5_state'] in ('NOT_EXECUTED','FAILED'))]
        supported={'LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE','LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_SYNTHETIC_COORDINATION_RECORDS','LOCAL_CASE_RECORD_RECHECK'}
        result['coverage_state']='P1_P2_P3_P4_P5_PREVIEW_ONLY' if final and final['verification_current'] is True and not a['error'] and all(g in supported for g in current['required_goals']) else 'PARTIAL_PREVIEW'
    def _p4_document(self,doc):
        super()._p4_document(doc)
        try:
            actions=SEQUENCES[doc['lifecycle_sequence']];a=doc['artifact'];attempts=a['lifecycle_attempts'];events=a['lifecycle_events'];ledger=a['lifecycle_ledger'];final=a['lifecycle_final']
            if a['p5_state'] not in ('NOT_EXECUTED','FAILED','READY','LOCAL_RECORD_CLOSED','REOPENED') or len(attempts)>len(actions) or len(events)>3 or len(ledger)>1:raise ValueError()
            required_missing=[stage for stage in ('P2','P3','P4') if a[stage.lower()+'_state']=='NOT_EXECUTED']
            if a['p5_state'] in ('NOT_EXECUTED','FAILED'):required_missing.append('P5')
            if any(stage not in doc['not_previewed'] for stage in required_missing) or ('P5' in doc['not_previewed'])!=(a['p5_state'] in ('NOT_EXECUTED','FAILED')):raise ValueError()
            if not self._upstream_complete(doc):
                if attempts or events or ledger or final is not None or a['p5_state']!='NOT_EXECUTED':raise ValueError()
                return
            self._check_resources(a,doc['binding']['resource_rules'])
            for i,attempt in enumerate(attempts):
                body=attempt['body'];before=attempt['before'];result=attempt.get('result')
                if body['action']!=actions[i] or body['expected_revision']!=before['revision'] or body['expected_cycle']!=before['cycle'] or body['expected_snapshot_sha256']!=(before['current_snapshot_sha256'] if actions[i]!='REOPEN' else None):raise ValueError()
                if attempt['fingerprint']!=digest(prep.canonical({'preparation_id':a['p1']['preparation_id'],**body})):raise ValueError()
                if before['actor_id']!=a['p1']['owner_id'] or before['actor_id']==a['executor_id'] or before['preparation_id']!=a['p1']['preparation_id'] or before['case_goal_completed'] is not False:raise ValueError()
                if result is None:
                    if a['p5_state']!='FAILED' or i!=len(attempts)-1:raise ValueError()
                    continue
                e=events[i]
                if (e['action']!=body['action'] or e['actor_id']!=before['actor_id'] or e['request_key']!=attempt['request_key'] or e['fingerprint']!=attempt['fingerprint'] or e['revision']!=i+1 or e['payload']!=result['event'] or e['preparation_id']!=a['p1']['preparation_id']):raise ValueError()
                if body['action']=='REOPEN':
                    if e['snapshot'] is not None or e['cycle']!=2 or result['verification_current'] is not None or result['verified_snapshot_sha256'] is not None:raise ValueError()
                elif e['snapshot'] is None or lc._sha(e['snapshot'],e['cycle'])!=result['verified_snapshot_sha256'] or result['verification_current'] is not True or result['case_state']!='WAITING_CONFIRMATION':raise ValueError()
            if len(events)!=sum('result' in attempt for attempt in attempts):raise ValueError()
            if final is None or final['actor_id']!=a['p1']['owner_id'] or final['case_goal_completed'] is not False or final['qualification']!='NOT_EVALUATED' or final['external_acceptance']!='NOT_SUBMITTED' or final['offline_fulfillment']!='NO_EVIDENCE':raise ValueError()
            if events:
                row=ledger[0]
                if row['revision']!=len(events) or row['state']!=final['local_record_state'] or row['cycle']!=final['cycle'] or row['verified_sha256']!=final['verified_snapshot_sha256'] or row['case_id']!=a['p1']['case_id'] or row['preparation_id']!=a['p1']['preparation_id']:raise ValueError()
                if row['verified_snapshot'] is not None and lc._sha(row['verified_snapshot'],row['cycle'])!=row['verified_sha256']:raise ValueError()
            elif ledger or final['revision']!=0:raise ValueError()
            if doc['state']=='SUCCEEDED':
                if len(events)!=len(actions) or a['p4_state']!='LOCAL_ACKNOWLEDGED' or a['p5_state']!=final['local_record_state']:raise ValueError()
                if actions[-1]=='REOPEN':
                    if final['cycle']!=2 or final['verification_current'] is not False or final['verified_snapshot_sha256'] is not None or set(final['required_rechecks'])!=set(lc.RECHECKS) or final['case_state']!='REOPENED':raise ValueError()
                elif final['verification_current'] is not True or final['case_state']!='WAITING_CONFIRMATION':raise ValueError()
        except (ValueError,KeyError,TypeError,IndexError):raise ValueError() from None
