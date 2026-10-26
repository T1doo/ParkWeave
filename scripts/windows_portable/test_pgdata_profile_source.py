"""Pure profile/path formats, real owner buffers and isolated refusal checks.

No DPAPI, native ACL/token setter, Windows handle, PG or credential operation.
"""
import ast
from copy import deepcopy
import ctypes as C
from pathlib import Path
import struct
import unittest

from . import credential_envelope as e, pgdata_candidate as p, restricted_token_candidate as t
from . import fixed_secret_store as s, endpoint_plan as ep
from .test_credential_envelope import binding, payloads
from .test_fixed_secret_store import MemoryFiles, MemoryJournal
from .fixed_directories import FixedDirectoryLease
from .test_windows_user_protection import Buffers
from .windows_user_protection import IsolatedUserProtection


def profile_config():
    b = binding(); cfg = payloads()[e.Purpose.CONFIG]
    parts = b.sid.split('-')
    sid = bytes((1,len(parts)-3))+int(parts[2]).to_bytes(6,'big')+b''.join(struct.pack('<I',int(x)) for x in parts[3:])
    sd = (b.sid,0x9004,p.root_descriptor(sid)[20+len(sid):])
    cfg.update(schema=4,endpoints=dict(schema='parkweave-private-endpoints/1',host='127.0.0.1',database_port=54000,api_port=58000),
        pgdata=dict(profile=p.PROFILE,instance_id=b.instance_id,sid=b.sid,parent_identity=[7,17],
                    root_identity=cfg['database']['data_identity'],root_control=0x9004,
                    root_security_sha256=p.descriptor_digest(sd)))
    return cfg


class PGDataProfileChecks(unittest.TestCase):
    def test_token_owner_real_pointer_buffer_and_unowned_pointers(self):
        sid=b'\x01\x02'+b'\0'*5+b'\x05'+struct.pack('<II',32,544)
        buffer=C.create_string_buffer(8+len(sid)); pointer=C.c_void_p.from_buffer(buffer)
        pointer.value=C.addressof(buffer)+8; C.memmove(pointer.value,sid,len(sid))
        self.assertEqual(t._parse(buffer,len(buffer),4),sid)
        for value in (None,C.addressof(buffer)-1,C.addressof(buffer),C.addressof(buffer)+len(buffer)-7):
            pointer.value=value
            with self.assertRaises(t.TokenRefused):t._parse(buffer,len(buffer),4)
        with self.assertRaises(t.TokenRefused):t._parse(buffer,7,4)

    def test_owner_setter_is_explicit_derived_only_and_fresh_readback_required(self):
        tree=ast.parse(Path(t.__file__).read_text())
        methods={x.name:x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef)}
        setter=methods['prepare_owner']
        self.assertIn('_serialized',[x.id for x in setter.decorator_list])
        calls=[x for x in ast.walk(setter) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='SetTokenInformation']
        self.assertEqual(len(calls),1)
        self.assertEqual(ast.unparse(calls[0].args[0]),'self._derived')
        self.assertEqual(calls[0].args[1].value,4)
        self.assertEqual(ast.unparse(calls[0].args[3]),'C.sizeof(value)')
        reads=[x.lineno for x in ast.walk(setter) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='_read_owner']
        self.assertLess(min(reads),calls[0].lineno); self.assertGreater(max(reads),calls[0].lineno)
        for filename,method in (('initdb_pipe_candidate.py','_owner_sid_held'),('restricted_initdb_candidate.py','_child_token')):
            tree=ast.parse(Path(t.__file__).with_name(filename).read_text())
            node=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name==method)
            self.assertTrue(any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='_read_owner' for x in ast.walk(node)))
        self.assertFalse(t._RestrictedPrimaryCandidate.launch_ready)

    def test_pg_path_exact_extended_dos_subset_and_utf16_length(self):
        self.assertEqual(p.pg_command_path(r'\\?\C:\临时目录\data\postgresql'),
                         ('C:/临时目录/data/postgresql','C:\\',('临时目录','data','postgresql')))
        accepted='\\\\?\\C:\\'+'x'*237
        self.assertEqual(len(p.pg_command_path(accepted)[0]),240)
        for value in (r'C:\private\data',r'\\?\UNC\server\share',r'\\?\Volume{123}\data',
                      r'\\.\C:\data',r'\\?\C:\..\data',r'\\?\C:\data:stream',r'\\?\C:\name.\data',
                      r'\\?\C:\PROGRA~1\data','\\\\?\\C:\\'+'x'*238,'\\\\?\\C:\\'+'😀'*119):
            with self.subTest(value=value),self.assertRaises(Exception):p.pg_command_path(value)

    def test_source_pins_whole_dos_chain_and_guid_root_before_string_use(self):
        tree=ast.parse(Path(p.__file__).read_text())
        methods={x.name:x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef)}
        pin=ast.unparse(methods['_pin_command_path']); verify=ast.unparse(methods['_verify'])
        self.assertIn('self.api.open_drive(drive)',pin)
        self.assertIn('self._open(handle, name, anchor=True)',pin)
        self.assertIn('chain[-1][1] == root_id',pin)
        self.assertIn('binding.command_chain',verify)
        self.assertIn('self._dos_path()[0] == binding.command_path',verify)
        self.assertIn('binding.command_path',ast.unparse(methods['_path_held']))

    def test_schema4_roundtrip_exact_profile_and_closed_version_selection(self):
        cfg=profile_config();fmt=e.ConfigFormat.PGDATA_SCHEMA4
        raw=e.encode_plaintext(binding(),e.Purpose.CONFIG,cfg,config_format=fmt)
        self.assertEqual(e.decode_plaintext(binding(),e.Purpose.CONFIG,raw,config_format=fmt),cfg)
        for old in (e.ConfigFormat.SCHEMA2,e.ConfigFormat.INSTANCE_SCHEMA3):
            with self.assertRaises(e.EnvelopeRefused):e.decode_plaintext(binding(),e.Purpose.CONFIG,raw,config_format=old)
        for purpose in (e.Purpose.DATABASE,e.Purpose.SESSION):
            self.assertEqual(e.encode_plaintext(binding(),purpose,payloads()[purpose]),
                             e.encode_plaintext(binding(),purpose,payloads()[purpose],config_format=fmt))

    def test_schema4_rejects_missing_old_unknown_and_cross_instance_or_physical_roots(self):
        cfg=profile_config()
        variants=[]
        for key,value in (('profile','unknown/2'),('instance_id','22222222-2222-4222-8222-222222222222'),
                          ('sid','S-1-5-18'),('parent_identity',[8,17]),('parent_identity',[7,11]),
                          ('parent_identity',[7,16]),('root_identity',[7,99]),('root_control',0x8404),
                          ('parent_identity',[7,0]),
                          ('root_control',True),('root_security_sha256','f'*64)):
            bad=deepcopy(cfg);bad['pgdata'][key]=value;variants.append(bad)
        bad=deepcopy(cfg);del bad['pgdata'];variants.append(bad)
        bad=deepcopy(cfg);bad['pgdata']['verified']=True;variants.append(bad)
        bad=deepcopy(cfg);del bad['endpoints'];variants.append(bad)
        for bad in variants:
            with self.assertRaises(e.EnvelopeRefused):
                e.encode_plaintext(binding(),e.Purpose.CONFIG,bad,config_format=e.ConfigFormat.PGDATA_SCHEMA4)

    def test_schema4_store_rejects_json_target_before_config_write(self):
        fs=MemoryJournal();lease=FixedDirectoryLease(fs,fs.record,fs.snapshot)
        # Existing isolated IO, explicit synthetic values, no new filesystem seam.
        api=MemoryFiles(lease);crypto=Buffers()
        store=s.IsolatedFixedSecretStore(lease,binding(),api,IsolatedUserProtection(crypto),config_format=e.ConfigFormat.PGDATA_SCHEMA4)
        # Validate the actual callback's origin gate before any file operation.
        callback=store._config_writer(profile_config()['database'],profile_config()['runtime'],ep.InstanceEndpointPlan(),profile_config()['pgdata'])
        with self.assertRaises(p.DataRefused):callback(object())
        self.assertEqual(api.events,[]);self.assertEqual(crypto.calls,[])

    def test_isolated_schema4_never_issues_native_reopen_authentication(self):
        fs=MemoryJournal();lease=FixedDirectoryLease(fs,fs.record,fs.snapshot)
        api=MemoryFiles(lease);crypto=Buffers()
        store=s.IsolatedFixedSecretStore(lease,binding(),api,IsolatedUserProtection(crypto),config_format=e.ConfigFormat.PGDATA_SCHEMA4)
        with self.assertRaises(s.StoreRefused):store._authenticate_existing_held()
        with self.assertRaises(s.StoreRefused):store.read_existing_with_endpoint_plan()
        self.assertEqual(api.events,[]);self.assertEqual(crypto.calls,[])
        with self.assertRaises(p.DataRefused):p.native_pgdata()


if __name__=='__main__':unittest.main()
