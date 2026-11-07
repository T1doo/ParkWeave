#pragma once
#include <string>
// Reserved .invalid name is intercepted in-process, never an external server.
inline constexpr const wchar_t* DESKTOP_STARTUP_URI=L"https://parkweave.invalid/desktop-startup";
inline bool desktopStartupNavigation(const std::wstring& uri){
 return uri==L"about:blank"||uri==DESKTOP_STARTUP_URI;
}
inline bool desktopStartupDocumentRequest(const std::wstring& uri,const std::wstring& method){
 return uri==DESKTOP_STARTUP_URI&&method==L"GET";
}
