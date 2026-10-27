"""Original bounded consistency projection, shared by worker and read-only view.

These functions consume already authorized rows. They neither authorize callers
nor choose authoritative evidence or persist a new assessment.
"""
from datetime import datetime
import json


def results(fields, rows, now):
    projected = []
    for field in fields:
        all_rows = [row for row in rows if row['field_name'] == field]
        valid = [row for row in all_rows if row['valid_from'] <= now < row['valid_until']]
        values = {json.dumps([row['value'], row['unit']], ensure_ascii=False) for row in valid}
        reason = ('MISSING_EVIDENCE' if not all_rows else 'EXPIRED_OR_NOT_YET_VALID' if not valid
                  else 'CONFLICTING_EVIDENCE' if len(values) > 1 else 'CONSISTENT_EVIDENCE')
        projected.append(dict(field=field, state='KNOWN' if reason == 'CONSISTENT_EVIDENCE' else 'UNKNOWN',
            reason=reason, evidence=[dict(id=str(row['evidence_id']), fact_id=str(row['id']),
                source_ref=row['source_ref'], value=row['value'], unit=row['unit'],
                valid_from=row['valid_from'].isoformat(), valid_until=row['valid_until'].isoformat(),
                applicable_at_assessment=row in valid, source_excerpt=row['source_excerpt'],
                revision=row['revision'], fingerprint=row['fingerprint'], source_kind=row['source_kind'])
                for row in all_rows]))
    return projected


def next_conditions(items):
    return [dict(field=item['field'], condition={
        'MISSING_EVIDENCE': 'PROVIDE_SOURCED_EVIDENCE',
        'EXPIRED_OR_NOT_YET_VALID': 'PROVIDE_CURRENT_SOURCED_EVIDENCE',
        'CONFLICTING_EVIDENCE': 'RESOLVE_CONFLICT_WITH_SOURCED_EVIDENCE',
        'CONSISTENT_EVIDENCE': 'AUTHORITATIVE_VERIFICATION_REQUIRED',
    }[item['reason']]) for item in items]


def changes(historical, current, fields, now):
    """Compare identity/fingerprint/applicability without changing old results."""
    before = historical['results']
    if ([item['field'] for item in before] != list(fields) or
            datetime.fromisoformat(historical['assessed_at']) > now):
        raise ValueError('historical assessment binding unavailable')
    changes = []
    for old, new in zip(before, current):
        left = {item['fact_id']: item for item in old['evidence']}
        right = {item['fact_id']: item for item in new['evidence']}
        if len(left) != len(old['evidence']) or len(right) != len(new['evidence']):
            raise ValueError('duplicate historical evidence')
        common = left.keys() & right.keys()
        if any(type(item['applicable_at_assessment']) is not bool for item in left.values()):
            raise ValueError('historical applicability unavailable')
        expired = sorted(key for key in common if left[key]['applicable_at_assessment'] and
                         not right[key]['applicable_at_assessment'] and
                         datetime.fromisoformat(right[key]['valid_until']) <= now)
        newly_applicable = sorted(key for key in common if not left[key]['applicable_at_assessment']
                                  and right[key]['applicable_at_assessment'])
        changed = sorted(key for key in common if left[key]['fingerprint'] != right[key]['fingerprint'])
        item = dict(field=old['field'], historical_reason=old['reason'], current_reason=new['reason'],
                    added_source_ids=sorted(right.keys() - left.keys()),
                    unavailable_source_ids=sorted(left.keys() - right.keys()),
                    changed_source_ids=changed, newly_expired_source_ids=expired,
                    newly_applicable_source_ids=newly_applicable,
                    current_conflicting_source_ids=sorted(key for key, value in right.items()
                        if new['reason'] == 'CONFLICTING_EVIDENCE' and value['applicable_at_assessment']))
        item['changed'] = bool(item['added_source_ids'] or item['unavailable_source_ids'] or
            changed or expired or newly_applicable or old['reason'] != new['reason'] or
            any(left[key]['applicable_at_assessment'] != right[key]['applicable_at_assessment'] for key in common))
        changes.append(item)
    return changes
