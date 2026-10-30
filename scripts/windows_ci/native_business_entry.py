"""Plan-only by default; fixed source approval precedes every native action."""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--check-window',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    parser.add_argument('--extract-only',action='store_true')
    parser.add_argument('--payload',type=Path)
    parser.add_argument('--candidate-zip',type=Path)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root))
    if not (args.execute or args.check_window or args.verify_only or args.extract_only):
        from scripts.windows_ci.native_business_plan import plan
        print(json.dumps(plan(),ensure_ascii=False));return 0
    scope=None;primary=None;cleanup=None;pins=None;pin_cleanup_end=None
    try:
        from scripts.windows_ci.native_business_window import load_source_window,verify_bootstrap_and_consume,need
        source=load_source_window()  # Null currently: refuse BEFORE native/candidate/RNG/OS actions.
        if args.check_window:
            print(json.dumps(dict(window='SOURCE_BOUND_NOT_EXECUTED',activation_allowed=False)));return 0
        need(args.payload is not None and args.candidate_zip is not None)
        if args.extract_only:
            from scripts.windows_ci.native_business_window import extract_approved_archive
            extract_approved_archive(source,args.payload,args.candidate_zip)
            print(json.dumps(dict(candidate='EXTRACTED_VERIFIED_NOT_EXECUTED',activation_allowed=False)));return 0
        if args.verify_only:
            from scripts.windows_ci.native_business_window import verify_staged_bytes
            verify_staged_bytes(source,args.payload,args.candidate_zip)
            print(json.dumps(dict(candidate='BYTES_VERIFIED_NOT_EXECUTED',activation_allowed=False)));return 0
        verified=verify_bootstrap_and_consume(source,args.payload,args.candidate_zip)
        # Frozen vendor is admitted only after the actual package bytes passed.
        from scripts.windows_ci.native_business_window import _verified
        pins=_verified[verified][7]
        pin_cleanup_end=_verified[verified][5]+_verified[verified][0].cleanup_seconds
        from scripts.windows_ci.pinned_vendor_imports import restrict_bootstrap_imports
        restrict_bootstrap_imports(root,pins)
        from scripts.windows_ci.native_business_scope import NativeBusinessScope
        scope=NativeBusinessScope(verified)
        result=scope.run()
    except BaseException as error:primary=error
    finally:
        if scope is not None:
            try:scope.close(failed=primary is not None)
            except BaseException as error:cleanup=error
        elif pins is not None:
            try:pins.close(pin_cleanup_end)
            except BaseException as error:cleanup=error
    if primary is not None or cleanup is not None:
        print(json.dumps(dict(result='NOT_EXECUTED_OR_UNKNOWN',
            primary_type=type(primary).__name__ if primary is not None else None,
            cleanup_type=type(cleanup).__name__ if cleanup is not None else None,
            activation_allowed=False,usable_product=False,native_acceptance='NOT_ACCEPTED')))
        return 2
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
