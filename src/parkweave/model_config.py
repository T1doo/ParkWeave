"""Credential-name compatibility only. No file lookup, provider request, or logging."""
from collections.abc import Mapping
from pydantic import SecretStr


def resolve_intern_token(environment: Mapping[str,str]) -> SecretStr | None:
    # Explicit mapping only; this accessor is not called by the disabled live adapter.
    for name in ('PARKWEAVE_INTERN_API_TOKEN','INTERN_API_TOKEN'):
        value=environment.get(name)
        if value and value.strip():return SecretStr(value)
    return None
