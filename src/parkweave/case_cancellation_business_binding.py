"""Single-Case business connection declarations, not installation or live authority.

Keep the native application/writer connections unchanged. A separately approved
business role may later use the original cancellation API and its current auth.
This module opens no connection, retains no DSN, and generates no SQL GRANT.
"""
import re
from uuid import UUID

import psycopg
from psycopg.conninfo import conninfo_to_dict
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import native_run_access_preflight as preflight, native_run_access_writer as writer
from .case_cancellation import Cancel
from .store import Denied


_SELECT_ALL = ('principals', 'preparations', 'service_dispatches', 'cases',
               'case_local_lifecycles', 'case_local_events', 'runs', 'operations')
_COLUMN_SELECT = (
    ('capability_grants', ('principal_id', 'capability', 'park_id', 'org_id', 'active')),
    ('preparation_grants', ('principal_id', 'capability', 'park_id', 'org_id', 'active')),
    ('schema_version', ('version',)),
    ('service_dispatch_events', ('dispatch_id', 'action')),
    ('service_dispatch_offers', ('dispatch_id', 'state', 'receipt_step_id')),
    ('service_receipt_steps', ('preparation_id', 'case_id')),
    ('preparation_evidence', ('preparation_id', 'id', 'slot', 'version', 'text',
        'source_kind', 'source_label', 'source_sha256', 'authenticity')),
)
_UPDATE = (
    ('preparations', ('revision',)),       # Technical row-lock privilege only.
    ('service_dispatches', ('revision',)), # Technical row-lock privilege only.
    ('cases', ('state',)),
    ('case_local_lifecycles', ('revision', 'state', 'verified_snapshot', 'verified_sha256')),
)
_INSERT = (
    ('case_local_lifecycles', ('preparation_id', 'case_id', 'revision', 'cycle', 'state')),
    ('case_local_events', ('id', 'preparation_id', 'actor_id', 'request_key',
        'fingerprint', 'revision', 'cycle', 'action', 'payload', 'snapshot')),
    ('authorization_audit', ('id', 'principal_id', 'category', 'outcome')),
)


def required_privileges():
    """Fresh rows describing this exact API path; None means current SELECT *."""
    rows = [dict(action='SELECT', table=t, columns=None) for t in _SELECT_ALL]
    for action, entries in (('SELECT', _COLUMN_SELECT), ('UPDATE', _UPDATE), ('INSERT', _INSERT)):
        rows.extend(dict(action=action, table=t, columns=list(columns)) for t, columns in entries)
    return rows


class BusinessBinding(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    installation_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    trial_root: str = Field(pattern=r'^/tmp/parkweave-trial-[a-f0-9]{32}$')
    database_name: str = Field(pattern=r'^fixture_[a-f0-9]{32}$')
    database_oid: int = Field(gt=0)
    system_identifier: str
    database_host: str
    database_port: int = Field(gt=0, le=65535)
    native_application_role: str = Field(pattern=preflight.ROLE_NAME)
    writer_role: str = Field(pattern=preflight.ROLE_NAME)
    installer_role: str = Field(pattern=preflight.ROLE_NAME)
    business_role: str = Field(pattern=preflight.ROLE_NAME)
    source: writer.Source

    @model_validator(mode='after')
    def exact(self):
        if (len({self.native_application_role, self.writer_role, self.installer_role, self.business_role}) != 4 or
                self.database_host != self.trial_root+'/pg/socket' or
                not re.fullmatch(r'[0-9]{1,20}', self.system_identifier) or
                any(str(UUID(v)) != v for v in (self.source.run_id, self.source.case_id, self.source.preparation_id)) or
                any(not v or len(v)>128 or '*' in v for v in (
                    self.source.owner_id, self.source.park_id, self.source.org_id))):
            raise ValueError('exact independent single-Case business declaration required')
        return self

    @classmethod
    def from_spec(cls, spec, *, business_role, trial_root):
        spec = preflight.InstallationSpec.model_validate(spec)
        p = spec.policy
        if (p is None or spec.installer_role is None or spec.transport != 'LINUX_UNIX' or
                spec.permission_strategy != 'DIRECT_DML' or spec.protected_location != trial_root):
            raise Denied('exact isolated installation declaration required')
        return cls(installation_sha256=writer._sha(spec.model_dump()), trial_root=trial_root,
            database_name=p.database_name, database_oid=p.database_oid, system_identifier=p.system_identifier,
            database_host=p.database_host, database_port=p.database_port,
            native_application_role=p.application_role, writer_role=p.writer_role,
            installer_role=spec.installer_role, business_role=business_role, source=p.source)

    def check_spec(self, spec):
        current = type(self).from_spec(spec, business_role=self.business_role, trial_root=self.trial_root)
        if current.model_dump() != self.model_dump():
            raise Denied('business connection declaration changed; explicit rebind required')

    def check_private_dsn(self, value):
        """Compare caller-supplied private input; do not store, return or discover it."""
        try:
            d = conninfo_to_dict(value) if type(value) is str else {}
            if (set(d) != {'host', 'port', 'dbname', 'user', 'password'} or not d['password'] or
                    (d['host'], int(d['port']), d['dbname'], d['user']) != (
                        self.database_host, self.database_port, self.database_name, self.business_role)):
                raise ValueError()
        except (ValueError, TypeError, psycopg.Error):
            raise Denied('exact private business connection input required; values not echoed') from None

    def read_path(self):
        return '/api/preparations/'+self.source.preparation_id+'/case-cancellation'

    def recovery_path(self, original_key):
        if type(original_key) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', original_key):
            raise Denied('original cancellation request key required')
        return self.read_path()+'/recovery/'+original_key

    def check_cancel_request(self, preparation_id, request):
        request = Cancel.model_validate(request)
        if (str(preparation_id) != self.source.preparation_id or
                str(request.case_id) != self.source.case_id or
                request.expected_preparation_revision != self.source.preparation_revision):
            raise Denied('exact bound Case and preparation version required')
        # Lifecycle/hash/reason/confirmation still come from explicit original
        # GET/owner input and are checked by the original transaction, never here.

    def observation(self):
        return dict(status='DECLARATION_VALIDATED_ONLY', actual_run='NOT_RUN',
            connection_authorized=False, installation_authorized=False,
            activation_enabled=False, production_connected=False,
            resource_release_automatic=False, restore_supported=False)
