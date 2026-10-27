"""Owned schema33 accepted/manual cancellation; direct modules and real ASGI only."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import threading
import os, json
from pathlib import Path
import psycopg
import pytest

from parkweave import business_frontier as bf, preparation as prep
from parkweave import case_cancellation_before_receipt as cancellation
from parkweave import executor_receipts as er, service_dispatches as sd
from parkweave.store import Store, Conflict
from test_preparation import preparation_fixture, headers, command as material
from test_executor_receipts import receipt_fixture, ready, act
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog
from test_plan_replacement_reapproval import bind_all, generate
from test_new_enterprise_local_chain import ALL_GOALS
from test_request_intents import save
from test_service_case_steps import verified
from test_resource_bundles import bundle, states
from test_case_resource_delivery import quoted, submit
from test_service_plan_approval import enable, approved
from test_service_dispatches import offer, command as dispatch
from test_case_cancellation import snapshot, wait_for_pg_lock
from test_case_cancellation_before_receipt import get, body, post, recover


@pytest.fixture
def cancel33_case(capability_resource_catalog):
    a = capability_resource_catalog
    f = a['f']
    artifacts = Path(os.environ.get('CANCEL33_ARTIFACT_ROOT', os.environ.get('FRONTIER_ARTIFACT_ROOT', '.runtime/cancel33-fixture/artifacts')))
    artifacts.mkdir(parents=True, exist_ok=True)
    private_fd = os.open(artifacts / ('fixture_' + uuid4().hex + '.private.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(private_fd, 'w') as private_output:
        private_output.write(json.dumps(sorted(f[2].values())) + '\n')
    protocol = bf.KnownNotStartedFrontier(f[1], f[1]._case_fact_fixture_receipt,
        enabled_for_isolated_tests=True)
    protocol.attach_store(f[0])
    bind_all(a)
    p = ready(f)
    r = save(f, p, goals=ALL_GOALS)
    assert r.status_code == 200, r.text
    p = {**p, 'revision': r.json()['revision']}
    for action, actor in [('REVIEW', 'prep-specialist-fixture-a'), ('CONFIRM', 'fixture-a')]:
        r = material(f, p, action, actor, reason='SYNTHETIC six-goal cancellation ' + action)
        assert r.status_code == 200, r.text
        p = r.json()
    generate(a, p)
    verified(f, p, 'P1')
    bridge = enable(f, p)
    hs, resource_request = bundle(f)
    delivery = quoted(f, p, resource_request)
    approval, _ = approved(f, p, delivery)
    r = submit(f, p, {**delivery, 'approval_id': approval['id']})
    assert r.status_code == 201, r.text
    verified(f, p, 'P2')
    catalog = f[3].get('/api/service-dispatches/catalog',
        params={'preparation_id': p['preparation_id']},
        headers=headers(f[2], 'prep-specialist-fixture-a'))
    assert catalog.status_code == 200, catalog.text
    r, _, _ = offer(f, p, expected_business_frontier=catalog.json()['business_frontier'])
    assert r.status_code == 201, r.text
    r = dispatch(f, r.json(), 'ACCEPT', expected_business_frontier=r.json()['business_frontier'])
    assert r.status_code == 200, r.text
    d = r.json()
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 33
        plan = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',
            (p['preparation_id'],)).fetchone()['service_case_plan']
    assert plan['required_goals'] == ALL_GOALS and len(plan['steps']) == 5
    assert states(f, hs) == ['CONFIRMED'] * len(hs)
    return dict(f=f, p=p, d=d, hs=hs, accepted=d, holds=hs, protocol=protocol, bridge=bridge)

