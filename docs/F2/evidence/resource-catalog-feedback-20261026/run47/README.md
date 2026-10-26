# Resource catalog presentation: run47 FAIL

Source: `0c072b1398bb2e9c0192240136640869d3173a3e`. [Official run](https://github.com/T1doo/ParkWeave/actions/runs/40365887109), job `121723340101`, artifact `12670426837` (`fictional-park-browser-47`).

The unmodified official ZIP is 953982 bytes, SHA256 `7dbde98dee3c46d4b2946255f6a52abca2d8b231c3084fa65133c675f3144566`, containing eight original PNGs and `result.json`. Its bytes match the official artifact digest. The complete GitHub job log was not obtained; the ZIP includes the original result and captured worker traceback, not a replacement full job log.

The terminal result is FAIL at the final network invariant. The four original page identity changes each requested `/api/run-access/status`, absent from the driver's exact route plan and blocked. The server received21 GETs; the browser observed25 GET attempts (including these four blocked attempts), not46 combined requests. The simulated500 and403 remain failure/refusal responses. No POST, page error or unexpected server GET was recorded. No second run was started.

All eight PNGs were viewed independently. They support limited original-renderer observations for1200/390 ready and loading/empty/error/denied states. The390 title is squeezed by its adjacent badge. In image06 EMPTY the expected simulated-view label is not visible in pixels despite the recorded DOM rectangle; cause is unproven, so the label assertions do not establish visible provenance in that frame. These are simulated UI responses, not real API, session authority, availability, reservation or business acceptance. No global visual or accessibility PASS.

Cleanup records: browser CLOSED, listener REFUSED, owned tree CLEANUP_CONFIRMED, bound processes exited, remaining children/private-session members empty, no cleanup errors. Worker exit1 reflects the failed network assertion. Work-and-cleanup elapsed10.885s is not a separately measured cleanup duration. Private directory deletion was not verified. No Windows, PG, OWNER, real credentials, DPAPI or model call was executed.
