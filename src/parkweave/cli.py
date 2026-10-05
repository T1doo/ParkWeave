"""Explicit setup actions, no hidden credential lookup or destructive reset."""
import argparse
import json
import os
from pathlib import Path
import secrets
from .store import Store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["migrate", "seed-synthetic", "revoke"])
    p.add_argument("--principal")
    args = p.parse_args()
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        p.error("PARKWEAVE_DSN required")
    store = Store(dsn)
    if args.command == "migrate":
        store.migrate()
    elif args.command == "seed-synthetic":
        path = Path(".runtime/synthetic-sessions.json")
        if path.exists():
            p.error("session file exists; setup will not overwrite it")
        path.parent.mkdir(mode=0o700, exist_ok=True)
        identities = {i: secrets.token_urlsafe(32) for i in ("fixture-a", "fixture-b", "fixture-c")}
        # Exclusive private output, no tokens in stdout or logs.
        with path.open("x") as f:
            os.chmod(path, 0o600)
            json.dump(identities, f)
        store.seed(identities)
        print("Synthetic sessions written to private .runtime/synthetic-sessions.json")
    else:
        if not args.principal:
            p.error("--principal required")
        store.revoke(args.principal)


if __name__ == "__main__":
    main()
