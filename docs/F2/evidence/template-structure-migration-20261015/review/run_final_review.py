from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = sys.argv[1]
LABEL = sys.argv[2] if len(sys.argv)>2 else 'source'+SOURCE[:8]
assert LABEL and all(c.isalnum() or c in '-_' for c in LABEL)
assert len(SOURCE) == 40 and all(c in '0123456789abcdef' for c in SOURCE)
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]
os.environ['PYTHONPATH'] = str(ROOT/'src')


def manifest():
    paths = [p for folder in ('src', 'tests', 'scripts') for p in (ROOT/folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')]
    paths.append(ROOT/'pyproject.toml')
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


before = manifest()
(OUT/(LABEL+'-before.json')).write_text(json.dumps(dict(source_sha=SOURCE, files=before), indent=2)+'\n')
modules = ['tests/test_structure_review_runtime.py', 'tests/test_template_structure_commit_expiry.py', 'tests/test_template_upgrade.py',
           'tests/test_template_migration_independent.py', 'tests/test_service_case_steps.py',
           'tests/test_registered_local_revision.py', 'tests/test_case_goal_results.py',
           'tests/test_independent_template_migration_runtime.py',
           'tests/test_independent_template_migration_capacity_final.py',
           'tests/test_native_run_access_offline.py', 'tests/test_template_migration_legacy.py',
           'tests/test_template_migration_legacy_independent.py',
           'tests/test_template_migration_nodevm_actual.py', 'tests/test_template_migration_ui_offline.py']
started = datetime.now(timezone.utc).isoformat()
result = pytest.main(['-q', '--tb=short', *modules, '--junitxml='+str(OUT/(LABEL+'-related.xml'))])
after = manifest()
loaded = {name: str(Path(value.__file__).resolve()) for name, value in tuple(sys.modules.items())
          if name.startswith('parkweave') and getattr(value, '__file__', None)}
deviations = {n: p for n, p in loaded.items() if not Path(p).is_relative_to(ROOT/'src')}
report = dict(source_sha=SOURCE, started_utc=started, completed_utc=datetime.now(timezone.utc).isoformat(),
              pytest_exit=int(result), modules=modules, loaded_modules=loaded, source_path_deviations=deviations,
              source_drift={p: [before.get(p), after.get(p)] for p in before.keys() | after.keys() if before.get(p)!=after.get(p)})
(OUT/(LABEL+'-run.json')).write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(int(result) or (3 if deviations or report['source_drift'] else 0))
