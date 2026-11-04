"""Normal worker's live composition, without credential/budget provisioning.

All four approval facts come from the separately configured coordinator under
its current DB role. Missing facts refuse startup; the DB repeats the check in
the reserve and dispatch transactions, including owner revocation/expiry.
"""
from .intern_adapter import ModelBoundaryError
from .live_credentials import LiveCredentials, read_live_credentials
from .live_safety import LiveSafety
from .http_transport import InternHTTPTransport
from .quota import PersistentBudget


class LiveWorkerRuntime:
    def __init__(self,credentials):
        if type(credentials) is not LiveCredentials:raise ModelBoundaryError('LIVE_CREDENTIAL_SOURCE_REFUSED')
        self.credentials=credentials
        self.transport=InternHTTPTransport()

    def safety(self):
        c=self.credentials
        facts=PersistentBudget(c.quota_dsn.get_secret_value(),account=c.account,
            product='parkweave',work='startup',kind='LIVE').invoke(
                'SELECT shared_model_quota.live_worker_status(%s,%s,%s)',
                ('parkweave',c.account,c.coordinator_id))
        keys={'budget_authorized','injection_authorized','rate_verified','shared_binding_verified'}
        if type(facts) is not dict or set(facts)!=keys or any(type(v) is not bool for v in facts.values()):
            raise ModelBoundaryError('LIVE_SAFETY_BLOCKED')
        # Presence derives from the successfully decoded protected source;
        # no caller bool, environment flag or fake approval is substituted.
        result=LiveSafety(enabled=True,**facts,
            token_name_present=bool(c.token.get_secret_value().strip()),
            coordinator_names_present=bool(c.account and c.quota_dsn.get_secret_value() and c.coordinator_id))
        result.require()
        return result

    def chain(self,store):
        from .model_chain import ModelChain
        c=self.credentials
        self.safety()  # Before claiming any user work, even with --once.
        return ModelChain(store,quota_dsn=c.quota_dsn.get_secret_value(),account=c.account,
            transport=self.transport,token=c.token,kind='LIVE',live_runtime=self)


def configured_chain(store,config_fd=None):
    import os
    if any(name.upper().startswith('PG') for name in os.environ):
        raise ModelBoundaryError('LIVE_AMBIENT_CONFIG_REFUSED')
    return LiveWorkerRuntime(read_live_credentials(config_fd)).chain(store)
