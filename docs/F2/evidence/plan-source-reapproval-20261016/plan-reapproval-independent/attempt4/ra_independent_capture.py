from pathlib import Path
import os,json,hashlib

def pytest_configure(config):
 import parkweave
 actual=Path(parkweave.__file__).resolve();expected=Path(os.environ['RA_PROJECT'])/'src/parkweave/__init__.py'
 assert actual==expected, 'exact private source package required'
 target=Path(os.environ['RA_COLLECTION'])
 target.with_name('product-package.json').write_text(json.dumps(dict(actual=str(actual),expected=str(expected),sha256=hashlib.sha256(actual.read_bytes()).hexdigest()),indent=2)+'\n')

def pytest_collection_finish(session):
 Path(os.environ['RA_COLLECTION']).write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
