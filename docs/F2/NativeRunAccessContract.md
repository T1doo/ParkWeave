# Ordinary PostgreSQL single-Run access protocol (disabled)

This slice persists requests, independent decisions, proposed leases and their
immutable command receipts in one PostgreSQL transaction. It does not install
production storage, adopt an approval policy, or create/update a Run assignment,
authority, Grant or SQL privilege. Approval is explicitly `NON_EFFECTIVE` until a
separately authorized activation implementation and policy have been installed.
The four/eight-hour policy in ENG089 remains a proposal, not an authorization.

## Boundary

The production API can authenticate and expose disabled status. If the additive
storage has already been installed, the current enterprise owner can read the
protocol and recover a command by its original key. Production command writes
remain closed. Tests may issue an explicit bounded decision-only permit against
an already authorized, fresh owned synthetic PostgreSQL database. This permit
never makes a lease usable by business endpoints. No SQLite state participates.

The ordinary namespace is distinct from isolated SQLite/PG projections. Exact
tenant/owner, successful verified synthetic `case.create` Run, preparation and
Case are bound. REQUEST requires current READ/PREPARE/EXECUTE owner permission;
the beneficiary must be an existing same-tenant service executor with READ.
APPROVE/REJECT require an explicitly designated independent decision actor in the
test permit; a preparation reviewer alone is not an approval authority. CANCEL
belongs to the requester; REVOKE belongs to the owner or designated decision
actor. No permission is inferred from a role name alone.

## Transaction and recovery

Use the existing parent → dispatch → Case business lock order: the protocol
locks the preparation parent before its Run row and reads the Case under that
parent lock. Actor/key advisory locking serializes reuse across Runs. The command
fingerprint binds the exact Run and strict DTO. Same actor/key/parameters returns
the original receipt, even after a later decision; different parameters conflict.
Current metadata authorization is checked before replay/recovery. A lost response
is recovered only with GET of the original key; the workbench does not POST it
again or manufacture a new request key.

The ledger update contains the request, decision, proposed lease and event
receipt. A database trigger rejects changes to earlier receipts or removal of
the ledger; an event failure rolls back all state. Version/source checks and
database time are rechecked after lock waits and immediately before commit.
Read and cold recovery do not invalidate plans or modify business state.

## Use boundary and compatibility

Legacy assignments retain their behavior. Isolated managed assignments retain
their separate guard. Any assignment marked with ordinary native metadata is
denied until an authorized effective-access provider is implemented; ambiguous
ordinary plus isolated metadata is denied. All lists, dispatch/receipt entry
points, notices and registered dependencies use the shared assignment predicate.
Decision approval alone is never an assignment or business execution right.

Storage is additive to schema 32 and is delivered as an unenabled SQL file,
outside automatic migrations. It leaves cancellation/handoff schema gates,
Run success, business revisions, resources, reservations and history intact.
Case cancellation prevents new REQUEST/APPROVE but preserves authorized historical
reads, original-key recovery and CANCEL/REVOKE of protocol state.

## Verification scope

Required actual PostgreSQL tests: strict DTOs, same/different key reuse and
concurrency, append failure rollback, source/version changes, parent lock waits,
current permission revocation, cross-tenant/non-owner rejection, cold recovery,
decision-only approval, unchanged permission/assignment snapshots, cancellation
compatibility and central denial of native-marked assignments. Offline NodeVM
checks the pending workbench and GET-only lost-response recovery. Existing
related regression and independent review remain required.

Actual production installation, adopted approver identities/TTL policy, SQL
permission changes, authority/Grant/assignment activation, and effective native
lease end-to-end tests are NOT RUN under this task's authorization. They require
a separately reviewed daytime activation decision. This slice must not claim a
complete effective-access lifecycle or formal AT35 acceptance.
