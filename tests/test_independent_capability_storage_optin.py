"""Explicit capability storage cannot change ordinary schema32 startup authority."""
from uuid import uuid4
import pytest
import psycopg
from psycopg.conninfo import conninfo_to_dict
from parkweave.store import Store,Denied,Conflict
from parkweave.template_candidate import TemplateEngine,TemplateRepository
from parkweave.template_consumer import TemplateConsumer,ConsumerConfig,ConsumerRepository
from parkweave.service_capability_catalog import IsolatedServiceCapabilityCatalog
from test_preparation import preparation_fixture,create
from test_template_candidate import template_config
from test_service_capability_catalog_actual import capability_catalog,register,material_instance,snapshot


def state(owner):
    with owner.connect() as c:
        columns=c.execute("SELECT attname,format_type(atttypid,atttypmod) type FROM pg_attribute WHERE attrelid='preparation_catalog'::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum").fetchall()
        result=dict(versions=c.execute('SELECT version FROM schema_version ORDER BY version').fetchall(),columns=columns,
            functions=c.execute("SELECT oid,proname,prosrc,proconfig,prosecdef FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname LIKE 'service_capability_%' ORDER BY proname").fetchall(),
            triggers=c.execute("SELECT tgname,tgfoid,tgenabled,tgtype,tgattr::text attrs FROM pg_trigger WHERE tgrelid='preparation_catalog'::regclass AND tgname LIKE 'service_capability_%' ORDER BY tgname").fetchall())
        if any(x['attname']=='service_capability_catalog' for x in columns):
            result['journals']=c.execute('SELECT park_id,service_id,version,service_capability_catalog FROM preparation_catalog ORDER BY park_id,service_id,version').fetchall()
        return result


def test_ordinary_owned_startup_stays32_without_capability_column(preparation_fixture):
    owner=preparation_fixture[1];before=state(owner)
    assert before['versions'][-1]['version']==32
    assert not any(x['attname']=='service_capability_catalog' for x in before['columns'])
    owner.migrate();owner.migrate()
    assert state(owner)==before


def test_capability_constructor_on32_refuses_without_implicit_ddl(preparation_fixture,tmp_path):
    app,owner,_,_=preparation_fixture
    engine=TemplateEngine(template_config(),TemplateRepository(tmp_path/'optin.template.candidate.sqlite3'))
    consumer=TemplateConsumer(app,engine,ConsumerConfig(enabled_for_isolated_tests=True,allowed_database_names=[conninfo_to_dict(app.dsn)['dbname']],allowed_orgs=[dict(park_id='park-a',org_id='org-a')]),ConsumerRepository(tmp_path/'optin.consumer.candidate.sqlite3'))
    before=state(owner)
    with pytest.raises(Denied,match='immutable capability schema'):
        IsolatedServiceCapabilityCatalog(consumer,owner,enabled_for_isolated_tests=True)
    assert state(owner)==before


@pytest.mark.parametrize('kind',['owner-without-receipt','app-without-receipt','native-marker','app-with-issued-linux-receipt'])
def test_explicit_capability_install_rejects_unissued_or_wrong_authority(preparation_fixture,kind):
    app,owner,_,_=preparation_fixture
    subject=Store(app.dsn if kind.startswith('app-') else owner.dsn)
    if kind=='native-marker':
        from parkweave.installed_fixture_receipt import NativeDatabaseCreationEvidence
        subject._case_fact_fixture_receipt=object.__new__(NativeDatabaseCreationEvidence)
    elif kind=='app-with-issued-linux-receipt':subject._case_fact_fixture_receipt=owner._case_fact_fixture_receipt
    before=state(owner)
    with pytest.raises((Denied,psycopg.Error)):
        subject.migrate_service_capability_fixture()
    assert state(owner)==before


def test_future_schema_refuses_explicit_extension_without_partial_install(preparation_fixture):
    owner=preparation_fixture[1]
    with owner.connect() as c:c.execute('INSERT INTO schema_version VALUES(34)')
    before=state(owner)
    with pytest.raises(psycopg.Error):owner.migrate_service_capability_fixture()
    assert state(owner)==before and not before['functions']


def test_retained_explicit33_repair_keeps_original_journal_and_plain_migrate_rejects(capability_catalog):
    a=capability_catalog;owner=a['f'][1];release=register(a)['release']
    a['catalog'].bind_instance('park-a',uuid4().hex,material_instance(release))
    before=state(owner)
    assert before['versions'][-1]['version']==33
    owner.migrate_service_capability_fixture();owner.migrate_service_capability_fixture()
    assert state(owner)==before
    with owner.connect() as c:c.execute('DELETE FROM schema_version WHERE version=33')
    owner.migrate_service_capability_fixture()
    assert state(owner)==before
    with pytest.raises(Conflict,match='newer'):owner.migrate()
    assert state(owner)==before


def test_new_store_cold_capability_read_requires_no_startup_migration(capability_catalog):
    a=capability_catalog;release=register(a)['release'];a['catalog'].bind_instance('park-a',uuid4().hex,material_instance(release));p,_,_=create(a['f'])
    first=snapshot(a,p);before=state(a['f'][1]);app=Store(a['f'][0].dsn)
    consumer=TemplateConsumer(app,a['engine'],a['consumer'].config,a['consumer'].repository)
    cold=IsolatedServiceCapabilityCatalog(consumer,a['f'][1],enabled_for_isolated_tests=True)
    with app.connect() as c:
        parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
        assert cold.snapshot(c,parent)==first
    assert state(a['f'][1])==before
