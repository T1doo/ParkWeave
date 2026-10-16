import os,json,pathlib,subprocess,datetime,hashlib

def pytest_collection_finish(session):
    path=pathlib.Path(os.environ['RELEASE_COLLECTION_JSON'])
    value={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           'collected':[item.nodeid for item in session.items],
           'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path.write_text(json.dumps(value,indent=2)+'\n')
