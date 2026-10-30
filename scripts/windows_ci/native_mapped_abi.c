/* Compile-only Windows AMD64 ABI check. Never a native execution result. */
#include <windows.h>
#include <stddef.h>
_Static_assert(sizeof(DEBUG_EVENT)==176,"DEBUG_EVENT size");
_Static_assert(offsetof(DEBUG_EVENT,u)==16,"DEBUG_EVENT union");
_Static_assert(sizeof(EXCEPTION_RECORD)==152,"EXCEPTION_RECORD size");
_Static_assert(sizeof(CREATE_PROCESS_DEBUG_INFO)==72,"process event size");
_Static_assert(sizeof(LOAD_DLL_DEBUG_INFO)==40,"DLL event size");
_Static_assert(sizeof(CREATE_THREAD_DEBUG_INFO)==24,"thread event size");
_Static_assert(sizeof(FILE_ID_INFO)==24,"original file identity size");
_Static_assert(offsetof(JOBOBJECT_BASIC_PROCESS_ID_LIST,ProcessIdList)==8,"Job PID layout");
static BOOL (WINAPI *attach_signature)(DWORD)=DebugActiveProcess;
static BOOL (WINAPI *continue_signature)(DWORD,DWORD,DWORD)=ContinueDebugEvent;
static BOOL (WINAPI *wait_signature)(LPDEBUG_EVENT,DWORD)=WaitForDebugEventEx;
