# Default-off history summary page contract

Base delivery: `873e426255cb62c55cf485cb81e1d1c3c706c373`; previous reviewed summary source: `25740641d03802e50558724c037a40895b00e669`.

Add one independent GET: `/api/cases/{case_id}/preparations/{preparation_id}/history-summary/{stage}` (`P4` or `P5`, optional original `request_key`). `create_app(..., summary_reader=None)` remains off. Only an explicitly injected exact `MemoryHistorySummaryReader` for the requested stage is accepted. `configured_app` keeps its default; no registry loading, environment/file switch, enrollment, grant, POST, or execution provider changes.

The reader checks current owner READ and the requested Case within its existing read-only transaction before decoding history. Trusted baseline identity, database binding, validity, revocation, fixed projection, and before/after guards remain required. Withdrawing EXECUTE does not withdraw READ. Missing/expired/revoked registration denies; unavailable is never presented as an available empty history. The response includes requested Case/stage correlation without full documents, proofs, material text, reports, or private body fields.

Add a separate display beside the existing Case/history controls. It performs only this summary GET, renders a strictly validated fixed projection using text nodes, stores nothing, and invalidates pending replies on session, Case, preparation, stage, key, run, tab, or newer request changes. Older success and denial must not replace a newer result. Historical verification and local close are not current execution qualification, real approval, fulfillment, or Case completion.

Acceptance uses isolated synthetic baselines and actual loopback HTTP/Chromium. Cover current READ, withdrawn EXECUTE, denied registration and wrong identity/Case, delayed replies, projection privacy, and unchanged old full GET/POST gates. Preserve failures and private raw logs, use serial owned-resource windows, freeze exact source for independent review, then one ordinary development push. Production registration and full issuer cold recovery remain open; Actions REST is not retried and CI remains unverified here.
