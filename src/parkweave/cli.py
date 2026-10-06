"""Explicit setup actions, no hidden credential lookup or destructive reset."""
import argparse
import json
import os
from pathlib import Path
import secrets
from .store import Store
from .synthetic_session_file import create_synthetic_session_file


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["migrate", "seed-synthetic", "revoke", "revoke-field"])
    p.add_argument("--principal")
    p.add_argument("--field", choices=['region','employees','service_need'])
    p.add_argument("--capability", choices=['READ','WRITE'])
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
        with (create_synthetic_session_file(path) if os.name == "nt" else path.open("x")) as f:
            if os.name != "nt":os.chmod(path, 0o600)
            json.dump(identities, f)
        store.seed(identities)
        print("Synthetic sessions written to private .runtime/synthetic-sessions.json")
    else:
        if not args.principal:
            p.error("--principal required")
        if args.command=='revoke-field':
            if not args.field or not args.capability:p.error("--field and --capability required")
            store.revoke_field(args.principal,args.field,args.capability)
        else:store.revoke(args.principal)


if __name__ == "__main__":
    main()
