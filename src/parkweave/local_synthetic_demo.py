"""Default-off local SYNTHETIC inputs, never publication or authorization.

The two pre-existing files are hash-pinned inputs. Their journal is an input
binding anchor, not an approval ledger. Startup only reads them and PostgreSQL.
No fixture owner, TemplateConsumer, model transport or credentials are accepted.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import stat
import os
from typing import Literal
from uuid import uuid5, NAMESPACE_URL

from pydantic import BaseModel, ConfigDict, Field

from . import bounded_planning as bp, service_capability_contract as contract
from . import service_selection as ss
from .domain import PlanID, Validity
from .intern_adapter import strict_json, ModelBoundaryError
from .store import Denied, Conflict

PROFILE = 'LOCAL_SYNTHETIC_DEMO'
ORIGIN = 'LOCAL_SYNTHETIC_DEMO_NO_MODEL_V1'


class Exact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class DatabaseBinding(Exact):
    name: str = Field(min_length=1, max_length=63)
    oid: int = Field(ge=1)
    address: str | None
    port: int | None = Field(ge=1, le=65535)
    user: str = Field(min_length=1, max_length=63)


class DemoConfig(Exact):
    schema_version: Literal['parkweave-local-synthetic-demo-config/1']
    pack_path: str = Field(min_length=1, max_length=4096)
    pack_sha256: contract.Hash
    journal_path: str = Field(min_length=1, max_length=4096)
    journal_sha256: contract.Hash
    database: DatabaseBinding
    catalog_sha256: contract.Hash
    catalog_generation: str = Field(pattern=r'^[0-9]+$')


class DemoPack(Exact):
    schema_version: Literal['parkweave-local-synthetic-demo-pack/1']
    kind: Literal['SYNTHETIC']
    id: PlanID
    revision: int = Field(ge=1, le=64)
    validity: Validity
    park_id: PlanID
    org_id: PlanID
    roles: dict[contract.Role, PlanID]
    resources: dict[contract.ResourceKey, PlanID]
    fields: dict[contract.Slot, contract.FieldMapping]
    services: list[contract.ServiceID] = Field(min_length=1, max_length=3)


def database_binding(c):
    return dict(c.execute('SELECT current_database() name, '
        '(SELECT oid::bigint FROM pg_database WHERE datname=current_database()) oid, '
        'host(inet_server_addr()) address, inet_server_port() port, current_user::text AS user').fetchone())


def _file(path, expected, *, private=False):
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise Denied('existing absolute regular demo input required')
    try:
        fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_size > 65536
                    or private and stat.S_IMODE(info.st_mode)&0o077):
                raise Denied('bounded regular private local demo input required')
            raw = stream.read(65537)
    except OSError:
        raise Denied('existing local demo input unavailable') from None
    if not 1 <= len(raw) <= 65536 or sha256(raw).hexdigest() != expected:
        raise Denied('local demo input hash changed')
    return strict_json(raw.decode('utf-8'))


def pack(raw):
    value = DemoPack.model_validate(raw).model_dump(mode='json')
    if (type(value['revision']) is not int or len(set(value['services'])) != len(value['services'])
            or set(value['roles']) != {'enterprise_operator','park_specialist','service_executor'}
            or len(set(value['roles'].values())) != 3
            or set(value['resources']) != {'primary','secondary'}
            or len(set(value['resources'].values())) != 2
            or set(value['fields']) != {'need_summary','material_outline'}
            or any(v['slot'] != k for k,v in value['fields'].items())
            or len({v['input_field'] for v in value['fields'].values()}) != 2):
        raise ValueError('complete distinct existing demo mappings required')
    return value


def contracts(value, pack_sha256, *, now, frozen=None):
    """Compile original finite contracts, with an independent demo source tag."""
    value = pack(value)
    contract._effective(value['validity'], now)
    releases, instances = [], []
    registry,actions = (bp.REGISTRY,bp.ACTIONS) if frozen is None else (frozen['steps'],frozen['actions'])
    source = dict(kind='SYNTHETIC', pack_id=value['id'], revision=value['revision'],
                  pack_sha256=pack_sha256, publication=False, approval=False)
    for service in sorted(value['services']):
        goals = sorted(contract.SERVICE_GOALS[service])
        if frozen is None: _, steps = bp.compile(goals)
        else: steps = contract._frozen_closure(goals,registry,actions)
        ids = [s['id'] for s in steps]
        roles = sorted({a['role'] for id in ids for a in actions[id]})
        resources = ['primary','secondary'] if 'P2' in ids else []
        fields = ['need_summary','material_outline']
        release = dict(schema_version='local-synthetic-demo-release/1', service_id=service,
            release_id=str(uuid5(NAMESPACE_URL, ORIGIN+':'+pack_sha256+':'+service)),
            revision=value['revision'], owner_org_id=value['org_id'], title='SYNTHETIC '+service,
            supported_goals=goals, steps=steps, role_keys=roles, resource_keys=resources,
            field_keys=fields, material_requirements=[dict(field_key=f,purpose='CURRENT_CASE_MATERIAL_PREPARATION') for f in fields],
            resource_requirements=[dict(resource_key=r,required=True) for r in resources],
            completion_checks=[contract.CHECKS[id] for id in ids], validity=value['validity'],
            demo_source=deepcopy(source), business_publication=False)
        release['release_sha256'] = contract.hash_release(release)
        instance = dict(schema_version='local-synthetic-demo-instance/1',
            instance_id=str(uuid5(NAMESPACE_URL, ORIGIN+':instance:'+pack_sha256+':'+service)),
            park_id=value['park_id'], release_id=release['release_id'], release_sha256=release['release_sha256'],
            config_revision=value['revision'], roles={r:value['roles'][r] for r in roles},
            resources={r:value['resources'][r] for r in resources}, fields=value['fields'],
            source=deepcopy(source), new_grants=False)
        instance['config_sha256'] = contract.hash_instance(instance)
        releases.append(release); instances.append(instance)
    return releases, instances


def validated_pairs(snapshot, request, *, now, frozen=None):
    """Demo contracts cannot be interpreted as reviewed template releases."""
    releases, instances = contracts(snapshot['demo_pack'],snapshot['pack_sha256'],now=now,frozen=frozen)
    if (snapshot['scope'] != PROFILE or contract.digest(snapshot['releases']) != contract.digest(releases) or contract.digest(snapshot['instances']) != contract.digest(instances)
            or request['park_id'] != snapshot['demo_pack']['park_id']):
        raise Conflict('exact local demo contract binding required')
    return sorted(zip(releases,instances),key=lambda pair:ss._identity(ss.selection_ref(*pair)))


class LocalDemoCatalog:
    def __init__(self, store, config):
        if type(config) is not DemoConfig or store.mode!='LOCAL':
            raise Denied('exact local demo configuration required')
        self.store, self.config = store, config
        if Path(config.pack_path).resolve() == Path(config.journal_path).resolve():
            raise Denied('distinct existing demo pack and input journal required')
        with store.connect() as c: self.validate(c)

    def validate(self, c, parent=None):
        cfg = self.config
        value = pack(_file(cfg.pack_path,cfg.pack_sha256))
        journal = _file(cfg.journal_path,cfg.journal_sha256,private=True)
        expected = dict(schema_version='parkweave-local-synthetic-demo-journal/1',
            kind='SYNTHETIC', pack_sha256=cfg.pack_sha256, database=cfg.database.model_dump(),
            park_id=value['park_id'], org_id=value['org_id'],
            catalog_sha256=cfg.catalog_sha256,catalog_generation=cfg.catalog_generation)
        if journal != expected or database_binding(c) != cfg.database.model_dump():
            raise Denied('local demo database/park/input journal binding changed')
        version = c.execute('SELECT max(version) version FROM schema_version').fetchone()['version']
        if version != 32:
            raise Denied('preinstalled ordinary schema 32 required; demo startup never migrates')
        row = c.execute('SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation '
            'FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=1',
            (value['park_id'],'synthetic-material-preparation')).fetchone()
        from .ordinary_runtime_read import catalog_hash
        generation = row.pop('row_generation') if row else None
        if (not row or row['namespace'] != 'SYNTHETIC' or not isinstance(row['source'],dict) or row['source'].get('kind') != 'SYNTHETIC'
                or catalog_hash(row) != cfg.catalog_sha256 or generation != cfg.catalog_generation):
            raise Denied('existing exact SYNTHETIC preparation catalog required')
        if parent and (parent['park_id'],parent['org_id'],parent['owner_id'],parent['reviewer_id']) != (
                value['park_id'],value['org_id'],value['roles']['enterprise_operator'],value['roles']['park_specialist']):
            raise Denied('current demo Case owner/park/reviewer mapping required')
        contracts(value,cfg.pack_sha256,now=c.execute('SELECT clock_timestamp() t').fetchone()['t'])
        return value

    @contextmanager
    def connection(self):
        from .ordinary_plan_sources import selected
        from .case_step_assignments import local_demo_pair
        service=selected(self.store)
        if service is not None and (not local_demo_pair(service,self.store,service.local_synthetic_demo)
                or service.local_synthetic_demo.catalog is not self):
            raise Denied('local demo reads require their exact ordinary transaction pair')
        transaction=service._connection(self.store) if service is not None else self.store.connect()
        with transaction as c:
            self.validate(c)
            yield c
            self.validate(c)

    read_connection = connection

    def snapshot(self, c, parent):
        value = self.validate(c,parent)
        releases, instances = contracts(value,self.config.pack_sha256,
            now=c.execute('SELECT clock_timestamp() t').fetchone()['t'])
        from .service_capability_catalog import current_mapping_states
        states = dict(principals={},resources={},fields={})
        for instance in instances:
            mapping = current_mapping_states(self.store,{(value['park_id'],value['org_id'])},c,instance,parent)
            for key in states: states[key].update(mapping[key])
        return dict(scope=PROFILE,revision=value['revision'],demo_pack=value,
            pack_sha256=self.config.pack_sha256,journal_sha256=self.config.journal_sha256,
            database_sha256=contract.digest(self.config.database.model_dump()),
            releases=releases,instances=instances,mapping_states=states,unknowns=[],
            business_publication=False,new_grants=False)


class LocalDemoSelector:
    """Unique finite solution only. No model, HTTP, usage, budget or fake token."""
    def select(self, current):
        oracle = current['selection_oracle']
        if oracle['state'] != 'UNIQUE' or len(oracle['minimal_solutions']) != 1:
            raise Conflict('local demo requires one proven solution; explicit choice not implemented')
        from .service_selection_candidates import binding
        return ss.parse_selection(contract.canonical(dict(schema_version=1,
            binding=binding(current),selections=oracle['minimal_solutions'][0])),binding(current))


class LocalSyntheticDemo:
    def __init__(self, catalog, selector):
        if type(catalog) is not LocalDemoCatalog or type(selector) is not LocalDemoSelector:
            raise Denied('exact independent local demo providers required')
        self.catalog, self.selector = catalog, selector


def configure(store, profile, raw):
    if profile is None and raw is None: return None
    if profile != PROFILE or raw is None:
        raise Denied('explicit LOCAL_SYNTHETIC_DEMO profile and configuration required')
    try:
        if type(raw) is not str or not 1 <= len(raw.encode()) <= 16384: raise ValueError()
        cfg = DemoConfig.model_validate(strict_json(raw))
        return LocalSyntheticDemo(LocalDemoCatalog(store,cfg),LocalDemoSelector())
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,ModelBoundaryError):
        raise Denied('invalid local synthetic demo inputs; values not echoed') from None
