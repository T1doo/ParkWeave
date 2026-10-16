"""Record collected identities only; no hooks alter test or product logic."""
import json,os
from pathlib import Path

def pytest_collection_finish(session):
    Path(os.environ['PLAN_REAPPROVAL_REVIEW_COLLECTION']).write_text(json.dumps([x.nodeid for x in session.items],indent=2)+'\n')
