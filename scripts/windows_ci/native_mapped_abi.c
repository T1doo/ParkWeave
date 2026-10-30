/* Compile-only Windows AMD64 ABI check. Never a native execution result. */
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#include <wintrust.h>
#include <mscat.h>
#include <stddef.h>
_Static_assert(sizeof(DEBUG_EVENT)==176,"DEBUG_EVENT size");
_Static_assert(offsetof(DEBUG_EVENT,u)==16,"DEBUG_EVENT union");
_Static_assert(sizeof(EXCEPTION_RECORD)==152,"EXCEPTION_RECORD size");
_Static_assert(sizeof(CREATE_PROCESS_DEBUG_INFO)==72,"process event size");
_Static_assert(sizeof(LOAD_DLL_DEBUG_INFO)==40,"DLL event size");
_Static_assert(sizeof(CREATE_THREAD_DEBUG_INFO)==24,"thread event size");
_Static_assert(sizeof(FILE_ID_INFO)==24,"original file identity size");
_Static_assert(offsetof(JOBOBJECT_BASIC_PROCESS_ID_LIST,ProcessIdList)==8,"Job PID layout");
_Static_assert(sizeof(CATALOG_INFO)==524,"catalog info UTF16 layout");
_Static_assert(sizeof(WINTRUST_CATALOG_INFO)==72,"catalog trust size");
_Static_assert(offsetof(WINTRUST_CATALOG_INFO,pcCatalogContext)==56,"catalog CTL pointer");
_Static_assert(offsetof(WINTRUST_CATALOG_INFO,hCatAdmin)==64,"catalog admin pointer");
/* Pinned Zig/MinGW wintrust.h omits the modern pSignatureSettings tail.
   Verify its complete common prefix, then the documented pointer extension:
   https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data
   A Microsoft SDK build additionally checks its actual modern declaration. */
typedef struct {
    DWORD size;
    PVOID policy,sip;
    DWORD ui,revocation,choice;
    PVOID subject;
    DWORD action;
    HANDLE state;
    PVOID url;
    DWORD flags,context;
    PVOID settings;
} ParkWeaveModernTrust;
_Static_assert(offsetof(WINTRUST_DATA,pFile)==offsetof(ParkWeaveModernTrust,subject),"trust subject prefix");
_Static_assert(offsetof(WINTRUST_DATA,dwStateAction)==offsetof(ParkWeaveModernTrust,action),"trust action prefix");
_Static_assert(offsetof(WINTRUST_DATA,hWVTStateData)==offsetof(ParkWeaveModernTrust,state),"trust state prefix");
_Static_assert(offsetof(WINTRUST_DATA,dwUIContext)==offsetof(ParkWeaveModernTrust,context),"trust context prefix");
_Static_assert(sizeof(ParkWeaveModernTrust)==88,"modern WinTrust union ABI");
_Static_assert(offsetof(ParkWeaveModernTrust,settings)==80,"modern WinTrust signature settings");
#ifndef __MINGW32__
_Static_assert(sizeof(WINTRUST_DATA)==sizeof(ParkWeaveModernTrust),"Microsoft SDK modern WinTrust ABI");
#endif
/* Field-order layout facts from fixed phnt ntpebteb.h 53fbbdc5..., not a
   Microsoft stable ABI promise or observed platform acceptance. */
typedef struct {
    BYTE initial[4];
    HANDLE mutant;
    PVOID image_base,ldr,parameters,subsystem,heap,fast_lock,atl_list;
    HANDLE ifeo;
    ULONG cross_flags;
    PVOID kernel_callback;
    ULONG system_reserved,atl_list32;
    PVOID api_set;
} ParkWeaveTrialPebPrefix;
_Static_assert(offsetof(ParkWeaveTrialPebPrefix,api_set)==0x68,"reviewed AMD64 PEB prefix");
static BOOL (WINAPI *attach_signature)(DWORD)=DebugActiveProcess;
static BOOL (WINAPI *continue_signature)(DWORD,DWORD,DWORD)=ContinueDebugEvent;
static BOOL (WINAPI *wait_signature)(LPDEBUG_EVENT,DWORD)=WaitForDebugEventEx;
