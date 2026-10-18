"""Freeze a contract-first review design; does not import or execute ParkWeave."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/ParkWeave')
OUT = Path(__file__).resolve().parent
BASE = '1f7e4d4a11606a511062fecb1863803209f3831d'
CONTRACT_COMMIT = '1ae1566076b269e9a79797f7ddc4f8b3643c5b47'
CONTRACT = 'docs/F2/OrdinaryCaseRecordRecheckContract-20261018.md'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def source(commit, path):
    data = git('show', commit + ':' + path)
    return dict(commit=commit, path=path, bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                git_blob=git('rev-parse', commit + ':' + path).decode().strip())

def save(name, obj):
    path = OUT / name
    if path.exists():
        raise RuntimeError('immutable oracle artifact already exists: ' + name)
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
    path.write_bytes(data)
    (OUT / (name + '.sha256')).write_text(hashlib.sha256(data).hexdigest() + '  ' + name + '\n')

inputs = [source(CONTRACT_COMMIT, CONTRACT)]
for path in [
    'docs/sources/V1/平台产品设计 (2).md',
    'docs/sources/V1/分阶段开发计划 (2).md',
    'docs/验收规格.json', 'docs/F1/ATBindings.json',
    'docs/F2/CaseLifecycleRecoveryContract.md',
    'docs/F2/CaseGoalResultsContract.md',
    'docs/F2/CaseRecordPackContract-20261017.md',
    'docs/F2/OrdinaryCaseStepContract-20261018.md',
    'docs/F2/OrdinaryCaseGoalResultsContract-20261018.md',
    'src/parkweave/case_lifecycle.py',
    'src/parkweave/ordinary_plan_sources.py',
    'src/parkweave/case_step_assignments.py',
    'src/parkweave/controlled_plans.py',
    'src/parkweave/service_case_steps.py',
    'src/parkweave/case_goal_results.py',
    'src/parkweave/business_frontier_types.py',
    'src/parkweave/api.py', 'src/parkweave/web.py',
    'tests/test_case_lifecycle.py',
    'tests/test_case_lifecycle_recovery.py',
]:
    inputs.append(source(BASE, path))

oracles = [
    dict(id='P5-O01', title='Explicit ordinary admission only',
         stimulus='Use the existing ordinary configured_app and exact same-Store CURRENT_PREPARATION service with already legitimate preparation, actors and grants.',
         expect='Original local-case read/command/recovery and P5 source use this explicit lane. No new principal, grant, Run assignment, policy, publication or approval is created.',
         negative='No ordinary DI, foreign Store/provider, legacy ISOLATED marker, active or inactive Run assignment, Native history and a mixed provider remain denied; an old denial never selects ordinary authority.'),
    dict(id='P5-O02', title='Original owner lifecycle sequence and explicit P5 VERIFY',
         stimulus='From actually current original P1-P4 business evidence and owner VERIFY events, explicitly REVALIDATE, CLOSE_LOCAL_RECORD, then VERIFY P5.',
         expect='Ledger uses original revision/cycle/event/request-key semantics. Close yields LOCAL_RECORD_CLOSED and Case WAITING_CONFIRMATION. P5 is a current verified local output only after the original owner VERIFY matches its current source.',
         negative='CLOSE, ledger flags, receipt prose or a mere verified_sha field cannot auto-VERIFY P5 or declare physical fulfillment. Original READY compatibility is preserved, not silently tightened to CLOSED-only.'),
    dict(id='P5-O03', title='Original evidence and plan gates stay effective',
         stimulus='Omit or stale one material REVIEW/CONFIRM, actual current resource link, ACCEPT/CREATE proof, submitted-and-owner-ACK receipt, original P1-P4 VERIFY, or leave an unresolved material objection.',
         expect='REVALIDATE/CLOSE and current P5 output fail or remain blocked under the existing gate; no step, goal, reservation, history or required goal is removed to make the request succeed.',
         negative='A synthetic setup or current DTO is not itself business evidence; ordinary admission grants no bypass of original owner verification.'),
    dict(id='P5-O04', title='Original absolute offer deadline and generation binding',
         stimulus='Change a bound actor grant generation, revoke and restore it, revise bound materials/catalogue, cross the original first-offer absolute deadline, or restart API/worker.',
         expect='No fresh P5 validation/close/VERIFY or current P5 source may rely on the expired or changed ordinary acceptance. First offer UUID and at-most-300-second deadline are preserved across restarts; restored grants do not revive the old generation.',
         negative='No REOPEN, current-source read, rebind or recovery renews a deadline, reoffers, reissues authority, or writes the manual receipt.'),
    dict(id='P5-O05', title='P1/P2-only consumer scope remains independent',
         stimulus='Read or verify an otherwise current P1-only/P2-only plan or goal while an unrelated ordinary offer expires during a real final lock wait.',
         expect='Unrelated ordinary deadline does not turn these original consumers into 403 or falsely block their current local output. P3/P4/P5 consumers retain their actual-source protections.',
         negative='Merely observing an ordinary marker must not attach the deadline to every Case read.'),
    dict(id='P5-O06', title='Resource time checked after final ledger wait',
         stimulus='Hold the lifecycle ledger lock, let a resource/hold or reservation window expire while a P5 read or VERIFY is waiting, then release the owned lock.',
         expect='The actual response or write evaluates database time after that wait. It cannot report CURRENT/LOCAL_OUTPUT_VERIFIED or commit a stale P5 VERIFY. Any failure preserves original business revisions and events.',
         negative='A pre-ledger _timed result, first source capture, or ordinary-only _live callback is insufficient evidence of current resource time.'),
    dict(id='P5-O07', title='Ordinary deadline checked after final lifecycle wait',
         stimulus='Hold the final original Case/ledger/operation lock and cross first-offer deadline during REVALIDATE, CLOSE, P5 VERIFY or goal-result retrieval.',
         expect='A current P5 operation is denied/blocked after the last wait, without invalid commit or false-current output; actual response and unchanged relevant business rows must be captured.',
         negative='No claim of commit-time atomicity beyond the implemented last-admission check; observing a timeout or missing HTTP response alone is not a semantic result.'),
    dict(id='P5-O08', title='Current ledger requires original immutable proof',
         stimulus='Keep or forge a matching ledger state/snapshot SHA while the corresponding original REVALIDATE or latest CLOSE event/request fingerprint, actor, scope, IDs, revision/cycle, snapshot or payload is absent or inconsistent.',
         expect='Current lifecycle/P5 cannot certify a valid current local record from ledger fields alone. The reused original proof rejects corruption and preserves historical source/event bytes.',
         negative='Do not implement a second event verifier from a copied algorithm or accept a self-consistent rehash as proof of the original request.'),
    dict(id='P5-O09', title='Owner history separates EXECUTE from READ/PREPARE',
         stimulus='After a valid close, remove only owner EXECUTE while retaining current required owner READ/PREPARE and all resource READ scopes.',
         expect='Owner historical read/recovery remains readable with write controls disabled; all lifecycle writes, new P5 VERIFY and original POST replay are denied. Restoring capability does not change original offer deadline or generations.',
         negative='Removing owner READ/PREPARE must deny. Historical-resource READ required by original recovery is not bypassed by the phrase historical access.'),
    dict(id='P5-O10', title='Executor and reviewer limits remain original',
         stimulus='Use the accepted executor and the currently assigned reviewer against lifecycle read/command/recovery, whole-plan/goal-results and record pack.',
         expect='Executor gains no whole Case, P5, goal-results, pack or Run read; no role can owner-VERIFY or close for the owner. Reviewer sees only the original allowed responsible status, without newly expanded source snapshots, receipt/material bodies or private event payloads.',
         negative='CaseStep acceptance or a marker never confers whole-Run READ, owner role or cross-Case scope.'),
    dict(id='P5-O11', title='REOPEN after invalid old dependencies does not renew them',
         stimulus='After close, expire or revoke old ordinary executor dependencies, then explicitly REOPEN as a currently authorized owner.',
         expect='Original REOPEN may succeed despite old-source invalidity, increments cycle, sets REOPENED, clears current validation and retains all old events/evidence. No reservation is released, receipt rewritten, offer replaced, deadline extended or authority reissued. A subsequent REVALIDATE still needs original current prerequisites and therefore cannot reuse expired acceptance.',
         negative='Do not register an old P5 _live callback for REOPEN merely because an old ledger or marker exists.'),
    dict(id='P5-O12', title='Original-key cold recovery stays historical and read-only',
         stimulus='Cold restart after each of REVALIDATE, CLOSE and REOPEN; GET each original actor/key before and after a later cycle or dependency change.',
         expect='COMMITTED returns the exact original receipt/action/revision/cycle and the current projection separately. Old original_is_current_version becomes false after a later operation; NOT_OBSERVED remains unknown. Repeated GETs do not POST, revalidate, close, reopen, restore a cycle or mutate business tables.',
         negative='Current invalidity never erases a valid original COMMITTED event; corruption/scope mismatch is rejected rather than silently treated as NOT_OBSERVED.'),
    dict(id='P5-O13', title='Recovery compatibility is truthful about original proof',
         stimulus='Recover a historical valid REOPEN including the legacy permitted ignored optional expected_snapshot_sha256, plus original validation and close events.',
         expect='REVALIDATE/CLOSE reconstruct the exact saved original source SHA and request fingerprint. REOPEN preserves original structural proof and documented inability to reconstruct its optional ignored body field; it does not invent or retroactively tighten historical proof.',
         negative='A current forged REOPEN or inconsistent event coordinate is not accepted merely because a legacy optional body field was not reconstructible.'),
    dict(id='P5-O14', title='CAS, key conflicts, concurrency, rollback and history bounds',
         stimulus='Repeat the same key/body; use same key/different fingerprint; race close/reopen against stale expected revision/cycle; fail an event insert; reach original history/cycle limits.',
         expect='Original idempotency, bounded 64-revision history and reopen headroom remain. Stale/conflicting requests do not both commit; event failure rolls back ledger and Case state; no previous event or later cycle is overwritten.',
         negative='This small slice reuses existing concurrency/rollback algorithms and does not claim their whole historical matrix was rerun.'),
    dict(id='P5-O15', title='Original current results and TXT pack remain a limited record index',
         stimulus='After explicit current P5 VERIFY, read original goal-results and generate/download the original TXT via a cold configured_app and full original HTML flow; then invalidate sources/reopen.',
         expect='Allowed P5 output references actual lifecycle cycle/revision/revalidation evidence with original owner VERIFY and current dependencies. The pack follows existing re-read/hash/whitelist and clears changed/forbidden results. History and all required goals remain visible; no material/receipt body, credential or private full source snapshot is exported.',
         negative='LOCAL_OUTPUTS_VERIFIED is local SYNTHETIC evidence only. case_goal_completed=false, qualification NOT_EVALUATED, external NOT_SUBMITTED, offline NO_EVIDENCE. No formal AT35 or physical service completion claim.'),
    dict(id='P5-O16', title='Original UI intent and cold-unknown boundaries',
         stimulus='Use original controls for explicit REVALIDATE/CLOSE/P5 VERIFY/REOPEN and original opaque recovery handles; switch Case/identity while original GET or POST recovery is in flight.',
         expect='Original explicit commands and GET-only unknown recovery remain separate; current 403 clears private views while recovery handles survive. Late success/denial cannot replace a new Case/identity view; no automatic business resend, silent VERIFY, localStorage token/body or goal reduction occurs.',
         negative='HTML NodeVM and owned Linux HTTP are bounded engineering evidence; browser/Windows/formal AT35/real sources/init remain NOT_RUN.'),
]

plan = dict(
    schema=1, review='ordinary-case-record-recheck-20261018',
    frozen_at_utc=datetime.now(timezone.utc).isoformat(), baseline_sha=BASE,
    contract_commit=CONTRACT_COMMIT, contract_path=CONTRACT,
    status='WAITING_FOR_IMPLEMENTATION_FREEZE', tests_run=0,
    project_imports=0, database_instances_started=0, test_processes_started=0,
    oracle_origin='Literal original product/AT and frozen contract; baseline code read only to identify original compatibility boundaries, not to generate expected values.',
    code_under_review='No implementation sign-off; root worktree implementation intentionally not read or executed by this design freeze.',
    inputs=inputs, oracles=oracles,
    bounded_future_probe_groups=[
        dict(id='I01', scope=['P5-O01','P5-O02','P5-O03','P5-O10','P5-O15'],
             design='Original HTTP full path and hostile roles/default lane; use true owned original records and inspect exact outputs, not a synthetic alternate workflow wrapper.'),
        dict(id='I02', scope=['P5-O08','P5-O12','P5-O13'],
             design='One original-event corruption composite against a valid current ledger and original-key cold recovery; preserve original failed diagnostics and reject false current P5 proof.'),
        dict(id='I03', scope=['P5-O09','P5-O11','P5-O12'],
             design='Owner EXECUTE historical split, executor dependency invalidity, authorized explicit REOPEN, failed stale revalidation and original-key GET-only recovery; compare business snapshots.'),
        dict(id='I04', scope=['P5-O04','P5-O06','P5-O07'],
             design='Real owned PG lock wait crossing an original ordinary/resource deadline. Record exact waiter identity, database time and actual HTTP status/detail, not inference from a missing response.'),
        dict(id='I05', scope=['P5-O05','P5-O14'],
             design='Narrow original P1/P2-only current source scope and one suitable original CAS/key-conflict boundary; do not rerun historical full matrices.'),
        dict(id='I06', scope=['P5-O12','P5-O15','P5-O16'],
             design='Cold ordinary app/original full HTML close-reopen-P5/result/TXT read path and original unknown-recovery handle behavior, with minimal meaningful root-selector overlap.'),
    ],
    future_execution_limits=dict(
        require_parent_frozen_sha=True, private_git_archive=True,
        shared_and_mirror_pre_post_hashes=True, origins_and_phases_and_junit=True,
        preserve_every_failure_and_controller_version=True,
        overlap_separate_and_unique_nodeids=True,
        no_tests_before_freeze=True, no_tracked_or_git_mutation=True,
        no_real_authority_identity_grant_assignment_publication_approval_credentials=True,
        no_browser_windows_formal_at35_model_install_root_seal=True,
        no_prior_39_or_prior_slice_matrix_reruns=True),
    pending_clarifications=[
        'P5 READY and LOCAL_RECORD_CLOSED original compatibility is retained; the target demonstration explicitly closes before VERIFY.',
        'Historical expiry/dependency-revocation readability still requires current owner READ/PREPARE and original required resource READ.',
        'Legacy REOPEN complete optional body fingerprint cannot be reconstructed; preserve original structural proof truthfully.',
    ])
save('literal-oracle-plan.json', plan)
save('baseline-input-manifest.json', dict(schema=1, baseline_sha=BASE, contract_commit=CONTRACT_COMMIT, inputs=inputs))
print(json.dumps(dict(oracle_count=len(oracles), inputs=len(inputs), tests_run=0,
                     oracle_sha256=hashlib.sha256((OUT/'literal-oracle-plan.json').read_bytes()).hexdigest()), indent=2))
