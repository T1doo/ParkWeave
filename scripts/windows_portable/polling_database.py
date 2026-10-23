"""Nonblocking libpq startup probe; one absolute deadline, owned socket finish.

No cancel request, synchronous connection context/COMMIT, worker thread or retry.
Only the frozen read-only catalogue SELECT is sent. No database is created.
"""
import selectors
import time

from parkweave import runtime_readiness as runtime
from .controller import CandidateRefused


class DatabaseProbeFailure(CandidateRefused):
    def __init__(self,phase,*,cleanup_confirmed=False):
        self.phase,self.outcome,self.cleanup_confirmed=phase,'UNKNOWN',cleanup_confirmed
        super().__init__('DATABASE_PROBE_UNKNOWN:'+phase)


def _remaining(deadline):
    left=deadline-time.monotonic()
    if left<=0:raise DatabaseProbeFailure('DEADLINE')
    return left


def _wait(connection,events,deadline):
    with selectors.DefaultSelector() as selector:
        selector.register(connection.socket,events)
        if not selector.select(_remaining(deadline)):raise DatabaseProbeFailure('DEADLINE')
    _remaining(deadline)


def _row(result):
    names=[result.fname(i).decode('ascii') for i in range(result.nfields)]
    if result.ntuples!=1 or names!=['name','role','login','oid','address','port','postmaster','schema','safe']:
        raise DatabaseProbeFailure('ROW_SHAPE')
    values=[result.get_value(0,i) for i in range(result.nfields)]
    if any(value is None or len(value)>256 for value in values):raise DatabaseProbeFailure('ROW_VALUE')
    decoded={name:value.decode('utf-8') for name,value in zip(names,values)}
    for name in ('oid','port','schema'):
        if not decoded[name].isascii() or not decoded[name].isdigit():raise DatabaseProbeFailure('ROW_NUMBER')
        decoded[name]=int(decoded[name])
    if decoded['safe'] not in ('t','f'):raise DatabaseProbeFailure('ROW_BOOLEAN')
    decoded['safe']=decoded['safe']=='t'
    return runtime.validate_database(decoded,'LOCAL')


def probe(inputs,deadline):
    from psycopg import pq
    from psycopg.conninfo import make_conninfo
    from parkweave.installed_fixture_receipt import _dsn,refuse_inherited_configuration
    import os
    refuse_inherited_configuration()
    parsed=_dsn(inputs.application_dsn,'parkweave')
    if parsed['host']!='127.0.0.1' or parsed['user']!='parkweave_app':raise CandidateRefused('explicit IPv4 database required')
    options={**parsed,'hostaddr':'127.0.0.1','password':parsed.get('password',''),'passfile':os.devnull,
             'sslmode':'disable','gssencmode':'disable','require_auth':'none,password,md5,scram-sha-256',
             'options':'-c default_transaction_read_only=on','connect_timeout':'2'}
    connection=None;primary=None;result=None
    try:
        _remaining(deadline)
        connection=pq.PGconn.connect_start(make_conninfo(**options).encode('utf-8'))
        while True:
            _remaining(deadline)
            status=connection.connect_poll()
            if status==pq.PollingStatus.OK:break
            if status==pq.PollingStatus.READING:_wait(connection,selectors.EVENT_READ,deadline)
            elif status==pq.PollingStatus.WRITING:_wait(connection,selectors.EVENT_WRITE,deadline)
            else:raise DatabaseProbeFailure('CONNECT')
        connection.nonblocking=1
        # A single SELECT; default_transaction_read_only was set at connection.
        # No transaction manager, cancellation roundtrip or COMMIT can extend it.
        connection.send_query(runtime.DATABASE_SQL.encode('ascii'))
        while True:
            _remaining(deadline)
            flushed=connection.flush()
            if flushed==0:break
            if flushed!=1:raise DatabaseProbeFailure('FLUSH')
            _wait(connection,selectors.EVENT_READ|selectors.EVENT_WRITE,deadline)
            connection.consume_input()
        while True:
            while connection.is_busy():
                _wait(connection,selectors.EVENT_READ,deadline)
                connection.consume_input()
            _remaining(deadline)
            item=connection.get_result()
            if item is None:break
            if item.status!=pq.ExecStatus.TUPLES_OK or result is not None:raise DatabaseProbeFailure('QUERY')
            result=_row(item)
        if result is None or result['port']!=int(parsed['port']):raise DatabaseProbeFailure('DATABASE_BINDING')
        _remaining(deadline)
    except BaseException as error:
        primary=error
    finally:
        if connection is not None:
            try:
                connection.finish()  # Close our nonblocking socket, no server acknowledgement.
                if connection.status!=pq.ConnStatus.BAD:raise DatabaseProbeFailure('FINISH_UNKNOWN')
            except BaseException as cleanup:
                failure=DatabaseProbeFailure('FINISH_UNKNOWN')
                failure.owned_connection=connection  # Keep the original cleanup capability; never guess fd.
                raise BaseExceptionGroup('DATABASE_PROBE_AND_CLOSE_UNKNOWN',([primary] if primary else [])+[cleanup,failure]) from primary
    if primary is not None:
        if isinstance(primary,DatabaseProbeFailure):primary.cleanup_confirmed=True
        raise primary
    _remaining(deadline)
    return result
