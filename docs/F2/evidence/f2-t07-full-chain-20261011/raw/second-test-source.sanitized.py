"""Bounded original T07: real ordinary HTTP, owned PG and CLI worker, no bridge.

The executor assignment in the B fixture is an explicit administrative test
precondition. The A case proves that a normal fresh Run cannot create it.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from parkweave.store import Store
from parkweave import preparation, resource_holds, resource_combinations
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_case_resources import link_fixture
from test_new_enterprise_local_chain import actual_http
from test_service_case_steps import GOALS


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class Chain:
    def __init__(self, f, client, name):
        self.f = f[:3] + (client,)
        self.name = name
        self.trace = []
        self.workers = []
        self.setup = []

    def __repr__(self):
        return '<T07 ordinary API/PG synthetic chain; no credentials in repr>'

    def request(self, method, path, body=None, actor='fixture-a', key=None, status=200):
        key = key or (str(uuid4()) if method == 'POST' else None)
        r = self.f[3].request(method, path, headers=headers(self.f[2], actor, key),
                              **({'json': body} if body is not None else {}))
        try: payload = r.json()
        except ValueError: payload = r.text
        self.trace.append(dict(sequence=len(self.trace)+1, utc=datetime.now(timezone.utc).isoformat(),
                               method=method, path=path, actor=actor, request_key=key,
                               request_body=body, request_sha256=fingerprint(body),
                               status=r.status_code, response=payload))
        assert r.status_code == status, (method, path, r.status_code, r.text)
        return payload

    def get(self, path, **kw): return self.request('GET', path, **kw)
    def post(self, path, body, **kw): return self.request('POST', path, body, **kw)

    def worker(self):
        argv = [sys.executable, '-m', 'parkweave.worker', '--once']
        env = minimal_environment(os.environ, PARKWEAVE_DSN=self.f[0].dsn, PARKWEAVE_MODE='LOCAL')
        started = datetime.now(timezone.utc).isoformat()
        p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        timed_out = False
        try: stdout, stderr = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out = True
            p.terminate()
            try: stdout, stderr = p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); stdout, stderr = p.communicate(timeout=5)
        self.workers.append(dict(argv=argv, pid=p.pid, started_utc=started,
                                 ended_utc=datetime.now(timezone.utc).isoformat(),
                                 exit_code=p.returncode, stdout=stdout, stderr=stderr,
                                 mode='LOCAL', mock=False, DSN_recorded=False, timed_out=timed_out))
        assert p.returncode == 0 and not timed_out, (stdout, stderr)

    def rows(self, tables):
        with self.f[1].connect() as c:
            return {t: c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in tables}

    def authority(self):
        return self.rows(['principals', 'capability_grants', 'field_grants', 'preparation_grants',
                          'action_grants', 'synthetic_resource_grants', 'run_assignments'])

    def business(self):
        return self.rows(['runs', 'operations', 'cases', 'preparations', 'preparation_evidence',
                          'preparation_events', 'case_resource_links', 'resource_case_claims',
                          'synthetic_resource_holds', 'synthetic_resource_combinations',
                          'synthetic_resource_combination_members', 'synthetic_resource_combination_receipts',
                          'service_dispatches', 'service_dispatch_offers', 'service_dispatch_events',
                          'service_receipt_steps', 'service_step_receipts', 'service_receipt_events',
                          'case_local_lifecycles', 'case_local_events'])

    def new(self, label, assigned=False):
        run_key = str(uuid4())
        body = {'goal': 'SYNTHETIC T07 '+label+' new composite local request'}
        run = self.post('/api/runs', body, key=run_key, status=202)['run_id']
        self.worker()
        saved = self.get('/api/runs/'+run)
        assert saved['state'] == 'SUCCEEDED' and saved['success_scope'] == 'LOCAL_CASE_CREATED'
        assert saved['operation']['state'] == 'VERIFIED' and saved['case']['state'] == 'NEEDS_INPUT'
        assert self.post('/api/runs', body, key=run_key, status=202)['run_id'] == run
        assert self.post('/api/runs', {'goal': body['goal']+' different'}, key=run_key, status=409)
        if assigned:
            before = self.authority()
            self.f[1].assign_status('executor-a', UUID(run), active=True)
            after = self.authority()
            assert all(after[t] == before[t] for t in before if t != 'run_assignments')
            self.setup.append(dict(kind='EXISTING_OWNER_ONLY_SYNTHETIC_ASSIGN_STATUS_PRECONDITION',
                                   run_id=run, actor='executor-a', business_API=False,
                                   formal_new_Run_authorization_acceptance=False,
                                   before_sha256=fingerprint(before), after_sha256=fingerprint(after),
                                   capability_grants_unchanged=True, trust_registry_created=False))
        p = self.post('/api/preparations', dict(run_id=run, service_id=preparation.SERVICE,
                      service_version=1, reviewer_id='prep-specialist-fixture-a'), status=201)
        assert p['case_id'] == saved['case']['id']
        return p

    def path(self, p, suffix=''): return '/api/preparations/'+p['preparation_id']+suffix

    def material(self, p, action, actor='fixture-a', **fields):
        return self.post(self.path(p, '/commands'), dict(action=action, expected_revision=p['revision'], **fields), actor=actor)

    def prepared(self, label='first', assigned=True):
        p = self.new(label, assigned)
        p = self.post(self.path(p, '/request-intent'), dict(expected_preparation_revision=p['revision'],
                      request_text='SYNTHETIC T07 '+label+' independently selected five local goals', required_goals=GOALS))
        p = self.material(p, 'REQUEST_CHANGES', 'prep-specialist-fixture-a', reason='SYNTHETIC T07 two missing material slots')
        before = self.business()
        self.post(self.path(p, '/commands'), dict(action='REVIEW', expected_revision=p['revision'],
                  reason='SYNTHETIC T07 must not approve missing materials'), actor='prep-specialist-fixture-a', status=409)
        assert self.business() == before
        evidence_key = str(uuid4())
        p = self.material(p, 'ADD_EVIDENCE', slot='need_summary', text='SYNTHETIC T07 '+label+' new need',
                          source_kind='USER_STATEMENT', source_label='SYNTHETIC new user statement')
        body = dict(action='ADD_EVIDENCE', expected_revision=p['revision'], slot='material_outline',
                    text='SYNTHETIC T07 '+label+' new outline', source_kind='DOCUMENT_EXCERPT',
                    source_label='SYNTHETIC current document')
        p = self.post(self.path(p, '/commands'), body, key=evidence_key)
        # Only GET observes the committed original key after simulated caller response loss.
        before = self.business()
        recovered = self.get(self.path(p, '/command-recovery'), key=evidence_key)
        assert recovered['status'] == 'COMMITTED' and recovered['event'] == p
        assert self.business() == before
        p = self.material(p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC test-driven independent material review')
        p = self.material(p, 'CONFIRM', reason='SYNTHETIC test-driven enterprise explicitly confirms')
        return p

    def adopt(self, p):
        view = self.get(self.path(p, '/planning-preview'))['current']
        plan = self.get(self.path(p, '/service-case-plan'))
        return self.post(self.path(p, '/service-case-plan'), dict(expected_preparation_revision=p['revision'],
                         expected_request_revision=plan['request_revision'], expected_plan_revision=0,
                         expected_source_sha256=view['source_sha256'], required_goals=GOALS,
                         reason='SYNTHETIC explicit registered finite plan'), status=201)

    def verify(self, p, adapter):
        view = self.get(self.path(p, '/service-case-plan'))
        step = next(s for s in view['steps'] if s['adapter_id'] == adapter)
        body = dict(action='VERIFY', step_id=step['id'], expected_revision=view['revision'],
                    expected_source_sha256=step['source_sha256'], reason='SYNTHETIC test-driven owner verifies '+adapter)
        key = str(uuid4())
        done = self.post(self.path(p, '/service-case-plan/commands'), body, key=key)
        assert next(s for s in done['steps'] if s['adapter_id'] == adapter)['state'] == 'VERIFIED'
        before = self.business()
        recovery = self.get(self.path(p, '/service-case-plan/command-recovery'), key=key)
        assert recovery['status'] == 'COMMITTED' and recovery['historical_only']
        assert not recovery['automatically_replayed'] and recovery['read_only']
        assert (recovery['case_id'], recovery['run_id']) == (p['case_id'], p['run_id'])
        for field in ['id', 'plan_id', 'revision', 'action', 'step_id']:
            assert recovery['event'][field] == done['event'][field]
        assert recovery['event']['request_key'] == key
        assert self.business() == before
        return done

    def resources(self, p, offset=0):
        with self.f[1].connect() as c:
            now = c.execute('SELECT clock_timestamp() t').fetchone()['t']
        data = dict(starts_at=(now+timedelta(hours=1+offset)).isoformat(),
                    ends_at=(now+timedelta(hours=2+offset)).isoformat(), quantity=2,
                    expected_revision=1, ttl_seconds=300, purpose='SYNTHETIC same-Case T07 resource use')
        hs = [self.post('/api/synthetic-resources/'+str(id)+'/holds', data, status=201)['hold']
              for id in [resource_holds.RESOURCE_ID, resource_combinations.SECOND_RESOURCE_ID]]
        combo = self.post('/api/resource-combinations', dict(members=[dict(hold_id=h['id'], expected_revision=h['resource_revision']) for h in hs]), status=201)['combination']
        self.post(self.path(p, '/resource-link'), dict(combination_id=combo['id'],
                  expected_preparation_revision=p['revision'], expected_link_revision=0,
                  reason='SYNTHETIC explicit same-Case resource association'), status=201)
        return combo, data

    def offer(self, p, revision=0):
        return self.post(self.path(p, '/dispatch'), dict(expected_preparation_revision=p['revision'],
                         expected_dispatch_revision=revision, executor_id='executor-a',
                         reason='SYNTHETIC specialist offers current existing assignment'),
                         actor='prep-specialist-fixture-a', status=201)

    def decision(self, d, action):
        return self.post('/api/service-dispatches/'+d['dispatch_id']+'/commands',
                         dict(action=action, expected_revision=d['revision'], reason='SYNTHETIC counterparty '+action),
                         actor='executor-a')

    def receipt(self, d): return self.get('/api/executor-receipts/'+d['receipt_step_id'], actor='executor-a')

    def receipt_action(self, s, action, **fields):
        body = dict(action=action, expected_revision=s['step']['revision'])
        if action == 'SUBMIT':
            body.update(text='SYNTHETIC T07 actual manually provided local work record', source_kind='SYNTHETIC', source_label='SYNTHETIC manual work log')
        else: body.update(reason='SYNTHETIC test-driven enterprise '+action, receipt_sha256=s['current_receipt']['source_sha256'])
        body.update(fields)
        return self.post('/api/executor-receipts/'+s['step']['id']+'/commands', body,
                         actor='executor-a' if action == 'SUBMIT' else 'fixture-a')

    def local(self, p, action):
        view = self.get(self.path(p, '/local-case'))
        body = dict(action=action, expected_revision=view['revision'], expected_cycle=view['cycle'], reason='SYNTHETIC test-driven explicit '+action)
        if action != 'REOPEN': body['expected_snapshot_sha256'] = view['current_snapshot_sha256']
        return self.post(self.path(p, '/local-case/commands'), body)

    def completed(self, label='first', offset=0, feedback=False):
        p = self.prepared(label)
        authority = self.authority()
        self.adopt(p); self.verify(p, 'P1')
        combo, data = self.resources(p, offset); self.verify(p, 'P2')
        d = self.offer(p)
        if feedback:
            d = self.decision(d, 'DECLINE')
            for action in ['REPORT_FAILURE', 'RETRY']:
                view = self.get(self.path(p, '/service-case-plan')); step = next(s for s in view['steps'] if s['adapter_id'] == 'P3')
                self.post(self.path(p, '/service-case-plan/commands'), dict(action=action, step_id=step['id'], expected_revision=view['revision'], reason='SYNTHETIC explicit declined step '+action), actor='prep-specialist-fixture-a')
            d = self.offer(p, d['revision'])
        d = self.decision(d, 'ACCEPT'); self.worker(); self.verify(p, 'P3')
        s = self.receipt_action(self.receipt(d), 'SUBMIT', text='SYNTHETIC T07 '+label+' actual receipt v1')
        if feedback:
            s = self.receipt_action(s, 'REQUEST_CHANGES')
            view = self.get(self.path(p, '/goal-results')); assert view['state'] != 'LOCAL_OUTPUTS_VERIFIED'
            s = self.receipt_action(s, 'SUBMIT', text='SYNTHETIC T07 '+label+' corrected receipt v2')
        s = self.receipt_action(s, 'ACKNOWLEDGE'); self.verify(p, 'P4')
        self.local(p, 'REVALIDATE'); self.verify(p, 'P5')
        outputs = self.get(self.path(p, '/goal-results'))
        assert outputs['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(outputs['results']) == 5
        assert all(r['state'] == 'LOCAL_OUTPUT_VERIFIED' for r in outputs['results'])
        receipt = next(r['actual_output'] for r in outputs['results'] if r['adapter_id'] == 'P4')
        assert receipt['kind'] == 'MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT' and receipt['execution_id'] is None
        assert not outputs['case_goal_completed']
        assert self.authority() == authority
        return p, combo, data, d, s


@pytest.fixture
def chain(link_fixture, request):
    # Original fixture setup only: exact owned UUID DB, fixed synthetic identities,
    # existing material/resource/table rights, no new bridge/Grant/registry.
    f = link_fixture
    with f[1].connect() as c:
        assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] == 0 for t in ['runs', 'cases', 'run_assignments'])
    with actual_http(create_app(f[0])) as (client, _):
        value = Chain(f, client, request.node.nodeid)
        try: yield value
        finally:
            out = Path(os.environ.get('PARKWEAVE_T07_EVIDENCE_DIR', '.runtime/f2-t07-full-chain/exploratory'))
            out.mkdir(parents=True, exist_ok=True)
            target = out/(hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]+'.json')
            assert not target.exists(), 'actual evidence window may not overwrite a previous run'
            target.write_text(json.dumps(dict(test_id=value.name, scope='SYNTHETIC_ORDINARY_HTTP_PG_MANUAL_CHAIN',
                browser_attempts=0, formal_AT35=False, fixture_assignment_preconditions=value.setup,
                requests=value.trace, independent_worker_processes=value.workers), indent=2, default=str)+'\n')


def test_fresh_ordinary_chain_exposes_missing_production_run_access_without_repair(chain):
    u = chain; p = u.prepared('ordinary-default', assigned=False)
    authority = u.authority(); u.adopt(p); u.verify(p, 'P1'); u.resources(p); u.verify(p, 'P2')
    status = u.get('/api/run-access/status'); assert not status['enabled']
    u.get('/api/runs/'+p['run_id']+'/access', status=403)
    before = u.business()
    u.post(u.path(p, '/dispatch'), dict(expected_preparation_revision=p['revision'], expected_dispatch_revision=0,
           executor_id='executor-a', reason='SYNTHETIC no assignment must remain blocked'), actor='prep-specialist-fixture-a', status=403)
    assert u.business() == before and u.authority() == authority
    outputs = u.get(u.path(p, '/goal-results')); assert outputs['state'] != 'LOCAL_OUTPUTS_VERIFIED'
    assert not outputs['case_goal_completed']


def test_whole_local_chain_cold_read_and_two_new_inputs_keep_first_history(chain):
    u = chain; p, g, data, d, s = u.completed('first')
    first = u.business()
    again, _, _, _, s2 = u.completed('second', offset=24)
    assert all(p[k] != again[k] for k in ['case_id', 'run_id', 'preparation_id'])
    assert s['current_receipt']['id'] != s2['current_receipt']['id']
    for table, rows in first.items():
        assert all(row in u.business()[table] for row in rows), table
    # A fresh API/Store has no isolated authority bridge or copied session state.
    with actual_http(create_app(Store(u.f[0].dsn))) as (client, _):
        old_client = u.f[3]; u.f = u.f[:3]+(client,)
        before = u.business(); result = u.get(u.path(p, '/goal-results'))
        assert result['state'] == 'LOCAL_OUTPUTS_VERIFIED' and u.business() == before
        u.f = u.f[:3]+(old_client,)
    with u.f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n'] == 2
        assert not c.execute("SELECT 1 FROM cases WHERE state='FULFILLED'").fetchone()


def test_failure_correction_delivery_feedback_and_explicit_local_reopen_preserve_history(chain):
    u = chain; p, g, data, d, s = u.completed(feedback=True)
    assert [r['version'] for r in s['receipt_history']] == [1, 2]
    original = u.business()
    s = u.receipt_action(s, 'REOPEN')
    assert u.get(u.path(p, '/goal-results'))['state'] != 'LOCAL_OUTPUTS_VERIFIED'
    s = u.receipt_action(s, 'SUBMIT', text='SYNTHETIC T07 delivery feedback actual receipt v3')
    s = u.receipt_action(s, 'ACKNOWLEDGE'); u.verify(p, 'P4'); u.local(p, 'REVALIDATE'); u.verify(p, 'P5')
    assert [r['version'] for r in s['receipt_history']] == [1, 2, 3]
    closed = u.local(p, 'CLOSE_LOCAL_RECORD'); assert closed['local_record_state'] == 'LOCAL_RECORD_CLOSED'
    assert not closed['case_goal_completed']
    u.verify(p, 'P5')
    opened = u.local(p, 'REOPEN'); assert opened['cycle'] == 2 and opened['local_record_state'] == 'REOPENED'
    u.local(p, 'REVALIDATE'); u.verify(p, 'P5')
    assert u.get(u.path(p, '/goal-results'))['state'] == 'LOCAL_OUTPUTS_VERIFIED'
    after = u.business()
    for table in ['preparation_evidence', 'preparation_events', 'service_dispatch_events', 'service_step_receipts', 'service_receipt_events']:
        assert all(r in after[table] for r in original[table]), table


@pytest.mark.parametrize('actor', ['fixture-b', 'fixture-c', 'executor-b', 'unassigned'])
def test_cross_tenant_chain_outputs_materials_receipts_and_late_confirmation_are_denied(chain, actor):
    u = chain; p, _, _, d, s = u.completed()
    before = u.business()
    for path in [u.path(p), u.path(p, '/goal-results'), u.path(p, '/local-case'), '/api/executor-receipts/'+d['receipt_step_id']]:
        response = u.get(path, actor=actor, status=403)
        assert 'SYNTHETIC T07 first new outline' not in json.dumps(response)
    u.post('/api/executor-receipts/'+s['step']['id']+'/commands',
           dict(action='ACKNOWLEDGE', expected_revision=s['step']['revision'], receipt_sha256=s['current_receipt']['source_sha256'], reason='SYNTHETIC forbidden late confirmation'), actor=actor, status=403)
    assert u.business() == before


def test_current_owner_revocation_blocks_cold_original_material_key_and_delivery_read(chain):
    u = chain; p, _, _, _, _ = u.completed()
    evidence = next(x for x in u.trace if x['request_body'] and x['request_body'].get('slot') == 'material_outline')
    # Existing explicit synthetic administrative revocation; never regrant.
    u.f[1].revoke_capability('fixture-a', 'READ')
    before = u.business()
    u.get(u.path(p, '/command-recovery'), key=evidence['request_key'], status=403)
    u.get(u.path(p, '/goal-results'), status=403)
    assert u.business() == before


def test_offer_cancel_retains_capacity_and_history_until_independent_release(chain):
    u = chain; p = u.prepared(); u.adopt(p); u.verify(p, 'P1')
    g, data = u.resources(p); u.verify(p, 'P2'); d = u.offer(p); u.worker()
    original = u.business()
    v = u.get(u.path(p, '/case-cancellation')); key = str(uuid4())
    body = dict(case_id=v['case_id'], expected_preparation_revision=v['preparation_revision'],
                expected_lifecycle_revision=v['lifecycle_revision'], expected_source_sha256=v['source_sha256'],
                confirm_cancel=True, reason='SYNTHETIC T07 owner cancels before actual acceptance')
    done = u.post(u.path(p, '/case-cancellation'), body, key=key)
    u.get(u.path(p, '/case-cancellation/recovery/'+key))
    u.post('/api/service-dispatches/'+d['dispatch_id']+'/commands', dict(action='ACCEPT', expected_revision=d['revision'], reason='SYNTHETIC late offer acceptance'), actor='executor-a', status=409)
    u.worker()
    preview_body = {k:data[k] for k in ['starts_at', 'ends_at', 'quantity']}
    preview_path = '/api/synthetic-resources/'+str(resource_holds.RESOURCE_ID)+'/preview'
    assert u.post(preview_path, preview_body)['occupied_peak'] == 2
    after = u.business()
    for table in original:
        if table not in ['cases', 'case_local_lifecycles', 'case_local_events']:
            assert after[table] == original[table], table
    u.post('/api/resource-combinations/'+g['id']+'/cancel', {})
    assert u.post(preview_path, preview_body)['occupied_peak'] == 0
    assert done['case_state'] == 'CANCELLED'


def test_unsupported_new_goal_and_invalid_inputs_do_not_erase_prior_chain(chain):
    u = chain; p, _, _, _, _ = u.completed()
    before = u.business()
    u.post('/api/runs', dict(goal='SYNTHETIC invalid unknown tool', action='unsafe.tool'), status=422)
    assert u.business() == before
    other = u.new('unsupported', assigned=False)
    other = u.post(u.path(other, '/request-intent'), dict(expected_preparation_revision=other['revision'],
                   request_text='SYNTHETIC must retain external required goal',
                   required_goals=[GOALS[0], 'REAL_EXTERNAL_FULFILLMENT']))
    view = u.get(u.path(other, '/planning-preview'))
    assert view['current']['state'] == 'PARTIAL' and 'REAL_EXTERNAL_FULFILLMENT' in json.dumps(view)
    assert u.get(u.path(p, '/goal-results'))['state'] == 'LOCAL_OUTPUTS_VERIFIED'
    assert u.get(u.path(other, '/goal-results'))['state'] != 'LOCAL_OUTPUTS_VERIFIED'
