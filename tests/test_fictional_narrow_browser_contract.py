"""Pure contract fixtures only; no browser, services, real glyphs or CI."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess

import pytest
from scripts import fictional_park_browser_once as base
from scripts import fictional_park_narrow_browser_once as narrow
from scripts import fictional_park_restart_browser_once as fonts


def probe():
    return dict(viewport_width=390,viewport_height=1000,document_width=390,x=20,y=30,width=300,height=44,hit=True)


def test_narrow_probe_accepts_visible_control():narrow.validate_probe(probe())


@pytest.mark.parametrize('change',[dict(viewport_width=1440),dict(document_width=391),dict(x=200),dict(width=0),dict(y=1001),dict(hit=False)])
def test_narrow_probe_rejects_overflow_resize_occlusion_or_invisible_control(change):
    with pytest.raises(AssertionError):narrow.validate_probe(dict(probe(),**change))


@pytest.mark.parametrize('include_new',[False,True])
def test_font_preflight_requires_original_and_new_input_codepoints(tmp_path,monkeypatch,include_new):
    from scripts import fictional_park_font_once as stage
    monkeypatch.setattr(stage,'verified_font',lambda **kw:None)
    source=''.join((base.ROOT/p).read_text() for p in ['src/parkweave/web.html','src/parkweave/park_demo_web.html'])
    old=fonts.ui_codepoints(source);all_points=fonts.ui_codepoints(source+narrow.Narrow.fixed_input_text)
    assert len(old)==683 and all_points-old=={ord(c) for c in '仪月温湿'}
    path=next(Path('/usr/share/fonts').rglob('*.ttf'))
    points=all_points if include_new else old
    raw='\t'.join([str(path),'0','UNIT_SYNTHETIC_CHARSET_NOT_REAL_CJK','UnitSynthetic',' '.join(f'{p:x}' for p in sorted(points))])+'\n'
    monkeypatch.setattr(fonts.subprocess,'run',lambda argv,**kw:subprocess.CompletedProcess(argv,0,stdout=raw.encode(),stderr=b''))
    report={}
    if include_new:
        fonts.installed_font_environment({},tmp_path/'fontconfig',report,extra_text=narrow.Narrow.fixed_input_text)
        assert len(report['installed_CJK_font']['required_codepoints'])==687
        assert not report['installed_CJK_font']['rendering_observed']
    else:
        with pytest.raises(RuntimeError):fonts.installed_font_environment({},tmp_path/'fontconfig',report,extra_text=narrow.Narrow.fixed_input_text)
        assert set(report['installed_CJK_font']['missing_codepoints'])==all_points-old


def separation_fixture(tmp_path):
    observer=narrow.Narrow({},tmp_path,0)
    old=dict(preparation_id='OLD_PREP_ID',case_id='OLD_CASE_ID',run_id='OLD_RUN_ID')
    new=dict(preparation_id='NEW_PREP_ID',case_id='NEW_CASE_ID',run_id='NEW_RUN_ID',plan_id='NEW_PLAN_ID')
    before=dict(preparations=[dict(service_case_plan=None)],service_dispatches=[],service_receipt_steps=[],preparation_evidence=[dict(id='OLD_EVIDENCE',text='OLD MATERIAL')])
    after=deepcopy(before)
    current=dict(preparation_events=[],preparation_evidence=[dict(id='NEW_'+slot,slot=slot,text=narrow.NEW_INPUT[slot]) for slot in ['need_summary','material_outline']])
    result=dict(new,original_request=narrow.NEW_INPUT['goal'],current_request=narrow.NEW_INPUT['request'])
    receipt=dict(step={k:new[k] for k in ['preparation_id','case_id','run_id']},current_receipt=dict(text=narrow.NEW_INPUT['receipt'],source_label=narrow.NEW_INPUT['receipt_source']))
    txt='\n'.join([*new.values(),narrow.NEW_INPUT['goal'],narrow.NEW_INPUT['request']])
    return observer,[old,new,before,after,current,result,receipt,txt]


def test_narrow_input_oracle_accepts_exact_new_and_unchanged_old(tmp_path):
    observer,args=separation_fixture(tmp_path);observer.separation(*args)
    assert observer.data['separation']['old_history_before_sha256']==observer.data['separation']['old_history_after_sha256']


@pytest.mark.parametrize('failure',[False,True])
def test_narrow_font_observation_retains_actual_stage_and_partial_failure(tmp_path,monkeypatch,failure):
    report={'installed_CJK_font':{}}
    observer=narrow.Narrow(report,tmp_path,0)
    monkeypatch.setattr(narrow.time,'monotonic',lambda:0)
    def observe(page,current):
        current['installed_CJK_font'].update(visible_node_font_usage=[{'node':'UNIT_NOT_REAL_GLYPH'}],
            rendering_observation_scope='legacy guide-only scope')
        if failure:raise RuntimeError('UNIT_OBSERVATION_FAILURE')
    monkeypatch.setattr(fonts,'verify_rendered_font',observe)
    if failure:
        with pytest.raises(RuntimeError,match='UNIT_OBSERVATION_FAILURE'):observer.font_observation(None,'NEW_RECEIPT')
    else:observer.font_observation(None,'NEW_RECEIPT')
    entry=observer.data['font_observations'][0]
    assert entry['complete'] is not failure and entry['stage']=='NEW_RECEIPT'
    assert entry['nodes']==[{'node':'UNIT_NOT_REAL_GLYPH'}]
    assert report['installed_CJK_font']['rendering_observation_stage']=='NEW_RECEIPT'
    assert report['installed_CJK_font']['rendering_observation_scope']==entry['scope']


def test_narrow_font_failure_before_observation_does_not_relabel_prior_nodes(tmp_path,monkeypatch):
    report={'installed_CJK_font':dict(visible_node_font_usage=[{'node':'OLD_STAGE'}],rendering_observed=True)}
    observer=narrow.Narrow(report,tmp_path,0)
    monkeypatch.setattr(narrow.time,'monotonic',lambda:0)
    def fail(page,current):raise RuntimeError('UNIT_BEFORE_NEW_NODES')
    monkeypatch.setattr(fonts,'verify_rendered_font',fail)
    with pytest.raises(RuntimeError,match='UNIT_BEFORE_NEW_NODES'):observer.font_observation(None,'NEW_TXT')
    assert observer.data['font_observations'][0]['nodes']==[]
    assert not observer.data['font_observations'][0]['complete']
    assert not report['installed_CJK_font']['rendering_observed']


@pytest.mark.parametrize('fault',['old_changed','material_reused','wrong_receipt','old_id_in_TXT'])
def test_narrow_input_oracle_rejects_old_new_mixing(tmp_path,fault):
    observer,args=separation_fixture(tmp_path)
    if fault=='old_changed':args[3]['preparations'][0]['service_case_plan']={}
    elif fault=='material_reused':args[4]['preparation_evidence'][0]['id']='OLD_EVIDENCE'
    elif fault=='wrong_receipt':args[6]['current_receipt']['text']='OLD6DEVICE_RECEIPT'
    else:args[7]+='\nOLD_CASE_ID'
    with pytest.raises(AssertionError):observer.separation(*args)


def dummy_files(tmp_path):
    public=tmp_path/'candidate';public.mkdir()
    for name in narrow.PUBLIC_FILES-{'result.json'}:(public/name).write_bytes(b'UNIT_PLACEHOLDER_NOT_REAL_SCREENSHOT_OR_TXT')
    return public


def test_narrow_publisher_rejects_unlisted_image_without_exposing_success(tmp_path,monkeypatch):
    public=dummy_files(tmp_path);(public/'07-unapproved.png').write_bytes(b'UNIT_PLACEHOLDER')
    monkeypatch.delenv('GITHUB_STEP_SUMMARY',raising=False)
    with redirect_stdout(StringIO()):code=base.finish_report(dict(status='PASS'),[],public,allowed_names=narrow.PUBLIC_FILES)
    assert code==1 and not public.with_name('parkweave-fictional-browser-evidence').exists()
    assert public.exists()


def test_narrow_post_summary_timeout_removes_PASS_for_exact_profile(tmp_path,monkeypatch):
    public=dummy_files(tmp_path);summary=tmp_path/'summary';summary.write_text('PRIOR\n')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    monkeypatch.setattr(base.time,'monotonic',MockClock([300,310,311,361]))
    with redirect_stdout(StringIO()):code=base.finish_report(dict(status='PASS'),[],public,started=0,allowed_names=narrow.PUBLIC_FILES)
    terminal=json.loads((public.with_name('parkweave-fictional-browser-evidence')/'result.json').read_text())
    assert code==1 and terminal['status']=='FAIL' and '"status": "PASS"' not in summary.read_text()


class MockClock:
    def __init__(self,values):self.values=iter(values)
    def __call__(self):return next(self.values)


def test_narrow_single_clock_preserves_work_and_cleanup_reservations(tmp_path,monkeypatch):
    observer=narrow.Narrow({},tmp_path,0)
    monkeypatch.setattr(narrow.time,'monotonic',lambda:269)
    observer.work_complete();observer.closing_reservation()
    with pytest.raises(AssertionError):observer.require(15)
    monkeypatch.setattr(narrow.time,'monotonic',lambda:341)
    with pytest.raises(AssertionError):observer.closing_reservation()
