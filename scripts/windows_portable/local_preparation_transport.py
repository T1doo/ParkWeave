"""Bounded original-API transport; no admission, credential creation or retries.

Only invoked inside an already admitted running Controller callback. Real
endpoint ownership still requires the original native adapter implementation;
unit socket ports cannot grant that authority.
"""
import json
import math
import re
import socket
import time

from .application_readiness import ExistingActorProbe, RegisteredApplication
from .controller import CandidateRefused
from .processes import PrivateProcessAdapter

UUID_PATH = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class OwnedPreparationRequest:
    """One owned connection; bearer is sent only after endpoint verification."""

    def request(self, application, actor, method, path, body, request_key, deadline):
        if (type(application) is not RegisteredApplication
                or type(application.adapter) is not PrivateProcessAdapter
                or application.api is application.worker or type(actor) is not ExistingActorProbe
                or type(application.port) is not int or not 1 <= application.port <= 65535
                or type(deadline) not in (int, float) or not math.isfinite(deadline)
                or not 0 < deadline - time.monotonic() <= 30):
            raise CandidateRefused('bounded original application request required')
        actor.expected()
        reads = re.fullmatch('/api/(?:runs/' + UUID_PATH + '|preparations/' + UUID_PATH + ')', path)
        recovery = re.fullmatch('/api/preparations/' + UUID_PATH + '/command-recovery', path)
        writes = path in ('/api/runs', '/api/preparations') or re.fullmatch(
            '/api/preparations/' + UUID_PATH + '/commands', path)
        if method == 'GET':
            if (not (reads or recovery) or body is not None
                    or (recovery and (type(request_key) is not str
                                      or re.fullmatch(UUID_PATH, request_key) is None))
                    or (not recovery and request_key is not None)):
                raise CandidateRefused('fixed preparation read required')
            encoded = b''
        elif method == 'POST':
            if (not writes or type(body) is not dict or type(request_key) is not str
                    or re.fullmatch('[A-Za-z0-9_-]{1,100}', request_key) is None):
                raise CandidateRefused('fixed explicit preparation write required')
            encoded = json.dumps(body, ensure_ascii=False, allow_nan=False,
                                 separators=(',', ':')).encode('utf-8')
            if len(encoded) > 16384:  # Same existing API middleware limit.
                raise CandidateRefused('request exceeds original 16 KiB limit')
        else:
            raise CandidateRefused('only original preparation GET/POST supported')

        def remaining():
            left = deadline - time.monotonic()
            if left <= 0:
                raise CandidateRefused('owned preparation request deadline')
            return min(.3, left)

        adapter = application.adapter
        adapter.require_endpoint_support(application.api)
        tokens = (application.api, application.worker)
        identities = tuple(adapter.live_identity(token) for token in tokens)

        def unchanged():
            remaining()
            if tuple(adapter.live_identity(token) for token in tokens) != identities:
                raise CandidateRefused('original application process identity changed')

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(remaining())
            connection.connect(('127.0.0.1', application.port))
            # Same original live capability/connected socket check as readiness.
            # No bearer or request body has been sent before this returns.
            adapter.verify_api_connection(application.api, connection)
            unchanged()
            headers = [f'{method} {path} HTTP/1.1', f'Host: 127.0.0.1:{application.port}',
                       'Authorization: Bearer ' + actor.bearer,
                       'Content-Type: application/json', 'Connection: close',
                       'Content-Length: ' + str(len(encoded))]
            if request_key is not None:
                headers.append('Idempotency-Key: ' + request_key)
            payload = ('\r\n'.join(headers) + '\r\n\r\n').encode('ascii') + encoded
            connection.settimeout(remaining())
            connection.sendall(payload)  # Single attempt; unknown send is never repeated.
            raw, length, status = bytearray(), None, None
            while True:
                connection.settimeout(remaining())
                chunk = connection.recv(4096)
                if not chunk:
                    raise CandidateRefused('preparation response incomplete')
                raw.extend(chunk)
                if length is None:
                    split = raw.find(b'\r\n\r\n')
                    if split < 0:
                        if len(raw) > 8192:
                            raise CandidateRefused('preparation response header limit')
                        continue
                    if split > 8192:
                        raise CandidateRefused('preparation response header limit')
                    lines = bytes(raw[:split]).split(b'\r\n')
                    first = lines[0].split(b' ', 2)
                    if (len(lines) > 50 or len(first) != 3
                            or first[0] not in (b'HTTP/1.0', b'HTTP/1.1')
                            or not re.fullmatch(b'[1-5][0-9]{2}', first[1])):
                        raise CandidateRefused('preparation response status invalid')
                    status = int(first[1])
                    headers = {}
                    for line in lines[1:]:
                        name, separator, value = line.partition(b':')
                        name = name.lower()
                        if not separator or name in headers or not re.fullmatch(b'[a-z0-9-]+', name):
                            raise CandidateRefused('preparation response headers invalid')
                        headers[name] = value.strip()
                    if (b'transfer-encoding' in headers or b'content-encoding' in headers
                            or headers.get(b'content-type', b'').split(b';')[0] != b'application/json'
                            or headers.get(b'cache-control') != b'no-store'
                            or not re.fullmatch(b'[0-9]{1,7}', headers.get(b'content-length', b''))):
                        raise CandidateRefused('bounded no-store JSON framing required')
                    length = int(headers[b'content-length'])
                    if not 0 < length <= 1_000_000:
                        raise CandidateRefused('preparation response body limit')
                    raw = raw[split + 4:]
                if len(raw) > length:
                    raise CandidateRefused('preparation response extra bytes')
                if len(raw) == length:
                    break
            unchanged()

        expected = 200 if method == 'GET' or path.endswith('/commands') else (
            202 if path == '/api/runs' else 201)
        if status != expected:
            # No remote error body/private data in the surfaced message.
            raise CandidateRefused('original preparation API refused status ' + str(status))

        def reject_constant(value):
            raise CandidateRefused('non-finite preparation JSON refused')

        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise CandidateRefused('duplicate preparation JSON keys refused')
                result[key] = value
            return result

        result = json.loads(bytes(raw).decode('utf-8'), parse_constant=reject_constant,
                            object_pairs_hook=unique_pairs)
        if type(result) is not dict:
            raise CandidateRefused('preparation JSON object required')
        remaining()
        return result
