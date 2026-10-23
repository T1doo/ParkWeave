"""Verify this immutable run28 archive offline; no business/browser execution."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json

p = Path(__file__).parent
read = lambda name: json.loads((p / name).read_text())
digest = lambda name: sha256((p / name).read_bytes()).hexdigest()
manifest = dict(line.split('  ', 1)[::-1] for line in (p / 'checksums.sha256').read_text().splitlines())
assert set(manifest) == {x.name for x in p.iterdir() if x.is_file() and x.name != 'checksums.sha256'}
assert all(digest(name) == value for name, value in manifest.items())
run = read('run-api.json'); job = read('job-api.json')['jobs'][0]; a = read('artifact-metadata.json')['artifacts'][0]; r = read('result.json')
source = '5a96c11a0413630515c3bec6a17a269ac434eba7'
assert run['id'] == 39879954079 and run['run_number'] == 28 and run['run_attempt'] == 1 and run['head_sha'] == source and run['conclusion'] == 'success'
assert job['id'] == 120174662792 and job['conclusion'] == 'success' and all(s['conclusion'] == 'success' for s in job['steps'])
assert a['id'] == 12470425980 and a['digest'] == 'sha256:' + digest('artifact.zip') == 'sha256:91e441bb4662467f515a4ff22113215c5baecf3d9722af9d9cc513653bea0fa1'
assert r['source_sha'] == source and r['status'] == 'PASS' and r['stage'] == 'COMPLETE' and r['worker_final'] and not r['worker_output_truncated']
assert not any(r[k] for k in ('cleanup_errors', 'page_errors', 'violations', 'unexpected_GET', 'business_POSTs', 'real_model_calls', 'product_API', 'database'))
assert len(r['requests']) == len(r['browser_requests']) == 7 and all(x['method'] == 'GET' for x in r['requests'] + r['browser_requests'])
assert len(r['checks']) == len(r['font_observations']) == 10
assert all(x['documentWidth'] == x['width'] for x in r['checks'])
assert r['narrow_height_change'] == {'before': 8538, 'after': 7471, 'saved': 1067}
h = r['historical_rendering']; assert len(h) == 4
assert len({x['projection_sha256'] for x in h}) == len({x['rendered_history_sha256'] for x in h}) == 1
assert all(x['step_ids'] == h[0]['step_ids'] and x['rendered_preview_articles'] == h[0]['rendered_preview_articles'] and x['rendered_history_text'] == h[0]['rendered_history_text'] for x in h)
assert all(x['disclosures_expanded_and_closed'] and x['disclosure_GETs'] == 0 for x in h if x['variant'] == 'after')
assert r['source_binding']['workspace']['business_script_unchanged_except_case_plan_render_and_clear']
assert [s['tone'] for s in r['guide_states']] == ['neutral', 'error', 'success', 'neutral', 'neutral']
assert all(s['height'] >= s['scrollHeight'] and s['width'] >= s['scrollWidth'] for s in r['guide_states'])
assert 'NOT_A_REAL_SESSION_OR_AUTHORITY' in r['guide_success_scope'] and 'not real navigation' in r['guide_event_scope']
o = r['owned_launch']; assert o['status'] == 'CLEANUP_CONFIRMED' and o['operation_status'] == 'PASS' and o['worker_returncode'] == 0
assert o['bound_processes_exited'] and o['subtree_complete'] and len(o['processes']) == 8 and all(x['exited'] and x['ownership_basis'] for x in o['processes'])
assert not any(o[k] for k in ('errors', 'signals', 'remaining_children', 'remaining_private_session_members'))
assert r['browser_close'] == 'CLOSED' and r['listener_after_cleanup'] == 'REFUSED' and r['work_and_cleanup_seconds'] <= 90 and r['seconds'] <= 360
assert r['installed_CJK_font']['status'] == 'INSTALLED_CHARSET_COVERS_UI' and r['installed_CJK_font']['rendering_observed'] and len(r['installed_CJK_font']['required_codepoints']) == 684
log = (p / 'ci-original.log').read_bytes().decode()
assert len(log) == 373346 and len(log.encode()) == 378804 and digest('ci-original.log') == '9be67c59eb1b9f75655bb93acc08ba52fe74effcd2b57721ad444dd1f3ac06cf'
rows = [s.partition('Z ')[2] for s in log.splitlines() if s.partition('Z ')[2].startswith('{"scope": "REAL_CHROME_ORIGINAL_PAGES_PRESENTATION_NO_BACKEND"')]
assert len(rows) == 1
v = json.loads(rows[0]); assert v['status'] == 'PENDING_FINALIZATION'; v['status'] = v.pop('observation_outcome'); v.pop('terminal_result')
assert v == {k: v for k, v in r.items() if k not in ('seconds', 'seconds_scope')}
assert 'FINALIZATION_OUTPUT_CHECKPOINT' in log and 'upload aborted' not in log.lower()
with ZipFile(p / 'artifact.zip') as z:
    assert len(z.infolist()) == 9 and sum(i.file_size for i in z.infolist()) == 3676691 < 8 * 1024 * 1024
    assert sum(n.endswith('.png') for n in z.namelist()) == 8
    assert all('/' not in n and z.read(n) == (p / n).read_bytes() for n in z.namelist())
assert read('visual-review.json')['status'] == 'EIGHT_ORIGINAL_PNGS_ACTUALLY_VIEWED_LIMITED_PRODUCT_VISUAL_REVIEW'
print(json.dumps({'status': 'OFFLINE_ARCHIVE_CONSISTENT', 'source_sha': source, 'run': 28, 'attempt': 1, 'ZIP_members': 9, 'ZIP_bytes': 3676691, 'complete_log_characters': len(log), 'historical_projections': 4, 'new_business_POSTs': 0}))
