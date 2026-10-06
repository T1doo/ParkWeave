"""Versioned, current-run report storage; no raw command output or environment dump."""
import json
import os
from pathlib import Path
import re
import uuid

SCHEMA=1
ROOT_PATTERN=r'parkweave-server-ci-([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})'


def current_binding(root,source):
    match=re.fullmatch(ROOT_PATTERN,Path(root).name)
    values={key:source.get(name) for key,name in (('run_id','GITHUB_RUN_ID'),('run_attempt','GITHUB_RUN_ATTEMPT'),('head_sha','GITHUB_SHA'))}
    if not match or not all(isinstance(values[k],str) and re.fullmatch(pattern,values[k]) for k,pattern in (('run_id',r'[1-9][0-9]{0,19}'),('run_attempt',r'[1-9][0-9]{0,5}'),('head_sha',r'[0-9a-f]{40}'))):return None
    return {**values,'cluster_id':match[1]}


def persist(report,summary,source,state='IN_PROGRESS',phase='UNKNOWN'):
    """Atomic checkpoints survive later stage failure; persistence never blocks cleanup."""
    report=Path(report);temporary=report.with_name('.engineering-'+uuid.uuid4().hex+'.tmp')
    record={**summary,'diagnostic_schema':SCHEMA,'diagnostic_binding':current_binding(report.parent,source),'report_state':state,'active_phase':phase}
    try:
        report.parent.mkdir(parents=True,exist_ok=True)
        temporary.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        os.replace(temporary,report)
        return True
    except (OSError,ValueError,TypeError):return False
    finally:
        try:temporary.unlink(missing_ok=True)
        except OSError:pass
