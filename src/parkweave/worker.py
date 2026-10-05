"""Independent worker; trusted local and opt-in synthetic fixture actions, never calls a model provider."""
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
