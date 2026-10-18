"""Contract-first literals only; no project imports, DB or test execution."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,subprocess

BASE='a9c725babd36561a6a25733953cc374ee1b77bd5'
CONTRACT_COMMIT='1c430b61b223620d152df2ae78e0732f536ed423'
CONTRACT='docs/F2/ExistingPreparationAccessContract-20261018.md'
ROOT=Path('/workspace/ParkWeave');OUT=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def source(commit,path):
    raw=git('show',commit+':'+path)
    return dict(commit=commit,path=path,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),git_blob=git('rev-parse',commit+':'+path).decode().strip())
def save(name,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    with (OUT/name).open('xb') as f:f.write(raw)
    with (OUT/(name+'.sha256')).open('x') as f:f.write(hashlib.sha256(raw).hexdigest()+'  '+name+'\n')

inputs=[source(CONTRACT_COMMIT,CONTRACT)]
for path in [
 'docs/sources/V1/平台产品设计 (2).md','docs/sources/V1/分阶段开发计划 (2).md',
 'docs/F1/ATBindings.json','docs/验收规格.json',
 'src/parkweave/cli.py','src/parkweave/store.py','src/parkweave/preparation.py',
 'src/parkweave/migration-004.sql','src/parkweave/migration-009.sql','src/parkweave/roles.sql',
 'src/parkweave/catalog_publication.py','src/parkweave/controlled_plans.py',
 'src/parkweave/permissions.py','src/parkweave/case_step_assignments.py',
 'src/parkweave/ordinary_plan_sources.py','src/parkweave/native_run_access.py',
 'src/parkweave/native_run_access_writer.py','scripts/windows/Setup.ps1','scripts/windows/lifecycle.py',
]:inputs.append(source(BASE,path))

oracles=[
 dict(id='EPA-O01',title='Strict bounded reference-only JSON',
  stimulus='Supply exact existing owner/reviewer/domain/catalog references and a bounded reason; alternatively unknown or repeated keys at any nested level, extra capability lists, credential/hash/DSN/path/SQL fields, malformed types including boolean-as-version, or oversized input.',
  expect='Only the finite reference config is accepted. Invalid config is rejected before business writes and cannot create entities, choose arbitrary SQL/permissions or expose raw input/credentials in errors. Reason is bound by the plan hash and never echoed as free text.'),
 dict(id='EPA-O02',title='Default is an actual read-only dry-run',
  stimulus='Run prepare-access --config FILE without --apply, including missing/blocked/no-change target states.',
  expect='Use a genuine READ ONLY transaction and only inspect current state/differences. Zero INSERT/UPDATE/DELETE/DDL, authorization_audit writes, session issuance, schema install or startup repair. Do not use FOR SHARE/FOR UPDATE row locking in this path. No transaction or missing permission exception implies approval.'),
 dict(id='EPA-O03',title='Only existing exact current subjects and capabilities',
  stimulus='Use active same-domain enterprise_operator owner and park_specialist reviewer with pre-existing owner READ/EXECUTE and reviewer READ; then omit/deactivate/change role/domain/capability.',
  expect='Only the exact current prerequisites pass; all missing or mismatched rows block. No principal, capability/action/resource/Run grant, token, directory or material is created or reactivated. Existing role and scope checks are reused.'),
 dict(id='EPA-O04',title='The original preparation-grant key determines missingness',
  stimulus='For each target principal/capability, supply no row, active same-scope row, inactive row, or same primary key with wrong park/org.',
  expect='Only truly absent original keys are insert candidates: owner PREPARE and reviewer REVIEW_ASSIGNED. Active same-scope rows are preserved. Inactive or wrong-scope same-key rows block the entire apply; no UPDATE, ON CONFLICT repair, deletion or resurrection. One existing valid row means at most the other missing row is inserted.'),
 dict(id='EPA-O05',title='Existing catalogue proof is consumed, never published',
  stimulus='Reference the exact original supported service/version/park, namespace SYNTHETIC and qualification NOT_EVALUATED, with original publication proof and binding_catalog_known; try unknown/withdrawn/corrupt/changed/wrong-version source.',
  expect='Reuse the original proof and known-source rules. A valid original explicit SYNTHETIC catalogue without a journal remains supported when the original proof returns None; no forced INIT/PUBLISH or new source is invented. All bad or missing current references block and no catalogue field/history is modified.'),
 dict(id='EPA-O06',title='Grant scope is represented truthfully',
  stimulus='Inspect planned/applied scope and use original owner/reviewer business endpoints afterward.',
  expect='The two grants have original principal+park/org+capability scope, not a single catalogue/Case restriction. Original owner-only and responsible-reviewer Case checks remain current on every request; config catalogue reference is a source fence, not a substitute narrowing or broadening of business authorization.'),
 dict(id='EPA-O07',title='Apply needs both explicit fence intent and actual owner authority',
  stimulus='Request --apply with correct expected-plan SHA from a real direct database owner; alternatively omit/malform SHA, use the normal app role, merely grant INSERT, SET ROLE, or claim admin in config.',
  expect='Only explicit apply plus the exact current fence and actual session_user=current_user=database owner with ownership of relevant original public tables can write. A SHA, role flag, INSERT privilege, superuser label without the selected owner identity, or config text is not authorization. Normal app denial remains even if INSERT is accidentally available.'),
 dict(id='EPA-O08',title='Management context is separate from runtime providers',
  stimulus='Use an existing application/provider-bound Store or mixed Native/isolated/ordinary service context instead of a fresh direct owner Store.',
  expect='Reject the mixed context; no fallback from a Native/default refusal, fixture permit or application actor to administrator rights. Runtime configured_app/worker do not auto-discover/call this command. No roles/schema/conftest changes or real installation are required or executed.'),
 dict(id='EPA-O09',title='Plan SHA is a current-state fence, not approval',
  stimulus='Dry-run the same semantic config on the same actual endpoint/database/state, then change config/reason, database endpoint/OID/name/postmaster-start, relevant principal/capability/preparation-grant xmin or catalogue content/generation.',
  expect='A matching fence binds the normalized config and selected current state; each relevant change invalidates the old SHA. Credentials/token hashes/material bodies/DSN strings are not exposed or included as credentials in the plan. Actual endpoint+database OID/name+postmaster start is a bounded state fence, not a cryptographic instance identifier, signature, Approval or Native permit; no pg_control_system/root/seal privilege is added.'),
 dict(id='EPA-O10',title='Apply acquires original locks before its final fresh decision',
  stimulus='Apply while another owned transaction holds a relevant principal/row/catalogue lock, then alter the relevant state before releasing the wait.',
  expect='Take original principal exclusive advisory locks in stable ID order, acquire required row/catalogue locks in deterministic order, and re-read all required generations/source/owner state after every admission wait before comparing the expected SHA and writing. Never compare a pre-wait cached plan as the final fence.'),
 dict(id='EPA-O11',title='ABA and conflicting administration are rejected atomically',
  stimulus='Revoke/restore or replace a relevant row between dry-run and apply; concurrently attempt the same missing keys or introduce an inactive/wrong-scope key.',
  expect='Changed xmin/current state makes the old SHA stale, or an original uniqueness/lock conflict cleanly rejects/rolls back. No partial grant/audit set, ignored conflict or automatic retry that silently accepts the new state. Trusted-admin uncooperative rewriting/deleted historical revocations are not claimed detectable.'),
 dict(id='EPA-O12',title='Original audit and both inserts share one transaction',
  stimulus='Apply a valid two-missing-grant plan; fail the second insert or original audit, or inspect the audit record.',
  expect='All required grant inserts and original authorization_audit records commit together or all roll back. Audit uses actual beneficiary principal, operation/specific capability/plan SHA and ALLOWED; it does not invent an application-admin identity or log reason/config/secrets. No new audit schema or alternate authorization engine.'),
 dict(id='EPA-O13',title='NO_CHANGE and old-plan reuse are not false issuance or recovery',
  stimulus='After a successful apply, repeat the previous expected SHA, then take a new dry-run of the already active same-scope grants.',
  expect='The pre-insert SHA is stale after new xmin generations. A current no-difference plan returns NO_CHANGE without claiming a new grant. No persistent original-key receipt is invented, no automatic exact-request idempotency or cold-recovery guarantee is claimed, and existing valid grants remain byte-identical.'),
 dict(id='EPA-O14',title='Commit connection failure leaves an unknown outcome',
  stimulus='Lose the client/connection around transaction commit or receive an ambiguous transport error.',
  expect='Report that the result is unconfirmed, never assert no commit solely from a connection exception, and never automatically replay apply. A new read-only dry-run can inspect current state; it is not an immutable receipt proving which original invocation committed. Errors do not echo credentials or raw config.'),
 dict(id='EPA-O15',title='Applied prerequisites feed the original user flow',
  stimulus='In an explicitly owned synthetic test initial state containing existing legal subjects/capabilities/catalogue, add only the two missing preparation grants, then use original preparation HTTP entry/material REVIEW/CONFIRM and cold startup.',
  expect='Original current identity/Case/source algorithms consume the resulting grants; ordinary startup still does not seed or install. Principals/capabilities/catalogue/Run access/Native/provider/receipt resources remain unchanged. This finite code path is not a real management execution or formal end-to-end AT35.'),
 dict(id='EPA-O16',title='New grant generations never revive an old CaseStep marker',
  stimulus='In owned negative data only, delete/reinsert a previously bound preparation grant through the proposed missing-key workflow, or restore a row after an original marker was issued.',
  expect='Original CaseStep current-generation checks still reject the old marker. The initializer need not infer deleted revocation history, but must never reset or rewrite a marker, UUID, original deadline, actor generation, receipt or lifecycle to revive it. Broader real subjects/catalogue/executor/resource initialization and Windows/formal installation remain separate gaps.'),
]

clarifications=[
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION',topic='Owner authority',decision='Fresh direct owner context; actual database owner=session_user=current_user and relevant original public table owners; reject runtime/provider-bound Store. No new fixture authority.'),
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION',topic='Dry-run/catalogue/audit',decision='Genuine READ ONLY and no row locks/audit. Preserve valid original no-journal SYNTHETIC catalogue. Audit principal is beneficiary, not invented application administrator.'),
 dict(status='PARENT_ACCEPTED_BEFORE_IMPLEMENTATION',topic='Instance fence',decision='Actual connection endpoint hashed internally, database OID/name and pg_postmaster_start_time. No pg_control_system, OS seal/root or new privilege. State fence only, no cryptographic identity or physical commit-time guarantee.'),
 dict(status='DOCUMENT_REFERENCE_CORRECTION_REPORTED',topic='Original section labels',decision='Frozen V1 product line317 is section9.3; plan line325 is section11 and line366 section13. Contract line anchors and actual source text are used rather than the mistaken chapter numbers. A later mechanical citation correction may be recorded as a frozen diff; this oracle is not overwritten.'),
]
save('literal-oracle-plan.json',dict(schema=1,review='existing-preparation-access-20261018',frozen_at_utc=datetime.now(timezone.utc).isoformat(),baseline_sha=BASE,contract_commit=CONTRACT_COMMIT,contract_path=CONTRACT,status='WAITING_FOR_FROZEN_IMPLEMENTATION',oracle_origin='Independent literal original product/AT requirements and frozen contract; baseline code only bounds existing semantics, never supplies generated expected answers.',oracles=oracles,inputs=inputs,parent_preimplementation_clarifications=clarifications,execution=dict(project_imports=0,tests_run=0,database_instances=0,business_commands=0,network_requests=0,tracked_or_Git_mutations=0),bounded_future_groups=[
 dict(id='I01',oracles=['EPA-O01','EPA-O02'],design='Strict nested duplicate/unknown/credential-shaped config plus genuine read-only dry-run and complete business/authorization/audit snapshot.'),
 dict(id='I02',oracles=['EPA-O03','EPA-O04','EPA-O05','EPA-O06'],design='Small current-state matrix: missing/active/inactive/wrong-scope keys; exact original no-journal and invalid catalogue; no entity import/publication.'),
 dict(id='I03',oracles=['EPA-O07','EPA-O08','EPA-O09'],design='Actual owned owner versus original app connection and a mixed provider; exact database/fence changes; never grant the app INSERT merely to bypass a guard.'),
 dict(id='I04',oracles=['EPA-O10','EPA-O11','EPA-O12'],design='Real owned PG lock wait with relevant generation change; exact stale rejection and original two-insert/audit rollback, using no new schema/roles.'),
 dict(id='I05',oracles=['EPA-O13','EPA-O14'],design='Success/old SHA/current NO_CHANGE and a narrowly instrumented commit-uncertainty path with no auto-replay; preserve precise actual outcome versus unknown.'),
 dict(id='I06',oracles=['EPA-O15','EPA-O16'],design='One original preparation user/cold-read chain from existing synthetic principals and current capabilities, plus old-marker generation refusal; no old P5 matrix.'),
],limits=['No WIP implementation read or sign-off. Wait for final SHA before owned PG/tests.','Only private runtime writes; root sole tracked/Git writer.','No real identity/Grant/assignment/publication/approval/credential/install or broader authorization.','No roles/schema/conftest mutation, real browser/Windows/model/root/seal retry.','No old P5 42-node whole-slice rerun or transferred counts.']))
save('baseline-input-manifest.json',dict(schema=1,baseline_sha=BASE,contract_commit=CONTRACT_COMMIT,inputs=inputs))
save('contract-first-review.json',dict(status='ORACLE_FROZEN_WAITING_IMPLEMENTATION_SHA',baseline_sha=BASE,contract_commit=CONTRACT_COMMIT,oracle_count=len(oracles),oracle_sha256=hashlib.sha256((OUT/'literal-oracle-plan.json').read_bytes()).hexdigest(),input_count=len(inputs),implementation_P1_P2='NOT_ASSESSED_NO_FROZEN_IMPLEMENTATION',parent_preimplementation_clarifications=clarifications,baseline_evidence=[dict(path='src/parkweave/cli.py',lines=[13,24,34],finding='Only migrate/fixed enterprise seed/revoke routes; no existing-preparation access configuration.'),dict(path='src/parkweave/migration-009.sql',lines=[9,12],finding='Preparation grant primary key is principal+capability; wrong domain cannot be interpreted as a new key.'),dict(path='src/parkweave/store.py',lines=[83,95,374,386,840,842],finding='Direct versus provider-managed connections, original principal lock and current-capability checks, original four-field audit.'),dict(path='src/parkweave/catalog_publication.py',lines=[82,88,129,135],finding='Original proof permits no journal; snapshot attaches a descriptor only if non-None.'),dict(path='src/parkweave/controlled_plans.py',lines=[119,120],finding='Original known catalogue requires explicit SYNTHETIC source and ACTIVE cooperative state.'),dict(path='scripts/windows/lifecycle.py',lines=[399,407],finding='Original Windows candidate migrates/roles and optionally fixed enterprise seed; not this missing existing-subject preparation configuration. No execution attempted.')],execution=dict(tests_run=0,project_imports=0,DB_instances=0,business_commands=0,network=0,tracked_or_Git_mutations=0),read_path_failure=dict(target=BASE+':scripts/Setup.ps1',outcome='git128 path absent; actual original is scripts/windows/Setup.ps1 and calls scripts/windows/lifecycle.py setup. Read-only lookup error, not a business test or permission denial.'),remaining=['Await frozen implementation SHA; no implementation sign-off yet.','Real subject mapping/legitimate source/catalogue publication/executor and resource administration/production schema installation/Windows formal AT35 are not completed by this limited code contract.']))
print(json.dumps(dict(oracle_count=len(oracles),input_count=len(inputs),oracle_sha256=hashlib.sha256((OUT/'literal-oracle-plan.json').read_bytes()).hexdigest(),report_sha256=hashlib.sha256((OUT/'contract-first-review.json').read_bytes()).hexdigest(),tests_run=0),indent=2))
