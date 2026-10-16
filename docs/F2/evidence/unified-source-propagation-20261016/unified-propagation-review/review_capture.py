"""Capture item identities only; never alter tests or product logic."""
import os,json
from pathlib import Path

def pytest_collection_finish(session):
    Path(os.environ['UNIFIED_REVIEW_COLLECTION']).write_text(json.dumps([item.nodeid for item in session.items],indent=2)+'\n')
