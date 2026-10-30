"""Concrete private trial composition from the verified source grant only."""
from hashlib import sha256
import json
from pathlib import Path
import secrets
import time

from scripts.windows_portable import native_trial_authority as a

_retained = []


class NativeBusinessScope:
    def __init__(self, verified_source):
        self.cap = a.activate(verified_source)
        self.storage = self.adapter = None
        self.started = self.closed = False

    def run(self, *, consume=lambda observation: None):
        value = a.state(self.cap)
        a.need(not self.started); self.started = True
        # Imports/constructors with real OS actions are below source admission.
        from .native_acceptance_storage import OwnedNativeObjects
        from scripts.windows_portable.endpoint_plan import PlanMode
        from scripts.windows_portable.entry import native_invocation
        from scripts.windows_portable.native_business_adapter import NativeBusinessTestAdapter
        from scripts.windows_portable.native_web_login import NativeLoginEnrollment, ACCOUNTS
        runner_temp=dict(value.context[0])['RUNNER_TEMP']
        name = 'parkweave-native-acceptance-'+sha256(json.dumps(value.key).encode()).hexdigest()[:24]
        self.storage = object.__new__(OwnedNativeObjects)
        OwnedNativeObjects.__init__(self.storage,runner_temp,value.deadline,name)
        self.storage.verify(self.storage.root)
        value.parent_binding=(tuple(self.storage.root.identity),self.storage.root.descriptor,self.storage.root.path)
        value.parent = Path(runner_temp)/name
        value.root = str(value.parent/'trial-instance')
        # Each role has separate temporary input, never a test dictionary as
        # the session supplier: native provider/DPAPI still creates all tokens.
        enrollment = NativeLoginEnrollment({account:secrets.token_urlsafe(32) for account in ACCOUNTS})
        first = native_invocation(value.payload,value.manifest,Path(value.root),PlanMode.NEW,
            manifest_raw=value.manifest_raw,database_port=55431,api_port=58761,enrollment=enrollment)
        second = native_invocation(value.payload,value.manifest,Path(value.root),PlanMode.REOPEN,
            manifest_raw=value.manifest_raw)
        a.bind_compositions(self.cap,first,second,enrollment)
        self.adapter = NativeBusinessTestAdapter(first,second,value.root,
            business_seconds=min(180,value.deadline-time.monotonic()))
        observed=()
        def collect(proof):
            nonlocal observed
            from scripts.windows_portable import native_acceptance_issuer as issuer
            end=min(self.adapter.trial.deadline,value.deadline,time.monotonic()+20)
            observations=(issuer.observe_business_restart(proof,second,end),)+issuer.collect_trial_facts(second,end)
            observed=issuer.observed_requirements(second,observations,end)
            consume(proof)
        result=self.adapter.run(consume=collect)
        from scripts.windows_portable.native_acceptance_contract import coverage
        result.update(observations=list(observed),coverage=coverage(observed))
        return result

    def close(self, *, failed=False):
        if self.closed:return
        self.closed=True
        _retained.append(self)  # Before any fallible context/deadline validation.
        if failed:
            a.fail(self.cap)
        s=self.storage
        try:
            value=a.state(self.cap,cleanup=True)
            if s is not None:
                # The complete trial subtree and persistent marker are retained
                # for runner disposal, never recursively deleted or adopted.
                a.need(not s.failed and not getattr(s.api.readonly,'_nt_create_pending',False))
                a.need(all(not lease.active for lease in value.generations))
                if s.root is not None:
                    a.state(self.cap,cleanup=True)
                    s.deadline=value.cleanup_end;s.verify(s.root);s.close_node(s.root)
                while s.ancestors:
                    a.state(self.cap,cleanup=True)
                    h=s.ancestors.pop();s.ancestor_closes.append(h);s.api.close(h)
                s.closed=True
            value.source_pins.close(value.cleanup_end)
            a.finish(self.cap)
        except BaseException:
            a.fail(self.cap)
            raise
        if not failed and self in _retained:_retained.remove(self)
