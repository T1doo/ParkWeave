"""Fixed disposable interruption child: ONLY its inherited stdout file cap."""
import base64
import ctypes as C
import os
import sys
import zlib


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    stages=('BEFORE_WRITE','PARTIAL_WRITE','BEFORE_FLUSH','AFTER_FLUSH')
    if os.name!='nt' or len(args)!=2 or args[0] not in stages or len(args[1])>12000:return 2
    compressed=base64.b64decode(args[1],validate=True);decoder=zlib.decompressobj()
    raw=decoder.decompress(compressed,8193)
    if len(raw)!=8192 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:return 2
    import msvcrt
    msvcrt.setmode(1,os.O_BINARY)
    h=msvcrt.get_osfhandle(1)
    k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
    k.GetFileType.argtypes,k.GetFileType.restype=[C.c_void_p],C.c_uint32
    k.FlushFileBuffers.argtypes,k.FlushFileBuffers.restype=[C.c_void_p],C.c_int32
    k.SetFilePointerEx.argtypes,k.SetFilePointerEx.restype=[C.c_void_p,C.c_int64,C.c_void_p,C.c_uint32],C.c_int32
    k.Sleep.argtypes,k.Sleep.restype=[C.c_uint32],None
    if k.GetFileType(h)!=1 or not k.SetFilePointerEx(h,0,None,0):return 2
    if args[0]!='BEFORE_WRITE':
        data=raw[:317] if args[0]=='PARTIAL_WRITE' else raw
        if os.write(1,data)!=len(data):return 2
    if args[0]=='AFTER_FLUSH' and not k.FlushFileBuffers(h):return 2
    frame=('PW_SLOT_INTERRUPTION/1 '+args[0]+' '+str(os.getpid())+'\n').encode('ascii')
    if os.write(2,frame)!=len(frame):return 2
    k.Sleep(0xffffffff)  # Only the original owning Job coordinator ends this child.
    return 2


if __name__=='__main__':raise SystemExit(main())
