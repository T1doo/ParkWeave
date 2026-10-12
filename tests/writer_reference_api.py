"""Actual fresh API process with app-only configuration supplied by controller."""
import json
from pathlib import Path
import sys
import uvicorn
from parkweave.store import Store
from parkweave.api import create_app
from parkweave import native_run_access as native,native_run_access_writer as writer


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text())
    assert set(config) in ({'app_dsn','port'},{'app_dsn','port','policy','pin'})
    store=Store(config['app_dsn'])
    if 'policy' in config:
        client=writer.WriterClient(store,config['policy'],config['pin'])
        store._native_run_access=native.NativeRunAccess(store,writer=client)
    uvicorn.run(create_app(store),host='127.0.0.1',port=config['port'],log_level='warning',access_log=False)
