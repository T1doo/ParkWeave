"""Bounded original P2 commands on disposable shadows; independent artifacts only."""
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID, uuid4
import json
import secrets

from psycopg import sql
from psycopg.types.json import Jsonb
from . import isolated_execution_preview as ep, resource_holds as rh, resource_combinations as rc
from . import case_resources as cr, preparation as prep, bounded_planning as planning
from .resource_preview_sql import RESOURCE_SQL
from .store import Store, Conflict, Denied, digest

SCOPE = 'ISOLATED_REGISTERED_P2_RESOURCE_EXECUTION_PREVIEW'
RESOURCES = (rh.RESOURCE_ID, rc.SECOND_RESOURCE_ID)
TABLES = ('principals','capability_grants','preparation_grants','preparation_catalog','preparations',
          'controlled_plans','runs','cases','synthetic_resources','synthetic_resource_grants',
          'synthetic_resource_holds','synthetic_resource_receipts','synthetic_resource_combinations',
          'synthetic_resource_combination_members','synthetic_resource_combination_receipts',
          'resource_case_claims','case_resource_links')
P2_ACTIONS = [{'method':'POST','path':'/api/preparations/{preparation_id}/resource-link',
               'role':'enterprise_operator','commands':['CREATE_OR_RECHECK_LINK']}]
CONTRACT = ep._sha(dict(storage_version=2,adapter='case-resources',revision=1,actions=P2_ACTIONS,
                       sql=sorted(RESOURCE_SQL),tables=TABLES,p1=ep.EXECUTION_CONTRACT_SHA256,
                       resource_ids=list(map(str,RESOURCES)),quantity=1,window_hours=1))
PROOF_FIELDS = (*ep.PROOF_FIELDS,'artifact','state')


def registered(current):
    selected = [s for s in current['steps'] if s['id']=='P2']
    return (ep._registered(current) and len(selected)==1 and selected[0]['depends_on']==['P1'] and
            selected[0]['adapter_ref']=='case-resources' and type(selected[0]['adapter_revision']) is int and
            selected[0]['adapter_revision']==1 and selected[0]['request_service_ref']==prep.SERVICE and
            type(selected[0]['request_service_version']) is int and selected[0]['request_service_version']==1 and
            ep._sha(selected[0]['actions'])==ep._sha(P2_ACTIONS))


class _Connection:
    def __init__(self, raw): self._raw = raw
    @property
    def autocommit(self): return self._raw.autocommit
    def execute(self, query, params=None):
        if type(query) is not str or query not in RESOURCE_SQL:
            raise Denied('unregistered P2 preview SQL template')
        return self._raw.execute(query, params)


class _Store(Store):
    def __init__(self, raw): self.connection = _Connection(raw)
    @contextmanager
    def connect(self): yield self.connection


class ResourceExecutionPreview(ep.IsolatedExecutionPreview):
    storage_scope = SCOPE
    attachment_attribute = '_isolated_resource_execution_preview'

    def _rules(self, c, p):
        result = []
        for id in sorted(RESOURCES,key=str):
            r = rh._scope(c,p,id,write=True)
            if (r['namespace']!='SYNTHETIC' or r['authority']!='LOCAL_AUTHORITY' or
                    not isinstance(r['source'],dict) or r['source'].get('kind')!='SYNTHETIC' or
                    not r['source'].get('id') or not r['source'].get('revision')):
                raise Conflict('known registered synthetic resource source required')
            result.append(ep._normal(r))
        return result

    def _source(self, store, c, token, id):
        p,parent,current = super()._source(store,c,token,id)
        # The actor/Case/catalogue locks precede resource locks, as on original
        # association routes. Only existing authorised fixed resources are read.
        for resource_id in sorted(RESOURCES,key=str):
            rh._scope(c,p,resource_id,write=True)
            rh._lock(c,resource_id,shared=True)
        current['resource_rules'] = self._rules(c,p)
        current['planning_source_sha256'] = current['source_sha256']
        current['source_sha256'] = ep._sha(dict(planning=current['planning_source_sha256'],resources=current['resource_rules']))
        return p,parent,current

    def _guard(self, store, c, token, p):
        super()._guard(store,c,token,p)
        self._rules(c,p)

    def _comparison(self, store, c, p, parent):
        current = planning._proposal(store,c,p,parent)
        rules = self._rules(c,p)
        return ep._sha(dict(planning=current['source_sha256'],resources=rules))

    def _view(self, db, p, parent, current):
        rows=db.execute('SELECT * FROM previews WHERE owner=? AND preparation=? ORDER BY rowid',(p['id'],str(parent['id']))).fetchall()
        history=[dict(document=self._document(row),source_state='SNAPSHOT_MATCH' if self._document(row)['binding']['source_sha256']==current['source_sha256'] else 'STALE') for row in rows]
        return dict(scope=SCOPE,enabled=True,preparation_id=str(parent['id']),namespace=self.namespace,history=history,
                    preparation_revision=parent['revision'],request_revision=parent['request_intent']['revision'],
                    current_source_sha256=current['source_sha256'],execution_available=registered(current),isolated_steps=['P1','P2'],
                    formal_writes=0,new_grants=False,case_goal_completed=False,source_atomicity=False,
                    source_consistency='COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON',capacity_scope='EMPTY_ISOLATED_SPACE_ONLY')

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
                           expected_request_revision=b['request_revision'],expected_source_sha256=b['source_sha256']))
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
            return doc
        except (ValueError,KeyError,TypeError):
            raise Conflict('isolated P2 artifact proof unavailable') from None

    def _capture_resources(self, connection, artifact, current, resource_ids):
        pass

    def _execute(self, store, parent, current, materials):
        p1 = super()._execute(store,parent,current,materials)
        artifact=dict(namespace='PREVIEW_EXECUTION',roles='SIMULATED_ROLES_ONLY',capacity_scope='EMPTY_ISOLATED_SPACE_ONLY',
                      p1=p1,prechecks=[],holds=[],receipts=[],combination=None,combination_receipts=[],links=[],claims=[],
                      error='P1_PREREQUISITE_FAILED' if p1['error'] else None,p2_state='NOT_EXECUTED')
        if p1['error']: return artifact
        c=Store(store.dsn).connect()
        try:
            if c.execute(ep.IDENTITY_SQL).fetchone()!=self.database_identity: raise Denied('original preview cluster required')
            for table in TABLES:
                c.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE public.{} INCLUDING DEFAULTS) ON COMMIT DROP').format(sql.Identifier(table),sql.Identifier(table)))
            c.execute('SET LOCAL search_path TO pg_temp')
            c.execute("SET LOCAL statement_timeout='3s'");c.execute("SET LOCAL lock_timeout='3s'")
            owner=p1['owner_id'];park='preview-park-'+uuid4().hex;org='preview-org-'+uuid4().hex
            token=secrets.token_urlsafe(32);id=UUID(p1['preparation_id']);run=UUID(p1['run_id']);case=UUID(p1['case_id'])
            c.execute("INSERT INTO principals(id,token_hash,park_id,org_id,role,active) VALUES(%s,%s,%s,%s,'enterprise_operator',true)",(owner,digest(token),park,org))
            for cap in ('READ','EXECUTE'): c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(owner,cap,park,org))
            c.execute("INSERT INTO preparation_grants(principal_id,capability,park_id,org_id,active) VALUES(%s,'PREPARE',%s,%s,true)",(owner,park,org))
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state) VALUES(%s,%s,%s,%s,'SYNTHETIC',%s,%s,'{}','SUCCEEDED')",(run,owner,park,org,uuid4().hex,ep._sha(p1)))
            c.execute("INSERT INTO cases VALUES(%s,%s,%s,%s,'SYNTHETIC isolated P2','NEEDS_INPUT','SYNTHETIC','NOT_SUBMITTED','NO_EVIDENCE')",(case,run,park,org))
            c.execute("INSERT INTO preparations(id,run_id,case_id,owner_id,reviewer_id,park_id,org_id,service_id,service_version,namespace,goal,state,revision,review_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,1,'PREVIEW_EXECUTION','SYNTHETIC isolated P2','LOCAL_CONFIRMED',%s,%s)",(id,run,case,owner,p1['reviewer_id'],park,org,prep.SERVICE,p1['revision'],p1['review_sha256']))
            c.execute("INSERT INTO preparation_catalog(park_id,service_id,version,name,source,namespace,qualification) VALUES(%s,%s,1,'Synthetic P2 preview',%s,'SYNTHETIC','NOT_EVALUATED')",(park,prep.SERVICE,Jsonb(dict(kind='SYNTHETIC',id='P2-preview',revision='1'))))
            ids=[]
            for rule in current['resource_rules']:
                resource_id=uuid4();ids.append(resource_id)
                c.execute('INSERT INTO synthetic_resources VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(resource_id,park,'SYNTHETIC isolated resource',rule['revision'],rule['capacity'],rule['buffer_seconds'],rule['open_from'],rule['open_until'],rule['enabled'],rule['timezone'],rule['namespace'],rule['authority'],Jsonb(rule['source'])))
                for cap in ('READ','HOLD'): c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true)',(owner,resource_id,park,org,cap))
            private=_Store(c);now=rh._now(c);window=rh.Preview(starts_at=now+timedelta(hours=1),ends_at=now+timedelta(hours=2),quantity=1)
            try:
                for resource_id,rule in zip(ids,current['resource_rules']):
                    artifact['prechecks'].append(ep._normal(rh.preview(private,token,resource_id,window)))
                    rh.create(private,token,resource_id,uuid4().hex,rh.Hold(**window.model_dump(),expected_revision=rule['revision'],purpose='SYNTHETIC PREVIEW only'))
                holds=c.execute('SELECT * FROM synthetic_resource_holds ORDER BY id').fetchall()
                combined=rc.confirm(private,token,uuid4().hex,rc.Combination(members=[rc.Member(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds]))
                artifact['combination']=ep._normal(combined['combination'])
                cr.bind(private,token,id,uuid4().hex,cr.Bind(combination_id=combined['combination']['id'],expected_preparation_revision=p1['revision'],expected_link_revision=0,reason='SYNTHETIC PREVIEW only'))
                artifact['p2_state']='LOCAL_ASSOCIATION_PREVIEWED'
            except Conflict:
                artifact['error']='RESOURCE_PREREQUISITE_FAILED';artifact['p2_state']='FAILED'
            for name,table in (('holds','synthetic_resource_holds'),('receipts','synthetic_resource_receipts'),('combination_receipts','synthetic_resource_combination_receipts'),('links','case_resource_links'),('claims','resource_case_claims')):
                artifact[name]=ep._normal(c.execute(sql.SQL('SELECT * FROM {} ORDER BY 1').format(sql.Identifier(table))).fetchall())
            self._capture_resources(c,artifact,current,ids)
            return artifact
        finally:
            c.rollback();c.close()

    def execute(self, store, token, id, key, data):
        with store.connect() as c:
            p,parent,current=self._source(store,c,token,id);fp=ep._sha({'preparation_id':str(id),**data.model_dump()})
            with self._database() as db:
                db.execute('BEGIN EXCLUSIVE');self._guard(store,c,token,p)
                old=db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone()
                if old:
                    if old['preparation']!=str(id) or old['fingerprint']!=fp: raise Conflict('P2 preview key body or scope mismatch')
                    return {**self._view(db,p,parent,current),'result':self._document(old)}
                if (parent['revision']!=data.expected_preparation_revision or parent['request_intent']['revision']!=data.expected_request_revision or current['source_sha256']!=data.expected_source_sha256): raise Conflict('P2 preview sources changed; explicitly read current proposal')
                if not registered(current): raise Conflict('exact registered P1/P2 action and service contract required')
                if db.execute('SELECT count(*) FROM previews').fetchone()[0]>=128 or db.execute('SELECT count(*) FROM previews WHERE preparation=?',(str(id),)).fetchone()[0]>=16: raise Conflict('bounded P2 preview history limit reached')
                materials=prep.latest(c,id);artifact=self._execute(store,parent,current,materials);self._guard(store,c,token,p)
                if self._comparison(store,c,p,parent)!=current['source_sha256']: raise Conflict('P2 preview sources changed during execution')
                result=dict(scope=SCOPE,version=2,id=str(uuid4()),namespace=self.namespace,actor_id=p['id'],request_key=key,fingerprint=fp,
                            binding=dict(preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),service_id=parent['service_id'],service_version=parent['service_version'],preparation_revision=parent['revision'],request_revision=parent['request_intent']['revision'],source_sha256=current['source_sha256'],resource_rules=current['resource_rules'],slots=[{k:str(m[k]) if isinstance(m[k],UUID) else m[k] for k in ('id','slot','version','source_sha256')} for m in materials]),
                            execution_contract_sha256=CONTRACT,state='FAILED' if artifact['error'] else 'SUCCEEDED',coverage_state='P1_P2_PREVIEW_ONLY' if all(g in ('LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION') for g in current['required_goals']) else 'PARTIAL_PREVIEW',required_goals=current['required_goals'],not_previewed=[s['id'] for s in current['steps'] if s['id'] not in ('P1','P2') or (s['id']=='P2' and artifact['p2_state']=='NOT_EXECUTED')],goal_coverage=current['goal_coverage'],artifact=artifact,formal_writes=0,new_grants=False,case_goal_completed=False,qualification='NOT_EVALUATED',external_acceptance='NOT_SUBMITTED',offline_fulfillment='NO_EVIDENCE')
                result['sha256']=ep._sha(result);document=prep.canonical(result);proof=prep.canonical({k:result[k] for k in PROOF_FIELDS})
                if max(len(document.encode()),len(proof.encode()))>65536: raise Conflict('bounded P2 artifact bytes exceeded')
                db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?)',(p['id'],str(id),key,fp,document,proof))
                self._document(db.execute('SELECT * FROM previews WHERE owner=? AND request_key=?',(p['id'],key)).fetchone());self._guard(store,c,token,p);db.commit()
                current['source_sha256']=self._comparison(store,c,p,parent)
                return {**self._view(db,p,parent,current),'result':result}
