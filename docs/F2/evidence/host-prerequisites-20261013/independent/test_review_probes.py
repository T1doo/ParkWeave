"""Independent pure counterexamples. No PG, process, socket, private reads or permissions."""
import json,stat,socket,subprocess,os
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest,psycopg
from parkweave import native_run_access_restricted_host as h
from parkweave.store import Denied

@pytest.fixture(autouse=True)
def prohibit_actions():
 def blocked(*a,**k):raise AssertionError('Independent audit forbids live action/private-content read')
 with ExitStack() as s:
  for obj,name in [(h,'_protected_bytes'),(psycopg,'connect'),(psycopg.Connection,'connect'),(subprocess,'Popen'),(socket.socket,'connect'),(socket.socket,'bind'),(os,'chmod'),(os,'chown'),(os,'fchmod'),(os,'fchown'),(os,'memfd_create')]:s.enter_context(patch.object(obj,name,blocked))
  yield

def layout():
 return h.RuntimeLayout.model_validate(dict(trial_root='/tmp/parkweave-trial-'+'1'*32,source_sha='2'*40,source_root='/opt/review/src',source_files={'/opt/review/src/parkweave/a.py':'3'*64},interpreter='/opt/review/env/bin/python',interpreter_sha256='4'*64,dependency_roots=['/opt/review/env'],import_paths=['/opt/review/env/lib'],api_uid=101,api_gid=102,writer_uid=103,ipc_gid=104,boot_id='11111111-1111-1111-1111-111111111111',private_bootstrap_sha256='5'*64,creation_receipt_sha256='6'*64))
def controller():
 c=object.__new__(h.LinuxHost);c._layout_json=layout().model_dump_json();c._live_approval=None;c._owned={};c._consumed=False;return c

def pass_metadata(s):
 s.enter_context(patch.object(os,'geteuid',return_value=0))
 for name in ['_identities_check','_source_metadata_check','_interpreter_metadata_check','_dependencies_check']:s.enter_context(patch.object(h,name,return_value=None))

def test_all_observations_pass_is_not_authority_and_does_not_mutate():
 c=controller();prior=dict(c.__dict__)
 with ExitStack() as s:
  pass_metadata(s);result=c.inspect_prerequisites()
  assert result['status']=='APPROVAL_REQUIRED' and c.__dict__==prior
  assert result['checks']['protected_approval_and_private_inputs']==result['checks']['database_and_business_acl']=='NOT_CHECKED'
  for operation in [lambda:c.start(),lambda:c._spawn(result,9),lambda:c._claim(result),lambda:c._publish(result,{})]:
   with pytest.raises(Denied):operation()
  assert result['actual_run']=='NOT_RUN' and not any(result[k] for k in ['can_start','installation_authorized','activation_enabled','production_connected'])

@pytest.mark.parametrize('uid,error,status',[(1000,None,'BLOCKED'),(0,RuntimeError,'UNKNOWN'),(0,PermissionError,'BLOCKED'),(1000,RuntimeError,'BLOCKED')])
def test_precedence_and_exception_redaction(uid,error,status):
 with ExitStack() as s:
  pass_metadata(s);s.enter_context(patch.object(os,'geteuid',return_value=uid))
  if error:s.enter_context(patch.object(h,'_source_metadata_check',side_effect=error('PRIVATE_MARKER_MUST_NOT_BE_EMITTED')))
  result=controller().inspect_prerequisites();assert result['status']==status and not result['can_start'] and 'PRIVATE_MARKER' not in json.dumps(result)

@pytest.mark.parametrize('which',['interpreter','source'])
def test_metadata_pass_cannot_bypass_content_hash(which):
 l=layout();calls=[]
 def content(path,owner,**kw):
  calls.append((path,kw['expected']))
  if (path==l.interpreter)==(which=='interpreter'):raise Denied('hash mismatch')
 with patch.object(h,'_source_metadata_check',return_value=None),patch.object(h,'_protected_bytes',side_effect=content):
  with pytest.raises(Denied):h._code_check(l)
 assert calls[0]==(l.interpreter,l.interpreter_sha256)
 if which=='source':assert calls[1]==next(iter(l.source_files.items()))

@pytest.mark.parametrize('mutation',['extra','missing','symlink','writable'])
def test_source_names_and_modes_fail_closed_without_content(mutation):
 l=layout();root=Path(l.source_root+'/parkweave');a=Path(next(iter(l.source_files)));files=[] if mutation=='missing' else [a]
 if mutation=='extra':files.append(root/'extra.py')
 def metadata(p):
  mode=stat.S_IFDIR|0o755 if p==root else stat.S_IFREG|0o644
  if p==a and mutation=='symlink':mode=stat.S_IFLNK|0o777
  if p==a and mutation=='writable':mode|=0o020
  return SimpleNamespace(st_uid=0,st_mode=mode)
 with patch.object(h,'_path_chain',return_value=None),patch.object(Path,'rglob',return_value=iter(files)),patch.object(Path,'lstat',metadata):
  with pytest.raises(Denied):h._source_metadata_check(l)
