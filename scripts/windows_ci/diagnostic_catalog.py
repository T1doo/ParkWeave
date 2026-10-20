"""Maintain the original bounded static catalog; overflow is never an update.

This developer command checks working-tree AST identifiers, not test execution.
It does not change the runtime reader, its global 3000-ID contract, or any ID.
Both modes finish every input/capacity check before creating a temporary file.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

try:
    from .diagnostics import TEST_ID_PATTERN, MAX_ALLOWLIST_BYTES
except ImportError:
    from diagnostics import TEST_ID_PATTERN, MAX_ALLOWLIST_BYTES

MAX_ALLOWLIST_IDS = 3000  # Original total, not a per-file/per-shard allowance.
MAX_SOURCE_FILES = 1024
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 32 * 1024 * 1024  # Offline maintenance only.
CATALOG = 'scripts/windows_ci/diagnostic-test-ids.json'


class CatalogRefused(ValueError):
    pass


def _source(root):
    directory = root / 'tests'
    paths = sorted(directory.glob('test_*.py'))
    if not 0 < len(paths) <= MAX_SOURCE_FILES:
        raise CatalogRefused('SOURCE_REFUSED')
    ids, snapshot, total = [], {}, 0
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if (path.is_symlink() or path.resolve() != path.absolute() or
                not re.fullmatch(r'tests/test_[a-z0-9_]+\.py', relative)):
            raise CatalogRefused('SOURCE_REFUSED')
        with path.open('rb') as stream:
            raw = stream.read(min(MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES-total) + 1)
        total += len(raw)
        if len(raw) > MAX_SOURCE_FILE_BYTES or total > MAX_SOURCE_TOTAL_BYTES:
            raise CatalogRefused('SOURCE_REFUSED')
        snapshot[relative] = hashlib.sha256(raw).hexdigest()
        tree = ast.parse(raw.decode('utf-8'))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                ids.append(relative + '::' + node.name)
            elif isinstance(node, ast.ClassDef) and node.name[0].isalpha() and node.name.isascii():
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith('test_'):
                        ids.append(relative + '::' + node.name + '::' + method.name)
    if (not ids or any(len(value) > 256 or not re.fullmatch(TEST_ID_PATTERN, value) for value in ids)
            or len(set(ids)) != len(ids)):
        raise CatalogRefused('SOURCE_REFUSED')
    return sorted(ids), snapshot


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogRefused('CATALOG_REFUSED')
        result[key] = value
    return result


def _current(path):
    if path.is_symlink() or path.resolve() != path.absolute():
        raise CatalogRefused('CATALOG_REFUSED')
    with path.open('rb') as stream:
        raw = stream.read(MAX_ALLOWLIST_BYTES + 1)
    if len(raw) > MAX_ALLOWLIST_BYTES:
        raise CatalogRefused('CATALOG_REFUSED')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique)
    if (not isinstance(value, dict) or set(value) != {'schema', 'test_ids'} or
            type(value['schema']) is not int or value['schema'] != 1):
        raise CatalogRefused('CATALOG_REFUSED')
    ids = value['test_ids']
    if (not isinstance(ids, list) or not 0 < len(ids) <= MAX_ALLOWLIST_IDS or
            any(not isinstance(item, str) or len(item) > 256 or not re.fullmatch(TEST_ID_PATTERN, item) for item in ids)
            or len(set(ids)) != len(ids)):
        raise CatalogRefused('CATALOG_REFUSED')
    return frozenset(ids), raw


def inspect(root, *, write=False):
    """Return only fixed reasons/counts; no private IDs, paths or exceptions.

    Capacity refusal preserves the target bytes and creates no temporary file.
    A write I/O failure is reported as unconfirmed, never as confirmed rollback.
    """
    result = {'schema': 1, 'scope': 'WORKTREE_AST_CATALOG_MAINTENANCE', 'status': 'INPUT_REFUSED',
              'expected': None, 'current': None, 'missing': None, 'extra': None,
              'limit_ids': MAX_ALLOWLIST_IDS, 'limit_bytes': MAX_ALLOWLIST_BYTES,
              'candidate_bytes': None, 'write_state': 'NOT_ATTEMPTED'}
    temporary = None
    try:
        root = Path(root).absolute()
        ids, snapshot = _source(root)
        current, original = _current(root / CATALOG)
        wanted = frozenset(ids)
        raw = (json.dumps({'schema': 1, 'test_ids': ids}, indent=2, ensure_ascii=True) + '\n').encode('ascii')
        result.update(expected=len(ids), current=len(current), missing=len(wanted-current),
                      extra=len(current-wanted), candidate_bytes=len(raw))
        if len(ids) > MAX_ALLOWLIST_IDS:
            return dict(result, status='CAPACITY_EXCEEDED')
        if len(raw) > MAX_ALLOWLIST_BYTES:
            return dict(result, status='BYTE_CAPACITY_EXCEEDED')
        if not write:
            return dict(result, status='VALID' if wanted == current else 'MISMATCH')
        # Recheck the complete source snapshot and target before replacing it.
        if _source(root)[1] != snapshot or _current(root / CATALOG)[1] != original:
            return dict(result, status='INPUT_CHANGED')
        path = root / CATALOG
        temporary = path.with_name('.diagnostic-catalog-' + uuid.uuid4().hex + '.tmp')
        result['write_state'] = 'UNCONFIRMED'
        with temporary.open('xb') as stream:
            stream.write(raw)
        os.replace(temporary, path)
        result.update(status='UPDATED', write_state='CONFIRMED')
        return result
    except CatalogRefused as error:
        result['status'] = str(error)
    except (OSError, UnicodeError, ValueError, TypeError, SyntaxError):
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = inspect(Path(__file__).resolve().parents[2], write=args.write)
    print(json.dumps(report, separators=(',', ':'), ensure_ascii=True))
    return 0 if report['status'] in ('VALID', 'UPDATED') else 2


if __name__ == '__main__':
    raise SystemExit(main())
