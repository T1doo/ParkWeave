"""Explicit isolated composition; the deployment app never calls this factory."""
from pathlib import Path

from fastapi.responses import HTMLResponse

from .api import create_app
from .store import Denied


def create_isolated_template_app(store, engine, consumer):
    """Retain the original product routes and add only explicitly enabled fixtures."""
    from .template_candidate_api import create_template_candidate_app

    if not engine.config.enabled_for_isolated_tests:
        raise Denied('explicit isolated template contract required')
    if (consumer.store is not store or consumer.template_engine is not engine
            or not consumer.config.enabled_for_isolated_tests):
        raise Denied('explicit owned isolated consumer required')
    consumer.validate_fixture()
    app = create_app(store)
    candidate = create_template_candidate_app(engine, consumer)
    from .template_consumer import ConsumerUnknown
    app.add_exception_handler(ConsumerUnknown, candidate.exception_handlers[ConsumerUnknown])
    for route in candidate.router.routes:
        if getattr(route, 'path', '/') not in ('/', '/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'):
            app.router.routes.append(route)

    @app.get('/template', response_class=HTMLResponse)
    def template_page():
        return Path(__file__).with_name('template_candidate_web.html').read_text(encoding='utf-8')

    return app
