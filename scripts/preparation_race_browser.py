"""Synthetic response-order oracle on the real page, no business API or model calls."""
import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
from parkweave.process_env import minimal_environment


def main(oracle_name="preparation_race_oracle.js"):
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expect-vulnerable', action='store_true')
    args = parser.parse_args()
    if args.expect_vulnerable and oracle_name != 'preparation_race_oracle.js': parser.error('baseline oracle applies to preparation only')
    root = Path.cwd()
    candidates = [p for p in (root/'.cache/npm/_npx').glob('*/node_modules/agent-browser/package.json') if json.loads(p.read_text())['version'] == '0.38.2']
    assert candidates, 'Approved cached agent-browser required'
    baseline = subprocess.check_output(['git', 'show', '6ff160abe979f9d1c28d0e7804fda668daf72cf5:src/parkweave/web.html']) if args.expect_vulnerable else None
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if baseline is not None and self.path == '/web.html':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(baseline)
            else: super().do_GET()
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root/'src/parkweave')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = minimal_environment(os.environ, npm_config_cache=str(root/'.cache/npm'), XDG_RUNTIME_DIR=str(root/'.runtime/sockets'))
    cmd = ['node', str(candidates[0].parent/'bin/agent-browser.js'), '--session', 'prep-race', '--executable-path', '/usr/bin/chromium', '--args', '--no-sandbox']
    def browser(*items, stdin=None):
        p = subprocess.run(cmd+list(items), input=stdin, capture_output=True, text=True, env=env, timeout=60)
        if p.returncode: raise RuntimeError(p.stderr)
        return p.stdout.strip()
    try:
        browser('open', f'http://127.0.0.1:{server.server_port}/web.html')
        browser('snapshot', '-i')
        source = (root/'scripts'/oracle_name).read_text()
        source = source.replace('const pending=', 'const expectVulnerable='+str(args.expect_vulnerable).lower()+';const pending=', 1)
        result = json.loads(browser('eval', '--stdin', stdin=source))
        if isinstance(result, str): result = json.loads(result)
        result.update(scope='SYNTHETIC_BROWSER_RESPONSE_ORDER_ONLY', model_calls=0, business_API_calls=0, backend_authorization_tested=False)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        if args.expect_vulnerable:
            assert result['old_case_overwrites_selection'] and result['old_identity_restored'] and result['wrong_case_write'] and result['cross_case_draft_carried'], result
        else:
            assert all(result['checks'].values()), result
        assert not browser('errors')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        browser('close')
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

if __name__ == '__main__': main()
