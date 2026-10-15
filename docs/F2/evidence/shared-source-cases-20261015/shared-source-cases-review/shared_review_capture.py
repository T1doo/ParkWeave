from pathlib import Path
import json,os

def pytest_collection_finish(session):
    Path(os.environ['SHARED_REVIEW_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')
