# Run49 — FAIL, integration not started

Source `5eb7511ab121eff606674cb4c4f3d981986a4177`, attempt1, [official run](https://github.com/T1doo/ParkWeave/actions/runs/40447548257).

Dependencies installed; bootstrap emitted only `Closed` at 04:03:36.347Z.
The exact rejected condition is unknown. The PG/API/Chrome integration step was
skipped: no business request, browser screenshot, or business cleanup acceptance.
The artifact uploader separately rejected its literal `../` pattern; artifacts0.
This failure is preserved; no repeat execution was started.

`cli-cached-job.log` is the full job member (34671 bytes, SHA256
`5cbbdb8bd0cba1abcdf76cab2f854b2376f2a1db82d4e0ae351eff1a9dcb18d9`)
from the already successfully retrieved CLI run-log ZIP. It is not claimed to
be the separately requested raw job-log API: that later API redirect returned
Forbidden and was not retried or bypassed. The existing local CLI cache was
read without another network request. The ZIP hash/size are in receipt.json;
its other members and private diagnostics stay in the original environment.

Source-only follow-up closes the activation, removes parent traversal from
upload patterns, and adds fixed preparation stages/boolean checks and bounded
public diagnostics. These changes have offline tests only, no new hosted,
PG/API or Chrome execution and no pixel acceptance.
