# Official CfT preparation run3 — FAIL preserved

Run: https://github.com/T1doo/ParkWeave/actions/runs/40480601813

Source b35f8950ac002c02f451560c07530e7ea6d2e8ce, attempt1. The exact metadata gate passed and the read counter reached 198,195,769 bytes. This counter is updated before writing the corresponding block, so it does not prove a complete file write. The worker then recorded OSError in FIXED_OFFICIAL_DOWNLOAD; no errno or exception body was retained. MD5 completion and SHA256 readback were not reported. The broad phase does not distinguish whether those checks had started or failed partway; unpack was not entered. This is not an accepted asset. The private tree and both bound processes were cleaned; Chrome, PG and API were not started. Original run1 remains separately preserved.

`official-artifact.zip` is the normally retrieved new artifact 12722153462, 1083 bytes, SHA256 b8f295a41a1368a2fdac8962115249ecf10c7489e4f903c08f45a523a9e64f2c; `result.json` is its exact sole member. Run metadata and artifact metadata are unmodified normal GitHub CLI responses. `cli-original-job.log` is the unmodified CLI failed-step output; `cli-original-run-logs.zip` is the accepted CLI cache archive. No previously refused log path was retried. `receipt.json` is a locally authored summary and hashes, not a server-issued receipt.

A focused offline real-socket fault reproduces errno9 after exact receipt because HTTPResponse can close the socket at Content-Length. The fix stops the pinned-size read loop before another socket timeout change; exact count, MD5 and local SHA256 readback remain required. This proves a source defect, not direct observation of run3's unavailable errno. No repeat preparation was dispatched.

The later local diagnostic patch records a fixed subphase and numeric errno, retaining primary and individual stream-close faults separately. Offline injection covers last-block write plus both closes failing, readback plus close failing, and a close-only primary failure. No new download or preparation was executed by that patch.
