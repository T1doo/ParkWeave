"""Fresh, original-command P3 histories; independent of zero-frontier qualification.

Only issued synthetic owned-PG fixtures are used. Stage stops describe actual
business states and do not disable any original command or approval gate.
"""
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4
import json
import os

import pytest

from parkweave import service_release_preflight as pf, service_capability_catalog as catalogs
from parkweave.template_consumer import ConsumerRepository
from test_preparation import preparation_fixture, headers, command
from test_executor_receipts import receipt_fixture, ready
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog
from test_plan_replacement_reapproval import generate, bind_all
from test_new_enterprise_local_chain import ALL_GOALS
from test_request_intents import save
from test_template_upgrade import publication
from test_service_case_steps import verified
from test_resource_bundles import bundle
from test_case_resource_delivery import quoted, submit
from test_plan_source_reapproval import approved
from test_service_plan_approval import enable


PROFILE = 'P3_NEVER_ACCEPTED_CLOSED_V1'
REVIEWER = 'prep-specialist-fixture-a'


def dispatch_read(f, row, actor=REVIEWER):
    r = f[3].get('/api/service-dispatches/' + row['dispatch_id'], headers=headers(f[2], actor))
    assert r.status_code == 200, r.text
    return r.json()


def offer_current(t):
    from test_service_dispatches import offer
    f, p = t['f'], t['p']
    r = f[3].get('/api/service-dispatches/catalog', params={'preparation_id': p['preparation_id']}, headers=headers(f[2], REVIEWER))
    assert r.status_code == 200, r.text
    view = r.json()
    r, _, body = offer(f, p, revision=view['dispatch_revision'], expected_business_frontier=view['business_frontier'])
    assert r.status_code == 201, r.text
    return r.json(), body


def build_closure(a, tmp_path, *, action='WITHDRAW', cycles=1, stop_after='new_adopted', hook=None):
    """Return after old_p2/offered/closed/new_adopted; every change uses original APIs."""
    from parkweave.p3_never_accepted_closure import P3NeverAcceptedClosure
    from test_service_dispatches import command as dispatch_command
    assert action in ('WITHDRAW', 'DECLINE') and type(cycles) is int and 1 <= cycles <= 3
    assert stop_after in ('old_p2', 'offered', 'closed', 'new_adopted')
    f = a['f']
    out = Path(os.environ.get('P3_CLOSURE_ARTIFACT_ROOT', '.runtime/p3-closure-root/dev-artifacts'))
    out.mkdir(parents=True, exist_ok=True)
    fd = os.open(out / ('fixture-' + uuid4().hex + '.private.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps(sorted(f[2].values())) + '\n')
    protocol = P3NeverAcceptedClosure(f[1], f[1]._case_fact_fixture_receipt, enabled_for_isolated_tests=True)
    protocol.attach_store(f[0])
    oldpairs = bind_all(a)
    p = ready(f)
    r = save(f, p, goals=ALL_GOALS)
    assert r.status_code == 200, r.text
    p = {**p, 'revision': r.json()['revision']}
    for op, actor in (('REVIEW', REVIEWER), ('CONFIRM', 'fixture-a')):
        r = command(f, p, op, actor, reason='SYNTHETIC original closure material ' + op)
        assert r.status_code == 200, r.text
        p = r.json()
    generate(a, p)
    verified(f, p, 'P1')
    checker = pf.ServiceReleasePreflight(a['catalog'], ConsumerRepository(tmp_path / 'closure-preflight.consumer.candidate.sqlite3'), enabled_for_isolated_tests=True)
    bridge = enable(f, p, enabled_for_source_reapproval_tests=True, enabled_for_plan_replacement_tests=True,
                    plan_replacement_preflight=checker, enabled_for_p3_closure_tests=True, p3_closure_frontier=protocol)
    holds, b = bundle(f)
    data = quoted(f, p, b)
    item, _ = approved(f, p, data)
    r = submit(f, p, {**data, 'approval_id': item['id']})
    assert r.status_code == 201, r.text
    verified(f, p, 'P2')
    with f[1].connect() as c:
        old = deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['service_case_plan'])
    t = dict(f=f, p=p, a=a, old=old, oldreceipt=r.json(), old_holds=holds, oldpairs=oldpairs,
             checker=checker, bridge=bridge, protocol=protocol, out=out, closure_action=action)

    def stage(name):
        if hook:
            hook(name, t)
        return stop_after == name

    if stage('old_p2'):
        return t
    for i in range(cycles):
        row, body = offer_current(t)
        t.update(dispatch=row, old_offer_body=body)
        t['old_accept_body'] = dict(action='ACCEPT', expected_revision=row['revision'], reason='SYNTHETIC captured original acceptance', expected_business_frontier=deepcopy(row['business_frontier']))
        if i == cycles - 1 and stage('offered'):
            return t
        actor = REVIEWER if action == 'WITHDRAW' else row['current_offer']['executor_id']
        row = dispatch_read(f, row, actor)
        t['old_resolve_body'] = dict(action=action, expected_revision=row['revision'], reason='SYNTHETIC captured original resolution', expected_business_frontier=deepcopy(row['business_frontier']))
        r = dispatch_command(f, row, action, user=actor, **{'expected_business_frontier': row['business_frontier']})
        assert r.status_code == 200, r.text
        t['dispatch'] = r.json()
    assert t['dispatch']['current_offer']['state'] == {'WITHDRAW': 'WITHDRAWN', 'DECLINE': 'DECLINED'}[action]
    if stage('closed'):
        return t
    a['published'] = publication(a, goals=a['published']['snapshot']['definition']['required_goals'], source='1', name='SYNTHETIC explicit never-accepted closed-history replacement')
    newpairs = bind_all(a, 2)
    for release, _ in oldpairs:
        with a['catalog'].connection() as c:
            revision = catalogs.proof(catalogs.row(c, 'park-a'))['revision']
        a['catalog'].withdraw_release('park-a', uuid4().hex, release['release_id'], revision, 'SYNTHETIC original superseded release retirement')
    old_preflights = [checker.preview(f[2]['fixture-a'], UUID(p['preparation_id']), original_release_id=r['release_id'], original_instance_id=i['instance_id'], target_instance_id=ni['instance_id']) for (r, i), (_, ni) in zip(oldpairs, newpairs)]
    assert all(q['classification'] == 'UNKNOWN' for q in old_preflights)
    for op, actor in (('REOPEN', 'fixture-a'), ('REVIEW', REVIEWER), ('CONFIRM', 'fixture-a')):
        r = command(f, p, op, actor, reason='SYNTHETIC fresh closed-history catalog review ' + op)
        assert r.status_code == 200, r.text
        p = r.json()
    generate(a, p, old['revision'])
    verified(f, p, 'P1')
    with f[1].connect() as c:
        new = deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['service_case_plan'])
    t.update(p=p, new=new, newpairs=newpairs, old_preflights=old_preflights)
    stage('new_adopted')
    return t


@pytest.fixture
def closure_case(capability_resource_catalog, tmp_path, request):
    value = getattr(request, 'param', {})
    if isinstance(value, str):
        value = dict(action=value)
    return build_closure(capability_resource_catalog, tmp_path, **value)
