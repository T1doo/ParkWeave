"""One real owned DB binds repaired catalog ACL to persisted ordinary Case cancel."""
from uuid import UUID, uuid4

from psycopg import sql

from parkweave import native_run_access as native, native_run_access_activation as activation
from parkweave import native_run_access_preflight as preflight, native_run_access_writer as writer
from scripts.catalog_only import probe as catalog
from scripts.catalog_only.bootstrap import initial
from test_case_resources import link_fixture, group, post as link
from test_executor_receipts import receipt_fixture, ready
from test_preparation import preparation_fixture
from test_case_cancellation import body, post, recover, snapshot
from test_resource_combinations import cancel as release


def test_catalog_fix_and_case_cancellation_share_owned_database(link_fixture, pg):
    f = link_fixture; owner = f[1]; parent = ready(f); combination = group(f)
    assert link(f, parent, combination).status_code == 201
    native.install_owned_test_storage(owner, owner._case_fact_fixture_receipt)
    activation.install_owned_test_activation_storage(owner, owner._case_fact_fixture_receipt)
    with owner.connect() as c:
        c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        c.execute('GRANT USAGE ON SCHEMA public TO pwci_writer')
        for _, action, table, column in preflight.required_privileges('revision') + [('writer', 'SELECT', 'schema_version', None)]:
            if action == 'LOCK_UPDATE':continue
            if action == 'EXECUTE':
                c.execute('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer'); continue
            c.execute(sql.SQL('GRANT '+action+(' ({})' if column else '')+' ON {} TO pwci_writer').format(
                *([sql.Identifier(column)] if column else []), sql.Identifier(table)))
        bridge = native.NativeRunAccess(owner)
        run = c.execute('SELECT * FROM runs WHERE id=%s', (UUID(parent['run_id']),)).fetchone()
        source = bridge._source(c, run, bridge._parent(c, run))
    spec = catalog.make_spec(owner, pg.root).model_dump()
    spec['policy'].update(application_role='parkweave_app', owner_id=source['owner_id'],
        approver_id='prep-specialist-fixture-a', beneficiary_id='executor-a', source=writer._source(source))
    spec = preflight.InstallationSpec.model_validate(spec)
    assert spec.policy.source.case_id == parent['case_id']
    observed = initial('0'*40)
    with owner.connect() as c:before = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    catalog.record_rights(before, observed, 'before')
    catalog.role_call(owner.dsn, 'parkweave_app', spec, True)
    catalog.role_call(owner.dsn, 'pwci_writer', spec, True)
    catalog.analyze_snapshot(spec, before, observed, 'before')
    with owner.connect() as c:c.execute(catalog.REVOKE)
    with owner.connect() as c:after = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    catalog.record_rights(after, observed, 'after')
    catalog.role_call(owner.dsn, 'parkweave_app', spec, False)
    catalog.role_call(owner.dsn, 'pwci_writer', spec, True)
    catalog.analyze_snapshot(spec, after, observed, 'after')
    # Same real business Case and repaired SQL-app role; original transaction/API.
    data = body(f, parent); key = uuid4().hex; original = snapshot(f)
    result = post(f, parent, data, key); assert result.status_code == 200
    current = snapshot(f)
    assert all(current[t] == original[t] for t in original if t not in ('cases', 'case_local_lifecycles', 'case_local_events'))
    assert recover(f, parent, key).json()['event_id'] == result.json()['event_id']
    assert snapshot(f) == current
    assert post(f, parent, {**data, 'reason': 'SYNTHETIC changed'}, key).status_code == 409
    with owner.connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s', (UUID(parent['case_id']),)).fetchone()['state'] == 'CANCELLED'
        assert c.execute('SELECT state FROM runs WHERE id=%s', (UUID(parent['run_id']),)).fetchone()['state'] == 'SUCCEEDED'
    assert release(f, combination['id']).status_code == 200
    with owner.connect() as c:last = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    catalog.analyze_snapshot(spec, last, observed, 'after')
    catalog.role_call(owner.dsn, 'parkweave_app', spec, False)
