"""Atomic NO_MODEL candidates for the independent local SYNTHETIC profile.

All solving, minimality and graph reconstruction use the original V4 core.
These records never claim the offline HTTP model proof of that older profile.
"""
from copy import deepcopy
from datetime import timedelta, timezone
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from . import bounded_planning as bp, controlled_plans as cp, preparation as prep
from . import service_selection as ss, service_selection_candidates as v4
from . import service_plan_candidates as old
from . import local_synthetic_demo as demo
from . import difference_observation as observation
from .store import Conflict, Denied
from .intern_adapter import ModelBoundaryError

PROFILE = demo.PROFILE
SCOPE = 'LOCAL_SYNTHETIC_DEMO_SELECTION_CANDIDATE'
ORIGIN = demo.ORIGIN
VALIDATOR = 'LOCAL_SYNTHETIC_DEMO_V1'
OBSERVATION_VALIDATOR = 'LOCAL_SYNTHETIC_DEMO_V2'
Capture, clock, binding = v4.Capture, v4.clock, v4.binding
KEYS = v4.KEYS
BASIS = ('validator_version','validated_contract_sha256','candidate_id','candidate_sha256',
    'current_source_sha256','state',*KEYS[:5],*KEYS[6:],'validity','producer_sha256')


def document(value):
    result = old.document(value)
    result.update(origin=ORIGIN,profile=PROFILE,binding=binding(value),selection=deepcopy(value['selection']))
    if observation.version(value)==2:
        result.update({k:deepcopy(value[k]) for k in (observation.VERSION,observation.FIELD)})
    return result


def _apply(base, selection, *, now, frozen=None):
    value = deepcopy(base)
    snapshot, request = value['catalog_snapshot'], value['selection_request']
    pairs = demo.validated_pairs(snapshot,request,now=now,frozen=frozen)
    parsed = ss.parse_selection(demo.contract.canonical(selection),binding(value))
    oracle = ss._enumerate_pairs(pairs,request)
    rebuilt = ss._rebuild_pairs(parsed,pairs,request,binding(value),oracle,actions=None if frozen is None else frozen['actions'])
    originals = {s['id']:s for s in base['steps']}
    steps = []
    for step in rebuilt['steps']:
        merged = deepcopy(originals.get(step['id'],{})); merged.update(step); steps.append(merged)
    value.update(selection=parsed,steps=steps,selection_rebuild=rebuilt)
    return value


def current(store,c,p,parent,catalog,selection=None):
    if type(catalog) is not demo.LocalDemoCatalog or catalog.store is not store:
        raise Denied('exact independent local demo catalog required')
    base = bp._proposal(store,c,p,parent)
    snapshot = catalog.snapshot(c,parent)
    base['legacy_source_sha256'] = base['source_sha256']
    base['capability_catalog_sha256'] = cp._hash(cp._normal(snapshot))
    base['source_sha256'] = cp._hash(dict(legacy_source_sha256=base['legacy_source_sha256'],
        capability_catalog_sha256=base['capability_catalog_sha256']))
    request = v4._request(parent,snapshot,base)
    oracle = ss._enumerate_pairs(demo.validated_pairs(snapshot,request,now=clock(c)),request)
    base.update(profile=PROFILE,catalog_snapshot=snapshot,selection_request=request,selection_oracle=oracle,selection=None)
    base['source_unknowns'] = sorted(set(base['source_unknowns'])|set(oracle['unknowns']))
    if oracle['state'] not in ('UNIQUE','MULTIPLE'):
        base['state'] = 'UNKNOWN' if oracle['state']=='UNKNOWN' else 'SELECTION_BLOCKED'
    base[observation.VERSION]=1
    base[observation.FIELD]=None
    if oracle['state']=='UNIQUE':
        choice=dict(schema_version=1,binding=binding(base),selections=oracle['minimal_solutions'][0])
        full=_apply(base,choice,now=clock(c))
        base[observation.FIELD]=observation.capture(store,c,p,parent,full)
    base['source_sha256']=observation.source_hash(base)
    if selection is not None:
        try:base = _apply(base,selection,now=clock(c))
        except ModelBoundaryError:raise Conflict('local demo selection or observation source changed') from None
    return base


def _fingerprint(id,data):
    return cp._hash(dict(preparation_id=str(id),kind=SCOPE,**data.model_dump()))


def _producer(record):
    base = record['base_document']; snapshot = base['catalog_snapshot']
    version=observation.version(base)
    return dict(schema_version='local-synthetic-demo-producer/'+str(version),origin=ORIGIN,mode='NO_MODEL',
        model=None,provider_enabled=False,real_model_calls=0,executed=False,
        selection_sha256=cp._hash(record['selection']),pack_sha256=snapshot['pack_sha256'],
        journal_sha256=snapshot['journal_sha256'],base_sha256=cp._hash(base),
        attempt_sha256=cp._hash({k:record[k] for k in ('id','actor_id','request_key','fingerprint','validity')}))


def _proof(parent,record):
    try:
        UUID(record['id']); data=Capture.model_validate(record['candidate_request'])
        doc,base = record['document'],record['base_document']
        frozen=record['frozen_registry']
        old._window(record)
        version=observation.version(base)
        if ((version==1 and 'difference_observation_record_version' in record) or
            (version==2 and (type(record.get('difference_observation_record_version')) is not int or record['difference_observation_record_version']!=2))):
            raise ValueError()
        if (record['profile'] != PROFILE or base['profile'] != PROFILE or base['selection'] is not None
                or record['actor_id'] != parent['owner_id'] or doc['preparation_id'] != str(parent['id'])
                or record['fingerprint'] != _fingerprint(parent['id'],data)
                or set(frozen)!={'steps','actions'} or base['registry_sha256'] != cp._hash(frozen)
                or base['capability_catalog_sha256'] != cp._hash(cp._normal(base['catalog_snapshot']))
                or base['source_sha256'] != observation.source_hash(base)
                or data.expected_preparation_revision != base['preparation_revision']
                or data.expected_source_sha256 != base['source_sha256']
                or data.expected_capability_catalog_sha256 != base['capability_catalog_sha256']
                or cp._hash(record['producer']) != cp._hash(_producer(record))):
            raise ValueError()
        at = old._time(record['validity']['created_at'])
        pairs = demo.validated_pairs(base['catalog_snapshot'],base['selection_request'],now=at,frozen=frozen)
        if (base['catalog_snapshot']['unknowns'] or base['selection_oracle'] != ss._enumerate_pairs(pairs,base['selection_request'])
                or base['selection_oracle']['state'] != 'UNIQUE'
                or record['selection']['selections'] != base['selection_oracle']['minimal_solutions'][0]):
            raise ValueError()
        expected = _apply(base,record['selection'],now=at,frozen=frozen)
        observation.validate(expected,expected['steps'])
        expected.update(candidate_validity=record['validity'],candidate_producer=record['producer'])
        if (cp._hash(doc) != cp._hash(expected) or cp._hash(record['candidate']) != cp._hash(document(doc))
                or record['candidate_sha256'] != cp._hash(record['candidate'])): raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError,ModelBoundaryError):
        raise Conflict('local demo original NO_MODEL provenance invalid') from None


def find(parent,id):
    rows = [h for h in parent.get('planning_previews') or [] if h.get('id')==str(id)]
    if len(rows)!=1: raise Conflict('exact local demo candidate required')
    _proof(parent,rows[0]); return rows[0]


def verify(parent,record,value,*,now,historical=False):
    _proof(parent,record)
    expected = document(value)
    full = value['state']=='COVERED_PREVIEW_ONLY' and not value['source_unknowns'] and value['selection_oracle']['state']=='UNIQUE'
    state = ('STALE' if record['candidate']['binding']!=expected['binding'] else
        'REJECTED' if record['candidate']!=expected else 'VERIFIED_STRUCTURE_ONLY' if full else 'BLOCKED')
    window = record['validity']
    if now < old._time(window['created_at']): state='CLOCK_UNCERTAIN'
    elif now >= old._time(window['expires_at']): state='EXPIRED'
    basis = dict(validator_version=OBSERVATION_VALIDATOR if observation.version(record['base_document'])==2 else VALIDATOR,validated_contract_sha256=cp._hash({k:v for k,v in expected.items() if k!='binding'}),
        candidate_id=record['id'],candidate_sha256=record['candidate_sha256'],current_source_sha256=value['source_sha256'],
        state=state,**{k:value[k] for k in KEYS if k!='source_sha256'},validity=deepcopy(window),producer_sha256=cp._hash(record['producer']))
    return dict(**basis,verification_sha256=cp._hash(basis),scope=SCOPE,profile=PROFILE,origin=ORIGIN,
        can_adopt=state=='VERIFIED_STRUCTURE_ONLY' and full,can_adopt_partial=False,producer=deepcopy(record['producer']),
        required_goals=value['required_goals'],goal_coverage=value['goal_coverage'],steps=value['steps'],
        source_unknowns=value['source_unknowns'],selection=record['selection'],selection_oracle=value['selection_oracle'],
        read_only=True,provider_enabled=False,execution_enabled=False,new_grants=False,case_goal_completed=False)


def _prior(c,p,parent,key,fp):
    rows = c.execute('SELECT * FROM preparations WHERE planning_previews @> %s',
        (Jsonb([dict(actor_id=p['id'],request_key=key)]),)).fetchall()
    matches = [(row,h) for row in rows for h in row['planning_previews'] or [] if h['actor_id']==p['id'] and h['request_key']==key]
    if not matches: return None
    if len(matches)!=1: raise Conflict('local demo original key ambiguous')
    row,record=matches[0]
    if row['id']!=parent['id'] or record.get('profile')!=PROFILE or record['fingerprint']!=fp:
        raise Conflict('local demo original key scope changed')
    return find(parent,record['id'])


def _availability(store,c,p,parent,catalog,record):
    try: return verify(parent,record,current(store,c,p,parent,catalog,record['selection']),now=clock(c))
    except (Denied,Conflict,ValueError,ModelBoundaryError):
        view=verify(parent,record,record['document'],now=clock(c),historical=True)
        view.update(state='CURRENT_SOURCE_UNAVAILABLE',can_adopt=False)
        view['verification_sha256']=cp._hash({k:view[k] for k in BASIS})
        return view


def generate(store,token,id,key,data,*,catalog,planner):
    if type(planner) is not demo.LocalDemoSelector: raise Denied('exact NO_MODEL demo selector required')
    with catalog.connection() as c:
        p,parent=bp._context(store,c,token,id,True)
        prep.key_lock(c,p,'planning-preview:'+key)
        fp=_fingerprint(id,data); prior=_prior(c,p,parent,key,fp)
        if prior is not None: return _availability(store,c,p,parent,catalog,prior)
        value=current(store,c,p,parent,catalog); v4._exact(data,parent,value)
        history=deepcopy(parent.get('planning_previews') or [])
        if len(history)>=bp.LIMIT or any(h.get('planner_attempt',{}).get('state')=='STARTED' for h in history):
            raise Conflict('bounded original history requires GET recovery')
        selection=planner.select(value)
        now=clock(c).astimezone(timezone.utc)
        window=dict(version=2,created_at=now.isoformat(),expires_at=(now+timedelta(seconds=old.VALIDITY_SECONDS)).isoformat(),seconds=old.VALIDITY_SECONDS)
        record=dict(id=str(uuid4()),profile=PROFILE,revision=len(history)+1,actor_id=p['id'],request_key=key,
            fingerprint=fp,candidate_request=data.model_dump(),validity=window,base_document=deepcopy(value),selection=selection,
            frozen_registry=deepcopy(dict(steps=bp.REGISTRY,actions=bp.ACTIONS)))
        record['difference_observation_record_version']=2
        record['producer']=_producer(record)
        saved=_apply(value,selection,now=now)
        saved.update(candidate_validity=window,candidate_producer=record['producer'])
        record.update(document=saved,candidate=document(saved)); record['candidate_sha256']=cp._hash(record['candidate'])
        view=verify(parent,record,saved,now=clock(c))
        if not view['can_adopt']: raise Conflict('current local demo selection not adoptable')
        history.append(record)
        bp._context(store,c,token,id,True)
        c.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s',(Jsonb(history),id))
        return view


def read(store,token,id,candidate_id=None,key=None,*,catalog):
    with catalog.read_connection() as c:
        p,parent=bp._context(store,c,token,id)
        rows=[h for h in parent.get('planning_previews') or [] if h.get('profile')==PROFILE]
        if candidate_id is not None: rows=[find(parent,candidate_id)]
        if key is not None: rows=[h for h in rows if h['actor_id']==p['id'] and h['request_key']==key]
        items=[_availability(store,c,p,parent,catalog,h) for h in rows]
        actor=cp._hash(dict(actor_id=p['id']))
        if candidate_id is not None: return dict(**items[0],actor_ref=actor)
        return dict(scope=SCOPE,profile=PROFILE,preparation_id=str(id),case_id=str(parent['case_id']),run_id=str(parent['run_id']),
            actor_ref=actor,status='COMMITTED' if key is not None and items else 'NOT_OBSERVED' if key is not None else 'LIST',
            request_key=key,items=items,attempts=[],provider_enabled=False,read_only=True,automatically_replayed=False,
            execution_enabled=False,new_grants=False,case_goal_completed=False)


def consume(parent,current,data,*,now=None,historical=False):
    record=find(parent,data.candidate_id)
    view=verify(parent,record,current,now=now,historical=historical)
    if data.partial_adoption or not view['can_adopt'] or view['candidate_sha256']!=data.expected_candidate_sha256 or view['verification_sha256']!=data.expected_verification_sha256:
        raise Conflict('current explicit local demo verification required')
    return dict(candidate_id=view['candidate_id'],candidate_sha256=view['candidate_sha256'],verification_sha256=view['verification_sha256'],
        origin=ORIGIN,verification_basis={k:deepcopy(view[k]) for k in BASIS},accepted_at=now.astimezone(timezone.utc).isoformat(),
        producer=deepcopy(view['producer']),selection=deepcopy(record['selection']),capability_catalog_sha256=current['capability_catalog_sha256'])


def consumption_proof(parent,plan,request):
    try:
        proof=plan['candidate_consumption']; record=find(parent,request.candidate_id)
        if (request.expected_preparation_revision!=plan['adoption_preparation_revision']
                or request.expected_request_revision!=plan['binding']['request_intent']['revision']
                or request.expected_source_sha256!=plan['adoption_preview']['source_sha256']
                or request.required_goals!=plan['required_goals']
                or plan['events'][0].get('candidate_consumption_sha256')!=cp._hash(proof)
                or plan['binding'].get('service_selection')!=dict(profile=PROFILE,
                    capability_catalog_sha256=record['document']['capability_catalog_sha256'],selection=record['selection'])):
            raise ValueError()
        actual=[{k:s[k] for k in ('adapter_id','adapter','adapter_revision','depends_on','contract')} for s in plan['steps']]
        expected=[dict(adapter_id=s['id'],adapter=s['adapter'],adapter_revision=s['revision'],depends_on=s['depends_on'],contract=s) for s in plan['adoption_preview']['steps']]
        expected_proof=consume(parent,plan['adoption_preview'],request,now=old._time(proof['accepted_at']),historical=True)
        if observation.version(plan['adoption_preview'])==2:
            expected_proof[observation.SEAL]=observation.seal(parent,plan,expected_proof)
        if actual!=expected or proof!=expected_proof: raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise Conflict('local demo original adoption provenance invalid') from None


def seal_observation(parent,plan):
    if observation.version(plan['adoption_preview'])==2:
        proof=plan['candidate_consumption']
        proof[observation.SEAL]=observation.seal(parent,plan,proof)
