"""Read-only diagnostic data, never an execution grant or cleanup receipt.

No native imports, exception text/args, frame locals, environment or private
paths. Source sites must match compiled reviewed checkout code, not just a
caller-selected module name or filename. Unknowns remain explicitly unknown.
"""
from pathlib import Path
import os
import re
import sys
from types import CodeType


# Only concrete classes already loaded by the original execution path. This
# is a finite category contract, not permission to accept arbitrary type names.
_KNOWN=(("parkweave.store","Denied","Denied","ACCESS_OR_BINDING_REFUSED"),
        ("_ctypes","ArgumentError","CTYPES_ARGUMENT_ERROR","FFI_ARGUMENT_CONVERSION"),
        ("struct","error","STRUCT_ERROR","BINARY_LAYOUT"),
        ("scripts.windows_portable.native_runtime_staging","RuntimeMetadataChanged",
         "RuntimeMetadataChanged","RUNTIME_METADATA_MISMATCH"),
        ("scripts.windows_portable.native_runtime_staging","RuntimeStagingFailure",
         "RuntimeStagingFailure","RUNTIME_CONSTRUCTION"),
        ("scripts.windows_portable.native_system_crt","CRTTrustFailure",
         "CRTTrustFailure","CRT_SIGNATURE_INSPECTION"))
_SOURCES=(
    ('scripts.windows_portable.controller','scripts/windows_portable/controller.py'),
    ('scripts.windows_portable.directories','scripts/windows_portable/directories.py'),
    ('scripts.windows_portable.fixed_directories','scripts/windows_portable/fixed_directories.py'),
    ('scripts.windows_portable.fixed_journal','scripts/windows_portable/fixed_journal.py'),
    ('scripts.windows_portable.fixed_windows_journal','scripts/windows_portable/fixed_windows_journal.py'),
    ('scripts.windows_portable.windows_directory_handles','scripts/windows_portable/windows_directory_handles.py'),
    ('scripts.windows_portable.native_instance_security','scripts/windows_portable/native_instance_security.py'),
    ('scripts.windows_portable.native_runtime_staging','scripts/windows_portable/native_runtime_staging.py'),
    ('scripts.windows_portable.native_layout_candidate','scripts/windows_portable/native_layout_candidate.py'),
    ('scripts.windows_portable.native_secret_store_candidate','scripts/windows_portable/native_secret_store_candidate.py'),
    ('scripts.windows_portable.native_preparation_sessions','scripts/windows_portable/native_preparation_sessions.py'),
    ('scripts.windows_portable.native_system_crt','scripts/windows_portable/native_system_crt.py'),
    ('scripts.windows_portable.native_protected_objects','scripts/windows_portable/native_protected_objects.py'),
    ('scripts.windows_portable.native_trial_authority','scripts/windows_portable/native_trial_authority.py'),
    ('scripts.windows_portable.native_trial_domain','scripts/windows_portable/native_trial_domain.py'),
    ('parkweave.windows_files','src/parkweave/windows_files.py'),
    ('parkweave.windows_handles','src/parkweave/windows_handles.py'))


def known_exception(error):
    for module,name,label,category in _KNOWN:
        loaded=sys.modules.get(module)
        cls=vars(loaded).get(name) if loaded is not None else None
        if cls is not None and type(error) is cls:
            return dict(type=label,category=category)
    return None


class SourceSites:
    """Compile fixed source without executing it, after verified admission.

    The source SHA is the reviewed parent of the source-bound window. Existing
    checkout trust is the same as the original coordinator, not a same-user
    hostile-code sandbox. No file reads occur while traversing an exception.
    """
    def __init__(self,root,source_commit,*,runtime_files=()):
        if not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('SOURCE_ID_REQUIRED')
        self.source_commit=source_commit;self.modules={}
        # Only the original verified public software manifest supplies paths.
        # No installed root, exception args, unknown directory entry or SID.
        self.runtime_paths=set()
        if runtime_files:
            from scripts.windows_portable.payload import safe_name,MANIFEST,MAX_FILES
            if type(runtime_files) is not dict or len(runtime_files)>MAX_FILES:
                raise ValueError('RUNTIME_CATALOG_REQUIRED')
            for relative in (*runtime_files,MANIFEST):
                safe_name(relative)
                parts=relative.split('/')
                self.runtime_paths.update('/'.join(parts[:i]) for i in range(1,len(parts)+1))
            self.runtime_paths.add('')
        for module,relative in _SOURCES:
            path=Path(root)/relative
            if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024:
                raise ValueError('FIXED_SOURCE_REQUIRED')
            raw=path.read_bytes()
            code=compile(raw,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize)
            pending=[code];catalogue={}
            while pending:
                current=pending.pop()
                if len(catalogue)>=4096:raise ValueError('SOURCE_CODE_LIMIT')
                catalogue[current]=(current.co_qualname,
                    frozenset(line for _,_,line in current.co_lines() if line is not None))
                pending.extend(value for value in current.co_consts if type(value) is CodeType)
            self.modules[module]=(os.path.normcase(str(path)),catalogue)

    def locate(self,error,*,max_nodes=64,max_frames=8):
        max_nodes=max(0,min(64,max_nodes));max_frames=max(0,min(8,max_frames))
        rows=[];count=0;seen=set()
        # Read the original BaseException descriptor, never a custom property.
        tb=BaseException.__dict__['__traceback__'].__get__(error,type(error))
        while tb is not None and count<max_nodes and id(tb) not in seen:
            seen.add(id(tb));count+=1
            frame=tb.tb_frame;module=frame.f_globals.get('__name__')
            item=self.modules.get(module) if type(module) is str else None
            loaded=sys.modules.get(module) if item is not None else None
            if item is not None and loaded is not None and vars(loaded) is frame.f_globals:
                code=frame.f_code;filename,catalogue=item
                allowed=catalogue.get(code)
                if (allowed is not None and os.path.normcase(code.co_filename)==filename
                        and tb.tb_lineno in allowed[1]):
                    # Names come from compiled fixed source, never arbitrary frames.
                    rows.append(dict(module=module,function=allowed[0],line=tb.tb_lineno))
            tb=tb.tb_next
        return dict(status='MATCHED' if rows else 'SITE_UNAVAILABLE',
            source_commit=self.source_commit,frames=rows[-max_frames:] if max_frames else [],
            examined_nodes=count,truncated=tb is not None or len(rows)>max_frames)


def detail(error,public_type,sites=None,budget=None):
    kind=known_exception(error)
    result=dict(type=kind['type'] if kind else public_type,
        category=kind['category'] if kind else
            'UNCLASSIFIED' if public_type=='UNLISTED_EXCEPTION' else 'RECORDED_TYPE')
    if kind is not None and kind['category']=='CRT_SIGNATURE_INSPECTION':
        from scripts.windows_portable.native_system_crt import TRUST_PHASES,TRUST_ACTIVITIES,TRUST_CLOSE,CRT_DLLS
        data=vars(error);stage=data.get('stage');activity=data.get('activity')
        returned=data.get('verify_returned');ok=data.get('verify_ok');closed=data.get('close_outcome')
        if (type(stage) is str and stage in TRUST_PHASES and type(activity) is str and activity in TRUST_ACTIVITIES
                and type(returned) is bool and (type(ok) is bool if returned else ok is None)
                and type(closed) is str and closed in TRUST_CLOSE):
            facts=dict(stage=stage,activity=activity,verify_returned=returned,verify_returned_zero=ok,wvt_close=closed)
            name=data.get('image_name')
            if type(name) is str and name in CRT_DLLS:facts['image_name']=name
            result['crt_signature']=facts
        else:result['crt_signature']=dict(details='UNAVAILABLE')
    if kind is not None and kind['category']=='RUNTIME_METADATA_MISMATCH':
        # Known exact class only; never call arbitrary public()/str()/args.
        data=vars(error);object_kind=data.get('object_kind');fields=data.get('changed_fields')
        allowed=('IDENTITY','ATTRIBUTES','SIZE','LINKS','SECURITY','PATH','LAYOUT')
        if (type(object_kind) is str and object_kind in ('DIRECTORY','FILE')
                and type(fields) is tuple and 0<len(fields)<=len(allowed)
                and all(type(field) is str and field in allowed for field in fields)
                and len(set(fields))==len(fields)):
            result['runtime_metadata']=dict(object_kind=object_kind,changed_fields=list(fields))
        else:result['runtime_metadata']=dict(details='UNAVAILABLE')
    if kind is not None and kind['category'] in ('RUNTIME_METADATA_MISMATCH','RUNTIME_CONSTRUCTION'):
        data=vars(error);relative=data.get('relative_path')
        if sites is not None and type(relative) is str and relative in sites.runtime_paths:
            result['runtime_relative_path']=relative or '<RUNTIME_ROOT>'
        if kind['category']=='RUNTIME_CONSTRUCTION':
            from scripts.windows_portable.native_runtime_staging import STAGING_PHASES
            stage=data.get('stage')
            result['runtime_stage']=stage if type(stage) is str and stage in STAGING_PHASES else 'UNAVAILABLE'
    if sites is None:
        location=dict(status='SITE_UNAVAILABLE',frames=[],truncated=False)
    elif budget is not None and (budget['nodes']<=0 or budget['frames']<=0):
        location=dict(status='SITE_LIMIT',frames=[],truncated=True)
    else:
        location=sites.locate(error,max_nodes=budget['nodes'] if budget else 64,
            max_frames=min(8,budget['frames']) if budget else 8)
        if budget is not None:
            budget['nodes']-=location['examined_nodes'];budget['frames']-=len(location['frames'])
    result['source_sites']=location
    return result
