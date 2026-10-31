"""Plan-only by default; fixed source approval precedes every native action."""
import argparse
import json
from pathlib import Path
import sys


_PHASES=frozenset(('PREPARE','ACQUIRE','CREDENTIALS','CLUSTER','CREATE_SCHEMA','ROLES',
    'SESSIONS','SEED','CONFIG','VERIFY_FILES','VERIFY_DATABASE','READY','APPLICATION','RUNNING',
    'NOT_STARTED','VERIFY_EXISTING','NEW_LAYOUT','CLUSTER_INPUTS','PINNED_SUSPENDED_INITDB','CLOSE',
    'STOP_OWNED','CLOSE_SECURITY_FILES','RETAIN_SECURITY_FILES','FINAL_STATE','UNKNOWN_STATE','RELEASE',
    'LAYOUT','STORE','TARGET','OWNER','PIPE'))
_ERROR_TYPES=frozenset(('BaseException','Exception','ExceptionGroup','BaseExceptionGroup',
    'RuntimeError','ValueError','TypeError','AssertionError','OSError','PermissionError',
    'FileNotFoundError','FileExistsError','TimeoutError','ProcessLookupError','ChildProcessError',
    'ImportError','ModuleNotFoundError','KeyError','IndexError','AttributeError','OverflowError',
    'UnicodeError','UnicodeDecodeError','UnicodeEncodeError','SystemExit','KeyboardInterrupt',
    'CandidateRefused','ControlFailure','WindowRefused','TrialRefused','BoundaryError',
    'AcceptanceRefused','OwnedJobError','BrokenPipeError','ConnectionError','ConnectionRefusedError',
    'ConnectionResetError','EOFError','NotImplementedError','JSONDecodeError',
    'CalledProcessError','TimeoutExpired','CRTRefused','ProtectionRefused','ProtectionFailure',
    'RuntimePayloadRefused','TokenRefused','TokenFailure','StartupRefused','StartupFailure',
    'ProcessRefused','ProcessStartFailure','DatabaseProbeFailure','DataRefused','PayloadRefused',
    'LayoutRefused','PipeRefused','PipeFailure','SecurityFailure','StoreRefused','StoreFailure',
    'EndpointRefused','NativeFailure','LeaseRefused','DaclRefused','DaclFailure','EnvelopeRefused',
    'ClusterStartFailure','OperationalError','ProgrammingError','IntegrityError','InterfaceError',
    'DatabaseError','NotSupportedError','InternalError','DataError','InvalidPassword',
    'InsufficientPrivilege','ConnectionTimeout','SignatureRejected','UnsupportedNamespaceObservation',
    'PreparationCommandUnknown','GenerationRefused','InstallFailure'))


def _error_type(error):
    diagnostics=sys.modules.get('scripts.windows_ci.native_failure_diagnostics')
    known=diagnostics.known_exception(error) if diagnostics is not None else None
    if known is not None:return known['type']
    name=type(error).__name__
    return name if name in _ERROR_TYPES else 'UNLISTED_EXCEPTION'


def _control_summary(value,error,chain):
    # public() excludes exception text but its phase/type fields are not an
    # output allowlist. Never serialize caller-selected strings or extra keys.
    def phase(item):return item if type(item) is str and item in _PHASES else 'UNLISTED_PHASE'
    result=dict(outcome='UNKNOWN',phase=phase(value['phase']),
        cause_count=value['cause_count'],cleanup_count=value['cleanup_count'],
        causes=[_error_type(item) for item in error.causes[:16]],
        cleanup=[dict(phase=phase(row['phase']),types=[_error_type(item) for item in chain(original[1])[:16]])
            for row,original in zip(value['cleanup'][:16],error.cleanup_errors[:16])])
    if 'operation' in value:
        result['operation']=value['operation'] if type(value['operation']) is str and value['operation'] in ('CREATE','REOPEN') else 'UNLISTED_OPERATION'
    return result


def _failure_diagnostic(error,sites=None):
    if error is None:return None
    result=dict(type=_error_type(error))
    # No product/native import on a null source window. Only an already loaded
    # exact original ControlFailure may run its known public serializer.
    module=sys.modules.get('scripts.windows_portable.controller')
    cls=vars(module).get('ControlFailure') if module is not None else None
    if cls is None or type(error) is not cls:return result
    try:
        chain=vars(module)['exception_chain']
        result['control']=_control_summary(cls.public(error),error,chain)
        nested=[];seen={id(error)};truncated=len(error.causes)>64
        # Causal postorder places wrapper ControlFailures AFTER their leaves.
        # Scan a bounded suffix backwards to retain the nearest wrappers too.
        for cause in reversed(error.causes[-64:]):
            if type(cause) is cls and id(cause) not in seen:
                seen.add(id(cause))
                if len(nested)<4:nested.append(_control_summary(cls.public(cause),cause,chain))
                else:truncated=True
        result['nested_controls']=nested
        result['nested_controls_truncated']=truncated
        diagnostics=sys.modules.get('scripts.windows_ci.native_failure_diagnostics')
        if diagnostics is not None:
            # Shared references distinguish repeated causal/context appearances
            # from independent faults. Never expose process object addresses.
            details=[];references={};limited=(len(error.causes)>16 or len(error.cleanup_errors)>16)
            budget=dict(nodes=64,frames=16)
            def describe(item):
                nonlocal limited
                if id(item) in references:return references[id(item)]
                if len(details)>=32:limited=True;return 'DETAIL_LIMIT'
                reference=len(details);references[id(item)]=reference
                details.append(diagnostics.detail(item,_error_type(item),sites,budget))
                return reference
            result['cause_details']=[describe(item) for item in error.causes[:16]]
            cleanup_details=[]
            for row,original in zip(result['control']['cleanup'],error.cleanup_errors[:16]):
                causes=chain(original[1]);limited=limited or len(causes)>16
                cleanup_details.append(dict(phase=row['phase'],errors=[describe(item) for item in causes[:16]]))
            result['cleanup_details']=cleanup_details
            result['exception_details']=details
            result['details_truncated']=limited or any(item['source_sites']['truncated'] for item in details)
    except BaseException:
        # Diagnostic failure cannot replace the original failure or exit code.
        result=dict(type=_error_type(error),diagnostic='UNAVAILABLE')
    return result


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
    scope=None;primary=None;cleanup=None;pins=None;pin_cleanup_end=None;sites=None
    stage='SOURCE_WINDOW';failure_stage=None;cleanup_scope='NOT_ATTEMPTED'
    try:
        from scripts.windows_ci.native_business_window import load_source_window,verify_bootstrap_and_consume,need
        source=load_source_window()  # Null currently: refuse BEFORE native/candidate/RNG/OS actions.
        from scripts.windows_ci.native_failure_diagnostics import SourceSites
        if args.check_window:
            print(json.dumps(dict(window='SOURCE_BOUND_NOT_EXECUTED',activation_allowed=False)));return 0
        stage='CANDIDATE_ARGUMENTS'
        need(args.payload is not None and args.candidate_zip is not None)
        if args.extract_only:
            stage='EXTRACT_ARCHIVE'
            from scripts.windows_ci.native_business_window import extract_approved_archive
            extract_approved_archive(source,args.payload,args.candidate_zip)
            print(json.dumps(dict(candidate='EXTRACTED_VERIFIED_NOT_EXECUTED',activation_allowed=False)));return 0
        if args.verify_only:
            stage='VERIFY_ARCHIVE'
            from scripts.windows_ci.native_business_window import verify_staged_bytes
            verify_staged_bytes(source,args.payload,args.candidate_zip)
            print(json.dumps(dict(candidate='BYTES_VERIFIED_NOT_EXECUTED',activation_allowed=False)));return 0
        stage='BOOTSTRAP_PINS'
        verified=verify_bootstrap_and_consume(source,args.payload,args.candidate_zip)
        # Frozen vendor is admitted only after the actual package bytes passed.
        from scripts.windows_ci.native_business_window import _verified
        pins=_verified[verified][7]
        pin_cleanup_end=_verified[verified][5]+_verified[verified][0].cleanup_seconds
        # Optional source diagnostics never grant work or change failure into success.
        try:sites=SourceSites(root,_verified[verified][0].reviewed_parent)
        except Exception:sites=None
        stage='PINNED_IMPORTS'
        from scripts.windows_ci.pinned_vendor_imports import restrict_bootstrap_imports
        restrict_bootstrap_imports(root,pins)
        stage='SCOPE_CONSTRUCTION'
        from scripts.windows_ci.native_business_scope import NativeBusinessScope
        scope=NativeBusinessScope(verified)
        stage='BUSINESS'
        result=scope.run()
    except BaseException as error:primary=error;failure_stage=stage
    finally:
        if scope is not None:
            cleanup_scope='SCOPE_CLOSE'
            try:scope.close(failed=primary is not None)
            except BaseException as error:cleanup=error
        elif pins is not None:
            cleanup_scope='PINS_CLOSE'
            try:pins.close(pin_cleanup_end)
            except BaseException as error:cleanup=error
    if primary is not None or cleanup is not None:
        print(json.dumps(dict(result='NOT_EXECUTED_OR_UNKNOWN',
            primary_type=_error_type(primary) if primary is not None else None,
            cleanup_type=_error_type(cleanup) if cleanup is not None else None,
            failure_stage=failure_stage or cleanup_scope,
            primary=_failure_diagnostic(primary,sites),cleanup=_failure_diagnostic(cleanup,sites),
            outer_cleanup=dict(scope=cleanup_scope,
                returned_without_exception=cleanup_scope!='NOT_ATTEMPTED' and cleanup is None,
                controller_cleanup='SEE_CONTROL_SUMMARIES_OR_NOT_OBSERVED'),
            activation_allowed=False,usable_product=False,native_acceptance='NOT_ACCEPTED')))
        return 2
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
