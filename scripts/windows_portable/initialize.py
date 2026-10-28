"""Paused, schema-only native creation candidate; never a portable entry point.

No private PostgreSQL bootstrap, roles, grants, seed, sessions or ACL mutations
are implemented here. The original setup pause is checked before dependency
imports, file reads or database work. Nothing exposes an override for it.
"""
from hashlib import sha256
from pathlib import Path


MIGRATIONS = (
    (26, '625208b5620e8c5a0840e6672fd08c1081e148b5bd1d401697f0810dec8b50a3'),
    (27, '97034ad99ad21af9c0e36724481a65c179638e7e49a27d5d140e8aaa93a73c79'),
    (28, 'ed94c37d627300651dc13935665baf774fa07ea9f3589e4089649ff6005591f0'),
    (29, '179ff8f16b862cc7b5a076a6f21a31dd77961a0c62af37cc53d9315e89b9bac7'),
    (30, 'c50c7224db5723611a79bac721238c66683608b18a6bfef4e72c4ce7d29d3f03'),
    (31, '906b70e775e70e7706558395ab779a0bfbe2b598004fac29b0eb30d3181e1eac'),
    (32, 'c24bd55751a7922341557d48270f83e6f911513d4588c6f3571c7beca10a284b'),
)
VERSION_QUERY = 'SELECT max(version) AS version FROM schema_version'
LOCK_QUERY = "SELECT pg_advisory_xact_lock(hashtextextended('parkweave:migrate',0))"


def create_fresh_native_schema32(
        maintenance_dsn, owner_dsn, application_dsn, expected_data_directory, *, endpoint=None):
    """One fresh CREATE with the original live proof; no existing-DB adoption.

    Currently always refused by OWNER_MUTATION_PAUSED. If that original gate
    is independently enabled in future, the caller still needs the existing
    authorized cluster, credentials and restricted application role. This
    function does not supply them or produce a usable end-user installation.

    CREATE and Store's committed schema 25 cannot be rolled back by the new
    026–032 transaction. SQL-stage failure requests rollback of that extension;
    COMMIT/rollback transport failure can leave the result UNKNOWN. Preserve
    that state and the original exception for inspection; there is no DROP,
    retry, receipt serialization or cold reissuance path.
    A rollback/close exception may become the surfaced exception; the private
    controller retains its cause/context chain as well as later cleanup errors.
    Do not publish exception text/DSNs or assume SQL error is always top-level.
    """
    from scripts.windows.lifecycle import require_setup_readiness
    require_setup_readiness()

    # Deliberately below the original pause: even missing runtime dependencies
    # must not obscure the first refusal or cause setup side effects.
    from parkweave import store as store_module
    from parkweave.installed_fixture_receipt import (
        NativeDatabaseCreationEvidence, _InstalledSyntheticSetupStore,
        create_installed_synthetic_store,
    )
    from parkweave.store import Denied

    frozen_sql = []
    for version, expected in MIGRATIONS:
        raw = Path(store_module.__file__).with_name(f'migration-{version:03}.sql').read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise Denied('native candidate migration source integrity refused')
        frozen_sql.append((version, raw.decode('utf-8')))

    owner = create_installed_synthetic_store(
        maintenance_dsn, owner_dsn, application_dsn, expected_data_directory,
        **({'endpoint':endpoint} if endpoint is not None else {}))
    receipt = getattr(owner, '_case_fact_fixture_receipt', None)
    if (type(owner) is not _InstalledSyntheticSetupStore or
            type(receipt) is not NativeDatabaseCreationEvidence):
        raise Denied('exact native creation store and issued evidence required')

    # The original Store keeps its native skip branches. It validates the
    # live issuer registry itself before any schema work and stops at 25.
    owner.migrate()
    with owner.connect() as connection:
        if connection.autocommit:
            raise Denied('explicit owner migration transaction required')
        NativeDatabaseCreationEvidence.authorize_migration(receipt, connection)
        connection.execute(LOCK_QUERY)

        def require_version(expected):
            row = connection.execute(VERSION_QUERY).fetchone()
            if not row or type(row.get('version')) is not int or row['version'] != expected:
                raise Denied('native candidate exact schema version refused')

        require_version(25)
        for version, sql in frozen_sql:
            # Exact original class, original issuer/DB/cluster/session/txid
            # checks and original SQL ticket consumer; no substitute proof.
            NativeDatabaseCreationEvidence.authorize_migration(receipt, connection)
            connection.execute(sql)
            require_version(version)
    return owner
