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


# Only exact original test-driver argv and fixed test trace destinations change.
# No product functions, assertions, transport results or business permissions.
def pytest_configure(config):
    import subprocess
    root = Path('/workspace/ParkWeave')
    destination = root / '.runtime/at24-27-repair-review'
    originals = ('partial_service_plan.js', 'partial_service_plan_expansion.js', 'template_full_chain.js')
    mapping = {str((root / 'tests' / name).resolve()): str(destination / 'candidates' / name) for name in originals}
    config._repair_original_popen = subprocess.Popen
    config._repair_original_write_text = Path.write_text
    config._repair_original_mkdir = Path.mkdir
    legacy = [root / '.runtime' / name for name in ('partial-plan-20261013', 'template-full-chain-20261013', 'template-repeat-cold-20261013')]
    records = []
    def record(value):
        records.append(value)
        config._repair_original_write_text(destination / 'runtime-redirections.json', json.dumps(records, indent=2) + '\n')
    def replacement(path):
        absolute = Path(os.path.abspath(str(path)))
        for folder in legacy:
            if absolute.is_relative_to(folder):
                return destination / 'artifacts' / folder.name / absolute.relative_to(folder)
        return None
    def popen(args, *a, **kw):
        if isinstance(args, (list, tuple)) and len(args) >= 2 and Path(str(args[0])).name == 'node':
            original = str((Path(kw.get('cwd', root)) / str(args[1])).resolve())
            if original in mapping:
                updated = list(args); updated[1] = mapping[original]
                record(dict(kind='exact_node_driver_argv', original=original, actual=updated[1]))
                args = updated
        return config._repair_original_popen(args, *a, **kw)
    def write_text(path, data, *a, **kw):
        target = replacement(path)
        if target is not None:
            config._repair_original_mkdir(target.parent, parents=True, exist_ok=True)
            record(dict(kind='test_trace_write', original=str(path), actual=str(target)))
            return config._repair_original_write_text(target, data, *a, **kw)
        return config._repair_original_write_text(path, data, *a, **kw)
    def mkdir(path, *a, **kw):
        target = replacement(path)
        return config._repair_original_mkdir(target if target is not None else path, *a, **kw)
    subprocess.Popen = popen
    Path.write_text = write_text
    Path.mkdir = mkdir


def pytest_unconfigure(config):
    import subprocess
    subprocess.Popen = config._repair_original_popen
    Path.write_text = config._repair_original_write_text
    Path.mkdir = config._repair_original_mkdir
