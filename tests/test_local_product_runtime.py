"""Real isolated PostgreSQL, normal worker and loopback HTTP; no API doubles."""
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest

if sys.platform != 'linux':
    pytest.skip('Linux local product only; Windows is not activated', allow_module_level=True)
pytest.importorskip('cryptography')
pytest.importorskip('pgserver')
from parkweave.local_identity import LocalSessionVault
from parkweave.store import Denied, Store
from scripts import material_only_demo as material


def test_sealed_install_http_review_correction_confirmation_and_process_reopen(tmp_path):
    passwords = {role: secrets.token_urlsafe(24) for role in ('enterprise', 'specialist')}
    previous_mask = os.umask(0o077)
    try:
        path = material.setup(session_provider=LocalSessionVault(passwords))
    finally:
        os.umask(previous_mask)
    marker = json.loads((path / 'state.json').read_text())
    assert not (path / 'sessions.json').exists()
    cipher = (path / LocalSessionVault.filename).read_bytes()
    for password in passwords.values():
        assert password.encode() not in cipher
    with pytest.raises(Denied):
        LocalSessionVault.unlock(path, marker, 'enterprise', passwords['specialist'])
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    server = None
    log = (path / 'logs/integration.log').open('a')

    def start():
        nonlocal server
        server = subprocess.Popen([sys.executable, '-B', '-m', 'scripts.local_product', 'start',
            '--state-dir', str(path), '--port', str(port)], cwd=material.ROOT,
            env={**os.environ, 'PYTHONPATH':str(material.ROOT / 'src')}, stdout=log, stderr=log)
        for _ in range(100):
            if server.poll() is not None:
                raise AssertionError('owned local server exited; private logs retained')
            try:
                if httpx.get(base + '/health', timeout=.3).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(.1)
        raise AssertionError('local HTTP readiness timeout')

    def stop():
        nonlocal server
        if server is not None and server.poll() is None:
            server.send_signal(signal.SIGINT)
            server.wait(timeout=25)
            assert server.returncode == 0
        server = None
        assert not (path / 'data/postmaster.pid').exists()
        assert not (path / 'stop-unconfirmed').exists()

    def login(role):
        result = httpx.post(base + '/api/local/session', headers={'Origin':base},
            json=dict(role=role, password=passwords[role]))
        assert result.status_code == 200
        token = result.json()['bearer']
        assert token.encode() not in cipher
        return {'Authorization':'Bearer ' + token}

    def post(route, headers, body, expected=200):
        response = httpx.post(base + route, headers={**headers, 'Idempotency-Key':str(uuid4())}, json=body)
        assert response.status_code == expected, 'original HTTP operation refused; private logs retained'
        return response.json()

    def read(route, headers):
        response = httpx.get(base + route, headers=headers)
        assert response.status_code == 200, 'original HTTP read refused; private logs retained'
        return response.json()

    try:
        start()
        assert httpx.get(base + '/').status_code == 200
        assert 'editor-scroll' in httpx.get(base + '/').text
        assert httpx.post(base + '/api/local/session', json=dict(role='enterprise', password=passwords['enterprise'])).status_code == 403
        assert httpx.post(base + '/api/local/session', headers={'Origin':'https://unrelated.invalid'}, json=dict(role='enterprise', password=passwords['enterprise'])).status_code == 403
        invalid = httpx.post(base + '/api/local/session', headers={'Origin':base},
            json=dict(role='enterprise', password={'private':'do not echo input'}))
        assert invalid.status_code == 422
        assert 'do not echo input' not in invalid.text
        enterprise, reviewer = login('enterprise'), login('specialist')
        run = post('/api/runs', enterprise, dict(goal='SYNTHETIC local product training materials', source='SYNTHETIC'), 202)['run_id']
        for _ in range(60):
            if read('/api/runs/' + run, enterprise)['state'] == 'SUCCEEDED':
                break
            time.sleep(.1)
        else:
            raise AssertionError('normal worker did not finish local case')
        catalog = read('/api/preparation-catalog', enterprise)
        reference = post('/api/preparations', enterprise, dict(run_id=run,
            service_id='synthetic-material-preparation', service_version=1,
            reviewer_id=catalog['reviewers'][0]['id']), 201)
        prep = reference['preparation_id']
        route = '/api/preparations/' + prep

        def command(headers, action, **fields):
            nonlocal reference
            reference = post(route + '/commands', headers,
                dict(action=action, expected_revision=reference['revision'], **fields))

        command(enterprise, 'ADD_EVIDENCE', slot='need_summary', text='SYNTHETIC training request',
            source_kind='DOCUMENT_EXCERPT', source_label='SYNTHETIC document v1')
        command(reviewer, 'REQUEST_CHANGES', reason='Add the material outline and revise training dates')
        command(enterprise, 'ADD_EVIDENCE', slot='need_summary', text='SYNTHETIC training request revised dates',
            source_kind='DOCUMENT_EXCERPT', source_label='SYNTHETIC document v2')
        command(enterprise, 'ADD_EVIDENCE', slot='material_outline', text='SYNTHETIC request and attendee outline',
            source_kind='DOCUMENT_EXCERPT', source_label='SYNTHETIC outline v1')
        for headers, action in [(enterprise, 'REVIEW'), (reviewer, 'CONFIRM')]:
            post(route + '/commands', headers, dict(action=action, expected_revision=reference['revision'],
                reason='wrong role must be refused'), 403)
        command(reviewer, 'REVIEW', reason='Independent specialist reviewed current local materials')
        command(enterprise, 'CONFIRM', reason='Enterprise confirms the current reviewed local materials')
        before = read(route, enterprise)
        assert before['preparation']['state'] == 'LOCAL_CONFIRMED'
        assert len(before['material_history']) == 3
        assert before['qualification'] == 'NOT_EVALUATED'
        assert before['external_acceptance'] == 'NOT_SUBMITTED'
        stop()
        start()
        enterprise, reviewer = login('enterprise'), login('specialist')
        after = read(route, enterprise)
        assert before == after
        assert any(item['id'] == prep for item in read('/api/preparations', reviewer)['items'])
        command(enterprise, 'REOPEN', reason='Explicitly reopen persisted local materials')
        command(reviewer, 'REVIEW', reason='Review again after the explicit reopen')
        command(enterprise, 'CONFIRM', reason='Confirm again after reopen and specialist review')
        final = read(route, enterprise)
        assert final['preparation']['state'] == 'LOCAL_CONFIRMED'
        assert final['preparation']['revision'] == 10
        # A revoked principal remains revoked. Login is never a grant/seed path.
        with Store(material.dsn(path)).connect() as connection:
            Store(material.dsn(path)).lock_principal(connection, marker['ids']['specialist'], exclusive=True)
            connection.execute('UPDATE principals SET active=false WHERE id=%s', (marker['ids']['specialist'],))
        denied = httpx.post(base + '/api/local/session', headers={'Origin':base},
            json=dict(role='specialist', password=passwords['specialist']))
        assert denied.status_code == 403
        summary = dict(source_commit=material.source_binding()['source_commit'],
            runtime_source_sha256=marker['runtime_source_sha256'],
            scope='REAL_LOOPBACK_HTTP_LOCAL_SYNTHETIC_MATERIAL_ONLY',
            commands=[item['action'] for item in final['history']], revision=10,
            process_restart_exact_readback=True, role_isolation=True, revoked_login_refused=True, plaintext_sessions=False,
            browser='NOT_RUN_NATIVE_SANDBOX_REFUSAL', windows='NOT_RUN', state_dir=str(path))
        (tmp_path / 'local-product-result.json').write_text(json.dumps(summary, indent=2))
    finally:
        stop()
        log.close()
