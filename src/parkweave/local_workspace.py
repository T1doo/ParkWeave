"""Loopback workspace transport; authentication remains an explicit provider."""
from html import escape
from pathlib import Path
import threading
import time

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
        start = page.index('<select id="role">') + len('<select id="role">')
        end = page.index('</select>', start)
        options = ''.join('<option value="'+escape(name, quote=True)+'">'+escape(label)+'</option>'
                          for name, label in accounts)
        return page[:start] + options + page[end:]

    @app.get('/workspace', response_class=HTMLResponse)
    def original_workspace(): return (root/'web.html').read_text()

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
