"""Whitelist only OS plumbing. Explicit caller-owned overrides carry project config.
Never forward inherited provider tokens, DB secrets, proxies, PYTHONPATH or HOME.
"""
from collections.abc import Mapping
import os

OS_ENV_NAMES=frozenset({'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'})
WINDOWS_OS_ENV_NAMES=tuple(sorted(OS_ENV_NAMES-{'SYSTEMROOT'}))


def windows_environment(source:Mapping[str,str],**project_overrides):
    """Canonical Windows keys; inherited ambient configuration is not copied.

    A controlled case-sensitive Mapping can contain conflicting aliases even
    though Windows os.environ cannot. Refuse those rather than choose by order.
    Explicit project inputs are still caller-owned, never inherited inputs.
    """
    canonical={name.upper():name for name in WINDOWS_OS_ENV_NAMES}
    result={}
    for key,value in source.items():
        name=canonical.get(key.upper()) if type(key) is str else None
        if name is None:continue
        if type(value) is not str or any(ord(c)<32 for c in value):
            raise ValueError('INVALID_OS_ENVIRONMENT')
        if name in result and result[name]!=value:
            raise ValueError('AMBIGUOUS_OS_ENVIRONMENT')
        result[name]=value
    explicit={}
    for key,value in project_overrides.items():
        folded=key.upper()
        if folded in explicit and explicit[folded][1]!=value:
            raise ValueError('AMBIGUOUS_PROJECT_ENVIRONMENT')
        explicit[folded]=(canonical.get(folded,key),value)
    result.update(explicit.values())
    return result


def minimal_environment(source:Mapping[str,str],**project_overrides):
    if os.name=='nt':return windows_environment(source,**project_overrides)
    result={name:source[name] for name in OS_ENV_NAMES if name in source}
    result.update(project_overrides)
    return result
