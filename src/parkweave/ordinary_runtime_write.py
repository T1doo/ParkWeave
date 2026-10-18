"""Explicit ordinary client binding, never an installer or authority issuer.

The environment selects a root-protected public record. That record authorizes
only the original COMMAND/ACTIVATE channel for one existing scope and pins the
original protected host binding. No credentials, test permits or private writer
context enter the API. The existing writer remains the transaction authority.
"""
from typing import Literal
import sys

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import psycopg

from .intern_adapter import strict_json
from .ordinary_runtime_read import ReadConfig, check_scope
from .store import Conflict, Denied

LIMIT = 16384


class WriteConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['parkweave-ordinary-runtime-write/1']
    binding_path: str = Field(min_length=1, max_length=4096)
    binding_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    @field_validator('binding_path')
    @classmethod
    def protected_path(cls, value):
        from .native_run_access_restricted_host import canonical_path
        if not canonical_path(value):
            raise ValueError('canonical absolute public path required')
        return value


class WriteBinding(ReadConfig):
    schema_version: Literal['parkweave-ordinary-runtime-write-binding/1']
    operations: list[Literal['COMMAND', 'ACTIVATE']]

    @model_validator(mode='after')
    def exact_operations(self):
        if self.operations != ['COMMAND', 'ACTIVATE']:
            raise ValueError('exact command and activation scope required')
        WriteConfig.protected_path(self.binding_path)
        return self


def _parse(raw, model):
    if not isinstance(raw, str) or not 1 <= len(raw.encode('utf-8')) <= LIMIT:
        raise ValueError('bounded public configuration required')
    return model.model_validate(strict_json(raw))


def _load(cfg):
    from .native_run_access_restricted_host import _protected_bytes
    raw = _protected_bytes(cfg.binding_path, 0, expected=cfg.binding_sha256, limit=LIMIT)
    binding = _parse(raw.decode('utf-8'), WriteBinding)
    # Re-read both pins even after startup. Neither file is created or repaired.
    inner = _protected_bytes(binding.binding_path, 0, expected=binding.binding_sha256)
    public = strict_json(inner.decode('utf-8'))
    if (type(public) is not dict or set(public) !=
            {'schema', 'policy', 'pin', 'api_uid', 'api_gid', 'ipc_gid', 'source_sha'}
            or public['schema'] != 'parkweave-restricted-api-binding/1'):
        raise ValueError('exact existing host public binding required')
    return binding, public


def check_binding(bridge, c, run_id):
    """Read-only scope gate; uses the caller's connection, including commit checks."""
    from .native_run_access import NativeRunAccess
    from .native_run_access_writer import WriterClient, _writer
    try:
        if (type(bridge) is not NativeRunAccess or bridge.read_only is not False
                or getattr(bridge.store, '_native_run_access', None) is not bridge
                or getattr(bridge, 'runtime_read_binding', None) is not None):
            raise Denied('exact ordinary write client required')
        cfg = _parse(bridge.runtime_write_binding, WriteConfig)
        binding, public = _load(cfg)
        client = _writer(bridge)
        if (type(client) is not WriterClient or client.policy.environment != 'PRODUCTION'
                or client.policy.model_dump() != public['policy']
                or client.pin.model_dump() != public['pin']):
            raise Denied('existing production client and exact protected policy/pin required')
        return check_scope(bridge, c, run_id, binding)
    except (AttributeError, OSError, ValueError, TypeError, KeyError, UnicodeError, psycopg.Error, Denied, Conflict):
        raise Denied('ordinary write binding unavailable or changed; no fallback') from None


def before_invoke(bridge, operation, run_id):
    if operation not in ('COMMAND', 'ACTIVATE'):
        raise Denied('ordinary write operation unavailable')
    from .native_run_access_writer import WriterClient, history
    with bridge.store._guarded_connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        check_binding(bridge, c, run_id)
        WriterClient.validate(bridge.writer, c)
        history(bridge, c, run_id)
        check_binding(bridge, c, run_id)
    # No local replay cache or retry. The original writer owns auth, original-key
    # decisions and the atomic event/assignment transaction. A pin change cannot
    # atomically recall a command that has already reached that writer.


def configure(store, raw):
    if raw is None:
        return None
    bridge = None
    complete = False
    previous = getattr(store, '_native_run_access', None)
    try:
        cfg = _parse(raw, WriteConfig)
        if (sys.platform != 'linux' or store.mode != 'LOCAL' or previous is not None
                or any(getattr(store, name, None) is not None for name in
                       ('_isolated_run_access', '_isolated_plan_approval', '_isolated_service_capability_catalog'))):
            raise Denied('independent supported ordinary write binding required')
        binding, public = _load(cfg)
        from .native_run_access_writer import WriterPolicy
        if WriterPolicy.model_validate(public['policy']).environment != 'PRODUCTION':
            raise Denied('reference writer is not ordinary startup authority')
        from .native_run_access_restricted_host import bind_api
        bridge = bind_api(store, binding.binding_path, binding.binding_sha256, read_only=False)
        bridge.runtime_write_binding = cfg.model_dump_json()
        before_invoke(bridge, 'COMMAND', binding.run_id)
        complete = True
        return bridge
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, psycopg.Error, Denied, Conflict):
        raise Denied('invalid or unavailable ordinary runtime write configuration; no fallback') from None
    finally:
        # Also runs for unexpected errors and interruption; never clears another
        # or pre-existing bridge. No partial writer survives failed startup.
        if not complete and bridge is not None and getattr(store, '_native_run_access', None) is bridge:
            del store._native_run_access
