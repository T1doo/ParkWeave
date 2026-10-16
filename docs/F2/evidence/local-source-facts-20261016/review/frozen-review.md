# Frozen independent review: PASS

Source: b2c99eaa906ac320c83e1b0a78e09f935304e959. Baseline: 41b7342cb0e757a3e17fe795e3d07a5b5b7ddd6b. Root alone writes source and Git; reviewer changed no source or Git. Full 706-file frozen manifest matched before and after independent execution.

Independent command:

```
.venv/bin/python -m pytest -q tests/test_local_fact_entry.py tests/test_facts_heartbeat.py --basetemp=/tmp/parkweave-local-facts-independent-final --junitxml=.runtime/local-facts-review/independent.xml
```

Result: 21 passed, 0 failed/error/skipped, 97.95 seconds, two complete modules. These 21 overlap root's 102-node gate and are not additional unique coverage. Four existing Pydantic schema-shadow warnings are recorded.

Security and scope review:

- Existing original POST /api/facts, POST /api/runs and original facts.assess worker retain READ/WRITE/EXECUTE/action authorization. No new PREPARE, assignment, approval, credentials, permissions or real-model call was introduced. Existing synthetic setup and negative-test owner revocation remain outside user business actions.
- Original conflict/missing/expired/consistent reason and KNOWN/UNKNOWN algorithm is unchanged. Durable receipts add exact synthetic excerpts, purpose/goal, UNVERIFIED, NOT_EVALUATED, and reason-derived next-step conditions. A consistent value does not certify source truth or eligibility.
- Recovery GET is exact owner + park + org + key, current field READ, read-only transaction, candidate-review excluded; only ID/fingerprint metadata is returned and no POST is replayed. Existing original result reads recheck READ; assigned non-owner roles only receive preexisting status projection.
- Source text and goal render with textContent; real Chromium injection string remains inert. SessionStorage contains only actor digest, opaque key/kind/field, expected request digest and confirmation bit; token and fact body are not persisted there.
- R1 initial-load pending-handle overwrite finding was fixed before freeze: initial restore, nonblank-session guards and foreign/invalid-handle blocking. Actual browser drop/reload test preserves the original opaque handle while blank-session POST buttons are disabled.
- Actual FACT and ASSESSMENT response loss recover through original key + Python-compatible fingerprint GET. Altered metadata fingerprint does not reveal release or enable new POST. Cross-identity A-B-A and read-selection ABA ignore late original responses; only fresh reads restore content.

Independent runtime evidence:

- Two explicit browser fact inputs and checks preserve first consistent and later conflicting history, source evidence and persistent next conditions; missing and expired fields, zero employees and idempotency parameter conflict are covered.
- Actual isolated launcher -> configured ASGI -> original worker -> retained owned PostgreSQL runs, same-port stop/restart and cold browser GETs preserve receipts, with cold POST count zero and product/permission snapshots unchanged.
- Cross-organization/tenant facts and run reads are denied or scoped-empty; original READ/WRITE/EXECUTE/identity revocations remain revoked after restart. READ withdrawal does not invent WRITE revocation and WRITE withdrawal does not invent assessment READ/EXECUTE revocation.
- No Case, assignment or model_step is created by the positive facts path. No blocked full P1-P5 flow is claimed.

No unresolved blocker in the reviewed source. Linux isolated synthetic browser scope only: Windows, formal AT, real models, live credentials and production remain unexecuted.

Artifacts: before.json, after.json, independent.xml, independent.log, preliminary-review.md. Failure/debug history in root's runtime was not modified by this reviewer.
