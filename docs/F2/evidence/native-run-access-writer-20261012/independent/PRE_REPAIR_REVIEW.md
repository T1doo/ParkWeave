# Independent writer review before repair

**BLOCKED** — source `77e8e98b98bd1ad6d6aebc5e684f450ce2b56b5a`. All 420 selected source/contract files matched this commit before and after each actual window; manifest SHA256 `46e2d256356b3f79525464d883e5039ee43c8ec08a87b2448e7c355bd9ad82fb`.

The complete writer and offline NodeVM modules actually passed **60/60**, exit0, 72.916 process seconds. The separate independent probes finished **7PASS/2FAIL**, exit1. A further baseline-byte-exact command compatibility probe finished **0PASS/1FAIL**, exit1, after three separately preserved probe setup/oracle failures. These are separate windows and no root or old review results transfer.

## Blocking findings

1. **W1 HIGH**, `native_run_access.py:225–231`: an app-written valid-shaped unsigned REQUEST changes the metadata reader via `request.target_id`. The existing same-tenant unassigned executor changes from403 to200, despite `writer_history_verified=false`. Business access remains false, but the private ledger/source is disclosed outside the independently selected participant policy.
2. **W2 MEDIUM**, `native_run_access.py:377–391`, `web.html:1084–1086`: original-key GET returns a valid-shaped unsigned event with `found=true` and no receipt authentication state. The UI can clear its unknown original operation using that unissued event. Preserve legitimate authorized historical reads through transport loss, but distinguish authenticated receipt from untrusted storage and retain UNKNOWN when proof cannot be authenticated.
3. **W3 MEDIUM**, `native_run_access.py:419–445`: the newly added optional `confirm_request:null` changes the canonical fingerprint for a pre-writer command. A receipt created by byte-exact9ea Native code and SQL rejects identical originalkey/original fields in current code. The explicit `prior.writer=None` adapter only supports the current activation projection; the old command source was unedited. Keep the old omitted-field canonical for legacy nonwriter requests while maintaining strict confirmed writer fingerprint semantics.

## Preserved failed evidence

`frozen-complete/precheck.json` records the original overstrict clean-worktree wrapper exit1 before tests: a legal new untracked root evidence directory caused the assertion. The corrected runtime-data-directory call then finished **9PASS/51setupERROR** because the existing creation-proof guard correctly refused a non-`/tmp` PG data directory. The guard was retained and that creation-proof action stopped; the subsequent60PASS used a new explicitly owned `/tmp` fixture under the original contract.

The three early legacy windows preserve their actual1FAIL each: current DTO reparsing could not simulate old canonical; the copied baseline module initially lacked its relative SQL file; and the old class lacked a `writer` attribute needed by current projection glue. None is a product defect or an access-denial recovery. The final adapted baseline probe reaches the actual fingerprint conflict and is W3. See `PRE_REPAIR_REVIEW.json` for every raw window/count/hash and classification.

## Boundary

The contract and InstallationPlan honestly keep production startup/installation, restricted writer role, external key source and production OS isolation unimplemented/unverified. The reference uses original issued owned-fixture owner authority with a separate real writer process. API instances hold app DSN/public pins, and private Context binding is now rejected. A policy expiry closes all new commands; an earlier lease expiry can still be revoked while the external policy remains live. No production permissions, SQL GRANT, business Grant/registry, browser, paid model, Windows IPC or formal AT35 was run.

Root must repair W1/W2/W3 and freeze a new source before independent repair verification and final limited signoff. All prior architecture reports, signed reviews and original raw bytes remain unchanged.
