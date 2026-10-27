"""Actual owned Unix IPC/PG; production OS protection positives are explicit DI."""
from dataclasses import replace
import base64
import json
import os
from pathlib import Path
import socket
import time
from uuid import UUID,uuid4

from fastapi.testclient import TestClient
import pytest

from parkweave import resource_approval_host_read as host
from parkweave import resource_plan_approval_read as approval
from parkweave.api import configured_app
from parkweave.store import Denied
from resource_approval_host_support import running_host,fixture_binding
from resource_approval_read_support import seeded,read,path
from test_executor_receipts import receipt_fixture
from test_ordinary_runtime_read import snapshot
from test_preparation import preparation_fixture,headers


def lookup():
    ids={k:uuid4() for k in ('preparation_id','case_id','run_id','plan_id')}
    return approval.Lookup(approval.Scope(**ids,plan_revision=1,preparation_revision=1,
        owner_id='SYNTHETIC-owner',park_id='park-a',org_id='org-a',
        **{k:'a'*64 for k in ('plan_definition_sha256','action_scope_sha256','source_sha256','authority_sha256','database_binding_sha256')}),'SYNTHETIC-viewer')


def test_actual_unix_protocol_read_verify_and_fixed_original_id(tmp_path,monkeypatch):
    with running_host(tmp_path/'host') as (cfg,binding,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding)
        provider=host.configure(cfg.model_dump_json());selection=lookup()
        with provider.read_window():
            raw=provider.read_existing(selection)
            assert provider.verify_existing(replace(selection,approval_id=uuid4()),raw) is True
        assert raw==b'{"SYNTHETIC":"existing raw bytes"}'
        assert provider.source_kind=='SYNTHETIC_CONTRACT_FIXTURE'
        rows=[json.loads(x) for x in (tmp_path/'host/calls.jsonl').read_text().splitlines()]
        assert [x['operation'] for x in rows]==['READ_EXISTING','VERIFY_EXISTING']
        assert rows[0]['approval_id'] is None and rows[1]['approval_id'] is not None
        with pytest.raises(Denied,match='read window'):provider.read_existing(selection)


@pytest.mark.parametrize('damage',['nonce','request','pin','source','integer','duplicate','truncated','oversize'])
def test_actual_bad_response_is_not_a_source_proof_or_retry(tmp_path,monkeypatch,damage):
    with running_host(tmp_path/'host',mode=damage) as (cfg,_,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding);provider=host.configure(cfg.model_dump_json())
        with provider.read_window(),pytest.raises(Denied):provider.read_existing(lookup())
        rows=(tmp_path/'host/calls.jsonl').read_text().splitlines();assert len(rows)==1


def test_slowloris_uses_absolute_total_deadline_not_timeout_per_byte(tmp_path,monkeypatch):
    with running_host(tmp_path/'host',mode='slowloris') as (cfg,_,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding);provider=host.configure(cfg.model_dump_json())
        started=time.monotonic()
        with provider.read_window(),pytest.raises(Denied):provider.read_existing(lookup())
        assert 1.5<time.monotonic()-started<3


@pytest.mark.parametrize('damage',['missing','same-uid','fixture-kind','sha','symlink','mode','path-parent'])
def test_unmodified_production_binding_loader_refuses_fixture_or_unsafe_installation(tmp_path,damage):
    with running_host(tmp_path/'host') as (cfg,binding,_):
        value=binding.model_dump()
        if damage=='same-uid':value['source_kind']='EXISTING_AUTHORITY_ADAPTER'
        elif damage=='fixture-kind':pass
        elif damage=='sha':cfg=cfg.model_copy(update={'binding_sha256':'0'*64})
        elif damage=='missing':cfg=cfg.model_copy(update={'binding_path':str(tmp_path/'absent')})
        elif damage=='mode':Path(cfg.binding_path).chmod(0o666)
        elif damage=='symlink':
            link=tmp_path/'link';link.symlink_to(cfg.binding_path);cfg=cfg.model_copy(update={'binding_path':str(link)})
        elif damage=='path-parent':
            tmp_path.chmod(0o777)
        if damage=='same-uid':
            raw=host._canonical(value);Path(cfg.binding_path).write_bytes(raw);cfg=cfg.model_copy(update={'binding_sha256':host._sha(raw)})
        with pytest.raises(Denied,match='values not echoed'):host.configure(cfg.model_dump_json())
        assert not (tmp_path/'host/calls.jsonl').exists()


@pytest.mark.parametrize('damage',['extra','duplicate','relative','empty','json','boolean-sha','module-loader'])
def test_bad_config_or_ambiguous_provider_never_loads_host(monkeypatch,damage):
    value=dict(schema_version=host.PROTOCOL,binding_path='/existing/public.json',binding_sha256='a'*64)
    if damage=='extra':value['verified']=True
    elif damage=='relative':value['binding_path']='relative.json'
    elif damage=='boolean-sha':value['binding_sha256']=True
    elif damage=='module-loader':value['module']='untrusted.module'
    raw=json.dumps(value)
    if damage=='duplicate':raw=raw[:-1]+',"binding_sha256":"'+'b'*64+'"}'
    elif damage=='empty':raw=''
    elif damage=='json':raw='['
    monkeypatch.setattr(host,'_load_binding',lambda x:pytest.fail('invalid configuration reached host'))
    with pytest.raises(Denied,match='values not echoed'):host.configure(raw)
    with pytest.raises(Denied,match='one explicit'):host.configure(raw,object())
    marker=object();assert host.configure(None,marker) is marker


@pytest.mark.parametrize('operation',['COMMAND','ACTIVATE','APPROVE','CONSUME','READ_URL','VERIFY'])
def test_host_refuses_non_read_protocol_before_backend(tmp_path,operation):
    with running_host(tmp_path/'host') as (cfg,binding,_):
        calls=[];provider=approval.ReadOnlyApprovalProvider(binding.source_id,lambda x:calls.append(x),lambda x,y:calls.append(x),binding.source_kind)
        dispatcher=host.ReadOnlyDispatcher(provider,binding,cfg.binding_sha256)
        value=dict(protocol=host.PROTOCOL,operation=operation,nonce='a'*32,binding_sha256=cfg.binding_sha256,
            source_id=binding.source_id,backend_contract_id=binding.backend_contract_id,
            lookup=host.WireLookup(scope=lookup().scope,viewer_id='SYNTHETIC-viewer').model_dump(mode='json'))
        with pytest.raises(ValueError):dispatcher.dispatch(host._canonical(value))
        assert calls==[]


@pytest.mark.parametrize('mode,expected',[('normal','VERIFIED'),('replace','INVALID'),('final_false','INVALID'),('slow','MISSING_SOURCE')])
def test_factory_config_real_ipc_reuses_existing_double_read_and_final_source_check(receipt_fixture,tmp_path,monkeypatch,mode,expected):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch)
    with running_host(tmp_path/'host',source,mode) as (cfg,_,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding)
        monkeypatch.setenv('PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG',cfg.model_dump_json())
        app=configured_app();before=snapshot(f[1]);started=time.monotonic()
        with TestClient(app) as api:
            result=read(api,f,p,query);assert result.status_code==200,result.text;x=result.json()
            assert x['state']==expected
            for key in ('execution_authorized','approval_consumable','decision_writes_enabled','run_read_access_granted'):assert x[key] is False
            if mode=='normal':
                assert x['approval_source_kind']=='SYNTHETIC_CONTRACT_FIXTURE' and not x['production_installation_verified']
                assert x['record']['approval_id']==source.record()['approval_id']
            if mode=='slow':assert time.monotonic()-started<3
        assert snapshot(f[1])==before
        calls=[json.loads(x) for x in (tmp_path/'host/calls.jsonl').read_text().splitlines()]
        if mode in ('normal','final_false'):
            assert [x['operation'] for x in calls]==['READ_EXISTING','VERIFY_EXISTING','READ_EXISTING','VERIFY_EXISTING','VERIFY_EXISTING']
            assert all(x['approval_id'] is None for x in calls[:2])
            assert all(x['approval_id']==source.record()['approval_id'] for x in calls[2:])


def test_current_revocation_precedes_any_host_call_and_isolated_never_substitutes(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch)
    with running_host(tmp_path/'host',source) as (cfg,_,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding);monkeypatch.setenv('PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG',cfg.model_dump_json());app=configured_app()
        with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        before=snapshot(f[1])
        with TestClient(app) as api:
            assert read(api,f,p,query).status_code==403
            assert api.post(path(p),headers=headers(f[2]),json={'APPROVED':True}).status_code==405
        assert not (tmp_path/'host/calls.jsonl').exists() and snapshot(f[1])==before


@pytest.mark.parametrize('damage',['peer','started','boot','inode'])
def test_real_instance_or_peer_mismatch_never_reaches_source(tmp_path,monkeypatch,damage):
    with running_host(tmp_path/'host') as (cfg,binding,_):
        replacement=None
        if damage=='inode':
            Path(binding.socket_path).rename(tmp_path/'host/original.sock')
            replacement=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);replacement.bind(binding.socket_path)
            os.chmod(binding.socket_path,0o660);replacement.listen(1)
        else:
            value=binding.model_dump()
            if damage=='peer':
                from parkweave.native_run_access_writer import _pid_started
                value.update(host_pid=os.getpid(),host_started=str(_pid_started(os.getpid())))
            elif damage=='started':value['host_started']='0'
            else:value['boot_id']='00000000-0000-0000-0000-000000000000'
            raw=host._canonical(value);Path(cfg.binding_path).write_bytes(raw);cfg=cfg.model_copy(update={'binding_sha256':host._sha(raw)})
        monkeypatch.setattr(host,'_load_binding',fixture_binding)
        try:
            if damage in ('inode','started','boot'):
                with pytest.raises(Denied):host.configure(cfg.model_dump_json())
            else:
                provider=host.configure(cfg.model_dump_json())
                with provider.read_window(),pytest.raises(Denied,match='peer'):provider.read_existing(lookup())
            assert not (tmp_path/'host/calls.jsonl').exists()
        finally:
            if replacement:replacement.close()


def test_last_post_response_pin_check_cannot_overrun_budget_and_return_true(tmp_path,monkeypatch):
    with running_host(tmp_path/'host') as (cfg,_,_):
        calls=[]
        def load(value):
            binding=fixture_binding(value);calls.append(1)
            if len(calls)==3:time.sleep(2.05)  # Final VERIFY reply already arrived.
            return binding
        monkeypatch.setattr(host,'_load_binding',load);provider=host.configure(cfg.model_dump_json())
        with provider.read_window(),pytest.raises(Denied,match='budget exhausted'):
            provider.verify_existing(lookup(),b'SYNTHETIC raw')
        assert len((tmp_path/'host/calls.jsonl').read_text().splitlines())==1


def test_concurrent_read_windows_do_not_share_or_renew_deadline(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    with running_host(tmp_path/'host') as (cfg,_,_):
        monkeypatch.setattr(host,'_load_binding',fixture_binding);provider=host.configure(cfg.model_dump_json())
        def once(_):
            with provider.read_window():
                with pytest.raises(Denied,match='nested'):
                    with provider.read_window():pass
                return provider.read_existing(lookup())
        with ThreadPoolExecutor(2) as pool:assert len(set(pool.map(once,range(2))))==1
        with pytest.raises(Denied,match='read window'):provider.read_existing(lookup())


@pytest.mark.parametrize('damage',['extra','duplicate','pin','source','raw-sha','boolean-revision'])
def test_dispatcher_bad_selection_or_bytes_are_refused_before_backend(tmp_path,damage):
    with running_host(tmp_path/'host') as (cfg,binding,_):
        calls=[];provider=approval.ReadOnlyApprovalProvider(binding.source_id,lambda x:calls.append(x),lambda x,y:calls.append(x),binding.source_kind)
        dispatcher=host.ReadOnlyDispatcher(provider,binding,cfg.binding_sha256)
        value=dict(protocol=host.PROTOCOL,operation='VERIFY_EXISTING',nonce='a'*32,binding_sha256=cfg.binding_sha256,
            source_id=binding.source_id,backend_contract_id=binding.backend_contract_id,
            lookup=host.WireLookup(scope=lookup().scope,viewer_id='SYNTHETIC-viewer').model_dump(mode='json'),
            raw_base64=base64.b64encode(b'SYNTHETIC').decode(),raw_sha256=host._sha(b'SYNTHETIC'))
        if damage=='extra':value['url']='https://untrusted.invalid/'
        elif damage=='pin':value['binding_sha256']='0'*64
        elif damage=='source':value['source_id']='other'
        elif damage=='raw-sha':value['raw_sha256']='0'*64
        elif damage=='boolean-revision':value['lookup']['scope']['plan_revision']=True
        raw=host._canonical(value)
        if damage=='duplicate':raw=raw[:-1]+b',"operation":"READ_EXISTING"}'
        if damage=='raw-sha':assert host.strict_json(dispatcher.dispatch(raw))['error']=='SOURCE_UNAVAILABLE'
        else:
            with pytest.raises((ValueError,Denied)):dispatcher.dispatch(raw)
        assert calls==[]


@pytest.mark.parametrize('damage',['fixture','same-uid','root-api','root-host','foreign-api','ipc-group'])
def test_identity_rejection_branches_with_only_protected_file_read_di(tmp_path,monkeypatch,damage):
    # These are rejected numeric claims, not newly created OS identities.
    with running_host(tmp_path/'host') as (cfg,binding,_):
        value=binding.model_dump();value.update(source_kind='EXISTING_AUTHORITY_ADAPTER',host_uid=os.geteuid()+1)
        if damage=='fixture':value['source_kind']='SYNTHETIC_CONTRACT_FIXTURE'
        elif damage=='same-uid':value['host_uid']=value['api_uid']
        elif damage=='root-api':value['api_uid']=0
        elif damage=='root-host':value['host_uid']=0
        elif damage=='foreign-api':value['api_uid']+=1
        else:value['host_gid']=max([os.getegid(),*os.getgroups()])+100000
        from parkweave import native_run_access_restricted_host as protected
        monkeypatch.setattr(protected,'_protected_bytes',lambda *a,**k:host._canonical(value))
        monkeypatch.setattr(host,'_endpoint',lambda *a:pytest.fail('invalid identity reached endpoint'))
        with pytest.raises(Denied,match='distinct restricted'):host._load_binding(cfg)
