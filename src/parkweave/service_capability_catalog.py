"""Explicit owned-fixture capability metadata; no application publication route.

The original TemplateEngine supplies current reviewed immutable releases. This
layer derives registered service contracts and independently binds park data.
Metadata never supplies identities, grants, Case materials or business results.
"""
from copy import deepcopy
from contextlib import contextmanager
import sqlite3
import threading
from urllib.parse import quote
from pathlib import Path
import json
import re
from uuid import uuid4,uuid5,NAMESPACE_URL
from psycopg.types.json import Jsonb
from . import bounded_planning as bp
from . import service_capability_contract as contract
from .store import Conflict, Denied

SCOPE='ISOLATED_SERVICE_CAPABILITIES_V1'
COL='service_capability_catalog'
LIMIT=64


def event_view(event):
    result=deepcopy(event)
    for name in ('release','instance'):
        if name in event['record']:result[name]=deepcopy(event['record'][name])
    return result


def lock(c,park_id,exclusive=False):
    # A global set gate covers portable release lookup and new park inserts.
    fn='pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
    c.execute('SELECT '+fn+'(hashtextextended(%s,0))',('service-capability-universe',))
    name='service-capability-set:'+contract.canonical(park_id)
    fn='pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
    c.execute('SELECT '+fn+'(hashtextextended(%s,0))',(name,))


def row(c,park_id,write=False):
    return c.execute("SELECT * FROM preparation_catalog WHERE park_id=%s AND service_id='synthetic-material-preparation' AND version=1"+(' FOR UPDATE' if write else ''),(park_id,)).fetchone()


def proof(value):
    journal=(value or {}).get(COL)
    if journal is None:return dict(scope=SCOPE,revision=0,events=[])
    try:
        if type(journal) is not dict or set(journal)!={'scope','revision','events'} or journal['scope']!=SCOPE or type(journal['revision']) is not int or not 1<=journal['revision']<=LIMIT or type(journal['events']) is not list or len(journal['events'])!=journal['revision']:raise ValueError()
        previous=None;keys=set();ids=set()
        for n,event in enumerate(journal['events'],1):
            if (type(event) is not dict or set(event)!={'id','revision','action','park_id','key','request','fingerprint','actor','record','previous_sha256','sha256'} or
                event['revision']!=n or type(event['revision']) is not int or event['park_id']!=value['park_id'] or
                event['action'] not in ('ADD_RELEASE','BIND_INSTANCE','WITHDRAW_RELEASE','WITHDRAW_INSTANCE') or
                event['key'] in keys or event['id'] in ids or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',event['key']) or
                event['fingerprint']!=contract.digest(event['request']) or event['previous_sha256']!=previous or
                event['sha256']!=contract.digest({k:v for k,v in event.items() if k!='sha256'})):raise ValueError()
            from uuid import UUID
            UUID(event['id']);keys.add(event['key']);ids.add(event['id']);previous=event['sha256']
    except (KeyError,TypeError,ValueError,AttributeError):raise Conflict('original capability journal proof invalid')
    return deepcopy(journal)


def fold(journal):
    releases={};instances={}
    for event in journal['events']:
        data=event['record']
        if event['action']=='ADD_RELEASE':
            id=data['release']['release_id']
            if id in releases:raise Conflict('immutable capability release id reused')
            releases[id]=dict(**deepcopy(data),state='ACTIVE')
        elif event['action']=='BIND_INSTANCE':
            value=data['instance'];old=instances.get(value['instance_id'])
            if old and value['config_revision']!=old['instance']['config_revision']+1 or not old and value['config_revision']!=1:raise Conflict('instance configuration revision changed')
            instances[value['instance_id']]=dict(**deepcopy(data),state='ACTIVE')
        else:
            table=instances if event['action']=='WITHDRAW_INSTANCE' else releases
            target=table.get(data['id'])
            if target is None or target['state']!='ACTIVE':raise Conflict('capability withdrawal history invalid')
            target['state']='WITHDRAWN'
    return releases,instances


class IsolatedServiceCapabilityCatalog:
    def __init__(self,consumer,owner,*,enabled_for_isolated_tests=False):
        from .template_consumer import TemplateConsumer
        from .case_fact_clarifications import FixtureDatabaseEvidence
        if enabled_for_isolated_tests is not True or type(consumer) is not TemplateConsumer or type(getattr(owner,'_case_fact_fixture_receipt',None)) is not FixtureDatabaseEvidence:raise Denied('explicit owned isolated capability fixture required')
        self.consumer,self.owner,self.engine=consumer,owner,consumer.template_engine
        self._local=threading.local()
        self.database=consumer.validate_fixture()
        self.orgs={(s.park_id,s.org_id) for s in consumer.config.allowed_orgs}
        with owner.connect() as c:self._owner(c)

    @contextmanager
    def source_lease(self):
        # BEGIN IMMEDIATE is the original source repository's durable publication
        # gate. Other TemplateEngine instances must wait until the PG commit.
        if getattr(self._local,'source',None) is not None:
            yield self._local.source;return
        if self.engine.repository is None:raise Denied('original durable reviewed source required')
        with self.engine.repository.transaction() as connection:
            self._local.source=connection
            try:yield connection
            finally:self._local.source=None

    @contextmanager
    def owner_connection(self):
        with self.source_lease():
            with self.owner.connect() as connection:yield connection

    @contextmanager
    def connection(self):
        # Short application save/adoption transactions only; never model wait.
        with self.source_lease():
            with self.consumer.store.connect() as connection:yield connection

    @contextmanager
    def read_connection(self):
        # Historical reads must not depend on a current publication writer lease.
        with self.consumer.store.connect() as connection:yield connection

    def _owner(self,c):
        self.owner._case_fact_fixture_receipt.authorize_migration(c)
        actual=c.execute('SELECT current_database() name,current_user=session_user AND current_user=pg_get_userbyid(datdba) own FROM pg_database WHERE datname=current_database()').fetchone()
        if not actual or actual['name']!=self.database or not actual['own']:raise Denied('original fixture database owner required')
        def schema_for(name):
            return c.execute("SELECT t.tgenabled,t.tgtype,t.tgattr::text attrs,f.prosecdef,f.proconfig,f.prosrc,"
                " f.proowner=r.relowner correct_owner,l.lanname,f.oid=to_regprocedure(%s) exact_function"
                " FROM pg_trigger t JOIN pg_proc f ON f.oid=t.tgfoid JOIN pg_class r ON r.oid=t.tgrelid"
                " JOIN pg_language l ON l.oid=f.prolang WHERE t.tgrelid='public.preparation_catalog'::regclass"
                " AND t.tgname=%s AND NOT t.tgisinternal",('public.'+name+'()',name)).fetchone()
        def intact(value,kind,body):
            return bool(value and value['tgenabled']=='O' and value['tgtype']==kind and value['attrs']==''
                and not value['prosecdef'] and value['proconfig'] is None and value['correct_owner']
                and value['lanname']=='plpgsql' and value['exact_function'] and value['prosrc'].strip()==body.strip())
        schema=schema_for('service_capability_prefix')
        expected=Path(__file__).with_name('migration-033.sql').read_text().split('AS $$\n',1)[1].split('\n$$;',1)[0]
        if not intact(schema,27,expected):raise Denied('owned immutable capability schema required')
        truncate=schema_for('service_capability_no_truncate')
        expected=Path(__file__).with_name('migration-033.sql').read_text().split('$truncate_expected$\n',1)[1].split('\n$truncate_expected$',1)[0]
        if not intact(truncate,34,expected):raise Denied('owned immutable capability truncate schema required')

    def _scope(self,park,org=None):
        if not any(p==park and (org is None or o==org) for p,o in self.orgs):raise Denied('approved current fixture park/organization required')
        self.consumer.validate_fixture()

    def _append(self,c,value,key,action,request,record):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key):raise Conflict('bounded original capability request key required')
        journal=proof(value);prior=next((e for e in journal['events'] if e['key']==key),None)
        if prior:
            if prior['action']!=action or prior['request']!=request:raise Conflict('capability original key parameters changed')
            return event_view(prior)
        if journal['revision']>=LIMIT:raise Conflict('capability journal capacity reached')
        event=dict(id=str(uuid4()),revision=journal['revision']+1,action=action,park_id=value['park_id'],key=key,request=request,
                   fingerprint=contract.digest(request),actor=self.owner._case_fact_fixture_receipt.cluster.owner,record=record,
                   previous_sha256=journal['events'][-1]['sha256'] if journal['events'] else None)
        event['sha256']=contract.digest(event);journal['events'].append(event);journal['revision']+=1
        updated=c.execute('UPDATE preparation_catalog SET service_capability_catalog=%s WHERE park_id=%s AND service_id=%s AND version=%s AND service_capability_catalog IS NOT DISTINCT FROM %s RETURNING *',
                          (Jsonb(journal),value['park_id'],value['service_id'],value['version'],Jsonb(value[COL]) if value[COL] is not None else None)).fetchone()
        if updated is None:raise Conflict('capability journal CAS changed')
        fold(proof(updated));return event_view(event)

    def _source(self,scope,id,sha):
        from .template_candidate import Scope
        scope=Scope.model_validate(scope)
        def resolve(connection):
            self.engine._enabled(connection)
            entry=connection.execute('SELECT * FROM template_releases WHERE id=? AND scope=?',(str(id),contract.canonical(scope.model_dump()))).fetchone()
            if entry is None:raise Denied('original scoped reviewed release required')
            value=self.engine._available(connection,entry)
            if not value['candidate_available']:raise Denied('original reviewed service source unavailable: '+str(value['availability_reason']))
            if value['release_sha256']!=sha:raise Conflict('original reviewed release hash changed')
            return dict(**value['snapshot'],release_sha256=value['release_sha256'])
        leased=getattr(self._local,'source',None)
        if leased is not None:return resolve(leased)
        # Standalone catalog GET is a point-in-time read, not an adoption lease.
        # Read-only SQLite avoids PG->writer-gate inversion against mutations.
        try:
            with sqlite3.connect('file:'+quote(str(self.engine.repository.path),safe='/')+'?mode=ro',uri=True,timeout=3) as connection:
                connection.row_factory=sqlite3.Row
                return resolve(connection)
        except sqlite3.Error:raise Denied('original durable reviewed source unavailable') from None

    def register_release(self,park_id,owner_org_id,key,*,template_scope,template_release_id,expected_template_release_sha256,service_id):
        self._scope(park_id,owner_org_id)
        scope=template_scope.model_dump() if hasattr(template_scope,'model_dump') else template_scope
        request=dict(owner_org_id=owner_org_id,template_scope=scope,template_release_id=str(template_release_id),expected_template_release_sha256=expected_template_release_sha256,service_id=service_id)
        with self.owner_connection() as c:
            self._owner(c);lock(c,park_id,True);value=row(c,park_id,True)
            if not value:raise Conflict('original fixture service catalogue required')
            old=next((e for e in proof(value)['events'] if e['key']==key),None)
            if old:return self._append(c,value,key,'ADD_RELEASE',request,{})
            source=self._source(scope,str(template_release_id),expected_template_release_sha256)
            release=self._derive_release(source,owner_org_id,service_id)
            record=dict(release=release,template_scope=scope,registry=deepcopy(bp.REGISTRY),actions=deepcopy(bp.ACTIONS))
            return self._append(c,value,key,'ADD_RELEASE',request,record)

    def _derive_release(self,source,owner_org_id,service_id):
        definition=source['definition']
        if service_id not in contract.SERVICE_GOALS:raise Conflict('finite registered capability service kind required')
        goals=[g for g in definition['required_goals'] if g in contract.SERVICE_GOALS[service_id]]
        if not goals:raise Conflict('reviewed source does not cover this capability kind')
        _,steps=bp.compile(goals)
        ids=[s['id'] for s in steps];fields=['need_summary','material_outline'];resources=['primary','secondary'] if 'P2' in ids else []
        source_rule=definition['source']
        release=dict(schema_version=1,service_id=service_id,release_id=str(uuid5(NAMESPACE_URL,SCOPE+':'+service_id+':'+source['release_id'])),revision=source['content_version'],owner_org_id=owner_org_id,title=definition['name'],supported_goals=goals,steps=steps,
                     role_keys=sorted({a['role'] for id in ids for a in bp.ACTIONS[id]}),resource_keys=resources,field_keys=fields,
                     material_requirements=[dict(field_key=f,purpose='CURRENT_CASE_MATERIAL_PREPARATION') for f in fields],resource_requirements=[dict(resource_key=r,required=True) for r in resources],
                     completion_checks=[contract.CHECKS[id] for id in ids],validity=source['validity'],business_publication=False,
                     source_review=dict(template_release_id=source['release_id'],template_release_sha256=source['release_sha256'],definition_sha256=source['definition_sha256'],registry_sha256=source['registry_sha256'],
                                        review_revision=source['review']['revision'],review_action=source['review']['action'],source_id=source_rule['id'],source_revision=source_rule['revision'],source_sha256=contract.digest(source_rule),validity=source_rule['validity']))
        release['release_sha256']=contract.hash_release(release);release=contract.validate_release(release,now=self.engine.clock())
        return release

    def _current_release(self,record):
        release=contract.validate_release(record['release'],now=self.engine.clock());ref=release['source_review']
        source=self._source(record['template_scope'],ref['template_release_id'],ref['template_release_sha256'])
        if source['definition_sha256']!=ref['definition_sha256'] or source['review']['revision']!=ref['review_revision'] or source['registry_sha256']!=ref['registry_sha256'] or contract.digest(source['definition']['source'])!=ref['source_sha256']:raise Conflict('current reviewed service source changed')
        if release!=self._derive_release(source,release['owner_org_id'],release['service_id']):raise Conflict('capability differs from original trusted reviewed definition')
        return release

    def bind_instance(self,park_id,key,instance):
        self._scope(park_id)
        with self.owner_connection() as c:
            self._owner(c);value=row(c,park_id)
            if not value:raise Conflict('original fixture service catalogue required')
            if instance.get('park_id')!=park_id:raise Denied('instance park mismatch')
            old=next((e for e in proof(value)['events'] if e['key']==key),None)
            if old:
                lock(c,park_id,True);value=row(c,park_id,True)
                return self._append(c,value,key,'BIND_INSTANCE',instance,{})
            data=contract.validate_instance(instance,self._current_release(self._release_record(c,value,instance.get('release_id'))),now=self.engine.clock())
            # Original resource business routes can hold resource EXCLUSIVE
            # before inspecting the plan's capability collection. Do not take
            # the collection EXCLUSIVE gate before waiting on those resources.
            self.mapping_states(c,data)
            lock(c,park_id,True);value=row(c,park_id,True)
            if any(e['key']==key for e in proof(value)['events']):return self._append(c,value,key,'BIND_INSTANCE',instance,{})
            latest=contract.validate_instance(instance,self._current_release(self._release_record(c,value,instance.get('release_id'))),now=self.engine.clock())
            if latest!=data:raise Conflict('instance contract changed while acquiring collection gate')
            self.mapping_states(c,data)
            return self._append(c,value,key,'BIND_INSTANCE',instance,dict(instance=data))

    def _release_record(self,c,value,id):
        releases,_=fold(proof(value));record=releases.get(id)
        if record is None:
            matches=[]
            for other in c.execute("SELECT * FROM preparation_catalog WHERE service_id='synthetic-material-preparation' AND version=1 AND service_capability_catalog IS NOT NULL ORDER BY park_id").fetchall():
                published,_=fold(proof(other))
                if id in published:matches.append(published[id])
            if len(matches)!=1:raise Conflict('unique portable release reference required')
            record=matches[0]
        if record['state']!='ACTIVE':raise Conflict('active exact release required')
        return record

    def mapping_states(self,c,instance,parent=None):
        return current_mapping_states(self.consumer.store,self.orgs,c,instance,parent)

    def snapshot(self,c,parent):
        self._scope(parent['park_id'],parent['org_id']);lock(c,parent['park_id'])
        value=row(c,parent['park_id']);journal=proof(value);releases,instances=fold(journal)
        collections=[dict(park_id=parent['park_id'],revision=journal['revision'],sha256=contract.digest(journal))]
        # Portable releases are definitions; only this park's instances supply identities/data.
        for other in c.execute("SELECT * FROM preparation_catalog WHERE service_id='synthetic-material-preparation' AND version=1 AND service_capability_catalog IS NOT NULL ORDER BY park_id").fetchall():
            if other['park_id']==parent['park_id']:continue
            portable=proof(other)
            collections.append(dict(park_id=other['park_id'],revision=portable['revision'],sha256=contract.digest(portable)))
            published,_=fold(portable)
            for id,record in published.items():
                if id in releases and releases[id]!=record:raise Conflict('portable release identity ambiguous')
                releases[id]=record
        current=[];configs=[];states=dict(principals={},resources={},fields={});unknowns=[]
        for record in releases.values():
            if record['state']!='ACTIVE':continue
            try:current.append(self._current_release(record))
            except (ValueError,Conflict,Denied):unknowns.append(record['release']['release_id'])
        by_id={r['release_id']:r for r in current}
        for record in instances.values():
            data=record['instance']
            if record['state']!='ACTIVE' or data['release_id'] not in by_id or data['roles']['enterprise_operator']!=parent['owner_id']:continue
            try:
                data=contract.validate_instance(data,by_id[data['release_id']],now=self.engine.clock());mapping=self.mapping_states(c,data,parent)
                for name in states:states[name].update(mapping[name])
                configs.append(data)
            except (ValueError,Conflict,Denied):unknowns.append(data['instance_id'])
        current.sort(key=lambda r:r['release_id']);configs.sort(key=lambda r:r['instance_id'])
        collections.sort(key=lambda collection:collection['park_id'])
        basis=dict(park_id=parent['park_id'],journal=journal,source_collections=collections,releases=current,instances=configs,mapping_states=states,unknowns=sorted(unknowns))
        return dict(scope=SCOPE,revision=journal['revision'],sha256=contract.digest(basis),releases=current,instances=configs,mapping_states=states,unknowns=sorted(unknowns),business_publication=False,new_grants=False)

    def _withdraw(self,park,key,id,expected_revision,reason,action):
        self._scope(park)
        if not isinstance(reason,str) or not reason.strip():raise Conflict('explicit withdrawal reason required')
        request=dict(id=id,expected_revision=expected_revision,reason=reason)
        with self.owner_connection() as c:
            self._owner(c);lock(c,park,True);value=row(c,park,True);journal=proof(value)
            if any(e['key']==key for e in journal['events']):return self._append(c,value,key,action,request,{})
            if type(expected_revision) is not int or journal['revision']!=expected_revision:raise Conflict('catalogue withdrawal revision changed')
            releases,instances=fold(journal);target=(instances if action=='WITHDRAW_INSTANCE' else releases).get(id)
            if not target or target['state']!='ACTIVE':raise Conflict('active capability required for withdrawal')
            return self._append(c,value,key,action,request,dict(id=id))

    def withdraw_release(self,park_id,key,release_id,expected_revision,reason):return self._withdraw(park_id,key,release_id,expected_revision,reason,'WITHDRAW_RELEASE')
    def withdraw_instance(self,park_id,key,instance_id,expected_revision,reason):return self._withdraw(park_id,key,instance_id,expected_revision,reason,'WITHDRAW_INSTANCE')


def current_mapping_states(store,orgs,c,instance,parent=None):
    """Existing identity/resource intersection, shared without fixture authority."""
    states=dict(principals={},resources={},fields={})
    roles=instance['roles']
    for id in sorted(roles.values()):store.lock_principal(c,id)
    owner=c.execute('SELECT * FROM principals WHERE id=%s',(roles['enterprise_operator'],)).fetchone()
    if not owner or not owner['active'] or owner['park_id']!=instance['park_id'] or (instance['park_id'],owner['org_id']) not in orgs or parent and owner['id']!=parent['owner_id']:raise Denied('current instance enterprise reference unavailable')
    for role,id in roles.items():
        p=c.execute('SELECT * FROM principals WHERE id=%s',(id,)).fetchone()
        if not p or not p['active'] or p['role']!=role or p['park_id']!=instance['park_id'] or role=='park_specialist' and p['org_id']!=owner['org_id']:raise Denied('current same-park role reference required')
        store.check_capability(c,p,'READ')
        if role in ('enterprise_operator','park_specialist'):
            from . import preparation
            preparation.grant(store,c,p,'PREPARE' if role=='enterprise_operator' else 'REVIEW_ASSIGNED')
        if role=='enterprise_operator':store.check_capability(c,p,'EXECUTE')
        if parent and role=='park_specialist' and id!=parent['reviewer_id']:raise Denied('current Case reviewer mapping required')
        states['principals'][id]='TRUE'
    from . import resource_holds
    for id in sorted(instance['resources'].values()):
        from uuid import UUID
        try:
            resource_id=UUID(id)
            if id!=str(resource_id):raise ValueError()
        except (ValueError,TypeError,AttributeError):raise Denied('existing exact resource UUID required') from None
        resource_holds._lock(c,resource_id,shared=True)
        resource=c.execute('SELECT * FROM synthetic_resources WHERE id=%s',(id,)).fetchone()
        grants=c.execute("SELECT capability FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=%s AND park_id=%s AND org_id=%s AND active",(owner['id'],id,owner['park_id'],owner['org_id'])).fetchall()
        if not resource or resource['park_id']!=instance['park_id'] or not resource['enabled'] or resource['namespace']!='SYNTHETIC' or not {'READ','HOLD'}<={v['capability'] for v in grants}:raise Denied('current own-park resource READ/HOLD required')
        states['resources'][id]='TRUE'
    for mapping in instance['fields'].values():states['fields'][mapping['input_field']]='TRUE'
    return states

