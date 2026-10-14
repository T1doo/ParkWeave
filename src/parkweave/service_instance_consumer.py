"""Explicit cold-input preparation for a trusted park instance.

This facade admits immutable inputs and prepares original product commands. It
never sends those commands, resumes an unknown send, adopts a plan, or copies a
source Case. Each product command requires a separate explicit user submission.
"""
import json
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import preparation as prep, request_intents as intents, controlled_plans as cp
from . import service_capability_contract as contract
from .domain import Intake
from .store import Conflict, Denied, digest
from .template_consumer import ConsumerRepository, Material, canonical, normal
from .service_capability_catalog import IsolatedServiceCapabilityCatalog, fold, proof, row, lock
from .planning_constraints import Constraints


class ColdInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    instance_id: str = Field(min_length=1, max_length=100)
    expected_config_revision: int = Field(ge=1, le=64)
    expected_config_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    expected_release_id: str = Field(min_length=1, max_length=100)
    expected_release_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    goal: str = Field(min_length=1, max_length=2000)
    required_goals: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(min_length=1, max_length=8)
    fields: dict[str, Material] = Field(min_length=2, max_length=2)
    reason: str = Field(min_length=1, max_length=1000)
    planning_constraints: Constraints = Field(default_factory=Constraints)

    @model_validator(mode='after')
    def complete(self):
        if len(self.required_goals) != len(set(self.required_goals)):
            raise ValueError('explicit distinct mandatory goals required')
        if {material.slot for material in self.fields.values()} != set(prep.SLOTS):
            raise ValueError('both original slots require new explicit material text')
        if len(set(self.required_goals + self.planning_constraints.additional_requirements)) > 8:
            raise ValueError('all goals and conditions must fit the original request contract')
        return self


class ParkInstanceConsumer:
    """Default disabled, owned fixture only; no product write capability."""
    def __init__(self, catalog, repository, *, enabled_for_isolated_tests=False):
        if enabled_for_isolated_tests is not True or type(catalog) is not IsolatedServiceCapabilityCatalog:
            raise Denied('isolated park instance cold input disabled')
        if type(repository) is not ConsumerRepository or repository.path == catalog.consumer.repository.path:
            raise Denied('separate exact isolated cold-input journal required')
        self.catalog = catalog
        self.consumer = catalog.consumer
        self.store = self.consumer.store
        self.repository = repository
        self.consumer.validate_fixture()

    def _auth(self, token, c, *, write=False):
        p = self.store.auth(c, token, lock=True)
        self.store.check_capability(c, p, 'READ')
        if p['role'] != 'enterprise_operator' or (p['park_id'], p['org_id']) not in self.catalog.orgs:
            raise Denied('current approved enterprise owner required')
        if write:
            prep.grant(self.store, c, p, 'PREPARE')
            self.store.check_capability(c, p, 'EXECUTE')
            if not c.execute("SELECT 1 FROM action_grants WHERE principal_id=%s AND park_id=%s AND org_id=%s AND action='case.create' AND active", (p['id'], p['park_id'], p['org_id'])).fetchone():
                raise Denied('current original Case creation grant required')
        return p

    def configurations(self, token):
        """Discover current own configurations without a Case or a write lease.

        The bounded result contains input names, never existing input values or
        mapped principal/resource identifiers. Admission rechecks this metadata
        and original authority under the original prepare transaction.
        """
        self.consumer.validate_fixture()
        with self.catalog.read_connection() as c:
            p = self._auth(token, c, write=True)
            lock(c, p['park_id'])
            value = row(c, p['park_id'])
            _, instances = fold(proof(value))
            available = []
            has_unknown_sources = False
            for record in sorted(instances.values(), key=lambda item: item['instance']['instance_id']):
                instance = record['instance']
                if record['state'] != 'ACTIVE' or instance['roles']['enterprise_operator'] != p['id']:
                    continue
                try:
                    release = self.catalog._current_release(self.catalog._release_record(c, value, instance['release_id']))
                    instance = contract.validate_instance(instance, release, now=self.catalog.engine.clock())
                    parent = dict(park_id=p['park_id'], org_id=p['org_id'], owner_id=p['id'], reviewer_id=instance['roles']['park_specialist'])
                    self.catalog.mapping_states(c, instance, parent)
                except (ValueError, Conflict, Denied):
                    has_unknown_sources = True
                    continue
                available.append(dict(instance_id=instance['instance_id'], config_revision=instance['config_revision'],
                    config_sha256=instance['config_sha256'], release_id=release['release_id'],
                    release_revision=release['revision'], release_sha256=release['release_sha256'],
                    service_id=release['service_id'], title=release['title'], supported_goals=release['supported_goals'],
                    fields={slot: mapping['input_field'] for slot, mapping in instance['fields'].items()}))
                if len(available) > 16:
                    raise Conflict('bounded current instance directory exceeded')
            return dict(scope='SYNTHETIC_PARK_INSTANCE_COLD_INPUT_DIRECTORY', actor_ref=cp._hash(dict(actor_id=p['id'])),
                park_id=p['park_id'], read_only=True, automatically_replayed=False, provider_enabled=False,
                execution_enabled=False, new_grants=False, automatic_adoption=False, instances=available,
                allowed_goals=sorted({goal for instance in available for goal in instance['supported_goals']}),
                has_unknown_sources=has_unknown_sources)

    def _current(self, c, p, data):
        _, instances = fold(proof(row(c, p['park_id'])))
        record = instances.get(data.instance_id)
        if not record or record['state'] != 'ACTIVE':
            raise Conflict('current exact park instance unavailable')
        instance = record['instance']
        if (instance['config_revision'], instance['config_sha256'], instance['release_id'], instance['release_sha256']) != (data.expected_config_revision, data.expected_config_sha256, data.expected_release_id, data.expected_release_sha256):
            raise Conflict('exact cold-input instance binding changed')
        parent = dict(park_id=p['park_id'], org_id=p['org_id'], owner_id=p['id'], reviewer_id=instance['roles']['park_specialist'])
        snapshot = self.catalog.snapshot(c, parent)
        if instance not in snapshot['instances']:
            raise Denied('current reviewed instance or mapped authority unavailable')
        expected = {mapping['input_field']: slot for slot, mapping in instance['fields'].items()}
        if set(data.fields) != set(expected) or any(data.fields[field].slot != slot for field, slot in expected.items()):
            raise Conflict('exact external field names and original slot meanings required')
        return instance, snapshot

    def prepare(self, token, key, data):
        self.consumer._key(key)
        database = self.consumer.validate_fixture()
        with self.catalog.connection() as c:
            p = self._auth(token, c, write=True)
            instance, snapshot = self._current(c, p, data)
            body = data.model_dump(mode='json')
            fp = digest(canonical(dict(action='PARK_INSTANCE_COLD_INPUT', body=body)))
            with self.repository.connect(write=True) as journal:
                old = journal.execute('SELECT * FROM consumer_requests WHERE actor=? AND key=?', (p['id'], key)).fetchone()
                if old:
                    if old['fp'] != fp:
                        raise Conflict('cold-input original key fingerprint changed')
                    id = old['instance_id']
                else:
                    id = str(uuid4())
                    binding = dict(kind='PARK_INSTANCE_COLD_INPUT_V1', instance=instance, catalog_sha256=snapshot['sha256'])
                    journal.execute('INSERT INTO consumer_instances VALUES(?,?,?,?,?,?,?,?)', (id, p['id'], p['park_id'], p['org_id'], database, canonical(binding), canonical(body), 'COMMANDS_REQUIRE_EXPLICIT_SUBMISSION'))
                    journal.execute('INSERT INTO consumer_requests VALUES(?,?,?,?)', (p['id'], key, fp, id))
                    run_body = Intake(goal=data.goal).snapshot()
                    journal.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)', (id, 'CREATE_RUN', self.consumer._stage_key(id, 'CREATE_RUN'), digest(canonical(run_body)), canonical(run_body), 'ADMITTED'))
        return self.read(token, key)

    def _saved(self, journal, p, key, database):
        saved = journal.execute('SELECT i.* FROM consumer_requests r JOIN consumer_instances i ON i.id=r.instance_id WHERE r.actor=? AND r.key=? AND i.actor=? AND i.park=? AND i.org=? AND i.database_name=?', (p['id'], key, p['id'], p['park_id'], p['org_id'], database)).fetchone()
        if saved is None:
            raise Denied('own cold-input original key unavailable')
        return dict(saved)

    def read(self, token, key):
        self.consumer._key(key)
        database = self.consumer.validate_fixture()
        with self.store.connect() as c:
            p = self._auth(token, c)
            with self.repository.connect() as journal:
                saved = self._saved(journal, p, key, database)
                stages = [dict(stage) for stage in journal.execute('SELECT name,request_key,body_sha256,body,state FROM consumer_stages WHERE instance_id=? ORDER BY rowid', (saved['id'],)).fetchall()]
            observations = self._observations(c, p, saved, stages)
            try:
                self._current(c, p, ColdInput.model_validate(json.loads(saved['input'])))
                available = True
            except (Denied, Conflict, ValueError):
                available = False
        return dict(scope='SYNTHETIC_PARK_INSTANCE_COLD_INPUT', actor_ref=cp._hash(dict(actor_id=p['id'])),
                    request_key=key, park_id=p['park_id'], read_only=True, automatically_replayed=False,
                    provider_enabled=False, execution_enabled=False, cold_input_id=saved['id'], binding=json.loads(saved['binding']), input=json.loads(saved['input']), current_available=available,
                    stages=[dict(stage, body=json.loads(stage['body'])) for stage in stages],
                    product_observations=observations, automatic_execution=False, automatic_adoption=False, new_grants=False,
                    business_publication=False, case_goal_completed=False)

    def _observations(self, c, p, saved, stages):
        """Read original keys only. Absence never proves a delayed send impossible."""
        results = []
        run = c.execute('SELECT * FROM runs WHERE principal_id=%s AND request_key=%s', (p['id'], self.consumer._stage_key(saved['id'], 'CREATE_RUN'))).fetchone()
        parent = None
        if run:
            if (run['park_id'], run['org_id'], run['namespace']) != (p['park_id'], p['org_id'], 'SYNTHETIC'):
                raise Conflict('original cold-input Run scope changed')
            parent = c.execute('SELECT * FROM preparations WHERE run_id=%s AND owner_id=%s', (run['id'], p['id'])).fetchone()
            if parent:
                prep.scoped(self.store, c, p, parent['id'])
        for stage in stages:
            body = json.loads(stage['body'])
            if digest(stage['body']) != stage['body_sha256']:
                raise Conflict('immutable original stage body corrupted')
            result = None
            if stage['name'] == 'CREATE_RUN':
                expected = digest(json.dumps(Intake.model_validate(body).snapshot(), sort_keys=True, ensure_ascii=False))
                if run and run['fingerprint'] != expected:
                    raise Conflict('original cold-input Run fingerprint changed')
                if run:
                    result = dict(run_id=str(run['id']), run_state=run['state'], case_id=str(run['case_id']) if run.get('case_id') else None)
            elif parent:
                if stage['name'] == 'CREATE_PREPARATION':
                    expected = digest(prep.canonical(prep.CreatePreparation.model_validate(body).model_dump(mode='json')))
                elif stage['name'] == 'SAVE_REQUEST':
                    expected = digest(prep.canonical(dict(preparation_id=str(parent['id']), action='UPDATE_REQUEST', **intents.Save.model_validate(body).model_dump(exclude_none=True))))
                else:
                    command = prep.PreparationCommand.model_validate(body)
                    command_body = command.model_dump(mode='json', exclude={'correction_slots'} if command.correction_slots is None else set())
                    expected = digest(prep.canonical(dict(preparation_id=str(parent['id']), **command_body)))
                result = prep.replay(c, p, stage['request_key'], expected, parent['id'])
            results.append(dict(name=stage['name'], request_key=stage['request_key'], status='COMMITTED' if result else 'NOT_OBSERVED', result=result, automatically_replayed=False, not_committed_final=False))
        return results

    def prepare_stage(self, token, key, stage):
        """Prepare one original command after observing its actual dependencies.

        ADMITTED is an immutable command description, never a claim of send or
        completion. A lost reply is inspected through the original product key.
        """
        if stage not in ('CREATE_PREPARATION', 'SAVE_REQUEST', 'ADD_need_summary', 'ADD_material_outline'):
            raise Conflict('registered cold-input stage required')
        database = self.consumer.validate_fixture()
        with self.catalog.connection() as c:
            p = self._auth(token, c, write=True)
            with self.repository.connect(write=True) as journal:
                saved = self._saved(journal, p, key, database)
                data = ColdInput.model_validate(json.loads(saved['input']))
                instance, _ = self._current(c, p, data)
                run_key = self.consumer._stage_key(saved['id'], 'CREATE_RUN')
                run = c.execute('SELECT * FROM runs WHERE principal_id=%s AND request_key=%s', (p['id'], run_key)).fetchone()
                if not run or run['state'] != 'SUCCEEDED' or run['namespace'] != 'SYNTHETIC' or normal(run['input']) != Intake(goal=data.goal).snapshot():
                    raise Conflict('original exact newly submitted successful Case run required')
                if stage == 'CREATE_PREPARATION':
                    body = dict(run_id=str(run['id']), service_id=prep.SERVICE, service_version=1, reviewer_id=instance['roles']['park_specialist'])
                else:
                    parent = c.execute('SELECT * FROM preparations WHERE run_id=%s AND owner_id=%s', (run['id'], p['id'])).fetchone()
                    if not parent or parent['reviewer_id'] != instance['roles']['park_specialist']:
                        raise Conflict('original new preparation dependency required')
                    # Reuse the original scoped business guard, including cancelled Cases.
                    parent = prep.scoped(self.store, c, p, parent['id'], write=True, business_write=True)
                    if stage == 'SAVE_REQUEST':
                        body = dict(expected_preparation_revision=parent['revision'], request_text=data.goal, required_goals=data.required_goals, planning_constraints=data.planning_constraints.model_dump())
                    else:
                        slot = stage[4:]
                        material = next(material for material in data.fields.values() if material.slot == slot)
                        body = dict(action='ADD_EVIDENCE', expected_revision=parent['revision'], **material.model_dump())
                old = journal.execute('SELECT * FROM consumer_stages WHERE instance_id=? AND name=?', (saved['id'], stage)).fetchone()
                if old is None:
                    journal.execute('INSERT INTO consumer_stages VALUES(?,?,?,?,?,?,NULL,NULL)', (saved['id'], stage, self.consumer._stage_key(saved['id'], stage), digest(canonical(body)), canonical(body), 'ADMITTED'))
                elif digest(old['body']) != old['body_sha256']:
                    raise Conflict('immutable original stage body corrupted')
        return self.read(token, key)
