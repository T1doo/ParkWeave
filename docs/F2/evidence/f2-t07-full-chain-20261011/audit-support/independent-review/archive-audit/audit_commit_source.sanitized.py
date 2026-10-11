"""Verify the frozen source against read-only loose Git objects; no Git command."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCE = "b5ea90ac9b366b015b43c426ad94b72faf7c8b72"
MANIFEST = "fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf"
sha256 = lambda b: hashlib.sha256(b).hexdigest()
cache = {}


def obj(sha):
    if sha not in cache:
        path = ROOT / ".git/objects" / sha[:2] / sha[2:]
        raw = zlib.decompress(path.read_bytes())
        assert hashlib.sha1(raw).hexdigest() == sha
        header, payload = raw.split(b"\0", 1)
        kind, length = header.split(b" ", 1)
        assert len(payload) == int(length)
        cache[sha] = kind.decode(), payload
    return cache[sha]


def entries(tree_sha):
    kind, raw = obj(tree_sha)
    assert kind == "tree"
    result = {}
    while raw:
        header, tail = raw.split(b"\0", 1)
        mode, name = header.split(b" ", 1)
        result[name.decode()] = (mode.decode(), tail[:20].hex())
        raw = tail[20:]
    return result


def blob_from_tree(tree_sha, path):
    parts = Path(path).parts
    for i, name in enumerate(parts):
        mode, child = entries(tree_sha)[name]
        if i < len(parts) - 1:
            assert mode == "40000"
            tree_sha = child
        else:
            assert mode in {"100644", "100755"}
            kind, content = obj(child)
            assert kind == "blob"
            return content
    raise AssertionError("empty source path")


def main():
    start = datetime.now(timezone.utc).isoformat()
    head = (ROOT / ".git/HEAD").read_text().strip()
    assert head.startswith("ref: ")
    head_sha = (ROOT / ".git" / head[5:]).read_text().strip()
    assert head_sha == SOURCE
    kind, commit = obj(SOURCE)
    assert kind == "commit"
    tree_line = commit.split(b"\n", 1)[0].decode()
    assert tree_line.startswith("tree ")
    tree_sha = tree_line[5:]
    freeze = ROOT / ".runtime/f2-t07-full-chain/final-frozen-source-manifest.json"
    assert sha256(freeze.read_bytes()) == MANIFEST
    files = json.loads(freeze.read_text())
    assert len(files) == 406
    rows = []
    for path, expected in sorted(files.items()):
        committed = blob_from_tree(tree_sha, path)
        working = (ROOT / path).read_bytes()
        assert committed == working and sha256(committed) == expected
        rows.append({"path": path, "manifest_sha256": expected,
                     "source_commit_blob_sha256": sha256(committed),
                     "workspace_sha256": sha256(working)})
    result = {"status": "PASS", "source_sha": SOURCE,
              "source_manifest_sha256": MANIFEST, "source_tree_sha": tree_sha,
              "source_paths": 406, "source_commit_workspace_manifest_drift": [],
              "git_commands_invoked": 0, "git_configuration_mutations": 0,
              "business_tests_run": False, "started_at_utc": start,
              "ended_at_utc": datetime.now(timezone.utc).isoformat(), "files": rows}
    target = OUT / "source-commit-byte-proof.json"
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
