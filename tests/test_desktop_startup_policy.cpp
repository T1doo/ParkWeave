#include "../scripts/windows_desktop/startup_policy.h"
#include <cassert>
int main(){
 assert(desktopStartupNavigation(DESKTOP_STARTUP_URI));
 assert(desktopStartupNavigation(L"about:blank"));
 assert(desktopStartupDocumentRequest(DESKTOP_STARTUP_URI,L"GET"));
 assert(!desktopStartupDocumentRequest(DESKTOP_STARTUP_URI,L"POST"));
 for(const auto* uri:{L"https://example.com/",L"file:///C:/private",L"https://parkweave.invalid/desktop-startup?command=x",L"https://parkweave.invalid/other",L"https://parkweave.invalid.evil/desktop-startup"}){
  assert(!desktopStartupNavigation(uri));assert(!desktopStartupDocumentRequest(uri,L"GET"));
 }
}
