"""Independent worker; trusted local and opt-in synthetic fixture actions, explicit offline planning; live activation remains disabled."""
import argparse
import os
import time
import uuid
from .store import Store, Conflict
from .gateway import ExecutionGateway, InjectedCrash
from .lease import LeaseKeeper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--fault-stage", choices=["after-dispatch", "after-effect"])
    parser.add_argument("--lease-seconds", type=int, default=30)
    parser.add_argument("--mock-model-wait-seconds", type=float, default=0)
    parser.add_argument("--model-fixture", choices=['good','wrong-model','bad-args','truncated','secret-echo','timeout','feedback-error'])
    args = parser.parse_args()
    if not 0<=args.mock_model_wait_seconds<=10:parser.error("mock wait must be 0..10 seconds")
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        parser.error("PARKWEAVE_DSN required")
    store = Store(dsn, mode=os.environ.get("PARKWEAVE_MODE", "LOCAL"))
    if args.fault_stage and store.mode != "FAULT_INJECTION":
        parser.error("fault-stage requires explicit FAULT_INJECTION mode")
    gateway = ExecutionGateway(store)
    worker_id = str(uuid.uuid4())
    while True:
        claim = store.claim(worker_id, args.lease_seconds)
        if claim:
            try:
                with LeaseKeeper(store,claim,args.lease_seconds) as keeper:
                    if args.mock_model_wait_seconds and keeper.lost.wait(args.mock_model_wait_seconds):
                        raise Conflict("lease lost during MODEL_MOCK wait")
                    if keeper.lost.is_set():raise Conflict("lease lost")
                    with store.connect() as c:
                        model_started=c.execute('SELECT 1 FROM model_steps WHERE run_id=%s',(claim['id'],)).fetchone()
                    if model_started and not args.model_fixture:
                        from .model_chain import fail_model_run
                        with store.connect() as c:
                            known=c.execute("SELECT state FROM operations WHERE run_id=%s",(claim['id'],)).fetchone()
                        fail_model_run(store,claim,'FEEDBACK' if known['state']=='VERIFIED' else 'PLAN','MODEL_CHAIN_RUNTIME_REQUIRED')
                    elif args.model_fixture:
                        from .model_chain import ModelChain,synthetic_transport,FAKE_TOKEN
                        from pydantic import SecretStr
                        # Explicit offline mode: owner must provision SYNTHETIC coordinator budget.
                        ModelChain(store,quota_dsn=store.dsn,account='synthetic-shared-account',
                                   transport=synthetic_transport(args.model_fixture),token=SecretStr(FAKE_TOKEN)).execute(claim)
                    else:
                        gateway.execute(claim, crash_at=args.fault_stage)
            except InjectedCrash as exc:
                print(str(exc), flush=True)
                raise SystemExit(75)
            except Conflict:
                print("claim fenced or authorization changed", flush=True)
        while store.consume():
            pass
        if args.once:
            return
        time.sleep(0.25)


if __name__ == "__main__":
    main()
