"""Finite, default-off candidate revision gate; never migrates existing Cases."""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .template_candidate import Command, TemplateDraft, canonical, sha, active
from . import bounded_planning as planning
from .store import Conflict

PROFILE = 'ISOLATED_SAME_CONTRACT_NEW_CASE_RELEASE_V1'


class Publication(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    command: Command
    expected_preflight_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def exact_confirmation(cls,value):
        if value is not True:raise ValueError('explicit boolean confirmation required')
        return value

    def validate_publication(self):
        if self.command.action != 'CANDIDATE_PUBLISH':
            raise Conflict('compatible publication requires original publish command')


def inspect(engine, connection, actor, scope):
    try:return _inspect(engine,connection,actor,scope)
    except (ValueError,TypeError,KeyError,AttributeError):
        raise Conflict('unknown or malformed original publication proof') from None


def _inspect(engine, connection, actor, scope):
    """Called under the original engine lock and SQLite write transaction."""
    engine._authorize(actor, 'CANDIDATE_PUBLISH', scope, engine.clock())
    engine._enabled(connection)
    row = engine._row(connection, scope)
    if row is None or row['state'] != 'REVIEWED' or not row['review']:
        raise Conflict('current independently reviewed draft required')
    definition = json.loads(row['definition'])
    review = json.loads(row['review'])
    registry_hash = sha(dict(steps=planning.REGISTRY, actions=planning.ACTIONS))
    contract_hash = sha(engine.config.model_dump(mode='json'))
    if (review['action'] != 'REVIEW' or review['definition_sha256'] != sha(definition)
            or review['contract_sha256'] != contract_hash or review['registry_sha256'] != registry_hash):
        raise Conflict('current reviewed definition, registry and contract required')
    engine._authorize(row['author_id'], 'SUBMIT', scope, engine.clock())
    engine._authorize(review['reviewer_id'], 'REVIEW', scope, engine.clock())
    if actor in (row['author_id'], review['reviewer_id']):
        raise Conflict('independent original publisher required')
    if (not active(definition['source']['validity'], engine.clock())
            or not engine._source_current(connection, scope, definition['source'])):
        raise Conflict('current reviewed source required')
    previous = connection.execute('SELECT * FROM template_releases WHERE scope=? ORDER BY rowid DESC LIMIT 1',
                                  (canonical(scope.model_dump()),)).fetchone()
    classification, reasons = 'UNKNOWN', ['ORIGINAL_RELEASE_REQUIRED']
    prior = None
    if previous is not None:
        prior = json.loads(previous['payload'])
        valid = (previous['state'] in ('PUBLISHED', 'SUPERSEDED')
                 and sha(prior) == previous['payload_sha']
                 and prior['definition_sha256'] == sha(prior['definition'])
                 and prior['scope'] == scope.model_dump()
                 and prior['registry_sha256'] == registry_hash and prior['contract_sha256'] == contract_hash
                 and active(prior['validity'], engine.clock()))
        try:
            TemplateDraft.model_validate(prior['definition'])
            TemplateDraft.model_validate(definition)
        except (ValueError, TypeError):
            valid = False
        if valid:
            old = prior['definition']
            # Deliberately only presentation changes. New semantic sources, goals,
            # steps, fields or unknown schema need a separate supported contract.
            hard = set(old) - {'name', 'description'}
            changed = sorted(k for k in hard if old[k] != definition[k])
            if set(old) != set(definition) or row['content_version'] <= prior['content_version']:
                classification, reasons = 'UNKNOWN', ['NONFORWARD_OR_UNKNOWN_DEFINITION']
            elif changed:
                classification, reasons = 'BREAKING_REJECTED', ['UNSUPPORTED_CONTRACT_CHANGE:' + k for k in changed]
            else:
                classification, reasons = 'COMPATIBLE', []
        else:
            reasons = ['ORIGINAL_RELEASE_PROOF_OR_CURRENT_CONTRACT_UNAVAILABLE']
    proof = dict(profile=PROFILE, scope=scope.model_dump(), draft_revision=row['revision'],
                 draft_content_version=row['content_version'], definition_sha256=sha(definition),
                 review_sha256=sha(review), registry_sha256=registry_hash, contract_sha256=contract_hash,
                 original_release_id=previous['id'] if previous else None,
                 original_release_sha256=previous['payload_sha'] if previous else None,
                 original_release_state=previous['state'] if previous else None,
                 classification=classification, blockers=reasons, business_publication=False,
                 migration_performed=False, new_grants=False, future_validity_guaranteed=False)
    return dict(preflight=proof, preflight_sha256=sha(proof), can_publish=classification == 'COMPATIBLE')
