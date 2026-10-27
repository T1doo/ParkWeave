"""Strict, offline proposal parsing. A proposal confers no execution authority.

The caller supplies a freshly computed trusted candidate document. Model output
must reproduce that entire contract; this boundary neither plans new adapters
nor executes the registered actions embedded in the document.
"""
import math

from .intern_adapter import ModelBoundaryError, strict_json

MAX_BYTES = 65536
MAX_DEPTH = 32
MAX_NODES = 4096
REGISTERED_ADAPTERS = {
    'P1': ('preparation', 1),
    'P2': ('case-resources', 1),
    'P3': ('dispatch', 1),
    'P4': ('executor-receipts', 1),
    'P5': ('case-lifecycle', 1),
}
DOCUMENT_KEYS = frozenset({
    'schema_version', 'origin', 'provider_enabled', 'binding',
    'required_goals', 'goal_coverage', 'steps', 'constraints',
    'global_requirements',
})


class ProposalValidationError(ModelBoundaryError):
    def __init__(self):
        super().__init__('INVALID_PLANNER_PROPOSAL')


def _json_tree(value):
    """Bound the parsed tree and reject non-JSON trusted inputs as well."""
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError('proposal tree limit')
        kind = type(item)
        if kind is dict:
            if any(type(key) is not str for key in item):
                raise ValueError('JSON object key required')
            pending.extend((child, depth + 1) for child in item.values())
        elif kind is list:
            pending.extend((child, depth + 1) for child in item)
        elif kind is str:
            # JSON escaped lone surrogates are not a valid UTF-8 contract.
            item.encode('utf-8')
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError('finite JSON number required')
        elif kind not in (int, bool, type(None)):
            raise ValueError('JSON value required')


def _graph(document):
    if type(document) is not dict or set(document) != DOCUMENT_KEYS:
        raise ValueError('exact proposal document required')
    if (type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['origin'] != 'SYNTHETIC_UNTRUSTED_CANDIDATE'
            or document['provider_enabled'] is not False):
        raise ValueError('synthetic document required')
    steps = document['steps']
    if type(steps) is not list or len(steps) > len(REGISTERED_ADAPTERS):
        raise ValueError('bounded registered steps required')
    dependencies = {}
    for step in steps:
        if type(step) is not dict:
            raise ValueError('registered step required')
        identifier = step.get('id')
        if type(identifier) is not str or identifier not in REGISTERED_ADAPTERS or identifier in dependencies:
            raise ValueError('unique registered step required')
        adapter, revision = REGISTERED_ADAPTERS[identifier]
        if (step.get('adapter') != adapter or type(step.get('revision')) is not int
                or step['revision'] != revision
                or step.get('adapter_ref') != adapter
                or type(step.get('adapter_revision')) is not int
                or step['adapter_revision'] != revision):
            raise ValueError('registered adapter version required')
        parents = step.get('depends_on')
        if (type(parents) is not list or any(type(parent) is not str for parent in parents)
                or len(parents) != len(set(parents))):
            raise ValueError('unique dependencies required')
        dependencies[identifier] = set(parents)
    if any(not parents <= dependencies.keys() for parents in dependencies.values()):
        raise ValueError('dependency node missing')
    completed = set()
    for _ in dependencies:
        completed.update(identifier for identifier, parents in dependencies.items() if parents <= completed)
    if completed != dependencies.keys():
        raise ValueError('dependency cycle')


def _equal(actual, expected):
    """JSON equality with bool, integer and float kept distinct."""
    if type(actual) is not type(expected):
        return False
    if type(actual) is dict:
        return actual.keys() == expected.keys() and all(_equal(actual[key], expected[key]) for key in actual)
    if type(actual) is list:
        return len(actual) == len(expected) and all(_equal(a, e) for a, e in zip(actual, expected))
    return actual == expected


def validate_proposal(raw: str | bytes, expected: dict) -> dict:
    """Return a detached exact contract, or fail closed without exposing output.

    UNKNOWN and UNSUPPORTED are preserved when present in the trusted document;
    successful parsing means structural agreement, never permission to ADOPT.
    """
    try:
        if type(raw) not in (str, bytes):
            raise ValueError('raw JSON text required')
        encoded = raw.encode('utf-8') if type(raw) is str else raw
        if not 0 < len(encoded) <= MAX_BYTES:
            raise ValueError('proposal byte limit')
        actual = strict_json(encoded.decode('utf-8'))
        _json_tree(actual)
        _json_tree(expected)
        _graph(actual)
        _graph(expected)
        if not _equal(actual, expected):
            raise ValueError('trusted contract differs')
        return actual
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise ProposalValidationError() from None
