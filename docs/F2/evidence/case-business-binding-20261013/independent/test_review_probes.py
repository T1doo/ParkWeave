"""Independent bounded declaration probes; never issue live authority."""
from contextlib import ExitStack
from copy import deepcopy
import os,socket,subprocess
import pytest,psycopg
from psycopg.conninfo import make_conninfo
from parkweave.case_cancellation_business_binding import BusinessBinding,required_privileges
from parkweave.store import Denied,Store
from test_native_run_access_restricted_adapter import adapter_inputs

@pytest.fixture(autouse=True)
def forbid_actions():
 from unittest.mock import patch
 def blocked(*a,**k):raise AssertionError('Independent declaration audit forbids live actions')
 with ExitStack() as s:
  for obj,name in [(psycopg,'connect'),(psycopg.Connection,'connect'),(Store,'connect'),(subprocess,'Popen'),(socket.socket,'connect'),(socket.socket,'bind'),(os,'chown'),(os,'chmod'),(os,'memfd_create')]:s.enter_context(patch.object(obj,name,blocked))
  yield

def inputs():
 spec,_,_,_=adapter_inputs();root='/tmp/parkweave-trial-'+'c'*32
 spec['protected_location']=root;spec['policy']['database_host']=root+'/pg/socket'
 return spec,BusinessBinding.from_spec(spec,business_role='review_case',trial_root=root)

@pytest.mark.parametrize('role',['application_role','writer_role','installer_role'])
def test_four_role_collision_closed(role):
 spec,b=inputs();r=spec['installer_role'] if role=='installer_role' else spec['policy'][role]
 with pytest.raises(ValueError):BusinessBinding.from_spec(spec,business_role=r,trial_root=b.trial_root)

@pytest.mark.parametrize('field',['review_sha256','input_fingerprint','run_revision','park_id','org_id'])
def test_whole_source_pin_not_just_case_identifiers(field):
 spec,b=inputs();v=spec['policy']['source'][field];spec['policy']['source'][field]=v+1 if isinstance(v,int) else 'e'*64 if 'sha' in field or field=='input_fingerprint' else 'different'
 with pytest.raises((Denied,ValueError)):b.check_spec(spec)

def test_role_declaration_has_no_secret_retention_or_authority():
 spec,b=inputs();prior=b.model_dump_json();p='PRIVATE_PROBE_ONLY_NOT_A_REAL_CREDENTIAL'
 d=make_conninfo(host=b.database_host,port=b.database_port,dbname=b.database_name,user=b.business_role,password=p)
 assert b.check_private_dsn(d) is None and b.model_dump_json()==prior and p not in prior
 result=b.observation();assert result['actual_run']=='NOT_RUN' and result['status']=='DECLARATION_VALIDATED_ONLY'
 assert not any(v for k,v in result.items() if k not in ['status','actual_run'])
 for value in [d+' sslmode=disable',d+' connect_timeout=3',{},True]:
  with pytest.raises(Denied) as e:b.check_private_dsn(value)
  assert p not in str(e.value)

def test_no_unrequested_native_or_identity_mutation_and_deep_fresh_rows():
 rows=required_privileges();assert len(rows)==22
 writes=[x for x in rows if x['action']!='SELECT'];assert len(writes)==7
 assert {x['table'] for x in writes}=={'preparations','service_dispatches','cases','case_local_lifecycles','case_local_events','authorization_audit'}
 original=deepcopy(rows);rows[-1]['columns'].append('forbidden');rows[0]['table']='forbidden';assert required_privileges()==original

def test_original_request_is_not_rewritten_or_claimed_committed():
 _,b=inputs();request=dict(case_id=b.source.case_id,expected_preparation_revision=b.source.preparation_revision,expected_lifecycle_revision=0,expected_source_sha256='a'*64,confirm_cancel=True,reason='explicit independent synthetic request')
 prior=deepcopy(request);assert b.check_cancel_request(b.source.preparation_id,request) is None and prior==request
 assert b.observation()['actual_run']=='NOT_RUN'
 # Lifecycle/source proof remains for original cc.cancel; pure binding must not synthesize it.
 assert b.check_cancel_request(b.source.preparation_id,{**request,'expected_source_sha256':'b'*64,'expected_lifecycle_revision':1}) is None
