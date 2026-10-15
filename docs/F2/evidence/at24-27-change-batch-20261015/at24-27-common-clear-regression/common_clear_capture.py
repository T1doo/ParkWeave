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
    if fixturedef.argname not in {'fixture', 'preparation_fixture', 'receipt_fixture', 'link_fixture', 'fresh_chain', 'upgrade_case', 'template_consumption'} or not fixturedef.cached_result:
        return
    value = fixturedef.cached_result[0]
    tokens = value.get('tokens') if isinstance(value, dict) else None
    if tokens is None:
        if isinstance(value, dict):
            value = value.get('f')
        if not isinstance(value, tuple) or len(value) < 3 or not isinstance(value[2], dict):
            return
        tokens = value[2]
    assert isinstance(tokens, dict)
    _private.update(v for v in tokens.values() if isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}', v))
    path = Path(os.environ['AT_REVIEW_PRIVATE'])
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(sorted(_private)) + '\n')
    path.chmod(0o600)


# Fixed test artifact paths only. Original source/assertions/Node/API/PG stay intact.
def pytest_configure(config):
    root = Path('/workspace/ParkWeave')
    destination = root / '.runtime/at24-27-common-clear-regression'
    config._common_original_open = Path.open
    config._common_original_mkdir = Path.mkdir
    roots = [root / '.runtime' / name for name in json.loads((destination / 'artifact-legacy-roots.json').read_text())]
    records = []
    seen = set()
    def replacement(path):
        absolute = Path(os.path.abspath(str(path)))
        for folder in roots:
            if absolute.is_relative_to(folder):
                # This is only a fixed test artifact directory, never PG state.
                # Keep evidence in archive inventory despite legacy pytest-PID name.
                pieces = [('process-' + part[len('pytest-'):]) if part.startswith('pytest-') else part for part in absolute.relative_to(folder).parts]
                return destination / 'artifacts' / folder.relative_to(root / '.runtime') / Path(*pieces)
        return None
    def record(old, new, mode):
        key = (str(old), str(new), mode)
        if key in seen:
            return
        seen.add(key)
        records.append(dict(original=str(old), actual=str(new), mode=mode))
        target = destination / 'fixed-test-artifact-redirections.json'
        with config._common_original_open(target, 'w') as stream:
            stream.write(json.dumps(records, indent=2) + '\n')
    def opened(path, mode='r', *a, **kw):
        target = replacement(path)
        if target is None:
            return config._common_original_open(path, mode, *a, **kw)
        if any(letter in mode for letter in 'wax+'):
            config._common_original_mkdir(target.parent, parents=True, exist_ok=True)
        record(path, target, mode)
        return config._common_original_open(target, mode, *a, **kw)
    def mkdir(path, *a, **kw):
        target = replacement(path)
        if target is None:
            return config._common_original_mkdir(path, *a, **kw)
        # All target parents are new artifact preparation, not business state.
        record(path, target, 'mkdir')
        return config._common_original_mkdir(target, parents=True, exist_ok=True)
    Path.open = opened
    Path.mkdir = mkdir


def pytest_unconfigure(config):
    Path.open = config._common_original_open
    Path.mkdir = config._common_original_mkdir
