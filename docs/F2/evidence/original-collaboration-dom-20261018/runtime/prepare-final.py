from pathlib import Path
import hashlib,io,json,subprocess,tarfile,tempfile
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018'
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
contracts=['docs/F2/LocalSyntheticDemoContract-20261017.md','docs/F2/ReceiptSubmitRecovery-20261018.md','docs/F2/ReceiptSubmitRefreshFix-20261018.md','docs/F2/OriginalCollaborationDOM-20261018.md']
names=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml',*contracts],cwd=root,text=True).splitlines()
expected={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}
outer=Path(tempfile.mkdtemp(prefix='pw-collaboration-final-'+sha[:7]+'-'));mirror=outer/'mirror';mirror.mkdir()
archive=subprocess.check_output(['git','archive',sha,'src','tests','scripts','pyproject.toml',*contracts],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(mirror,filter='data')
assert all(hashlib.sha256((mirror/name).read_bytes()).hexdigest()==digest for name,digest in expected.items())
legacy=['same-case-goals-20261014','partial-plan-20261013','manual-goal-task-late-20261014','manual-goal-tasks-20261014','manual-goal-recheck-20261014','manual-goal-reply-20261014','manual-goal-privacy-20261014']
for name in legacy:(mirror/'.runtime'/name).mkdir(parents=True)
modules=['test_manual_goal_collaboration_browser','test_case_feedback_cycle_browser','test_assigned_demo_chain_browser','test_demo_original_page_intake_browser','test_manual_goal_requests','test_manual_goal_privacy','test_manual_goal_tasks','test_manual_goal_tasks_late','test_manual_goal_reply','test_manual_goal_recheck','test_partial_service_plan','test_case_lifecycle','test_case_goal_results','test_executor_receipts']
freeze=dict(source_sha=sha,source_tree=subprocess.check_output(['git','rev-parse',sha+':src'],cwd=root,text=True).strip(),tests_tree=subprocess.check_output(['git','rev-parse',sha+':tests'],cwd=root,text=True).strip(),input_count=len(expected),contracts={p:expected[p] for p in contracts},outer=str(outer),mirror=str(mirror),modules=modules,automatic_retries=0)
(r/'frozen-inputs.json').write_text(json.dumps(expected,indent=2)+'\n');(r/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
print(json.dumps(freeze,indent=2))
