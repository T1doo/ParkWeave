from pathlib import Path
import ast, collections, hashlib, json, re, subprocess, xml.etree.ElementTree as ET

root = Path('/workspace/ParkWeave')
run = root / '.runtime/synthetic-pause-clock-ui-20261018'
target = root / 'docs/F2/evidence/synthetic-pause-clock-ui-20261018'
head = '1373cd74b7a9ab775f707ad194e43a9ce6cd5a5b'
base = '8cb957dfd3e546f6b24410a005c75a2cddfb211e'
sha = lambda b: hashlib.sha256(b).hexdigest()
dump = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip() == head
final = run / 'frozen-1373cd74'
maps = [json.loads((final / n).read_text()) for n in ('shared-before.json', 'shared-after.json', 'mirror-before.json', 'mirror-after.json')]
assert len(maps[0]) == 817 and all(m == maps[0] for m in maps)
assert all(sha((root / p).read_bytes()) == h for p, h in maps[0].items())
origins = json.loads((final / 'module-origins.json').read_text())
assert len(origins) == 108 and all(x['within_mirror'] for x in origins.values())
collection = json.loads((final / 'collection.json').read_text())
groups = dict(collections.Counter(n.split('::')[0] for n in collection))
assert groups == {'tests/test_synthetic_pause_clock_ui.py': 12, 'tests/test_synthetic_pause_clock.py': 35, 'tests/test_handling_deadline.py': 5}
suite = next(ET.parse(final / 'results.xml').getroot().iter('testsuite'))
assert tuple(suite.attrib[k] for k in ('tests', 'failures', 'errors', 'skipped')) == ('52', '0', '0', '0')
paths = ['src/parkweave/web.html', 'src/parkweave/synthetic_pause_clock.py', 'tests/synthetic_pause_clock_ui_real_html.js', 'tests/test_synthetic_pause_clock_ui.py', 'docs/F2/SyntheticPauseClockUIContract-20261018.md']
source_hashes = {}
for p in paths:
    b = (root / p).read_bytes()
    assert b == subprocess.check_output(['git', 'show', head + ':' + p], cwd=root)
    source_hashes[p] = sha(b)
protected_names = ['src/parkweave/handling_deadline.py', 'src/parkweave/api.py', 'src/parkweave/preparation.py', 'src/parkweave/permissions.py', 'src/parkweave/store.py', 'src/parkweave/roles.sql', 'src/parkweave/schema.sql', 'src/parkweave/migration-032.sql', 'src/parkweave/migration-033.sql', 'docs/验收规格.json', 'docs/F1/ATBindings.json']
protected = {}
for p in protected_names:
    b = (root / p).read_bytes()
    assert b == subprocess.check_output(['git', 'show', base + ':' + p], cwd=root)
    protected[p] = sha(b)
def without_read(b):
    tree = ast.parse(b)
    tree.body = [n for n in tree.body if not (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'read')]
    return ast.dump(tree, include_attributes=False)
assert without_read((root / paths[1]).read_bytes()) == without_read(subprocess.check_output(['git', 'show', base + ':' + paths[1]], cwd=root))
review = dict(reviewed_sha=head, mode='STATIC_ONLY', result='finite static review passed; two prior P2 closed; no definite open P1/P2',
    oracle_ids=['UI01 explicit read entry, no automatic capability GET', 'UI02 actor/case/revision/binding/history checked',
    'UI03 owner readonly, plain REVIEW not capability, UNKNOWN no write', 'UI04 fixed reason/nonblank note/separate confirmation/current action',
    'UI05 exact original actor/key/fp/event SHA/history; event need not be tail', 'UI06 NOT_OBSERVED/lost response/error retain handle, no auto resend/new key',
    'UI07 bounded opaque handles; real original form reenters exact stored case', 'UI08 actor/case ABA and late success/403 generation guards',
    'UI09 original common write gates; readonly exception preserves other pending and actual GET authority', 'UI10 original command/journal/calculation/authority unchanged, read metadata only'],
    reviewer='/root/review_typed_dependency', product_imports=0, dynamic_executions=0, DB_HTTP_calls=0, file_writes_by_reviewer=0,
    source_hashes={p: source_hashes[p] for p in paths if p != 'tests/test_synthetic_pause_clock_ui.py'},
    nonblocking_limit='After exact handle settlement, original material/review fieldsets require original refresh-current-case action to redraw; not all old buttons instantly enabled.',
    not_verified=['real browser', 'Windows', 'ordinary persistent pause provider', 'formal AT29'], old_risk_windows_retried=False)
dump(run / 'independent-final-review.json', review)
verification = dict(tested_source_sha=head, baseline_sha=base, final_dynamic=dict(tests=52, failures=0, errors=0, skipped=0,
    junit_seconds=float(suite.attrib['time']), groups=groups), frozen_inputs=817, frozen_four_maps_equal=True,
    after_frozen_input_differences=[], module_origins=108, all_recorded_modules_from_mirror=True,
    source_tests_contract_byte_equal=True, source_hashes=source_hashes, protected_baseline_byte_equal=protected,
    clock_except_top_level_read_AST_equal_baseline=True, no_new_calendar_coverage_end_cases=True,
    independent=dict(mode='STATIC_ONLY', oracles=10, open_P1=0, open_P2=0, closed_P2=2, dynamic_executions=0, product_imports=0),
    full_regression=False, current_BC_dynamic=0, real_model_calls=0, historic_tests_not_summed=True,
    old_risk_windows_retried=False, old_HTTP_UNKNOWN_OPEN_closed=False, real_authority_created=False,
    real_gaps=['ordinary persistent provider not implemented', 'real authority source adapter not implemented', 'real policy consumption wiring not implemented'],
    limits=['owned synthetic HTTP/PG only', 'Node mechanical DOM, not actual browser', 'documented transport/current-projection FAULTs are not real revocation/calendar faults', 'no Windows/formal AT29/33/real SLA/whole-project acceptance'])
dump(run / 'root-verification.json', verification)
root_files = ['contract-source-blind.md', 'independent-source-blind-oracle.json', 'independent-e4c4-static-findings.json', 'independent-final-review.json',
    'root-verification.json', 'window-and-core-verification.json', 'development-artifact-attribution.json',
    'development.log', 'development.xml', 'development-fixed.log', 'development-fixed.xml',
    'development-additional.log', 'development-additional.xml', 'development-ui-boundaries.log', 'development-ui-boundaries.xml',
    'frozen-controller.stdout', 'frozen-controller.stderr', 'final-controller.stdout', 'final-controller.stderr', 'run-frozen.py', 'run-final.py', 'archive-ui-evidence.py']
files = [run / n for n in root_files]
for name in ['frozen-e4c4f1a2', 'frozen-1373cd74', 'development-fixed-ui-retained', 'development-ui']:
    files += [p for p in (run / name).rglob('*') if p.is_file() and not p.name.startswith('private-')]
assert len(files) == len(set(files)) and all(p.is_file() for p in files)
tokens = set()
for p in run.glob('frozen-*/private-fixture-session-values.json'):
    tokens.update(json.loads(p.read_text()))
assert tokens and all(isinstance(t, str) and len(t) == 43 for t in tokens)
target.mkdir(parents=True, exist_ok=False)
entries = []
for p in sorted(files):
    rel = p.relative_to(run)
    raw = p.read_bytes()
    public = raw
    exact_redactions = 0
    for token in tokens:
        exact_redactions += public.count(token.encode())
        public = public.replace(token.encode(), b'[REDACTED_FIXTURE_SESSION]')
    text = public.decode()
    pattern = r"((?:'|\")(?:fixture-[abc]|prep-specialist-fixture-[abc])(?:'|\"):\s*(?:'|\"))([A-Za-z0-9_-]{1,43})"
    text, displays = re.subn(pattern, r'\1[REDACTED_FIXTURE_SESSION_DISPLAY]', text)
    public = text.encode()
    assert not any(t.encode() in public for t in tokens)
    dest = target / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(public)
    entries.append(dict(original=str(p), export=str(rel), raw_sha256=sha(raw), export_sha256=sha(public), raw_bytes=len(raw), export_bytes=len(public),
        exact_captured_session_redactions=exact_redactions, fixture_session_display_redactions=displays))
scan = dict(source_sha=head, files=len(entries), exact_captured_fixture_sessions=len(tokens), all_exact_values_absent=True,
    captured_scope='two frozen windows, private exact-value files excluded',
    old_development_capture_limit='not all sessions captured; six known fixture dictionary display prefixes/full values redacted',
    raw_export_equal=sum(e['raw_sha256']==e['export_sha256'] for e in entries),
    redacted_files=sum(e['raw_sha256']!=e['export_sha256'] for e in entries), actual_session_values_published=False)
dump(target / 'session-publication-check.json', scan)
index = dict(source_sha=head, baseline_sha=base, entries=entries, metadata_files=['publication-files.json', 'session-publication-check.json'],
    excludes=['private exact fixture sessions', 'opening process/shared runtime observations', 'unknown process/locks', 'original first-window mode output overwritten by second developer helper; complete failed XML/log retained'],
    development_loose_UI_scope='second/later developer outputs only; source-bound frozen traces in each frozen directory are authoritative',
    original_raw_logs_retained_privately=True, independent_dynamic=0, historic_tests_not_summed=True)
dump(target / 'publication-files.json', index)
print(json.dumps(scan))
print('evidence files including metadata:', len(entries)+2)
