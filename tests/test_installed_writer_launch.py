"""Direct offline unittest: protected observations/FD/processes are explicit DI.

No test starts a process, connects to a database/socket, installs, grants or
issues real authority. Retained keys and records below are synthetic memory.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import psycopg
import pytest
from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave import native_run_access_writer as writer
from parkweave.store import Denied
import test_native_run_access_restricted_adapter as legacy


KEY=b'SYNTHETIC_HOST_KEY_NOT_REAL_12345'[:32].ljust(32,b'_')


def signed(payload):
    return writer._canonical(dict(payload=payload,hmac_sha256=hmac.new(
        KEY,writer._canonical(payload).encode(),'sha256').hexdigest())).encode()


def inputs(root_digit='c'):
    spec,catalog,layout,private=legacy.adapter_inputs()
    old=spec['policy']['database_name'];spec['policy']['database_name']='synthetic_installed_case'
    private['writer_dsn']=private['writer_dsn'].replace(old,spec['policy']['database_name'])
    catalog['database']['name']=spec['policy']['database_name']
    layout['schema_version']='parkweave-installed-writer-layout/1'
    layout['runtime_root']='/var/lib/parkweave/runtimes/'+root_digit*32
    layout['installation_receipt_sha256']=layout.pop('creation_receipt_sha256');layout.pop('trial_root')
    spec['protected_location']=layout['runtime_root']
    layout['private_bootstrap_sha256']=sha256(writer._canonical(private).encode()).hexdigest()
    receipt=signed(host.installed_receipt_payload(spec,layout))
    layout['installation_receipt_sha256']=sha256(receipt).hexdigest()
    return spec,catalog,layout,private,receipt


class Child:
    def __init__(self,pid=90101):self.pid=pid;self.code=None;self.signals=[]
    def poll(self):return self.code
    def send_signal(self,value):self.signals.append(value)
    def wait(self,timeout):self.code=0;return 0
    def kill(self):self.signals.append(signal.SIGKILL);self.code=-9


class Harness:
    def __init__(self,root_digit='c'):
        self.spec,self.catalog,self.layout,self.private,self.receipt=inputs(root_digit)
        self.controller=host.LinuxHost(self.spec,self.layout);self.reads=[];self.events=[]
        self.spawned=False;self.child=Child();self.published=None;self.payload=None
    def protected(self,path,owner,*,private=False,expected=None,**kwargs):
        self.reads.append((path,owner,private,expected));layout=self.controller.layout
        records={layout.approval_key_path:KEY,layout.approval_path:signed(host.installed_launch_request(self.spec,self.layout)),
                 layout.installation_path:self.receipt,layout.bootstrap_path:writer._canonical(self.private).encode()}
        raw=records[path]
        if expected is not None and sha256(raw).hexdigest()!=expected:raise Denied('DI protected input content changed')
        return raw
    def process(self,pid):
        child=pid==self.child.pid;uid=self.layout['writer_uid'] if child else 0
        gid=self.layout['ipc_gid'] if child else 0
        return dict(pid=pid,uid=uid,gid=gid,uids=[uid]*4,gids=[gid]*4,groups=[],started='DI_CHILD' if child else 'DI_HOST')
    def endpoint(self,path,layout):
        return dict(device=1,inode=11 if path==layout.command_path else 12,
                    uid=layout.writer_uid,gid=layout.ipc_gid,mode=0o660)
    def popen(self,**kwargs):
        self.spawned=True;self.events.append(('Popen',kwargs));return self.child
    def exists(self,path):
        return self.spawned and str(path) in (self.controller.layout.command_path,self.controller.layout.verify_path)
    @contextmanager
    def observations(self):
        with ExitStack() as stack:
            for index,name in enumerate(('F_ADD_SEALS','F_GET_SEALS','F_SEAL_SEAL','F_SEAL_WRITE','F_SEAL_GROW','F_SEAL_SHRINK')):
                stack.enter_context(patch.object(host.fcntl,name,1<<index,create=True))
            for name in ('_identities_check','_code_check','_dependencies_check','_path_chain'):
                stack.enter_context(patch.object(host,name,side_effect=lambda *a,_name=name,**k:self.events.append((_name,))))
            stack.enter_context(patch.object(host,'_protected_bytes',side_effect=self.protected))
            stack.enter_context(patch.object(host.os,'geteuid',return_value=0))
            yield
    @contextmanager
    def start_observations(self):
        with self.observations(),ExitStack() as stack:
            stack.enter_context(patch.object(host.LinuxHost,'_claim',side_effect=lambda a:self.events.append(('claim',))))
            stack.enter_context(patch.object(host.Path,'exists',new=lambda p:self.exists(p)))
            stack.enter_context(patch.object(host.Path,'is_symlink',return_value=False))
            stack.enter_context(patch.object(host,'_process',side_effect=self.process))
            stack.enter_context(patch.object(host,'_endpoint',side_effect=self.endpoint))
            stack.enter_context(patch.object(host.os,'memfd_create',return_value=91))
            stack.enter_context(patch.object(host,'_write_all',side_effect=lambda fd,raw:setattr(self,'payload',json.loads(raw))))
            stack.enter_context(patch.object(host.os,'lseek',return_value=0))
            stack.enter_context(patch.object(host.os,'close',return_value=None))
            stack.enter_context(patch.object(host.fcntl,'fcntl',return_value=0))
            stack.enter_context(patch.object(host.subprocess,'Popen',side_effect=self.popen))
            stack.enter_context(patch.object(host.LinuxHost,'_publish',side_effect=lambda a,p:setattr(self,'published',p)))
            yield
    def ticket(self,mutate=None):
        payload=dict(spec=self.controller.spec.model_dump(),layout=self.layout,private=self.private,host_pid=90000,host_started='DI_HOST')
        if mutate:mutate(payload)
        return writer._canonical(payload).encode()
    @contextmanager
    def descriptor_observations(self,raw,*,owner=0,seals=None):
        with ExitStack() as stack:
            for index,name in enumerate(('F_ADD_SEALS','F_GET_SEALS','F_SEAL_SEAL','F_SEAL_WRITE','F_SEAL_GROW','F_SEAL_SHRINK')):
                stack.enter_context(patch.object(host.fcntl,name,1<<index,create=True))
            required=host.fcntl.F_SEAL_SEAL|host.fcntl.F_SEAL_WRITE|host.fcntl.F_SEAL_GROW|host.fcntl.F_SEAL_SHRINK
            stack.enter_context(patch.object(host.os,'fstat',return_value=SimpleNamespace(st_uid=owner,st_mode=stat.S_IFREG|0o600,st_size=len(raw))))
            stack.enter_context(patch.object(host.os,'pread',return_value=raw))
            stack.enter_context(patch.object(host.os,'close',return_value=None))
            stack.enter_context(patch.object(host.fcntl,'fcntl',return_value=required if seals is None else seals))
            stack.enter_context(patch.object(host.os,'geteuid',return_value=self.layout['writer_uid']))
            stack.enter_context(patch.object(host.os,'getegid',return_value=self.layout['ipc_gid']))
            stack.enter_context(patch.object(host.os,'getgroups',return_value=[]))
            stack.enter_context(patch.object(host.os,'getppid',return_value=90000))
            stack.enter_context(patch.object(host,'_process',side_effect=self.process))
            for name in ('_imports_check','_identities_check','_code_check','_dependencies_check'):
                stack.enter_context(patch.object(host,name,return_value=None))
            yield


class Offline(TestCase):
    def setUp(self):
        self.guards=ExitStack();self.addCleanup(self.guards.close)
        def forbidden(*args,**kwargs):raise AssertionError('real PG/process/IPC/permission action forbidden in offline window')
        for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(subprocess,'Popen'),
                         (socket.socket,'bind'),(socket.socket,'connect'),(os,'chmod'),(os,'chown'),
                         (os,'fchmod'),(os,'fchown'),(os,'umask'),(os,'memfd_create')]:
            self.guards.enter_context(patch.object(obj,name,side_effect=forbidden))


class InstalledLaunchTests(Offline):
    def test_layout_is_separate_strict_schema_and_roundtrips_aliases(self):
        spec,_,layout,_,_=inputs();parsed=host._runtime_layout(layout)
        self.assertIs(type(parsed),host.InstalledRuntimeLayout);self.assertEqual(parsed.model_dump(by_alias=True),layout)
        with self.assertRaises(ValueError):host.RuntimeLayout.model_validate(layout)
        self.assertEqual(host.LinuxHost(spec,layout).layout.model_dump(by_alias=True),layout)
        for change in ({'schema_version':'unknown'},{'trial_root':layout['runtime_root']},{'creation_receipt_sha256':'a'*64},{'runtime_root':'/tmp/parkweave-trial-'+'c'*32},{'api_uid':0},{'writer_uid':layout['api_uid']}):
            with self.subTest(change=change),self.assertRaises(ValueError):host._runtime_layout({**layout,**change})
        class Unknown(host.InstalledRuntimeLayout):pass
        with self.assertRaises(Denied):host._runtime_layout(Unknown.model_validate(layout))
    def test_trial_and_installed_targets_cannot_be_interchanged(self):
        spec,_,layout,_,_=inputs()
        with self.assertRaises((Denied,ValueError)):host.launch_request(spec,layout)
        old,_,trial,_=legacy.adapter_inputs()
        with self.assertRaises(Denied):host.launch_request(old,host.InstalledRuntimeLayout.model_validate(layout))
        self.assertEqual(host.launch_request(old,trial)['action'],'START_BIND_OWNED_LINUX_RESTRICTED_TRIAL')
        with self.assertRaises(Denied):host.installed_launch_request(old,trial)
        for name in ('fixture_'+'a'*32,'postgres','template0','template1','bad name'):
            changed=deepcopy(spec);changed['policy']['database_name']=name
            with self.subTest(name=name),self.assertRaises(Denied):host.installed_launch_request(changed,layout)
    def test_installed_contract_requires_local_exact_installation_and_source_refs(self):
        spec,_,layout,_,_=inputs()
        for key,value in [('transport','WINDOWS_NATIVE'),('permission_strategy','NARROW_FUNCTIONS'),('protected_location','/workspace'),('policy_source_ref',''),('key_source_ref',''),('host_pin_source_ref',''),('object_owners',{}),('parent_lock_column',None),('api_uid',10005)]:
            changed=deepcopy(spec);changed[key]=value
            with self.subTest(key=key),self.assertRaises(Denied):host.installed_launch_request(changed,layout)
        for dbhost in ('10.0.0.1','/var/run/../postgresql','/var/run//postgresql'):
            changed=deepcopy(spec);changed['policy']['database_host']=dbhost
            with self.subTest(host=dbhost),self.assertRaises(Denied):host.installed_launch_request(changed,layout)
        changed=deepcopy(spec);changed['policy']['database_host']='/var/run/postgresql'
        self.assertEqual(host.installed_launch_request(changed,layout)['action'],'START_BIND_INSTALLED_SINGLE_RUN')
    def test_default_start_and_unissued_objects_refuse_before_private_reads(self):
        h=Harness()
        with patch.object(host,'_protected_bytes',side_effect=AssertionError('private read reached')):
            for reference in (None,True,{},'/wrong/path'):
                with self.subTest(reference=reference),self.assertRaises(Denied):h.controller.start(reference)
        copied=host._LiveApproval(h.controller,host._ISSUER,host.installed_launch_request(h.spec,h.layout))
        for fn,args in [(h.controller._claim,(copied,)),(h.controller._spawn,(copied,91)),(h.controller._publish,(copied,{}))]:
            with self.assertRaises(Denied):fn(*args)
    def test_pure_private_validation_does_not_create_ordinary_engine_authority(self):
        h=Harness();config,key,dsn,boot=runtime.validated_private_input(h.spec,h.private,h.layout['boot_id'])
        self.assertEqual(key,bytes.fromhex(h.private['key']));self.assertEqual(boot,h.layout['boot_id'])
        for extra in ({},{'store_factory':lambda:(_ for _ in ()).throw(AssertionError('store reached'))}):
            with self.assertRaises(Denied):runtime.RestrictedEngine(h.spec,h.private,boot,lambda:None,**extra)
        fake=host._RuntimeAuthorization(host._ISSUER,json.loads(h.ticket()))
        fake.permits_installed_engine=lambda *args:True
        with self.assertRaises(Denied):runtime.RestrictedEngine(h.spec,h.private,boot,fake.check)
    def test_unsupported_seal_runtime_refuses_before_private_read_or_descriptor_io(self):
        h=Harness()
        with patch.object(host,'_supported_linux_runtime',return_value=False),patch.object(host,'_protected_bytes',side_effect=AssertionError('private read')),patch.object(host.os,'fstat',side_effect=AssertionError('descriptor IO')):
            with self.assertRaises(Denied):h.controller.start(h.controller.layout.approval_path)
            with self.assertRaises(Denied):host.load_host_ticket(91)
    def test_signed_installation_record_still_is_data_without_live_issuance(self):
        h=Harness();payload=host.installed_receipt_payload(h.spec,h.layout)
        self.assertIsNone(host.verified_record(json.loads(h.receipt),KEY,payload))
        self.assertNotEqual(payload['action'],'ORIGINAL_NEW_OWNED_DATABASE')
        self.assertEqual(h.controller._owned,{})
        with self.assertRaises(Denied):runtime.RestrictedEngine(h.spec,h.private,h.layout['boot_id'],lambda:None)
    def test_protected_approval_checks_exact_installation_receipt_and_metadata(self):
        h=Harness()
        with h.observations():
            approval=h.controller._approve(h.controller.layout.approval_path)
        self.assertIs(approval,h.controller._live_approval)
        self.assertTrue(any(p==h.controller.layout.installation_path and private and expected==h.layout['installation_receipt_sha256'] for p,_,private,expected in h.reads))
        self.assertEqual({x[0] for x in h.events},{'_identities_check','_code_check','_dependencies_check'})
        self.assertFalse(any('creation-receipt' in p for p,*_ in h.reads))
    def test_wrong_signed_receipt_target_source_code_bootstrap_or_identity_refuses(self):
        for key in ('database_oid','system_identifier','policy_sha256','source_sha','source_files_sha256','private_bootstrap_sha256','api_uid','writer_uid'):
            h=Harness();record=json.loads(h.receipt);record['payload'][key]='SYNTHETIC_WRONG'
            h.receipt=signed(record['payload']);h.layout['installation_receipt_sha256']=sha256(h.receipt).hexdigest();h.controller=host.LinuxHost(h.spec,h.layout)
            with self.subTest(field=key),h.observations(),self.assertRaises(Denied):h.controller._approve(h.controller.layout.approval_path)
        h=Harness();record=json.loads(h.receipt);record['hmac_sha256']='0'*64;h.receipt=writer._canonical(record).encode();h.layout['installation_receipt_sha256']=sha256(h.receipt).hexdigest();h.controller=host.LinuxHost(h.spec,h.layout)
        with h.observations(),self.assertRaises(Denied):h.controller._approve(h.controller.layout.approval_path)
    def test_fresh_trial_receipt_cannot_replace_installed_receipt(self):
        h=Harness();h.receipt=signed(dict(action='ORIGINAL_NEW_OWNED_DATABASE',database_name=h.spec['policy']['database_name']))
        h.layout['installation_receipt_sha256']=sha256(h.receipt).hexdigest();h.controller=host.LinuxHost(h.spec,h.layout)
        with h.observations(),self.assertRaises(Denied):h.controller._approve(h.controller.layout.approval_path)
    def test_changed_protected_bytes_and_expired_policy_refuse_without_renewal(self):
        h=Harness();h.receipt+=b' '
        with h.observations(),self.assertRaises(Denied):h.controller._approve(h.controller.layout.approval_path)
        h=Harness();now=datetime.now(timezone.utc);h.spec['policy'].update(valid_from=(now-timedelta(hours=1)).isoformat(),valid_until=(now-timedelta(minutes=30)).isoformat());h.controller=host.LinuxHost(h.spec,h.layout)
        with h.observations(),patch.object(host,'_protected_bytes',side_effect=AssertionError('expired policy private read')),self.assertRaisesRegex(Denied,'original host policy interval required'):h.controller.start(h.controller.layout.approval_path)
    def test_metadata_refusal_precedes_engine_and_spawn(self):
        for name in ('_identities_check','_code_check','_dependencies_check'):
            h=Harness()
            with self.subTest(check=name),h.observations(),patch.object(host,name,side_effect=Denied('DI refused')),self.assertRaises(Denied):h.controller.start(h.controller.layout.approval_path)
            self.assertFalse(h.spawned)
    def test_sealed_descriptor_route_constructs_exact_engine_without_connection(self):
        h=Harness()
        with h.descriptor_observations(h.ticket()):engine,authority=host.load_host_ticket(91)
        self.assertTrue(authority.matches(engine));self.assertTrue(authority.matches_guard(engine._guard))
        self.assertEqual(engine.policy.model_dump(),writer.WriterPolicy.model_validate(h.spec['policy']).model_dump())
        self.assertEqual(engine._key,bytes.fromhex(h.private['key']));self.assertEqual(engine._dsn,h.private['writer_dsn'])
        self.assertFalse(engine._injected_store)
    def test_bad_descriptor_owner_seals_profile_and_fields_are_not_authority(self):
        h=Harness()
        for change in ({'owner':1},{'seals':0}):
            with self.subTest(change=change),h.descriptor_observations(h.ticket(),**change),self.assertRaises(Denied):host.load_host_ticket(91)
        for mutate in (lambda p:p.update(approved=True),lambda p:p['layout'].update(schema_version='UNKNOWN'),lambda p:p['layout'].update(runtime_root='/tmp/shared')):
            with h.descriptor_observations(h.ticket(mutate)),self.assertRaises((Denied,ValueError)):host.load_host_ticket(91)
    def test_issued_descriptor_cannot_be_reused_for_foreign_spec_boot_key_or_callback(self):
        h=Harness()
        with h.descriptor_observations(h.ticket()):_,authority=host.load_host_ticket(91)
        for kind in ('spec','boot','key','callback'):
            spec=deepcopy(h.spec);private=deepcopy(h.private);boot=h.layout['boot_id'];callback=authority.check
            if kind=='spec':spec['policy']['database_oid']+=1
            elif kind=='boot':boot=str(uuid4())
            elif kind=='key':private['key']='33'*32
            else:callback=lambda:authority.check()
            with self.subTest(kind=kind),self.assertRaises(Denied):runtime.RestrictedEngine(spec,private,boot,callback)
    def test_start_reuses_protected_host_and_keeps_private_values_out_of_argv(self):
        h=Harness()
        with h.start_observations():child,pin=h.controller.start(h.controller.layout.approval_path)
        self.assertIs(child,h.child);self.assertEqual(h.published['pin'],pin.model_dump())
        self.assertEqual(h.payload['layout'],h.layout);self.assertEqual(h.payload['private'],h.private)
        args=next(event[1] for event in h.events if event[0]=='Popen')
        self.assertEqual(args['user'],h.layout['writer_uid']);self.assertEqual(args['group'],h.layout['ipc_gid'])
        self.assertEqual(args['extra_groups'],[]);self.assertEqual(args['pass_fds'],(91,));self.assertEqual(args['args'][1:3],['-I','-S'])
        self.assertFalse(args['shell']);self.assertTrue(all(value not in json.dumps(args) for value in h.private.values()))
        self.assertEqual(h.published['policy'],writer.WriterPolicy.model_validate(h.spec['policy']).model_dump())
    def test_existing_outputs_are_not_adopted_overwritten_or_retried(self):
        h=Harness()
        with h.start_observations(),patch.object(host.Path,'exists',return_value=True),self.assertRaises(Denied):h.controller.start(h.controller.layout.approval_path)
        self.assertFalse(h.spawned);self.assertIsNone(h.published)
        with h.observations(),self.assertRaises(Denied):h.controller.start(h.controller.layout.approval_path)
        self.assertFalse(h.spawned)
    def test_publication_failure_stops_only_the_owned_child_and_preserves_error(self):
        h=Harness()
        with h.start_observations(),patch.object(host.LinuxHost,'_publish',side_effect=RuntimeError('DI publication failed')),self.assertRaisesRegex(RuntimeError,'DI publication failed'):h.controller.start(h.controller.layout.approval_path)
        self.assertEqual(h.child.signals,[signal.SIGTERM]);self.assertEqual(h.controller._owned,{})
        with self.assertRaises(Denied):h.controller.stop(Child())
    def test_restart_request_uses_new_root_boot_pin_but_keeps_original_policy_key_deadline(self):
        first=Harness();second=Harness('d');second.spec['policy']=deepcopy(first.spec['policy']);second.private=deepcopy(first.private)
        second.layout['private_bootstrap_sha256']=first.layout['private_bootstrap_sha256'];second.receipt=signed(host.installed_receipt_payload(second.spec,second.layout));second.layout['installation_receipt_sha256']=sha256(second.receipt).hexdigest();second.controller=host.LinuxHost(second.spec,second.layout);second.child=Child(90102)
        with first.start_observations():old_child,old=first.controller.start(first.controller.layout.approval_path)
        first.controller.stop(old_child)
        with second.start_observations():_,new=second.controller.start(second.controller.layout.approval_path)
        self.assertNotEqual(old.command_path,new.command_path);self.assertNotEqual(old.boot_id,new.boot_id);self.assertNotEqual(old.pid,new.pid)
        self.assertEqual(old.policy_sha256,new.policy_sha256);self.assertEqual(first.published['policy'],second.published['policy']);self.assertEqual(first.private,second.private)
        old_client=writer.WriterClient(None,first.spec['policy'],old.model_dump())
        with patch.object(writer,'_socket_stat',return_value=SimpleNamespace(st_dev=new.command_device,st_ino=new.command_inode,st_uid=new.uid)),patch.object(writer,'_pid_started',return_value='DI_CHANGED_INSTANCE'),self.assertRaises(Denied):old_client.rpc('VALIDATE')


class LegacyChecks(Offline):
    def test_original_prerequisites_with_declared_linux_capabilities(self):
        with patch.object(host,'_supported_linux_runtime',return_value=True),pytest.MonkeyPatch.context() as monkeypatch:legacy.test_prerequisites_do_not_read_secrets_connect_or_issue_launch_authority(monkeypatch)
    def test_original_launch_arguments(self):legacy.test_launch_arguments_have_explicit_identity_fixed_entry_and_no_private_values()
    def test_original_pin_observations(self):legacy.test_pin_is_bound_to_host_observations_and_endpoint_instance()
    def test_original_unknown_child_refusal(self):legacy.test_unknown_child_cannot_be_adopted_or_stopped()
    def test_original_expired_mac_only_verify(self):legacy.test_verify_is_mac_only_even_after_expiry_and_no_store_factory()
    def test_original_unissued_backend_and_store(self):
        with pytest.MonkeyPatch.context() as monkeypatch:legacy.test_unissued_default_backend_and_connection_are_closed_before_dependencies(monkeypatch)
    def test_original_fake_guard_and_instance_override(self):
        for provider in ('ducktyped','overridden_method'):
            with self.subTest(provider=provider),pytest.MonkeyPatch.context() as monkeypatch:legacy.test_default_store_cannot_accept_fake_live_guard_or_instance_override(monkeypatch,provider)


if __name__=='__main__':main(verbosity=2)
