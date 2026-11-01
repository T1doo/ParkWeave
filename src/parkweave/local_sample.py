"""Explicit fresh Linux SYNTHETIC collaboration installation.

Initial configuration only. No approved plan, hold, dispatch, receipt or Case
is seeded. Runtime uses the existing ordinary providers and current SQL rights.
The resource administrator has READ only, never HOLD/PUBLISH or Case access.
"""
from datetime import timedelta
from hashlib import sha256
import json
import os
import stat
from pathlib import Path

from psycopg.types.json import Jsonb
from .local_identity import LocalSessionVault, SAMPLE_ROLES, SAMPLE_SCHEMA
from .store import Store, Denied, digest

PROFILE = 'LOCAL_SYNTHETIC_COLLABORATION_V1'
PARK, ORG = 'local-synthetic-park', 'local-synthetic-org'
IDS = {name:'local-sample-'+name for name in SAMPLE_ROLES}
ROLES = dict(enterprise='enterprise_operator', specialist='park_specialist',
             executor='service_executor', **{'resource-admin':'resource_admin'})
LABELS = [('enterprise','企业 · 诉求、资源审批与确认'),('specialist','专员 · 资料核对与分派'),
          ('executor','执行者 · 本人接单与合成回执'),('resource-admin','资源管理员 · 样例目录与来源只读核对')]
RESOURCES = [('fa161ea0-b665-4ec5-b345-a070bfec764d','合成协作空间'),
             ('fb161ea0-b665-4ec5-b345-a070bfec764d','合成研讨设备')]
SQL_RIGHTS = {
 'SELECT':('schema_version','principals','capability_grants','action_grants','preparation_grants',
    'preparation_catalog','field_grants','run_assignments','model_steps','dispatch_notice_outbox',
    'service_dispatch_events','controlled_plans','synthetic_resources','synthetic_resource_grants'),
 'SELECT,INSERT,UPDATE':('runs','operations','outbox','run_projection','deliveries','preparations','cases'),
 'SELECT,INSERT':('preparation_evidence','preparation_events','synthetic_resource_holds',
    'synthetic_resource_receipts','synthetic_resource_combinations','synthetic_resource_combination_members',
    'synthetic_resource_combination_receipts','resource_case_claims','case_resource_links',
    'service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
    'service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events','dispatch_notices'),
 'INSERT':('authorization_audit',),
 'UPDATE(invalidated_from,invalidated_at)':('controlled_plans',),
 'SELECT,INSERT,UPDATE(state,consumed_at)':('dispatch_notice_outbox',),
 'UPDATE(state)':('synthetic_resource_holds','synthetic_resource_combinations'),
 'UPDATE(revision,current_offer_id)':('service_dispatches',),
 'UPDATE(state,receipt_step_id)':('service_dispatch_offers',),
 'UPDATE(state,revision,current_receipt_id)':('service_receipt_steps',),
 'UPDATE(revision,cycle,state,verified_snapshot,verified_sha256)':('case_local_lifecycles',),
 'UPDATE(seen_at,read_at)':('dispatch_notices',),
}


def initialize(owner, provider):
    from .local_installation import PersistentSetupStore
    if (type(owner) is not PersistentSetupStore or not owner.installation.fresh
            or owner.installation.record['phase']!='INSTALLING'
            or type(provider) is not LocalSessionVault or provider.roles!=SAMPLE_ROLES):
        raise Denied('explicit new sealed sample installation required')
    owner.migrate()
    owner.install_local_sample_storage()
    tokens=provider.generate()
    with owner.connect() as c:
        for account,role in ROLES.items():
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                (IDS[account],digest(tokens[account]),PARK,ORG,role))
            for cap in ('READ','EXECUTE') if account=='enterprise' else ('READ',):
                c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',(IDS[account],cap,PARK,ORG))
        c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create',%s,%s)",(IDS['enterprise'],PARK,ORG))
        for account,cap in (('enterprise','PREPARE'),('specialist','REVIEW_ASSIGNED')):
            c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s)',(IDS[account],PARK,ORG,cap))
        source=dict(kind='SYNTHETIC',id=PROFILE,revision='1',statement='显式本地合成样例初始化；非真实园区、正式发布、资格批准或线下履约。')
        c.execute("INSERT INTO preparation_catalog VALUES(%s,'synthetic-material-preparation',1,'本地合成服务与资源协同',%s,'SYNTHETIC','NOT_EVALUATED')",(PARK,Jsonb(source)))
        for id,name in RESOURCES:
            c.execute("INSERT INTO synthetic_resources VALUES(%s,%s,%s,1,2,300,clock_timestamp()-interval '1 day',clock_timestamp()+interval '7 days',true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)",(id,PARK,name,Jsonb(source)))
            for cap in ('READ','HOLD'):
                c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true)',(IDS['enterprise'],id,PARK,ORG,cap))
        c.execute('REVOKE ALL ON DATABASE parkweave FROM PUBLIC')
        c.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
        c.execute('GRANT CONNECT ON DATABASE parkweave TO parkweave_app')
        c.execute('GRANT USAGE ON SCHEMA public TO parkweave_app')
        for rights,tables in SQL_RIGHTS.items():
            c.execute('GRANT '+rights+' ON '+','.join(tables)+' TO parkweave_app')
        for table in ('runs','cases','preparations','synthetic_resource_holds','service_dispatches','service_receipt_steps'):
            if c.execute('SELECT 1 FROM '+table+' LIMIT 1').fetchone():raise Denied('sample setup cannot adopt existing business')


def create_inputs(state, application_dsn):
    """Original finite demo contract, with public hashes and real DB binding."""
    from . import local_synthetic_demo as demo
    from .ordinary_runtime_read import catalog_hash
    directory=state/'local-sample';directory.mkdir(mode=0o700)
    with Store(application_dsn).connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        now=c.execute('SELECT clock_timestamp() t').fetchone()['t'];database=demo.database_binding(c)
        row=c.execute('SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=1',(PARK,'synthetic-material-preparation')).fetchone()
    generation=row.pop('row_generation')
    value=dict(schema_version='parkweave-local-synthetic-demo-pack/1',kind='SYNTHETIC',id='local-synthetic-collaboration',revision=1,
        validity=dict(valid_from=(now-timedelta(days=1)).isoformat(),valid_until=(now+timedelta(days=7)).isoformat(),timezone='UTC'),
        park_id=PARK,org_id=ORG,roles={ROLES[a]:IDS[a] for a in ('enterprise','specialist','executor')},
        resources={k:id for k,(id,_) in zip(('primary','secondary'),RESOURCES)},
        fields={slot:dict(slot=slot,input_field='demo_'+slot) for slot in ('need_summary','material_outline')},services=list(demo.contract.SERVICE_GOALS))
    demo.pack(value)
    def write(name,value):
        p=directory/name
        with p.open('x') as f:
            json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        return p,sha256(p.read_bytes()).hexdigest()
    pack,pack_sha=write('pack.json',value)
    cfg=dict(schema_version='parkweave-local-synthetic-demo-config/1',pack_path=str(pack),pack_sha256=pack_sha,
        database=database,catalog_sha256=catalog_hash(row),catalog_generation=generation)
    journal,journal_sha=write('journal.json',dict(schema_version='parkweave-local-synthetic-demo-journal/1',kind='SYNTHETIC',pack_sha256=pack_sha,database=database,park_id=PARK,org_id=ORG,catalog_sha256=cfg['catalog_sha256'],catalog_generation=generation))
    cfg.update(journal_path=str(journal),journal_sha256=journal_sha)
    config,config_sha=write('config.json',cfg)
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    demo.configure(Store(application_dsn),demo.PROFILE,json.dumps(cfg))
    return dict(profile=PROFILE,config_sha256=config_sha,valid_until=value['validity']['valid_until'])


def environment(path, marker):
    from .case_step_assignments import LOCAL_DEMO_MODE
    from .local_synthetic_demo import PROFILE as DEMO_PROFILE
    if marker.get('schema')!=SAMPLE_SCHEMA or marker.get('ids')!=IDS or marker.get('sample',{}).get('profile')!=PROFILE:
        raise Denied('original collaboration sample profile required')
    config=path/'local-sample/config.json'
    if config.is_symlink() or config.resolve()!=config.absolute():raise Denied('unaliased sample config required')
    try:
        fd=os.open(config,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                    or info.st_mode&0o077 or not 0<info.st_size<=16384):
                raise Denied('bounded private sample configuration required')
            raw=os.read(fd,16385)
            if len(raw)!=info.st_size:raise Denied('sample configuration changed during read')
        finally:os.close(fd)
    except OSError:raise Denied('original sample configuration unavailable') from None
    if sha256(raw).hexdigest()!=marker['sample']['config_sha256']:
        raise Denied('original sample config changed; no repair')
    return dict(PARKWEAVE_CASE_STEP_MODE=LOCAL_DEMO_MODE,PARKWEAVE_SERVICE_PROFILE=DEMO_PROFILE,
        PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=raw.decode(),PARKWEAVE_LOCAL_RESOURCE_APPROVAL_MODE='CURRENT_OWNER')


def application(store,path,marker):
    from .api import create_app
    from .case_step_assignments import from_environment
    from .local_resource_approval import configure
    env=environment(path,marker);steps=from_environment(store,env)
    approval=configure(store,'CURRENT_OWNER')
    return create_app(store,local_synthetic_demo=steps.local_synthetic_demo,
        case_step_assignments=steps,local_resource_approval=approval)


def resource_directory(store,token):
    with store.connect() as c:
        actor=store.auth(c,token,lock=True);store.check_capability(c,actor,'READ')
        if (actor['id'],actor['role'],actor['park_id'],actor['org_id'])!=(IDS['resource-admin'],'resource_admin',PARK,ORG):
            raise Denied('sample resource administrator only')
        rows=c.execute('SELECT id,name,revision,capacity,buffer_seconds,open_from,open_until,enabled,timezone,namespace,authority,source FROM synthetic_resources WHERE park_id=%s AND id=ANY(%s::uuid[]) ORDER BY id',(PARK,[x[0] for x in RESOURCES])).fetchall()
        if len(rows)!=2 or any(r['namespace']!='SYNTHETIC' or r['authority']!='LOCAL_AUTHORITY' or r['source'].get('id')!=PROFILE for r in rows):
            raise Denied('original synthetic resource source required')
    return dict(scope='LOCAL_SYNTHETIC_RESOURCE_CONFIGURATION_READ_ONLY',items=rows,
        holds_exposed=False,private_Cases_exposed=False,publish_allowed=False,hold_allowed=False,case_goal_completed=False)


def workspace_page(root,marker):
    from .local_workspace import full_workspace_page
    from html import escape
    page=full_workspace_page(root,LABELS,materials_path='/materials')
    panel=('<section id="local-sample-resource-panel" class="card"><h2>样例资源配置与来源</h2>'
        '<p>资源管理员仅核对已初始化的合成目录，不读取企业占位或私有事项，不发布或预约资源。</p>'
        '<button id="local-sample-resources-read" type="button">读取样例资源与来源</button>'
        '<p id="local-sample-resources-status" role="status"></p><div id="local-sample-resource-items"></div></section>')
    marker_html='<div class="entry-workbench">'
    if page.count(marker_html)!=1:raise Denied('original sample workspace entry required')
    page=page.replace(marker_html,panel+marker_html)
    page=page.replace('</style>',
        'body:not([data-local-role="resource_admin"]) #local-sample-resource-panel{display:none}'
        'body[data-local-role="resource_admin"] .workspace-nav{display:none}'
        'body[data-local-role="resource_admin"] #park-main>:not(#local-sample-resource-panel):not(.shell-toolbar){display:none!important}</style>')
    page=page.replace('合成工程验证 · 未接入真实园区或模型',
        '本地合成样例 · 有效至 '+escape(marker['sample']['valid_until'])+' · 无真实园区或模型')
    script='<script src="/local-sample-resources.js"></script>'
    if '</body>' in page:return page.replace('</body>',script+'</body>')
    if '</html>' in page:return page.replace('</html>',script+'</html>')
    return page+script
