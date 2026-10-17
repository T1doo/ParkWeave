"""Independent read-only contract for an EXISTING resource-plan approval source.

Only trusted application composition can supply a source adapter. No environment
approval JSON, role, candidate ledger or Run READ decision supplies this adapter.
Adapters must independently authenticate the original source and its current
revision/revocation; the application then checks its exact live local bindings.
Nothing in this module grants or consumes authority or executes a resource action.
"""
from dataclasses import dataclass
import json
from typing import Callable, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from . import ordinary_runtime_read as runtime, controlled_plans as cp, preparation as prep
from . import service_case_steps as steps, bounded_planning as planning, registered_dependencies as dependencies
from .case_resource_delivery import _definition
from .executor_receipts import material_current
from .store import Conflict, Denied

CONTRACT = 'parkweave-existing-resource-plan-approval/1'


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


class Scope(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    preparation_id: UUID = Field(strict=False)
    case_id: UUID = Field(strict=False)
    run_id: UUID = Field(strict=False)
    plan_id: UUID = Field(strict=False)
    plan_revision: int = Field(ge=1, le=64)
    preparation_revision: int = Field(ge=1, le=64)
    owner_id: str
    park_id: str
    org_id: str
    plan_definition_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    action_scope_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    source_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    authority_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    database_binding_sha256: str = Field(pattern='^[a-f0-9]{64}$')


@dataclass(frozen=True)
class Lookup:
    scope: Scope
    viewer_id: str
    approval_id: UUID | None = None


@dataclass(frozen=True)
class ReadOnlyApprovalProvider:
    """Trusted host seam, NOT a client-authored approval or a production adapter.

    read_existing must select one existing original record (never create it).
    verify_existing must validate source authenticity/current revision using its
    already authorized trust mechanism, not trust a field in that record. No
    backend/trust root is supplied by this repository. Synthetic adapters prove
    this contract only and are not accepted as real approval evidence.
    """
    source_id: str
    read_existing: Callable[[Lookup], bytes | None]
    verify_existing: Callable[[Lookup, bytes], bool]
    source_kind: Literal['EXISTING_AUTHORITY_ADAPTER', 'SYNTHETIC_CONTRACT_FIXTURE'] = 'EXISTING_AUTHORITY_ADAPTER'

    def __post_init__(self):
        import re
        if (not isinstance(self.source_id, str) or not re.fullmatch('[a-zA-Z0-9_.:-]{1,100}', self.source_id)
                or not callable(self.read_existing) or not callable(self.verify_existing)
                or self.source_kind not in ('EXISTING_AUTHORITY_ADAPTER', 'SYNTHETIC_CONTRACT_FIXTURE')):
            raise Denied('explicit existing resource approval source adapter required')


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['parkweave-existing-resource-plan-approval/1']
    purpose: Literal['RESOURCE_PLAN_APPROVAL']
    source_id: str = Field(min_length=1, max_length=100)
    approval_id: UUID = Field(strict=False)
    record_revision: int = Field(ge=1)
    original_record_id: str = Field(min_length=1, max_length=200)
    binding: Scope
    approver_id: str = Field(min_length=1, max_length=100)
    approver_role: Literal['enterprise_operator', 'park_specialist']
    authority_reference: str = Field(min_length=1, max_length=200)
    approved_at: AwareDatetime = Field(strict=False)
    valid_from: AwareDatetime = Field(strict=False)
    valid_until: AwareDatetime = Field(strict=False)
    state: Literal['APPROVED', 'REVOKED']
    revoked_at: AwareDatetime | None = Field(default=None, strict=False)

    @field_validator('original_record_id', 'authority_reference')
    @classmethod
    def nonblank_reference(cls, value):
        if not value.strip():
            raise ValueError('existing source reference required')
        return value

    @field_validator('approved_at', 'valid_from', 'valid_until', 'revoked_at', mode='before')
    @classmethod
    def explicit_timestamp(cls, value):
        if value is not None and (type(value) is not str or len(value) > 64
                                  or not value.endswith(('Z', '+00:00'))):
            raise ValueError('explicit ISO UTC timestamp required')
        return value

    @field_validator('approved_at', 'valid_from', 'valid_until', 'revoked_at')
    @classmethod
    def utc(cls, value):
        if value is not None and value.utcoffset().total_seconds() != 0:
            raise ValueError('explicit UTC approval time required')
        return value

    @model_validator(mode='after')
    def interval(self):
        if self.valid_until <= self.valid_from or self.approved_at > self.valid_until:
            raise ValueError('original approval interval invalid')
        if (self.state == 'REVOKED') != (self.revoked_at is not None):
            raise ValueError('original revocation state/time required')
        return self


class Selection(runtime.Selection):
    expected_plan_id: UUID
    expected_plan_revision: int = Field(ge=1, le=64)
    expected_context_sha256: str = Field(pattern='^[a-f0-9]{64}$')


def validate_provider(provider):
    if provider is not None and type(provider) is not ReadOnlyApprovalProvider:
        raise Denied('independent read-only resource approval provider required; no isolated or Run access substitution')
    return provider


def _boundary(state, reason, **extra):
    return dict(contract=CONTRACT, purpose='RESOURCE_PLAN_APPROVAL', state=state, reason=reason,
                read_only=True, verified_existing_approval=state == 'VERIFIED',
                execution_authorized=False, approval_consumable=False, decision_writes_enabled=False,
                run_read_access_granted=False, **extra)


def _authority(c, parent):
    ids = sorted({parent['owner_id'], parent['reviewer_id']})
    principals = c.execute('SELECT id,role,active,park_id,org_id,xmin::text generation FROM principals '
                           'WHERE id=ANY(%s) ORDER BY id', (ids,)).fetchall()
    capability = c.execute('SELECT principal_id,capability,active,revision,park_id,org_id,xmin::text generation '
                           'FROM capability_grants WHERE principal_id=ANY(%s) ORDER BY principal_id,capability', (ids,)).fetchall()
    preparation = c.execute('SELECT principal_id,capability,active,park_id,org_id,xmin::text generation '
                            'FROM preparation_grants WHERE principal_id=ANY(%s) ORDER BY principal_id,capability', (ids,)).fetchall()
    fields = c.execute('SELECT principal_id,field_name,purpose,capability,active,revision,valid_until,park_id,org_id,xmin::text generation '
                       'FROM field_grants WHERE principal_id=%s ORDER BY field_name,purpose,capability', (parent['owner_id'],)).fetchall()
    return cp._normal(dict(principals=principals, capabilities=capability, preparation=preparation, fields=fields))


def _snapshot(store, c, parent):
    plan = parent.get('service_case_plan')
    if not plan or sum(s.get('adapter_id') == 'P2' for s in plan.get('steps', [])) != 1:
        return None
    dependencies.plan_proof(parent, plan)
    steps._initial_adoption_proof(parent, plan)
    catalog, generation = runtime._catalog(c, parent)
    p1 = cp.binding_p1(c, parent, dict(preparation_id=str(parent['id']), case_id=str(parent['case_id']),
                                     run_id=str(parent['run_id']), service_id=parent['service_id'],
                                     service_version=parent['service_version'], preparation_revision=parent['revision'],
                                     preparation_sha256=parent['review_sha256']), store=store)
    materials = c.execute('SELECT id,slot,version,source_sha256,xmin::text generation FROM preparation_evidence '
                          'WHERE preparation_id=%s ORDER BY slot,version', (parent['id'],)).fetchall()
    authority = _authority(c, parent)
    actions = cp._normal(planning.ACTIONS['P2'])
    source = cp._normal(dict(p1=p1, material_versions=materials, catalog=catalog, catalog_generation=generation,
                            case_state=prep.case_state(c, parent), current_binding=steps._binding(c, parent)))
    database = c.execute('SELECT current_database() name,current_user role,oid FROM pg_database WHERE datname=current_database()').fetchone()
    database.update(host=c.info.host, port=c.info.port)
    scope = Scope(preparation_id=parent['id'], case_id=parent['case_id'], run_id=parent['run_id'],
                  plan_id=UUID(plan['id']), plan_revision=plan['revision'], preparation_revision=parent['revision'],
                  owner_id=parent['owner_id'], park_id=parent['park_id'], org_id=parent['org_id'],
                  plan_definition_sha256=_definition(plan), action_scope_sha256=cp._hash(actions),
                  source_sha256=cp._hash(source), authority_sha256=cp._hash(authority),
                  database_binding_sha256=cp._hash(cp._normal(database)))
    issues = steps._binding_issues(c, parent, plan, store=store)
    if prep.case_write_blocked(c, parent): issues.append('CASE_NOT_CURRENT')
    if not material_current(c, parent, store): issues.append('CURRENT_CONFIRMED_MATERIALS_REQUIRED')
    owner = next((p for p in authority['principals'] if p['id'] == parent['owner_id']), None)
    try:
        if (not owner or not owner['active'] or (owner['park_id'], owner['org_id']) !=
                (parent['park_id'], parent['org_id'])):
            raise Denied('current exact owner required')
        prep.grant(store, c, owner, 'PREPARE')
        store.check_capability(c, owner, 'EXECUTE')
    except Denied:
        issues.append('CURRENT_OWNER_AUTHORITY_REQUIRED')
    return dict(scope=scope, context_sha256=cp._hash(scope.model_dump(mode='json')), actions=actions,
                principals=authority['principals'], issues=sorted(set(issues)))


def _base(selection):
    return runtime.Selection.model_validate({k: getattr(selection, k) for k in runtime.Selection.model_fields})


def context(store, token, preparation_id, selection, provider):
    validate_provider(provider)
    with runtime.selected(store, token, preparation_id, selection) as (c, _, parent, _, _, _):
        try: snapshot = _snapshot(store, c, parent)
        except (Conflict, ValueError, KeyError, TypeError):
            return _boundary('MISSING_SOURCE', 'CURRENT_PLAN_SOURCE_UNAVAILABLE')
        if snapshot is None: return _boundary('MISSING_SOURCE', 'ADOPTED_RESOURCE_PLAN_REQUIRED')
        return _boundary('READY_TO_READ' if provider else 'CONTRACT_UNAVAILABLE',
                         'READ_EXISTING_SOURCE_REQUIRED' if provider else 'EXISTING_APPROVAL_PROVIDER_REQUIRED',
                         binding=snapshot['scope'].model_dump(mode='json'), context_sha256=snapshot['context_sha256'],
                         action_scope=snapshot['actions'], current_source_issues=snapshot['issues'])


def _read(provider, lookup):
    raw = provider.read_existing(lookup)
    if raw is None: return None, None
    if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
        raise ValueError('bounded original source bytes required')
    if provider.verify_existing(lookup, raw) is not True:
        raise ValueError('original source verification refused')
    record = ApprovalRecord.model_validate(strict_json(raw))
    if record.source_id != provider.source_id: raise ValueError('exact source identity required')
    if lookup.approval_id is not None and record.approval_id != lookup.approval_id:
        raise ValueError('exact original approval record required')
    return record, raw


def read(store, token, preparation_id, selection, provider, approval_id=None):
    validate_provider(provider)
    if type(selection) is not Selection: raise Denied('exact resource approval selection required')
    with runtime.selected(store, token, preparation_id, _base(selection)) as (c, actor, parent, _, _, _):
        try: before = _snapshot(store, c, parent)
        except (Conflict, ValueError, KeyError, TypeError):
            return _boundary('MISSING_SOURCE', 'CURRENT_PLAN_SOURCE_UNAVAILABLE')
        if before is None: return _boundary('MISSING_SOURCE', 'ADOPTED_RESOURCE_PLAN_REQUIRED')
        scope = before['scope']
        if (scope.plan_id, scope.plan_revision, before['context_sha256']) != (
                selection.expected_plan_id, selection.expected_plan_revision, selection.expected_context_sha256):
            raise Conflict('resource approval plan/version/source selection changed; reread original context')
        if provider is None: return _boundary('CONTRACT_UNAVAILABLE', 'EXISTING_APPROVAL_PROVIDER_REQUIRED')
        lookup = Lookup(scope, actor['id'], approval_id)
        try:
            record, raw = _read(provider, lookup)
            if record is None: return _boundary('MISSING_SOURCE', 'EXISTING_APPROVAL_RECORD_REQUIRED')
            # Explicit original-ID second read catches replacement/revocation while checking the first read.
            again, second = _read(provider, Lookup(scope, actor['id'], record.approval_id))
        except Exception:
            return _boundary('MISSING_SOURCE', 'EXISTING_APPROVAL_SOURCE_UNVERIFIED')
        current_actor = store.auth(c, token, lock=True)
        current_parent, _ = prep.entry_context(store, c, current_actor, preparation_id)
        try: after = _snapshot(store, c, current_parent)
        except (Conflict, ValueError, KeyError, TypeError): after = None
        if after is None or after['context_sha256'] != before['context_sha256']:
            return _boundary('INVALID', 'CURRENT_PERMISSION_OR_SOURCE_CHANGED')
        if raw != second or record != again:
            return _boundary('INVALID', 'ORIGINAL_APPROVAL_CHANGED_DURING_READ')
        if record.binding != scope: return _boundary('INVALID', 'APPROVAL_EXACT_BINDING_MISMATCH')
        approver = next((p for p in after['principals'] if p['id'] == record.approver_id), None)
        if (not approver or not approver['active'] or approver['role'] != record.approver_role
                or (approver['park_id'], approver['org_id']) != (scope.park_id, scope.org_id)):
            return _boundary('INVALID', 'CURRENT_APPROVER_IDENTITY_REQUIRED')
        try:
            prep.grant(store, c, approver, 'PREPARE' if approver['role'] == 'enterprise_operator' else 'REVIEW_ASSIGNED')
        except Denied:
            return _boundary('INVALID', 'CURRENT_APPROVER_PERMISSION_REQUIRED')
        try:
            if provider.verify_existing(Lookup(scope, current_actor['id'], record.approval_id), raw) is not True:
                return _boundary('INVALID', 'CURRENT_APPROVAL_SOURCE_CHANGED')
        except Exception:
            return _boundary('MISSING_SOURCE', 'EXISTING_APPROVAL_SOURCE_UNVERIFIED')
        now = c.execute('SELECT clock_timestamp() now').fetchone()['now']
        reason = ('ORIGINAL_APPROVAL_REVOKED' if record.state == 'REVOKED' else
                  'ORIGINAL_APPROVAL_EXPIRED' if now >= record.valid_until else
                  'ORIGINAL_APPROVAL_NOT_YET_VALID' if now < record.valid_from or now < record.approved_at else
                  'CURRENT_PLAN_SOURCE_INVALID' if after['issues'] else None)
        state = 'INVALID' if reason else 'VERIFIED'
        return _boundary(state, reason or 'EXISTING_APPROVAL_SOURCE_VERIFIED',
                         record=record.model_dump(mode='json'), action_scope=after['actions'],
                         approval_source_kind=provider.source_kind, production_installation_verified=False,
                         checked_at=now.isoformat(),
                         context_sha256=after['context_sha256'],
                         original_record_path=f'/api/preparations/{preparation_id}/runtime/resource-plan-approval/records/{record.approval_id}')
