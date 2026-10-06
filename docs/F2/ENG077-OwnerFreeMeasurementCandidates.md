# ENG077 owner-free native measurement candidates

Candidate parent: `8e40f429c356af1ba7b2e2b0a390549c88e65c5e`. This is local implementation and injected verification, not a Windows result. Owner writes, push and CI remain paused. F1 is unsigned, F2 is parallel exploration, Server is not Win11 acceptance, R4 stays disabled and model budget is zero.

## Controlled Job entry

On Windows / Python 3.12 x64, the explicit entry is `python -m scripts.windows_ci.controlled_job_measurement --run-controlled`. No flag returns NOT_RUN. It uses production `run` / `stop_tree` with a dedicated measurement backend; generic production launch/inheritance and owner helpers are unchanged.

The fixed trusted parent creates a suspended leaf, then duplicates its exact creation handle into the coordinator with QUERY_LIMITED_INFORMATION | SYNCHRONIZE (`0x101000`). Only that parent inherits a coordinator PROCESS_DUP_HANDLE (`0x40`) capability, alongside three standard handles. The leaf has handle inheritance disabled. No PID discovery, OpenProcess, owner helper, privilege adjustment or model code is involved. Bounded private record and ACK publication use exclusive temporary files and atomic hard links without overwriting an existing destination.

The coordinator validates the transferred handle's PID, creation time, LIVE signal and actual inner-Job membership before ACK. Normal parent exit 17 and primary timeout have separate cases. Each uses the existing unique cleanup deadline and held-handle timeline: BEFORE_TERMINATE, AFTER_TERMINATE, ACCOUNTING_ZERO, and bounded AFTER_ACCOUNTING_ZERO samples. PASS requires initial LIVE, membership throughout and final exact SIGNALED with accounting zero. Accounting alone cannot prove descendant termination. A separately created process in its own Job must retain the same identity and remain LIVE after main cleanup, then be stopped only through its own Job.

The runtime root must already be a trusted, caller-owned accessible checkout `.runtime`, or the explicit existing RUNNER_TEMP. Symlink, junction and reparse roots are refused. Ordinary directory creation does not prove ACL protection; the entry neither repairs nor sets ACLs. Native confirmation still needs actual Windows cross-process DuplicateHandle rights, nested Job inheritance, NTFS hard-link publication, normal/timeout/unrelated golds and cleanup timing. Synchronous native calls cannot be preempted, so the deadline is not a hard guarantee against a stuck API.

Cleanup uses non-inherited Job handles and KILL_ON_JOB_CLOSE. Before acceptance, parent failures terminate only the leaf's creation handle. The coordinator releases its borrowed read-only handle after production stop and owned-handle closure. The unrelated process is cleaned through its own Job after its LIVE observation. Exclusive fixture directories are deleted locally. Public results contain fixed enums, booleans and bounded samples; private logs, records, PIDs, handles and paths are never exported.

## Existing descriptor reads

`python -m scripts.windows.descriptor_readonly_probe --held-handle N` requires an already held process-local exact-object READ_CONTROL handle. It never opens, creates or closes the target and never changes owner, ACL or privileges. Two reads use the existing OWNER | DACL scope; SACL and group are not queried. Returned security descriptors are freed after successful acquisition, and LocalFree failure refuses the observation.

The diagnostic reports concrete control-bit names/deltas, reserved-bit presence, full-storage read stability and ordered complete ACE-byte equality. Normalization excludes unused storage only for observation, never reorders ACEs or claims effective access equivalence. The strict production full-storage/control comparison remains unchanged. Owner content is NOT_COMPARED, object identity is CALLER_PINNED_NOT_MEASURED, historical owner transition is NOT_MEASURED and semantic permission change is UNKNOWN. This cannot explain historical owner-write failures without further evidence.

## Verification and next independent Windows measurement

Actually executed local tests: **290 passed, 5 native skipped, 1 existing Starlette warning**, 4.38 seconds. This includes both new suites, owned Job/session regressions and shard/diagnostic tests. The narrow four suites previously produced 194 passed / 5 skipped. Independent review recorded NO_BLOCKERS_LOCAL; native proof remains open.

Collection freeze: 1463 cases in pieces 345 / 345 / 349 / 424, exact multiset match, all 1403 ENG074 keys retained, 60 new cases. All 53 test-source and 33 implementation hashes plus diagnostic allowlist hash match local bytes. Collection is not execution or native S4 PASS.

The reviewable [workflow patch](evidence/eng077-independent-job-workflow.patch) passes `git apply --check` and is **not applied**. It preserves windows-2025, Python 3.12 x64, contents:read, concurrency and the existing 25-minute job budget, replacing the owner-dependent lifecycle/validation/publish/stop sequence with one two-minute isolated measurement step and Server guard. Engineering.ps1 performs owner/ACL protection on every Action, so none of those Actions can be reused for this independent measurement. No pip, PostgreSQL, app, model, cache or artifact upload is added. This one measurement does not execute S4 or replace acceptance evidence.

Parent review can arrange the next native run by applying the isolated-step patch before any authorized push; pushing the source alone would retain the old owner-dependent workflow. Bind results to that actual workflow source SHA. No patch application, push, CI or native descriptor read occurred here. Original workflow, owner helpers, production owned_job and existing environments/backups are preserved.
