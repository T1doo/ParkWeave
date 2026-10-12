# Single isolated Linux trial: FAIL

The one explicitly approved public GitHub standard `ubuntu-24.04` VM trial ran once and failed. Frozen trial source: `86bd07ef65135d749d6f0f9e9ae43039c4bd8fc8`; accepted business/adapter base: `ac7d83ed50190673f10c598e472861312491bcb0`. Dedicated branch: `dev/f2-restricted-linux-trial-20261012`. This report changes no runtime code and does not authorize a second trial.

[Actual run 38256730195](https://github.com/T1doo/ParkWeave/actions/runs/38256730195), [job 114836607019](https://github.com/T1doo/ParkWeave/actions/runs/38256730195/job/114836607019): completed/failure, push, run number 1, attempt 1. GitHub created the run at 13:35:20 UTC; the allowlisted failure appeared at 13:35:42 UTC on 2026-10-12. The initial normal branch push and exact remote SHA readback succeeded. No rerun, dispatch, PR, main update, deployment or paid service was requested.

| Observation | PASS | FAIL | ERROR | SKIP | NOT_RUN |
| --- | ---: | ---: | ---: | ---: | ---: |
| Root frozen pure contract/adapter/diagnostics | 166 | 0 | 0 | 0 | — |
| Independent original pure window | 169 | 3 | 0 | 0 | — |
| Independent corrected seal-observation window | 3 | 0 | 0 | 0 | — |
| Actual isolated VM case projection | 3 | 1 | — | — | 13 |

These are separate invocations, with overlapping shared pure cases. Counts are not added. The independent original three failures occurred before worker code because local Python lacked `fcntl.F_SEAL_SEAL`; original stdout, XML and probe remain preserved. A separate probe explicitly supplied synthetic Linux seal constants and passed. That correction was pure observation testing, with no physical FD issuance or local privilege changes.

Actual PASS: `REAL_IDENTITIES`, `FRESH_CLUSTER`, `OWNED_STOP`. Actual FAIL marker: `ACTUAL_ROLE_ACL`, phase `PG_SETUP`, closed error category `CHECK_FAILED`, cleanup `true`. This marker means the setup stage did not complete; it does not establish which SQL privilege or helper check failed. The specific internal cause is UNKNOWN because VM private diagnostics were deliberately not uploaded or retrieved.

Actual NOT_RUN: `PROTECTED_RUNTIME`, `HOST_CHANNELS`, `API_PRIVATE_BOUNDARY`, `EXPLICIT_BIND`, `EVENT_ROLLBACK`, `REAL_PARENT_LOCK`, `REQUEST_APPROVE`, `ACTIVATION_ROLLBACK`, `LOST_RESPONSE_GET`, `COLD_REBIND`, `LEASE_EXPIRY`, `CHANGED_SOURCE_REVOKE`, `NO_RENEWAL`. Bootstrap copied protected source/interpreter/dependencies before the controller ran, but the adapter's protection validation was not reached. Preparation work is not a physical acceptance PASS. Dual sockets, sealed FD/peer checks, restricted writer ACL, transactions, lock waiting, activation, expiry and recovery therefore remain unqualified by this run. No production installation, full worker chain, formal AT35, browser or paid/LIVE model acceptance is claimed.

The exact public result and exit-code line are preserved in [actual-allowed-output.txt](evidence/restricted-linux-trial-once-20261012/actual-allowed-output.txt); structured result, Actions metadata, frozen pure result summary, independent signatures and reviewed original pure failures are beside it. The manifest binds every copied evidence file. Raw VM dependency/PG/helper/exception files remained private in the disposable VM. The artifact endpoint returned an empty list; the workflow contains no artifact or cache upload action. Standard hosted compute for public repositories is free under [GitHub's Actions billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions); this trial requested that standard runner only, with 25-minute job and 23-minute step limits.

The earlier GitHub CLI repository GET remains stopped with the complete diagnostic `Get "https://api.github.com/repos/T1doo/ParkWeave": Forbidden`. Its exact transcription and provenance are preserved separately; it was not retried through another endpoint or tool. Independent review distinguished the previously authorized dedicated Git push/new VM and distinct Actions status reads from that refused repository GET. The historical Chromium `data:` navigation `ERR_BLOCKED_BY_ADMINISTRATOR` remains unretried; no browser was started.

The failure was reported immediately before this documentation-only archive. Trial scripts and adapter guards stay unchanged. Further runtime repair or another VM run requires the user's next decision after reviewing this failure. A future proposal can define narrowly allowlisted setup diagnostics without exporting private logs or weakening the actual guard; no such repair or additional run has been performed here.
