"""Original HTML over actual owned HTTP/PG; Node DOM is not a real browser."""
import json
from pathlib import Path
import subprocess
import sqlite3
import pytest
from test_handling_deadline import deadline_http, attach, snapshot
from test_preparation import preparation_fixture, filled
from test_synthetic_pause_clock import setup


@pytest.mark.parametrize('mode',['chain','no-cap','lost-cold','advanced-history','not-observed','late-success','late-denied','late-case',
                                 'missing-calendar','wrong-case','wrong-revision','wrong-actor'])
def test_original_page_existing_fixture_pause_end_history_and_original_key_recovery(deadline_http,tmp_path,mode):
    f,_=deadline_http
    if mode=='no-cap':
        p=filled(f);attach(f,p);service=None
    else:p,service,_=setup(f,tmp_path)
    other=filled(f) if mode=='late-case' else p
    before=snapshot(f)
    config=dict(base=str(f[3].base_url),id=p['preparation_id'],reviewer=f[2]['prep-specialist-fixture-a'],owner=f[2]['fixture-a'],other_id=other['preparation_id'],mode=mode)
    result=subprocess.run(['node','tests/synthetic_pause_clock_ui_real_html.js'],input=json.dumps(config)+'\n',
                          capture_output=True,text=True,timeout=45)
    out=Path('.runtime/synthetic-pause-clock-ui-20261018/development-ui')/tmp_path.parent.name/mode;out.mkdir(parents=True,exist_ok=True)
    (out/'html.stdout').write_text(result.stdout);(out/'html.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    actual=json.loads(result.stdout.splitlines()[-1]);(out/'result.json').write_text(json.dumps(actual,indent=2)+'\n')
    assert snapshot(f)==before
    expected=2 if mode in ('chain','advanced-history') else 1 if mode in ('lost-cold','late-success','late-denied','late-case') else 0
    assert actual['posts']==expected
    if service:
        with sqlite3.connect(service.path) as db:assert db.execute('SELECT count(*) FROM fixture_events').fetchone()[0]==expected
