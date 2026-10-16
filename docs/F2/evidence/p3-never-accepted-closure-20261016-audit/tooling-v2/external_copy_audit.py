"""Independent explicit external-copy manifest audit. No discovery of secrets.

The final producer must supply external-copy-selection.json (paths and hashes,
never values); no expected manifest is silently skipped. Preparation only until
that actual final receipt exists.
"""
from pathlib import Path
import hashlib,json,datetime

def verify_external_copies(root,require):
 config_path=root/'.runtime/p3-closure-audit/tooling-v2/external-copy-selection.json'
 config=json.loads(config_path.read_text())
 require(set(config)=={'source_sha','chromium_manifests','private_manifests','support_manifest','writer_cessation'},'external selection exact schema')
 source=json.loads((root/'.runtime/p3-closure-root/v1/freeze.json').read_text())['source_sha']
 require(config['source_sha']==source,'external selection source mismatch')
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 def path(name):
  p=(root/name).resolve();require(p.is_relative_to((root/'.runtime').resolve()),'external path outside runtime');require(not (root/name).is_symlink(),'external symlink refused');return p
 def dt(value):
  d=datetime.datetime.fromisoformat(value);require(d.tzinfo is not None,'naive external timestamp');return d
 def modified(p):return datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()
 chrome=[];private=[]
 for selected in config['chromium_manifests']:
  require(set(selected)=={'manifest','sha256','receipt'},'external Chrome selection schema')
  mpath=path(selected['manifest']);require(sha(mpath)==selected['sha256'],'external Chrome manifest hash changed');m=json.loads(mpath.read_text());rpath=path(selected['receipt']);r=json.loads(rpath.read_text())
  require(m['source_sha']==r['source_sha']==source and r['exit_code']==0,'external Chrome source/result mismatch')
  require(m['window_started_utc']==r['started_utc'] and m['window_finished_utc']==r['finished_utc'],'external Chrome times mismatch')
  seen=set()
  for row in m['files']:
   a,b=path(row['original_path']),path(row['copy_path']);raw=a.read_bytes();value=json.loads(raw)
   require(raw==b.read_bytes() and sha(a)==sha(b)==row['sha256'] and len(raw)==row['bytes'],'external Chrome bytes changed')
   require(modified(a)==row['mtime_utc'] and dt(r['started_utc'])<=dt(row['mtime_utc'])<=dt(r['finished_utc']),'external Chrome original outside exact window')
   require(row['within_completed_window'] is True and value['mode']==row['mode'],'external Chrome mode mismatch')
   require(value['actual_browser']==row['actual_browser']=='INSTALLED_CHROMIUM' and value['page_errors']==row['page_errors']==[],'external Chrome actual browser/errors mismatch')
   require(row['original_path'] not in seen,'duplicate external original');seen.add(row['original_path'])
  require(len(seen)==r['counts']['PASS'] and r['counts']['FAIL']==r['counts']['ERROR']==r['counts']['SKIP']==0,'external originals count/JUnit receipt mismatch')
  chrome.append(dict(manifest=selected['manifest'],sha256=sha(mpath),originals=len(seen)))
 for selected in config['private_manifests']:
  require(set(selected)=={'manifest','sha256'},'external private selection schema');mpath=path(selected['manifest']);require(sha(mpath)==selected['sha256'],'external private manifest hash changed');m=json.loads(mpath.read_text());require(m['source_sha']==source,'external private source mismatch')
  for row in m['files']:
   a,b=path(row['original']),path(row['copy']);raw=a.read_bytes();value=json.loads(raw)
   require(raw==b.read_bytes() and sha(a)==sha(b)==row['sha256'],'external private original/copy mismatch')
   require(modified(a)==row['mtime_utc'] and (a.stat().st_mode&0o777)==(b.stat().st_mode&0o777)==0o600,'external private mtime/mode mismatch')
   require(type(value) is list and all(type(v) is str for v in value),'external private schema differs')
   require(len(value)==row['entry_count'] and bool(row['fully_registered_in']),'external private entry count/registration missing')
   for registered in row['fully_registered_in']:
    registry=path(registered);obj=json.loads(registry.read_text());pool=obj['synthetic_private_values'] if type(obj) is dict else obj
    require(set(value)<=set(pool),'external private copy not fully registered')
  private.append(dict(manifest=selected['manifest'],sha256=sha(mpath),pairs=len(m['files'])))
 support=config['support_manifest'];stop=config['writer_cessation']
 require(set(support)=={'path','sha256'} and set(stop)=={'path','sha256','expected_status'},'external support selection schema')
 sp,wp=path(support['path']),path(stop['path']);require(sha(sp)==support['sha256'] and sha(wp)==stop['sha256'],'external support/cessation bytes changed')
 s,w=json.loads(sp.read_text()),json.loads(wp.read_text());require(s['source_sha']==w['source_sha']==source,'external support/cessation source changed')
 for row in s['files']:
  p=path(row['path']);require(sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],'external support file changed')
 require(w['status']==stop['expected_status'],'oracle exact cessation status differs')
 require(s['freeze_sha256']==w['freeze_sha256']==sha(root/'.runtime/p3-closure-root/v1/freeze.json'),'oracle freeze binding differs')
 require(s['counts']==w['counts'] and s['counts']['PASS']>0 and all(s['counts'][k]==0 for k in ('FAIL','ERROR','SKIP')) and w['actual_junit_collection_unique_exact'] is True and w['all_drift']==[],'oracle final receipt aggregate differs')
 require(w['active_tests_owned_by_this_agent']==0 and w['active_primary_writers_after_this_receipt']==0 and w['shared_source_git_old_primary_writes'] is False,'oracle writers not stopped')
 require(path(w['support_manifest'])==sp and w['support_manifest_sha256']==sha(sp),'writer cessation support binding mismatch')
 require(dt(modified(sp))<=dt(w['utc']),'cessation before support completed')
 require(w['externalcopyselection']==s['externalcopyselection']==[] and config['chromium_manifests']==config['private_manifests']==[],'actual oracle zero external-copy scope differs')
 routing_rows=[row for row in s['files'] if row['path']=='.runtime/p3-closure-oracle/final-artifact-routing-v1.json']
 require(len(routing_rows)==1,'one actual routing receipt required');routing_path=path(routing_rows[0]['path']);routing=json.loads(routing_path.read_text())
 require(routing['source_sha']==source and routing['externalcopyselection']==[] and routing['external_copy_files_created']==0 and routing['external_files_found']==[],'oracle actual no-external-copy route differs')
 require(type(routing['windows']) is list and {row['window'] for row in routing['windows']}=={'p3-independent','p3-races-solo'},'exact oracle original two window routes required')
 support_windows={row['name']:row for row in s['windows']}
 require(set(support_windows)=={'p3-independent','p3-races-solo'},'oracle support two window identities differ')
 total=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
 for route in routing['windows']:
  name=route['window'];record=support_windows[name];rp=path(record['receipt']['path']);raw=rp.read_bytes();receipt=json.loads(raw)
  require(sha(rp)==record['receipt']['sha256'] and len(raw)==record['receipt']['bytes'],'oracle actual window receipt changed')
  require(receipt['source_sha']==source and receipt['exit_code']==0 and receipt['counts']==record['counts'],'oracle actual source/window result differs')
  require(receipt['started_utc']==record['started_utc'] and receipt['finished_utc']==record['finished_utc'],'oracle window times differ')
  require(dt(receipt['finished_utc'])<=dt(w['utc']),'oracle window ends after cessation')
  require(route['actual_artifact_root']=='.runtime/p3-closure-root/v1/final/artifacts/'+name and route['oracle_route']==route['actual_artifact_root']+'/p3-oracle' and route['fixture_route']==route['actual_artifact_root']+'/p3-closure','oracle exact original artifact route changed')
  require(route['externalcopyselection']==[] and route['collection_artifact_paths']==[],'oracle routing external/collection output differs')
  require(route['actual_import_records']==record['counts']['PASS'],'oracle actual import records count differs')
  for key in total:total[key]+=record['counts'][key]
 require(total==s['counts']==dict(PASS=37,FAIL=0,ERROR=0,SKIP=0),'oracle real35+race2 count union differs')
 registration_path=path(w['private_registration_manifest']);require(sha(registration_path)==w['private_registration_manifest_sha256'],'oracle private registration manifest changed');registration=json.loads(registration_path.read_text())
 require(registration['source_sha']==source and len(registration['files'])==w['private_registration_files'] and w['all_private_registrations_600'] is True,'oracle private registry aggregate differs')
 for row in registration['files']:
  target=path(row['path']);raw=target.read_bytes();value=json.loads(raw);values=value['synthetic_private_values'] if type(value) is dict else value
  require(sha(target)==row['sha256'] and len(raw)==row['bytes'] and (target.stat().st_mode&0o777)==0o600 and row['mode']=='0600','oracle registered private bytes/mode changed')
  require(type(values) is list and all(type(v) is str for v in values) and len(values)==row['registered_values_count'] and row['all_values_in_window_capture_registry'] is True,'oracle registered private schema/count differs')
  require(target.stat().st_mtime_ns==row['mtime_ns'],'oracle private registration original mtime changed')
  windows=[name for name in ('p3-independent','p3-races-solo') if '/artifacts/'+name+'/' in row['path'] or row['path'].endswith('/redaction-'+name+'.private.json')]
  require(len(windows)==1,'oracle private registry actual window not unique')
  capture=path('.runtime/p3-closure-root/v1/final/redaction-'+windows[0]+'.private.json');capture_value=json.loads(capture.read_text());capture_values=capture_value['synthetic_private_values'] if type(capture_value) is dict else capture_value
  require(set(values)<=set(capture_values),'oracle private values not independently covered by exact original capture')


 return dict(chromium_originals=chrome,private_manifests=private,support_sha256=sha(sp),writer_cessation_sha256=sha(wp),routing_sha256=sha(routing_path),private_registration_sha256=sha(registration_path),external_copy_selection=[])
