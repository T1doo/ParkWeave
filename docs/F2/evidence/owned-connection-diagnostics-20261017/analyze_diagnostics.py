"""Read-only reduction of recorded metadata; raw records remain the evidence."""
from pathlib import Path
from collections import Counter
import json,re,sys

r=Path('/workspace/ParkWeave/.runtime/runtime-read-diagnostics')
names=sys.argv[1:] or ['target-v1','target-v2','target-v3','full-v1','full-v2']
for name in names:
 d=r/(name+'-diagnostics')
 if not (d/'connections.jsonl').exists():continue
 rows=[json.loads(s) for s in (d/'connections.jsonl').read_text().splitlines()]
 starts={x['attempt']:x for x in rows if x['kind']=='connect_begin'}
 ends={x['attempt']:x for x in rows if x['kind']=='connect_end'}
 closes={x['attempt']:x for x in rows if x['kind']=='close_end'}
 failed={x['attempt']:x for x in rows if x['kind']=='connect_failed'}
 authorized={};disconnected={};pg_files=[]
 for p in sorted(d.glob('postgres*.log')):
  pg_files.append(p.name)
  for line in p.read_text().splitlines():
   m=re.match(r'(\d{4}-\d{2}-\d{2} [\d:.]+ UTC) \[(\d+)\] session=(\S+) app=(\S+) ',line)
   if not m:continue
   stamp,pid,session,app=m.groups()
   if 'connection authorized:' in line:
    found=re.search(r'application_name=(\S+)',line)
    if found:authorized[found[1],int(pid)]=dict(utc_millisecond_text=stamp,session=session,log=p.name)
   if 'disconnection:' in line:
    disconnected[app,int(pid)]=dict(utc_millisecond_text=stamp,session=session,log=p.name)
 matches=[];unmatched=[]
 for attempt,x in ends.items():
  key=x['application_name'],x['backend_pid']
  record=dict(attempt=attempt,application_name=key[0],backend_pid=key[1],fixture_node=x['fixture_node'],
              connect_begin_monotonic_ns=starts[attempt]['monotonic_ns'],connect_end_monotonic_ns=x['monotonic_ns'],
              close_end_monotonic_ns=closes.get(attempt,{}).get('monotonic_ns'),connect_elapsed_ns=x['elapsed_ns'],
              pg_authorized=authorized.get(key),pg_disconnected=disconnected.get(key))
  (matches if key in authorized and key in disconnected else unmatched).append(record)
 failures=[]
 for attempt,x in failed.items():
  name_matches=[dict(backend_pid=pid,authorized=event,disconnected=disconnected.get((app,pid)))
                for (app,pid),event in authorized.items() if app==x['application_name']]
  samples=[s for s in rows if s['kind']=='failure_activity' and s['failed_attempt']==attempt]
  failures.append(dict(connect_begin=starts[attempt],connect_failed=x,pg_authorized_by_exact_application_name=name_matches,
                       single_activity_samples=samples))
 stats=dict(window=name,events=len(rows),attempts=len(starts),connected=len(ends),connect_failed=len(failed),
  close_ends=len(closes),all_observed_close_flags_true=all(x['closed'] for x in closes.values()),
  correlated_authorized_and_disconnected=len(matches),unmatched_pg_records=len(unmatched),
  failure_activity_samples=sum(x['kind']=='failure_activity' for x in rows),
  sample_attempts=sum(x['kind']=='failure_sample_begin' for x in rows),
  max_connect_ms=max((x['elapsed_ns']/1e6 for x in ends.values()),default=None),
  event_counts=dict(Counter(x['kind'] for x in rows)),pg_files=pg_files,
  diagnostic_finished=any(x['kind']=='diagnostic_finish' for x in rows),
  final_unclosed_metadata=next((x.get('successful_connections_without_observed_close') for x in reversed(rows) if x['kind']=='diagnostic_finish'),None),
  failures=failures,connections_correlated=matches,connections_without_complete_pg_match=unmatched,
  writer_lifecycle=[x for x in rows if x['kind'] in ('owned_writer_application','WRITER_PROCESS_READY','OWNED_PROCESS_STOP_BEGIN','OWNED_PROCESS_SIGINT_SENT','OWNED_PROCESS_EXITED')],
  interpretation='A new successful window does not establish historical timeout cause. PG clocks have millisecond precision; client events carry separate monotonic and UTC nanoseconds. No SQL text sampled.')
 (r/(name+'-analysis.json')).write_text(json.dumps(stats,indent=2)+'\n')
 print(json.dumps({k:v for k,v in stats.items() if k not in ('failures','connections_correlated','connections_without_complete_pg_match','writer_lifecycle','event_counts','final_unclosed_metadata')},ensure_ascii=False))
