"""Independent two API PID, live issuer, closed framing and failure oracles."""
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import json,socket,struct,sqlite3
import pytest
import test_receipt_history_recovery as helper
from parkweave import receipt_history_recovery as h,isolated_execution_preview as ep,preparation as prep
from parkweave.store import Store
PRIVATE=Path('/workspace/ParkWeave/.runtime/independent-p4-history-api-recovery-rereview')
helper.OUT=PRIVATE/'independent-cases'
# Private issuer observer wraps actual original generation before first HTTP
# execute, so every subsequent recovery is independently proven generation-free.
helper.ISSUER=helper.ISSUER.replace("BASE=Path(os.environ['PARKWEAVE_HISTORY_TEST_DIR'])", "from parkweave import isolated_local_execution as original_local\n_GENERATION_CALLS=[]\n_GENERATE=original_local.IsolatedLocalExecutor.generate\ndef observed_generate(*args,**kwargs):\n _GENERATION_CALLS.append(1)\n return _GENERATE(*args,**kwargs)\noriginal_local.IsolatedLocalExecutor.generate=observed_generate\nBASE=Path(os.environ['PARKWEAVE_HISTORY_TEST_DIR'])")
helper.ISSUER=helper.ISSUER.replace("  original=r.json()['result']", "  original=r.json()['result']\n  assert len(_GENERATION_CALLS)==1")
helper.ISSUER=helper.ISSUER.replace(" private('closed.json',dict(issuer_pid=os.getpid(),authority_closed=True,", " assert len(_GENERATION_CALLS)==1,'READ triggered forbidden original generation'\n private('closed.json',dict(generation_calls=len(_GENERATION_CALLS),issuer_pid=os.getpid(),authority_closed=True,")
issuer=helper.issuer
api_process=helper.api_process
get=helper.get
business=helper.business
bytes_all=helper.bytes_all
schema=helper.schema
note=helper.note

@pytest.mark.parametrize('issuer',['ACKNOWLEDGE','REQUEST_CHANGES'],indirect=True)
def test_independent_old_api_gone_new_api_source_stale_no_execute(issuer):
 base,d,authority,case=issuer;original_bytes=bytes_all(d);before=business(d);original_schema=schema(d)
 with api_process(issuer) as (client,old,port,network):
  q=get(client,d,d['key']);assert q.status_code==200 and q.json()['result']==d['result'];oldpid=old.pid
 assert not Path('/proc',str(oldpid)).exists() and authority.poll() is None and authority.pid!=oldpid
 p=d['preparation'];prep.command(Store(d['app_dsn']),d['tokens']['fixture-a'],p['preparation_id'],uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',text='SYNTHETIC independent later original material',source_kind='USER_STATEMENT',source_label='SYNTHETIC independent version2'))
 changed=business(d)
 with api_process(issuer,port) as (client,new,_,network):
  assert len({new.pid,oldpid,authority.pid})==3
  with ThreadPoolExecutor(3) as pool:responses=list(pool.map(lambda _:get(client,d,d['key']),range(6)))
  assert all(q.status_code==200 and q.json()['result']==d['result'] and q.json()['history'][0]['source_state']=='STALE' and q.json()['read_only'] is True and q.json()['automatically_replayed'] is False for q in responses)
  unknown=get(client,d,'independent-never-sent');assert unknown.status_code==200 and unknown.json()['status']=='NOT_OBSERVED' and unknown.json()['automatically_replayed'] is False
  path='/api/preparations/'+p['preparation_id'];auth={'Authorization':'Bearer '+d['tokens']['fixture-a'],'Idempotency-Key':'ind-no-replay'}
  assert client.post(path+'/receipt-execution-history',headers=auth,json={}).status_code==405
  assert client.get(path+'/receipt-execution-preview/recovery/'+d['key'],headers=auth).status_code==403
  assert client.post(path+'/receipt-execution-preview',headers=auth,json={'expected_preparation_revision':1,'expected_request_revision':1,'expected_source_sha256':'0'*64}).status_code==403
  assert authority.poll() is None
 assert bytes_all(d)==original_bytes and business(d)==changed and schema(d)==original_schema
 note(case,'independent-two-pid',dict(original_actual_http_generate=1,issuer_pid=authority.pid,old_api_pid=oldpid,new_api_pid=new.pid,old_confirmed_gone_before_new=True,issuer_alive_and_three_different_pids=True,api_proof_registries_empty=True,original_decision=d['result']['review_decision'],concurrent_get=6,exact_original_result=True,source_state='STALE',unknown_key='NOT_OBSERVED',history_post=405,original_p4_get_and_post=403,five_log_bytes_unchanged=True,formal_business_after_explicit_source_action_and_schema_privileges_unchanged=True,source_atomicity=False))


def test_independent_malformed_and_exact_binding_closed_frames_no_write(issuer):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d);store=Store(d['app_dsn']);client=h.ReceiptHistoryClient(store,base/'history.sock',authority_pid=authority.pid,authority_generation=d['generation'],namespace=d['namespace'],enabled_for_isolated_tests=True)
 request=dict(version=1,operation='READ',preparation=d['preparation']['preparation_id'],key=d['key'],token=d['tokens']['fixture-a'],binding=client.binding)
 messages=[{**request,'version':True},{**request,'version':1.0},{**request,'operation':'READ','binding':{**client.binding,'history_contract':'0'*64}},{**request,'binding':{**client.binding,'database':{}}},{**request,'key':'x'*129},{**request,'token':''},{**request,'sql':'SELECT 1'}]
 for message in messages:
  with socket.socket(socket.AF_UNIX) as conn:
   conn.settimeout(3);conn.connect(str(base/'history.sock'));h._send(conn,message,h.REQUEST_LIMIT);assert h._receive(conn,h.RESPONSE_LIMIT)=={'status':403}
 for raw in (struct.pack('!I',0),struct.pack('!I',h.REQUEST_LIMIT+1),struct.pack('!I',1)+b'\xff'):
  with socket.socket(socket.AF_UNIX) as conn:
   conn.settimeout(3);conn.connect(str(base/'history.sock'));conn.sendall(raw);assert h._receive(conn,h.RESPONSE_LIMIT)=={'status':403}
 with api_process(issuer) as (api,_,_,_):assert get(api,d,d['key']).status_code==200
 assert bytes_all(d)==saved and business(d)==before
 note(case,'independent-frames',dict(closed_message_rejections=7,zero_oversize_invalid_utf8_frame_rejections=3,status=403,valid_read_after_fault=200,no_data_or_exception_text_in_error=True,five_log_bytes_and_formal_business_unchanged=True))


def test_independent_socket_disappearance_and_replacement_refused_without_rebind(issuer):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d);path=base/'history.sock';backup=base/'same-original-socket'
 with api_process(issuer) as (client,api,_,_):
  assert get(client,d,d['key']).status_code==200;path.rename(backup)
  try:
   q=get(client,d,d['key']);assert q.status_code==503 and 'history' not in q.json() and 'result' not in q.json()
   with socket.socket(socket.AF_UNIX) as other:
    other.bind(str(path));path.chmod(0o600);other.listen(1);q=get(client,d,d['key']);assert q.status_code==403 and 'history' not in q.json() and 'result' not in q.json()
   path.unlink()
  finally:
   if path.exists():path.unlink()
   backup.rename(path)
  # Restore precisely the original same inode/listener, not a restarted authority.
  assert get(client,d,d['key']).status_code==200 and authority.poll() is None
 assert bytes_all(d)==saved and business(d)==before
 note(case,'independent-socket',dict(issuer_continuously_alive=True,missing_socket_status=503,different_socket_inode_status=403,restored_original_same_inode_status=200,authority_or_proof_rebound=False,five_log_bytes_and_formal_business_unchanged=True))

@pytest.mark.parametrize('gate',['lease','proof'])
def test_independent_live_current_gate_no_old_history(issuer,gate):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
 with api_process(issuer) as (client,old,port,_):assert get(client,d,d['key']).status_code==200
 id=uuid4().hex;(base/'control.json').write_text(json.dumps(dict(id=id,gate=gate)));(base/'control.json').chmod(0o600)
 helper.wait_for(lambda:(base/'control-ack.json').exists() and json.loads((base/'control-ack.json').read_text())['id']==id,authority)
 with api_process(issuer,port) as (client,new,_,_):
  q=get(client,d,d['key']);assert q.status_code==403 and 'result' not in q.json() and 'history' not in q.json()
 assert bytes_all(d)==saved and business(d)==before
 note(case,'independent-gate-'+gate,dict(two_actual_api_pids=True,current_original_gate=gate,status=403,old_history_not_leaked=True,proof_reissued=False,no_formal_permission_repair=True,five_log_bytes_and_business_unchanged=True))


def test_independent_composed_nested_body_rehash_cannot_replace_original_proof(issuer):
 base,d,authority,case=issuer;before=business(d);path=Path(d['paths'][3])
 with sqlite3.connect(path) as db:
  db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM previews').fetchone());doc=json.loads(row['document']);receipt=doc['artifact']['p4_receipts'][0]
  report=receipt['adapter_execution']['report'];report['binding']['managed_access']={};report['checks']=[];receipt['text']=prep.canonical(report);receipt['source_sha256']=ep._sha(report)
  doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'});db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(doc),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
 saved=bytes_all(d)
 with api_process(issuer) as (client,new,_,_):q=get(client,d,d['key']);assert q.status_code==409 and 'history' not in q.json() and 'result' not in q.json()
 with sqlite3.connect(path) as db:assert db.execute('SELECT proof,fingerprint FROM previews').fetchone()==(row['proof'],row['fingerprint'])
 assert bytes_all(d)==saved and business(d)==before
 note(case,'independent-composed-rehash',dict(actual_api_pid=new.pid,single_body_composed_report_text_hash_change=True,independent_proof_and_original_request_fp_unchanged=True,status=409,no_repair=True,five_log_bytes_and_business_unchanged_by_get=True))


def test_independent_original_issuer_exit_fails_closed_without_generation(issuer):
 base,d,authority,case=issuer;saved=bytes_all(d)
 with api_process(issuer) as (client,new,_,_):
  assert get(client,d,d['key']).status_code==200;(base/'stop').touch();authority.wait(15);assert authority.returncode==0 and not Path('/proc',str(authority.pid)).exists()
  q=get(client,d,d['key']);assert q.status_code==503 and 'result' not in q.json() and 'history' not in q.json() and bytes_all(d)==saved
 closed=json.loads((base/'closed.json').read_text());assert closed['generation_calls']==1 and closed['formal_business']==d['source_business'] and closed['schema']==d['schema']
 note(case,'independent-issuer-exit',dict(original_issuer_pid=authority.pid,issuer_confirmed_gone=True,api_pid=new.pid,current_get_status=503,no_restart_or_proof_reissue=True,original_generate_calls_entire_lifetime=1,five_log_bytes_unchanged=True,formal_business_before_issuer_teardown_unchanged=True))

def test_same_live_issuer_legitimate_other_key_reply_fresh_api_fails_closed(issuer):
 base,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
 with api_process(issuer) as (client,new,_,_):
  unknown='independent-client-never-sent';assert get(client,d,unknown).json()['status']=='NOT_OBSERVED'
  id=uuid4().hex;(base/'control.json').write_text(json.dumps(dict(id=id,gate='other_key_response')));(base/'control.json').chmod(0o600)
  helper.wait_for(lambda:(base/'control-ack.json').exists() and json.loads((base/'control-ack.json').read_text())['id']==id,authority)
  # Original live authority calls original _reply for another genuine stored key.
  # Full original body/hash/proof stay genuine, with no recovery generation.
  q=get(client,d,unknown);assert q.status_code==503 and 'history' not in q.json() and 'result' not in q.json()
 assert bytes_all(d)==saved and business(d)==before
 note(case,'independent-client-other-key',dict(actual_new_api_pid=new.pid,original_issuer_pid=authority.pid,requested_unknown_key='NOT_OBSERVED',actual_other_original_key_reply=True,body_hash_proof_fabrication=False,current_status=503,private_result_not_returned=True,original_generate_not_replayed=True,five_log_bytes_and_formal_business_unchanged=True))
