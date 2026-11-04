"""Native SYNTHETIC sample composition; no import-time native actions.

Public catalog inputs are configuration, never acceptance. Private identities
remain in the original native provider/DPAPI files. No Linux password vault,
fixture credential issuer, trust override or startup migration is used here.
"""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path

from psycopg.types.json import Jsonb
from parkweave.store import Denied,digest
from parkweave import local_synthetic_demo as demo
from parkweave.ordinary_runtime_read import catalog_hash
from .controller import CandidateRefused
from .local_preparation_identity import (PreparationIdentities,PreparationProfile,
    EXECUTOR,RESOURCE_ADMIN,seed_preparation_transaction)

ENVIRONMENT='PARKWEAVE_NATIVE_SAMPLE'
MAX_CONFIG=12288
PROFILE='NATIVE_SYNTHETIC_COLLABORATION_V1'
RESOURCE_IDS=('fa161ea0-b665-4ec5-b345-a070bfec764d','fb161ea0-b665-4ec5-b345-a070bfec764d')
ROLE_MAP={'enterprise_operator':'fixture-a','park_specialist':'prep-specialist-fixture-a','service_executor':EXECUTOR}
LABELS=(('fixture-a','企业 · 诉求、资源审批与确认'),('prep-specialist-fixture-a','专员 · 核对与分派'),
        (EXECUTOR,'执行者 · 本人接单与回执'),(RESOURCE_ADMIN,'资源管理员 · 目录与来源只读核对'))
SQL_SHA256='470a85e9adfeee7f279be5538bacd176710bd5d82dad746bf13eeefb0633a4f3'


def seed_sample_transaction(owner,connection,identities):
    from parkweave.installed_fixture_receipt import _InstalledSyntheticSetupStore,NativeDatabaseCreationEvidence
    from parkweave import store as storage
    receipt=getattr(owner,'_case_fact_fixture_receipt',None)
    if (type(owner) is not _InstalledSyntheticSetupStore or type(receipt) is not NativeDatabaseCreationEvidence
        or type(identities) is not PreparationIdentities or identities.profile is not PreparationProfile.SAMPLE
        or connection.autocommit is not False):
        raise CandidateRefused('same live native owner and explicit sample identities required')
    values=identities.mapping()
    NativeDatabaseCreationEvidence.authorize_migration(receipt,connection)
    for table in ('principals','runs','cases','preparations','synthetic_resources','service_dispatches','service_receipt_steps'):
        if connection.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone():
            raise CandidateRefused('native sample cannot adopt or repair existing data')
    raw=Path(storage.__file__).with_name('local-resource-approval-schema.sql').read_bytes()
    if sha256(raw).hexdigest()!=SQL_SHA256:raise CandidateRefused('original local approval storage source required')
    connection.execute(raw.decode())
    seed_sample_rows(connection,identities)


def seed_sample_rows(connection,identities):
    """SQL consumer only; the native owner/issuer and transaction stay above.

    Also exercised with supported Linux SQL components, never a native proof.
    """
    if type(identities) is not PreparationIdentities or identities.profile is not PreparationProfile.SAMPLE or connection.autocommit is not False:
        raise CandidateRefused('sample identities and caller-owned transaction required')
    values=identities.mapping()
    seed_preparation_transaction(connection,identities)
    for account,role in ((EXECUTOR,'service_executor'),(RESOURCE_ADMIN,'resource_admin')):
        connection.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',(account,digest(values[account]),'park-a','org-a',role))
        connection.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,'READ','park-a','org-a')",(account,))
    source=dict(kind='SYNTHETIC',id=PROFILE,revision='1',statement='原生模式显式本地合成样例，不是正式发布、业务批准或外部履约。')
    for id,name in zip(RESOURCE_IDS,('合成协作空间','合成研讨设备')):
        connection.execute("INSERT INTO synthetic_resources VALUES(%s,'park-a',%s,1,2,300,clock_timestamp()-interval '1 day',clock_timestamp()+interval '7 days',true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)",(id,name,Jsonb(source)))
        for cap in ('READ','HOLD'):
            connection.execute("INSERT INTO synthetic_resource_grants VALUES('fixture-a',%s,'park-a','org-a',%s,true)",(id,cap))


def public_inputs(connection):
    """Read actual app-role database/catalog facts; never manufacture a proof."""
    database=demo.database_binding(connection)
    if database['user']!='parkweave_app':raise Denied('native sample application database binding required')
    now=connection.execute('SELECT clock_timestamp() t').fetchone()['t']
    row=connection.execute("SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation FROM preparation_catalog WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1").fetchone()
    if not row or row['namespace']!='SYNTHETIC':raise Denied('existing native synthetic catalog required')
    generation=row.pop('row_generation')
    value=dict(schema_version='parkweave-local-synthetic-demo-pack/1',kind='SYNTHETIC',id='native-local-synthetic-collaboration',revision=1,
        validity=dict(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=7)).isoformat(),timezone='UTC'),
        park_id='park-a',org_id='org-a',roles=ROLE_MAP,resources=dict(zip(('primary','secondary'),RESOURCE_IDS)),
        fields={s:dict(slot=s,input_field='demo_'+s) for s in ('need_summary','material_outline')},services=list(demo.contract.SERVICE_GOALS))
    demo.pack(value);pack_sha=sha256(demo.contract.canonical(value).encode()).hexdigest()
    journal=dict(schema_version='parkweave-local-synthetic-demo-journal/1',kind='SYNTHETIC',pack_sha256=pack_sha,database=database,
        park_id='park-a',org_id='org-a',catalog_sha256=catalog_hash(row),catalog_generation=generation)
    meta=dict(database=database,catalog_sha256=journal['catalog_sha256'],catalog_generation=generation,
        pack_sha256=pack_sha,journal_sha256=sha256(demo.contract.canonical(journal).encode()).hexdigest())
    raw=demo.contract.canonical(dict(schema='parkweave-native-sample-inputs/1',metadata=meta,pack=value,journal=journal))
    validate_public(raw)
    return raw


def validate_public(raw):
    inputs=demo.NativeDemoInputs.parse(raw);meta,value,journal=inputs.values()
    if value['roles']!=ROLE_MAP or value['resources']!=dict(zip(('primary','secondary'),RESOURCE_IDS)) or (value['park_id'],value['org_id'])!=('park-a','org-a'):
        raise Denied('fixed original native sample mappings required')
    return inputs


def dependencies(store,raw):
    from parkweave.case_step_assignments import OrdinaryCaseStepAssignments
    inputs=validate_public(raw)
    local=demo.LocalSyntheticDemo(demo.LocalDemoCatalog(store,inputs),demo.LocalDemoSelector())
    return OrdinaryCaseStepAssignments(store,local_synthetic_demo=local)


class NativeSampleWorkspace:
    """Concrete application/read-only directory adapter, not an authority issuer."""
    material_accounts=LABELS[:2]
    def __init__(self,store,raw):
        self.store,self.inputs=store,validate_public(raw)
        self.catalog=demo.LocalDemoCatalog(store,self.inputs)

    def page(self,root):
        from parkweave.local_workspace import full_sample_workspace_page
        _,value,_=self.inputs.values()
        return full_sample_workspace_page(root,LABELS,value['validity']['valid_until'])

    def resources(self,token):
        with self.store.connect() as c:
            p=self.store.auth(c,token,lock=True);self.store.check_capability(c,p,'READ');self.catalog.validate(c)
            if (p['id'],p['role'],p['park_id'],p['org_id'])!=(RESOURCE_ADMIN,'resource_admin','park-a','org-a'):
                raise Denied('original sample resource administrator required')
            rows=c.execute("SELECT id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE park_id='park-a' AND id=ANY(%s::uuid[]) ORDER BY id",(list(RESOURCE_IDS),)).fetchall()
            if len(rows)!=2 or any(r['source'].get('id')!=PROFILE or r['namespace']!='SYNTHETIC' or r['authority']!='LOCAL_AUTHORITY' for r in rows):
                raise Denied('original native synthetic resource source required')
        return dict(scope='LOCAL_SYNTHETIC_RESOURCE_CONFIGURATION_READ_ONLY',items=rows,
            private_Cases_exposed=False,holds_exposed=False,hold_allowed=False,publish_allowed=False,case_goal_completed=False)
