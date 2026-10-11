"""Read source objects with authorized read-only git cat-file; no mutation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCE = "b5ea90ac9b366b015b43c426ad94b72faf7c8b72"
MANIFEST = "fc3abe9a5f7854d05bdc4913df74b642944c6a575dee930ea7eef99227c723bf"
sha256 = lambda b: hashlib.sha256(b).hexdigest()


def main():
    start = datetime.now(timezone.utc).isoformat()
    head = (ROOT / ".git/HEAD").read_text().strip()
    assert head.startswith("ref: ")
    assert (ROOT / ".git" / head[5:]).read_text().strip() == SOURCE
    freeze = ROOT / ".runtime/f2-t07-full-chain/final-frozen-source-manifest.json"
    assert sha256(freeze.read_bytes()) == MANIFEST
    files = json.loads(freeze.read_text())
    assert len(files) == 406
    ordered_paths = sorted(files)
    requests = [SOURCE] + [SOURCE + ":" + path for path in ordered_paths]
    stdin = ("\n".join(requests) + "\n").encode()
    argv = ["git", "cat-file", "--batch"]
    process = subprocess.run(argv, input=stdin, cwd=ROOT, capture_output=True)
    assert process.returncode == 0, process.stderr.decode()
    stream = process.stdout
    cursor = 0
    rows = []
    tree_sha = None
    for index, request in enumerate(requests):
        end = stream.index(b"\n", cursor)
        object_sha, kind, size = stream[cursor:end].split(b" ")
        size = int(size)
        payload = stream[end + 1:end + 1 + size]
        assert len(payload) == size and stream[end + 1 + size:end + 2 + size] == b"\n"
        assert hashlib.sha1(kind + b" " + str(size).encode() + b"\0" + payload).hexdigest() == object_sha.decode()
        cursor = end + 2 + size
        if index == 0:
            assert object_sha.decode() == SOURCE and kind == b"commit"
            tree_sha = payload.split(b"\n", 1)[0].decode().removeprefix("tree ")
        else:
            path = ordered_paths[index - 1]
            working = (ROOT / path).read_bytes()
            assert kind == b"blob" and payload == working and sha256(payload) == files[path]
            rows.append({"path": path, "manifest_sha256": files[path],
                         "source_commit_blob_sha256": sha256(payload),
                         "workspace_sha256": sha256(working)})
    assert cursor == len(stream)
    result = {"status": "PASS", "source_sha": SOURCE,
              "source_manifest_sha256": MANIFEST, "source_tree_sha": tree_sha,
              "source_paths": 406, "source_commit_workspace_manifest_drift": [],
              "git_read_only_argv": argv, "git_process_exit": process.returncode,
              "git_stderr": process.stderr.decode(), "git_mutations": 0,
              "batch_request_manifest": str(freeze.relative_to(ROOT)),
              "batch_stdin_sha256": sha256(stdin), "business_tests_run": False,
              "started_at_utc": start, "ended_at_utc": datetime.now(timezone.utc).isoformat(),
              "files": rows}
    target = OUT / "source-commit-byte-proof-corrected.json"
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
