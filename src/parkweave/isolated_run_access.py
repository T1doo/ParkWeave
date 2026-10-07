"""Explicit fresh-owned-fixture bridge for ENG089 exact Run READ decisions.

The unchanged SQLite engine is the approval/audit authority. PG is a projection,
not a distributed transaction: a committed SQLite decision with a failed PG
projection grants nothing. Every managed use needs both current stores. No
production migration/GRANT, credential/persona creation, or default activation.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from threading import RLock
from uuid import UUID

from psycopg.errors import LockNotAvailable
from psycopg.types.json import Jsonb

from . import case_fact_clarifications as facts
from . import run_access_candidate as candidate
from .domain import SourceRef, Validity
from .store import Conflict, Denied

NAMESPACE = 'ISOLATED_SYNTHETIC_RUN_ACCESS_PG_PROJECTION_V1'


class ProjectionPending(Conflict):
    decision_committed = True
    projection_pending = True

    def __init__(self):
        super().__init__('isolated decision recorded; assignment projection unconfirmed; retry the original key and input')


class IsolatedRunAccessBridge:
    def __init__(self, owner_store, fixture_proof, repository_path, *,
                 approver_ids, enabled_for_isolated_tests=False,
                 max_access_seconds=14400, clock=None):
        self.enabled = enabled_for_isolated_tests is True
        self.owner = owner_store
        self.proof = fixture_proof
        self.approver_ids = frozenset(approver_ids)
        self.max_access_seconds = max_access_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._engines, self._bindings, self._sources, self._projections = {}, {}, {}, {}
        self._mutex = RLock()
        self.repository = None
        if not self.enabled:
            return
        if (owner_store.mode != 'LOCAL' or type(max_access_seconds) is not int or
                not 60 <= max_access_seconds <= 28800 or not self.approver_ids or
                len(self.approver_ids) > 8 or
                any(not isinstance(id, str) or not id for id in self.approver_ids)):
            raise Denied('explicit bounded isolated access contract required')
        now = self.clock()
        self.authority_validity = Validity(valid_from=(now - timedelta(seconds=60)).isoformat(),
            valid_until=(now + timedelta(hours=8)).isoformat(), timezone='UTC')
        self._issued_proof()
        path = Path(repository_path)
        root = Path(tempfile.gettempdir()).resolve()
        if (not path.is_absolute() or path.resolve() != path or
                not path.is_relative_to(root) or path.parent == root or
                not path.parent.is_dir() or path.is_symlink() or
                not hasattr(os, 'geteuid') or path.parent.stat().st_uid != os.geteuid()):
            raise Denied('owned temporary access journal required')
        # Validate journal schema before changing the verified fixture schema.
        # No connection/DDL is attempted at all without exact issued proof.
        with self.owner.connect() as c:
            self._proof(c)
            self._endpoint = (c.info.host, c.info.port)
            for id in sorted(self.approver_ids):
                p = c.execute('SELECT * FROM principals WHERE id=%s', (id,)).fetchone()
                if not p or p['role'] != 'park_specialist':
                    raise Denied('explicit existing synthetic access approver required')
                self.owner.check_capability(c, p, 'READ')
            self.repository = candidate.RunAccessRepository(path)
            c.execute('ALTER TABLE run_assignments ADD COLUMN IF NOT EXISTS managed_access jsonb')
            column = c.execute("""SELECT data_type,is_nullable FROM information_schema.columns
                WHERE table_schema='public' AND table_name='run_assignments'
                  AND column_name='managed_access'""").fetchone()
            if not column or column['data_type'] != 'jsonb' or column['is_nullable'] != 'YES':
                raise Denied('isolated managed assignment schema refused')

    def _issued_proof(self):
        proof = self.proof
        if (not self.enabled or type(proof) is not facts.FixtureDatabaseEvidence or
                facts._fixture_databases.get(proof.nonce) is not proof or
                facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster or
                set(dict(proof.cluster.initial_databases)) != {'postgres', 'template0', 'template1'} or
                proof.database_name in dict(proof.cluster.initial_databases)):
            raise Denied('issued fresh owned temporary fixture proof required')
        return proof

    def _proof(self, c):
        proof = self._issued_proof()
        actual = facts._migration_identity(c)
        facts._same_cluster(proof.cluster, actual)
        if (actual['database_oid'] != proof.database_oid or
                actual['database_name'] != proof.database_name or
                actual['owner_name'] != proof.cluster.owner or
                actual['session_name'] != proof.cluster.owner):
            raise Denied('isolated fixture proof no longer matches database')

    def _connection(self, c):
        # The application role need not acquire pg_control_system privileges.
        # Bind its actual local endpoint, DB OID and postmaster start to the
        # owner's issued fixture proof. Owner checks additionally verify system
        # identifier/data directory, with no added database permissions.
        if not self.enabled or (c.info.host, c.info.port) != self._endpoint:
            raise Denied('isolated access connection unavailable')
        row = c.execute("""SELECT d.oid,d.datname,pg_postmaster_start_time() started
            FROM pg_database d WHERE d.datname=current_database()""").fetchone()
        if (not row or row['oid'] != self.proof.database_oid or
                row['datname'] != self.proof.database_name or
                row['started'] != self.proof.cluster.postmaster_start or
                facts._fixture_databases.get(self.proof.nonce) is not self.proof or
                facts._fixture_clusters.get(self.proof.cluster.nonce) is not self.proof.cluster):
            raise Denied('isolated access connection binding refused')

    def attach_store(self, store):
        if not self.enabled or store.mode != 'LOCAL':
            raise Denied('isolated access bridge disabled')
        with self.owner.connect() as c:
            self._proof(c)
        with store.connect() as c:
            self._connection(c)
        store._isolated_run_access = self
        return store

    def _lock(self, c, run_id, *, exclusive=False):
        c.execute("SET LOCAL lock_timeout='3s'")
        fn = 'pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
        c.execute('SELECT ' + fn + '(hashtextextended(%s,0))', ('isolated-run-access:' + str(run_id),))

    def _run(self, c, run_id):
        read_only = c.execute("SELECT current_setting('transaction_read_only')='on' readonly").fetchone()['readonly']
        row = c.execute('SELECT * FROM runs WHERE id=%s' + ('' if read_only else ' FOR SHARE'), (run_id,)).fetchone()
        if (not row or row['namespace'] != 'SYNTHETIC' or
                row['input'].get('action', 'case.create') != 'case.create'):
            raise Denied('exact synthetic Case Run required')
        return row

    def _auth(self, c, token):
        p = self.owner.auth(c, token, lock=True)
        self.owner.check_capability(c, p, 'READ')
        if p['role'] not in ('enterprise_operator', 'park_specialist', 'service_executor'):
            raise Denied('isolated access role required')
        if p['role'] == 'park_specialist' and p['id'] not in self.approver_ids:
            raise Denied('explicit synthetic access approval permit required')
        return p

    def _scope(self, p, run):
        if ((p['park_id'], p['org_id']) != (run['park_id'], run['org_id']) or
                p['role'] == 'enterprise_operator' and p['id'] != run['principal_id']):
            raise Denied('owned exact Run scope required')
        return candidate.RunScope(park_id=run['park_id'], org_id=run['org_id'], run_id=str(run['id']))

    def _snapshot(self, c, id):
        self.owner.lock_principal(c, id)
        row = c.execute("""SELECT p.id,p.role,p.park_id,p.org_id,p.active,
            g.active read_active,g.revision read_revision,g.park_id read_park,g.org_id read_org
            FROM principals p LEFT JOIN capability_grants g
              ON g.principal_id=p.id AND g.capability='READ' WHERE p.id=%s""", (id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _readable(row, run):
        return bool(row and row['active'] and row['read_active'] and
                    (row['park_id'], row['org_id']) == (run['park_id'], run['org_id']) and
                    (row['read_park'], row['read_org']) == (run['park_id'], run['org_id']))

    @staticmethod
    def _source(run):
        return candidate.sha({k: str(run[k]) for k in ('id', 'principal_id', 'park_id', 'org_id', 'namespace', 'revision', 'state')} |
                             {'input_sha256': candidate.sha(run['input'])})

    def _config(self, c, run, revision):
        ids = {run['principal_id'], *self.approver_ids}
        ids.update(row['id'] for row in c.execute("""SELECT id FROM principals
            WHERE role='service_executor' AND park_id=%s AND org_id=%s ORDER BY id LIMIT 17""",
            (run['park_id'], run['org_id'])).fetchall())
        if len(ids) > 16:
            raise Conflict('bounded isolated access participant limit')
        bindings = {id: self._snapshot(c, id) for id in sorted(ids)}
        eligible = [p for p in bindings.values() if self._readable(p, run) and (
            p['id'] == run['principal_id'] and p['role'] == 'enterprise_operator' or
            p['id'] in self.approver_ids and p['role'] == 'park_specialist' or
            p['role'] == 'service_executor')]
        if not any(p['id'] == run['principal_id'] and p['role'] == 'enterprise_operator' for p in eligible):
            raise Denied('current synthetic Run owner READ required')
        validity = self.authority_validity
        scope = candidate.RunScope(park_id=run['park_id'], org_id=run['org_id'], run_id=str(run['id']))
        personas, read_facts, permits = [], [], []
        for index, p in enumerate(eligible):
            personas.append(candidate.RunPersona(id=p['id'], park_id=p['park_id'], org_id=p['org_id'], role=p['role']))
            read_facts.append(candidate.MockReadFact(principal_id=p['id'], park_id=p['park_id'], org_id=p['org_id'], validity=validity))
            actions = (['STATUS', 'REQUEST', 'CANCEL', 'REVOKE'] if p['role'] == 'enterprise_operator' else
                       ['STATUS', 'APPROVE', 'REJECT', 'REVOKE'] if p['role'] == 'park_specialist' else ['STATUS', 'ACCESS'])
            permits.append(candidate.RunPermit(id='isolated-permit-' + str(index), principal_id=p['id'], scope=scope, actions=actions, validity=validity))
        cfg = candidate.RunAccessConfig(enabled_for_isolated_tests=True, revision=revision,
            max_access_seconds=self.max_access_seconds, personas=personas, read_facts=read_facts,
            permits=permits, runs=[candidate.MockRun(scope=scope, owner_id=run['principal_id'], revision=run['revision'],
                source_ref=SourceRef(id=str(run['id']), kind='SYNTHETIC', revision=str(run['revision'])),
                snapshot='SYNTHETIC exact Case Run metadata ' + self._source(run) + ' authority ' + candidate.sha(bindings))])
        return cfg, bindings

    def _authority_current(self, c, run):
        key = str(run['id'])
        if self._sources.get(key) != self._source(run):
            return False
        return all(self._snapshot(c, id) == value for id, value in self._bindings.get(key, {}).items())

    def _engine(self, c, run, *, refresh=False):
        key = str(run['id'])
        with self._mutex:
            engine = self._engines.get(key)
            if engine is None or refresh and not self._authority_current(c, run):
                cfg, bindings = self._config(c, run, 1 if engine is None else engine.config.revision + 1)
                if engine is None:
                    engine = candidate.RunAccessEngine(cfg, self.repository, clock=self.clock)
                    self._engines[key] = engine
                else:
                    engine.replace_test_contract(cfg)
                self._bindings[key], self._sources[key] = bindings, self._source(run)
            return engine

    def status(self, token):
        if not self.enabled:
            return {'enabled': False, 'role': None, 'can_approve': False, 'can_revoke': False, 'max_validity_hours': self.max_access_seconds / 3600}
        with self.owner.connect() as c:
            self._proof(c)
            p = self._auth(c, token)
            within = self.clock() < datetime.fromisoformat(self.authority_validity.valid_until)
            approve = within and p['role'] == 'park_specialist' and p['id'] in self.approver_ids
            return {'enabled': True, 'namespace': NAMESPACE, 'role': p['role'], 'can_approve': approve,
                    'can_revoke': within and (approve or p['role'] == 'enterprise_operator'),
                    'approval_authority': 'EXPLICIT_ISOLATED_RUN_PERMIT' if approve else None,
                    'max_validity_hours': self.max_access_seconds / 3600,
                    'authority_valid_until': self.authority_validity.valid_until, 'deployment_enabled': False}

    def _view(self, c, p, run, engine, view):
        request = view['request']
        assignment = c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',
            (request['target_id'], run['id'])).fetchone() if request else None
        available = False
        if assignment and assignment['active'] and assignment.get('managed_access') is not None:
            beneficiary = c.execute('SELECT * FROM principals WHERE id=%s', (request['target_id'],)).fetchone()
            available = bool(beneficiary and self.assignment_allowed(c, beneficiary, run['id'], assignment))
        case = c.execute('SELECT id FROM cases WHERE run_id=%s', (run['id'],)).fetchone()
        own = p['role'] == 'enterprise_operator'
        approver = p['role'] == 'park_specialist' and p['id'] in self.approver_ids
        active = view['candidate_access_available'] and self._authority_current(c, run)
        return {**view, 'enabled': True, 'role': p['role'], 'case_id': str(case['id']) if case else None,
            'actual_run_access': available, 'actual_assignment_written': available,
            'projection_state': 'APPLIED' if available else 'PENDING' if active else 'INACTIVE',
            'can_request': own and view['state'] != 'REQUESTED' and not active,
            'can_cancel': own and view['state'] == 'REQUESTED',
            'can_approve': approver and view['state'] == 'REQUESTED',
            'can_reject': approver and view['state'] == 'REQUESTED',
            'can_revoke': (own or approver) and view['state'] == 'APPROVED',
            'can_probe': p['role'] == 'service_executor' and available,
            'executors': [{'id': actor.id, 'role': 'service_executor', 'capability': 'READ'}
                for actor in engine.config.personas if actor.role == 'service_executor'],
            'candidate_access_available': active, 'bridge_namespace': NAMESPACE,
            'authority_valid_until': self.authority_validity.valid_until}

    def read(self, token, run_id):
        try:
            run_id = UUID(str(run_id))
            with self.owner.connect() as c:
                self._proof(c)
                # Contract refresh invalidates old authority; serialize it like
                # a command instead of mutating configuration under read locks.
                self._lock(c, run_id, exclusive=True)
                p, run = self._auth(c, token), self._run(c, run_id)
                scope = self._scope(p, run)
                engine = self._engine(c, run, refresh=True)
                return self._view(c, p, run, engine, engine.read(p['id'], scope))
        except candidate.Denied as error:
            raise Denied(str(error)) from None
        except (candidate.Conflict, LockNotAvailable) as error:
            raise Conflict('isolated access authority changed or busy; refresh/retry same input') from None

    def _managed(self, c, run, engine, view):
        request = view['request']
        return {'namespace': NAMESPACE, 'run_id': str(run['id']), 'park_id': run['park_id'], 'org_id': run['org_id'],
            'principal_id': request['target_id'], 'lease_id': view['lease_id'], 'approval_revision': view['revision'],
            'run_revision': run['revision'], 'contract_sha256': candidate.sha(engine.config.model_dump()),
            'source_sha256': self._source(run), 'authority_sha256': candidate.sha(self._bindings[str(run['id'])]),
            'valid_from': request['approved_validity']['valid_from'], 'valid_until': request['approved_validity']['valid_until']}

    def _project(self, c, run, engine, receipt, actor):
        scope = self._scope(actor, run)
        view = engine.read(actor['id'], scope)
        target = receipt['request']['target_id']
        row = c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s FOR UPDATE', (target, run['id'])).fetchone()
        if row and row.get('managed_access') is None:
            raise Conflict('legacy assignment protected; isolated approval cannot replace it')
        if row:
            prior = row['managed_access']
            approved = next((event for event in view['history'] if event['action'] == 'APPROVE'
                and event['lease_id'] == prior.get('lease_id')), None) if isinstance(prior, dict) else None
            expected = self._projections.get(prior.get('lease_id')) if isinstance(prior, dict) else None
            if expected is None and approved and approved['contract_sha256'] == candidate.sha(engine.config.model_dump()):
                expected = self._managed(c, run, engine, {'request': approved['request'],
                    'lease_id': approved['lease_id'], 'revision': approved['revision']})
            if (not approved or expected is None or prior != expected or
                    approved['request']['target_id'] != target or
                    approved['scope']['run_id'] != str(run['id'])):
                raise Conflict('foreign or changed managed assignment protected')
            if receipt['action'] == 'REVOKE':
                latest_approval = next((event for event in reversed(view['history'])
                    if event['action'] == 'APPROVE' and event['revision'] < receipt['revision']), None)
                if not latest_approval or prior['lease_id'] != latest_approval['lease_id']:
                    raise Conflict('revocation does not match prior approved lease')
            elif prior['lease_id'] != receipt['lease_id']:
                lease = next((item for item in view['leases'] if item['id'] == prior['lease_id']), None)
                if not lease or lease['state'] == 'APPROVED' and self.clock() < datetime.fromisoformat(prior['valid_until']):
                    raise Conflict('current different managed lease protected')
        if receipt['action'] == 'APPROVE':
            if (not view['candidate_access_available'] or view['revision'] != receipt['revision'] or
                    view['lease_id'] != receipt['lease_id'] or not self._authority_current(c, run)):
                raise Denied('current approval required for isolated projection')
            metadata = self._managed(c, run, engine, view)
            c.execute("""INSERT INTO run_assignments(principal_id,run_id,park_id,org_id,active,managed_access)
                VALUES(%s,%s,%s,%s,true,%s) ON CONFLICT(principal_id,run_id) DO UPDATE
                SET active=true,managed_access=excluded.managed_access
                WHERE run_assignments.managed_access IS NOT NULL""",
                (target, run['id'], run['park_id'], run['org_id'], Jsonb(metadata)))
            self._projections[metadata['lease_id']] = metadata
        elif receipt['action'] == 'REVOKE' and row:
            if view['state'] != 'REVOKED' or view['revision'] != receipt['revision']:
                raise Conflict('current revocation required for isolated projection')
            c.execute('UPDATE run_assignments SET active=false WHERE principal_id=%s AND run_id=%s AND managed_access IS NOT NULL', (target, run['id']))

    def command(self, token, run_id, key, data):
        receipt = None
        try:
            run_id = UUID(str(run_id))
            data = candidate.RunCommand.model_validate(data)
            with self.owner.connect() as c:
                self._proof(c)
                self._lock(c, run_id, exclusive=True)
                p, run = self._auth(c, token), self._run(c, run_id)
                scope = self._scope(p, run)
                engine = self._engine(c, run, refresh=data.action in ('REQUEST', 'APPROVE'))
                if data.action in ('APPROVE', 'REVOKE'):
                    before = engine.read(p['id'], scope)
                    if before['request']:
                        old_assignment = c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',
                            (before['request']['target_id'], run_id)).fetchone()
                        if old_assignment and old_assignment.get('managed_access') is None:
                            raise Conflict('legacy assignment protected; isolated decision cannot replace it')
                # SQLite decision commits first. A PG failure must never be
                # represented as an atomic rollback of its immutable audit.
                receipt = engine.command(p['id'], scope, key, data)
                if receipt['action'] in ('APPROVE', 'REVOKE'):
                    self._project(c, run, engine, receipt, p)
                current = self._view(c, p, run, engine, engine.read(p['id'], scope))
                return {**current, 'event': receipt, 'distributed_commit': False}
        except candidate.Denied as error:
            if receipt is not None:
                raise ProjectionPending() from None
            raise Denied(str(error)) from None
        except candidate.Conflict as error:
            if receipt is not None:
                raise ProjectionPending() from None
            raise Conflict(str(error)) from None
        except LockNotAvailable:
            if receipt is not None:
                raise ProjectionPending() from None
            raise Conflict('isolated access authority busy; retry same input') from None
        except Exception:
            if receipt is not None:
                raise ProjectionPending() from None
            raise

    def assignment_allowed(self, c, p, run_id, assignment):
        """Live guard; shared scope and Run locks remain until caller COMMIT.

        Root Store must repeat this guard with fresh principal/row at its final
        commit boundary, so TTL and current grants are checked again there.
        Any failed/unavailable component denies; it never falls back to legacy.
        """
        try:
            self._connection(c)
            self._lock(c, run_id)
            run = self._run(c, run_id)
            metadata = assignment.get('managed_access') if assignment else None
            if (not assignment or not assignment['active'] or not isinstance(metadata, dict) or
                    metadata.get('namespace') != NAMESPACE or p['role'] != 'service_executor' or
                    assignment['principal_id'] != p['id'] or str(assignment['run_id']) != str(run['id']) or
                    (assignment['park_id'], assignment['org_id']) != (run['park_id'], run['org_id']) or
                    self._scope(p, run).run_id != str(run['id'])):
                return False
            current = self._snapshot(c, p['id'])
            if not self._readable(current, run) or current['role'] != 'service_executor':
                return False
            engine = self._engine(c, run)
            if not self._authority_current(c, run):
                return False
            scope = self._scope(p, run)
            view = engine.read(p['id'], scope)
            if not view['candidate_access_available'] or view['request']['target_id'] != p['id']:
                return False
            if metadata != self._managed(c, run, engine, view):
                return False
            probe = candidate.AccessProbe(expected_revision=view['revision'], expected_run_revision=view['run_revision'],
                expected_authority_sha256=view['authority_sha256'], lease_id=view['lease_id'])
            return engine.access(p['id'], scope, probe)['candidate_read_allowed'] is True
        except Exception:
            return False
