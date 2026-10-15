"""Hash-only scan of structured exported synthetic fixture contexts."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET

QUOTED = re.compile(r"['\"]([A-Za-z0-9_-]{43})['\"]")
WHOLE = re.compile(r'[A-Za-z0-9_-]{43}\Z')
CONTEXT = re.compile(r'^\s*(?:\w+\s*=\s*[({].*Store object at 0x|(?:tokens|session_tokens|template_consumption)\s*=\s*[({])')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def scan_fixture_contexts(raw, suffix):
    findings = []

    def text(value, location, token_map=False):
        if token_map and WHOLE.fullmatch(value):
            findings.append(dict(kind='unredacted_token_map_value', location=location, value_sha256=digest(value)))
        for number, line in enumerate(value.splitlines(), 1):
            if not CONTEXT.match(line):
                continue
            matches = list(QUOTED.finditer(line))
            if 'Store object at 0x' in line:
                findings.append(dict(kind='unmasked_original_fixture_repr', location=location, line=number, line_sha256=digest(line)))
            for match in matches:
                findings.append(dict(kind='complete_session_candidate_in_fixture_context', location=location,
                    line=number, value_sha256=digest(match.group(1)), line_sha256=digest(line)))

    def walk(value, location='$', token_map=False):
        if isinstance(value, str):
            text(value, location, token_map)
        elif isinstance(value, dict):
            for key, child in value.items():
                walk(child, location + '.' + key, token_map or key in {'tokens', 'session_tokens'})
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, location + '[' + str(index) + ']', token_map)

    decoded = raw.decode('utf-8')
    if suffix == '.xml':
        for index, node in enumerate(ET.fromstring(raw).iter()):
            if node.text:
                text(node.text, 'xml[' + str(index) + '].text')
            if node.tail:
                text(node.tail, 'xml[' + str(index) + '].tail')
            for key, value in node.attrib.items():
                text(value, 'xml[' + str(index) + '].@' + key)
    elif suffix == '.json':
        walk(json.loads(decoded))
    elif suffix == '.jsonl':
        for number, line in enumerate(decoded.splitlines(), 1):
            if line.strip():
                walk(json.loads(line), '$line' + str(number))
    else:
        text(decoded, '$text')
    return findings
