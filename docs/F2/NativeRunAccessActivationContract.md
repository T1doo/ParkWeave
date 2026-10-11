# Native Run access activation: disabled production, owned synthetic tests

This slice implements an effective native provider and an explicit ACTIVATE API.
Production activation remains closed: there is no adopted production enablement
authority, approver policy or writer. The four/eight-hour suggestion is not a
policy. Merely installing storage or finding APPROVED in a Run never enables it.

The sole issuer is restricted to the existing fresh owned synthetic PostgreSQL
fixture evidence, original cluster/database identity and existing owner
connection. An immutable issued permit binds one already approved lease, exact
approver, existing executor, owner, Run/Case/tenant/material and permission
versions, and the explicitly supplied approved UTC interval. It cannot expand
that interval or authorize another Run. Missing, forged, expired, stale or
cross-database enablement denies. The fixture issuer is not a production factory.
The provider must be the exact native implementation bound to the same Store;
an unknown provider or overridden instance access predicate cannot grant scope.
Activation checks the business Store's actual PostgreSQL endpoint and database
identity before using the independently verified, narrowly issued owner writer.

ACTIVATE requires current owner READ/PREPARE/EXECUTE, explicit confirmation,
reason, original request key and exact current versions/permit hash. Under
parent -> Run -> assignment locks, the existing owned fixture writer appends an
activation receipt and writes only the exact native assignment in one PG
transaction. It refuses to replace any legacy or isolated assignment. No SQL
GRANT, capability/preparation Grant, identity or registry mutation is performed.
The additive activation SQL remains outside automatic migrations/schema 32.

Original approval receipts and proposed leases remain NON_EFFECTIVE historical
facts. Effective access additionally requires the trusted live permit, immutable
activation, exact stored assignment, current approved unretracted lease, matching
source/permission versions and database UTC time. Every existing business access
consumer uses this predicate, including lists, dispatch, receipt, notices,
dependency collections and final transaction commit. A lease is only Run READ
scope; dispatch participant and receipt business-action guards still apply.
Within that exact Run, the existing executor role may accept/decline its own
offer and submit its manual receipt. This is the inherited business-action
surface tested here, not a promise of complete platform lifecycle authority.
Case state is business progress, not the READ lease version: legal progress,
cancellation/reconciliation and local closure preserve existing authorized
historical READ. New activation is blocked for cancelled/reconciling/locally
closed Cases, and their existing business write guards remain decisive. Material,
Run provenance/revision and participant permission changes invalidate the lease.
Permissions also bind PostgreSQL row generations (`xmin`), including principal,
capability and preparation permission rows: revoke/regrant or delete/recreate
cannot silently revive an old lease. The bounded issued permit is required again
on cold rebind; persisted records alone never reconstruct trusted enablement.
Temporary/shadow schemas, unguarded connections and autocommit deny native scope.

Revocation uses the existing decision protocol. Business access and revoke
serialize on the preparation parent before Run locking; the winning transaction
determines availability. Expiry during lock waits or before completion rolls back
business writes. No background cleanup or historical receipt rewrite is required.
GET original-key recovery includes activation receipts and performs current
metadata authorization. A cold Store without trustworthy enablement denies native
business scope; a cold Store explicitly rebound to the same issued fixture permit
rechecks persisted PG state. Reads and recovery never activate or repair rows.

Actual verification must cover real PG/API dispatch/ACCEPT/manual receipts and
notifications, parent lock waits, expiry/revoke races, current authority changes,
cross scope, exact-key concurrency, append/write rollback, cold recovery and all
shared consumers. No browser is started. Production installation, real permission
or assignment changes, production policy adoption/deployment and formal complete
AT35 acceptance remain NOT RUN.
The workbench displays current effective fixture READ separately from immutable
non-effective approval history and clears the effective display at lease expiry.
Activation itself is available only through the explicit restricted API in this
slice; no production activation control is exposed.
