// ABI declaration documented in Win32 EventRegistrationToken (eventtoken.h).
// MinGW lacks this one imported WinRT scalar header; SDK interfaces unchanged.
#pragma once
typedef struct EventRegistrationToken { __int64 value; } EventRegistrationToken;
static_assert(sizeof(EventRegistrationToken)==8,"Win32 event token ABI");
