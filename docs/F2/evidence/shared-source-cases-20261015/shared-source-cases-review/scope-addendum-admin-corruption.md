# Scope addendum: unsupported administrator corruption

This addendum narrows the earlier frozen review's shorthand “malformed plan UNKNOWN” to the behavior actually implemented and tested: invalid plan header or an original reader validation Conflict produces a sanitized per-Case UNKNOWN. It does not claim tolerance of every JSON-object body an administrator can write directly to PostgreSQL.

A separate owned-PG observation at bc4 retained a legitimate plan UUID/revision but deleted its steps key by direct test-owner SQL. This state cannot be produced by a supported plan/business command. The inherited typed reader accesses steps before its recovery-proof validation and the reverse request returned generic HTTP500. It returned no items/plan contents, granted no authority, changed no business/plan history and performed no automatic repair. Explicit test-owner restoration of the exact original object made the read return200.

The observation is an unsupported trusted-DB structural-corruption failure-closed boundary, not positive product validation and not a row-isolation/fault-tolerance guarantee. It is not added to the64 complete-module coverage or schema3 probes. No source repair or constraint weakening was performed. This does not block the bounded supported-flow delivery; public scope must retain this limitation rather than claim arbitrary administrator-corrupted histories are always projected as UNKNOWN.

Exact observation and rationale: `admin-corruption-observation.json` and `admin-corruption-boundary-assessment.json`; actual log/JUnit and source595 before/after snapshots are preserved.
