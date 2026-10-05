"""Independent heartbeat connection/thread, never holds a DB lock during model wait."""
import threading
from .store import Conflict


class LeaseKeeper:
    def __init__(self, store, claim, lease_seconds):
        self.store,self.claim,self.seconds=store,claim,lease_seconds
        self.stop=threading.Event()
        self.lost=threading.Event()
        self.thread=threading.Thread(target=self.maintain,daemon=True)

    def maintain(self):
        while not self.stop.wait(min(self.seconds/3,5)):
            try:
                if not self.store.heartbeat(self.claim,self.seconds):
                    self.lost.set();return
            except Exception:
                # No exception text/DSN/input is logged. Failure closes dispatch authority.
                self.lost.set();return

    def __enter__(self):
        self.thread.start();return self

    def __exit__(self,*args):
        self.stop.set();self.thread.join(timeout=3)
