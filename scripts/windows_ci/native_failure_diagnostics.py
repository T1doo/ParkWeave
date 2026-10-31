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
        ("struct","error","STRUCT_ERROR","BINARY_LAYOUT"))
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
    def __init__(self,root,source_commit):
        if not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('SOURCE_ID_REQUIRED')
        self.source_commit=source_commit;self.modules={}
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
