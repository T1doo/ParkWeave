# Historical independent review of 3e0c51ea

Source: `3e0c51eac33cd3ea017fee9b6361785c786daca7`; parent `a954bf6811e395d7515181f8bad8dd8f12d1cd7c`.

Actual new independent run: **37 passed**, 22 owned synthetic PostgreSQL/in-process ASGI and 15 offline Node VM handler probes, 6.61 seconds. Logs and JUnit remain unchanged in `historical-3e/`. This count does not include root tests.

The actual shared-lock wait was observed in PostgreSQL before an owner transaction released its exclusive lock. The reply used the committed revised rules and a database clock after release. Capacity expected values used an independently implemented midpoint-interval oracle. Full business and current authorization snapshots were unchanged; SQL audit observed SELECT/SET only.

Review is **blocked for final acceptance** by an integrated UI defect independently identified by the root: actual `bundleControls` disabled all original resource form buttons, including the new read-only search button, while combination recovery was unknown. The previous VM `bundle_unknown_read_search` directly invoked the handler and stubbed controls; it establishes a handler boundary only, not physical button availability. The integrated function at web.html:1126 confirms the defect. The root separately preserved a failing actual-control reproduction. No new independent execution was performed after the root requested a pause before its correction.

The 37 successes remain evidence for this historical source only and are not final acceptance of a subsequent corrected source. The frozen-source runtime review found no additional production blocker in the scoped resource search. The final revision must rerun these probes and a new actual bundle parser/lock/controls integration probe.

Scope excludes browser, listener, Windows, real models/resources, full original acceptance suite, multiworker, persistent trust registration and the previous isolated execution proof chain. The original browser `data: ERR_BLOCKED_BY_ADMINISTRATOR` restriction is preserved. Search covers the stated 15-minute bounded grid only; 100 is a defensive scan limit and at most 96 candidates can occur in the configured window. A search result does not reserve capacity or grant write permission.
