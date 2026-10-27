"""Build the existing NO_MODEL synthetic catalog in a fresh owned demo setup.

Only public bindings are generated. No business record, ADOPT, approval or
receipt is inserted; the user creates those through the ordinary application.
"""
from datetime import timedelta
from hashlib import sha256
import json

from parkweave import local_synthetic_demo as demo
from parkweave.ordinary_runtime_read import catalog_hash
from parkweave.store import Store


def create(state, application_dsn, scope):
    directory = state / 'local-demo'
    directory.mkdir(mode=0o700)  # Never reuse or repair existing input files.
    with Store(application_dsn).connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        now = c.execute('SELECT clock_timestamp() t').fetchone()['t']
        database = demo.database_binding(c)
        row = c.execute('SELECT service_id,version,name,source,namespace,qualification,xmin::text row_generation '
            'FROM preparation_catalog WHERE park_id=%s AND service_id=%s AND version=1',
            (scope['park_id'], 'synthetic-material-preparation')).fetchone()
    generation = row.pop('row_generation')
    value = dict(schema_version='parkweave-local-synthetic-demo-pack/1', kind='SYNTHETIC',
        id='qinghe-fictional-park-demo', revision=1,
        validity=dict(valid_from=(now-timedelta(days=1)).isoformat(),
                      valid_until=(now+timedelta(days=7)).isoformat(), timezone='UTC'),
        park_id=scope['park_id'], org_id=scope['org_id'],
        roles={role:scope['ids'][actor] for role,actor in
               (('enterprise_operator','enterprise'),('park_specialist','specialist'),('service_executor','executor'))},
        resources={key:resource['id'] for key,resource in zip(('primary','secondary'),scope['resources'])},
        fields={slot:dict(slot=slot,input_field='demo_'+slot) for slot in ('need_summary','material_outline')},
        services=list(demo.contract.SERVICE_GOALS))
    demo.pack(value)  # Existing strict format, not a new formal-source contract.

    def write(name, value):
        path = directory / name
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2);stream.write('\n')
        return path, sha256(path.read_bytes()).hexdigest()

    pack, pack_sha = write('pack.json',value)
    cfg = dict(schema_version='parkweave-local-synthetic-demo-config/1',
        pack_path=str(pack),pack_sha256=pack_sha,database=database,
        catalog_sha256=catalog_hash(row),catalog_generation=generation)
    journal, journal_sha = write('journal.json',dict(schema_version='parkweave-local-synthetic-demo-journal/1',
        kind='SYNTHETIC',pack_sha256=pack_sha,database=database,park_id=scope['park_id'],org_id=scope['org_id'],
        catalog_sha256=cfg['catalog_sha256'],catalog_generation=generation))
    cfg.update(journal_path=str(journal),journal_sha256=journal_sha)
    config, _ = write('config.json',cfg)
    demo.configure(Store(application_dsn),demo.PROFILE,json.dumps(cfg))
    return config
