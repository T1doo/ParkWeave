"""Explicit shared-account coordinator, separate DSN; no env/token lookups.
Owner installs/configures quota.sql and grants only schema USAGE and function EXECUTE.
A reservation survives process loss. Sent/unknown work is never automatically resent.
"""
import psycopg
from psycopg.types.json import Jsonb
from .intern_adapter import ModelBoundaryError

class AccountRateLimited(ModelBoundaryError):
    def __init__(self,retry_at=None,retry_after_seconds=None,denials=1):
        self.retry_at,self.retry_after_seconds,self.denials=retry_at,retry_after_seconds,denials
        super().__init__('ACCOUNT_RATE_LIMITED_NOT_SENT')

class PersistentBudget:
    reserve_per_call=8192
    def __init__(self,dsn,*,account,product,work,kind='SYNTHETIC'):
        if kind not in ('SYNTHETIC','LIVE'):raise ModelBoundaryError('QUOTA_KIND_REQUIRED')
        self.dsn,self.account,self.product,self.work,self.kind=dsn,account,product,work,kind
    def invoke(self,sql,args):
        try:
            with psycopg.connect(self.dsn,connect_timeout=2) as c:
                return c.execute(sql,args).fetchone()[0]
        except psycopg.Error:raise ModelBoundaryError('QUOTA_DENIED') from None
    def reserve(self):
        record=self.invoke('SELECT shared_model_quota.reserve(%s,%s,%s,%s,%s)',
                           (self.product,self.account,self.work,self.reserve_per_call,self.kind))
        if record['state']!='RESERVED':raise ModelBoundaryError('PREVIOUS_ATTEMPT_NO_RESEND')
        return record
    def hold_rate(self,record):
        result=self.invoke('SELECT shared_model_quota.hold_rate(%s,%s)',(record['id'],record['generation']))
        if not result['admitted']:
            self.release(record)  # Still RESERVED: send authorization never occurred.
            raise AccountRateLimited(result.get('retry_at'),result.get('retry_after_seconds'),result.get('denials',1))
    def dispatch(self,record):
        self.hold_rate(record)
        self.invoke('SELECT shared_model_quota.transition(%s,%s,%s,%s,%s)',(record['id'],record['generation'],'DISPATCHED',None,None))
    def release(self,record):
        self.invoke('SELECT shared_model_quota.transition(%s,%s,%s,%s,%s)',(record['id'],record['generation'],'RELEASED','NOT_SENT',None))
    def finish(self,record,outcome,usage=None):
        self.invoke('SELECT shared_model_quota.transition(%s,%s,%s,%s,%s)',
                    (record['id'],record['generation'],'SETTLED' if usage is not None else 'OUTCOME_UNKNOWN',outcome,Jsonb(usage) if usage is not None else None))
