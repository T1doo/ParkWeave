"""Capture actual collection in the executing pytest process, without test effects."""
from pathlib import Path
import json
import os


def pytest_collection_finish(session):
    rows = []
    for item in session.items:
        # Strip the full item name first: parameters may themselves contain ::.
        prefix = item.nodeid[:-(len(item.name) + 2)]
        parts = prefix.split('::')
        classname = parts[0][:-3].replace('/', '.')
        if len(parts) > 1:
            classname += '.' + '.'.join(parts[1:])
        rows.append(dict(nodeid=item.nodeid, classname=classname, name=item.name))
    target = Path(os.environ['PARKWEAVE_DELIVERY_COLLECTION_OUT'])
    assert not target.exists()
    target.write_text(json.dumps(dict(collected=rows), indent=2) + '\n')
