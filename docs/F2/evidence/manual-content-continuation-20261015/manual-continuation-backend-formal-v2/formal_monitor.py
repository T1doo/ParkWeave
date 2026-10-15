import json,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(os.environ['FORMAL_EVIDENCE_ROOT'])
def pytest_runtest_logreport(report):
    if report.when=='call' or report.failed:
        value=dict(utc=datetime.now(timezone.utc).isoformat(),nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration)
        with (ROOT/'progress.jsonl').open('a') as stream:stream.write(json.dumps(value)+'\n')
        if report.failed:
            with (ROOT/'failure-notices.jsonl').open('a') as stream:stream.write(json.dumps(value)+'\n')
