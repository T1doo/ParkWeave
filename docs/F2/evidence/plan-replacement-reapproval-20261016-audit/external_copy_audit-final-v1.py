"""Read-only external Chrome originals/private-copy audit; never returns values."""
from pathlib import Path
import hashlib,json,datetime

def verify_external_copies(root,require):
 oracle=root/'.runtime/plan-replacement-oracle'
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 def dt(v):
  x=datetime.datetime.fromisoformat(v);require(x.tzinfo is not None,'external manifest timestamp must be UTC-aware');return x
 def modified(p):return datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc)
 def bounded(name):
  p=(root/name).resolve();require(p.is_relative_to((root/'.runtime').resolve()),'external evidence path outside runtime');return p
 expected_sources={'v2':'06fd9a731f35d5691b5f6017e427eb24f2cf1865','v3':'b7eec40f005ba5877ecea1a7165e99bd668d041c','v4':'2dd98b67d52746dcdc3f358d2d60042cbea93909'}
 chrome=[]
 for version,source in expected_sources.items():
  manifest_path=oracle/('chromium-originals-'+version+'-manifest.json');manifest=json.loads(manifest_path.read_text())
  receipt_path=root/('.runtime/plan-replacement-root/'+version+'/final/replacement-chromium.json');receipt=json.loads(receipt_path.read_text())
  require(manifest['source_sha']==receipt['source_sha']==source,'Chrome original mapping source mismatch '+version)
  require(receipt['exit_code']==0 and receipt['counts']==dict(PASS=4,FAIL=0,ERROR=0,SKIP=0),'Chrome original mapping needs actual full4PASS '+version)
  require(manifest['window_started_utc']==receipt['started_utc'] and manifest['window_finished_utc']==receipt['finished_utc'],'Chrome mapping window mismatch '+version)
  rows=manifest['files'];require(len(rows)==4 and {x['mode'] for x in rows}=={'positive','lost_commit','lost_propose','lost_approve'},'Chrome mapping exact modes mismatch '+version)
  for row in rows:
   original=bounded(row['original_path']);copy=bounded(row['copy_path']);raw=original.read_bytes();replica=copy.read_bytes();data=json.loads(raw)
   require(sha(original)==sha(copy)==row['sha256'] and raw==replica and len(raw)==row['bytes'],'Chrome original/copy byte mismatch '+version)
   moment=modified(original);require(moment.isoformat()==row['mtime_utc'],'Chrome original mtime changed '+version)
   require(dt(receipt['started_utc'])<=moment<=dt(receipt['finished_utc']) and row['within_completed_window'] is True,'Chrome original outside completed window '+version)
   require(data['mode']==row['mode'] and data['browser_version']==row['browser_version'] and data['actual_browser']==row['actual_browser']=='INSTALLED_CHROMIUM','Chrome original parsed identity mismatch '+version)
   require(data['page_errors']==row['page_errors']==[],'Chrome original page errors mismatch '+version)
   for field,key in (('call_count','calls'),('python_request_count','python_http_requests')):
    if field in row:require(row[field]==len(data[key]),'Chrome original count metadata mismatch '+version)
   if 'python_prerequisites' in row:require(row['python_prerequisites']==data['python_prerequisites'],'Chrome prerequisite metadata mismatch '+version)
  chrome.append(dict(version=version,source_sha=source,files=4,manifest_sha256=sha(manifest_path),receipt_sha256=sha(receipt_path)))
 private_count=0;value_count=0;private_manifests=[]
 for version in ('v3','v4'):
  private_path=oracle/('ui-fixture-private-'+version+'-manifest.json');private_manifest=json.loads(private_path.read_text());source=expected_sources[version]
  require(private_manifest['source_sha']==source,'external private mapping source mismatch')
  for row in private_manifest['files']:
   original=bounded(row['original']);copy=bounded(row['copy']);raw=original.read_bytes();replica=copy.read_bytes()
   require(raw==replica and sha(original)==sha(copy)==row['sha256'],'external private registry copy mismatch')
   require(modified(original).isoformat()==row['mtime_utc'],'external private original mtime changed')
   require((original.stat().st_mode&0o777)==(copy.stat().st_mode&0o777)==0o600 and row['mode']=='0o600','external private registry mode differs')
   values=json.loads(raw);require(type(values) is list and all(type(v) is str for v in values),'external private registry shape differs')
   require(len(values)==row['entry_count'],'external private registry count differs')
   for window in row['matching_time_windows']:
    record=json.loads((root/('.runtime/plan-replacement-root/'+version+'/final/'+window+'.json')).read_text())
    require(record['source_sha']==source and dt(record['started_utc'])<=modified(original)<=dt(record['finished_utc']),'external private registry timestamp/window differs')
   require(bool(row['fully_registered_in']),'external private registry not covered by any original collector')
   for window in row['fully_registered_in']:
    registry=root/('.runtime/plan-replacement-root/'+version+'/final/redaction-'+window+'.private.json');pool=json.loads(registry.read_text());pool=pool['synthetic_private_values'] if isinstance(pool,dict) else pool
    require(set(values)<=set(pool),'external private registry not fully included in collector')
   private_count+=1;value_count+=len(values)
  private_manifests.append(dict(version=version,sha256=sha(private_path)))
 support_path=oracle/'final-v4-support-manifest.json';support=json.loads(support_path.read_text())
 require(support['source_sha']==source and support['actual_independent_tests']==30 and support['http_tests_separate']==4 and support['chromium_tests_separate']==4,'oracle final support scope differs')
 for row in support['files']:
  p=bounded(row['path']);require(sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],'oracle support file bytes changed')
 cessation_path=oracle/'writer-cessation-v4.json';cessation=json.loads(cessation_path.read_text())
 require(cessation['status']=='ORACLE_WRITERS_STOPPED_READY_FOR_PARENT_SEAL' and cessation['source_sha']==source,'oracle writer cessation status/source differs')
 require(cessation['active_tests_or_probes_owned_by_oracle']==0 and cessation['shared_source_or_git_writes'] is False,'oracle writers not stopped')
 require(bounded(cessation['support_manifest'])==support_path.resolve() and cessation['support_manifest_sha256']==sha(support_path),'oracle cessation support hash differs')
 require(modified(support_path)<=dt(cessation['utc']),'oracle cessation predates support manifest')
 return dict(chromium_originals=chrome,private_original_copy_pairs=private_count,private_entries_counted=value_count,private_manifest_versions=private_manifests,support_manifest_sha256=sha(support_path),writer_cessation_sha256=sha(cessation_path))
