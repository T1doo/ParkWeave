"""Optional fixed-phase pytest telemetry. No test IDs, counts, paths or messages."""
import json
import os
from pathlib import Path
import re
import uuid

PHASES=frozenset({'UNKNOWN','acceptance_bindings','pytest_launch','pytest_collect','pytest_setup','pytest_call','pytest_teardown','pytest_finish','report_summary','report_write'})
PATTERN=r'server-regression-([0-9a-f]{32})\.progress\.json'


def write(path,phase):
    if path is None:return
    temporary=None
    try:
        path=Path(path);match=re.fullmatch(PATTERN,path.name)
        if not match or phase not in PHASES:return
        temporary=path.with_name('.progress-'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps({'schema':1,'execution_id':match[1],'phase':phase},separators=(',',':'))+'\n',encoding='ascii')
        os.replace(temporary,path)
    except Exception:pass  # Telemetry cannot change a test's result or cleanup.
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass


def read(path):
    try:
        path=Path(path);match=re.fullmatch(PATTERN,path.name)
        if not match or path.resolve()!=path.absolute():return 'UNKNOWN'
        with path.open('rb') as stream:data=stream.read(513)
        if len(data)>512:return 'UNKNOWN'
        row=json.loads(data.decode('ascii'))
        if not isinstance(row,dict) or set(row)!={'schema','execution_id','phase'} or type(row['schema']) is not int or row['schema']!=1 or row['execution_id']!=match[1] or not isinstance(row['phase'],str) or row['phase'] not in PHASES:return 'UNKNOWN'
        return row['phase']
    except (OSError,ValueError,TypeError,UnicodeError,RecursionError):return 'UNKNOWN'
