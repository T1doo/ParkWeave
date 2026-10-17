"""Existing ordinary authorization wiring. No signing, provisioning or activation.

An explicit config only narrows a previously protected host binding. The original
writer verifies signed history and existing effective assignments; its command
channel remains closed in this API. Resource-plan Approval has no ordinary
contract and is never substituted with IsolatedPlanApproval.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
import psycopg

from . import preparation as prep, native_run_access as native
from .store import Conflict, Denied, digest


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_case_id: UUID
    expected_run_id: UUID
    expected_service_id: str = Field(min_length=1, max_length=100)
    expected_service_version: int = Field(ge=1)


class ReadConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal['parkweave-ordinary-runtime-read/1']
    binding_path: str = Field(min_length=1, max_length=4096)
    binding_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    preparation_id: UUID = Field(strict=False)
    case_id: UUID = Field(strict=False)
    run_id: UUID = Field(strict=False)
    service_id: str = Field(min_length=1, max_length=100)
    service_version: int = Field(ge=1)
    catalog_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    catalog_generation: str = Field(pattern=r'^[0-9]+$')

    @field_validator('binding_path')
    @classmethod
    def absolute_public_path(cls, value):
        if not Path(value).is_absolute() or any(x in value for x in ('\0', '\n', '\r')):
            raise ValueError('absolute existing public binding path required')
        return value


def catalog_hash(service):
    return digest(prep.canonical(service))


def _catalog(c, parent):
    service = c.execute('SELECT service_id,version,name,source,namespace,qualification,xmin::text AS row_generation FROM preparation_catalog '
                        'WHERE park_id=%s AND service_id=%s AND version=%s',
                        (parent['park_id'], parent['service_id'], parent['service_version'])).fetchone()
    if (not service or service['namespace'] != 'SYNTHETIC' or not isinstance(service['source'], dict)
            or service['source'].get('kind') != 'SYNTHETIC'):
        raise Conflict('current SYNTHETIC preparation catalog required')
    generation=service.pop('row_generation')
    return service,generation


def check_binding(bridge, c, run_id):
    """Also called by the ORIGINAL assignment predicate, including commit checks."""
    from .native_run_access_writer import WriterClient, _writer
    if (type(bridge) is not native.NativeRunAccess or bridge.read_only is not True
            or getattr(bridge.store, '_native_run_access', None) is not bridge):
        raise Denied('exact ordinary read provider required')
    try:
        cfg = ReadConfig.model_validate_json(bridge.runtime_read_binding)
    except (AttributeError, ValueError, TypeError):
        raise Denied('ordinary read provider configuration unavailable') from None
    client = _writer(bridge)
    if type(client) is not WriterClient:
        raise Denied('public writer client required; private context forbidden')
    policy = client.policy
    if (str(run_id), str(cfg.run_id), str(cfg.case_id), str(cfg.preparation_id)) != (
            str(cfg.run_id), policy.source.run_id, policy.source.case_id, policy.source.preparation_id):
        raise Conflict('ordinary read provider Case/Run/preparation binding changed')
    WriterClient._database(client, c)
    parent = c.execute('SELECT * FROM preparations WHERE id=%s', (cfg.preparation_id,)).fetchone()
    if (not parent or (parent['run_id'], parent['case_id'], parent['service_id'], parent['service_version']) !=
            (cfg.run_id, cfg.case_id, cfg.service_id, cfg.service_version)):
        raise Conflict('ordinary read provider exact service binding changed')
    run = c.execute('SELECT * FROM runs WHERE id=%s', (cfg.run_id,)).fetchone()
    if not run:
        raise Conflict('ordinary read provider original Run unavailable')
    source = bridge._source(c, run, parent)
    if (source['owner_id'], source['park_id'], source['org_id']) != (
            policy.source.owner_id, policy.source.park_id, policy.source.org_id):
        raise Conflict('ordinary read provider original owner/tenant changed')
    service,generation = _catalog(c, parent)
    if catalog_hash(service) != cfg.catalog_sha256 or generation != cfg.catalog_generation:
        raise Conflict('ordinary read provider exact catalog source changed')
    return cfg


def configure(store, raw):
    """Ordinary factory only reads an explicit existing protected public binding."""
    if raw is None:
        return None
    try:
        if not isinstance(raw, str) or not 1 <= len(raw.encode('utf-8')) <= 16384:
            raise ValueError()
        cfg = ReadConfig.model_validate_json(raw)
    except (ValueError, TypeError):
        raise Denied('invalid explicit ordinary runtime read configuration; values not echoed') from None
    if sys.platform != 'linux':
        raise Denied('ordinary protected read provider requires supported Linux host; Windows not verified')
    from .native_run_access_restricted_host import bind_api
    try:
        bridge = bind_api(store, cfg.binding_path, cfg.binding_sha256, read_only=True)
        bridge.runtime_read_binding = cfg.model_dump_json()
        with store._guarded_connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            check_binding(bridge, c, cfg.run_id)
            from .native_run_access_writer import history,WriterClient
            WriterClient.validate(bridge.writer,c)
            history(bridge,c,cfg.run_id)
    except (OSError, ValueError, TypeError, Denied, Conflict, psycopg.Error):
        raise Denied('existing protected ordinary runtime read binding invalid or unavailable; no fallback') from None
    return bridge


@contextmanager
def selected(store, token, preparation_id, selection):
    if type(selection) is not Selection:
        raise Denied('typed exact runtime selection required')
    with store.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL lock_timeout='3s'")
        p = store.auth(c, token, lock=True)
        parent, service = prep.entry_context(store, c, p, preparation_id)
        if (selection.expected_case_id, selection.expected_run_id, selection.expected_service_id,
                selection.expected_service_version) != (parent['case_id'], parent['run_id'],
                                                       parent['service_id'], parent['service_version']):
            raise Conflict('runtime selection Case/Run/service/version changed; reread original preparation')
        bridge = getattr(store, '_native_run_access', None)
        if bridge is not None and getattr(bridge, 'runtime_read_binding', None) is not None:
            check_binding(bridge, c, parent['run_id'])
        original = native.NativeRunAccess(store)
        run = original._run(c, p, parent['run_id'])
        original._source(c, run, parent)
        yield c, p, parent, service, run, bridge


def read_run(store, token, preparation_id, selection):
    with selected(store, token, preparation_id, selection) as (_, _, parent, _, _, _):
        # The original current Run permission chain, including native assignment
        # signature/expiry/generation/catalog checks, remains authoritative.
        return store.read(token, parent['run_id'])


def read_dispatch(store, token, preparation_id, selection):
    from .service_dispatches import read_preparation
    with selected(store, token, preparation_id, selection):
        return read_preparation(store, token, preparation_id)


def read_access_approval(store, token, preparation_id, selection):
    with selected(store, token, preparation_id, selection) as (c, p, parent, _, run, bridge):
        if bridge is None or getattr(bridge, 'runtime_read_binding', None) is None:
            raise Conflict('ordinary runtime read provider not configured; existing protected binding required')
        check_binding(bridge, c, run['id'])
        if not bridge._storage(c):
            raise Conflict('ordinary Run access approval storage unavailable')
        bridge._authorize_read(c, p, run)
        from .native_run_access_writer import WriterClient
        try:WriterClient.validate(bridge.writer,c)
        except Denied:
            raise Conflict('ordinary Run access provider current validation unavailable; effective authority refused') from None
        result = bridge._view(c, p, run)
        if result.get('writer_history_verified') is not True:
            raise Conflict('ordinary Run access approval verification channel unavailable; effective authority refused')
        check_binding(bridge, c, parent['run_id'])
        return result


def read_catalog(store, token, preparation_id, selection):
    with selected(store, token, preparation_id, selection) as (_, p, parent, service, _, bridge):
        source_visible=p['role']=='enterprise_operator'
        visible=service if source_visible else {k:service[k] for k in ('service_id','version','namespace','qualification')}
        return dict(preparation_id=str(parent['id']), case_id=str(parent['case_id']), run_id=str(parent['run_id']),
                    catalog=visible, catalog_source_visible=source_visible,catalog_sha256=catalog_hash(service), read_only=True,
                    provider_configured=bridge is not None and getattr(bridge, 'runtime_read_binding', None) is not None,
                    resource_plan_approval_available=False,
                    resource_plan_approval_reason='ORDINARY_RESOURCE_PLAN_APPROVAL_CONTRACT_UNAVAILABLE',
                    access_approval_purpose='RUN_READ_ACCESS_ONLY', qualification='NOT_EVALUATED')
