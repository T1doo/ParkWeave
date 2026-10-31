"""Actual Linux entry subprocess checks; no Windows/native business execution.

Only source admission/pins/scope are controlled protocol doubles. The entry,
ControlFailure causal graph, JSON boundary and harmless failing child are real.
"""
import json
from pathlib import Path
import subprocess
import sys

from scripts.windows_ci import native_business_entry as entry
from scripts.windows_portable.controller import ControlFailure

ROOT=Path(__file__).resolve().parents[1]
PRIVATE='SYNTHETIC_PRIVATE_DO_NOT_LOG'


PROGRAM=r'''
import json,subprocess,sys,types
sys.path.insert(0,sys.argv[1])
from scripts.windows_ci import native_business_entry as entry
from scripts.windows_portable.controller import ControlFailure
scenario=sys.argv[2];events=[];private='SYNTHETIC_PRIVATE_DO_NOT_LOG'
window=types.ModuleType('scripts.windows_ci.native_business_window')
grant=object();verified=object()
def load():events.append('source');return grant
def verify(*args):events.append('pins');return verified
def need(value):
    if not value:raise ValueError(private)
class Pins:
    def close(self,end):
        events.append('pins-close')
        if scenario=='pins-failure':raise OSError(private)
window.load_source_window=load;window.verify_bootstrap_and_consume=verify;window.need=need
window._verified={verified:(types.SimpleNamespace(cleanup_seconds=60,reviewed_parent='a'*40),None,None,None,None,100,None,Pins())}
sys.modules[window.__name__]=window
imports=types.ModuleType('scripts.windows_ci.pinned_vendor_imports')
def restrict(*args):
    events.append('imports')
    if scenario=='pins-failure':raise ValueError(private)
imports.restrict_bootstrap_imports=restrict;sys.modules[imports.__name__]=imports
scope=types.ModuleType('scripts.windows_ci.native_business_scope')
class Scope:
    def __init__(self,source):events.append('scope')
    def run(self):
        events.append('business-protocol')
        if scenario=='source-site':
            from scripts.windows_portable import directories
            try:directories._decode(b'')  # Real fixed-source pure validation.
            except directories.LeaseRefused as cause:raise ControlFailure('ACQUIRE',cause,[]) from cause
        if scenario in ('failure','both-nested','diagnostic-unavailable'):
            try:
                subprocess.run([sys.executable,'-I','-B','-S','-c',
                    "import sys;sys.stderr.write('SYNTHETIC_PRIVATE_DO_NOT_LOG');sys.exit(7)"],
                    check=True,capture_output=True,timeout=5)
            except subprocess.CalledProcessError as cause:
                events.append('actual-child-exit-'+str(cause.returncode))
                inner=ControlFailure('CLUSTER',cause,[])
                if scenario=='both-nested':
                    outer=ControlFailure('RUNNING',inner,[('STOP_OWNED',TimeoutError(private))])
                    raise outer from inner
                if scenario=='diagnostic-unavailable':inner.cleanup_errors=((private,),)
                raise inner from cause
        return dict(result='CONTROLLED_PROTOCOL_RESULT',activation_allowed=False,usable_product=False)
    def close(self,*,failed):
        events.append('scope-close-failed-'+str(failed))
        if scenario in ('cleanup-failure','both-nested'):
            raise ControlFailure('CLOSE',None,[('RELEASE',OSError(private))])
scope.NativeBusinessScope=Scope;sys.modules[scope.__name__]=scope
code=entry.main(['--execute','--payload','unused-protocol-payload','--candidate-zip','unused-protocol-archive'])
sys.stderr.write(json.dumps(events));raise SystemExit(code)
'''


def run_entry(scenario):
    result=subprocess.run([sys.executable,'-I','-B','-S','-c',PROGRAM,str(ROOT),scenario],
        text=True,capture_output=True,timeout=15,cwd=ROOT)
    assert PRIVATE not in result.stdout+result.stderr
    return result,json.loads(result.stdout),json.loads(result.stderr)


def test_actual_entry_normal_result_and_exit_preserved():
    process,report,events=run_entry('normal')
    assert process.returncode==0
    assert report==dict(result='CONTROLLED_PROTOCOL_RESULT',activation_allowed=False,usable_product=False)
    assert events==['source','pins','imports','scope','business-protocol','scope-close-failed-False']


def test_actual_child_failure_retains_control_phase_type_and_unknown():
    process,report,events=run_entry('failure')
    assert process.returncode==2 and events[-2:]==['actual-child-exit-7','scope-close-failed-True']
    assert report['result']=='NOT_EXECUTED_OR_UNKNOWN' and report['failure_stage']=='BUSINESS'
    assert report['primary_type']=='ControlFailure' and report['cleanup_type'] is None
    assert report['primary']['control']==dict(outcome='UNKNOWN',phase='CLUSTER',
        cause_count=1,cleanup_count=0,causes=['CalledProcessError'],cleanup=[])
    assert report['outer_cleanup']['returned_without_exception'] is True
    assert report['outer_cleanup']['controller_cleanup']=='SEE_CONTROL_SUMMARIES_OR_NOT_OBSERVED'
    assert report['usable_product'] is report['activation_allowed'] is False


def test_actual_entry_cleanup_failure_cannot_rewrite_success():
    process,report,events=run_entry('cleanup-failure')
    assert process.returncode==2 and events[-1]=='scope-close-failed-False'
    assert report['primary'] is None and report['failure_stage']=='SCOPE_CLOSE'
    assert report['cleanup']['control']==dict(outcome='UNKNOWN',phase='CLOSE',cause_count=0,
        cleanup_count=1,causes=[],cleanup=[dict(phase='RELEASE',types=['OSError'])])
    assert report['outer_cleanup']['returned_without_exception'] is False
    assert report['result']=='NOT_EXECUTED_OR_UNKNOWN'


def test_actual_entry_nested_primary_and_cleanup_keep_both_unknowns():
    process,report,events=run_entry('both-nested')
    assert process.returncode==2 and 'actual-child-exit-7' in events
    assert report['primary']['control']['phase']=='RUNNING'
    assert report['primary']['control']['cleanup']==[dict(phase='STOP_OWNED',types=['TimeoutError'])]
    assert report['primary']['nested_controls'][0]['phase']=='CLUSTER'
    assert report['primary']['nested_controls'][0]['causes']==['CalledProcessError']
    assert report['cleanup']['control']['cleanup']==[dict(phase='RELEASE',types=['OSError'])]
    assert report['failure_stage']=='BUSINESS'


def test_actual_entry_pins_cleanup_failure_preserves_primary_stage():
    process,report,events=run_entry('pins-failure')
    assert process.returncode==2 and events==['source','pins','imports','pins-close']
    assert report['failure_stage']=='PINNED_IMPORTS'
    assert report['primary_type']=='ValueError' and report['cleanup_type']=='OSError'
    assert report['outer_cleanup']['scope']=='PINS_CLOSE'


def test_actual_entry_uses_verified_source_sites_without_private_paths():
    process,report,events=run_entry('source-site')
    assert process.returncode==2 and events[-1]=='scope-close-failed-True'
    assert report['result']=='NOT_EXECUTED_OR_UNKNOWN' and report['primary']['control']['outcome']=='UNKNOWN'
    primary=report['primary'];reference=primary['cause_details'][0]
    location=primary['exception_details'][reference]['source_sites']
    assert location['source_commit']=='a'*40 and location['status']=='MATCHED'
    assert any(row['module']=='scripts.windows_portable.directories' and row['function']=='_decode'
        for row in location['frames'])
    assert str(ROOT) not in process.stdout


def test_actual_entry_diagnostic_failure_never_replaces_original_exit():
    process,report,events=run_entry('diagnostic-unavailable')
    assert process.returncode==2 and 'actual-child-exit-7' in events
    assert report['primary']==dict(type='ControlFailure',diagnostic='UNAVAILABLE')
    assert report['result']=='NOT_EXECUTED_OR_UNKNOWN'


def test_actual_null_entry_refuses_before_native_import_with_redacted_stage():
    process=subprocess.run([sys.executable,'-I','-B','-S',
        str(ROOT/'scripts/windows_ci/native_business_entry.py'),'--execute'],
        capture_output=True,text=True,timeout=5,cwd=ROOT)
    assert process.returncode==2 and process.stderr==''
    report=json.loads(process.stdout)
    assert report['failure_stage']=='SOURCE_WINDOW' and report['primary_type']=='WindowRefused'
    assert report['outer_cleanup']==dict(scope='NOT_ATTEMPTED',returned_without_exception=False,
        controller_cleanup='SEE_CONTROL_SUMMARIES_OR_NOT_OBSERVED')


def test_public_fields_are_filtered_even_when_phase_or_class_name_is_private():
    unusual=type(PRIVATE,(RuntimeError,),{})('postgres://secret@private/path')
    error=ControlFailure(PRIVATE,unusual,[(PRIVATE,OSError('password=secret'))])
    public=entry._failure_diagnostic(error)
    assert PRIVATE not in json.dumps(public) and 'secret' not in json.dumps(public)
    assert public['control']['phase']=='UNLISTED_PHASE'
    assert public['control']['causes']==['UNLISTED_EXCEPTION']
    assert public['control']['cleanup']==[dict(phase='UNLISTED_PHASE',types=['OSError'])]
    class Other:
        def public(self):raise AssertionError('must never call an arbitrary public method')
    assert entry._failure_diagnostic(Other())==dict(type='UNLISTED_EXCEPTION')


def test_cyclic_group_chains_are_bounded_without_messages_or_tracebacks():
    errors=[ValueError(PRIVATE) for _ in range(24)]
    group=ExceptionGroup(PRIVATE,errors);group.__context__=group
    first=ControlFailure('CLUSTER',group,[])
    first.__cause__=group  # Match the real controller's `raise failure from surfaced`.
    error=ControlFailure('RUNNING',first,[('STOP_OWNED',group)])
    report=entry._failure_diagnostic(error)
    assert len(report['control']['causes'])==len(report['control']['cleanup'][0]['types'])==16
    assert report['control']['cause_count']>16 and report['control']['cleanup_count']==1
    assert report['nested_controls'][0]['phase']=='CLUSTER'
    assert report['nested_controls'][0]['cause_count']>16
    assert report['nested_controls_truncated'] is False
    assert PRIVATE not in json.dumps(report)


def test_real_native_error_names_are_retained_without_native_calls():
    from scripts.windows_portable.directories import LeaseRefused
    from scripts.windows_portable.restricted_token_candidate import TokenRefused
    from scripts.windows_portable.processes import ProcessRefused
    for cls in (LeaseRefused,TokenRefused,ProcessRefused):
        error=ControlFailure('CLUSTER',cls(PRIVATE),[])
        assert entry._failure_diagnostic(error)['control']['causes']==[cls.__name__]


def test_nested_control_summary_limit_is_explicit():
    error=ControlFailure('CLUSTER',OSError(PRIVATE),[])
    for _ in range(8):
        wrapped=ControlFailure('RUNNING',error,[]);wrapped.__cause__=error;error=wrapped
    report=entry._failure_diagnostic(error)
    assert len(report['nested_controls'])==4 and report['nested_controls_truncated'] is True
    assert PRIVATE not in json.dumps(report)
