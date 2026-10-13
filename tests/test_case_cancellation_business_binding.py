"""Offline declarations and private-input comparisons; never connect or grant."""
from copy import deepcopy
import json
import os
import socket
import subprocess
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from parkweave.case_cancellation_business_binding import BusinessBinding, required_privileges
from parkweave.store import Denied, Store
from test_native_run_access_restricted_adapter import adapter_inputs

ROOT='/tmp/parkweave-trial-'+'b'*32


@pytest.fixture(autouse=True)
def no_actions(monkeypatch):
    def fail(*a,**kw):pytest.fail('offline binding attempted real connection/OS action')
    for obj,name in ((psycopg,'connect'),(psycopg.Connection,'connect'),(Store,'connect'),
        (subprocess,'Popen'),(socket.socket,'connect'),(socket.socket,'bind'),
        (os,'chown'),(os,'chmod'),(os,'memfd_create')):
        monkeypatch.setattr(obj,name,fail)


def inputs():
    spec,_,_,_=adapter_inputs();spec['protected_location']=ROOT
    spec['policy']['database_host']=ROOT+'/pg/socket'
    binding=BusinessBinding.from_spec(spec,business_role='pwci_case',trial_root=ROOT)
    return spec,binding


def dsn(binding,**change):
    fields=dict(host=binding.database_host,port=binding.database_port,dbname=binding.database_name,
        user=binding.business_role,password='SYNTHETIC_PRIVATE_NOT_REAL')
    fields.update(change);return make_conninfo(**fields)


def test_declaration_binds_spec_and_routes_without_live_authority():
    spec,b=inputs();b.check_spec(spec)
    assert b.check_private_dsn(dsn(b)) is None
    assert b.read_path()=='/api/preparations/'+b.source.preparation_id+'/case-cancellation'
    assert b.recovery_path('original-key')==b.read_path()+'/recovery/original-key'
    result=b.observation();assert result['status']=='DECLARATION_VALIDATED_ONLY' and result['actual_run']=='NOT_RUN'
    assert not any(v for k,v in result.items() if k not in ('status','actual_run'))
    assert 'dsn' not in b.model_dump() and 'SYNTHETIC_PRIVATE_NOT_REAL' not in b.model_dump_json()


@pytest.mark.parametrize('role',['application_role','writer_role'])
def test_native_connection_roles_cannot_be_used_as_business_role(role):
    spec,_=inputs()
    with pytest.raises(ValueError):BusinessBinding.from_spec(spec,business_role=spec['policy'][role],trial_root=ROOT)


def test_owner_connection_role_cannot_be_used_as_business_role():
    spec,_=inputs()
    with pytest.raises(ValueError):BusinessBinding.from_spec(spec,business_role=spec['installer_role'],trial_root=ROOT)


@pytest.mark.parametrize('field',['database_name','database_oid','system_identifier','application_role','writer_role','valid_until'])
def test_any_installation_pin_change_requires_explicit_rebind(field):
    spec,b=inputs()
    if field=='database_oid':spec['policy'][field]+=1
    elif field=='database_name':spec['policy'][field]='fixture_'+uuid4().hex
    elif field=='valid_until':spec['policy'][field]=spec['policy'][field].replace('+00:00','+01:00')
    else:spec['policy'][field]+='1'
    with pytest.raises((Denied,ValueError)):b.check_spec(spec)


@pytest.mark.parametrize('field',['run_id','case_id','preparation_id','material_sha256','preparation_revision','owner_id'])
def test_other_case_or_material_source_cannot_reuse_binding(field):
    spec,b=inputs()
    spec['policy']['source'][field]=spec['policy']['source'][field]+1 if field=='preparation_revision' else '1'*64 if field=='material_sha256' else str(uuid4()) if field.endswith('_id') and field!='owner_id' else 'another-owner'
    with pytest.raises((Denied,ValueError)):b.check_spec(spec)


@pytest.mark.parametrize('change',[{'user':'synthetic_installer'},{'user':'synthetic_writer'},
    {'dbname':'postgres'},{'host':'127.0.0.1'},{'host':ROOT+'/pg/socket,other'},{'port':1},
    {'service':'SYNTHETIC_PRIVATE_NOT_REAL'},{'options':'SYNTHETIC_PRIVATE_NOT_REAL'},
    {'passfile':'SYNTHETIC_PRIVATE_NOT_REAL'},{'password':''}])
def test_private_input_rejects_role_or_discovery_overrides_without_echo(change):
    _,b=inputs()
    with pytest.raises(Denied) as e:b.check_private_dsn(dsn(b,**change))
    assert 'SYNTHETIC_PRIVATE_NOT_REAL' not in str(e.value)


@pytest.mark.parametrize('key',['',None,1,'../private','key/another','x'*101])
def test_recovery_requires_original_bounded_key(key):
    _,b=inputs()
    with pytest.raises(Denied):b.recovery_path(key)


def test_explicit_request_is_checked_without_auto_source_or_reason_rewrite():
    _,b=inputs();request=dict(case_id=b.source.case_id,expected_preparation_revision=b.source.preparation_revision,
        expected_lifecycle_revision=0,expected_source_sha256='a'*64,confirm_cancel=True,reason='SYNTHETIC explicit owner cancellation')
    original=deepcopy(request);assert b.check_cancel_request(b.source.preparation_id,request) is None;assert request==original
    for field,value in [('case_id',str(uuid4())),('expected_preparation_revision',b.source.preparation_revision+1),('confirm_cancel',False)]:
        with pytest.raises((Denied,ValueError)):b.check_cancel_request(b.source.preparation_id,{**request,field:value})
    with pytest.raises(Denied):b.check_cancel_request(uuid4(),request)


def test_minimum_writes_never_touch_native_or_identity_objects_and_rows_are_fresh():
    rows=required_privileges();writes={r['table']:r for r in rows if r['action']=='UPDATE'}
    assert writes['preparations']['columns']==['revision'] and writes['service_dispatches']['columns']==['revision']
    assert writes['cases']['columns']==['state']
    assert writes['case_local_lifecycles']['columns']==['revision','state','verified_snapshot','verified_sha256']
    assert all(r['table'] not in ('runs','run_assignments','principals','capability_grants','preparation_grants') for r in rows if r['action']!='SELECT')
    assert all(r['action'] in ('SELECT','INSERT','UPDATE') for r in rows)
    rows[0]['table']='mutated';assert required_privileges()[0]['table']=='principals'
    assert not any(r['action']=='UPDATE' and r['table']=='case_local_events' for r in required_privileges())
