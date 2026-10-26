"""Bytes/ABI/source and negative ownership checks only; native NOT_RUN.

Negative tests corrupt private registries deliberately; they never mint a
successful native authentication result or substitute fake DPAPI evidence.
"""
import ast
from copy import copy,deepcopy
import ctypes as C
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import struct

from . import native_secret_store_candidate as n, fixed_secret_store as s, pgdata_candidate as p
from .fixed_directories import FixedDirectoryLease
from . import dpapi_native_candidate as dp, credential_envelope as e, endpoint_plan as ep
from parkweave.windows_handles import WinAPI,PTR
from parkweave.store import Denied
from .windows_directory_handles import NativeLeaseAPI


class NativeSecretSourceChecks(unittest.TestCase):
    def _allocation_reader(self,kind,*,primary=False,free_failure=True):
        calls=[];sd=C.create_string_buffer(32)
        acl=C.create_string_buffer(struct.pack('<BBHHH',2,0,8,0,0))
        text=C.create_unicode_buffer('S-1-5-18')
        def need(ok):
            if not ok:raise Denied('INJECTED_QUERY_FAILURE')
        def getsecurity(handle,object_kind,flags,owner,group,dacl,sacl,out):
            C.cast(owner,C.POINTER(PTR))[0]=PTR(123)
            C.cast(out,C.POINTER(PTR))[0]=PTR(C.addressof(sd))
            if kind=='descriptor':C.cast(dacl,C.POINTER(PTR))[0]=PTR(C.addressof(acl))
            return 0
        def free(pointer):calls.append('free');return 123 if free_failure else None
        api=object.__new__(WinAPI)
        api.need=need;api.getsecurity=getsecurity;api.valid_sd=lambda p:not primary
        api.valid_acl=lambda p:True;api.control=lambda *args:1
        api.sid=lambda p:'S-1-5-18';api.localfree=free
        if kind=='sid':
            api.valid_sid=lambda p:True
            def sidstring(pointer,out):
                C.cast(out,C.POINTER(PTR))[0]=PTR(C.addressof(text));return 1
            api.sidstring=sidstring
            # Retain real owned buffers in closure; no Windows allocation/call.
            def read():return WinAPI.sid(api,123)
        elif kind=='security':
            def read():return WinAPI.security(api,123)
        else:
            native=object.__new__(NativeLeaseAPI)
            native.readonly=api
            def read():return NativeLeaseAPI.descriptor(native,123)
        return read,calls

    def test_localfree_nonnull_refuses_all_three_actual_reader_methods(self):
        for kind in ('sid','security','descriptor'):
            with self.subTest(kind=kind):
                read,calls=self._allocation_reader(kind)
                with self.assertRaises(Exception):read()
                self.assertEqual(calls,['free'])
                read,calls=self._allocation_reader(kind,free_failure=False)
                self.assertIsNotNone(read());self.assertEqual(calls,['free'])

    def test_security_query_primary_and_free_failure_are_both_preserved(self):
        for kind in ('security','descriptor'):
            with self.subTest(kind=kind):
                read,calls=self._allocation_reader(kind,primary=True)
                with self.assertRaises(BaseExceptionGroup) as caught:read()
                self.assertEqual(len(caught.exception.exceptions),2)
                self.assertIn('INJECTED_QUERY_FAILURE',str(caught.exception.exceptions[0]))
                self.assertEqual(calls,['free'])

    def test_actual_private_file_descriptor_has_protected_explicit_user_only_acl(self):
        sid=b'\x01\x02'+b'\0'*5+b'\x05'+struct.pack('<II',32,544)
        raw=n.private_file_descriptor(sid)
        self.assertEqual(struct.unpack_from('<BBHIIII',raw),(1,0,0x9004,20,0,0,20+len(sid)))
        ace=raw[20+len(sid)+8:]
        self.assertEqual(struct.unpack_from('<BBHI',ace),(0,0,len(sid)+8,0x1f01ff))
        self.assertEqual(ace[8:],sid)
        self.assertEqual(C.sizeof(n.ObjectAttributes),48);self.assertEqual(C.sizeof(n.IOStatus),16)

    def test_fake_capability_and_unregistered_native_ticket_cannot_enter_native_domain(self):
        operation=object.__new__(n._NativeOperation)
        operation.store=SimpleNamespace(api=SimpleNamespace(caps={}))
        for cap in (s.FakeCapability(),object(),n._NativeCapability()):
            with self.assertRaises(s.StoreRefused):operation._admit_cap(cap)
        lease=object.__new__(FixedDirectoryLease)
        lease._operation_owner=get_ident();lease._operation_depth=1
        for token in (object(),{},n._Ticket()):
            with self.assertRaises(s.StoreRefused):n._consume_ticket(lease,token,'PGDATA')
        for token in (n._Ticket(),n.RecoveredInstance()):
            for transfer in (copy,deepcopy):
                with self.assertRaises(TypeError):transfer(token)

    def test_foreign_recovery_result_is_not_consumed_or_cleaned(self):
        lease=object.__new__(FixedDirectoryLease)
        lease._operation_owner=get_ident();lease._operation_depth=1
        store=object.__new__(n._NativeFixedSecretStore);store.lease=lease
        token=n.RecoveredInstance();foreign=object();n._recoveries[token]=(foreign,)
        with self.assertRaises(s.StoreRefused):store._consume_recovered_held(token)
        self.assertIs(n._recoveries[token][0],foreign)

    def test_failed_dpapi_out_pointer_is_never_sized_read_or_freed(self):
        native=object.__new__(dp._NativeDPAPI);native.failed=False;calls=[]
        def failed(source,descr,entropy,reserved,prompt,flags,out):
            output=C.cast(out,C.POINTER(dp.DataBlob)).contents
            output.pbData=1;output.cbData=4
            return 0  # An arbitrary failure output, not an owned allocation.
        native._unprotect=failed
        native._size=lambda ptr:calls.append('size')
        native._free=lambda ptr:calls.append('free')
        with patch.object(C,'get_last_error',return_value=5,create=True):
            with self.assertRaises(dp.NativeFailure) as caught:
                native.unprotect(b'SYNTHETIC_CIPHER',b'e'*32)
        self.assertEqual(calls,[])
        self.assertTrue(native.failed)
        self.assertIn('FAILED_OUTPUT_OWNERSHIP_UNKNOWN',caught.exception.cleanup_types)

    def test_native_source_closes_without_lease_and_reopen_only_opens_existing_names(self):
        tree=ast.parse(Path(n.__file__).read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='_NativeSecretFiles')
        self.assertFalse(cls.bases)
        methods={x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
        closed=ast.unparse(methods['close'])
        self.assertNotIn('_gate',closed);self.assertNotIn('_verify',closed)
        self.assertIn('row.close_attempted = True',closed)
        owner=ast.unparse(methods['current_sid_bytes'])
        self.assertIn('self.open_thread(self.thread(), 8, True',owner)
        self.assertIn('need(error == 1008)',owner)
        self.assertNotIn('RevertToSelf',owner)
        self.assertEqual([x.value for x in ast.walk(methods['_open']) if isinstance(x,ast.Constant) and x.value=='secrets'],['secrets'])
        tree=ast.parse(Path(p.__file__).read_text())
        recover=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_recover_held')
        opens=[x for x in ast.walk(recover) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='_open']
        self.assertEqual(len(opens),2)
        self.assertTrue(all(not any(k.arg=='create' for k in x.keywords) for x in opens))
        self.assertFalse(n._NativeFixedSecretStore.launch_ready)
        with self.assertRaises(s.StoreRefused):n.native_secret_store()

    def test_only_closed_real_read_context_reaches_native_ticket_registration(self):
        tree=ast.parse(Path(n.__file__).read_text())
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='_NativeFixedSecretStore')
        method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_finalize_closed')
        consume=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='consume_read_state')
        stores=[x for x in ast.walk(method) if isinstance(x,ast.Assign) and any('_tickets[' in ast.unparse(y) for y in x.targets)]
        self.assertTrue(stores);self.assertTrue(all(consume.lineno<x.lineno for x in stores))
        register=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='_register_held')
        self.assertEqual([k.arg for k in register.keywords],['native_recovery'])
        # Actual generic read/close finalization remains in the shared algorithm.
        tree=ast.parse(Path(s.__file__).read_text())
        method=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='_operate_held')
        close=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and ast.unparse(x.func)=='self.api.close')
        final=next(x for x in ast.walk(method) if isinstance(x,ast.Call) and ast.unparse(x.func)=='self._finalize_closed')
        self.assertLess(close.lineno,final.lineno)

    def test_failed_first_native_recovery_check_is_consumed_and_poisoned(self):
        lease=object.__new__(FixedDirectoryLease)
        lease._operation_owner=get_ident();lease._operation_depth=1;lease.poisoned=False
        store=object.__new__(n._NativeFixedSecretStore);store.lease=lease;store.failed=False
        target=object.__new__(p._NewDataTarget)
        target.lease=lease;target.handles=[];target.cleanup_errors=[];target.failed=target.closed=False
        def refuse():raise s.StoreRefused('SYNTHETIC_CURRENT_USER_DRIFT')
        store._native_check=refuse
        token=n.RecoveredInstance()
        n._recoveries[token]=(store,object(),s.PrivateState({}, {}, {}),object(),target,b'')
        with self.assertRaises(s.StoreFailure):store._consume_recovered_held(token)
        self.assertNotIn(token,n._recoveries)
        self.assertTrue(store.failed and lease.poisoned and target.failed and target.closed)


if __name__=='__main__':unittest.main()
