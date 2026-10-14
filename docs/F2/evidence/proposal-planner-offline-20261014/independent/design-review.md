Independent design review, pending implementation

Observed baseline: InternChatAdapter tools are fixed to case_create and live dispatch can use PersistentBudget + LiveSafety. InternHTTPTransport.post is reusable only with exact MockTransport; it does not itself prohibit None. OfflineBudget conservative reserve/usage contracts are suitable for offline proposal attempts. Existing candidate GET/POST bp._context calls lock parent through cp._auth. Existing candidate provenance/recovery is V1/V2 and historical accepted_at-bound.

Required review gates:
- New proposal adapter rejects real/None transport and LIVE/persistent budget before token access/reserve; no ModelChain/ExecutionGateway import/call, environment credential reads or actual sockets to provider.
- Dedicated strict JSON parse: duplicate keys, nonfinite constants, extra fields, typed booleans, malformed envelope, tools/truncation all reject; only independent trusted-current contract equality makes candidate adoptable. UNKNOWN and UNSUPPORTED remain.
- Full required-goal/graph/adapter version/dependency/action/roles/hard-condition/source binding must compare with independently recompiled current proposal, never saved claims as authority.
- Commit one exact-key attempt marker before wait, close Case transaction, prevent same-key resend after pending/unknown/error; conflicting params and cross-Case key reject. Lock order must not reverse parent/key.
- Model wait outside all business transactions; completion rechecks permissions, Case cancellation, material/catalog/registry/request source, original key and DB expiry. Attempt deadline does not renew on provider return/retry.
- V1/V2 consumption and current/historical recovery proofs remain unchanged. Model provenance must not downgrade to old deterministic marker; history filtering must handle pending records without bogus old preview entries.
- Actual PG blocking fake-provider race uses original material command/revoke/cancel, proves no Case lock held; duplicate concurrent request sends once.
- Fake transport actual original preview/ADOPT/goal-results source trace; lost response exact-key GET only; real socket constructor dispatch prevention counts zero; missing/invalid usage conservative budget, no retries.

Status: design constraints only, not executable acceptance. No source/Git edits or credential reads.
