"""Explicit synthetic prerequisites in an already owned UUID test database.

No existing enterprise, Case, material, result, or grant is copied. Product
operations must consume these current permissions without creating new ones.
"""
import re
import secrets

from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from parkweave import preparation
from parkweave.store import digest

PARK = 'template-isolated-park'
ORGS = ('template-new-org-a', 'template-new-org-b')
ENTERPRISES = ('template-new-enterprise-a', 'template-new-enterprise-b')
REVIEWERS = ('template-new-reviewer-a', 'template-new-reviewer-b')


def seed_new_enterprises(fixture_or_owner):
    owner = fixture_or_owner[1] if isinstance(fixture_or_owner, tuple) else fixture_or_owner
    database = conninfo_to_dict(owner.dsn).get('dbname', '')
    if not re.fullmatch(r'fixture_[0-9a-f]{32}', database):
        raise ValueError('only an owned UUID fixture database may be seeded')
    tokens = {name: secrets.token_urlsafe(32) for name in ENTERPRISES + REVIEWERS}
    with owner.connect() as c:
        for enterprise, reviewer, org in zip(ENTERPRISES, REVIEWERS, ORGS):
            # Explicit current identity and original role capabilities.
            for principal, role in ((enterprise, 'enterprise_operator'), (reviewer, 'park_specialist')):
                c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                          (principal, digest(tokens[principal]), PARK, org, role))
            for capability in ('READ', 'EXECUTE'):
                c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',
                          (enterprise, capability, PARK, org))
            c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,'READ',%s,%s)",
                      (reviewer, PARK, org))
            # Only the existing local Case action is needed, not fault/model work.
            c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create',%s,%s)",
                      (enterprise, PARK, org))
            owner.seed_field_grants(c, enterprise, PARK, org)
            for principal, capability in ((enterprise, 'PREPARE'), (reviewer, 'REVIEW_ASSIGNED')):
                c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s)',
                          (principal, PARK, org, capability))
        source = {'kind': 'SYNTHETIC', 'id': 'ENG098-new-enterprise-service',
                  'revision': '1', 'statement': 'Explicit isolated new enterprise material preparation prerequisites.'}
        c.execute("INSERT INTO preparation_catalog VALUES(%s,%s,1,%s,%s,'SYNTHETIC','NOT_EVALUATED')",
                  (PARK, preparation.SERVICE, 'New enterprise synthetic preparation', Jsonb(source)))
    return tokens


def grant_snapshot(owner):
    with owner.connect() as c:
        return {table: c.execute(f'SELECT * FROM {table} ORDER BY 1,2').fetchall()
                for table in ('principals', 'capability_grants', 'action_grants', 'field_grants',
                              'preparation_grants', 'synthetic_resource_grants', 'run_assignments')}
