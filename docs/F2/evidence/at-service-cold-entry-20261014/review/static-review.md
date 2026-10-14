# Independent cold-entry review (development snapshot)

Baseline 3bc1e96ccc6b6d73a5f1488bee644f92a15ddd97. Only this private worktree is modified by reviewer.
Original AT-07/08/14/33/35 steps/oracles read directly from docs/验收规格.json; no status or criterion changes.

Backend frozen mirror SHA256: service_instance_consumer.py 4ba55819e497959b497980989fda68fe845eccd34613dc970f1fe45843160a51; api.py 146c64de916e844f14ef276f9d52ffc703d66d63a68eed8c52111d424eedd3e5; test_service_instance_directory.py 465940f0305aa44c3143e9003befd5d8ecebefaefa435542abf35573a94db1e7.

Reviewed: exact injection default closed; directory authenticated current owner/READ/PREPARE/EXECUTE/case.create; own instances filtered before metadata projection; original reviewed release and current mapped role/resource checks; bounded 16 projected configurations; exact external field names only and no material/principal/resource DTO leakage; directory uses read_connection rather than source publication lease; no automatic product/model/adoption operation.

Observed business limitation: current_available describes current source/mappings and remains true after only case.create is revoked; it is not an execution grant. Current UI coldWritable also requires a successful current directory, and directory requires the original case.create grant. READ history is independently retained after each of EXECUTE/PREPARE/case.create revocation. Do not reinterpret current_available as authority.

Development UI findings sent to UI writer/root before freeze: completed five-stage opaque handle had no explicit reset/new input path; prepare-stage lost response could be retried instead of original-key GET recovery. Await corrected frozen UI actual verification. Neither is an accepted final defect.

Actual three-party owned PG lock probe: directory catalog shared gate then resource shared wait; actual bind_instance queued exclusive catalog gate; simulated original business resource exclusive gate requests original catalog shared gate. pg_blocking_pids observed actual advisory Lock waits in two transactions, all operations completed without deadlock/timeout. This uses original business lock helpers, not a complete HTTP resource business request; no stronger race claim.

Original first history test failure was reviewer harness patch lifetime (source_lease intentionally forbidden leaked into a later expected write-authority denial check), not product behavior. Initial source/log/XML/exit retained; corrected patch scoped only around recovery, 3 PASS.
