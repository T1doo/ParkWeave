# Official CfT preparation run3 — FAIL preserved

Run: https://github.com/T1doo/ParkWeave/actions/runs/40480601813

Source b35f8950ac002c02f451560c07530e7ea6d2e8ce, attempt1. The exact metadata gate passed and 198,195,769 bytes were received. The worker then recorded OSError in FIXED_OFFICIAL_DOWNLOAD; no errno or exception body was retained. MD5/SHA readback and unpack were not reached, so this is not an accepted asset. The private tree and both bound processes were cleaned; Chrome, PG and API were not started. Original run1 remains separately preserved.

`official-artifact.zip` is the normally retrieved new artifact 12722153462, 1083 bytes, SHA256 b8f295a41a1368a2fdac8962115249ecf10c7489e4f903c08f45a523a9e64f2c; `result.json` is its exact sole member. Run metadata and artifact metadata are unmodified normal GitHub CLI responses. `cli-original-job.log` is the unmodified CLI failed-step output; `cli-original-run-logs.zip` is the accepted CLI cache archive. No previously refused log path was retried. `receipt.json` is a locally authored summary and hashes, not a server-issued receipt.

A focused offline real-socket fault reproduces errno9 after exact receipt because HTTPResponse can close the socket at Content-Length. The fix stops the pinned-size read loop before another socket timeout change; exact count, MD5 and local SHA256 readback remain required. This proves a source defect, not direct observation of run3's unavailable errno. No repeat preparation was dispatched.
