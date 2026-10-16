"""Independent explicit external-copy manifest audit. No discovery of secrets.

The final producer must supply external-copy-selection.json (paths and hashes,
never values); no expected manifest is silently skipped. Preparation only until
that actual final receipt exists.
"""
from pathlib import Path
import hashlib,json,datetime

def verify_external_copies(root,require):
 config_path=root/'.runtime/frontier-audit/external-copy-selection.json'
 config=json.loads(config_path.read_text())
 require(set(config)=={'source_sha','chromium_manifests','private_manifests','support_manifest','writer_cessation'},'external selection exact schema')
 source=json.loads((root/'.runtime/frontier-root/v3/freeze.json').read_text())['source_sha']
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
 require(s['freeze_sha256']==w['freeze_sha256']==sha(root/'.runtime/frontier-root/v3/freeze.json'),'oracle freeze binding differs')
 require(s['counts']==w['counts']==dict(PASS=34,FAIL=0,ERROR=0,SKIP=0) and w['actual_junit_collection_unique_exact'] is True and w['all_drift']==[],'oracle final34 receipt aggregate differs')
 require(w['active_tests_owned_by_this_agent']==0 and w['active_primary_writers_after_this_receipt']==0 and w['shared_source_git_old_primary_writes'] is False,'oracle writers not stopped')
 require(path(w['support_manifest'])==sp and w['support_manifest_sha256']==sha(sp),'writer cessation support binding mismatch')
 require(dt(modified(sp))<=dt(w['utc']),'cessation before support completed')
 require(w['externalcopyselection']==s['externalcopyselection']==[] and config['chromium_manifests']==config['private_manifests']==[],'actual oracle zero external-copy scope differs')
 routing_rows=[row for row in s['files'] if row['path']=='.runtime/frontier-oracle-v2/final-artifact-routing-v1.json']
 require(len(routing_rows)==1,'one actual routing receipt required');routing_path=path(routing_rows[0]['path']);routing=json.loads(routing_path.read_text())
 require(routing['source_sha']==source and routing['externalcopyselection']==[] and routing['external_copy_files_created']==0 and routing['external_files_found']==[],'oracle actual no-external-copy route differs')
 require(routing['old_planreplacement_newer_than_baseline']==[],'oracle found late writes to prior roots')
 require(routing['actual_artifact_root']=='.runtime/frontier-root/v3/final/artifacts/frontier-independent','oracle actual artifact root changed')
 require(dt(routing['window_finished_utc'])<=dt(w['utc']),'oracle routing completed after cessation')
 registration_path=path(w['private_registration_manifest']);require(sha(registration_path)==w['private_registration_manifest_sha256'],'oracle private registration manifest changed');registration=json.loads(registration_path.read_text())
 require(registration['source_sha']==source and len(registration['files'])==w['private_registration_files'] and w['all_private_registrations_600'] is True,'oracle private registry aggregate differs')
 for row in registration['files']:
  target=path(row['path']);raw=target.read_bytes();value=json.loads(raw);values=value['synthetic_private_values'] if type(value) is dict else value
  require(sha(target)==row['sha256'] and len(raw)==row['bytes'] and (target.stat().st_mode&0o777)==0o600 and row['mode']=='0600','oracle registered private bytes/mode changed')
  require(type(values) is list and all(type(v) is str for v in values) and len(values)==row['entries'] and row['fully_registered'] is True,'oracle registered private schema/count differs')

 return dict(chromium_originals=chrome,private_manifests=private,support_sha256=sha(sp),writer_cessation_sha256=sha(wp),routing_sha256=sha(routing_path),private_registration_sha256=sha(registration_path),external_copy_selection=[])
