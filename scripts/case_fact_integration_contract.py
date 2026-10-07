"""Black-box assertions for ENG101 wiring, not a product launcher or browser script.

Import from main-line tests and pass their existing TestClient/current synthetic
sessions and an independent business oracle. Never prepares identities/grants,
reads DSNs, mounts routes, calls the fact module directly, or prints responses.
CLI prints the pending contract checklist only; it never claims integration PASS.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Callable
from uuid import uuid4
from urllib.parse import urlsplit, parse_qs

PROFILE = 'LOCAL_SERVICE_PREPARATION_FACTS_V1'
FIELDS = ('region', 'employees', 'service_need')
FORBIDDEN_PRIVATE_KEYS = frozenset((
    'fact_clarifications', 'source_snapshot', 'assertion_id',
    'expected_assertion_fingerprint', 'necessary_questions',
    'sources', 'choices', 'source_ref', 'source_excerpt', 'evidence_id',
    'field_name', 'confirmed_by', 'region', 'employees', 'service_need',
))


class ContractFailure(AssertionError):
    """Safe message contains check names/statuses, never private response data."""


def require(condition, check):
    if not condition:
        raise ContractFailure(check)


def _body(response, statuses=(200,)):
    require(response.status_code in statuses,
            'HTTP_STATUS_REQUIRED: expected ' + '/'.join(map(str, statuses)) + ', actual ' + str(response.status_code))
    try:
        value = response.json()
    except (ValueError, TypeError):
        raise ContractFailure('JSON_RESPONSE_REQUIRED') from None
    require(isinstance(value, dict), 'OBJECT_RESPONSE_REQUIRED')
    return value


def assert_redacted(value, private_markers=()):
    """Inspect keys recursively and exact unique marker substrings; never log them.

    Marker values must be unique synthetic fact IDs/text supplied by the caller,
    not common words/numbers or material values legitimately visible in this API.
    """
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                require(key not in FORBIDDEN_PRIVATE_KEYS, 'PRIVATE_FACT_KEY_EXPOSED')
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in private_markers:
        require(isinstance(marker, str) and bool(marker), 'UNIQUE_NONEMPTY_STRING_MARKER_REQUIRED')
        require(marker not in serialized, 'PRIVATE_FACT_VALUE_EXPOSED')


def assert_historical_replay(response, current_view, expected_original_revision):
    event = _body(response, (200, 201))
    require(event.get('recovery') == 'HISTORICAL_COMMITTED_EVENT', 'HISTORY_LABEL_REQUIRED')
    require(event.get('current_decision_restored') is False, 'HISTORY_MUST_NOT_RESTORE_CURRENT')
    require(event.get('revision') == expected_original_revision, 'HISTORY_ORIGINAL_PREPARATION_REVISION_REQUIRED')
    require(current_view.get('state') == 'STALE' and current_view.get('satisfied') is False,
            'CURRENT_GATE_MUST_REMAIN_STALE')
    return event


def assert_reconfirmation(event, previous_view, current_view, generic_view):
    require(event.get('action') == 'CONFIRM_FACT_PURPOSE', 'REAL_CONFIRM_ACTION_REQUIRED')
    expected = previous_view['preparation_revision'] + 1
    require(event.get('revision') == expected and event.get('state') == 'IN_PREPARATION',
            'NEW_PREPARATION_REVISION_AND_REVIEW_RESET_REQUIRED')
    require(current_view.get('preparation_revision') == expected and
            current_view.get('revision') == previous_view['revision'] + 1,
            'BOTH_REVISIONS_MUST_ADVANCE')
    require(current_view.get('state') == 'CURRENT' and current_view.get('satisfied') is True,
            'NEW_EXPLICIT_SELECTION_CURRENT_REQUIRED')
    require(current_view.get('authenticity') == 'USER_ASSERTED_UNVERIFIED' and
            current_view.get('qualification') == 'NOT_EVALUATED', 'SELECTION_IS_NOT_TRUTH_OR_QUALIFICATION')
    parent = generic_view.get('preparation', {})
    require(parent.get('revision') == expected and parent.get('state') == 'IN_PREPARATION' and
            parent.get('review_sha256') is None, 'GENERIC_CURRENT_MATERIAL_REVIEW_RESET_REQUIRED')
    old = previous_view.get('history', [])
    new = current_view.get('history', [])
    require(len(new) == len(old) + 1 and new[:len(old)] == old, 'IMMUTABLE_HISTORY_PREFIX_REQUIRED')


def assert_observed_invalidation(before, after, cause):
    require(cause in ('SOURCE', 'REQUEST', 'EXPIRED', 'WRITE_REVOKED', 'AUTHORITY_REVISION'), 'KNOWN_INVALIDATION_CAUSE_REQUIRED')
    require(before.get('state') == 'CURRENT' and before.get('satisfied') is True and after.get('state') == 'STALE' and after.get('satisfied') is False,
            'CURRENT_SELECTION_MUST_BECOME_STALE')
    require(after.get('revision') == before.get('revision') and after.get('history') == before.get('history'),
            'INVALIDATION_MUST_PRESERVE_DECISION_HISTORY')
    if cause == 'REQUEST':
        require(after['preparation_revision'] > before['preparation_revision'], 'ORIGINAL_REQUEST_REVISION_REQUIRED')
    else:
        require(after['preparation_revision'] == before['preparation_revision'], 'OBSERVATION_MUST_NOT_BUMP_PREPARATION')
    if cause in ('SOURCE', 'REQUEST', 'WRITE_REVOKED', 'AUTHORITY_REVISION'):
        require(after.get('source_sha256') != before.get('source_sha256'), 'ACTUAL_SOURCE_BINDING_MUST_CHANGE')
    else:
        require(after.get('source_sha256') == before.get('source_sha256'), 'CLOCK_MUST_NOT_REHASH_STABLE_SOURCE_BINDING')


def assert_recovery_generation(old_receipt, new_receipt, final_case):
    """Pass authoritative old/new GETs; this asserts generations, not authenticity."""
    old = old_receipt.get('step', {})
    new = new_receipt.get('step', {})
    for key in ('preparation_id', 'case_id', 'run_id', 'executor_id'):
        require(old.get(key) is not None and old.get(key) == new.get(key), 'SAME_CASE_RUN_ORIGINAL_EXECUTOR_REQUIRED')
    require(old.get('id') != new.get('id'), 'NEW_RECEIPT_STEP_UUID_REQUIRED')
    require(type(new.get('preparation_revision')) is int and type(old.get('preparation_revision')) is int and
            new['preparation_revision'] > old['preparation_revision'], 'NEW_RECEIPT_PREPARATION_GENERATION_REQUIRED')
    receipt = new_receipt.get('current_receipt') or {}
    require(receipt.get('version') == 1 and receipt.get('id') is not None, 'NEW_GENERATION_ACTUAL_RECEIPT_V1_REQUIRED')
    require(receipt['id'] != (old_receipt.get('current_receipt') or {}).get('id'), 'OLD_RECEIPT_MUST_NOT_BE_COPIED')
    require(receipt.get('step_id') == new.get('id'), 'ACTUAL_RECEIPT_MUST_BELONG_TO_NEW_STEP')
    require(new.get('state') == 'LOCAL_ACKNOWLEDGED', 'NEW_RECEIPT_OWNER_ACK_REQUIRED')
    # Caller passes the original /api/runs/{run_id} response, not a hand label.
    case = final_case.get('case') or {}
    require(case.get('id') == new.get('case_id') and final_case.get('run_id') == new.get('run_id'),
            'FINAL_CASE_RUN_MUST_MATCH_NEW_RECEIPT')
    require(case.get('state') == 'WAITING_CONFIRMATION', 'CASE_STILL_WAITING_CONFIRMATION_REQUIRED')


@dataclass(repr=False)
class FactAPI:
    client: object
    preparation_id: str
    owner_token: str = field(repr=False)

    def headers(self, token=None, key=None):
        headers = {'Authorization': 'Bearer ' + (self.owner_token if token is None else token)}
        if key is not None:
            headers['Idempotency-Key'] = key
        return headers

    @property
    def path(self):
        return '/api/preparations/' + self.preparation_id + '/fact-clarifications'

    def mount_probe(self):
        """Read-only. 404 is BLOCKED, never a positive refusal-boundary test."""
        response = self.client.get(self.path, headers=self.headers())
        if response.status_code == 404:
            return {'status': 'BLOCKED', 'reason': 'FACT_ROUTES_NOT_MOUNTED', 'http_status': 404}
        _body(response)
        return {'status': 'ROUTES_RESPONDED', 'integration_pass': False}

    def read(self):
        return _body(self.client.get(self.path, headers=self.headers()))

    def generic(self, token=None):
        return _body(self.client.get('/api/preparations/' + self.preparation_id, headers=self.headers(token)))

    def confirm_body(self, view, selected_ids):
        require(len(selected_ids) == 3 and len(set(selected_ids)) == 3, 'THREE_DISTINCT_SELECTED_ASSERTIONS_REQUIRED')
        chosen = {row['field_name']: row for row in view['sources'] if row['id'] in selected_ids}
        require(set(chosen) == set(FIELDS), 'ONE_SELECTED_ASSERTION_PER_FIELD_REQUIRED')
        return dict(expected_preparation_revision=view['preparation_revision'],
            expected_clarification_revision=view['revision'], expected_source_sha256=view['source_sha256'],
            choices=[dict(field=name, assertion_id=chosen[name]['id'],
                expected_assertion_revision=chosen[name]['revision'],
                expected_assertion_fingerprint=chosen[name]['fingerprint']) for name in FIELDS],
            reason='SYNTHETIC explicit Case-purpose selection; authenticity unverified')

    def assert_generic_redaction(self, tokens, private_markers):
        """tokens: current owner and assigned specialist supplied by existing fixture."""
        for token in tokens:
            assert_redacted(self.generic(token), private_markers)
            for path in ('/api/preparations', '/api/preparation-tasks'):
                response = self.client.get(path, headers=self.headers(token))
                assert_redacted(_body(response), private_markers)

    def assert_private_read_denied(self, token):
        response = self.client.get(self.path, headers=self.headers(token))
        require(response.status_code == 403, 'PRIVATE_OWNER_ONLY_READ_MUST_BE_403')
        # Error envelopes must not include the private ledger either.
        assert_redacted(_body(response, (403,)))

    def confirm(self, body, key=None):
        return self.client.post(self.path + '/confirm', headers=self.headers(key=key or uuid4().hex), json=body)

    def exercise_fact_roundtrip(self, selected_ids, add_competitor, prepare_before_change,
                                stale_requests, business_snapshot, tokens_for_redaction, private_markers,
                                expected_stale_checks=('P1_VERIFY',)):
        """Actual HTTP fact integration spine, with main's existing original flow.

        Precondition: current owner has explicit approved synthetic facts and
        this Case has not declared the profile. No permission/setup is added.
        prepare_before_change(api, original_confirm_event) executes main's original
        REVIEW/CONFIRM/P1-P5 flow. add_competitor() MUST use original POST /api/facts.
        stale_requests() yields main's original Request instances for the explicit
        expected_stale_checks subset in its genuinely eligible stage. business_snapshot excludes rejection audit
        and explicitly allowed observation metadata, never business effects.
        Main performs genuine recovery afterward and calls assert_recovery_generation.
        """
        require(self.mount_probe().get('status') == 'ROUTES_RESPONDED', 'FACT_ROUTES_NOT_MOUNTED')
        initial = self.read()
        require(initial.get('enabled') is False, 'FRESH_UNDECLARED_CASE_REQUIRED')
        declaration = dict(expected_preparation_revision=initial['preparation_revision'],
            expected_clarification_revision=0, profile=PROFILE, purpose='SERVICE_PREPARATION',
            reason='SYNTHETIC original API purpose declaration')
        _body(self.client.post(self.path + '/declare', headers=self.headers(key=uuid4().hex), json=declaration), (200, 201))
        original_body = self.confirm_body(self.read(), selected_ids)
        original_key = uuid4().hex
        original_event = _body(self.confirm(original_body, original_key), (200, 201))
        require(original_event.get('action') == 'CONFIRM_FACT_PURPOSE', 'REAL_CONFIRM_EVENT_REQUIRED')
        require(len(tokens_for_redaction) >= 2 and bool(private_markers), 'OWNER_SPECIALIST_AND_PRIVATE_MARKERS_REQUIRED')
        self.assert_generic_redaction(tokens_for_redaction, private_markers)
        prepare_before_change(self, original_event)
        before_sources = self.read()
        add_competitor()
        stale = self.read()
        assert_observed_invalidation(before_sources, stale, 'SOURCE')
        observations = verify_refusals(self.client, stale_requests(), business_snapshot, expected_stale_checks)
        before = deepcopy(business_snapshot())
        replay = self.confirm(original_body, original_key)
        current = self.read()
        assert_historical_replay(replay, current, original_event['revision'])
        require(business_snapshot() == before, 'HISTORY_RETRY_MUST_NOT_WRITE_BUSINESS')
        renewed = _body(self.confirm(self.confirm_body(current, selected_ids)), (200, 201))
        latest = self.read()
        generic = self.generic()
        assert_reconfirmation(renewed, current, latest, generic)
        self.assert_generic_redaction(tokens_for_redaction, private_markers)
        # Reconfirmation cannot skip the original assigned specialist REVIEW.
        before = deepcopy(business_snapshot())
        response = self.client.post('/api/preparations/' + self.preparation_id + '/commands',
            headers=self.headers(key=uuid4().hex), json=dict(action='CONFIRM', expected_revision=renewed['revision'],
            reason='SYNTHETIC must reject bypass of new specialist review'))
        require(response.status_code == 409, 'ORIGINAL_MATERIAL_CONFIRM_MUST_REQUIRE_NEW_REVIEW')
        require(business_snapshot() == before, 'REVIEW_BYPASS_REFUSAL_MUST_NOT_WRITE_BUSINESS')
        return {'scope': 'ACTUAL_HTTP_FACT_ROUNDTRIP_ONLY', 'stale_commands_checked': observations,
            'original_preparation_revision': original_event['revision'],
            'new_preparation_revision': renewed['revision'], 'full_recovery': 'CALLER_MUST_EXECUTE_AND_VERIFY'}


@dataclass(repr=False)
class Request:
    check: str
    path: str
    token: str = field(repr=False)
    body: dict = field(repr=False)
    key: str = field(default_factory=lambda: uuid4().hex)
    precondition: dict | None = field(default=None, repr=False)
    predecessors: dict | None = field(default=None, repr=False)
    precondition_path: str | None = field(default=None, repr=False)
    predecessor_path: str | None = field(default=None, repr=False)


def assert_eligible_before_invalidation(request):
    require(request.check in ('P1_VERIFY', 'NEW_OFFER', 'OLD_SUBMIT', 'P5_CLOSE'),
            'KNOWN_ORIGINAL_GATE_CHECK_REQUIRED')
    view = request.precondition
    require(isinstance(view, dict), request.check + ': PREINVALIDATION_API_READ_REQUIRED')
    body = request.body
    if request.check == 'NEW_OFFER':
        origin = urlsplit(request.precondition_path or '')
        query = parse_qs(origin.query)
        ids = query.get('preparation_id', [])
        require(not origin.scheme and not origin.netloc and origin.path == '/api/service-dispatches/catalog'
                and set(query) == {'preparation_id'} and len(ids) == 1 and bool(ids[0]),
                'EXACT_CATALOG_PREPARATION_ORIGIN_REQUIRED')
        preparation_id = ids[0]
        expected_read = request.precondition_path
        expected_write = '/api/preparations/' + preparation_id + '/dispatch'
    elif request.check == 'OLD_SUBMIT':
        row = view.get('step', {})
        preparation_id = row.get('preparation_id')
        expected_read = '/api/executor-receipts/' + str(row.get('id'))
        expected_write = expected_read + '/commands'
    else:
        preparation_id = view.get('preparation_id')
        suffix = {'P1_VERIFY': '/service-case-plan', 'P5_CLOSE': '/local-case'}.get(request.check)
        require(suffix is not None, 'KNOWN_ORIGINAL_GATE_CHECK_REQUIRED')
        expected_read = '/api/preparations/' + str(preparation_id) + suffix
        expected_write = expected_read + '/commands'
    require(isinstance(preparation_id, str) and bool(preparation_id) and
            request.precondition_path == expected_read and request.path == expected_write,
            'EXACT_ORIGINAL_COMMAND_AND_PREPARATION_READ_REQUIRED')
    if request.check == 'P1_VERIFY':
        step = next((s for s in view.get('steps', []) if s.get('id') == body.get('step_id') and s.get('adapter_id') == 'P1'), {})
        require(body.get('action') == 'VERIFY' and 'VERIFY' in step.get('allowed_actions', []) and
                body.get('expected_revision') == view.get('revision') and
                body.get('expected_source_sha256') == step.get('source_sha256'), 'P1_PREINVALIDATION_VERIFY_MUST_BE_ALLOWED')
    elif request.check == 'NEW_OFFER':
        require(view.get('ready') is True and body.get('expected_preparation_revision') == view.get('preparation_revision') and
                body.get('expected_dispatch_revision') == view.get('dispatch_revision') and
                body.get('executor_id') in [p.get('id') for p in view.get('executors', [])], 'OFFER_PREINVALIDATION_CATALOG_READY_REQUIRED')
        if body.get('recovery_receipt_step_id') is not None:
            require(view.get('can_reoffer') is True and body['recovery_receipt_step_id'] == view.get('recovery_receipt_step_id'),
                    'EXACT_RECOVERY_OFFER_PRECONDITION_REQUIRED')
    elif request.check == 'OLD_SUBMIT':
        step = view.get('step', {})
        require(body.get('action') == 'SUBMIT' and step.get('state') in ('AWAITING_RECEIPT', 'CHANGES_REQUESTED') and
                view.get('is_current_step') is True and view.get('dependency') == 'CURRENT' and
                body.get('expected_revision') == step.get('revision') and
                request.path == '/api/executor-receipts/' + str(step.get('id')) + '/commands',
                'RECEIPT_PREINVALIDATION_SUBMIT_MUST_BE_ALLOWED')
    elif request.check == 'P5_CLOSE':
        require(body.get('action') == 'CLOSE_LOCAL_RECORD' and view.get('can_close_local_record') is True and
                body.get('expected_revision') == view.get('revision') and body.get('expected_cycle') == view.get('cycle') and
                body.get('expected_snapshot_sha256') == view.get('current_snapshot_sha256'), 'LOCAL_CLOSE_PREINVALIDATION_READY_REQUIRED')
    else:
        raise ContractFailure('KNOWN_ORIGINAL_GATE_CHECK_REQUIRED')
    if request.check != 'P1_VERIFY':
        required = {'NEW_OFFER': 2, 'OLD_SUBMIT': 3, 'P5_CLOSE': 4}[request.check]
        plan = request.predecessors
        require(isinstance(plan, dict) and bool(plan.get('plan_id')) and
                plan.get('preparation_id') == preparation_id and
                request.predecessor_path == '/api/preparations/' + preparation_id + '/service-case-plan',
                'SAME_PREPARATION_ORIGINAL_PREDECESSOR_PLAN_REQUIRED')
        origin_view = view.get('step', {}) if request.check == 'OLD_SUBMIT' else view
        for name in ('case_id', 'run_id'):
            if name in origin_view:
                require(origin_view[name] is not None and plan.get(name) == origin_view[name],
                        'SAME_CASE_RUN_PREDECESSOR_PLAN_REQUIRED')
        for index in range(1, required + 1):
            step = next((s for s in plan.get('steps', []) if s.get('adapter_id') == 'P' + str(index)), {})
            require(step.get('state') == 'VERIFIED', 'ORIGINAL_PREDECESSORS_MUST_BE_VERIFIED_BEFORE_INVALIDATION')


def capture_eligibility(client, request, get_path, predecessor_path=None):
    """Call BEFORE changing facts/clock/rights; hold private snapshots only in memory."""
    request.precondition_path = get_path
    request.precondition = deepcopy(_body(client.get(get_path, headers={'Authorization': 'Bearer ' + request.token})))
    if predecessor_path is not None:
        request.predecessor_path = predecessor_path
        request.predecessors = deepcopy(_body(client.get(predecessor_path, headers={'Authorization': 'Bearer ' + request.token})))
    assert_eligible_before_invalidation(request)
    return request


def verify_refusals(client, requests, business_snapshot: Callable, expected_checks=('P1_VERIFY', 'NEW_OFFER', 'OLD_SUBMIT', 'P5_CLOSE')):
    requests = list(requests)
    require(bool(expected_checks) and len(set(expected_checks)) == len(expected_checks), 'EXPLICIT_UNIQUE_CHECK_SCOPE_REQUIRED')
    require(len(requests) == len(expected_checks) and {r.check for r in requests} == set(expected_checks), 'EXACT_ORIGINAL_GATE_CHECK_SCOPE_REQUIRED')
    # Check all preconditions before issuing any mutation request.
    for request in requests:
        assert_eligible_before_invalidation(request)
    checks = []
    for request in requests:
        before = deepcopy(business_snapshot())
        response = client.post(request.path,
            headers={'Authorization': 'Bearer ' + request.token, 'Idempotency-Key': request.key}, json=request.body)
        require(response.status_code == 409, request.check + ': ORIGINAL_GATE_MUST_REFUSE_409')
        require(business_snapshot() == before, request.check + ': REFUSAL_MUST_NOT_WRITE_BUSINESS')
        checks.append(request.check)
    return checks


def checklist():
    return {
        'scope': 'PENDING_MAIN_LINE_BLACK_BOX_CONTRACT', 'integration_pass': False,
        'routes': ['GET .../fact-clarifications', 'POST .../declare', 'POST .../confirm'],
        'checks': ['generic owner/specialist/list/tasks redaction', 'private foreign owner/specialist/READ-revoked 403',
            'original facts POST changes gate to STALE without history rewrite',
            'old confirm key returns historical only and cannot revive current state',
            'stale original P1 VERIFY/new OFFER/old SUBMIT/P5 CLOSE are 409 and zero business effect',
            'explicit reconfirmation increments both revisions and resets manual material review',
            'original CONFIRM cannot bypass new specialist REVIEW',
            'source expiry/request revision/field authority invalidate current descriptor',
            'original recovery accepts same executor into new prep generation and actual receipt v1',
            'old histories remain; final Case is WAITING_CONFIRMATION'],
        'not_automated': ['source expiry and grant withdrawal injection must use main approved fixture',
            'original full P1-P5/recovery sequence remains main-owned', 'browser', 'Windows', 'formal AT06'],
    }


if __name__ == '__main__':
    print(json.dumps(checklist(), ensure_ascii=False, indent=2))
