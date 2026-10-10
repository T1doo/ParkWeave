"""Owner-reviewed factual brief, appended through existing material records.

No policy requirements, models, publication, new schema or authority. Only
explicit current Case-purpose selections may enter the server-generated text.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb
from . import preparation as prep, case_fact_clarifications as facts
from . import material_corrections as corrections
from .store import Conflict, Denied, digest

RECIPE = 'USER_SELECTED_PREPARATION_BRIEF_V1'
LABELS = {'region': '地区自述', 'employees': '员工人数自述', 'service_need': '服务诉求自述'}

class Save(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_preparation_revision: int = Field(ge=1, le=61)
    expected_source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_material_share: Literal[True]
    expected_reviewer_id: str = Field(min_length=1, max_length=100)

    @field_validator("confirm_material_share", mode="before")
    @classmethod
    def explicit_true(cls, value):
        if value is not True: raise ValueError("explicit material sharing confirmation required")
        return value


def _context(store, c, token, id, key=None):
    c.execute("SET LOCAL lock_timeout='3s'")
    p = store.auth(c, token, lock=True)
    if p['role'] != 'enterprise_operator': raise Denied('owner material draft required')
    if key is not None: prep.key_lock(c, p, key)
    candidate = c.execute('SELECT owner_id,reviewer_id FROM preparations WHERE id=%s AND park_id=%s AND org_id=%s', (id, p['park_id'], p['org_id'])).fetchone()
    if not candidate or candidate['owner_id'] != p['id']: raise Denied('own material draft required')
    store.lock_principal(c, candidate['reviewer_id'])
    row = prep.scoped(store, c, p, id, write=key is not None)
    if row['reviewer_id'] != candidate['reviewer_id']: raise Conflict('material reviewer changed')
    facts._field_locks(c, p['id'])
    facts._scope(store, c, p, row, require_write=key is not None)
    return p, row


def _reviewer_source(c, row):
    reviewer = c.execute('SELECT id,park_id,org_id,role,active FROM principals WHERE id=%s', (row['reviewer_id'],)).fetchone()
    read = c.execute("SELECT principal_id,park_id,org_id,active,revision FROM capability_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability='READ'", (row['reviewer_id'], row['park_id'], row['org_id'])).fetchone()
    grant = c.execute("SELECT principal_id,park_id,org_id,active FROM preparation_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND capability='REVIEW_ASSIGNED'", (row['reviewer_id'], row['park_id'], row['org_id'])).fetchone()
    source = dict(principal=reviewer, read=read, preparation=grant)
    valid = bool(reviewer and reviewer['active'] and reviewer['role']=='park_specialist' and
                 (reviewer['park_id'],reviewer['org_id'])==(row['park_id'],row['org_id']) and
                 read and read['active'] and grant and grant['active'])
    return source, valid


def _build(store, c, p, row):
    ledger = facts._stored_ledger(c, row)
    status = facts.gate(store, c, row)
    catalog = c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s',
        (row['park_id'], row['service_id'], row['service_version'])).fetchone()
    source = catalog.get('source') if catalog else None
    known = bool(catalog and catalog['namespace'] == 'SYNTHETIC' and isinstance(source, dict) and
                 source.get('kind') == 'SYNTHETIC' and source.get('id') and source.get('revision'))
    reviewer_source, reviewer_valid = _reviewer_source(c, row)
    issues = []
    if not reviewer_valid: issues.append('CURRENT_ASSIGNED_REVIEWER_AUTHORITY_REQUIRED')
    if not known: issues.append('CURRENT_SYNTHETIC_SERVICE_SOURCE_REQUIRED')
    if not ledger or status['state'] != 'CURRENT': issues.append('CURRENT_EXPLICIT_FACT_SELECTION_REQUIRED')
    result = dict(preparation_id=str(row['id']), case_id=str(row['case_id']), run_id=str(row['run_id']),
        preparation_revision=row['revision'], recipe=RECIPE, state='BLOCKED' if issues else 'DRAFT',
        issues=issues, draft=None, can_save=False, scope='OWNER_SELECTED_SYNTHETIC_MATERIAL_PREPARATION',
        authenticity='USER_ASSERTED_UNVERIFIED', qualification='NOT_EVALUATED',
        external_acceptance='NOT_SUBMITTED', offline_fulfillment='NO_EVIDENCE', case_goal_completed=False,
        policy_requirements_generated=False, reviewer_id=row['reviewer_id'])
    if row['revision'] > 61: issues.append('RESERVE_REVIEW_AND_CONFIRM_HISTORY_CAPACITY'); result.update(state='BLOCKED',issues=issues)
    if issues: return result
    snapshot, fact_sha, applicable = facts._sources(store, c, row, p)
    choices = ledger['events'][-1]['choices']
    by_id = {s['id']: s for s in snapshot['sources']}
    selected = {choice['field']: by_id[choice['assertion_id']] for choice in choices}
    if set(selected) != set(facts.FIELDS) or not all(applicable[s['id']] for s in selected.values()):
        raise Conflict('current selected draft facts required')
    # This existing sharing recipe authorizes original global self assertions.
    # Case-only document extracts must not be copied or relabeled as self assertions.
    if any(s['source_kind'] != 'USER_ASSERTED_SYNTHETIC' for s in selected.values()):
        result.update(state='BLOCKED',issues=issues+['OWNER_CASE_ONLY_SOURCE_NOT_SHARED_BY_BRIEF_RECIPE'])
        return result
    request = row.get('request_intent')
    current_request = request['request_text'] if request else row['goal']
    text = '\n'.join(['企业资料准备诉求摘要（合成、自述未核实）', '本次企业诉求：' + current_request] +
        [LABELS[field] + '：' + prep.canonical(selected[field]['value']) + '（单位：' + selected[field]['unit'] + '；所选来源版本：' + str(selected[field]['revision']) + '；来源指纹：' + selected[field]['fingerprint'] + '）' for field in facts.FIELDS] +
        ['用途：仅用于本事项资料整理和获派专员核对。',
         '缺口：企业自述不证明真实性、资格或机构受理；所需证明及政策要求须由合法来源另行明确。'])
    items = prep.latest(c, row['id'])
    by_slot = {i['slot']: i for i in items}
    checklist = [dict(slot=slot, state='PROVIDED_UNVERIFIED' if slot in by_slot else 'MISSING',
        evidence_id=str(by_slot[slot]['id']) if slot in by_slot else None,
        version=by_slot[slot]['version'] if slot in by_slot else 0,
        source_sha256=by_slot[slot]['source_sha256'] if slot in by_slot else None,
        next_action='CHECK_CURRENT_CONTENT_WITH_ASSIGNED_REVIEWER' if slot in by_slot else 'SUPPLY_OWN_MATERIAL') for slot in prep.SLOTS]
    outline_edit_required = 'material_outline' not in by_slot or any(t['slot']=='material_outline' and not corrections.submitted(t,by_slot.get('material_outline'),row['owner_id']) for t in corrections.active(row.get('material_corrections')))
    followups = 2 + int(outline_edit_required)
    capacity = row['revision'] + 1 + followups <= 64
    pending = [dict(slot=t['slot'], reason=r['reason'], base_version=t['base_version'], status=t['status'])
        for r in row.get('material_corrections') or [] for t in r['targets'] if t['status'] == 'ACTIVE']
    binding = dict(recipe=RECIPE, case_id=str(row['case_id']), run_id=str(row['run_id']),
        preparation_id=str(row['id']), preparation_revision=row['revision'],
        fact_source_sha256=fact_sha, fact_decision_sha256=ledger['events'][-1]['decision_sha256'],
        service=catalog, reviewer=reviewer_source, materials=items, correction_requests=row.get('material_corrections'), draft_text=text)
    sha = facts._hash(binding)
    too_long = len(text) > 4000
    result.update(source_sha256=sha, source_fact_decision_sha256=ledger['events'][-1]['decision_sha256'],
        state='BLOCKED' if too_long or not capacity else 'DRAFT', issues=(['DRAFT_TOO_LONG_USE_MANUAL_MATERIAL_ENTRY'] if too_long else []) + ([] if capacity else ['RESERVE_MATERIAL_REVIEW_CONFIRM_HISTORY_CAPACITY']),
        draft=None if too_long else dict(slot='need_summary', text=text, text_sha256=digest(text)),
        material_checklist=checklist, pending_corrections=pending,
        can_save=not too_long and capacity, required_followup_revisions=followups, remaining_history_revisions=64-row['revision'],
        service_sha256=facts._hash(catalog), reviewer_sha256=facts._hash(reviewer_source),
        selected_sources=[dict(field=f,id=selected[f]['id'],revision=selected[f]['revision'],fingerprint=selected[f]['fingerprint']) for f in facts.FIELDS],
        share_recipient='EXISTING_ASSIGNED_PREPARATION_REVIEWER',
        next_steps=['OWNER_CHECK_AND_EXPLICITLY_SHARE_BRIEF', 'SUPPLY_OR_CORRECT_OWN_MATERIAL_OUTLINE',
                    'ASSIGNED_REVIEWER_CHECK_CURRENT_PACK', 'OWNER_CONFIRM_REVIEWED_PACK'])
    return result


def read(store, token, id):
    with store.connect() as c:
        p, row = _context(store, c, token, id)
        return _build(store, c, p, row)


def save(store, token, id, key, data):
    data = Save.model_validate(data)
    fp = facts._hash(dict(preparation_id=str(id), action='SAVE_OWNER_SELECTED_BRIEF', **data.model_dump()))
    with store.connect() as c:
        p, row = _context(store, c, token, id, key)
        # Recovery still requires current field/owner rights. Historical success
        # must never be presented as a fresh current-source generation.
        old = prep.replay(c, p, key, fp, id)
        if old: return dict(old, recovery='HISTORICAL_COMMITTED_EVENT', current_result=False)
        current = _build(store, c, p, row)
        if (data.expected_reviewer_id != row['reviewer_id'] or not current['can_save'] or row['revision'] != data.expected_preparation_revision or
            current.get('source_sha256') != data.expected_source_sha256):
            raise Conflict('material draft source changed or blocked; refresh required')
        added = prep._insert_evidence(c, p, row, 'need_summary', current['draft']['text'],
            'USER_STATEMENT', '企业明确来源整理草稿 v1 / ' + current['source_sha256'])
        ledger = corrections.submit(row, p, added) if row.get('material_corrections') else None
        state = 'IN_PREPARATION'
        if ledger:
            materials = {i['slot']: i for i in corrections.materials(c, id)}
            if any(not corrections.submitted(t, materials.get(t['slot']), row['owner_id']) for t in corrections.active(ledger)):
                state = 'CHANGES_REQUESTED'
        updated = c.execute('UPDATE preparations SET state=%s,revision=revision+1,review_sha256=NULL,material_corrections=%s WHERE id=%s RETURNING *',
            (state, Jsonb(ledger) if ledger is not None else None, id)).fetchone()
        from .controlled_plans import invalidate
        invalidate(c, id, 1)
        result = prep.event(c, p, updated, key, fp, 'ADD_EVIDENCE',
            snapshot_sha256=prep.snapshot(updated, prep.latest(c, id)),
            material_draft=dict(recipe=RECIPE, source_sha256=current['source_sha256'],
                source_fact_decision_sha256=current['source_fact_decision_sha256'],
                evidence_id=str(added['id']), evidence_version=added['version'], text_sha256=added['source_sha256'],
                service_sha256=current['service_sha256'], reviewer_id=row['reviewer_id'],
                reviewer_sha256=current['reviewer_sha256'], confirm_material_share=True, authenticity='UNVERIFIED', requires_independent_review=True))
        # Timed facts and grants may expire during INSERT/event work. Roll back
        # the complete original-table transaction if they are no longer current.
        late_catalog = c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s', (row['park_id'],row['service_id'],row['service_version'])).fetchone()
        late_reviewer, late_valid = _reviewer_source(c, updated)
        if (facts._hash(late_catalog)!=current['service_sha256'] or not late_valid or facts._hash(late_reviewer)!=current['reviewer_sha256']):
            raise Conflict('material draft catalog or receiver changed during save')
        if facts.gate(store, c, updated)['state'] != 'CURRENT':
            raise Conflict('selected fact purpose expired during material draft save')
        return result


def decorate_materials(c, row, items, history, fact_status):
    """Opaque current/history projection; no owner-only fact values or IDs."""
    catalog = c.execute('SELECT service_id,version,source,namespace,qualification FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=%s', (row['park_id'], row['service_id'], row['service_version'])).fetchone()
    reviewer_source, valid = _reviewer_source(c, row)
    for item in items:
        record = next((h['payload']['material_draft'] for h in history if h['payload'].get('material_draft',{}).get('evidence_id')==str(item['id'])), None)
        if record:
            current = bool(fact_status and fact_status.get('state')=='CURRENT' and valid and
                record['source_fact_decision_sha256']==fact_status.get('decision_sha256') and
                record['service_sha256']==facts._hash(catalog) and record['reviewer_id']==row['reviewer_id'] and
                record['reviewer_sha256']==facts._hash(reviewer_source) and record['text_sha256']==item['source_sha256']==digest(item['text']))
            item['material_draft_source'] = dict(recipe=record['recipe'], source_current=current,
                source_sha256=record['source_sha256'], requires_independent_review=True)


def source_status(c, row, fact_status):
    history=c.execute("SELECT payload FROM preparation_events WHERE preparation_id=%s AND payload ? 'material_draft' ORDER BY revision",(row['id'],)).fetchall()
    if not history:return None
    items=prep.latest(c,row['id']);decorate_materials(c,row,items,history,fact_status)
    generated=[i for i in items if i.get('material_draft_source')]
    if not generated:return None  # explicitly replaced by an original manual material
    return dict(satisfied=all(i['material_draft_source']['source_current'] for i in generated),
                items=[dict(slot=i['slot'],evidence_id=str(i['id']),**i['material_draft_source']) for i in generated])
