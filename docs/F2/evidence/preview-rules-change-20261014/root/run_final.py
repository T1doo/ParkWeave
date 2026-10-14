from pathlib import Path
import hashlib,json,subprocess,time
root=Path.cwd();base=root/'.runtime/preview-rules-change-20261014'
modules=['test_synthetic_rule_second_park', 'test_preview_rules_change_nodevm_actual', 'test_independent_preview_change_review', 'test_independent_rule_simulation_review', 'test_independent_rule_journal_review', 'test_service_selection_execution_preview', 'test_isolated_execution_preview', 'test_resource_execution_preview', 'test_dispatch_execution_preview', 'test_receipt_execution_preview', 'test_lifecycle_execution_preview', 'test_preview_commit_protection', 'test_synthetic_rule_readiness', 'test_synthetic_rule_readiness_api', 'test_rule_publication_candidate', 'test_readiness', 'test_readiness_checklist', 'test_service_resource_change_replay', 'test_resource_plan_binding', 'test_registered_local_revision', 'test_case_resources', 'test_resource_alternative_times', 'test_service_selection_replay_acceptance', 'test_preview_rules_change_web', 'test_service_instance_cold_web', 'test_service_selection_web', 'test_worklist_real_entries_offline', 'test_case_worklist_offline', 'test_service_cold_entry_nodevm_actual', 'test_resource_alternative_times_offline']
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
