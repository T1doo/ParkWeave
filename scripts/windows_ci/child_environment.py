"""Explicit phase config; app/helpers never inherit coordinator/owner credentials."""
from parkweave.process_env import minimal_environment

def application_dsn(value):
    from psycopg.conninfo import conninfo_to_dict
    info=conninfo_to_dict(value)
    if (info.get('user')!='parkweave_app' or info.get('dbname')!='parkweave' or
        info.get('host') not in ('127.0.0.1','localhost') or info.get('service') or
        info.get('hostaddr') not in (None,'127.0.0.1','::1') or info.get('options')):
        raise ValueError('CI application binding refused')
    return value

def command_environment(source,config,phase):
    if phase=='setup':
        overrides={'PARKWEAVE_OWNER_DSN':config['PARKWEAVE_OWNER_DSN'],
                   'PARKWEAVE_DSN':application_dsn(config['PARKWEAVE_DSN'])}
    elif phase in ('doctor','start','status'):
        overrides={'PARKWEAVE_DSN':application_dsn(config['PARKWEAVE_DSN'])}
    elif phase=='regression':
        overrides={'PARKWEAVE_TEST_OWNER_DSN':config['PARKWEAVE_TEST_OWNER_DSN']}
    elif phase in ('stop','file_probe','guard','browser'):overrides={}
    else:raise ValueError('unknown CI child phase')
    return minimal_environment(source,**overrides)
