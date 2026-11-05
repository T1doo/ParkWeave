"""Raw Windows candidate SQL bytes must match the original migration pins."""
from hashlib import sha256
from pathlib import Path
from scripts.windows_portable.initialize import MIGRATIONS
from scripts.windows_portable.native_sample import SQL_SHA256


def test_native_migration_sql_retains_exact_pinned_bytes():
    root=Path(__file__).parents[1]/'src/parkweave'
    for version,expected in MIGRATIONS:
        raw=(root/f'migration-{version:03}.sql').read_bytes()
        assert sha256(raw).hexdigest()==expected


def test_native_sample_storage_retains_exact_pinned_bytes():
    raw=(Path(__file__).parents[1]/'src/parkweave/local-resource-approval-schema.sql').read_bytes()
    assert sha256(raw).hexdigest()==SQL_SHA256
