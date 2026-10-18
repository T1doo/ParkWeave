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
    p.add_argument("command", choices=["migrate", "seed-synthetic", "revoke", "revoke-field", "prepare-access"])
    p.add_argument("--principal")
    p.add_argument("--field", choices=['region','employees','service_need'])
    p.add_argument("--capability", choices=['READ','WRITE'])
    p.add_argument('--config')
    p.add_argument('--apply',action='store_true')
    p.add_argument('--expected-plan-sha256')
    args = p.parse_args()
    if args.command!='prepare-access' and (args.config is not None or args.apply or args.expected_plan_sha256 is not None):
        p.error('configuration options require prepare-access')
    if args.command=='prepare-access':
        if not args.config or any(v is not None for v in (args.principal,args.field,args.capability)):
            p.error('prepare-access requires only --config and its explicit apply options')
        if args.apply!=(args.expected_plan_sha256 is not None):
            p.error('--apply and --expected-plan-sha256 must be explicit together')
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        p.error("PARKWEAVE_DSN required")
    if args.command=='prepare-access':
        from .preparation_access_configuration import ExistingPreparationAccess,load
        from .store import Conflict,Denied
        import psycopg
        try:
            configuration=load(args.config)
            manager=ExistingPreparationAccess(Store(dsn,mode=os.environ.get('PARKWEAVE_MODE','LOCAL')))
            result=manager.apply(configuration,args.expected_plan_sha256) if args.apply else manager.preview(configuration)
        except (ValueError,Conflict,Denied,psycopg.Error):
            p.exit(2,'Configuration result not confirmed; inspect a fresh dry-run before a new explicit action.\n')
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return
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
