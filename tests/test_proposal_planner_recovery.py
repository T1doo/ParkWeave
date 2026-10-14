"""Real PG/API and original HTML NodeVM for proposal attempt recovery only."""
from copy import deepcopy
from pathlib import Path
import json
import os
import selectors
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from test_preparation import preparation_fixture, headers
from test_bounded_planning import setup
from test_plan_preview import digest
from test_isolated_run_access import permission_snapshot
from test_proposal_planner_offline import planner, fake_envelope, GOAL


@pytest.mark.parametrize('mode', ['failed_same', 'failed_cold', 'unknown_cold', 'pending_cold', 'damaged_failed', 'revoke_read', 'backend_bad_outcome', 'frontend_bad_outcome'])
def test_original_page_attempt_recovery_and_explicit_new_key(preparation_fixture, mode):
    f = preparation_fixture
    p = setup(f, [GOAL])
    permissions = [permission_snapshot(f[1])]
    provider_requests = []
    def handler(request):
        provider_requests.append(request.method)
        proposal = json.loads(json.loads(request.content)['messages'][-1]['content'])['proposal']
        if len(provider_requests) == 1:
            if mode == 'pending_cold':
                with f[1].connect() as connection:
                    connection.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
                permissions[0] = permission_snapshot(f[1])
            if mode in ('unknown_cold', 'pending_cold', 'revoke_read', 'backend_bad_outcome', 'frontend_bad_outcome'):
                raise httpx.ConnectError('SYNTHETIC unknown offline producer result', request=request)
            proposal['approved'] = True
        return httpx.Response(200, json=fake_envelope(proposal))
    instance = planner(handler)
    messages = []; summary = None; stderr = ''; proc = None
    output = Path(os.environ.get('PROPOSAL_RECOVERY_EVIDENCE', '.runtime/proposal-planner-recovery-20261014/pages'))
    with TestClient(create_app(f[0], proposal_planner=instance)) as client:
        proc = subprocess.Popen(['node', 'tests/proposal_planner_recovery_actual.js', p['preparation_id'], 'fixture-a', mode],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        selector = selectors.DefaultSelector(); selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            while True:
                assert selector.select(timeout=15), 'recovery page bridge timeout'
                line = proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                if msg.get('revoke_read'):
                    with f[1].connect() as connection:
                        connection.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
                    permissions[0] = permission_snapshot(f[1])
                    proc.stdin.write(b'{}\n'); proc.stdin.flush(); continue
                if msg.get('corrupt_outcome_state'):
                    from psycopg.types.json import Jsonb
                    with f[1].connect() as connection:
                        records = connection.execute('SELECT planning_previews FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['planning_previews']
                        assert records[-1]['planner_attempt']['state'] == 'OUTCOME_UNKNOWN'
                        assert records[-1]['planner_attempt']['outcome'] == 'TRANSPORT_OUTCOME_UNKNOWN'
                        records[-1]['planner_attempt']['state'] = 'FAILED_SAFE'
                        connection.execute('UPDATE preparations SET planning_previews=%s WHERE id=%s', (Jsonb(records), p['preparation_id']))
                    proc.stdin.write(b'{}\n'); proc.stdin.flush(); continue
                if msg.get('result'):
                    summary = msg; break
                request = msg['request']; options = request['options']; method = options.get('method', 'GET')
                body = json.loads(options['body']) if options.get('body') else None
                before = digest(f)
                response = client.request(method, request['path'],
                                          headers=headers(f[2], key=options['headers'].get('Idempotency-Key')), json=body)
                assert response.status_code in (200, 201, 403, 409), response.text
                if method == 'GET':
                    assert digest(f) == before
                assert permission_snapshot(f[1]) == permissions[0]
                actual = response.json(); presented = deepcopy(actual)
                fault = None
                if mode == 'damaged_failed' and request['path'].endswith('/service-plan-candidates/recovery'):
                    assert actual['status'] == 'FAILED_SAFE'
                    presented['attempts'][0]['can_adopt'] = True
                    fault = 'NODEVM_RESPONSE_FAULT_can_adopt_true'
                if mode == 'frontend_bad_outcome' and request['path'].endswith('/service-plan-candidates/recovery'):
                    assert actual['status'] == 'OUTCOME_UNKNOWN'
                    presented['status'] = 'FAILED_SAFE'; presented['attempts'][0]['status'] = 'FAILED_SAFE'
                    fault = 'NODEVM_RESPONSE_FAULT_state_FAILED_SAFE_with_unknown_outcome'
                messages.append(dict(method=method, path=request['path'], status=response.status_code,
                                     key=options['headers'].get('Idempotency-Key'), body=body,
                                     actual_status=actual.get('status'), nodevm_fault=fault))
                proc.stdin.write((json.dumps(dict(status=response.status_code, body=presented)) + '\n').encode()); proc.stdin.flush()
            code = proc.wait(timeout=15); stderr = proc.stderr.read().decode()
            assert code == 0, stderr
            assert summary and summary['result'] == 'PASS'
            expected = 2 if mode.startswith('failed_') else 1
            assert len(provider_requests) == expected and instance.budget.calls == expected
            assert sum(x['method'] == 'POST' for x in messages) == expected
            assert all(x['method'] == 'GET' for x in messages if x['path'].endswith('/recovery'))
        finally:
            output.mkdir(parents=True, exist_ok=True)
            output.joinpath(mode + '.json').write_text(json.dumps(dict(summary=summary, requests=messages, stderr=stderr,
                                                                      fake_provider_requests=len(provider_requests), actual_provider_requests=0,
                                                                      live_quota_writes=0, browser_runs=0), indent=2) + '\n')
            selector.close()
            if proc.poll() is None:
                proc.terminate(); proc.wait(timeout=5)
