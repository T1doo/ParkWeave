"""Contract-first ordinary demo review design; stdlib/Git reads only."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,subprocess

ROOT=Path('/workspace/ParkWeave');OUT=Path(__file__).resolve().parent
BASE='6067cd3070ef3987d9013b1f47768df667d3f612'
CONTRACT_SHA='5e61cb1d84dd3e5c9523921be1d82856c3c45f83'
CONTRACT='docs/F2/OrdinarySyntheticDemoContract-20261018.md'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def entry(commit,path):
    raw=git('show',commit+':'+path)
    return dict(commit=commit,path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_blob=git('rev-parse',commit+':'+path).decode().strip())
def save(name,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    with (OUT/name).open('xb') as f:f.write(raw)
    with (OUT/(name+'.sha256')).open('x') as f:f.write(hashlib.sha256(raw).hexdigest()+'  '+name+'\n')

inputs=[entry(CONTRACT_SHA,CONTRACT)]
for path in [
 'docs/sources/V1/平台产品设计 (2).md','docs/sources/V1/分阶段开发计划 (2).md',
 'docs/F1/ATBindings.json','docs/验收规格.json',
 'docs/F2/OrdinaryCaseStepContract-20261018.md','docs/F2/OrdinaryCaseGoalResultsContract-20261018.md',
 'docs/F2/OrdinaryCaseRecordRecheckContract-20261018.md',
 'scripts/material_only_demo.py','scripts/linux_fixture_server.py',
 'src/parkweave/case_fact_clarifications.py','src/parkweave/store.py',
 'src/parkweave/roles.sql','src/parkweave/process_env.py',
 'src/parkweave/api.py','src/parkweave/worker.py','src/parkweave/bounded_planning.py',
 'src/parkweave/case_step_assignments.py','src/parkweave/case_lifecycle.py',
 'tests/test_ordinary_case_goal_results.py','tests/test_service_case_steps.py',
 'tests/test_ordinary_case_record_recheck.py',
]:inputs.append(entry(BASE,path))

oracles=[
 dict(id='OSD-O01',title='Setup is explicit and can only create a new owned fake installation',
  stimulus='Invoke setup in a supported existing nonroot Linux/Python environment, or supply a DSN/state-import/identity/SQL/permission/file import parameter or an existing target.',
  expect='Only a newly created private /tmp/parkweave-ordinary-demo-* state and fresh Unix-socket PG cluster/database can be initialized. No existing real or old material-only database is selected, adopted, repaired, reset, renamed or deleted. No download/root/security permission expansion and no implicit setup in ordinary API/worker/serve.'),
 dict(id='OSD-O02',title='Original fresh creation receipt and exact empty business initial state',
  stimulus='Initialize the new fake database, or call its initialization helper with a plain Store, constructed/copied receipt, persisted creation observation or wrong live connection.',
  expect='Use original fresh capture before CREATE, original process-local FixtureDatabaseEvidence and live connection verification, then original Store.migrate schema32. Only the fresh issued authority may initialize; observation JSON is forensic data, never new authority. Initial state has exactly3 marked SYNTHETIC actors,4 READ/EXECUTE capability rows,1 owner case.create,2 PREPARE/REVIEW_ASSIGNED rows,1 known SYNTHETIC catalogue,2 SYNTHETIC resources and4 owner READ/HOLD resource grants. field_grants,run_assignments and all Run/Case/preparation/plan/dispatch/receipt/lifecycle/notification business records start0. No prior accepted or closed Case is seeded.'),
 dict(id='OSD-O03',title='Serve validates retained state and never performs setup or repair',
  stimulus='Serve a valid retained installation before and after ordinary user business, then restart PG/API/worker on the same state.',
  expect='Serve checks source, schema32, original cluster system identifier/database OID, immutable authority/catalogue/resource state and private owned files, then starts ordinary API+worker with the same restricted app connection. Existing legitimate nonzero business records and a changed postmaster start on restart are normal. No migrate, seed, new receipt, new Grant, restored revocation or rewrites of state/offer/receipt/history occur.'),
 dict(id='OSD-O04',title='Content and file/state bindings work without Git metadata',
  stimulus='Run from a source copy with no .git or only documentation/Git metadata differences; alternatively change a runtime source, launcher/lifecycle helper, state identity or protected file permissions/symlink.',
  expect='Source binding uses actual product src files except __pycache__, current launcher, material_only_demo.py and linux_fixture_server.py used helpers. Git metadata is unnecessary. Runtime/helper content drift, wrong cluster/database, wrong schema/authority or nonprivate/nonowned/symlink state rejects without repair. Documentation or source-commit metadata alone does not issue authority or fabricate a new business authorization.'),
 dict(id='OSD-O05',title='App technical privileges and credentials remain narrowly scoped',
  stimulus='Inspect the new SQL app role and immutable business-authority state, or expand its SQL role/membership/database/schema/table/column rights; inspect stdout, URL and private sessions.',
  expect='Only this newly owned fake cluster receives the required technical ACL. App is not owner/superuser and cannot create/update identities, grants, catalogue/rules/resources or obtain Native writer rights. Serve detects actual role flags/memberships and technical ACL drift, not only rows in principals/grants/catalogue/resources. Tokens/DSNs stay out of stdout/URL/repository; sessions remain private and unchanged across restart. Sessions do not automatically expire; stopping service is not revocation.'),
 dict(id='OSD-O06',title='The real ordinary API and worker reuse original planning and P1-P5 algorithms',
  stimulus='Start from the actual launcher-created empty business database and submit a new explicit user request/materials through ordinary HTTP while the actual ordinary worker runs.',
  expect='Actual worker creates/finishes the new case.create Run; user explicitly REVIEW/CONFIRM, original planning-preview and ADOPT, P1 VERIFY, original two-resource combination/link/P2, reviewer OFFER, executor own ACCEPT/P3, manual SUBMIT/owner ACK/P4, original REVALIDATE/CLOSE and explicit P5 VERIFY lead to original goal-results/TXT. No Store.finish/test-ready assignment substitute or positive-path owner SQL editing business data. Existing planning positive path is reused, not reimplemented or described as absent. LOCAL record completion keeps case_goal_completed=false, qualification NOT_EVALUATED, external NOT_SUBMITTED and offline NO_EVIDENCE.'),
 dict(id='OSD-O07',title='Retained restart and independent new input preserve identity and history',
  stimulus='Stop and restart the same state, cold-read Case A, then submit different user input to create Case B.',
  expect='Case A/history/plan/receipt remain under the same database and original identities; currentness is re-evaluated rather than assumed after expiry. B has new Run/Case/preparation/plan/offer identities, new actual material/source and explicit decisions; no copied old Case-specific marker or receipt. The same3 current principals and current global Grants may be reused under original current checks, without issuing new identities/Grants. Old occupancy/history stays preserved, run_assignments remain0 and no old deadline is renewed.'),
 dict(id='OSD-O08',title='Only owned children and explicit ordinary providers run',
  stimulus='Bind an occupied HTTP port, encounter old lock/postmaster/unknown listener, fail API/worker/PG startup or stop, or provide conflicting inherited runtime/provider configuration.',
  expect='HTTP binds127.0.0.1 and PG only the private Unix socket. API/worker explicitly use LOCAL and CURRENT_PREPARATION with the same restricted app. Native/formal/resource-approval/IsolatedPlanApproval/LOCAL_SYNTHETIC_DEMO/V4/model providers stay off under unchanged guards. Unknown processes/locks/listeners are not adopted, signalled, removed or killed. Stop only actual child process references created by this invocation; unconfirmed stop preserves a marker and refuses later serve. Failures preserve state/logs and do not automatically retry creation/repair. Expired original300s steps remain rejected; ordinary restart never renews them.'),
 dict(id='OSD-O09',title='Evidence and delivery claims match the bounded synthetic execution',
  stimulus='Review commands, initial counts, actual full path/worker process evidence, restart, failure windows, source/module origins and published artifacts.',
  expect='Finite frozen-SHA execution distinguishes setup, serving, user business, negative injected faults and cleanup. Fresh same-input archives/maps and actual origins/collection/phases/JUnit are recorded; every failure is retained with private token inventory and one canonical redaction map. No real identity/Grant/publication/approval/credential/production install, browser/Windows/formal AT35/model or complete project claim. Earlier planning/P5 slices remain historical and are not rerun/recounted as this new demo.'),
]

clarifications=[
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION_REVIEW',topic='Technical ACL validation',decision='Do not inherit old material-only authority-row hash as complete permission proof. New serve records/checks actual app role flags/memberships and database/schema/table/column ACL, rejecting drift without repair.'),
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION_REVIEW',topic='Receipt gate',decision='Initialization requires exact original live FixtureDatabaseEvidence and verification on the actual initialization connection. Plain Store or persisted observation cannot initialize; serve never reissues creation authority.'),
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION_REVIEW',topic='Second Case',decision='Reuse current initial global Grants under original current checks, never old Case-specific records/markers. Do not require new principals/Grants for B or renew A deadlines.'),
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION_REVIEW',topic='Source identity',decision='Actual src contents excluding __pycache__ plus new launcher and both used lifecycle helpers; no .git dependency. No permission to alter old material-only behavior/state.'),
]
provenance=[
 dict(path='docs/sources/V1/平台产品设计 (2).md',lines=[93,100,385,389,422,428],finding='PR0-alpha local authorized loop, finite synthetic software work without real park inputs, explicit status/evidence and dependency-local blocking.'),
 dict(path='docs/sources/V1/分阶段开发计划 (2).md',lines=[51,53,89,90,98,102,364,370],finding='Runtime/identity/new-input/end-to-end/restart requirements; Linux evidence does not replace Windows native.'),
 dict(path='tests/test_ordinary_case_goal_results.py',lines=[26,35,38,50],finding='Existing start creates new preparation/request, actual REVIEW/CONFIRM and explicit original ADOPT, then ordinary resource/acceptance/receipt verification.'),
 dict(path='tests/test_service_case_steps.py',lines=[40,51],finding='adopt_body reads original /planning-preview current and adopt POSTs original service-case-plan; ordinary planning is already present.'),
 dict(path='scripts/material_only_demo.py',finding='Read-only baseline lifecycle reference: private Unix socket/new cluster/in-process receipt/exact child process cleanup. Existing source_binding requires Git and old authority hash omits SQL ACL; new contract cannot blindly inherit those limitations.'),
 dict(path='src/parkweave/case_fact_clarifications.py',lines=[404,423,491,517],finding='Original fresh live capture before CREATE and process-local receipt; no pre-existing target adoption or name/path-only authority.'),
 dict(path='scripts/linux_fixture_server.py',lines=[26,41],finding='Stop exact owned child references and retain unconfirmed stop; no arbitrary PID cleanup.'),
]
save('literal-oracle-plan.json',dict(schema=1,review='ordinary-synthetic-demo-20261018',baseline_sha=BASE,contract_commit=CONTRACT_SHA,contract_path=CONTRACT,frozen_at_utc=datetime.now(timezone.utc).isoformat(),status='WAITING_FOR_IMPLEMENTATION_FREEZE',oracle_origin='Independent original product/plan text and frozen contract; only fixed baseline lifecycle/positive-path semantics read. No WIP implementation inspected or tested.',inputs=inputs,oracles=oracles,preimplementation_clarifications=clarifications,provenance=provenance,future_bounded_groups=[
 dict(id='I01',oracles=['OSD-O01','OSD-O02','OSD-O05'],design='A real launcher-created new private state: exact empty business/3actor/2resource counts, actual technical ACL and original fresh receipt gate.'),
 dict(id='I02',oracles=['OSD-O03','OSD-O06','OSD-O07'],design='Actual normal API+worker original A loop, retained restart/cold read, new B input under original current global Grants; no direct Store.finish/owner business-write shortcut.'),
 dict(id='I03',oracles=['OSD-O04','OSD-O05','OSD-O08'],design='Finite retained-state/source/helper/technicalACL drift and occupied-port rejection; private Gitless mirror, no foreign-state adoption or repair.'),
 dict(id='I04',oracles=['OSD-O08','OSD-O09'],design='Narrow actual owned child startup/stop failure and expired-step observation; preserve exact process/response/failure evidence and private tokens without broad old-matrix reruns.'),
],execution=dict(project_imports=0,tests_run=0,database_instances_started=0,business_commands=0,network_requests=0,tracked_or_Git_mutations=0),limits=['Await final explicit implementation SHA and execution scope before any DB/test/process start.','Only private independent runtime writes; root remains sole controlled-source/Git writer.','No real authority/installation/credentials/model/browser/Windows/Native bypass.','No implementation P1/P2 sign-off and no full original AT/project acceptance.']))
save('baseline-input-manifest.json',dict(baseline_sha=BASE,contract_commit=CONTRACT_SHA,inputs=inputs))
save('contract-first-review.json',dict(status='ORACLE_FROZEN_WAITING_FINAL_IMPLEMENTATION_SHA',baseline_sha=BASE,contract_commit=CONTRACT_SHA,oracle_count=len(oracles),oracle_sha256=hashlib.sha256((OUT/'literal-oracle-plan.json').read_bytes()).hexdigest(),input_count=len(inputs),provenance=provenance,clarifications=clarifications,implementation_P1_P2='NOT_ASSESSED_WIP_NOT_READ',execution=dict(tests_run=0,project_imports=0,DB_started=0,processes_started=0,business_actions=0,network=0,controlled_file_or_Git_changes=0),remaining='Freeze/source review and bounded owned SYNTHETIC execution still pending. Real permissions/production install/Windows/formal AT35/physical service/model remain outside this oracle.'))
print(json.dumps(dict(oracle_count=len(oracles),input_count=len(inputs),oracle_sha256=hashlib.sha256((OUT/'literal-oracle-plan.json').read_bytes()).hexdigest(),report_sha256=hashlib.sha256((OUT/'contract-first-review.json').read_bytes()).hexdigest(),tests_run=0),indent=2))
