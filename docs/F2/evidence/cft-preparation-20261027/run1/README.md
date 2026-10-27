# CfT preparation run1 — FAIL before acquisition

[Official run](https://github.com/T1doo/ParkWeave/actions/runs/40474677242),
source `7f1c05fe1d906d9c4c11f86833214e825cd6404f`, attempt1.
Job08:36:26–08:36:52 UTC,26s. Original output records only
`SOURCE_GATE / UNCLASSIFIED_FAILURE`; it does not contain an exception type.
Uploader observed no receipt path, and official artifact metadata is empty.

A definite initialization bug was reproduced locally: helper.__file__ used
`str(ROOT/'scripts'/name+'.py')`, adding a string to PosixPath. Both real helper
loads fail with TypeError before execution of the imported helper. Parent
control flow reaches these loads before private-root/claim/worker creation or
metadata/archive fetch. Thus download and unpack were not entered; no package,
license inventory, browser hash, or process-tree cleanup acceptance was obtained.
The source reconstruction agrees with the logged phase; the original log alone
is not claimed to identify TypeError or rule out an earlier unclassified fault.

The minimal correction groups `(name+'.py')`; normal failure output also retains
error_type without exception text. Two real-source-load regressions give old2F
and corrected2P, and the final targeted suite20P independently reproduced.
The existing in-process worker fault fixture now restores ROOT after itself;
this is test isolation, not a change to worker process semantics.
No actual worker, HTTP, archive acquisition or retry was used by the regression.

Original accepted CLI-cache ZIP and its full job member are preserved unchanged;
hashes/sizes and provenance are in receipt.json. No denied old log was requested.
The consumed job remains FAIL. No repeated preparation or business execution.
Original run1/attempt1 gates and both disabled business contracts remain in place;
a later patch push can produce a skipped metadata run, not another preparation.
