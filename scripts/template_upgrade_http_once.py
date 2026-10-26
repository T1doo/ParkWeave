"""Closed candidate: one temporary Linux PG/real-HTTP/original-page integration.

No import-time service, credential generation or filesystem mutation. Actual
activation requires a separately reviewed invocation and exact source binding.
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode,urlsplit
from uuid import UUID,uuid4

from scripts import template_http_supervision as tree
from scripts import template_http_activation as activation

ROOT=Path(__file__).resolve().parents[1]
PRODUCT_SOURCE='cd44b2e4ac6ae375cb34f8e4749e591999dc4474'
WORK=300;INNER=315;TREE=330;TOTAL=360
FRAME=1024*1024;DISK_STOP=480*1024*1024;DISK_BUDGET=512*1024*1024
PLACEHOLDER='Bearer SYNTHETIC_HTTP_SESSION'
_SEAL=object()
SQL_GRANTS=('GRANT USAGE ON SCHEMA public TO parkweave_app', 'GRANT SELECT ON schema_version,principals,field_grants TO parkweave_app', 'GRANT SELECT,INSERT ON fact_assertions TO parkweave_app', 'GRANT SELECT ON capability_grants,run_assignments,file_resources TO parkweave_app', 'GRANT SELECT,INSERT,UPDATE ON deliveries TO parkweave_app', 'GRANT SELECT ON action_grants TO parkweave_app', 'GRANT INSERT ON authorization_audit TO parkweave_app', 'GRANT SELECT,INSERT,UPDATE ON runs,operations,cases,outbox,run_projection,model_steps TO parkweave_app', 'GRANT SELECT,INSERT ON model_plans TO parkweave_app', 'GRANT SELECT,INSERT ON fact_reviews,fact_followups TO parkweave_app', 'GRANT SELECT ON preparation_catalog,preparation_grants TO parkweave_app', 'GRANT SELECT,INSERT,UPDATE ON preparations TO parkweave_app', 'GRANT SELECT,INSERT ON preparation_evidence,preparation_events TO parkweave_app', 'GRANT SELECT ON synthetic_resources,synthetic_resource_grants TO parkweave_app', 'GRANT SELECT,INSERT ON synthetic_resource_holds,synthetic_resource_receipts TO parkweave_app', 'GRANT UPDATE(state) ON synthetic_resource_holds TO parkweave_app', 'GRANT SELECT,INSERT ON synthetic_resource_combinations,synthetic_resource_combination_members,synthetic_resource_combination_receipts TO parkweave_app', 'GRANT UPDATE(state) ON synthetic_resource_combinations TO parkweave_app', 'GRANT SELECT,INSERT ON service_receipt_steps,service_step_receipts,service_receipt_events TO parkweave_app', 'GRANT UPDATE(state,revision,current_receipt_id) ON service_receipt_steps TO parkweave_app', 'GRANT SELECT,INSERT ON resource_case_claims,case_resource_links TO parkweave_app', 'GRANT SELECT,INSERT ON service_dispatches,service_dispatch_offers,service_dispatch_events TO parkweave_app', 'GRANT UPDATE(revision,current_offer_id) ON service_dispatches TO parkweave_app', 'GRANT UPDATE(state,receipt_step_id) ON service_dispatch_offers TO parkweave_app', 'GRANT SELECT,INSERT ON case_local_lifecycles,case_local_events TO parkweave_app', 'GRANT UPDATE(revision,cycle,state,verified_snapshot,verified_sha256) ON case_local_lifecycles TO parkweave_app', 'GRANT SELECT,INSERT ON dispatch_notice_outbox,dispatch_notices TO parkweave_app', 'GRANT UPDATE(state,consumed_at) ON dispatch_notice_outbox TO parkweave_app', 'GRANT UPDATE(seen_at,read_at) ON dispatch_notices TO parkweave_app', 'GRANT SELECT,INSERT ON controlled_plans,controlled_plan_events TO parkweave_app', 'GRANT UPDATE(revision,checked,invalidated_from,invalidated_at) ON controlled_plans TO parkweave_app')
PAGE_SHA256='d957c7d9193c76e3f8f5b1024e1e16d1fb3da5991867070464bdf3b23e764212'
PG_HASHES={'initdb':'c725d1d5c4073f3eb95335f296685ed1b4822e9f7d35fea09916d52e58b0ddf2','postgres':'ae05b2a1b0685f2c69b8b9eb3765b1429a5c173c64b248f7f157de2af9db768d'}


Closed=activation.Closed


class Permit:
    def __init__(self,seal,source,invocation,approval=None):
        if seal is not _SEAL or approval is None or approval.invocation!=invocation:raise Closed('window closed')
        self.source=source;self.invocation=invocation;self.approval=approval
    def check(self):self.approval.check()


def authorize(source,invocation,approval=None,started=None):
    approval=approval or activation.load(invocation)
    if sys.platform!='linux' or os.geteuid()==0:raise Closed('unprivileged Linux required')
    activation.verify_source(source,approval,time.monotonic() if started is None else started)
    return Permit(_SEAL,source,invocation,approval)


def fault(error):
    name=type(error).__name__
    return dict(type=name if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}',name) else 'OTHER',
                errno=getattr(error,'errno',None) if type(getattr(error,'errno',None)) is int and 0<=error.errno<=4095 else None)


class Clock:
    def __init__(self,started,now=time.monotonic):self.started=started;self.now=now;self.stopped=False
    def left(self,seconds=10,*,cleanup=False):
        if self.stopped and not cleanup:raise Closed('disk monitor stopped work')
        left=self.started+(INNER if cleanup else WORK)-self.now()
        if left<=0:raise TimeoutError('shared deadline')
        return min(seconds,left)


def deadline_check(deadline):
    if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('absolute invocation deadline')


def save(path,value,tokens=(),*,deadline=None):
    # Callers supply only fixed schema/statuses/counts, never request objects.
    deadline_check(deadline)
    raw=json.dumps(value,sort_keys=True).encode()
    if len(raw)>FRAME or any(t.encode() in raw for t in tokens if t):raise Closed('unsafe report')
    deadline_check(deadline)
    tree.atomic_report(path,value)
    deadline_check(deadline)


class PrivateRoot:
    def __init__(self,path,fd):
        self.path=path;self.fd=fd;self.identity=os.fstat(fd)
    @classmethod
    def create(cls,permit,*,evidence=False):
        permit.check();parent=ROOT.parent/'scratch' if evidence else Path('/tmp')
        if not parent.is_dir() or parent.is_symlink():raise Closed('fixed private parent required')
        path=parent/(('parkweave-http-evidence-' if evidence else 'pw-api-')+uuid4().hex)
        path.mkdir(mode=0o700,exist_ok=False)
        fd=None
        try:
            fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            result=cls(path,fd);result.verify();return result
        except BaseException as error:
            error.private_created_path=str(path);error.private_close_errors=[]
            if fd is not None:
                try:os.close(fd)
                except BaseException as close_error:error.private_close_errors.append(fault(close_error))
            raise

    def verify(self):
        st=self.path.lstat();held=os.fstat(self.fd)
        fixed=(self.path.parent==Path('/tmp') and re.fullmatch('pw-api-[0-9a-f]{32}',self.path.name)
               or self.path.parent==ROOT.parent/'scratch' and re.fullmatch('parkweave-http-evidence-[0-9a-f]{32}',self.path.name))
        if (not fixed or self.path.resolve()!=self.path or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o077
                or (st.st_dev,st.st_ino)!=(self.identity.st_dev,self.identity.st_ino)
                or (held.st_dev,held.st_ino)!=(st.st_dev,st.st_ino)):raise Closed('private identity drift')
    def remove(self,owned,report,*,deadline=None):
        deadline_check(deadline);self.verify()
        if (owned.get('status')!='CLEANUP_CONFIRMED' or report.get('status')!='PASS'
                or report.get('sanitized') is not True or report.get('worker_final') is not True or report.get('partial') is not False):
            raise Closed('retain uncertain private state')
        # Cooperative same-UID boundary: all owned writers are already stopped.
        # Never follow a replacement root or a child symlink. No hostile-UID claim.
        def walk(fd):
            deadline_check(deadline)
            for name in os.listdir(fd):
                deadline_check(deadline)
                before=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if stat.S_ISLNK(before.st_mode):raise Closed('unexpected private symlink')
                if stat.S_ISDIR(before.st_mode):
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    try:
                        if not os.path.samestat(before,os.fstat(child)):raise Closed('private child drift')
                        walk(child)
                    finally:os.close(child)
                    if not os.path.samestat(before,os.stat(name,dir_fd=fd,follow_symlinks=False)):raise Closed('private child drift')
                    deadline_check(deadline);os.rmdir(name,dir_fd=fd)
                elif stat.S_ISREG(before.st_mode):os.unlink(name,dir_fd=fd)
                else:raise Closed('unexpected private object')
        walk(self.fd);deadline_check(deadline);self.verify();self.path.rmdir()


class BudgetHTTP:
    def __init__(self,origin,client,clock,token,checkpoint=lambda:None):
        parsed=urlsplit(origin)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path or parsed.username or parsed.password:raise Closed('loopback origin required')
        self.origin=origin;self.client=client;self.clock=clock;self.token=token;self.checkpoint=checkpoint
        self.gets=0;self.posts=0;self.traffic=[];self.instance=None;self.target=None;self.target_hash=None
    def request(self,method,path,*,body=None,actor=None,stage='read',key=None):
        self.clock.left()
        pub='/api/template-candidate/park-a/new-enterprise-material-template'
        base='/api/template-consumer/instances/'+str(self.instance)
        check='/api/template-upgrade/'+str(self.instance)+'/check?'+urlencode(dict(target_release_id=self.target,target_sha256=self.target_hash))
        if method not in ('GET','POST') or '#' in path:raise Closed('route')
        if method=='GET':
            if path not in (pub,'/api/template-consumer/catalog',base+'/planning',check):raise Closed('GET route')
            if self.gets>=20:raise Closed('GET budget')
            self.gets+=1
        else:
            if self.posts>=12 or stage not in ('publication','create','resume','adopt'):raise Closed('POST budget')
            plan=[('publication','SAVE_DRAFT'),('publication','SUBMIT'),('publication','REVIEW'),('publication','CANDIDATE_PUBLISH'),('create',None),('resume',None),('adopt',None),('publication','RETURN_DRAFT'),('publication','SAVE_DRAFT'),('publication','SUBMIT'),('publication','REVIEW'),('publication','CANDIDATE_PUBLISH')]
            wanted,action=plan[self.posts]
            routes={'publication':pub+'/commands','create':'/api/template-consumer/instances','resume':base+'/resume','adopt':base+'/adopt'}
            if stage!=wanted or path!=routes[stage] or type(body) is not dict or (action and body.get('action')!=action):raise Closed('POST sequence')
            expected='template-reviewer' if action=='REVIEW' else 'template-publisher' if action=='CANDIDATE_PUBLISH' else 'template-author'
            if stage=='publication' and actor!=expected or stage!='publication' and actor is not None:raise Closed('POST actor')
            self.posts+=1
        headers={'X-Isolated-Template-Actor':actor} if actor else {'Authorization':'Bearer '+self.token}
        if key:headers['Idempotency-Key']=key
        if body is not None and len(json.dumps(body).encode())>65536:raise Closed('request length')
        event=dict(sequence=len(self.traffic)+1,method=method,stage=stage,status=None)
        self.traffic.append(event);self.checkpoint()
        with self.client.stream(method,self.origin+path,headers=headers,json=body,
                                timeout=self.clock.left(10),follow_redirects=False) as response:
            chunks=[];size=0
            for chunk in response.iter_bytes():
                self.clock.left();size+=len(chunk)
                if size>FRAME:raise Closed('response length')
                chunks.append(chunk)
            if 300<=response.status_code<400:raise Closed('redirect refused')
            event['status']=response.status_code
            value=json.loads(b''.join(chunks))
        self.checkpoint()
        return response.status_code,value
    def page_read(self,path,options):
        expected='/api/template-upgrade/'+self.instance+'/check?'+urlencode(dict(target_release_id=self.target,target_sha256=self.target_hash))
        if path not in ('/api/template-consumer/catalog',expected):raise Closed('page route')
        if set(options)-{'method','headers','body'} or options.get('method','GET')!='GET' or options.get('body') is not None:raise Closed('page method')
        if options.get('headers')!={'Authorization':PLACEHOLDER,'Content-Type':'application/json'}:raise Closed('page identity')
        return self.request('GET',path)


def configure_template(permit,store,path):
    permit.check()
    from parkweave.template_candidate import TemplateConfig,TemplateEngine,TemplateRepository
    from parkweave.template_consumer import ConsumerConfig,ConsumerRepository,TemplateConsumer
    from parkweave.template_upgrade import TemplateUpgradeChecker,UpgradeRepository
    from parkweave.template_isolated_app import create_isolated_template_app
    from psycopg.conninfo import conninfo_to_dict
    from test_template_candidate import template_config
    config=template_config().model_dump()
    for permit in config['permits']:permit['scope']['park_id']='park-a'
    engine=TemplateEngine(TemplateConfig.model_validate(config),TemplateRepository(path/'http.template.candidate.sqlite3'))
    consumer=TemplateConsumer(store,engine,ConsumerConfig(enabled_for_isolated_tests=True,
        allowed_database_names=[conninfo_to_dict(store.dsn)['dbname']],allowed_orgs=[{'park_id':'park-a','org_id':'org-a'}]),ConsumerRepository(path/'http.consumer.candidate.sqlite3'))
    checker=TemplateUpgradeChecker(consumer,UpgradeRepository(path/'http.upgrade.candidate.sqlite3'),enabled_for_isolated_tests=True)
    return create_isolated_template_app(store,engine,consumer,checker),engine,consumer,checker


def publish(http,engine,revision):
    from test_template_candidate import definition,VALID
    path='/api/template-candidate/park-a/new-enterprise-material-template'
    status,view=http.request('GET',path,actor='template-author');assert status==200
    actions=[('SAVE_DRAFT','template-author'),('SUBMIT','template-author'),('REVIEW','template-reviewer'),('CANDIDATE_PUBLISH','template-publisher')]
    if view['state']!='NOT_CREATED':actions.insert(0,('RETURN_DRAFT','template-author'))
    for action,actor in actions:
        body=dict(action=action,expected_revision=view['revision'],expected_definition_sha256=view['definition_sha256'],reason='SYNTHETIC HTTP fixture')
        if action=='SAVE_DRAFT':body['draft']=definition(revision=revision).model_dump(mode='json')
        if action=='CANDIDATE_PUBLISH':body['validity']=VALID
        status,view=http.request('POST',path+'/commands',body=body,actor=actor,stage='publication',key=uuid4().hex);assert status==200
    return engine.public_catalog('park-a')['items'][0]


def bootstrap_case(http,store,engine):
    release=publish(http,engine,'1')
    body=dict(release_id=release['release_id'],expected_release_sha256=release['release_sha256'],goal='SYNTHETIC HTTP INPUT',
        reviewer_id='prep-specialist-fixture-a',materials=[dict(slot=s,text='SYNTHETIC HTTP '+s,source_kind='USER_STATEMENT',source_label='Synthetic temporary input') for s in ('need_summary','material_outline')],reason='SYNTHETIC explicit input')
    code,row=http.request('POST','/api/template-consumer/instances',body=body,stage='create',key=uuid4().hex);assert code==201
    run=UUID(row['run_id'])
    with store.connect() as c:
        candidates=c.execute("SELECT r.id,r.namespace,o.action,o.state FROM runs r JOIN operations o ON o.run_id=r.id WHERE r.state='QUEUED'").fetchall()
        if len(candidates)!=1 or candidates[0]['id']!=run or candidates[0]['namespace']!='SYNTHETIC' or candidates[0]['action']!='case.create' or candidates[0]['state']!='PREPARED':raise Closed('unique created Run required before claim')
    claim=store.claim('synthetic-http-fixture')
    if claim is None or claim['id']!=run:raise Closed('exact created Run claim required')
    with store.connect() as c:
        rows=c.execute('SELECT action,state FROM operations WHERE run_id=%s',(run,)).fetchall()
        if len(rows)!=1 or rows[0]['action']!='case.create' or rows[0]['state']!='PREPARED':raise Closed('exact prepared Case action required')
    store.finish(claim) # Original deterministic Case transaction, no model adapter.
    with store.connect() as c:
        completed=c.execute('SELECT r.state,c.id FROM runs r JOIN cases c ON c.run_id=r.id WHERE r.id=%s',(run,)).fetchall()
        if len(completed)!=1 or completed[0]['state']!='SUCCEEDED':raise Closed('created Case binding not observed')
    http.instance=str(row['instance_id']);base='/api/template-consumer/instances/'+http.instance
    code,row=http.request('POST',base+'/resume',body={},stage='resume',key=uuid4().hex);assert code==200
    code,preview=http.request('GET',base+'/planning');assert code==200
    body=dict(expected_preparation_revision=preview['current']['preparation_revision'],expected_request_revision=preview['request_intent']['revision'],expected_source_sha256=preview['current']['source_sha256'],expected_plan_revision=0,required_goals=preview['request_intent']['required_goals'],reason='SYNTHETIC explicit initial plan')
    code,row=http.request('POST',base+'/adopt',body=body,stage='adopt',key=uuid4().hex);assert code==200
    if row['state']!='PLAN_ADOPTED' or UUID(row['run_id'])!=run or UUID(row['case_id'])!=completed[0]['id']:raise Closed('exact adopted Case binding required')
    target=publish(http,engine,'2');http.target=str(target['release_id']);http.target_hash=target['release_sha256']
    assert http.posts==12
    return row


def business_snapshot(owner):
    values={}
    with owner.connect() as c:
        for table in ('runs','cases','preparations','preparation_evidence','preparation_events','controlled_plans','controlled_plan_events'):
            values[table]=c.execute('SELECT to_jsonb(t)::text AS value FROM '+table+' t ORDER BY to_jsonb(t)::text').fetchall()
    return sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()


def frame_write(stream,value,clock):
    raw=json.dumps(value).encode()+b'\n'
    if len(raw)>FRAME:raise Closed('IPC frame bound')
    fd=stream.fileno();os.set_blocking(fd,False);sent=0
    with selectors.DefaultSelector() as selector:
        selector.register(fd,selectors.EVENT_WRITE)
        while sent<len(raw):
            if not selector.select(clock.left(1)):continue
            try:sent+=os.write(fd,raw[sent:])
            except BlockingIOError:pass


def run_page(child,http,owner,clock,params):
    frame_write(child.stdin,params,clock);pending=b'';before=business_snapshot(owner);stage='CHECKED';done=False
    with selectors.DefaultSelector() as selector:
        selector.register(child.stdout,selectors.EVENT_READ)
        while not done:
            if not selector.select(clock.left(1)):
                if child.poll() is not None:raise Closed('page exited without terminal frame')
                continue
            chunk=os.read(child.stdout.fileno(),65536)
            if not chunk:raise Closed('page IPC EOF')
            pending+=chunk
            if len(pending)>FRAME:raise Closed('page IPC bound')
            while b'\n' in pending:
                raw,pending=pending.split(b'\n',1);message=json.loads(raw)
                if message.get('type')=='request':
                    if set(message)!={'type','id','path','options'} or type(message['id']) is not int:raise Closed('request frame')
                    code,value=http.page_read(message['path'],message['options'])
                    frame_write(child.stdin,dict(id=message['id'],status=code,body=value),clock)
                elif message=={'type':'CHECKED'} and stage=='CHECKED':
                    if business_snapshot(owner)!=before:raise Closed('read changed product')
                    owner.revoke_capability('fixture-a','READ');stage='DENIED'
                    frame_write(child.stdin,{'type':'REVOKED'},clock)
                elif message=={'type':'DONE'} and stage=='DENIED':
                    if business_snapshot(owner)!=before:raise Closed('denial changed product')
                    done=True
                else:raise Closed('unexpected page frame')
    child.wait(timeout=clock.left(5))
    if child.returncode!=0:raise Closed('page failed')


@contextmanager
def api_server(app,clock):
    import uvicorn
    baseline=set(threading.enumerate());listener=None;thread=None;server=None;port=None;primary=None;errors=[]
    try:
        listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='critical',access_log=False,proxy_headers=False,timeout_graceful_shutdown=5))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=False);thread.start()
        until=time.monotonic()+clock.left(10)
        while not server.started:
            clock.left()
            if not thread.is_alive() or time.monotonic()>=until:raise Closed('API readiness unknown')
            time.sleep(.02)
        yield 'http://127.0.0.1:'+str(port)
    except BaseException as error:primary=error
    finally:
        if server is not None:server.should_exit=True
        if thread is not None and thread.ident is not None:
            try:thread.join(clock.left(10,cleanup=True))
            except BaseException as error:errors.append(fault(error))
        if listener is not None:
            try:listener.close()
            except BaseException as error:errors.append(fault(error))
        try:
            while any(t.is_alive() for t in set(threading.enumerate())-baseline):
                clock.left(1,cleanup=True);time.sleep(.02)
            if port is not None:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=clock.left(.3,cleanup=True)):raise Closed('API listener remains')
                except ConnectionRefusedError:pass
        except BaseException as error:errors.append(fault(error))
        if primary is not None:
            primary.http_cleanup_errors=errors
            raise primary
        if errors:
            error=Closed('API cleanup unknown');error.http_cleanup_errors=errors;raise error


def freeze_client(permit,path,clock):
    permit.check()
    original=ROOT/'scripts/template_upgrade_http_client.js'
    raw,identity=activation.regular_bytes(original,65536)
    expected=activation.git(['show',permit.source+':scripts/template_upgrade_http_client.js'],clock.started)
    if raw!=expected:raise Closed('client source drift')
    dest=path/'frozen-client.js'
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        if os.write(fd,raw)!=len(raw):raise Closed('short frozen client write')
    finally:os.close(fd)
    frozen,held=activation.regular_bytes(dest,65536)
    if frozen!=expected:raise Closed('frozen client mismatch')
    return dest,held,sha256(raw).hexdigest()


def verify_frozen_client(frozen):
    path,identity,digest=frozen;raw,now=activation.regular_bytes(path,65536)
    if now!=identity or sha256(raw).hexdigest()!=digest:raise Closed('frozen client changed')
    return path


def real_worker(permit,path,clock,report):
    """Only called after the independent, presently closed invocation gate."""
    permit.check()
    import importlib.metadata
    import secrets
    import httpx
    import psycopg
    from psycopg.conninfo import make_conninfo
    from parkweave.store import Store
    from parkweave import preparation
    from parkweave.case_fact_clarifications import capture_fixture_cluster
    from parkweave.process_env import minimal_environment
    bins=Path(importlib.metadata.distribution('pgserver').locate_file('pgserver/pginstall/bin'))
    for name in ('socket','tmp','logs'): (path/name).mkdir(mode=0o700)
    frozen_client=freeze_client(permit,path,clock)
    env=minimal_environment(os.environ,TMPDIR=str(path/'tmp'),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'src')+':'+str(ROOT/'tests')+':'+str(ROOT))
    for name,digest in PG_HASHES.items():
        binary=bins/name
        if binary.is_symlink() or sha256(binary.read_bytes()).hexdigest()!=digest:raise Closed('fixed PG binary drift')
    if sha256((ROOT/'src/parkweave/template_upgrade_web.html').read_bytes()).hexdigest()!=PAGE_SHA256:raise Closed('original page drift')
    postgres=None;node=None;http=None;tokens={};sanitized=False;primary=None
    def checkpoint():
        if http is not None:report.update(GET=http.gets,POST=http.posts,traffic=http.traffic)
        save(path/'partial.json',report,tokens.values())
    try:
        report['phase']='INITDB';checkpoint()
        with (path/'logs/initdb.log').open('xb') as log:
            subprocess.run([str(bins/'initdb'),'-D',str(path/'data'),'-U','postgres','--auth-local=trust','--auth-host=reject','--encoding=UTF8','--no-locale'],env=env,stdout=log,stderr=log,check=True,timeout=clock.left(30))
        with (path/'logs/postgres.log').open('xb') as log:
            postgres=subprocess.Popen([str(bins/'postgres'),'-D',str(path/'data'),'-h','','-k',str(path/'socket'),'-p','5432','-c','unix_socket_permissions=0700','-c','shared_buffers=16MB','-c','max_connections=8','-c','dynamic_shared_memory_type=mmap'],env=env,stdout=log,stderr=log)
        admin=make_conninfo(host=str(path/'socket'),port=5432,user='postgres',dbname='postgres',connect_timeout=2,options='-c statement_timeout=5000')
        end=time.monotonic()+clock.left(15)
        while True:
            clock.left()
            if postgres.poll() is not None:raise Closed('owned PG exited')
            try:
                with psycopg.connect(admin) as c:
                    facts=c.execute("SELECT current_setting('listen_addresses'),current_setting('unix_socket_directories'),current_setting('unix_socket_permissions'),current_setting('dynamic_shared_memory_type'),current_setting('data_directory')").fetchone()
                    if facts!=('',str(path/'socket'),'0700','mmap',str(path/'data')):raise Closed('PG actual binding mismatch')
                break
            except psycopg.OperationalError:
                if time.monotonic()>=end:raise Closed('PG readiness unknown')
                time.sleep(.1)
        report['phase']='SCHEMA_AND_SYNTHETIC_AUTHORITY';checkpoint()
        cluster=capture_fixture_cluster(admin,path/'data');db='fixture_'+uuid4().hex
        with psycopg.connect(admin,autocommit=True) as c:
            c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        owner=Store(make_conninfo(admin,dbname=db))
        with owner.connect() as c:owner._case_fact_fixture_receipt=cluster.record_created_database(c)
        owner.migrate()
        tokens={k:secrets.token_urlsafe(32) for k in ('fixture-a','fixture-b','fixture-c')};owner.seed(tokens)
        tokens.update({k:secrets.token_urlsafe(32) for k in ('prep-specialist-fixture-a','prep-specialist-fixture-b','prep-specialist-fixture-c')});preparation.seed_synthetic(owner,tokens)
        with owner.connect() as c:
            for grant in SQL_GRANTS:c.execute(grant)
        app_store=Store(make_conninfo(owner.dsn,user='parkweave_app'));app,engine,consumer,checker=configure_template(permit,app_store,path)
        with api_server(app,clock) as origin,httpx.Client(trust_env=False,follow_redirects=False) as client:
            http=BudgetHTTP(origin,client,clock,tokens['fixture-a'],checkpoint);report['phase']='BOOTSTRAP_NEW_CASE';checkpoint()
            row=bootstrap_case(http,app_store,engine)
            params=dict(instance=http.instance,page=str(ROOT/'src/parkweave/template_upgrade_web.html'),page_sha256=PAGE_SHA256)
            report['phase']='ORIGINAL_PAGE_REAL_HTTP';checkpoint()
            with (path/'logs/node.log').open('xb') as log:
                node=subprocess.Popen(['node',str(verify_frozen_client(frozen_client))],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
                run_page(node,http,owner,clock,params)
            report.update(status='PASS',GET=http.gets,POST=http.posts,API='REAL_LOOPBACK_HTTP',PG='REAL_PRIVATE_UNIX_SOCKET',page='NODE_VM_ORIGINAL_SCRIPT_NOT_BROWSER')
    except BaseException as error:primary=error;report.update(status='FAIL',error=fault(error))
    finally:
        failures=list(getattr(primary,'http_cleanup_errors',()))
        for child,sig in ((node,signal.SIGTERM),(postgres,signal.SIGINT)):
            if child is None:continue
            try:
                if child.poll() is None:child.send_signal(sig)
                child.wait(timeout=clock.left(10,cleanup=True))
            except BaseException as error:failures.append(fault(error))
        # Never publish raw component logs. Scan known values before certifying
        # deletion; failed/unknown runs retain private originals for diagnosis.
        try:
            for p in (path/'logs').iterdir():
                if p.stat().st_size>2*FRAME:raise Closed('private component log bound')
                raw=p.read_bytes()
                if any(t.encode() in raw for t in tokens.values()):raise Closed('private log secret detected')
            if any(t in json.dumps(report) for t in tokens.values()):raise Closed('report secret detected')
            sanitized=True
        except BaseException as error:failures.append(fault(error))
        report.update(sanitized=sanitized,cleanup_errors=failures,worker_final=True)
        if http is not None:report.update(GET=http.gets,POST=http.posts,traffic=http.traffic)
        if report.get('status')!='PASS' and http is not None and http.posts:report['business_outcome']='PARTIAL_OR_UNKNOWN'
        if failures:report['status']='FAIL'


def directory_bytes(path):
    total=0
    for parent,dirs,files in os.walk(path,followlinks=False):
        for name in dirs+files:
            p=Path(parent)/name
            if p.is_symlink():raise Closed('private tree symlink')
            total+=p.lstat().st_size
    return total


def validate_worker_report(value):
    allowed={'status','phase','real_models','error','sanitized','cleanup_errors','worker_final','partial','GET','POST','traffic','API','PG','page','business_outcome','disk_errors'}
    if type(value) is not dict or set(value)-allowed:raise Closed('worker report shape')
    if value.get('status') not in ('PASS','FAIL') or value.get('phase') not in ('START','INITDB','SCHEMA_AND_SYNTHETIC_AUTHORITY','BOOTSTRAP_NEW_CASE','ORIGINAL_PAGE_REAL_HTTP'):raise Closed('worker report state')
    if value.get('real_models') is not False or type(value.get('worker_final')) is not bool or type(value.get('partial')) is not bool:raise Closed('worker report completion')
    for name,limit in [('GET',20),('POST',12)]:
        if name in value and (type(value[name]) is not int or not 0<=value[name]<=limit):raise Closed('worker request counts')
    for name in ('sanitized',):
        if name in value and type(value[name]) is not bool:raise Closed('worker boolean')
    for name in ('cleanup_errors','disk_errors'):
        errors=value.get(name,[])
        if type(errors) is not list or len(errors)>8:raise Closed('worker errors')
        for item in errors:validate_fault(item)
    if 'error' in value:validate_fault(value['error'])
    for k,v in [('API','REAL_LOOPBACK_HTTP'),('PG','REAL_PRIVATE_UNIX_SOCKET'),('page','NODE_VM_ORIGINAL_SCRIPT_NOT_BROWSER'),('business_outcome','PARTIAL_OR_UNKNOWN')]:
        if k in value and value[k]!=v:raise Closed('worker label')
    traffic=value.get('traffic',[])
    if type(traffic) is not list or len(traffic)>32:raise Closed('worker traffic')
    for index,event in enumerate(traffic,1):
        if type(event) is not dict or set(event)!={'sequence','method','stage','status'} or event['sequence']!=index or event['method'] not in ('GET','POST') or event['stage'] not in ('read','publication','create','resume','adopt') or (event['status'] is not None and (type(event['status']) is not int or not 100<=event['status']<=599)):raise Closed('worker traffic row')


def validate_fault(value):
    if (type(value) is not dict or set(value)!={'type','errno'} or type(value['type']) is not str
            or re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}',value['type']) is None
            or value['errno'] is not None and (type(value['errno']) is not int or not 0<=value['errno']<=4095)):raise Closed('worker fault shape')


def worker(permit,path,identity,claim_args):
    hand=json.loads(sys.stdin.buffer.readline(4096));started=hand['started']
    claim_path,claim_dev,claim_ino,file_dev,file_ino=claim_args
    parent=tree.identity(os.getppid())
    claim=activation.OnceClaim.restore(claim_path,(int(claim_dev),int(claim_ino)),(int(file_dev),int(file_ino)),permit.source,permit.invocation,os.getppid(),parent['start_ticks'])
    if started!=claim.value['started']:raise Closed('worker cannot reset original clock')
    if hand['parent_pid']!=os.getppid() or hand['worker_pid']!=os.getpid() or not 0<=time.monotonic()-started<300:raise Closed('worker handshake')
    st=path.lstat()
    if (path.parent!=Path('/tmp') or re.fullmatch('pw-api-[0-9a-f]{32}',path.name) is None or path.resolve()!=path
            or not stat.S_ISDIR(st.st_mode) or (st.st_dev,st.st_ino)!=identity or st.st_uid!=os.geteuid() or st.st_mode&0o077):raise Closed('worker root identity')
    os.environ['SQLITE_TMPDIR']=str(path/'tmp') # Only private SQLite spill path; Python tempfile stays /tmp.
    clock=Clock(started);report=dict(status='FAIL',phase='START',real_models=False,worker_final=False,partial=True,sanitized=False);stop=threading.Event();retired=threading.Event();disk_failed=[]
    def monitor():
        try:
            while not stop.wait(.1):
                try:
                    if directory_bytes(path)>=DISK_STOP:raise Closed('private disk threshold')
                except BaseException as error:
                    disk_failed.append(fault(error));clock.stopped=True
                    if not stop.is_set():os.kill(os.getpid(),signal.SIGALRM)
                    return
        finally:retired.set()
    monitor_thread=threading.Thread(target=monitor,daemon=False)
    def alarm(*_):raise TimeoutError('business deadline')
    old=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,clock.left(300));monitor_thread.start()
    try:real_worker(permit,path,clock,report)
    except BaseException as error:report.update(status='FAIL',error=fault(error))
    finally:
        stop.set()
        try:retired.wait(clock.left(2,cleanup=True))
        except BaseException as error:disk_failed.append(fault(error))
        signal.setitimer(signal.ITIMER_REAL,0)
        if retired.is_set():
            monitor_thread.join(0);signal.signal(signal.SIGALRM,old)
        # An unretired sender retains this handler, never the old default.
        if disk_failed or not retired.is_set() or monitor_thread.is_alive():report.update(status='FAIL',disk_errors=disk_failed)
        report.update(worker_final=True,partial=False)
        save(path/'result.json',report)
    return 0 if report['status']=='PASS' else 1


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--invocation',required=True)
    parser.add_argument('--owned-worker',nargs=3);parser.add_argument('--claim',nargs=5);args=parser.parse_args(argv)
    started=time.monotonic()
    try:approval=activation.load(args.invocation)
    except (Closed,ValueError,OSError):return 2 # Default closed before process/directory/credential actions.
    if args.owned_worker:
        if not args.claim:return 2
        # The claim/handshake supplies the original clock, never this parse time.
        claim_path,dev,ino,file_dev,file_ino=args.claim
        try:
            parent=tree.identity(os.getppid())
            claim=activation.OnceClaim.restore(claim_path,(int(dev),int(ino)),(int(file_dev),int(file_ino)),args.source,args.invocation,os.getppid(),parent['start_ticks'])
            permit=authorize(args.source,args.invocation,approval,claim.value['started'])
            path,root_dev,root_ino=args.owned_worker
            return worker(permit,Path(path),(int(root_dev),int(root_ino)),args.claim)
        except BaseException:return 1
    if args.claim:return 2
    watchdog=activation.TotalDeadline(started);watchdog.arm()
    try:
        permit=authorize(args.source,args.invocation,approval,started)
        claim=activation.OnceClaim.create(permit.source,permit.invocation,started,tree.identity(os.getpid())['start_ticks'])
    except BaseException as error:
        print(json.dumps(dict(status='NOT_STARTED',stage='SOURCE_AND_CLAIM',error=fault(error))),flush=True);return 1
    deadline=started+TOTAL;os.umask(0o077)
    evidence=None;root=None
    report=dict(status='PENDING_FINALIZATION',scope='ONE_TEMPORARY_REAL_HTTP_FIXTURE',source=permit.source)
    try:
        evidence=PrivateRoot.create(permit,evidence=True);report['evidence_directory']=str(evidence.path)
        root=PrivateRoot.create(permit)
        env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TZ') if k in os.environ}
        env.update(PYTHONPATH=str(ROOT/'src')+':'+str(ROOT/'tests')+':'+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        argv=[sys.executable,'-B','-m','scripts.template_upgrade_http_once','--source',permit.source,'--invocation',permit.invocation,'--owned-worker',str(root.path),str(root.identity.st_dev),str(root.identity.st_ino),'--claim',str(claim.path),str(claim.identity[0]),str(claim.identity[1]),str(claim.file_identity[0]),str(claim.file_identity[1])]
        report.update(directory_retained=str(root.path),claim_directory=str(claim.path),total_seconds=TOTAL,cleanup_reserve_seconds=30,required_exit=0)
        save(evidence.path/'result.json',report,deadline=deadline)
        owned=tree.supervise(argv,env=env,cwd=ROOT,directory=root.path,started=started)
        result=root.path/'result.json'
        if not result.is_file():result=root.path/'partial.json'
        data=json.loads(result.read_text()) if result.is_file() and result.stat().st_size<=FRAME else {}
        validate_worker_report(data)
        success=(data.get('status')=='PASS' and data.get('worker_final') is True and data.get('partial') is False
                 and owned['operation_status']=='PASS' and owned['status']=='CLEANUP_CONFIRMED')
        report.update(worker=data,owned=owned,operation_status='PASS' if success else 'FAIL')
        evidence.verify();save(evidence.path/'result.json',report,deadline=deadline)
        print(json.dumps(dict(status='PENDING_FINALIZATION',evidence_directory=str(evidence.path))),flush=True)
        if success:
            root.remove(owned,data,deadline=deadline);report['directory_removed']=True;report.pop('directory_retained',None)
        else:report['directory_retained']=str(root.path)
        report['status']='OBSERVED_COMPLETE_REQUIRES_EXIT_0' if success else 'FAIL'
    except BaseException as error:
        report.update(status='FAIL',parent_error=fault(error))
        if hasattr(error,'private_created_path'):
            report.update(retained_creation_directory=error.private_created_path,creation_close_errors=error.private_close_errors)
        if root is not None:report['directory_retained']=str(root.path)
    finally:
        if root is not None:
            try:os.close(root.fd)
            except OSError as error:report.update(status='FAIL',root_close_error=fault(error))
    if time.monotonic()-started>TOTAL:report['status']='FAIL'
    if evidence is None:
        print(json.dumps(report),flush=True);return 1
    try:
        evidence.verify();os.close(evidence.fd);evidence.fd=None
        save(evidence.path/'result.json',report,deadline=deadline)
        if time.monotonic()-started>TOTAL:
            report['status']='FAIL';save(evidence.path/'result.json',report,deadline=deadline)
    except BaseException:
        # Never print a PASS that could precede failed publication.
        return 1
    return 0 if report['status']=='OBSERVED_COMPLETE_REQUIRES_EXIT_0' else 1


if __name__=='__main__':raise SystemExit(main())
