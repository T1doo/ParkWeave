"""Owned-fixture, single-Case ServiceRelease comparison and private evidence.

The existing ConsumerRepository schema is reused in a separate journal. A
record is an immutable observation, never publication, migration, approval or
business execution. Source/PG/journal transactions are not a distributed commit.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import re
import sqlite3
from urllib.parse import quote
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from . import preparation as prep, controlled_plans as cp, bounded_planning as bp
from . import service_case_steps as service, service_selection_candidates as selection
from . import service_selection as refs, service_capability_contract as contract
from . import service_capability_catalog as catalog_module
from . import source_change_adoption as adoption, typed_source_impact as typed
from . import registered_dependencies as dependencies
from .executor_receipts import bounded
from .store import Conflict, Denied
from .template_consumer import ConsumerRepository

SCOPE='OWNED_SYNTHETIC_SERVICE_RELEASE_PREFLIGHT'
SCHEMA=1
MAX_RECORDS=64
MAX_TARGETS=16
FLAGS=dict(read_only=True,automatically_replayed=False,automatic_migration=False,
           automatic_adoption=False,automatic_execution=False,execution_enabled=False,
           provider_enabled=False,new_grants=False,business_publication=False,
           case_goal_completed=False,qualification_decision='NOT_EVALUATED',future_validity_guaranteed=False)


class Reference(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    release_id:str=Field(min_length=1,max_length=120)
    revision:int=Field(ge=1,le=64)
    release_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    instance_id:str=Field(min_length=1,max_length=120)
    config_revision:int=Field(ge=1,le=64)
    config_sha256:str=Field(pattern='^[a-f0-9]{64}$')


class Record(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    original_ref:Reference
    target_ref:Reference
    expected_plan_revision:int=Field(ge=1,le=64)
    expected_preflight_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    reason:str=Field(min_length=1,max_length=1000)


def _hash(value):return cp._hash(cp._normal(value))


def _difference(field,before,after,category):
    return dict(field=field,category=category,before_sha256=_hash(before),after_sha256=_hash(after))


def compare_v1(plan,old,original_instance,target,target_instance,old_source,target_source,frozen):
    """Exhaustive finite contract comparison; no current authority is inferred."""
    differences=[];roots=set();breaking=[]
    # Strict models reject unknown fields. Every accepted field is covered by
    # one explicit group, including provenance/identity fields that are metadata.
    info={'title','release_id','release_sha256','revision'}
    source={'validity','source_review'}
    hard={'schema_version','service_id','owner_org_id','steps','role_keys','resource_keys',
          'field_keys','material_requirements','resource_requirements','completion_checks','business_publication'}
    if set(old)!=info|source|hard|{'supported_goals'} or set(target)!=set(old):
        raise Conflict('unsupported finite release comparison schema')
    if old_source['scope']!=target_source['scope']:breaking.append('SOURCE_TEMPLATE_FAMILY_CHANGED')
    if target['release_id']!=old['release_id'] and target['revision']<=old['revision']:breaking.append('RELEASE_ROLLBACK_OR_NONFORWARD')
    if not set(old['supported_goals'])<=set(target['supported_goals']):breaking.append('ORIGINAL_SERVICE_GOAL_REMOVED')
    for key in sorted(info|hard|{'supported_goals','validity'}):
        if _hash(old[key])==_hash(target[key]):continue
        category='INFORMATIONAL' if key in info else 'SOURCE' if key=='validity' else 'CONTRACT'
        differences.append(_difference(key,old[key],target[key],category))
        if key in hard:breaking.append('REGISTERED_SERVICE_CONTRACT_CHANGED')
        if key in ('supported_goals','validity'):roots|={s['id'] for s in old['steps']+target['steps']}
    # Publication identity changes are evidence, not by themselves a semantic
    # rule change. Actual source identity/revision/hash/validity is compared.
    old_rule={k:old['source_review'][k] for k in ('source_id','source_revision','source_sha256','validity')}
    new_rule={k:target['source_review'][k] for k in old_rule}
    if _hash(old_rule)!=_hash(new_rule):
        differences.append(_difference('source_review.rule',old_rule,new_rule,'SOURCE'))
        roots|={s['id'] for s in old['steps']+target['steps']}
    if _hash(old['source_review'])!=_hash(target['source_review']):
        differences.append(_difference('source_review.publication',old['source_review'],target['source_review'],'INFORMATIONAL'))
    if _hash(frozen)!=_hash(dict(steps=bp.REGISTRY,actions=bp.ACTIONS)):
        breaking.append('REGISTERED_ACTION_PROFILE_CHANGED')
    if any(old_source[k]!=target_source[k] for k in ('contract_sha256','registry_sha256')):
        breaking.append('SOURCE_EXECUTABLE_CONTRACT_CHANGED')
    if any(_hash(old_source['definition'][k])!=_hash(target_source['definition'][k]) for k in ('service_id','service_version','parameter_schema')):
        breaking.append('SOURCE_SERVICE_OR_INPUT_CONTRACT_CHANGED')
    if not {s['id'] for s in target['steps']}<={s['adapter_id'] for s in plan['steps']}:
        breaking.append('TARGET_REQUIRES_UNADOPTED_CASE_STEP')
    for key in ('roles','resources','fields','source'):
        if _hash(original_instance[key])==_hash(target_instance[key]):continue
        differences.append(_difference('instance.'+key,original_instance[key],target_instance[key],'MAPPING'))
        roots|=({'P2'} if key=='resources' else {'P3'} if key=='roles' else {'P1'})
    affected=dependencies.closure(plan['steps'],roots)
    return dict(classification='BREAKING_REJECTED' if breaking else 'NEEDS_RECHECK' if roots else 'COMPATIBLE',
        differences=differences,affected=[s['id'] for s in plan['steps'] if s['adapter_id'] in affected],
        blocking_reasons=sorted(set(breaking)))


class ServiceReleasePreflight:
    def __init__(self,catalog,repository,*,enabled_for_isolated_tests=False):
        if enabled_for_isolated_tests is not True or type(catalog) is not catalog_module.IsolatedServiceCapabilityCatalog:
            raise Denied('isolated ServiceRelease preflight disabled')
        if type(repository) is not ConsumerRepository or repository.path==catalog.consumer.repository.path:
            raise Denied('separate exact isolated preflight journal required')
        self.catalog,self.repository,self.consumer=catalog,repository,catalog.consumer
        self.store,self.engine=self.consumer.store,catalog.engine
        self.consumer.validate_fixture()
        with repository.connect() as journal:
            saved_rows=journal.execute('SELECT binding FROM consumer_instances LIMIT 65').fetchall()
            if len(saved_rows)>MAX_RECORDS:raise Denied('bounded dedicated preflight evidence journal required')
            for saved in saved_rows:
                try:valid=json.loads(saved['binding']).get('kind')==SCOPE
                except (ValueError,TypeError,AttributeError):valid=False
                if not valid:raise Denied('dedicated ServiceRelease preflight evidence journal required')

    def _context(self,c,token,id,*,historical=False):
        self.consumer.validate_fixture()
        if historical:
            p=self.store.auth(c,token,lock=True);self.store.check_capability(c,p,'READ')
            parent=c.execute('SELECT * FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s',(id,p['park_id'],p['org_id'])).fetchone()
            if not parent or parent['owner_id']!=p['id']:raise Denied('own original preflight Case required')
            self.store.scoped_run(c,p,parent['run_id'])
        else:p,parent=service._context(self.store,c,token,id)
        if p['role']!='enterprise_operator' or parent['namespace']!='SYNTHETIC' or parent['service_id']!=prep.SERVICE or (p['park_id'],p['org_id']) not in self.catalog.orgs:
            raise Denied('current approved original Case owner required')
        return p,parent

    @contextmanager
    def _source_connection(self):
        leased=getattr(self.catalog._local,'source',None)
        if leased is not None:yield leased;return
        try:
            with sqlite3.connect('file:'+quote(str(self.engine.repository.path),safe='/')+'?mode=ro',uri=True,timeout=3) as c:
                c.row_factory=sqlite3.Row;yield c
        except sqlite3.Error:raise Conflict('original source repository busy or unavailable') from None

    def _historical_source(self,release):
        ref=release['source_review']
        with self._source_connection() as t:
            row=t.execute('SELECT * FROM template_releases WHERE id=?',(ref['template_release_id'],)).fetchone()
            if row is None:raise Conflict('original immutable service source missing')
            source=json.loads(row['payload'])
            if (_hash(source)!=row['payload_sha'] or row['payload_sha']!=ref['template_release_sha256'] or
                _hash(source['definition'])!=source['definition_sha256'] or source['definition_sha256']!=ref['definition_sha256'] or
                source['registry_sha256']!=ref['registry_sha256'] or source['review']['revision']!=ref['review_revision'] or
                source['review']['action']!=ref['review_action'] or _hash(source['definition']['source'])!=ref['source_sha256'] or
                source['definition']['source']['id']!=ref['source_id'] or source['definition']['source']['revision']!=ref['source_revision']):
                raise Conflict('original immutable service source proof changed')
            return source

    def _originals(self,parent):
        plan=parent.get('service_case_plan')
        version=(plan.get('candidate_consumption') or {}).get('verification_basis',{}).get('validator_version') if isinstance(plan,dict) else None
        if type(version) is not int or version!=4:
            raise Conflict('original adopted V4 service selection required')
        service._recovery_proofs(parent)
        record=selection.find(parent,plan['candidate_consumption']['candidate_id'])
        snapshot=record['document']['catalog_snapshot'];pairs=[]
        for ref in record['selection']['selections']:
            matches=[(r,i) for r in snapshot['releases'] for i in snapshot['instances'] if r['release_id']==i['release_id'] and refs.selection_ref(r,i)==ref]
            if len(matches)!=1:raise Conflict('original exact adopted service reference required')
            release,instance=matches[0]
            pairs.append((release,instance,self._historical_source(release)))
        return plan,record,pairs

    def _target(self,c,parent,instance_id):
        try:return self._target_value(c,parent,instance_id)
        except (KeyError,TypeError,ValueError,AttributeError,RecursionError):raise Conflict('current exact target source proof unavailable') from None

    def _target_value(self,c,parent,instance_id):
        catalog_module.lock(c,parent['park_id'])
        value=catalog_module.row(c,parent['park_id']);_,instances=catalog_module.fold(catalog_module.proof(value))
        record=instances.get(instance_id)
        if record is None or record['instance']['roles'].get('enterprise_operator')!=parent['owner_id'] or record['instance']['park_id']!=parent['park_id']:
            raise Denied('own exact target park instance required')
        if record['state']!='ACTIVE':raise Conflict('current target instance unavailable')
        release_record=self.catalog._release_record(c,value,record['instance']['release_id'])
        try:release=self.catalog._current_release(release_record)
        except Denied:raise Conflict('current reviewed target source unavailable') from None
        instance=contract.validate_instance(record['instance'],release,now=self.engine.clock())
        self.catalog.mapping_states(c,instance,parent)
        # Mapping authorization may actually wait on original principal/resource
        # locks. Recheck the publication/time after that wait, before claiming
        # this target is currently available.
        _,latest=catalog_module.fold(catalog_module.proof(catalog_module.row(c,parent['park_id'])))
        latest=latest.get(instance_id)
        if not latest or latest['state']!='ACTIVE' or _hash(latest['instance'])!=_hash(instance):
            raise Conflict('target instance changed during authorization')
        try:current_release=self.catalog._current_release(self.catalog._release_record(c,catalog_module.row(c,parent['park_id']),release['release_id']))
        except Denied:raise Conflict('current reviewed target source unavailable') from None
        if _hash(current_release)!=_hash(release):raise Conflict('target release changed during authorization')
        contract.validate_instance(latest['instance'],current_release,now=self.engine.clock())
        source=self._historical_source(release)
        with self._source_connection() as t:
            head=t.execute('SELECT revision,current_release FROM template_drafts WHERE scope=?',(contract.canonical(source['scope']),)).fetchone()
            if head is None or head['current_release']!=release['source_review']['template_release_id']:
                raise Conflict('latest reviewed target source required')
            source_version=dict(scope=source['scope'],draft_revision=head['revision'],current_release=head['current_release'],release_sha256=release['source_review']['template_release_sha256'])
        return release,instance,source,source_version

    def _header(self,parent,p,plan=None):
        return dict(scope=SCOPE,schema=SCHEMA,**FLAGS,actor_ref=_hash(dict(actor_id=p['id'])),preparation_id=str(parent['id']),
            case_id=str(parent['case_id']),run_id=str(parent['run_id']),plan_id=plan['id'] if plan else None,plan_revision=plan['revision'] if plan else 0)

    def _original_current(self,c,parent,old,original):
        value=catalog_module.row(c,parent['park_id']);_,instances=catalog_module.fold(catalog_module.proof(value))
        record=instances.get(original['instance_id'])
        if not record or record['state']!='ACTIVE' or _hash(record['instance'])!=_hash(original):return False
        release=self.catalog._current_release(self.catalog._release_record(c,value,old['release_id']))
        if _hash(release)!=_hash(old):return False
        instance=contract.validate_instance(record['instance'],release,now=self.engine.clock())
        self.catalog.mapping_states(c,instance,parent)
        return True

    @bounded
    def directory(self,token,id):
        with self.catalog.read_connection() as c:
            p,parent=self._context(c,token,id)
            try:plan,record,pairs=self._originals(parent)
            except (Conflict,ValueError,KeyError,TypeError,AttributeError):
                return dict(**self._header(parent,p),state='UNKNOWN',originals=[],targets=[],blocking_reasons=['ORIGINAL_SERVICE_SELECTION_PROOF_REQUIRED'])
            _,instances=catalog_module.fold(catalog_module.proof(catalog_module.row(c,parent['park_id'])))
            if len(instances)>64:raise Conflict('bounded target directory required')
            originals=[dict(ref=refs.selection_ref(r,i),service_id=r['service_id'],title=r['title']) for r,i,_ in pairs]
            targets=[];unavailable=False
            for id2,rec in sorted(instances.items()):
                if rec['state']!='ACTIVE' or rec['instance']['roles'].get('enterprise_operator')!=p['id']:continue
                try:r,i,source,_=self._target(c,parent,id2)
                except (Conflict,Denied,ValueError):unavailable=True;continue
                if not any(r['service_id']==old['service_id'] and r['owner_org_id']==old['owner_org_id'] and source['scope']==old_source['scope'] for old,_,old_source in pairs):continue
                targets.append(dict(ref=refs.selection_ref(r,i),service_id=r['service_id'],title=r['title']))
                if len(targets)>MAX_TARGETS:raise Conflict('bounded target directory required')
            return dict(**self._header(parent,p,plan),state='AVAILABLE' if targets else 'UNKNOWN',originals=originals,targets=targets,
                blocking_reasons=[] if targets else ['CURRENT_REVIEWED_TARGET_REQUIRED'],has_unavailable_targets=unavailable)

    def _build(self,c,p,parent,*,original_release_id,original_instance_id,target_instance_id):
        try:plan,record,pairs=self._originals(parent)
        except (Conflict,ValueError,TypeError,KeyError,AttributeError):
            unknown=dict(**self._header(parent,p),original_ref=None,target_ref=None,classification='UNKNOWN',contract_classification='UNKNOWN',change_kind='UNKNOWN',can_record=False,
                target_current_available=False,original_source_current_available=False,steps=[],differences=[],contract_affected=[],current_case_affected=[],affected=[],preserved=[],locked_affected=[],
                blocking_reasons=['ORIGINAL_SERVICE_SELECTION_PROOF_REQUIRED'],current_case_blocking_reasons=[],unknown_scope='THIS_CASE')
            unknown['preflight_sha256']=_hash(unknown);return unknown
        matches=[pair for pair in pairs if (pair[0]['release_id'],pair[1]['instance_id'])==(original_release_id,original_instance_id)]
        if len(matches)!=1:raise Conflict('original adopted service pair required')
        old,original,old_source=matches[0];all_ids=[s['id'] for s in plan['steps']]
        result=dict(**self._header(parent,p,plan),original_ref=refs.selection_ref(old,original),target_ref=None,
            classification='UNKNOWN',contract_classification='UNKNOWN',change_kind='UNKNOWN',can_record=False,
            target_current_available=False,original_source_current_available=False,steps=[dict(id=s['id'],adapter_id=s['adapter_id']) for s in plan['steps']],
            differences=[],contract_affected=[],current_case_affected=[],affected=all_ids,preserved=[],locked_affected=[],
            blocking_reasons=[],current_case_blocking_reasons=[],unknown_scope='THIS_CASE')
        try:result['original_source_current_available']=self._original_current(c,parent,old,original)
        except (Conflict,Denied,ValueError):pass
        try:target,instance,target_source,target_version=self._target(c,parent,target_instance_id)
        except Denied:raise
        except (Conflict,ValueError):
            result['blocking_reasons']=['CURRENT_REVIEWED_TARGET_REQUIRED'];result['preflight_sha256']=_hash(result);return result
        result.update(target_ref=refs.selection_ref(target,instance),target_current_available=True,
            change_kind='NO_RELEASE_CHANGE' if old['release_id']==target['release_id'] else 'RELEASE_VERSION_CHANGE')
        if (target['service_id']!=old['service_id'] or target['owner_org_id']!=old['owner_org_id'] or target_source['scope']!=old_source['scope']):
            raise Denied('same original service and template family required')
        comparison=compare_v1(plan,old,original,target,instance,old_source,target_source,record['frozen_registry'])
        issues,sources,_=service.current_sources(self.store,c,parent,plan)
        sources={s['adapter_id']:sources[s['adapter_id']] for s in plan['steps']}
        before=adoption.evidence_sources(parent,plan)
        basis,_,_=service.dependency_impact(self.store,c,parent,plan)
        graph=typed.build(parent,plan,before,sources,plan.get('dependency_manifest'),basis)
        blockers=service._binding_issues(c,parent,plan,store=self.store)
        unavailable=any(adoption.unavailable_sources().intersection(v) for v in issues.values())
        valid_graph=(isinstance(graph,dict) and type(graph.get('schema')) is int and graph['schema']==1 and
            isinstance(graph.get('affected'),list) and isinstance(graph.get('preserved'),list) and
            all(isinstance(v,str) for v in graph['affected']+graph['preserved']) and
            graph.get('unknown_scope','UNSUPPORTED') in (None,'THIS_CASE') and
            isinstance(graph.get('sha256'),str) and re.fullmatch('[a-f0-9]{64}',graph['sha256']) is not None and
            len(graph['affected'])==len(set(graph['affected'])) and len(graph['preserved'])==len(set(graph['preserved'])) and
            not set(graph['affected'])&set(graph['preserved']) and set(graph['affected'])|set(graph['preserved'])==set(all_ids))
        current=set(graph['affected']) if valid_graph else set(all_ids)
        # Definition/catalog binding changes need the original explicit
        # replacement/recheck path even when the two contracts have identical
        # semantics. Preserve that distinction instead of claiming readiness.
        if blockers:current=set(all_ids)
        affected=set(comparison['affected'])|current
        locks=[s['id'] for s in plan['steps'] if s['id'] in affected and service._manual_lock(plan,s)]
        unknown=bool(not valid_graph or graph['unknown_scope'] or unavailable)
        classification=('UNKNOWN' if unknown else 'BREAKING_REJECTED' if comparison['classification']=='BREAKING_REJECTED'
                        else 'LOCK_CONFLICT' if locks else 'NEEDS_RECHECK' if affected else 'COMPATIBLE')
        reasons=list(comparison['blocking_reasons'])
        if not valid_graph:reasons.append('SUPPORTED_SOURCE_GRAPH_SCHEMA_REQUIRED')
        if unknown:reasons.append('CURRENT_KNOWN_SOURCE_BASE_REQUIRED')
        if locks:reasons.append('AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK')
        if classification=='UNKNOWN':
            affected=set(all_ids)
            locks=[s['id'] for s in plan['steps'] if s['id'] in affected and service._manual_lock(plan,s)]
        versions=c.execute('SELECT pr.xmin::text preparation_epoch,ca.xmin::text case_epoch,r.xmin::text run_epoch FROM preparations pr JOIN cases ca ON ca.id=pr.case_id JOIN runs r ON r.id=pr.run_id WHERE pr.id=%s',(parent['id'],)).fetchone()
        catalogs=c.execute("SELECT park_id,service_id,version,xmin::text row_epoch FROM preparation_catalog WHERE service_id=%s AND version=1 AND service_capability_catalog IS NOT NULL ORDER BY park_id LIMIT 33",(prep.SERVICE,)).fetchall()
        if len(catalogs)>32:raise Conflict('bounded service source collection required')
        result.update(classification=classification,contract_classification=comparison['classification'],can_record=classification!='UNKNOWN',
            differences=comparison['differences'],contract_affected=comparison['affected'],current_case_affected=[s for s in all_ids if s in current],
            affected=[s for s in all_ids if s in affected],preserved=[s for s in all_ids if s not in affected],locked_affected=locks,
            blocking_reasons=sorted(set(reasons)),current_case_blocking_reasons=sorted(set(blockers)),
            unknown_scope='THIS_CASE' if unknown or blockers else None,
            source_impact_schema=graph.get('schema') if isinstance(graph,dict) and type(graph.get('schema')) is int else None,source_impact_sha256=graph.get('sha256') if valid_graph else None,
            binding_sha256=_hash(dict(parent=parent,plan=plan)),source_epochs_sha256=adoption.epochs(c,parent),
            case_versions_sha256=_hash(versions),catalog_epochs_sha256=_hash(catalogs),target_source_version_sha256=_hash(target_version),
            original_candidate_sha256=record['candidate_sha256'],frozen_registry_sha256=_hash(record['frozen_registry']))
        # Later current-source inspection can wait as well. This final, bounded
        # target check covers expiry/withdrawal/new head during that inspection;
        # it does not recursively rebuild or promise validity after return.
        try:
            last_release,last_instance,_,last_version=self._target(c,parent,target_instance_id)
            if (refs.selection_ref(last_release,last_instance)!=result['target_ref'] or _hash(last_version)!=_hash(target_version)):
                raise Conflict('target changed during Case inspection')
        except (Conflict,Denied,ValueError):
            result.update(classification='UNKNOWN',can_record=False,target_current_available=False,unknown_scope='THIS_CASE',affected=all_ids,preserved=[],
                locked_affected=[s['id'] for s in plan['steps'] if service._manual_lock(plan,s)],
                blocking_reasons=sorted(set(result['blocking_reasons'])|{'CURRENT_REVIEWED_TARGET_REQUIRED'}))
        result['preflight_sha256']=_hash(result)
        return result

    @bounded
    def preview(self,token,id,*,original_release_id,original_instance_id,target_instance_id):
        with self.catalog.read_connection() as c:
            p,parent=self._context(c,token,id)
            return self._build(c,p,parent,original_release_id=original_release_id,original_instance_id=original_instance_id,target_instance_id=target_instance_id)

    def _saved(self,journal,p,parent,key,database):
        row=journal.execute('SELECT r.fp,r.key,i.* FROM consumer_requests r JOIN consumer_instances i ON i.id=r.instance_id WHERE r.actor=? AND r.key=? AND i.actor=? AND i.park=? AND i.org=? AND i.database_name=?',(p['id'],key,p['id'],p['park_id'],p['org_id'],database)).fetchone()
        if row is None:return None
        try:
            binding=json.loads(row['binding']);body=json.loads(row['input']);data=Record.model_validate(body)
            proof=binding['preflight']
            expected=dict(schema=SCHEMA,kind=SCOPE,preparation_id=str(parent['id']),actor_ref=_hash(dict(actor_id=p['id'])),
                preflight=proof,request_sha256=_hash(body))
            if (set(binding)!=set(expected)|{'sha256'} or {k:v for k,v in binding.items() if k!='sha256'}!=expected or
                binding['sha256']!=_hash(expected) or row['fp']!=_hash(dict(scope=SCOPE,preparation_id=str(parent['id']),request=body)) or
                proof['preflight_sha256']!=_hash({k:v for k,v in proof.items() if k!='preflight_sha256'}) or
                proof['preflight_sha256']!=data.expected_preflight_sha256 or proof['plan_revision']!=data.expected_plan_revision or
                proof['original_ref']!=data.original_ref.model_dump() or proof['target_ref']!=data.target_ref.model_dump() or
                not proof['can_record'] or row['state']!='RECORDED_PREFLIGHT_ONLY'):
                raise ValueError()
        except (KeyError,TypeError,ValueError,AttributeError,RecursionError):raise Conflict('immutable preflight evidence proof invalid') from None
        return dict(id=row['id'],binding=binding,request=body)

    def _receipt(self,c,p,parent,key,saved):
        plan=parent.get('service_case_plan')
        if not isinstance(plan,dict) or not isinstance(plan.get('id'),str) or type(plan.get('revision')) is not int:plan=None
        result=dict(**self._header(parent,p,plan),status='NOT_OBSERVED' if saved is None else 'COMMITTED',request_key=key,
            record_id=None,record_sha256=None,recorded_preflight=None,current_available=False)
        if saved is None:return result
        proof=saved['binding']['preflight']
        try:
            prep.grant(self.store,c,p,'PREPARE')
            current=self._build(c,p,parent,original_release_id=proof['original_ref']['release_id'],original_instance_id=proof['original_ref']['instance_id'],target_instance_id=proof['target_ref']['instance_id'])
            available=current['can_record'] and current['preflight_sha256']==proof['preflight_sha256']
        except (Denied,Conflict,ValueError,TypeError,KeyError):available=False
        result.update(record_id=saved['id'],record_sha256=saved['binding']['sha256'],recorded_preflight=deepcopy(proof),current_available=bool(available))
        return result

    @bounded
    def save(self,token,id,key,data):
        self.consumer._key(key)
        data=Record.model_validate(data.model_dump() if isinstance(data,Record) else data)
        body=data.model_dump(mode='json');database=self.consumer.validate_fixture()
        # Source writer gate -> original PG scope/parent -> private journal.
        # No path obtains this journal and then waits for a PG lock.
        with self.catalog.connection() as c:
            p,parent=self._context(c,token,id)
            with self.repository.connect(write=True) as journal:
                saved=self._saved(journal,p,parent,key,database)
                if saved:
                    if saved['request']!=body:raise Conflict('preflight original key parameters changed')
                    return self._receipt(c,p,parent,key,saved)
                if journal.execute('SELECT count(*) FROM consumer_instances').fetchone()[0]>=MAX_RECORDS:
                    raise Conflict('bounded preflight evidence capacity reached')
                args=dict(original_release_id=data.original_ref.release_id,original_instance_id=data.original_ref.instance_id,target_instance_id=data.target_ref.instance_id)
                proof=self._build(c,p,parent,**args)
                if (not proof['can_record'] or proof['preflight_sha256']!=data.expected_preflight_sha256 or proof['plan_revision']!=data.expected_plan_revision or
                    proof['original_ref']!=data.original_ref.model_dump() or proof['target_ref']!=data.target_ref.model_dump()):
                    raise Conflict('current exact ServiceRelease preflight required')
                id2=str(uuid4());binding=dict(schema=SCHEMA,kind=SCOPE,preparation_id=str(parent['id']),actor_ref=_hash(dict(actor_id=p['id'])),preflight=proof,request_sha256=_hash(body))
                binding['sha256']=_hash(binding)
                journal.execute('INSERT INTO consumer_instances VALUES(?,?,?,?,?,?,?,?)',(id2,p['id'],p['park_id'],p['org_id'],database,contract.canonical(binding),contract.canonical(body),'RECORDED_PREFLIGHT_ONLY'))
                fp=_hash(dict(scope=SCOPE,preparation_id=str(parent['id']),request=body))
                journal.execute('INSERT INTO consumer_requests VALUES(?,?,?,?)',(p['id'],key,fp,id2))
                # Recheck after the actual log INSERT, before its commit. The
                # PG transaction writes no business row; the saved observation
                # does not claim future validity or distributed atomicity.
                if self._build(c,p,parent,**args)!=proof:raise Conflict('preflight source changed while recording')
                prep.grant(self.store,c,p,'PREPARE')
                saved=self._saved(journal,p,parent,key,database)
                return self._receipt(c,p,parent,key,saved)

    @bounded
    def recover(self,token,id,key):
        self.consumer._key(key);database=self.consumer.validate_fixture()
        with self.catalog.read_connection() as c:
            p,parent=self._context(c,token,id,historical=True)
            with self.repository.connect() as journal:saved=self._saved(journal,p,parent,key,database)
            return self._receipt(c,p,parent,key,saved)
