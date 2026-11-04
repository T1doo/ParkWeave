# Explicit LIVE worker composition

The ordinary worker remains local by default. `python -m parkweave.worker
--model-live` selects the real HTTPS client and a separately configured shared
coordinator; it does not provision a token, budget, approval, database or grant.
`--model-fixture` and fault/mock modes cannot be combined with LIVE. The LIVE
chain handles `case.create`; other trusted local actions retain their gateway.

## Existing protected credential input

On Windows the source is the current logon session's existing generic
Credential Manager target `ParkWeave/F1/InternModel`. It uses `CredReadW`, clears
the returned bounded memory and calls `CredFree` once. It never calls
`CredWrite`, `CredDelete`, changes identity or opens a credential prompt. Native
read/free outcomes that cannot be established retain their original call graph
without retry. Actual Windows execution of this new provider is not yet verified.

On Linux, `--model-config-fd N` selects an explicitly inherited private anonymous
pipe. The reader checks current UID, private mode and the held kernel `pipe:[id]`
identity, uses nonblocking reads, one two-second deadline, a 2560-byte maximum
and EOF. Regular files, named FIFOs (including unlinked ones), sockets and token
environment fallback are refused. No plaintext secret file is created.

Both sources contain one UTF-8 JSON document with exactly `schema`
(`parkweave-live-worker/1`), `token`, `quota_dsn`, `account`, `coordinator_id`
(canonical UUID). Duplicate/extra keys and malformed values produce fixed error
codes. The token and coordinator DSN are held as `SecretStr`; Python-managed
copies cannot be promised to be erased. Nothing is persisted by this reader.

The DSN explicitly names host/database/user; remote connections require a
password and `sslmode=verify-full`. Service/passfile indirection and inherited
`PG*` configuration are refused, pgpass lookup is disabled, and connections have
bounded connect/statement/lock timeouts. There is no fallback to the application
database, token environment values, arbitrary model URL or HTTP proxy.

The operator must supply an existing protected input through an already
authorized launcher/secret manager. Creating or replacing real credentials is
separate from this implementation and was not performed in its tests.

## Coordinator contract

The existing coordinator owner applies `quota.sql` under its original schema
owner role and existing limited function-execution grant policy. This preserves
budget/reservation records and adds `live_worker_approvals`; it inserts no live
approval or money/token allowance. An existing deployment must update its
coordinator functions before using the new worker. The application cannot write
approval rows.

Startup, each model phase and reserve/dispatch read current server facts:
account LIVE/approval/evidence/time/ceilings, measured rate evidence and limit,
product-to-`session_user` account binding, and the owner-approved credential
injection record with matching coordinator UUID and lifetime. Missing or expired
facts stop startup before claiming work or stop the phase before HTTP. No caller
boolean or CLI switch supplies an approval fact.

LIVE reserve and dispatch use the bound worker functions. Dispatch checks
approval, holds account-wide rate capacity and marks DISPATCHED in one database
transaction. A definite rate denial releases only the unsent reservation in that
same transaction. Old public LIVE reserve/send APIs reject; their private
implementations require the coordinator owner as `current_user`, including when
an old broad EXECUTE grant exists. SYNTHETIC APIs remain compatible. Release and
settlement remain possible after approval is revoked.

The sending-authorization checkpoint is the committed dispatch transaction.
Revocation committed before that checkpoint rejects sending. Revocation after
it cannot retract an in-flight request; the database and remote HTTP provider
are not one transaction. Lost dispatch/HTTP outcomes remain reserved/unknown,
without refund or automatic resend. A coordinator UUID identifies the configured
registration; it does not independently prove that every product uses one
uncloned physical deployment. Actual shared deployment and account/token mapping
remain operator facts, not conclusions from fixture results.

## Validation boundary

Tests use private pipes, actual separate application/coordinator PostgreSQL
databases, and the normal worker. Approval records and credentials are explicitly
synthetic. HTTPS wire responses use the existing offline provider fixture;
there are no actual model requests, new real credentials, Windows security
operations or changes to formal product acceptance.

Windows credential API source contract:
[CredReadW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credreadw),
[CREDENTIALW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw).
