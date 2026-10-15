"""Independent result/artifact capture; test artifact paths only, no product hooks."""
import json
import os
from pathlib import Path
import re
import sys

_private = set()
_redirected = {}


def redirect_test_artifacts():
    target = Path(os.environ['AT_REVIEW_ARTIFACT_ROOT'])
    for name, module in tuple(sys.modules.items()):
        if not name.startswith('test_') or module is None:
            continue
        value = getattr(module, 'OUT', None)
        if not isinstance(value, Path) or not str(value).startswith('.runtime/'):
            continue
        if name in _redirected:
            continue
        replacement = target / name
        replacement.mkdir(parents=True, exist_ok=True)
        setattr(module, 'OUT', replacement)
        _redirected[name] = dict(module=name, original=str(value), actual=str(replacement))
    Path(os.environ['AT_REVIEW_ARTIFACT_PATHS']).write_text(json.dumps(list(_redirected.values()), indent=2) + '\n')


def pytest_collection_modifyitems(session, config, items):
    redirect_test_artifacts()


def pytest_collection_finish(session):
    Path(os.environ['AT_REVIEW_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items], indent=2) + '\n')


def pytest_runtest_setup(item):
    redirect_test_artifacts()


def pytest_fixture_post_finalizer(fixturedef, request):
    if fixturedef.argname not in {'fixture', 'preparation_fixture', 'receipt_fixture', 'link_fixture', 'fresh_chain', 'upgrade_case'} or not fixturedef.cached_result:
        return
    value = fixturedef.cached_result[0]
    if isinstance(value, dict):
        value = value.get('f')
    if not isinstance(value, tuple) or len(value) < 3 or not isinstance(value[2], dict):
        return
    _private.update(v for v in value[2].values() if isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}', v))
    path = Path(os.environ['AT_REVIEW_PRIVATE'])
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(sorted(_private)) + '\n')
    path.chmod(0o600)
