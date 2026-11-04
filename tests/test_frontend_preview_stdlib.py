"""Real loopback HTTP and file integrity; no browser, app factory or database."""
import ast
from contextlib import closing, contextmanager
from hashlib import sha256
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('preview', ROOT / 'scripts/frontend_preview_server.py')
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


def historical_fixture():
    source = ROOT / 'scripts/resource_catalog_feedback_browser_once.py'
    tree = ast.parse(source.read_text())
    row = next(node.value for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'ROW' for target in node.targets))
    def literal(node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and not node.args:
            return {item.arg: literal(item.value) for item in node.keywords}
        return ast.literal_eval(node)
    return dict(scope='HISTORICAL_SYNTHETIC_PUBLIC_RESOURCE_VIEW', server_time='2026-10-26T12:00:00Z', resource=literal(row))


class FrontendPreview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {'web.html': (ROOT / 'src/parkweave/web.html').read_bytes(),
                 'local_preparation_web.html': (ROOT / 'src/parkweave/local_preparation_web.html').read_bytes(),
                 'local-command-pending.js': (ROOT / 'src/parkweave/local_command_pending.js').read_bytes(),
                 'serve.py': (ROOT / 'scripts/frontend_preview_server.py').read_bytes(),
                 'README.txt': (ROOT / 'docs/design/FrontendPreview-README.txt').read_bytes(),
                 'preview-fixture.json': json.dumps(historical_fixture(), ensure_ascii=False).encode()}
        for name, raw in files.items():
            (self.root / name).write_bytes(raw)
        manifest = dict(schema='parkweave-readonly-frontend-preview/1', source_commit='f0aa554b9247464e3ffb61f43a2d88782d0f7141', product_runtime=False,
                        files={name: dict(bytes=len(raw), sha256=sha256(raw).hexdigest()) for name, raw in files.items()})
        (self.root / 'preview-manifest.json').write_text(json.dumps(manifest))
        self.candidate = preview.load_candidate(self.root)

    @contextmanager
    def server(self, state='READY'):
        with preview.LoopbackServer(('127.0.0.1', 0), preview.handler_for(*self.candidate, state)) as server:
            thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                yield server.server_port
            finally:
                server.shutdown()
                thread.join(3)
                self.assertFalse(thread.is_alive())

    def request(self, port, path, method='GET', marker=True):
        with closing(HTTPConnection('127.0.0.1', port, timeout=3)) as connection:
            headers = {'Authorization': 'Bearer ' + preview.MARKER} if marker else {}
            connection.request(method, path, body=b'{}' if method != 'GET' else None, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    def test_actual_html_and_pending_script_are_served_unchanged(self):
        with self.server() as port:
            for route, (name, _) in preview.STATIC.items():
                code, headers, raw = self.request(port, route)
                self.assertEqual(code, 200)
                self.assertEqual(raw, (self.root / name).read_bytes())
                self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
                self.assertEqual(headers['Cache-Control'], 'no-store')
            code, _, raw = self.request(port, '/')
            self.assertEqual(code, 200)
            self.assertIn('合成只读前端验收'.encode(), raw)
            self.assertIn(b'iframe', raw)

    def test_original_read_only_resource_contract_and_disabled_authority(self):
        with self.server() as port:
            code, _, raw = self.request(port, '/api/synthetic-resources')
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(raw)['items'], [historical_fixture()['resource']])
            self.assertEqual(json.loads(self.request(port, '/api/resource-bundles')[2]), dict(actor_id=preview.MARKER, items=[]))
            for path in ('/api/plan-approval/status', '/api/run-access/status'):
                self.assertFalse(json.loads(self.request(port, path)[2])['enabled'])
            self.assertEqual(self.request(port, '/api/synthetic-resources', marker=False)[0], 401)

    def test_unknown_reads_and_all_writes_are_refused(self):
        with self.server() as port:
            for path in ('/api/preparations', '/api/synthetic-resources?extra=1', '/../README.txt', '/preview-manifest.json'):
                self.assertEqual(self.request(port, path)[0], 404)
            for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'):
                code, _, raw = self.request(port, '/api/synthetic-resources', method)
                self.assertEqual(code, 405)
                self.assertIn('没有执行'.encode(), raw)

    def test_empty_error_and_denial_are_explicit_synthetic_states(self):
        for state, expected in (('EMPTY', 200), ('ERROR', 500), ('DENIED', 403)):
            with self.subTest(state=state), self.server(state) as port:
                code, _, raw = self.request(port, '/api/synthetic-resources')
                self.assertEqual(code, expected)
                if state == 'EMPTY':
                    self.assertEqual(json.loads(raw)['items'], [])

    def test_changed_candidate_file_is_refused_before_serving(self):
        (self.root / 'web.html').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Candidate file changed'):
            preview.load_candidate(self.root)


if __name__ == '__main__':
    unittest.main()
