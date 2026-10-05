"""Separate Server-only engineering wrapper; Win11 probe main is never bypassed.
Reuses the published candidate's oracle helpers, leaves production dispatch disabled.
"""
import argparse
import ctypes
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import uuid

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'src'))

def require_server():
    if os.name!='nt' or sys.version_info[:2]!=(3,12) or ctypes.sizeof(ctypes.c_void_p)!=8:
        raise RuntimeError('NOT_RUN: native Server2025/Python3.12 x64 only')
    version=sys.getwindowsversion()
    if version.product_type==1 or version.build!=26100:
        raise RuntimeError('NOT_RUN: Server2025 build26100 required; no version spoof')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture-dir',type=Path,required=True);args=parser.parse_args()
    try:require_server()
    except RuntimeError as exc:print(str(exc));return 2
    base=args.fixture_dir
    if not base.is_absolute() or base.parent!=REPO/'.runtime' or not base.name.startswith('server-file-engineering-'):
        raise RuntimeError('fresh Server fixture binding refused')
    uuid.UUID(base.name.removeprefix('server-file-engineering-'))
    from parkweave.windows_files import root_parts,metadata,private_acl
    from parkweave.windows_handles import WinAPI
    api=WinAPI()
    with ExitStack() as stack:
        def hold(h):stack.callback(api.close,h);return h
        drive,parts=root_parts(str(base));parent=hold(api.open_drive(drive));volume=api.info(parent).volume
        for part in parts:
            parent=hold(api.open_relative(parent,part,False));metadata(api.info(parent),True,volume)
        private_acl(api.security(parent),api.user_sid())
        marker=hold(api.open_relative(parent,'SERVER-ENGINEERING-ONLY.txt',True))
        metadata(api.info(marker),False,volume);private_acl(api.security(marker),api.user_sid())
        expected=b'ParkWeave SYNTHETIC Server engineering; not Win11 acceptance.'
        if api.info(marker).size!=len(expected) or api.read(marker,len(expected)+1)!=expected:raise RuntimeError('Server marker mismatch')
        source=REPO/'scripts/windows/file_candidate_probe.py'
        spec=importlib.util.spec_from_file_location('published_candidate_oracles',source);probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        result=probe.run_probe(base,api)  # Only oracle helpers; never call/mutate Win11 main/guard.
    report=json.loads((base/'candidate-report.json').read_text(encoding='utf-8'))
    summary={'scope':'WINDOWS_SERVER_ENGINEERING_NOT_WIN11','platform_release':platform.release(),'build':sys.getwindowsversion().build,
             'counts':{s:sum(c['status']==s for c in report['cases']) for s in ('PASS','FAIL','NOT_RUN')},
             'candidate_exit_code':result,'whole_AT_EX':'NOT_RUN','win11_native_acceptance':'NOT_RUN','production_R4':'DISABLED','real_model_calls':0}
    # Separate public-safe summary. Original oracle evidence and guard remain unchanged.
    (base/'server-engineering-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    probe.acl_new(base/'server-engineering-summary.json',False)
    print(json.dumps(summary));return result

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('Server candidate engineering refused: '+type(exc).__name__+'; no fallback.',file=sys.stderr);raise SystemExit(1)
