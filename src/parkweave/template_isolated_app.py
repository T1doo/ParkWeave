"""Explicit isolated composition; the deployment app never calls this factory."""
from pathlib import Path

from fastapi.responses import HTMLResponse

from .api import create_app
from .store import Denied


def create_isolated_template_app(store, engine, consumer, upgrade_checker=None):
    """Retain the original product routes and add only explicitly enabled fixtures."""
    from .template_candidate_api import create_template_candidate_app

    if not engine.config.enabled_for_isolated_tests:
        raise Denied('explicit isolated template contract required')
    if (consumer.store is not store or consumer.template_engine is not engine
            or not consumer.config.enabled_for_isolated_tests):
        raise Denied('explicit owned isolated consumer required')
    consumer.validate_fixture()
    if upgrade_checker is not None and (upgrade_checker.consumer is not consumer or upgrade_checker.engine is not engine):
        raise Denied('exact original template upgrade bridge required')
    app = create_app(store)
    candidate = create_template_candidate_app(engine, consumer)
    from .template_consumer import ConsumerUnknown
    app.add_exception_handler(ConsumerUnknown, candidate.exception_handlers[ConsumerUnknown])
    for route in candidate.router.routes:
        if getattr(route, 'path', '/') not in ('/', '/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'):
            app.router.routes.append(route)
    if upgrade_checker is not None:
        from .template_upgrade import install_routes
        install_routes(app, upgrade_checker)

        @app.get('/template-upgrade', response_class=HTMLResponse)
        def upgrade_page():
            return Path(__file__).with_name('template_upgrade_web.html').read_text(encoding='utf-8')

    @app.get('/template', response_class=HTMLResponse)
    def template_page():
        return Path(__file__).with_name('template_candidate_web.html').read_text(encoding='utf-8')

    return app
