import json, os
from pathlib import Path
# Fixed test artifact paths only. Original source/assertions/Node/API/PG stay intact.
def pytest_configure(config):
    root = Path('/workspace/ParkWeave')
    destination = Path(os.environ['LEGACY_ARTIFACT_DESTINATION'])
    config._common_original_open = Path.open
    config._common_original_mkdir = Path.mkdir
    config._carry_original_exists = Path.exists
    config._carry_original_chmod = Path.chmod
    roots = [root / '.runtime' / name for name in json.loads((root / '.runtime/plan-reapproval-final/v2/artifact-legacy-roots.json').read_text())]
    records = []
    seen = set()
    def replacement(path):
        absolute = Path(os.path.abspath(str(path)))
        for folder in roots:
            if absolute.is_relative_to(folder):
                # This is only a fixed test artifact directory, never PG state.
                # Keep evidence in archive inventory despite legacy pytest-PID name.
                pieces = [('process-' + part[len('pytest-'):]) if part.startswith('pytest-') else part for part in absolute.relative_to(folder).parts]
                return destination / 'artifacts' / folder.relative_to(root / '.runtime') / Path(*pieces)
        return None
    def record(old, new, mode):
        key = (str(old), str(new), mode)
        if key in seen:
            return
        seen.add(key)
        records.append(dict(original=str(old), actual=str(new), mode=mode))
        target = destination / 'fixed-test-artifact-redirections.json'
        with config._common_original_open(target, 'w') as stream:
            stream.write(json.dumps(records, indent=2) + '\n')
    def opened(path, mode='r', *a, **kw):
        target = replacement(path)
        if target is None:
            return config._common_original_open(path, mode, *a, **kw)
        if any(letter in mode for letter in 'wax+'):
            config._common_original_mkdir(target.parent, parents=True, exist_ok=True)
        record(path, target, mode)
        return config._common_original_open(target, mode, *a, **kw)
    def mkdir(path, *a, **kw):
        target = replacement(path)
        if target is None:
            return config._common_original_mkdir(path, *a, **kw)
        # All target parents are new artifact preparation, not business state.
        record(path, target, 'mkdir')
        return config._common_original_mkdir(target, parents=True, exist_ok=True)
    def exists(path):
        target = replacement(path)
        return config._carry_original_exists(target if target is not None else path)
    def chmod(path, mode, *a, **kw):
        target = replacement(path)
        if target is not None:
            record(path, target, "chmod")
        return config._carry_original_chmod(target if target is not None else path, mode, *a, **kw)
    Path.exists = exists
    Path.chmod = chmod
    Path.open = opened
    Path.mkdir = mkdir


def pytest_unconfigure(config):
    Path.open = config._common_original_open
    Path.mkdir = config._common_original_mkdir

    Path.exists = config._carry_original_exists
    Path.chmod = config._carry_original_chmod
