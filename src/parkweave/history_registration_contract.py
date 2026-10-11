"""Synthetic declaration consistency only; no enrollment, loader or authority.

Independent observations are explicit fixture inputs, never discovered or inferred.
Their provenance labels are data, not a verified trust root. Even MATCH cannot
detect an indistinguishable complete replay of all caller-provided observations.
No I/O, environment, clock discovery, history/proof parsing or production hook.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath, PureWindowsPath
import re
from uuid import UUID


DECLARATION_KIND = 'SYNTHETIC_HISTORY_REGISTRATION_DECLARATION'
OBSERVATION_KIND = 'SYNTHETIC_INDEPENDENT_OBSERVATION'
PURPOSE = 'HISTORY_SUMMARY_READ_ONLY'
MAX_REVISION = 2**63 - 1
# Structural document compatibility pinned to parent 008ecdaf; not execution proof.
P4_DOCUMENT = ('ISOLATED_REGISTERED_P4_RECEIPT_EXECUTION_PREVIEW', 2,
               '61037dc0e1675e112fec756bf3b96ef5db4afd11b8dd9981ba0a32a7354db1ad')
P5_DOCUMENT = ('ISOLATED_REGISTERED_P5_LOCAL_CASE_EXECUTION_PREVIEW', 3,
               'deffd62e6e628ee17f4a9569c04d075af37c93587c67473cf2424abe6bc89a78')


@dataclass(frozen=True, slots=True)
class MaintainerBinding:
    installation_owner_ref: str
    database_owner_role: str
    application_role: str


@dataclass(frozen=True, slots=True)
class InstallationBinding:
    id: UUID
    generation: int
    root_ref: str
    owner_ref: str


@dataclass(frozen=True, slots=True)
class DatabaseBinding:
    name: str
    oid: str
    system_identifier: str
    data_directory_ref: str
    owner_role: str


@dataclass(frozen=True, slots=True)
class HistoryBinding:
    owner: str
    park: str
    org: str
    preparation: UUID
    case: UUID
    run: UUID
    stage: str
    scope: str
    namespace: str
    document_version: int
    document_contract_sha256: str


@dataclass(frozen=True, slots=True)
class OriginalAnchor:
    id: UUID
    key: str
    row_sha256: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class RegistrationDeclaration:
    kind: str
    schema_version: int
    purpose: str
    enrollment_id: UUID
    revision: int
    maintainer: MaintainerBinding
    approval_ref: str
    approved_manifest_sha256: str
    installation: InstallationBinding
    database: DatabaseBinding
    history: HistoryBinding
    anchors: tuple[OriginalAnchor, ...]
    valid_from: datetime
    valid_until: datetime
    revoked: bool
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class IndependentObservation:
    kind: str
    complete: bool | None
    generation_known: bool | None
    maintenance_isolated: bool | None
    registration: RegistrationDeclaration | None
    installation: InstallationBinding | None
    database: DatabaseBinding | None
    history: HistoryBinding | None
    anchors: tuple[OriginalAnchor, ...] | None
    approved_manifest_sha256: str | None
    minimum_revision: int | None
    ever_revoked: bool | None
    current_read: bool | None
    sources_current: bool | None
    now: datetime | None


@dataclass(frozen=True, slots=True)
class ContractClassification:
    classification: str
    reason: str

    def __bool__(self):
        raise TypeError('declaration classification is not an access permission')


def _text(value, limit=200):
    return (type(value) is str and 1 <= len(value.encode('utf-8')) <= limit and
            value == value.strip() and '*' not in value and
            not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _path(value):
    if not _text(value, 1024) or value.startswith(('//', '\\\\')):
        return False
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    return ((posix.is_absolute() or windows.is_absolute()) and
            '..' not in posix.parts and '..' not in windows.parts)


def _positive(value):
    return type(value) is int and 1 <= value <= MAX_REVISION


def _decimal(value, maximum):
    return (type(value) is str and re.fullmatch(r'[1-9][0-9]{0,19}', value) is not None and
            int(value) <= maximum)


def _hash(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _utc(value):
    # Fixed zero-offset stdlib timezone only: no caller-defined tzinfo callbacks.
    return (type(value) is datetime and type(value.tzinfo) is timezone and
            value.utcoffset() == timedelta(0))


def _maintainer(value):
    return (type(value) is MaintainerBinding and
            all(_text(x) for x in (value.installation_owner_ref, value.database_owner_role, value.application_role)) and
            value.database_owner_role != value.application_role)


def _installation(value):
    return (type(value) is InstallationBinding and type(value.id) is UUID and
            _positive(value.generation) and _path(value.root_ref) and _text(value.owner_ref))


def _database(value):
    return (type(value) is DatabaseBinding and _text(value.name) and
            _decimal(value.oid, 2**32 - 1) and _decimal(value.system_identifier, 2**64 - 1) and
            _path(value.data_directory_ref) and _text(value.owner_role))


def _history(value):
    if type(value) is not HistoryBinding or type(value.stage) is not str or value.stage not in ('P4', 'P5'):
        return False
    scope, version, contract = P4_DOCUMENT if value.stage == 'P4' else P5_DOCUMENT
    return (all(_text(x) for x in (value.owner, value.park, value.org, value.scope, value.namespace)) and
            all(type(x) is UUID for x in (value.preparation, value.case, value.run)) and
            value.scope == scope and type(value.document_version) is int and value.document_version == version and
            _hash(value.document_contract_sha256) and value.document_contract_sha256 == contract)


def _anchors(value):
    if type(value) is not tuple or not 1 <= len(value) <= 16:
        return False
    ids, keys = set(), set()
    for anchor in value:
        if (type(anchor) is not OriginalAnchor or type(anchor.id) is not UUID or
                type(anchor.key) is not str or re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', anchor.key) is None or
                not _hash(anchor.row_sha256) or not _hash(anchor.source_sha256) or
                anchor.id in ids or anchor.key in keys):
            return False
        ids.add(anchor.id);keys.add(anchor.key)
    return True


def _declaration(value):
    if type(value) is not RegistrationDeclaration:
        return False
    return (type(value.kind) is str and value.kind == DECLARATION_KIND and
            type(value.schema_version) is int and value.schema_version == 1 and
            type(value.purpose) is str and value.purpose == PURPOSE and type(value.enrollment_id) is UUID and
            _positive(value.revision) and _maintainer(value.maintainer) and _text(value.approval_ref) and
            _hash(value.approved_manifest_sha256) and _installation(value.installation) and
            _database(value.database) and _history(value.history) and _anchors(value.anchors) and
            value.maintainer.installation_owner_ref == value.installation.owner_ref and
            value.maintainer.database_owner_role == value.database.owner_role and
            _utc(value.valid_from) and _utc(value.valid_until) and value.valid_from < value.valid_until and
            type(value.revoked) is bool and
            ((_utc(value.revoked_at) if value.revoked else value.revoked_at is None)))


def _observation(value):
    return (type(value) is IndependentObservation and type(value.kind) is str and value.kind == OBSERVATION_KIND and
            value.complete is True and value.generation_known is True and value.maintenance_isolated is True and
            _declaration(value.registration) and _installation(value.installation) and _database(value.database) and
            _history(value.history) and _anchors(value.anchors) and _hash(value.approved_manifest_sha256) and
            _positive(value.minimum_revision) and type(value.ever_revoked) is bool and
            type(value.current_read) is bool and type(value.sources_current) is bool and _utc(value.now))


def check_history_registration_contract(declaration, before=None, after=None, *, enabled_for_synthetic_checks=False):
    """Classify supplied synthetic data. MATCH is never a permission or receipt.

    No trusted inputs are reconstructed from the declaration, proof or hashes.
    Unknown provenance/isolation/completeness fails closed as UNKNOWN. The caller
    can lie or replay *all* fixture inputs: this function does not authenticate it.
    """
    if enabled_for_synthetic_checks is not True:
        return ContractClassification('UNKNOWN', 'DEFAULT_DISABLED')
    try:
        if not _observation(before) or not _observation(after):
            return ContractClassification('UNKNOWN', 'INDEPENDENT_OBSERVATION_UNAVAILABLE')
        if not _declaration(declaration):
            return ContractClassification('MISMATCH', 'INVALID_DECLARATION')
        if after.now < before.now:
            return ContractClassification('MISMATCH', 'CLOCK_REGRESSION')
        if (after.minimum_revision < before.minimum_revision or
                after.registration.revision < before.registration.revision or
                any(o.registration.revision < o.minimum_revision or declaration.revision < o.minimum_revision for o in (before, after))):
            return ContractClassification('MISMATCH', 'REVISION_REGRESSION')
        if before.ever_revoked and not after.ever_revoked:
            return ContractClassification('MISMATCH', 'REVOCATION_REGRESSION')
        if declaration.revoked or any(o.ever_revoked or o.registration.revoked for o in (before, after)):
            return ContractClassification('MISMATCH', 'TERMINAL_REVOCATION')
        fields = ('registration', 'installation', 'database', 'history', 'anchors', 'approved_manifest_sha256',
                  'minimum_revision', 'ever_revoked', 'current_read', 'sources_current')
        if any(getattr(before, key) != getattr(after, key) for key in fields):
            return ContractClassification('MISMATCH', 'OBSERVATION_CHANGED')
        if any(o.registration != declaration or o.installation != declaration.installation or
               o.database != declaration.database or o.history != declaration.history or
               o.anchors != declaration.anchors or o.approved_manifest_sha256 != declaration.approved_manifest_sha256
               for o in (before, after)):
            return ContractClassification('MISMATCH', 'BINDING_MISMATCH')
        if not all(declaration.valid_from <= o.now < declaration.valid_until for o in (before, after)):
            return ContractClassification('MISMATCH', 'OUTSIDE_ABSOLUTE_VALIDITY')
        if not before.current_read or not before.sources_current:
            return ContractClassification('MISMATCH', 'CURRENT_READ_OR_SOURCE_MISMATCH')
        return ContractClassification('MATCH', 'SYNTHETIC_DECLARATION_CONSISTENT_ONLY')
    except (TypeError, ValueError, AttributeError, OverflowError, UnicodeError):
        return ContractClassification('UNKNOWN', 'INVALID_OBSERVATION_OR_VALUE')
