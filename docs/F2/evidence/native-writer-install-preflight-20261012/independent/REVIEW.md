# Independent installation-preflight review

**LIMITED_PASS** — source `d95cee3dc18052dc619e94f5826d79f7e5c76d3c`. Independent owned-fixture/offline testing and static review only.

| Actual window | Source | PASS | FAIL | ERROR | SKIP | Exit |
|---|---|---:|---:|---:|---:|---:|
| initial-frozen | `83431f445cec9ef8a0448aaf8714d29eaa01dbfa` | 123 | 3 | 0 | 0 | 1 |
| final-frozen | `d95cee3dc18052dc619e94f5826d79f7e5c76d3c` | 130 | 0 | 0 | 0 | 0 |

The original three failures and their complete stdout/stderr/JUnit are preserved. The same three testcase identities actually PASS in the new window: explicit extra DML hidden by a false summary, omitted writer-membership defaulting to false, and existing `pg_execute_server_program` misclassified as restricted. The last probe uses only the existing system role as a planned catalog identity; it issues no new role/GRANT/permission change.

The final window ran the complete new preflight module (66), complete diagnostic module (59), and five independent probes. Its 125 repository testcase identities overlap the root window; five additional independent identities are not added to root counts. It took 7.924 process seconds, 6.596 JUnit suite seconds, and 6.60 pytest stdout seconds. Exit 0; source and probe drift: none. Both original warnings remain in the log.

The independent binding covers 422 tracked files including both writer contracts. The root's 421-file manifest matches exactly; the additional file is `docs/F2/NativeRunAccessWriterContract.md`. Before/after source bytes equal their final Git objects. See `SOURCE_BINDING.json` and `final-frozen/{source-before.json,source-after.json,run.json,results.xml,stdout.log,stderr.log}` for exact hashes, argv, owned process PID, UTC time and results.

Static review confirms the entry accepts offline spec/snapshot files, has no connection/install/migration call, masks rejected values, and cannot issue authority. The collector requires original issued UUID creation evidence and an idle original owner connection, uses fixed READ ONLY catalog/schema_version queries, and does not read business/ledger data, create tickets or acquire row/advisory locks. The independent pending-transaction probe verifies zero collector SQL and no caller rollback. Exact object checks expose only mismatch field names and body hashes; missing owner configuration cannot hide known incompatible definitions. The synchronized diagnostic catalog contains test names and confers no business permission.

All results preserve `installation_authorized=false`, `activation_enabled=false`, `production_connected=false` and `installation_status=APPROVAL_REQUIRED`. Production connections, installation/DDL/GRANT/permission changes, activation, actual production identity/session/OS/key/pin/current-source verification, Windows native, formal AT35 and browsers were **NOT RUN**. Production custom NOINHERIT/SET ROLE privilege chains remain an unverified installation prerequisite. Original fixture setup privileges are setup, not a tested production installation.

No remaining blocker within this finite code/owned-fixture review. `STATIC_EXPORT_REVIEW.json` approves only seven explicitly read static paths and their exact hashes; it is not suffix-based export authorization. No earlier writer/cancellation results were transferred to this source.
