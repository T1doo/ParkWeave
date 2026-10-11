# Independent alternative-time search review

**PASS within the executed scope; no remaining blocker found.** Final reviewed and tested source is `f9bf9b76b512eb98ce23f92beba2fc4327e0b8a1`, direct parent `3e0c51eac33cd3ea017fee9b6361785c786daca7`, original business baseline `a954bf6811e395d7515181f8bad8dd8f12d1cd7c`. Read-only HEAD checks before and after execution matched the final source; the worktree was clean. The reviewer wrote only this private /tmp directory and owned fixture databases; no repository or Git mutation occurred.

## Actual new independent execution

**38 passed, 0 failed, 0 errors, 0 skipped**, 6.72 seconds: 22 owned synthetic PostgreSQL/in-process ASGI probes and 16 offline Node VM probes. These are independently authored probes; root suites and previous slices are not counted. The two warnings are the existing Starlette testclient deprecation and platformdirs XDG runtime fallback. Command:

```text
/tmp/parkweave-summary-venv/bin/python -m pytest -q -o pythonpath='src tests' --confcutdir=/tmp/parkweave-alternative-times-independent-review /tmp/parkweave-alternative-times-independent-review/test_alternatives_independent.py /tmp/parkweave-alternative-times-independent-review/test_alternatives_vm_independent.py --junitxml=/tmp/parkweave-alternative-times-independent-review/final-f9bf9b76.xml
```

The original owned fixture is explicitly imported through private conftest and retains its database cleanup fixture. No HTTP listener or browser was started.

## Findings and tested evidence

The original product resource section is `docs/sources/V1/平台产品设计 (2).md` §5.4, lines159–169: alternatives after scarcity, stable locks, UTC/buffers and separate preview/hold/confirmation. This implementation supplies same-resource time suggestions on an explicit anchored grid, not alternate resources or the entire original acceptance requirement.

- Three quantity cases independently calculate peak occupancy by sampling each constant-occupancy segment midpoint, rather than copying the implementation's sweep algorithm. Six real owned holds have different original buffer values. Exact earliest results, counts, truncation, anchor, duration and quantity agree with that independent oracle.
- A real exclusive advisory lock is held by an owner transaction. The independent reader announces its backend before calling the original shared lock; an observer queries `pg_stat_activity` and asserts `wait_event_type == 'Lock'` while the reader is unfinished. After committing changed capacity, buffer and revision, the reader returns those committed values and `server_time >=` the owner's immediately-before-release database time. This is an observed lock wait, not an injected delay or listener test.
- Searches succeed with EXECUTE and resource HOLD grants revoked while current READ remains. Five denial cases cover resource READ, global READ, inactive principal, changed tenant and unknown resource; all return the exact generic 403 without resource identity echo. SQL audit observes only SELECT/SET, and snapshots of resource, grants, holds, receipts, combinations, preparation/Case, service receipt, outbox and principal/capability tables remain identical for the audited searches. Expired HELD and RELEASED are excluded, whereas CONFIRMED still occupies capacity without cleanup writes.
- Both datetime buffer extrema return a bounded empty grid. Eight UTC conversion overflow cases cover every date field at minimum/maximum offset and return validation422, not an uncaught exception. A one-candidate window and the actual maximum96-candidate 24-hour grid are checked.
- Fifteen handler VM cases exercise detached old result buttons, draft/search changes, identity ABA, late JSON and403, current403 clearing, TTL/purpose changes, invalid result positions/duplicates/bool quantities, explicit selection without automatic writes, and empty/truncated wording.
- The new sixteenth VM case executes actual `bundleHandles`, `bundleLocked` and `bundleControls`, not a stubbed lock predicate. Current actor unknown handle, malformed stored handle and busy states all retain disabled original preview/HOLD/combination controls and enable only the new search button. A native-disabled click gate then invokes search, produces one read-only POST, and renders a result while HOLD remains disabled. Requests contain neither Idempotency-Key nor purpose/TTL. The original handler-level unknown-state case alone does not establish integrated button availability.

## Historical defect and correction

The previous frozen source3e ran 37 independent probes successfully in6.61 seconds. Those results remain separate in `historical-3e/` and are not reused as final-source passes. Root's subsequent actual-controls negative probe found that unknown combination state physically disabled the new search button. Independent static review confirmed the exact `bundleControls` loop; the previous handler harness had bypassed that controls integration. Accordingly3e was blocked for final UI acceptance. Root retained its actual failing reproduction separately; no independent failing test is invented or counted here.

Final sourcef9 adds only explicit `resource-alternatives.disabled=false` after the original controls are disabled, plus its corresponding root integration test. The independent final38 reran every earlier probe and the added actual-controls case. No failures occurred in either independent execution. `REVIEW-3e.md` records the historical limitation.

## Static boundary review and limitations

Relative to the original business baseline, runtime changes are confined to resource_holds.py, api.py and web.html. The added API delegates to the new strict model and read-only function. Existing auth, READ/HOLD grant checks, advisory lock, database clock and capacity calculation are reused. The resource READ scope is checked again after the resource lock. Existing HOLD/confirm/receipt and write gates are unchanged; extracting the two active-resource guards preserves their original `_window` behavior. No migration, roles, grants, authority configuration, preview SQL, registry or trust-loader changes exist. The other tracked runtime sources have identical Git blobs, recorded in verification.json.

The search is limited to the stated 15-minute grid over at most24 hours. Positive duration means at most96 starts; scan_limit100 is defensive and actual100-limit truncation was not triggered or claimed. Empty search does not prove all instants unavailable. Capacity and time are observed under the existing cooperating resource lock and database clock, not a long-lived reservation/MVCC promise. Suggestions neither grant HOLD nor guarantee later capacity; choosing one only changes the draft and clears preview, requiring the original explicit preview and write actions.

This review does not claim a real browser, Windows, multiworker, full AT09/10/11/29 or entire F2 acceptance, external resource booking, physical fulfillment, production authorization, or persistent trust registration. No browser, listener, external network, real model, credential/security operation, or old restricted execution/receipt proof chain was used. The original browser `data: ERR_BLOCKED_BY_ADMINISTRATOR` restriction remains intact.
