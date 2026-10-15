from pathlib import Path
import json
def pytest_collection_finish(session):
    Path('.runtime/source-adoption/delta-4c163fe-same-run-collection.json').write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')
