from pathlib import Path
import hashlib,json,subprocess,time
root=Path.cwd();base=root/'.runtime/template-local-migration-20261014'
modules=['test_template_migration_event_capacity', 'test_template_migration_legacy', 'test_template_migration_legacy_independent', 'test_template_migration_independent', 'test_template_migration_ui_offline', 'test_template_migration_nodevm_actual', 'test_template_upgrade', 'test_template_consumer', 'test_template_consumer_planning', 'test_template_consumer_compatibility', 'test_service_case_steps', 'test_service_plan_manual_lock', 'test_registered_local_revision', 'test_case_goal_results', 'test_template_candidate', 'test_template_full_chain', 'test_template_hold', 'test_template_partial', 'test_template_terminal', 'test_template_plan_continuity', 'test_template_consumer_planning_offline', 'test_case_resources', 'test_resource_plan_binding', 'test_executor_receipts', 'test_case_lifecycle', 'test_native_run_access', 'test_native_run_access_writer', 'test_native_run_access_activation', 'test_native_run_access_restricted_adapter', 'test_native_run_access_preflight', 'test_native_run_access_offline', 'test_case_cancellation', 'test_case_cancellation_business_binding', 'test_case_cancellation_before_receipt', 'test_case_cancellation_reconciliation', 'test_partial_service_plan', 'test_partial_service_plan_expansion', 'test_service_selection_full_chain', 'test_service_selection_execution_preview']
for name in modules:assert (root/'tests'/f'{name}.py').is_file(),name
files=sorted(p for d in ['src','tests','scripts'] for p in (root/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
def manifest():return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();before=manifest();(base/'final-before.json').write_text(json.dumps(before,indent=2)+'\n')
args=[str(root/'.venv/bin/python'),'-m','pytest',*[f'tests/{n}.py' for n in modules],'-q','--junitxml='+str(base/'final.xml')]
start=time.monotonic()
with (base/'final.log').open('w') as log:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT).returncode
elapsed=time.monotonic()-start;after=manifest();(base/'final-after.json').write_text(json.dumps(after,indent=2)+'\n');(base/'final.exit').write_text(str(code)+'\n')
record=dict(source_sha=source,argv=args,exit_code=code,elapsed_seconds=elapsed,files=len(before),source_drift=[p for p in before if before[p]!=after[p]])
(base/'final-window.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));print((base/'final.log').read_text()[-5000:])
