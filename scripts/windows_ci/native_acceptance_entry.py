"""Approved source-data entry; default plan performs no platform operation."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--check-window',action='store_true')
    p.add_argument('--payload',type=Path)
    p.add_argument('--candidate-zip',type=Path)
    args=p.parse_args(argv)
    # Only standard Python source imports, no native module/constructor.
    root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
    from scripts.windows_ci import native_acceptance_harness as h
    if not args.execute and not args.check_window:print(json.dumps(h.plan(),ensure_ascii=False));return 0
    try:
        import os
        from scripts.windows_ci.native_acceptance_window import load_source_window,consume
        cap=load_source_window(os.environ)
        if args.check_window:
            print(json.dumps(dict(window_context='BOUND_NOT_NATIVE_EXECUTED',activation_allowed=False)));return 0
        w,key=consume(cap,os.environ)
        h.need(args.payload is not None and args.candidate_zip is not None and not args.payload.is_symlink())
        h.verify_invocation(os.environ,w,args.payload.resolve(strict=True),args.candidate_zip)
        result=h.run_protocol(h.NativeBackend(os.environ['RUNNER_TEMP'],key),w.seconds)
        result.update(harness_commit=os.environ['GITHUB_SHA'],actual_run_id=os.environ['GITHUB_RUN_ID'],
            harness_sha256=h.sha256((root/'scripts/windows_ci/native_acceptance_harness.py').read_bytes()).hexdigest())
        raw=json.dumps(result,ensure_ascii=False);h.need(len(raw.encode())<=65536);print(raw)
        return 0 if result['result']=='OBSERVED_ONLY' else 2
    except BaseException as error:
        print(json.dumps(dict(result='NOT_EXECUTED_OR_UNKNOWN',error_type=type(error).__name__,
            activation_allowed=False,usable_product=False)));return 2


if __name__=='__main__':raise SystemExit(main())
