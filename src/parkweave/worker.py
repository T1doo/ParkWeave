"""Independent worker; local atomic actions only, never calls a model provider."""
import argparse
import os
import time
import uuid
from .store import Store, Conflict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    dsn = os.environ.get("PARKWEAVE_DSN")
    if not dsn:
        parser.error("PARKWEAVE_DSN required")
    store = Store(dsn)
    worker_id = str(uuid.uuid4())
    while True:
        claim = store.claim(worker_id)
        if claim:
            try:
                store.finish(claim)
            except Conflict:
                print("claim fenced or authorization changed", flush=True)
        while store.consume():
            pass
        if args.once:
            return
        time.sleep(0.25)


if __name__ == "__main__":
    main()
