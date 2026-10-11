"""Bounded original T07: real ordinary HTTP, owned PG and CLI worker, no bridge.

The executor assignment in the B fixture is an explicit administrative test
precondition. The A case proves that a normal fresh Run cannot create it.
"""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import socket
import time
from uuid import UUID, uuid4

import pytest
import httpx
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
        self.api_processes = []
        self.proofs = []
        with self.f[0].connect() as c:
            self.pg = c.execute('SELECT current_database() database, current_user app_role, '
                'pg_backend_pid() backend_pid, version() version, pg_postmaster_start_time() server_started').fetchone()
        self.initial_counts = {t: len(v) for t, v in self.business().items()}

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
            added = [r for r in after['run_assignments'] if r not in before['run_assignments']]
            assert len(added) == 1 and all(r in after['run_assignments'] for r in before['run_assignments'])
            assert (str(added[0]['run_id']), added[0]['principal_id'], added[0]['park_id'],
                    added[0]['org_id'], added[0]['active'], added[0].get('managed_access')) == (
                    run, 'executor-a', 'park-a', 'org-a', True, None)
            self.setup.append(dict(kind='EXISTING_OWNER_ONLY_SYNTHETIC_ASSIGN_STATUS_PRECONDITION',
                                   run_id=run, setup_actor='OWNED_SYNTHETIC_FIXTURE_DATABASE_OWNER',
                                   target_executor_id='executor-a', added_assignment=added[0], business_API=False,
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
        assert recovery['event']['expected_revision'] == body['expected_revision']
        actor_hash = hashlib.sha256(json.dumps({'actor_id': 'fixture-a'}, sort_keys=True,
                                              separators=(',', ':')).encode()).hexdigest()
        assert recovery['event']['actor_ref'] == actor_hash
        assert recovery['preparation_id'] == p['preparation_id']
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
        before = self.business()
        self.post('/api/synthetic-resources/'+str(resource_holds.RESOURCE_ID)+'/holds', data, status=409)
        assert self.business() == before
        preview = self.post('/api/synthetic-resources/'+str(resource_holds.RESOURCE_ID)+'/preview',
                            {k:data[k] for k in ['starts_at', 'ends_at', 'quantity']})
        assert preview['occupied_peak'] == 2 and not preview['available']
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

    def reject_close(self, p):
        view = self.get(self.path(p, '/local-case')); before = self.business()
        self.post(self.path(p, '/local-case/commands'), dict(action='CLOSE_LOCAL_RECORD',
            expected_revision=view['revision'], expected_cycle=view['cycle'],
            expected_snapshot_sha256=view['current_snapshot_sha256'],
            reason='SYNTHETIC missing current receipt acknowledgement must block closure'), status=409)
        assert self.business() == before

    @contextmanager
    def cold_api(self):
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen()
        port = listener.getsockname()[1]
        argv = [sys.executable, '-m', 'uvicorn', 'parkweave.api:configured_app', '--factory',
                '--log-level', 'warning', '--no-access-log']
        options = {}
        if os.name == 'nt':
            listener.close(); argv += ['--host', '127.0.0.1', '--port', str(port)]
        else:
            argv += ['--fd', str(listener.fileno())]; options['pass_fds'] = (listener.fileno(),)
        env = minimal_environment(os.environ, PARKWEAVE_DSN=self.f[0].dsn, PARKWEAVE_MODE='LOCAL')
        started = datetime.now(timezone.utc).isoformat()
        child = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, **options)
        old_client = self.f[3]
        try:
            with httpx.Client(base_url='http://127.0.0.1:'+str(port), timeout=2) as client:
                end = time.monotonic()+10
                while time.monotonic() < end and child.poll() is None:
                    try:
                        if client.get('/health').status_code == 200: break
                    except httpx.HTTPError: pass
                    time.sleep(.02)
                else: raise AssertionError('owned cold API failed to become ready')
                self.f = self.f[:3]+(client,)
                yield
        finally:
            self.f = self.f[:3]+(old_client,)
            child.terminate()
            stdout, stderr = child.communicate(timeout=10)
            listener.close()
            self.api_processes.append(dict(argv=argv, pid=child.pid, started_utc=started,
                ended_utc=datetime.now(timezone.utc).isoformat(), exit_code=child.returncode,
                stdout=stdout, stderr=stderr, DSN_recorded=False, configured_app=True, mock=False))

    def assert_outputs(self, p, combo, d, s, outputs):
        """Read persisted provenance independently of goal-results' own projection."""
        rows = self.business()
        one = lambda table, id: next(r for r in rows[table] if str(r['id']) == id)
        prep = one('preparations', p['preparation_id'])
        assert (str(prep['case_id']), str(prep['run_id']), prep['owner_id'], prep['park_id'],
                prep['org_id'], prep['revision']) == (p['case_id'], p['run_id'], 'fixture-a', 'park-a', 'org-a', p['revision'])
        assert (outputs['case_id'], outputs['run_id'], outputs['preparation_id']) == (
                p['case_id'], p['run_id'], p['preparation_id'])
        actual = {r['adapter_id']: r['actual_output'] for r in outputs['results']}
        evidence = [r for r in rows['preparation_evidence'] if str(r['preparation_id']) == p['preparation_id']]
        assert len(evidence) == 2
        assert actual['P1']['preparation_id'] == p['preparation_id']
        assert actual['P1']['snapshot_sha256'] == prep['review_sha256']
        for material in actual['P1']['materials']:
            row = one('preparation_evidence', material['evidence_id'])
            assert row in evidence and row['actor_id'] == 'fixture-a'
            assert (row['slot'], row['version'], row['source_sha256']) == (
                    material['slot'], material['version'], material['source_sha256'])
            assert hashlib.sha256(row['text'].encode()).hexdigest() == material['source_sha256']
        for action, field, actor in [('REVIEW', 'review_event_id', 'prep-specialist-fixture-a'),
                                     ('CONFIRM', 'confirm_event_id', 'fixture-a')]:
            event = one('preparation_events', actual['P1'][field])
            assert (str(event['preparation_id']), event['action'], event['actor_id']) == (p['preparation_id'], action, actor)
        link = one('case_resource_links', actual['P2']['resource_link_id'])
        assert (str(link['case_id']), str(link['run_id']), str(link['preparation_id']),
                str(link['combination_id']), link['revision']) == (p['case_id'], p['run_id'], p['preparation_id'], combo['id'], actual['P2']['resource_link_revision'])
        assert actual['P2']['combination_id'] == combo['id'] and actual['P2']['combination_state'] == 'CONFIRMED'
        member_ids = {str(r['hold_id']) for r in rows['synthetic_resource_combination_members']
                      if str(r['combination_id']) == combo['id']}
        members = [r for r in rows['synthetic_resource_holds'] if str(r['id']) in member_ids]
        assert len(members) == len(actual['P2']['members']) == 2
        for member in actual['P2']['members']:
            row = one('synthetic_resource_holds', member['id']); assert row in members
            for field in ['resource_id', 'resource_revision', 'starts_at', 'ends_at', 'buffer_seconds', 'quantity', 'state']:
                assert str(row[field]) == str(member[field]), field
        accept = one('service_dispatch_events', actual['P3']['acceptance_event_id'])
        assert (str(accept['dispatch_id']), str(accept['offer_id']), accept['actor_id'], accept['action']) == (
                d['dispatch_id'], d['current_offer']['id'], 'executor-a', 'ACCEPT')
        offer = one('service_dispatch_offers', actual['P3']['offer_id'])
        assert offer['state'] == 'ACCEPTED' and str(offer['receipt_step_id']) == d['receipt_step_id']
        assert (actual['P3']['dispatch_id'], actual['P3']['executor_id'], actual['P3']['receipt_step_id']) == (d['dispatch_id'], 'executor-a', s['step']['id'])
        step = one('service_receipt_steps', s['step']['id'])
        assert (str(step['case_id']), str(step['run_id']), str(step['preparation_id']),
                str(step['current_receipt_id']), step['state']) == (p['case_id'], p['run_id'], p['preparation_id'], s['current_receipt']['id'], 'LOCAL_ACKNOWLEDGED')
        output = actual['P4']; receipt = one('service_step_receipts', output['receipt_id'])
        assert output['kind'] == 'MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT' and output['execution_id'] is None
        assert (output['receipt_step_id'], output['receipt_id'], output['receipt_version'], output['receipt_sha256']) == (
                s['step']['id'], s['current_receipt']['id'], receipt['version'], hashlib.sha256(receipt['text'].encode()).hexdigest())
        for action, field, actor in [('SUBMIT', 'submit_event_ids', 'executor-a'), ('ACKNOWLEDGE', 'ack_event_ids', 'fixture-a')]:
            expected = [str(r['id']) for r in rows['service_receipt_events'] if str(r['step_id']) == s['step']['id'] and r['action'] == action and r['payload'].get('receipt_id') == output['receipt_id']]
            assert sorted(output[field]) == sorted(expected) and expected
            for id in expected:
                event = one('service_receipt_events', id)
                assert event['actor_id'] == actor and event['payload']['receipt_sha256'] == output['receipt_sha256']
        local = next(r for r in rows['case_local_lifecycles'] if str(r['preparation_id']) == p['preparation_id'])
        event = one('case_local_events', actual['P5']['revalidation_event_id'])
        assert (event['action'], event['actor_id'], event['cycle']) == ('REVALIDATE', 'fixture-a', local['cycle'])
        assert (actual['P5']['cycle'], actual['P5']['revision'], actual['P5']['local_record_state'], actual['P5']['source_sha256']) == (local['cycle'], local['revision'], local['state'], local['verified_sha256'])
        plan = prep['service_case_plan']; assert outputs['plan_id'] == plan['id'] and outputs['plan_revision'] == plan['revision']
        for result in outputs['results']:
            verify = next(e for e in plan['events'] if e['id'] == result['historical_verification']['id'])
            assert (verify['action'], verify['actor_id'], verify['step_id']) == ('VERIFY', 'fixture-a', result['step_id'])
            sha = hashlib.sha256(json.dumps(verify['sources'], sort_keys=True,
                separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
            step = next(r for r in plan['steps'] if r['id'] == result['step_id'])
            assert sha == verify['source_sha256'] == step['verified_sha256']
            assert verify['sources'] == step['verified_sources']
            assert result['historical_verification']['current']
        self.proofs.append(dict(case_id=p['case_id'], run_id=p['run_id'], preparation_id=p['preparation_id'],
                outputs=actual, persisted_provenance_asserted=True, business_sha256=fingerprint(rows)))

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
        self.reject_close(p)
        s = self.receipt_action(self.receipt(d), 'SUBMIT', text='SYNTHETIC T07 '+label+' actual receipt v1')
        self.reject_close(p)
        if feedback:
            s = self.receipt_action(s, 'REQUEST_CHANGES')
            view = self.get(self.path(p, '/goal-results')); assert view['state'] != 'LOCAL_OUTPUTS_VERIFIED'
            s = self.receipt_action(s, 'SUBMIT', text='SYNTHETIC T07 '+label+' corrected receipt v2')
        before = self.business()
        self.post('/api/executor-receipts/'+s['step']['id']+'/commands',
            dict(action='ACKNOWLEDGE', expected_revision=s['step']['revision'], receipt_sha256='0'*64,
                 reason='SYNTHETIC stale receipt hash must not acknowledge'), status=409)
        assert self.business() == before
        s = self.receipt_action(s, 'ACKNOWLEDGE'); self.verify(p, 'P4')
        self.local(p, 'REVALIDATE'); self.verify(p, 'P5')
        outputs = self.get(self.path(p, '/goal-results'))
        assert outputs['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(outputs['results']) == 5
        assert all(r['state'] == 'LOCAL_OUTPUT_VERIFIED' for r in outputs['results'])
        receipt = next(r['actual_output'] for r in outputs['results'] if r['adapter_id'] == 'P4')
        assert receipt['kind'] == 'MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT' and receipt['execution_id'] is None
        assert not outputs['case_goal_completed']
        self.assert_outputs(p, combo, d, s, outputs)
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
                owned_postgres=value.pg, initial_business_counts=value.initial_counts,
                final_business_counts={t:len(v) for t,v in value.business().items()},
                persisted_chain_proofs=value.proofs, requests=value.trace,
                independent_worker_processes=value.workers, cold_api_processes=value.api_processes), indent=2, default=str)+'\n')


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
    key = next(r['request_key'] for r in u.trace if r['path'] == u.path(p, '/commands')
               and r['request_body'].get('slot') == 'material_outline')
    before = u.business()
    u.get(u.path(again, '/command-recovery'), key=key, status=409)
    u.post(u.path(p, '/commands'), dict(action='REOPEN', expected_revision=p['revision']-1,
        reason='SYNTHETIC stale material version must not reopen'), status=409)
    assert u.business() == before
    for table, rows in first.items():
        assert all(row in u.business()[table] for row in rows), table
    # A fresh ordinary configured_app subprocess has no copied in-process session.
    with u.cold_api():
        before = u.business(); result = u.get(u.path(p, '/goal-results'))
        assert result['state'] == 'LOCAL_OUTPUTS_VERIFIED' and u.business() == before
        u.assert_outputs(p, g, d, s, result)
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
    notice = u.get('/api/dispatch-notices', actor='executor-a')['items'][0]
    original = u.business()
    v = u.get(u.path(p, '/case-cancellation')); key = str(uuid4())
    body = dict(case_id=v['case_id'], expected_preparation_revision=v['preparation_revision'],
                expected_lifecycle_revision=v['lifecycle_revision'], expected_source_sha256=v['source_sha256'],
                confirm_cancel=True, reason='SYNTHETIC T07 owner cancels before actual acceptance')
    done = u.post(u.path(p, '/case-cancellation'), body, key=key)
    u.get(u.path(p, '/case-cancellation/recovery/'+key))
    u.post('/api/service-dispatches/'+d['dispatch_id']+'/commands', dict(action='ACCEPT', expected_revision=d['revision'], reason='SYNTHETIC late offer acceptance'), actor='executor-a', status=409)
    u.worker()
    notices = u.get('/api/dispatch-notices', actor='executor-a')['items']
    assert any(n['event_id'] == notice['event_id'] and n['case_cancelled'] and not n['actionable'] for n in notices)
    for action in ['OPEN', 'MARK_READ']:
        opened = u.post('/api/dispatch-notices/'+notice['event_id']+'/commands',
            dict(action=action, expected_revision=notice['revision']), actor='executor-a')['notice']
        assert opened['case_cancelled'] and not opened['actionable']
    preview_body = {k:data[k] for k in ['starts_at', 'ends_at', 'quantity']}
    preview_path = '/api/synthetic-resources/'+str(resource_holds.RESOURCE_ID)+'/preview'
    assert u.post(preview_path, preview_body)['occupied_peak'] == 2
    after = u.business()
    for table in original:
        if table not in ['cases', 'case_local_lifecycles', 'case_local_events']:
            assert after[table] == original[table], table
    u.post('/api/resource-combinations/'+g['id']+'/cancel', {})
    assert u.post(preview_path, preview_body)['occupied_peak'] == 0
    assert done['event']['case_state'] == 'CANCELLED'
    assert u.get(u.path(p, '/dispatch'), actor='executor-a')['current_offer']['state'] == 'OFFERED'


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
