"""Source-bound local material readiness, never policy eligibility or publication."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from . import preparation as prep
from .domain import Rule, Truth, conjunction
from .store import Conflict, Denied, digest

RULE = Rule(kind='AND', children=[Rule(kind='EXISTS', field='service_need'), Rule(kind='MANUAL')])
LIMIT = 32

class Assess(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_preparation_revision: int = Field(ge=1, le=64)
    expected_source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

def _sources(store, c, row, actor):
    items = [{k: str(v) if isinstance(v, UUID) else v for k, v in i.items()} for i in prep.latest(c, row['id'])]
    service = c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s', (row['park_id'], row['service_id'], row['service_version'])).fetchone()
    # Current reviewer rights remain a prerequisite, including when reading old assessments.
    reviewer = c.execute('SELECT * FROM principals WHERE id=%s', (row['reviewer_id'],)).fetchone()
    authorized = False
    if reviewer and reviewer['active'] and (reviewer['park_id'], reviewer['org_id']) == (row['park_id'], row['org_id']):
        try: prep.grant(store, c, reviewer, 'REVIEW_ASSIGNED'); authorized = True
        except Denied: pass
    decision = c.execute("SELECT revision,action,payload,created_at FROM preparation_events WHERE preparation_id=%s AND action IN ('REVIEW','REQUEST_CHANGES') ORDER BY revision DESC LIMIT 1", (row['id'],)).fetchone()
    review = {'reviewer_id': row['reviewer_id'], 'current_authority': authorized, 'state': row['state'], 'review_sha256': row['review_sha256'], 'decision': None}
    if decision:
        review['decision'] = {'revision': decision['revision'], 'action': decision['action'], 'actor_id': decision['payload']['actor_id'], 'reason': decision['payload'].get('reason'), 'created_at': decision['created_at'].isoformat()}
    rule = {'expression': RULE.model_dump(mode='json'), 'revision': 1, 'source': 'LOCAL_MATERIAL_CONTRACT', 'review_status': 'ENGINEERING_ONLY', 'publication_status': 'DRAFT', 'business_publication': False}
    rule['sha256'] = digest(prep.canonical(rule))
    source = {'preparation_id': str(row['id']), 'case_id': str(row['case_id']), 'revision': row['revision'], 'service': service, 'rule': rule, 'materials': items, 'manual_review': review}
    facts=prep.fact_descriptor(store,c,row)
    if facts is not None:source['fact_clarification']=facts
    return source, digest(prep.canonical(source))

def _evaluate(source):
    items = {i['slot']: i for i in source['materials']}
    review = source['manual_review']; decision = review['decision']
    existence = Truth.TRUE if 'need_summary' in items else Truth.UNKNOWN
    reason = 'MISSING_MATERIALS'; manual = Truth.UNKNOWN
    missing = [s for s in prep.SLOTS if s not in items]
    if not review['current_authority']: reason = 'CURRENT_REVIEW_AUTHORITY_REQUIRED'
    elif review['state'] == 'CHANGES_REQUESTED' and decision and decision['action'] == 'REQUEST_CHANGES':
        manual = Truth.FALSE; reason = 'REVIEW_REQUIRES_CORRECTION'
    elif missing: pass
    elif review['state'] in ('REVIEWED', 'LOCAL_CONFIRMED') and decision and decision['action'] == 'REVIEW':
        # prep.snapshot must match the exact, complete current material pack.
        row = {'id': source['preparation_id'], 'service_id': source['service']['service_id'], 'service_version': source['service']['version']} if source['service'] else None
        if row and review['review_sha256'] == prep.snapshot(row, source['materials']): manual = Truth.TRUE; reason = 'CURRENT_LOCAL_MANUAL_REVIEW'
        else: reason = 'MATERIAL_REVIEW_STALE'
    else: reason = 'HUMAN_JUDGMENT_REQUIRED'
    if (not source['service'] or source['service']['namespace'] != 'SYNTHETIC'
            or not isinstance(source['service']['source'], dict)
            or source['service']['source'].get('kind') != 'SYNTHETIC'):
        manual = Truth.UNKNOWN; reason = 'SERVICE_SOURCE_UNAVAILABLE'
    result={'local_preparation_truth': conjunction([existence, manual]).value,
        'conditions': [{'id': 'service_need_exists', 'truth': existence.value, 'reason': 'CURRENT_RECORD_EXISTS' if existence == Truth.TRUE else 'MISSING_MATERIALS', 'material_ids': [items['need_summary']['id']] if 'need_summary' in items else []},
                       {'id': 'current_manual_material_review', 'truth': manual.value, 'reason': reason, 'material_ids': [i['id'] for i in source['materials']]}],
        'missing_slots': missing, 'next_actions': (['SUPPLY_MATERIALS'] if missing else []) + (['RESPOND_TO_CORRECTION'] if manual == Truth.FALSE else ['REQUEST_CURRENT_MANUAL_REVIEW'] if manual == Truth.UNKNOWN else []),
        'qualification_truth': Truth.UNKNOWN.value, 'qualification_decision': 'NOT_EVALUATED', 'business_publication': False, 'external_acceptance': 'NOT_SUBMITTED', 'offline_fulfillment': 'NO_EVIDENCE', 'case_goal_completed': False}
    facts=source.get('fact_clarification')
    if facts is not None:
        truth=Truth.TRUE if facts.get('satisfied') is True else Truth.UNKNOWN
        result['local_preparation_truth']=conjunction([existence,manual,truth]).value
        draft_stale='CURRENT_GENERATED_MATERIAL_SOURCE_REQUIRED' in facts.get('issues',[])
        result['conditions'].append({'id':'current_fact_purpose_confirmation','truth':truth.value,
                                     'reason':'CURRENT_USER_PURPOSE_CONFIRMATION' if truth==Truth.TRUE else 'CURRENT_GENERATED_MATERIAL_SOURCE_REQUIRED' if draft_stale else 'CURRENT_FACT_PURPOSE_CONFIRMATION_REQUIRED'})
        if truth!=Truth.TRUE:result['next_actions'].append('REBUILD_MATERIAL_BRIEF' if draft_stale else 'CONFIRM_FACT_PURPOSE')
    return result

def _checklist(row, source, result, sha, correction_items):
    """Explain existing local conditions; never invent service/policy requirements.

    Read-time projection only: no new rule, evidence, assessment or authority.
    The source hash/revision binds this candidate to the ordinary readiness view.
    """
    items = {i['slot']: i for i in source['materials']}
    conditions = {i['id']: i for i in result['conditions']}
    manual = conditions['current_manual_material_review']
    service = source['service']
    known = bool(service and service['namespace'] == 'SYNTHETIC'
                 and isinstance(service['source'], dict)
                 and service['source'].get('kind') == 'SYNTHETIC')
    requirements = []
    for slot in prep.SLOTS:
        item = items.get(slot)
        evidence = None if item is None else {k: item[k] for k in
                    ('id', 'version', 'source_kind', 'source_label', 'source_sha256', 'authenticity', 'text')}
        requests = []
        for target in correction_items:
            if target['slot'] == slot:
                requests.append({k: target[k] for k in ('request_id', 'reason', 'base_version', 'status')})
        # Evidence presence is separate from the complete-pack human judgment.
        status = 'MISSING' if item is None else 'PROVIDED_UNVERIFIED'
        if any(r['status'] == 'REQUESTED' for r in requests): status = 'CORRECTION_REQUIRED'
        elif requests: status = 'AWAITING_REVIEW'
        elif item and manual['truth'] == 'TRUE': status = 'CURRENT_PACK_REVIEWED'
        requirements.append(dict(slot=slot, status=status, evidence=evidence,
            correction_requests=requests, missing=item is None,
            truth='TRUE' if known and item and manual['truth'] == 'TRUE' else 'UNKNOWN',
            next_action='SUPPLY_MATERIALS' if item is None else
                'RESPOND_TO_CORRECTION' if status == 'CORRECTION_REQUIRED' else
                'REQUEST_CURRENT_MANUAL_REVIEW' if manual['truth'] != 'TRUE' else 'CHECK_CURRENT_REVIEW'))
    explained = []
    for condition in result['conditions']:
        ids = condition.get('material_ids', [])
        explained.append({**condition, 'evidence': [i for i in requirements
            if i['evidence'] and i['evidence']['id'] in ids],
            'basis': 'CURRENT_CASE_FACT_PURPOSE' if condition['id'] == 'current_fact_purpose_confirmation'
                     else 'EXISTING_LOCAL_MATERIAL_CONTRACT',
            'manual_decision': source['manual_review']['decision'] if condition['id'] == 'current_manual_material_review' else None,
            'fact_basis': source.get('fact_clarification') if condition['id'] == 'current_fact_purpose_confirmation' else None})
    return dict(scope='SYNTHETIC_HUMAN_REVIEW_CANDIDATE', preparation_revision=row['revision'],
        source_sha256=sha, source_available=known, requirements=requirements, conditions=explained,
        policy_requirements=dict(status='NOT_PROVIDED', truth='UNKNOWN',
            reason='REVIEWED_REAL_POLICY_SOURCE_REQUIRED', requirements_generated=False),
        rule_revision=source['rule']['revision'], rule_sha256=source['rule']['sha256'],
        business_publication=False, qualification_decision='NOT_EVALUATED',
        external_acceptance='NOT_SUBMITTED', case_goal_completed=False)


def _view(row, source, sha):
    history = row['readiness_assessments'] or []
    latest = history[-1] if history else None
    state = 'NOT_ASSESSED' if not latest else 'CURRENT' if latest['source_sha256'] == sha else 'STALE'
    inputs = _evaluate(source)
    return {'preparation_id': str(row['id']), 'case_id': str(row['case_id']), 'preparation_revision': row['revision'], 'source_sha256': sha,
        'state': state, 'current_truth': latest['result']['local_preparation_truth'] if state == 'CURRENT' else Truth.UNKNOWN.value,
        'sources': source, 'current_inputs': inputs, 'latest': latest, 'history': history,
        'scope': 'SYNTHETIC_LOCAL_MATERIAL_CONDITIONS_ONLY', 'business_publication': False, 'qualification_decision': 'NOT_EVALUATED'}

def _parent(store, c, p, id, write=False):
    # All relevant principals precede the preparation row, matching manual writes.
    prep.grant(store, c, p, 'PREPARE' if p['role'] == 'enterprise_operator' else 'REVIEW_ASSIGNED')
    candidate = c.execute('SELECT owner_id,reviewer_id FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s', (id, p['park_id'], p['org_id'])).fetchone()
    if not candidate or p['id'] != candidate['owner_id' if p['role'] == 'enterprise_operator' else 'reviewer_id']: raise Denied('assigned preparation scope required')
    if candidate['reviewer_id'] != p['id']: store.lock_principal(c, candidate['reviewer_id'])
    row = prep.scoped(store, c, p, id, write=write)
    if row['reviewer_id'] != candidate['reviewer_id']: raise Conflict('reviewer changed; refresh required')
    return row

def read(store, token, id):
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p = store.auth(c, token, lock=True); row = _parent(store, c, p, id)
        source, sha = _sources(store, c, row, p)
        from . import material_corrections as corrections
        view = _view(row, source, sha)
        view['material_checklist'] = _checklist(row, source, view['current_inputs'], sha, corrections._view(c, p, row)['active_targets'])
        return view

def assess(store, token, id, key, data):
    fp = digest(prep.canonical({'preparation_id': str(id), **data.model_dump(mode='json')}))
    with store.connect() as c:
        c.execute("SET LOCAL lock_timeout='3s'")
        p = store.auth(c, token, lock=True); prep.key_lock(c, p, 'readiness:' + key)
        row = _parent(store, c, p, id, write=True)
        # Keys are actor-wide, Case-bound, and replay still checks current authority.
        matches = c.execute('SELECT id,readiness_assessments FROM preparations WHERE readiness_assessments @> %s', (Jsonb([{'actor_id': p['id'], 'request_key': key}]),)).fetchall()
        if matches:
            record = next(a for a in matches[0]['readiness_assessments'] if a['actor_id'] == p['id'] and a['request_key'] == key)
            if matches[0]['id'] != id or record['fingerprint'] != fp: raise Conflict('readiness idempotency fingerprint mismatch')
            return record
        source, sha = _sources(store, c, row, p)
        if row['revision'] != data.expected_preparation_revision or sha != data.expected_source_sha256: raise Conflict('readiness source changed; refresh required')
        history = row['readiness_assessments'] or []
        if len(history) >= LIMIT: raise Conflict('bounded readiness history limit reached')
        record = {'id': str(uuid4()), 'sequence': len(history) + 1, 'actor_id': p['id'], 'request_key': key, 'fingerprint': fp, 'created_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': sha, 'preparation_revision': row['revision'], 'sources': source, 'result': _evaluate(source)}
        c.execute('UPDATE preparations SET readiness_assessments=%s WHERE id=%s', (Jsonb(history + [record]), id))
        return record
