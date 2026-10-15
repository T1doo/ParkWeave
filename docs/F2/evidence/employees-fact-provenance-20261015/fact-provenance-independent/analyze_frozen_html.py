"""Read actual owned-HTTP HTML traces; no execution or product import."""
import argparse,hashlib,json
from pathlib import Path
MODES=['positive','lost_ack','current_403','late_403']
SCOPE='FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG'
def main():
 p=argparse.ArgumentParser();p.add_argument('artifact_dir');p.add_argument('--output',required=True);p.add_argument('--source-sha',required=True);a=p.parse_args()
 assert a.source_sha=='8fe3e6c6ebdb14366dd80032c953c79e746e3fd1','Final source target mismatch'
 directory=Path(a.artifact_dir);rows=[]
 for mode in MODES:
  matches=[]
  for path in directory.glob(mode+'-*.stdout.jsonl'):
   lines=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
   result=next((x for x in reversed(lines) if x.get('scope')==SCOPE),None)
   if result:matches.append((path,lines,result))
  assert len(matches)==1,(mode,'one final formal successful trace required',len(matches))
  path,lines,result=matches[0];calls=result['calls'];posts=[c for c in calls if c['method']=='POST'];denied=[c for c in calls if c['status']==403]
  assert result['fake_dto'] is False and result['real_browser']=='NOT_RUN'
  for c in calls:assert 'headers' not in c and 'token' not in c
  r=dict(mode=mode,trace=str(path.resolve()),trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),checks=result['checks'],actual_native_fetches=len(calls),post_count=len(posts),backend403_count=len(denied),fake_dto=False,real_browser='NOT_RUN')
  if mode in ('positive','lost_ack'):
   adopts=[c for c in posts if c['path'].endswith('/service-case-plan')]
   assert len(adopts)==1 and adopts[0]['status']==201
   b=adopts[0]['body'];assert b['fact_provenance_scope']=='EMPLOYEES_USER_ASSERTION_V1' and b['local_revision'] is True and b['opportunity_proof']
   verify=[c for c in posts if c['path'].endswith('/service-case-plan/commands') and c['body']['action']=='VERIFY']
   assert len(verify)==5 and all(c['status']==200 for c in verify)
   assert len({c['body']['step_id'] for c in verify})==5
   assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
   assert any('/api/cases/worklist' in c['path'] and c['status']==200 for c in calls)
   r.update(original_adopt_201=1,original_verify_200=5,six_goal_and_worklist_reads=True)
   if mode=='lost_ack':
    gets=[c for c in calls if c['method']=='GET' and c['path'].endswith('/service-case-plan/command-recovery')]
    assert any(c['status']==200 for c in gets)
    bound=[c for c in gets if 'request_key' in c]
    assert bound,'Final frozen new driver must record the actual recovery Idempotency-Key'
    assert all(c['request_key']==adopts[0]['request_key'] and c['status']==200 for c in bound)
    r.update(controlled_committed_response_loss=True,original_command_recovery_get_200=True,no_duplicate_adopt=True,
       exact_get_key_raw_binding='EXACT_ORIGINAL_IDEMPOTENCY_HEADER_RECORDED' if bound else 'NOT_RECORDED_GET_IDEMPOTENCY_HEADER',
       recorded_bound_recovery_gets=len(bound),identity_probe_unkeyed_gets=len(gets)-len(bound))
  else:
   assert not posts and any(c['status']==403 and '/employees-fact-impact' in c['path'] for c in calls)
   r.update(read_only_denial_flow=True,current403_clear_or_late403_isolation_checked=True)
  rows.append(r)
 result=dict(schema=1,source_sha=a.source_sha,status='MECHANICAL_RAW_TRACE_VALIDATION',rows=rows,
   actual_native_fetches=sum(r['actual_native_fetches'] for r in rows),
   limit='Counts are original HTML native fetches only. Python control original API calls are additional and their aggregate is NOT_RECORDED here. Node VM mechanical DOM is not a real browser.')
 Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'modes':len(rows),'actual_native_fetches':result['actual_native_fetches']}))
if __name__=='__main__':main()
