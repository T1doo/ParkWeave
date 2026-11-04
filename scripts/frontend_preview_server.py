"""Read-only synthetic frontend review. Python standard library; no app/PG/native runtime."""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import time

MARKER = 'SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY'
STATIC = {'/workspace-design.css': ('workspace-design.css', 'text/css; charset=utf-8'),
          '/workspace-design.js': ('workspace-design.js', 'text/javascript; charset=utf-8'),
          '/parkweave-mark.png': ('parkweave-mark.png', 'image/png'),
          '/web.html': ('web.html', 'text/html; charset=utf-8'),
          '/local_preparation_web.html': ('local_preparation_web.html', 'text/html; charset=utf-8'),
          '/local-command-pending.js': ('local-command-pending.js', 'text/javascript; charset=utf-8')}
API = frozenset(('/api/synthetic-resources', '/api/resource-bundles',
                 '/api/plan-approval/status', '/api/run-access/status'))


def load_candidate(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / 'preview-manifest.json').read_bytes())
    if (manifest.get('schema') != 'parkweave-readonly-frontend-preview/1'
            or not re.fullmatch('[a-f0-9]{40}', manifest.get('source_commit', ''))
            or manifest.get('product_runtime') is not False):
        raise ValueError('Not a source-bound preview manifest')
    contents = {}
    for name, row in manifest['files'].items():
        path = root / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise ValueError('Only regular flat candidate files are supported')
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Candidate file changed: ' + name)
        contents[name] = raw
    required = {name for name, _ in STATIC.values()} | {'preview-fixture.json', 'serve.py', 'README.txt'}
    if not required <= contents.keys():
        raise ValueError('Incomplete preview candidate')
    fixture = json.loads(contents['preview-fixture.json'])
    if (fixture.get('scope') != 'HISTORICAL_SYNTHETIC_PUBLIC_RESOURCE_VIEW'
            or fixture['resource']['source']['kind'] != 'SYNTHETIC'):
        raise ValueError('Only the declared public synthetic fixture is supported')
    return manifest, contents, fixture


def handler_for(manifest, contents, fixture, state):
    if state not in ('READY', 'EMPTY', 'ERROR', 'DENIED'):
        raise ValueError('Unknown synthetic catalog state')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log supplied identity headers or request bodies.

        def reply(self, code, kind, raw):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; form-action 'none'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def value(self, code, value):
            self.reply(code, 'application/json', json.dumps(value, ensure_ascii=False).encode())

        def do_GET(self):
            if self.path == '/':
                source = manifest['source_commit']
                raw = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>ParkWeave 合成只读前端验收</title>
<style>body{{font:16px/1.6 system-ui;margin:16px;color:#141413;background:#faf9f5}}header{{max-width:1000px}}code{{overflow-wrap:anywhere}}iframe{{display:block;width:100%;height:768px;border:1px solid #91877d;background:white}}a,button{{margin-right:16px}}p{{margin:8px 0}}</style>
<header><h1>ParkWeave · 合成只读前端验收</h1><p>源码 <code>{source}</code> · 目录状态 {state} · 无数据库、真实身份、模型、预约或 Windows 原生运行。</p>
<p>下框为原页面字节。仅填公开回放标识 <code>{MARKER}</code>，切到资源后点“查看有权使用的合成资源”。日期固定回放2026-10-26；不是当前资源可用性。</p>
<p>检查：A/B主题、紧凑密度、长中文、日期格及头部Esc回焦。所有写请求拒绝；精简页仅登录外壳，不提供模拟登录或材料业务。</p>
<p><button type="button" data-page="web.html">完整工作台</button><button type="button" data-page="local_preparation_web.html">精简页登录外壳</button><span id="frame-size"></span></p></header>
<iframe id="page" title="原页面·公开合成只读回放" src="/web.html"></iframe>
<script>const frame=document.getElementById('page');document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>frame.src='/'+b.dataset.page);function size(){{document.getElementById('frame-size').textContent='页面内容视口宽 '+Math.round(frame.getBoundingClientRect().width-2)+' CSS px，高768；须按实际浏览器测量记录。';}}addEventListener('resize',size);size();</script></html>'''
                self.reply(200, 'text/html; charset=utf-8', raw.encode())
            elif self.path in STATIC:
                name, kind = STATIC[self.path]
                self.reply(200, kind, contents[name])
            elif self.path == '/favicon.ico':
                self.reply(204, 'image/x-icon', b'')
            elif self.path in API:
                if self.headers.get('Authorization') != 'Bearer ' + MARKER:
                    self.value(401, {'detail': '仅接受公开合成回放标识；不是账户认证服务。'})
                elif self.path == '/api/synthetic-resources':
                    if state in ('ERROR', 'DENIED'):
                        self.value(500 if state == 'ERROR' else 403, {'detail': '明确设置的合成目录' + state})
                    else:
                        self.value(200, dict(server_time=fixture['server_time'], items=[] if state == 'EMPTY' else [fixture['resource']]))
                elif self.path == '/api/resource-bundles':
                    self.value(200, dict(actor_id=MARKER, items=[]))
                elif self.path == '/api/run-access/status':
                    self.value(200, dict(enabled=False, read_available=False, role=None, can_approve=False, can_revoke=False, actual_run_access=False, deployment_enabled=False))
                else:
                    self.value(200, dict(enabled=False, approval_scope=None, source_reapproval_enabled=False, plan_replacement_enabled=False, known_not_started_enabled=False, p3_closure_enabled=False))
            else:
                self.value(404, {'detail': '此路径不在合成只读回放范围内。'})

        def do_POST(self):
            self.value(405, {'detail': '合成只读前端回放：没有执行、保存、登录、占位、释放或确认。'})
        do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_POST
    return Handler


class LoopbackServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(2)
        return connection, address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--catalog-state', choices=('READY', 'EMPTY', 'ERROR', 'DENIED'), default='READY')
    args = parser.parse_args()
    if not (args.port == 0 or 1024 <= args.port <= 65535) or not 1 <= args.seconds <= 1800:
        parser.error('port must be0 or1024..65535; seconds1..1800')
    manifest, contents, fixture = load_candidate(args.root)
    with LoopbackServer(('127.0.0.1', args.port), handler_for(manifest, contents, fixture, args.catalog_state)) as server:
        server.timeout = .5
        print(json.dumps(dict(url='http://127.0.0.1:' + str(server.server_port) + '/', source_commit=manifest['source_commit'], scope='SYNTHETIC_READ_ONLY_NO_PRODUCT_RUNTIME', expires_seconds=args.seconds)), flush=True)
        end = time.monotonic() + args.seconds
        try:
            while time.monotonic() < end:
                server.handle_request()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
