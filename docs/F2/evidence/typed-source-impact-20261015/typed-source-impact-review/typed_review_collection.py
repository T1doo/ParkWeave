from pathlib import Path
import json
OUT=Path('/workspace/ParkWeave/.runtime/typed-source-impact-review')
def pytest_collection_finish(session):
    (OUT/'extra-a5d9da25-collection.json').write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')
