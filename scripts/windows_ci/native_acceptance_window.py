"""Source-reviewed approval data loader. JSON is parsed, never executed.

Reading this fixed source metadata is the only IO before an unbound entry
refuses. No native module, payload, temp path, token or generator is touched.
An approved enabling commit may change this JSON and its workflow only.
"""
import json
from pathlib import Path
import stat
import weakref

from . import native_acceptance_harness as h

_issued=weakref.WeakKeyDictionary()
_CONTEXT=('GITHUB_ACTIONS','RUNNER_ENVIRONMENT','RUNNER_OS','NATIVE_PUBLIC','GITHUB_REPOSITORY','GITHUB_REF',
    'GITHUB_JOB','GITHUB_EVENT_NAME','GITHUB_RUN_ATTEMPT','GITHUB_RUN_NUMBER','GITHUB_RUN_ID',
    'GITHUB_SHA','GITHUB_WORKFLOW_REF','GITHUB_WORKFLOW_SHA','GITHUB_WORKSPACE','RUNNER_TEMP','PSYCOPG_IMPL')


def _context(context):
    # Snapshot only names of forbidden PG defaults, never their secret values.
    return tuple((key,context.get(key)) for key in _CONTEXT)+(tuple(sorted(key for key in context if key.upper().startswith('PG'))),)


class _SourceWindow:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('WINDOW_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('WINDOW_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('WINDOW_NOT_TRANSFERABLE')


def _pairs(items):
    result={}
    for key,value in items:
        h.need(key not in result);result[key]=value
    return result


def load_source_window(context):
    path=Path(__file__).with_suffix('.json');before=path.lstat()
    h.need(stat.S_ISREG(before.st_mode) and not path.is_symlink()
           and not getattr(before,'st_file_attributes',0)&0x400 and before.st_size<=8192)
    with path.open('rb') as source:record=source.read(8193)
    h.need(len(record)<=8192)
    after=path.lstat()
    h.need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
           (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns))
    value=json.loads(record,object_pairs_hook=_pairs)
    h.need(type(value) is dict and set(value)=={'repository','ref','job','run_number','run_id','expires_utc',
        'reviewed_parent','workflow_sha256','operations','seconds'})
    h.need(type(value['operations']) is list and len(value['operations'])==len(set(value['operations'])))
    value['operations']=frozenset(value['operations'])
    w=h.Window(**value);w,key=h.window_context(context,w)
    # Issued only by fixed committed source data, never by a caller JSON report.
    cap=_SourceWindow();_issued[cap]=(w,key,_context(context))
    return cap


def consume(cap,context):
    h.need(type(cap) is _SourceWindow and cap in _issued)
    w,key,before=_issued.pop(cap)
    h.need(before==_context(context))
    h.need(not any(key.upper().startswith('PG') for key in context) and context.get('PSYCOPG_IMPL')=='binary'
           and 360<w.expires_utc-h.time.time()<=86400)
    return w,key
