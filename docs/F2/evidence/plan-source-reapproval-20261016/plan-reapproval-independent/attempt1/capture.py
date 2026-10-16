from pathlib import Path
import os,json
def pytest_collection_finish(session):
 Path(os.environ['RA_COLLECTION']).write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
