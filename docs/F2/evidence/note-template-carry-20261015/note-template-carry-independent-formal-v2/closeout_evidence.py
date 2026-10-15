"""Read completed frozen windows, check private evidence, and write scoped handoff."""
import collections
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = next(p for p in BASE.parents if (p / "pyproject.toml").is_file())
SOURCE = sys.argv[1]


def read(name):
    return json.loads((BASE / name).read_text())


def write(name, value):
    (BASE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SOURCE
assert not subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
new = read("note-carry-v2-validation.json")
prior = read("prior-manual-v2-validation.json")
assert new["source_sha"] == prior["source_sha"] == SOURCE
assert new["counts"] == dict(PASS=28, FAIL=0, ERROR=0, SKIP=0)
assert prior["counts"] == dict(PASS=33, FAIL=0, ERROR=0, SKIP=0)

coverage = read("note-carry-v2-design-coverage.json")
mapped = []
for row in coverage["mappings"]:
    kind = row["coverage_kind"]
    status = {"NAMED_SCENARIO": "PASS", "VARIANTS_ONLY": "VARIANT", "NOT_RUN_IN_THIS_MODULE": "NOT_RUN"}[kind]
    mapped.append(dict(row, status=status, status_scope="Only the written scope and listed frozen-window test nodes"))
write("design-status-mapping.json", dict(source_sha=SOURCE, design_count=22,
    design_is_not_execution_denominator=True,
    statuses=dict(collections.Counter(x["status"] for x in mapped)), mappings=mapped))

private = sorted(BASE.rglob("*.private.json"))
values = set()
for path in private:
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    body = json.loads(path.read_text())
    assert isinstance(body, list) and all(isinstance(x, str) for x in body)
    values.update(body)
assert values and all(len(x) >= 32 for x in values)
patterns = {
    "full": {v.encode() for v in values},
    "prefix_16": {v[:16].encode() for v in values},
    "suffix_16": {v[-16:].encode() for v in values},
}
excluded_names = {"evidence-index.json", "private-evidence-check.json", "final-handoff.json"}
files = sorted(p for p in BASE.rglob("*") if p.is_file() and ".private." not in p.name
    and "__pycache__" not in p.parts and p.name not in excluded_names)
matches = []
for path in files:
    data = path.read_bytes()
    hits = {kind: sum(value in data for value in needles) for kind, needles in patterns.items()}
    if any(hits.values()):
        matches.append(dict(path=str(path.relative_to(ROOT)), match_counts=hits))
check = dict(source_sha=SOURCE, private_registry_count=len(private), known_private_values=len(values),
    private_modes="0600", full_and_prefix_suffix_characters=16, files_scanned=len(files),
    matching_files=matches, private_values_exported=False,
    excluded_private_files=[str(p.relative_to(ROOT)) for p in private],
    scanner_sha256=sha(Path(__file__)))
write("private-evidence-check.json", check)
assert not matches, "Known private synthetic session material found; counts only in private-evidence-check.json"

window_rows = []
legacy_rows = []
precision_rows = []
for prefix in ("note-carry-v2", "prior-manual-v2"):
    result = read(prefix + ".json")
    assert result["source_sha"] == result["head_after"] == SOURCE
    assert result["exit_code"] == 0 and not result["source_drift"] and not result["all_tracked_drift"]
    assert result["collection_junit_exact_match"] and result["unique_junit_nodes"]
    legacy_destination = Path(result["legacy_destination"])
    if not legacy_destination.is_absolute():
        legacy_destination = ROOT / legacy_destination
    legacy_record = legacy_destination / "fixed-test-artifact-redirections.json"
    actual_redirections = json.loads(legacy_record.read_text()) if legacy_record.is_file() else []
    legacy_rows.append(dict(prefix=prefix, fixed_roots=16,
        actual_recorded_redirections=len(actual_redirections),
        redirection_record=str(legacy_record.relative_to(ROOT)) if legacy_record.is_file() else None,
        no_record_means="No fixed legacy artifact root was accessed; collected-module OUT redirection still applied"))
    oracle_rows = []
    trace_records = read(prefix + "-related-traces.json")["records"] + read(prefix + "-own-traces.json")["records"]
    for trace in trace_records:
        path = ROOT / trace["path"]
        if path.name.startswith("oracle-") and path.suffix == ".jsonl":
            assert sha(path) == trace["sha256"]
            oracle_rows.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    assert oracle_rows and not any(x["intentional_unknown"] for x in oracle_rows)
    precision_rows.append(dict(prefix=prefix, known_rows=len(oracle_rows),
        expected_affected_pairs=sum(len(x["expected_affected"]) for x in oracle_rows),
        actual_affected_pairs=sum(len(x["actual_affected"]) for x in oracle_rows),
        expected_preserved_pairs=sum(len(x["expected_preserved"]) for x in oracle_rows),
        actual_preserved_pairs=sum(len(x["actual_preserved"]) for x in oracle_rows),
        missed_affected=sum(len(set(x["expected_affected"])-set(x["actual_affected"])) for x in oracle_rows),
        wrong_affected=sum(len(set(x["actual_affected"])-set(x["expected_affected"])) for x in oracle_rows),
        wrong_preserved=sum(len(set(x["expected_preserved"])^set(x["actual_preserved"])) for x in oracle_rows),
        unknown_impact_precision="NOT_MEASURED; refusal tests do not measure UNKNOWN impact accuracy"))
    window_rows.append(dict(prefix=prefix, modules=result["modules"], counts=result["counts"],
        elapsed_seconds=result["elapsed_seconds"], source_paths=result["tracked_source_paths"],
        all_tracked_paths=result["all_tracked_paths"], source_drift=[], all_tracked_drift=[],
        result=str((BASE/(prefix+".json")).relative_to(ROOT)),
        collection=str((BASE/(prefix+"-collection.json")).relative_to(ROOT)),
        junit=str((BASE/(prefix+".xml")).relative_to(ROOT)),
        validation=str((BASE/(prefix+"-validation.json")).relative_to(ROOT))))

handoff = dict(source_sha=SOURCE, windows=window_rows, modules=2, executed_nodes=61,
    counts=dict(PASS=61, FAIL=0, ERROR=0, SKIP=0),
    new_module=new, prior_module=prior,
    design_22_statuses=dict(collections.Counter(x["status"] for x in mapped)),
    design_counts_are_not_execution_denominators=True,
    old_interrupted_windows="Historical partial only; no scores migrated",
    legacy_capture=legacy_rows, impact_precision_by_window=precision_rows,
    private_registries="Retained locally at 0600; excluded from nonprivate evidence index",
    real_browser="NOT_RUN", Windows="NOT_RUN", formal_AT_signoff="NOT_RUN",
    production="NOT_RUN", real_model_calls=0)
write("final-handoff.json", handoff)

files = sorted(p for p in BASE.rglob("*") if p.is_file() and ".private." not in p.name
    and "__pycache__" not in p.parts and p.name != "evidence-index.json")
write("evidence-index.json", dict(source_sha=SOURCE, excludes=["*.private.*", "__pycache__", "index self"],
    records=[dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=sha(p)) for p in files]))
print(json.dumps(dict(source_sha=SOURCE, windows=2, modules=2, executed_nodes=61,
    counts=handoff["counts"], design_22_statuses=handoff["design_22_statuses"],
    private_registry_count=len(private), known_private_values=len(values),
    private_matches=0, nonprivate_index_records=len(files))))
