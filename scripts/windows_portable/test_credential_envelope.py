"""Pure in-memory format fixtures, not credentials or filesystem acceptance."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from . import credential_envelope as e


def binding():
    return e.InstanceBinding('11111111-1111-4111-8111-111111111111', 'S-1-5-21-1-2-3-1001',
                             (7, 11), (7, 12), (7, 13))


def payloads():
    return {
        e.Purpose.DATABASE: {'postgres': 'SYNTHETIC_OWNER_NOT_A_REAL_PASSWORD', 'parkweave_app': 'SYNTHETIC_APP_NOT_A_REAL_PASSWORD'},
        e.Purpose.SESSION: {k: 'SYNTHETIC_SESSION_'+k for k in ('fixture-a', 'fixture-b', 'fixture-c')},
        e.Purpose.CONFIG: dict(schema=2,
            files={name: dict(identity=[7, i], ciphertext_sha256=str(i % 10)*64)
                   for name, i in (('DATABASE', 14), ('SESSION', 15))},
            database=dict(system_identifier='123456789', database_oid=1234, database_name='parkweave',
                          owner='postgres', data_identity=[7, 16], schema_version=32),
            runtime=dict(source_commit='1'*40, manifest_sha256='2'*64))}


class EnvelopeChecks(unittest.TestCase):
    def test_all_closed_purposes_roundtrip_and_separate_entropy(self):
        b = binding()
        for purpose, payload in payloads().items():
            with self.subTest(purpose=purpose):
                raw = e.encode_plaintext(b, purpose, payload)
                self.assertEqual(e.decode_plaintext(b, purpose, raw), payload)
                self.assertEqual(raw, e.canonical(json.loads(raw)))
        self.assertEqual(len({e.entropy_bytes(b, p) for p in e.Purpose}), 3)
        self.assertNotIn(b.sid, repr(b))

    def test_binding_and_purpose_mismatch(self):
        b = binding(); purpose = e.Purpose.DATABASE
        raw = e.encode_plaintext(b, purpose, payloads()[purpose])
        for other in (replace(b, instance_id='22222222-2222-4222-8222-222222222222'),
                      replace(b, sid='S-1-5-21-1-2-3-1002'), replace(b, root=(7, 21)),
                      replace(b, lock=(7, 22)), replace(b, journal=(7, 23)),
                      replace(b, product='OtherProduct'), replace(b, version=2)):
            with self.subTest(binding_field_mismatch=True), self.assertRaises(e.EnvelopeRefused):
                e.decode_plaintext(other, purpose, raw)
        for other in (e.Purpose.SESSION, e.Purpose.CONFIG, 'DATABASE', None):
            with self.subTest(purpose=other), self.assertRaises(e.EnvelopeRefused):
                e.decode_plaintext(b, other, raw)

    def test_invalid_binding_types_aliases_and_extreme_values(self):
        b = binding()
        for other in (replace(b, version=True), replace(b, root=(True, 11)),
                      replace(b, lock=b.root), replace(b, journal=(8, 13)),
                      replace(b, root=(7, 2**64)), replace(b, root=[7, 11]),
                      replace(b, instance_id=b.instance_id.upper().replace('1', 'A', 1)),
                      replace(b, instance_id='x'*10000), replace(b, sid='S-1-'+'9'*10000),
                      replace(b, sid='S-1-5-01'), replace(b, sid='S-1-5-'+str(2**32))):
            with self.subTest(invalid_binding=True), self.assertRaises(e.EnvelopeRefused):
                other.record()

    def test_strict_json_duplicate_keys_canonical_encoding_and_size(self):
        b = binding(); purpose = e.Purpose.DATABASE
        raw = e.encode_plaintext(b, purpose, payloads()[purpose])
        damaged = [b'', b'x'*(e.MAX_PLAINTEXT+1), bytearray(raw), b'\xff', raw+b'\n',
                   raw.replace(b'"version":1', b'"version":true'),
                   raw.replace(b'"schema":', b'"schema":0,"schema":', 1),
                   raw.replace(b'"postgres":', b'"postgres":0,"postgres":', 1)]
        value = json.loads(raw)
        for key in ('generation', 'sequence', 'postmaster_start'):
            changed = deepcopy(value); changed['binding'][key] = 1; damaged.append(e.canonical(changed))
        for data in damaged:
            with self.subTest(invalid_bytes=True), self.assertRaises(e.EnvelopeRefused):
                e.decode_plaintext(b, purpose, data)

    def test_corrupt_payload_hash_and_unexpected_fields(self):
        b = binding(); purpose = e.Purpose.DATABASE
        value = json.loads(e.encode_plaintext(b, purpose, payloads()[purpose]))
        changed = deepcopy(value); changed['payload']['postgres'] += '_DAMAGED'
        extra = deepcopy(value); extra['unknown'] = True
        wrong_hash = deepcopy(value); wrong_hash['payload_sha256'] = 'f'*64
        for item in (changed, extra, wrong_hash):
            with self.subTest(corrupted_record=True), self.assertRaises(e.EnvelopeRefused):
                e.decode_plaintext(b, purpose, e.canonical(item))

    def test_payload_constraints_and_config_never_self_references(self):
        b = binding(); all_payloads = payloads()
        bad = [(e.Purpose.DATABASE, dict(postgres='x', parkweave_app=True)),
               (e.Purpose.DATABASE, dict(postgres='x'*513, parkweave_app='x')),
               (e.Purpose.DATABASE, dict(postgres='\ud800', parkweave_app='x')),
               (e.Purpose.DATABASE, dict(postgres='x\n', parkweave_app='x')),
               (e.Purpose.SESSION, dict.fromkeys(('fixture-a', 'fixture-b', 'fixture-c'), 'SYNTHETIC_DUPLICATE')),
               (e.Purpose.SESSION, dict(enterprise='x', specialist='y', executor='z'))]
        for mutation in ('self_reference', 'own_hash', 'alias', 'bool_schema', 'bool_oid', 'unstable_start', 'unknown_path', 'foreign_volume'):
            value = deepcopy(all_payloads[e.Purpose.CONFIG])
            if mutation == 'self_reference': value['files']['CONFIG'] = value['files']['DATABASE']
            elif mutation == 'own_hash': value['ciphertext_sha256'] = '0'*64
            elif mutation == 'alias': value['files']['SESSION']['identity'] = value['files']['DATABASE']['identity']
            elif mutation == 'bool_schema': value['schema'] = True
            elif mutation == 'bool_oid': value['database']['database_oid'] = True
            elif mutation == 'unstable_start': value['database']['postmaster_start'] = 'SYNTHETIC'
            elif mutation == 'unknown_path': value['files']['DATABASE']['path'] = 'other'
            else: value['files']['DATABASE']['identity'][0] = 8
            bad.append((e.Purpose.CONFIG, value))
        for purpose, payload in bad:
            with self.subTest(purpose=purpose), self.assertRaises(e.EnvelopeRefused) as raised:
                e.encode_plaintext(b, purpose, payload)
            self.assertEqual(str(raised.exception), 'PRIVATE_ENVELOPE_REFUSED')


if __name__ == '__main__':
    unittest.main()
