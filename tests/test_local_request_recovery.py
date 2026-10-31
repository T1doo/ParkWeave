"""New recovery operations against original API/SQL; no native acceptance."""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from parkweave import preparation as prep


def identities(owner, tokens):
    import secrets
    values = dict(tokens)
    for name in ('fixture-a','fixture-b','fixture-c'):
        values['prep-specialist-'+name] = secrets.token_urlsafe(32)
    prep.seed_synthetic(owner,values)
    return values


def test_page_unknown_recovery_for_all_other_writes_with_original_api_and_real_pg(fixture):
    store, owner, original, api = fixture
    tokens = identities(owner,original)
    actors = {}
    for name in ('fixture-a','fixture-b','prep-specialist-fixture-a'):
        with store.connect() as c:
            actor = store.auth(c,tokens[name],lock=True)
            actors[name] = dict(bearer=tokens[name],actor={k:actor[k] for k in ('id','park_id','org_id','role')})
    posts = []; interrupted = []
    class Bridge(BaseHTTPRequestHandler):
        # HTTP fault bridge to the original FastAPI/SQL. It is not a browser or
        # normal worker-process acceptance run; the old full-flow evidence is separate.
        def log_message(self,*args):pass
        def handle_request(self):
            count = int(self.headers.get('Content-Length','0'))
            assert 0 <= count < 16384
            body = self.rfile.read(count)
            headers = {k:v for k,v in self.headers.items() if k.lower() in
                ('authorization','idempotency-key','content-type')}
            response = api.request(self.command,self.path,headers=headers,content=body or None)
            if self.command == 'POST':
                posts.append((self.path,headers.get('Idempotency-Key') or headers.get('idempotency-key')))
                if self.path == '/api/runs' and response.status_code == 202:
                    store.finish(store.claim('new-readonly-recovery-test'))
            truncate = self.headers.get('X-Test-Truncate') == '1'
            if truncate:
                assert response.status_code < 300
                interrupted.append(self.path)
            self.send_response(response.status_code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(response.content)))
            self.end_headers()
            self.wfile.write(b'{' if truncate else response.content);self.wfile.flush()
            self.close_connection = True
        do_GET = do_POST = handle_request
    with ThreadingHTTPServer(('127.0.0.1',0),Bridge) as server:
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result = subprocess.run(['node','tests/local_request_recovery_interruption.js'],
                input=json.dumps(dict(base=f'http://127.0.0.1:{server.server_port}',actors=actors)),
                capture_output=True,text=True,timeout=40)
            assert result.returncode == 0,result.stderr
            metrics = json.loads(result.stdout)
        finally:server.shutdown();thread.join(timeout=2)
    assert metrics == dict(recovered=6,interrupted_posts=6,other_identity_reads=0,
        tampered_handle_retained=True,not_observed_retained=True,historical_receipt_recovered=True)
    assert len(interrupted) == 6
    keys = [key for _,key in posts]
    assert len(keys) == len(set(keys))  # every write exactly once; recovery is GET only
    with owner.connect() as c:
        assert c.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) AS n FROM preparations').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) AS n FROM preparation_events').fetchone()['n'] == 9


def test_recovery_is_exact_scoped_read_and_not_an_absence_or_revocation_override(fixture):
    store,owner,original,api = fixture
    tokens = identities(owner,original)
    def h(actor='fixture-a',key=None):
        return {'Authorization':'Bearer '+tokens[actor],'Idempotency-Key':key or str(uuid4())}
    key = str(uuid4())
    result = api.post('/api/runs',headers=h(key=key),json=dict(goal='SYNTHETIC recovery scope')).json()
    run_id = result['run_id']
    url = '/api/local-request-recovery?operation=CREATE_RUN'
    receipt = api.get(url,headers=h(key=key))
    assert receipt.status_code == 200 and receipt.json()['event']['run_id'] == run_id
    assert api.get(url,headers=h('fixture-b',key)).json()['status'] == 'NOT_OBSERVED'
    assert api.get(url,headers=h('prep-specialist-fixture-a',key)).status_code == 403
    assert api.get(url+'&preparation_id='+str(uuid4()),headers=h(key=key)).status_code == 409
    assert api.get(url,headers=h(key='not-uuid')).status_code == 422
    store.finish(store.claim('recovery-scope-test'))
    prep_key = str(uuid4())
    created = api.post('/api/preparations',headers=h(key=prep_key),json=dict(run_id=run_id,
        service_id=prep.SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a')).json()
    id = created['preparation_id']
    assert api.get('/api/local-request-recovery?operation=CREATE_PREPARATION',headers=h(key=prep_key)).json()['event'] == created
    bad = '/api/local-request-recovery?operation=REOPEN&preparation_id='+id
    assert api.get(bad,headers=h(key=prep_key)).status_code == 409
    assert api.get(bad,headers=h('fixture-b')).status_code == 403
    # The denial route must remain read-only, including no ordinary audit write.
    before = []
    audit = store.audit_denial
    store.audit_denial = lambda *_:before.append('UNEXPECTED_AUDIT_WRITE')
    try:
        with owner.connect() as c:
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        response = api.get('/api/local-request-recovery?operation=CREATE_PREPARATION',headers=h(key=prep_key))
        assert response.status_code == 403 and not before
    finally:store.audit_denial = audit
    with owner.connect() as c:
        assert c.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) AS n FROM preparation_events').fetchone()['n'] == 1
