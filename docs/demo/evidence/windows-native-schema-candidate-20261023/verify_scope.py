import subprocess,json,hashlib
from pathlib import Path
base='69345dee47845c8173be0ccbff150ef3b611f046'
unchanged=['src/parkweave/store.py','src/parkweave/installed_fixture_receipt.py','scripts/windows/lifecycle.py','src/parkweave/synthetic_session_file.py','scripts/windows_portable/entry.py','scripts/windows_portable/build.py','scripts/windows_portable/runtime-assets.json']+[f'src/parkweave/migration-{v:03}.sql' for v in range(26,33)]
report={'scope':'OFFLINE_CONTROL_FLOW_ONLY_NOT_NATIVE_ACCEPTANCE','base':base,'unchanged_files':{}}
for name in unchanged:
 raw=Path(name).read_bytes(); assert raw==subprocess.check_output(['git','show',base+':'+name]),name
 report['unchanged_files'][name]=hashlib.sha256(raw).hexdigest()
report['tests']={'command':'PYTHONPATH=src /workspace/parkweave-venv/bin/python -B -m unittest scripts.windows_portable.test_initialize -v','passed':11,'database_executions':0,'windows_executions':0,'ci_runs_started':0,'positive_seam_mocked':['original pause','CREATE factory','original Store migration to25','exact native class authorization'],'real_registry_case':'unissued evidence refused; not original live proof acceptance','pause_check':'lifecycle preimported; not cold-import execution','commit_failure':'offline before/after COMMIT failure retains UNKNOWN; no retry or claimed rollback','first_invocation':'9 passed,1 test error: BoundaryError.reason absent; test corrected to parkweave_lifecycle_reason; not a production failure'}
manifest=json.loads(Path('docs/F2/evidence/eng057-job-shards.json').read_text())
for group in ('source_file_sha256','implementation_source_sha256'):
 for name,digest in manifest[group].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
report['manifest']={'source_files_verified':len(manifest['source_file_sha256']),'implementation_files_verified':len(manifest['implementation_source_sha256']),'historical_collection':9521,'historical_collection_rerun':False}
report['remaining']=['private PG process/auth bootstrap and restricted role secrets persistence','native SESSION/CONFIG creation and owner pause','roles/grants/seed and local approval storage native path','maintained Python runtime and actual DLL loader/symbol/forwarder closure','Windows first run and same directory reopen']
Path('/workspace/scratch/parkweave-windows-schema-candidate-20261023/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['manifest']));print('14 default/native/payload files byte-identical to base')
