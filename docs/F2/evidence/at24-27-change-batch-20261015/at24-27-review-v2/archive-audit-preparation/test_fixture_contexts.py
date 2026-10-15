import json
import xml.etree.ElementTree as ET
from scan_fixture_contexts import scan_fixture_contexts


def token():
    return 'A' * 21 + 'b' * 21 + '7'


def test_store_repr_is_detected_without_any_recoverable_value():
    raw = b"template_consumption = {'owner': <Store object at 0x1>, 'tokens': {...}}\n"
    assert [x['kind'] for x in scan_fixture_contexts(raw, '.log')] == ['unmasked_original_fixture_repr']


def test_full_known_actor_value_in_fixture_is_detected_hash_only():
    value = "template_consumption = {'owner': <Store object at 0x1>, 'tokens': {'template-new-enterprise-a': '" + token() + "'}}"
    findings = scan_fixture_contexts(value.encode(), '.log')
    assert {x['kind'] for x in findings} == {'unmasked_original_fixture_repr', 'complete_session_candidate_in_fixture_context'}
    assert token() not in json.dumps(findings)


def test_compact_xml_is_parsed_before_context_scan():
    root = ET.Element('testsuites')
    failure = ET.SubElement(root, 'failure')
    failure.text = "template_consumption = {'owner': <Store object at 0x1>, 'tokens': {'template-new-enterprise-a': '" + token() + "'}}"
    assert len(scan_fixture_contexts(ET.tostring(root), '.xml')) == 2


def test_recursive_json_token_map_is_detected_without_fixture_repr():
    data = json.dumps(dict(nested=dict(tokens={'template-new-enterprise-a': token()}))).encode()
    result = scan_fixture_contexts(data, '.json')
    assert len(result) == 1 and result[0]['kind'] == 'unredacted_token_map_value'


def test_jsonl_embedded_fixture_repr_is_scanned_as_decoded_string():
    line = "tokens = {'template-new-enterprise-a': '" + token() + "'}"
    raw = (json.dumps({'stderr': line}) + '\n').encode()
    assert len(scan_fixture_contexts(raw, '.jsonl')) == 1


def test_unchanged_mask_and_normal_source_identifiers_are_not_fixture_residuals():
    raw = json.dumps({'failure': '[REDACTED_SYNTHETIC_FIXTURE_REPR]', 'normal_identifier': token(), 'source_sha256': 'c' * 64}).encode()
    assert scan_fixture_contexts(raw, '.json') == []


def test_nested_session_token_list_is_guarded():
    raw = json.dumps(dict(session_tokens=[token()])).encode()
    assert len(scan_fixture_contexts(raw, '.json')) == 1
