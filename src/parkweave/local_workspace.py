"""Loopback workspace transport; authentication remains an explicit provider."""
from html import escape
from pathlib import Path
import threading
import time
import re

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .store import Denied


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str
    password: SecretStr


def full_workspace_page(root, accounts, *, materials_path='/'):
    """Password entry only; never adds identities, resources or permissions."""
    if materials_path not in ('/','/materials'): raise Denied('original material entry required')
    page = (root/'web.html').read_text()
    options = ''.join('<option value="'+escape(name, quote=True)+'">'+escape(label)+'</option>'
                      for name, label in accounts)
    panel = ('<section id="local-workspace-session" class="session-panel">'
        '<h2>进入服务与协同工作台</h2><form id="local-workspace-login">'
        '<label>已有本地账号<select id="local-workspace-account">'+options+'</select></label>'
        '<label>密码<input id="local-workspace-password" type="password" '
        'autocomplete="current-password" required maxlength="512"></label>'
        '<button id="local-workspace-submit">登录</button></form>'
        '<p id="local-workspace-status" role="status" aria-live="polite">'
        '只使用本安装已有的账号与授权；此入口不会增加资源或执行者配置。</p>'
        '<button id="local-workspace-logout" type="button" hidden>退出账号</button>'
        '<button id="local-workspace-materials" data-target="'+materials_path+'" type="button" class="secondary">返回资料工作台</button>'
        '</section>')
    replacements = {
        '<body class="desktop-shell">': '<body class="desktop-shell" data-local-workspace="locked">',
        '<section class="session-panel">': '<section class="session-panel" hidden>',
        '</aside><main id="park-main"': panel+'</aside><main id="park-main"',
        '</style>': ('body[data-local-workspace="locked"] #park-main,'
            'body[data-local-workspace="locked"] .workspace-nav{display:none}'
            '#local-workspace-session h2{font-size:15px}'
            '#local-workspace-session button{margin-top:8px;width:100%}</style>'),
    }
    for marker, value in replacements.items():
        if page.count(marker) != 1: raise Denied('local workspace page binding unavailable')
        page = page.replace(marker, value)
    scripts = ('<script src="/local-command-pending.js"></script>'
               '<script src="/local-workspace-login.js"></script>')
    if '</body>' in page: return page.replace('</body>', scripts+'</body>')
    if '</html>' in page: return page.replace('</html>', scripts+'</html>')
    return page+scripts


def mount_workspace(app, unlock, port, accounts):
    if type(port) is not int or not 1 <= port <= 65535 or not callable(unlock):
        raise Denied('explicit local workspace configuration required')
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, 'path', None) != '/']
    original = app.exception_handlers[RequestValidationError]
    failures = []; lock = threading.Lock()
    root = Path(__file__).parent

    @app.exception_handler(RequestValidationError)
    async def private_validation(request, error):
        if request.url.path == '/api/local/session':
            return JSONResponse({'detail':'invalid local login'}, status_code=422)
        return await original(request, error)

    @app.middleware('http')
    async def private_response(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/', response_class=HTMLResponse)
    def index():
        page = (root/'local_preparation_web.html').read_text()
        selectors = list(re.finditer(r'<select\b[^>]*\bid="role"[^>]*>', page))
        if len(selectors) != 1: raise Denied('local account selector unavailable')
        start = selectors[0].end()
        end = page.index('</select>', start)
        options = ''.join('<option value="'+escape(name, quote=True)+'">'+escape(label)+'</option>'
                          for name, label in accounts)
        return page[:start] + options + page[end:]

    @app.get('/workspace', response_class=HTMLResponse)
    def original_workspace(): return full_workspace_page(root, accounts)

    @app.get('/local-workspace-login.js')
    def workspace_login():
        return Response((root/'local_workspace_login.js').read_text(), media_type='text/javascript')

    @app.get('/local-command-pending.js')
    def pending(): return Response((root/'local_command_pending.js').read_text(), media_type='text/javascript')

    @app.post('/api/local/session')
    def login(data: Login, request: Request):
        if (not request.client or request.client.host != '127.0.0.1' or
                request.headers.get('origin') != f'http://127.0.0.1:{port}'):
            raise HTTPException(403, 'local same-origin login required')
        # Serialize bounded password work and throttle failed attempts across tabs.
        if not lock.acquire(blocking=False): raise HTTPException(429, '请稍后再试')
        try:
            now = time.monotonic(); failures[:] = [t for t in failures if now-t < 60]
            if len(failures) >= 6: raise HTTPException(429, '请稍后再试')
            try: return unlock(data.role, data.password.get_secret_value())
            except Denied:
                failures.append(now)
                raise HTTPException(403, '账号不可用或密码不正确') from None
        finally: lock.release()

    return app
