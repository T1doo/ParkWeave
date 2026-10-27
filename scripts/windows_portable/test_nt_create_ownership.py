"""Pure status/local pointer-lifetime checks. No native call or real handle."""
import ast
import ctypes as C
from pathlib import Path
from types import SimpleNamespace
import unittest

from parkweave import windows_handles as w
from parkweave.store import Denied
from .windows_directory_handles import NativeLeaseAPI
from .directories import LeaseRefused
from . import native_secret_store_candidate as files,pgdata_candidate as data,native_layout_candidate as layout


class NtCreateOwnershipChecks(unittest.TestCase):
    def reader(self,kind,status,*,out=123,close_error=False):
        calls=[];closed=[];pointers=[]
        def create(handle,*args):
            calls.append(status);pointers.append((handle,args[2]))
            C.cast(handle,C.POINTER(C.c_void_p))[0]=out
            return status
        def close(handle):
            closed.append(handle)
            if close_error:raise OSError('INJECTED_OWNED_CLOSE')
        if kind=='readonly':
            api=object.__new__(w.WinAPI);api.ntcreate=create;api.close=close
            read=lambda:api.open_relative(321,'files',False)
            raw=api
        else:
            api=object.__new__(NativeLeaseAPI);raw=SimpleNamespace(ntcreate=create,close=close)
            api.readonly=raw
            read=lambda:api.relative_file(321,'file')
        return api,raw,read,calls,closed,pointers

    def test_failed_warning_unsigned_or_signed_status_never_closes_unowned_out(self):
        for kind in ('readonly','lease'):
            for status in (0xc0000022,C.c_int32(0xc0000022).value,0x80000005):
                with self.subTest(kind=kind,status=status):
                    _,_,read,calls,closed,_=self.reader(kind,status)
                    with self.assertRaises((Denied,LeaseRefused)):read()
                    self.assertEqual(closed,[]);self.assertEqual(len(calls),1)

    def test_normal_success_and_completed_information_keep_distinct_admission(self):
        for kind in ('readonly','lease'):
            _,_,read,_,closed,_=self.reader(kind,0)
            self.assertEqual(read(),123);self.assertEqual(closed,[])
            _,_,read,_,closed,_=self.reader(kind,0x40000000)
            with self.assertRaises((Denied,LeaseRefused)):read()
            self.assertEqual(closed,[123])
            for out in (None,0,C.c_void_p(-1).value,C.c_void_p(-2).value):
                _,_,read,_,closed,_=self.reader(kind,0,out=out)
                with self.assertRaises((Denied,LeaseRefused)):read()
                self.assertEqual(closed,[])

    def test_completed_success_refusal_and_close_error_both_survive(self):
        for kind in ('readonly','lease'):
            _,_,read,_,closed,_=self.reader(kind,0x40000000,close_error=True)
            with self.assertRaises(BaseExceptionGroup) as caught:read()
            self.assertEqual(len(caught.exception.exceptions),2)
            self.assertIsInstance(caught.exception.exceptions[1],OSError)
            self.assertEqual(closed,[123])

    def test_pending_retains_all_original_storage_and_refuses_reentry(self):
        for kind in ('readonly','lease'):
            _,raw,read,calls,closed,pointers=self.reader(kind,0x103)
            before=set(w._NT_CREATE_PENDING)
            try:
                with self.assertRaises((Denied,LeaseRefused)):read()
                added=set(w._NT_CREATE_PENDING)-before;self.assertEqual(len(added),1)
                record=w._NT_CREATE_PENDING[next(iter(added))]
                self.assertIs(record[0],raw)
                # Original output objects remain alive and writable even after
                # the call frame returned. This is local memory, not kernel IO.
                self.assertEqual(C.addressof(record[1]),C.addressof(C.cast(pointers[0][0],C.POINTER(C.c_void_p)).contents))
                record[1].value=456;record[2].Information=7
                self.assertEqual(C.cast(pointers[0][0],C.POINTER(C.c_void_p))[0],456)
                self.assertEqual(record[3].ObjectName.contents.Length,record[4].Length)
                with self.assertRaises(Denied):read()
                self.assertEqual(len(calls),1);self.assertEqual(closed,[])
            finally:
                # Explicitly known test doubles: no actual operation was issued.
                for key in set(w._NT_CREATE_PENDING)-before:w._NT_CREATE_PENDING.pop(key)

    def test_native_secret_information_success_is_registered_then_closed_not_accepted(self):
        owner=object.__new__(files._NativeSecretFiles)
        owner._gate=lambda:None;owner.lease=SimpleNamespace(fs=SimpleNamespace(root=321))
        owner._parent_cap=None;owner.caps={};owner.failed=False;owner.unknown=[]
        calls=[]
        def create(handle,*args):C.cast(handle,C.POINTER(C.c_void_p))[0]=123;return 0x40000000
        owner.api=SimpleNamespace(readonly=SimpleNamespace(),ntcreate=create,close=lambda handle:calls.append(handle))
        with self.assertRaises(Exception):owner._open(321,'secrets',directory=True,create=False)
        self.assertTrue(owner.failed);self.assertEqual(calls,[123])
        self.assertTrue(all(row.close_attempted for row in owner.caps.values()))

    def test_all_three_native_call_sites_share_pending_and_completed_classification(self):
        for module,method in ((data,'_open'),(files,'_open'),(layout,'_create')):
            tree=ast.parse(Path(module.__file__).read_text())
            fn=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name==method and
                    any(isinstance(y,ast.Call) and isinstance(y.func,ast.Attribute) and y.func.attr=='ntcreate' for y in ast.walk(x)))
            names={x.func.id for x in ast.walk(fn) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)}
            self.assertTrue({'nt_status','completed_nt_handle','require_nt_create_ready','retain_pending_nt_create'}<=names)


if __name__=='__main__':unittest.main()
