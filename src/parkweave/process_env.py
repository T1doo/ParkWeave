"""Whitelist only OS plumbing. Explicit caller-owned overrides carry project config.
Never forward inherited provider tokens, DB secrets, proxies, PYTHONPATH or HOME.
"""
from collections.abc import Mapping

OS_ENV_NAMES=frozenset({'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'})


def minimal_environment(source:Mapping[str,str],**project_overrides):
    result={name:source[name] for name in OS_ENV_NAMES if name in source}
    result.update(project_overrides)
    return result
