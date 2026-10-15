"""Synthetic preparation oracles only. Does not read primary/private sets/runtime evidence."""
from pathlib import Path
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

from shared_matcher import KnownTokenRedactor, PLACEHOLDER
from audit_archive import rebuild

HERE = Path(__file__).resolve().parent


def reference(text, values):
    count = 0
    for value in values:
        count += text.count(value)
        text = text.replace(value, '[REDACTED_SYNTHETIC_SESSION]')
    return text, count


def main():
    one = 'A' * 43
    two = 'B' * 43
    cases = [
        ('empty', '', [one]),
        ('none', 'unchanged assertion and traceback', [one]),
        ('exact', one, [one]),
        ('embedded_left', 'prefix_' + one, [one]),
        ('embedded_both', 'prefix_' + one + '_suffix', [one]),
        ('adjacent', one + two, [one, two]),
        ('repeat_overlaps', one + one, [one]),
        ('pool_overlap', 'A' * 43 + 'B', [one, 'A' * 42 + 'B']),
        ('fallback_short', 'short_short', ['short']),
        ('fallback_different_lengths', 'longer_value_and_short', ['longer_value', 'short']),
        ('placeholder_not_new_token', one + '[]' + two, [one, two]),
        ('newline_boundaries', '\n' + one + '\r\n' + two, [one, two]),
    ]
    records = []
    for name, text, values in cases:
        matcher = KnownTokenRedactor(values)
        actual = matcher.replace(text)
        expected = reference(text, values)
        assert actual == expected, name
        assert matcher.has_residual(text) == any(value in text for value in values)
        assert not matcher.has_residual(actual[0])
        records.append(dict(case=name, equivalent=True, input_sha256=hashlib.sha256(text.encode()).hexdigest(),
            replacements=actual[1], counters=matcher.public_statistics()))
    matcher = KnownTokenRedactor([one])
    raw = ('fixture = (<parkweave.store.Store object at 0xfeed>, {"actor":"' + one + '"})\n'
           'AssertionError: exact failed assertion\n').encode()
    result, counts = rebuild(raw, '.log', matcher)
    assert result == b'[REDACTED_SYNTHETIC_FIXTURE_REPR]\nAssertionError: exact failed assertion\n'
    assert counts == dict(exact_private_value=1, fixture_repr_line=1)
    json_raw = json.dumps(dict(assertion='unchanged', context=raw.decode())).encode()
    result, counts = rebuild(json_raw, '.json', matcher)
    value = json.loads(result)
    assert value['assertion'] == 'unchanged' and value['context'].startswith('[REDACTED_SYNTHETIC_FIXTURE_REPR]\n')
    xml_raw = ('<testsuite><testcase><failure>fixture = (&lt;Store object at 0xfeed&gt;, ' + one + ')\nAssertionError: retained</failure></testcase></testsuite>').encode()
    result, counts = rebuild(xml_raw, '.xml', matcher)
    assert ET.fromstring(result).find('.//failure').text == '[REDACTED_SYNTHETIC_FIXTURE_REPR]\nAssertionError: retained'
    untouched = b'{ "assertion" : "unchanged" }\n'
    assert rebuild(untouched, '.json', matcher) == (untouched, dict(exact_private_value=0, fixture_repr_line=0))
    scripts = {}
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_bytes(), filename=str(path))
        scripts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = dict(status='PREPARATION_SELF_CHECK_ONLY_NOT_ARCHIVE_OR_DELIVERY_PASS',
        matcher_synthetic_differential_cases=records, structured_oracles=4,
        syntax_checked_scripts=scripts, actual_primary_read=False, private_sets_read=False,
        source_or_business_execution=False, actual_archive_final_gate_run=False,
        algorithm_diversity_claimed=False)
    (HERE / 'preparation-selfcheck.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(dict(status=output['status'], differential_cases=len(records), structured_oracles=4,
        scripts=len(scripts), actual_archive_final_gate_run=False)))


if __name__ == '__main__':
    main()
