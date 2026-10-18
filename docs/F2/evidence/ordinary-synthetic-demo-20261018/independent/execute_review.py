"""Private mirror pytest observer. Executed only by frozen-window controller."""
from pathlib import Path
import atexit
import hashlib
import json
import os
import sys
import time

import pytest
import pgserver

out = Path(sys.argv[1]).resolve()
mirror = Path.cwd().resolve()
inputs = json.loads((out / 'mirror-before.json').read_text())
probe = mirror / 'tests/test_independent_ordinary_synthetic_demo.py'
probe_hash = hashlib.sha256(probe.read_bytes()).hexdigest()
reports, fixtures, collected, servers, tokens = [], [], [], [], set()
demo_states = []
original_server = pgserver.get_server


def owned_server(*args, **kwargs):
    server = original_server(*args, **kwargs)
    data = Path(args[0] if args else kwargs['data_dir']).resolve()
    pidfile = data / 'postmaster.pid'
    servers.append(dict(data=str(data), pid=int(pidfile.read_text().splitlines()[0]) if pidfile.exists() else None))
    return server


pgserver.get_server = owned_server


def pg_before_exit():
    for row in servers:
        stat = Path('/proc') / str(row['pid']) / 'stat'
        row['state_before_process_exit'] = stat.read_text().rsplit(')', 1)[1].strip().split()[0] if stat.exists() else 'EXITED'
        row['data_exists_before_process_exit'] = Path(row['data']).exists()
    (out / 'owned-pg-before-exit.json').write_text(json.dumps(servers, sort_keys=True, indent=2) + '\n')


class Observer:
    def pytest_collection_finish(self, session):
        collected.extend(dict(nodeid=i.nodeid, path=str(i.path), name=i.name) for i in session.items)
        (out / 'collection.json').write_text(json.dumps(collected, sort_keys=True, indent=2) + '\n')

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        fixtures.append(fixturedef.argname)
        result = yield
        if result.excinfo is None:
            value = result.get_result()
            def collect(value):
                if not isinstance(value, tuple):
                    return
                if len(value)>2 and isinstance(value[2],dict):
                    for key,token in value[2].items():
                        if (key.startswith(('fixture-','prep-specialist-','executor-')) or key in ('unassigned','configured-owner','configured-reviewer','enterprise','specialist','executor')) and isinstance(token,str):
                            tokens.add(token)
                for item in value:
                    if isinstance(item,tuple):collect(item)
            collect(value)
            if fixturedef.argname=='demo_state' and isinstance(value,tuple) and isinstance(value[0],Path):
                demo_states.append(value[0])

    def pytest_runtest_logreport(self, report):
        row = dict(nodeid=report.nodeid, when=report.when, outcome=report.outcome, duration=report.duration)
        if report.failed:
            row['longrepr'] = str(report.longrepr)
        reports.append(row)
        with (out / 'calls.jsonl').open('a') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')


start = time.perf_counter()
exit_code = pytest.main(sys.argv[2:], plugins=[Observer()])
elapsed = time.perf_counter() - start
atexit.register(pg_before_exit)
fd = os.open(out / 'fixture-token-values.private.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as file:
    json.dump(sorted(tokens), file)
origins = []
for name, module in sorted(sys.modules.items()):
    source = getattr(module, '__file__', None)
    if source and (name == 'parkweave' or name.startswith('parkweave.') or name.startswith('scripts.') or name.startswith('test_') or name in ('owned_connection_diagnostics','ordinary_case_step_support','service_release_acceptance_support','conftest')):
        path = Path(source).resolve()
        if not path.is_file():
            continue
        relative = str(path.relative_to(mirror)) if path.is_relative_to(mirror) else None
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        origins.append(dict(name=name, path=str(path), relative=relative, sha256=sha,
                            within_mirror=relative is not None,
                            matches_frozen=inputs.get(relative) == sha,
                            matches_independent_probe=path == probe and sha == probe_hash))
(out / 'module-origins.json').write_text(json.dumps(origins, sort_keys=True, indent=2) + '\n')
(out / 'pytest-result.json').write_text(json.dumps(dict(
    exit_code=int(exit_code), pytest_main_seconds=elapsed, collected=collected,
    reports=reports, fixture_names=sorted(set(fixtures)), owned_pg=servers,
    private_fixture_token_values_captured=len(tokens)), sort_keys=True, indent=2) + '\n')
# Preserve only explicit textual test evidence; never mirror/PGdata/config.
import shutil
owned_tmp=Path(os.environ['PARKWEAVE_REVIEW_TMP_ROOT'])
for directory,dirs,files in os.walk(owned_tmp):
    dirs[:]=[d for d in dirs if d!='data' and not d.startswith('parkweave-pg')]
    for name in files:
        if name in ('api.log','process.json','worker.stdout','worker.stderr','worker-result.json','html.stdout','html.stderr','chain-proof.json','summary.json','download.txt','process-chain.json','last-lock-proof.json','final-wait-proof.json','administrator-wait-proof.json','configuration-business-chain.json','cli.stdout','cli.stderr','setup.stdout','setup.stderr','serve.stdout','serve.stderr','ordinary-demo-chain.json'):
            source=Path(directory)/name
            target=out/'original-process-evidence'/source.relative_to(owned_tmp)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
state_observations=[]
for state in demo_states:
    marker=json.loads((state/'state.json').read_text())
    state_observations.append(dict(state_dir=str(state),state_retained=state.exists(),data_retained=(state/'data').exists(),postmaster_marker_exists=(state/'data/postmaster.pid').exists(),stop_unconfirmed=(state/'stop-unconfirmed').exists(),source_binding=marker.get('source',{}).get('sha256'),system_identifier=marker.get('system_identifier'),database_oid=marker.get('database_oid'),schema_version=marker.get('schema_version'),authority=marker.get('authority'),sessions_sha256=hashlib.sha256((state/'sessions.json').read_bytes()).hexdigest()))
    for relative in ('logs/initdb.log','logs/postgres.log','logs/application.log','failure.log'):
        file=state/relative
        if file.is_file():
            destination=out/'owned-state-logs'/state.name/relative
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,destination)
(out/'owned-demo-state-observations.json').write_text(json.dumps(state_observations,sort_keys=True,indent=2)+'\n')
raise SystemExit(int(exit_code))
