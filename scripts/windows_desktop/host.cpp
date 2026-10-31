// ParkWeave native desktop host. No ShellExecute/browser/installer fallback.
// Backend authority remains in the original Python Controller. PE compilation
// does not constitute Windows/native product acceptance.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <wintrust.h>
#include <softpub.h>
#include <wincrypt.h>
#include <aclapi.h>
#include <sddl.h>
#include <bcrypt.h>
#include <commdlg.h>
#include <WebView2.h>
#include "sdk_iids.h"
#include <atomic>
#include <functional>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <stdexcept>
#include <cstdio>
#include <cwctype>
#include <algorithm>
#include <memory>
#include <set>
#include "desktop_pins.h"
#include "namespace_guard.h"

static HWND window, statusLabel, instanceEdit, portDb, portApi;
static HWND pass[6], startButton, newButton;
static std::vector<HWND> startup;
static ICoreWebView2Controller* controller=nullptr;
static ICoreWebView2* view=nullptr;
static ICoreWebView2Environment* environment=nullptr;
static HMODULE loader=nullptr;
static HANDLE loaderPin=INVALID_HANDLE_VALUE, runtimePin=INVALID_HANDLE_VALUE;
static HANDLE child=nullptr, childInput=nullptr, childOutput=nullptr, job=nullptr;
static bool stopping=false, running=false, backendReady=false, terminal=false, closeWhenStopped=false;
static ULONGLONG lastAlive=0, stopStarted=0;
static std::wstring base, origin, runtimeFolder, profilePath;
static HANDLE pythonPin=INVALID_HANDLE_VALUE;
static HANDLE uiJob=nullptr, browserHandle=nullptr;
static UINT32 browserPID=0;
static bool environmentPending=false,controllerPending=false,browserExited=true,uiUnknown=false,stopSent=false;
static std::vector<HANDLE> bootstrapPins;
static std::vector<HANDLE> runtimeDirectories;
static std::vector<HANDLE> retainedFilePins;
static void need(bool b);
struct OwnedHandle {HANDLE value;bool attempted=false,closed=false;};
static std::vector<std::unique_ptr<OwnedHandle>> ownedHandles;
static OwnedHandle* remember(HANDLE h){need(h&&h!=INVALID_HANDLE_VALUE);auto r=std::make_unique<OwnedHandle>();r->value=h;auto p=r.get();ownedHandles.push_back(std::move(r));return p;}
static void closeTracked(HANDLE& h){if(!h||h==INVALID_HANDLE_VALUE)return;OwnedHandle* r=nullptr;for(auto i=ownedHandles.rbegin();i!=ownedHandles.rend();++i)if((*i)->value==h&&!(*i)->closed){r=i->get();break;}if(!r)r=remember(h);if(r->attempted){uiUnknown=true;h=nullptr;return;}r->attempted=true;if(CloseHandle(h))r->closed=true;else uiUnknown=true;h=nullptr;}
static std::thread reader;
static constexpr UINT EVENT_LINE=WM_APP+1, EVENT_EXIT=WM_APP+2;
static const wchar_t* accounts[]={L"fixture-a",L"fixture-b",L"fixture-c",L"prep-specialist-fixture-a",L"prep-specialist-fixture-b",L"prep-specialist-fixture-c"};
static void need(bool b){if(!b)throw std::runtime_error("DESKTOP_REFUSED");}
static void ok(HRESULT h){need(SUCCEEDED(h));}
static void status(const wchar_t* text){SetWindowTextW(statusLabel,text);}
static std::wstring text(HWND control){int n=GetWindowTextLengthW(control);need(n<=2048);std::wstring s(n+1,L'\0');GetWindowTextW(control,s.data(),n+1);s.resize(n);return s;}
static std::string json(const std::wstring& s){std::string out="\"";char h[7];for(wchar_t c:s){sprintf(h,"\\u%04x",unsigned(c));out+=h;}return out+"\"";}
static void clearPasswords(){for(HWND h:pass)SetWindowTextW(h,L"");}
static void closeView(){if(controller){if(FAILED(controller->Close()))uiUnknown=true;controller->Release();controller=nullptr;}if(view){view->Release();view=nullptr;}running=false;}
static void signalBackend(bool confirmed){if(stopSent||!childInput)return;stopSent=true;DWORD n=0;const char b=confirmed?'S':'U';if(!WriteFile(childInput,&b,1,&n,nullptr)||n!=1)uiUnknown=true;closeTracked(childInput);}
static bool uiProcessesExited();
static void finishUIStop(){if(stopping&&!environmentPending&&!controllerPending&&browserExited&&!uiUnknown&&uiProcessesExited())signalBackend(true);}
static void stop(){if(stopping)return;stopping=true;stopStarted=GetTickCount64();closeView();status(L"正在等待本窗口嵌入进程退出，再正常停止后台…");finishUIStop();}
static bool sameOrigin(const std::wstring& u){return !origin.empty()&&(u==origin||u.rfind(origin+L"/",0)==0);}
static std::wstring unhex(const std::string& s){need(s.size()<=8192&&s.size()%4==0);std::wstring out;auto nib=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("HEX");};for(size_t i=0;i<s.size();i+=4){unsigned lo=nib(s[i])*16+nib(s[i+1]),hi=nib(s[i+2])*16+nib(s[i+3]);need(lo||hi);out.push_back(wchar_t(lo+hi*256));}return out;}

// Fixed official loader hash, retained HANDLE denies replacement/deletion.
static HANDLE pin(const std::wstring& path,const char* expected=nullptr){
 HANDLE h=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);need(h!=INVALID_HANDLE_VALUE);
 retainedFilePins.push_back(h); // retain immediately, even on metadata/hash failure
 remember(h);
 BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(h,&info)&&info.nNumberOfLinks==1&&!(info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY)));
 if(expected){BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;need(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)==0);need(BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0)==0);
  BYTE buf[65536],digest[32];DWORD n;while(true){need(ReadFile(h,buf,sizeof(buf),&n,nullptr));if(!n)break;need(BCryptHashData(hash,buf,n,0)==0);}need(BCryptFinishHash(hash,digest,32,0)==0);BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);
  char value[65];for(int i=0;i<32;i++)sprintf(value+i*2,"%02x",digest[i]);need(std::string(value)==expected);SetFilePointer(h,0,nullptr,FILE_BEGIN);
 }return h;
}
struct FindState{HANDLE handle=INVALID_HANDLE_VALUE;WIN32_FIND_DATAW data{};std::wstring path;bool attempted=false,closed=false;};
static std::vector<std::unique_ptr<FindState>> findStates;
static void finishFind(FindState* r){if(r->handle!=INVALID_HANDLE_VALUE&&!r->attempted){r->attempted=true;r->closed=FindClose(r->handle);if(!r->closed)uiUnknown=true;}}
static void scanImmutable(const std::wstring& relative,DesktopNames& files,DesktopNames& dirs,unsigned depth=0){
 need(depth<=64&&files.size()+dirs.size()<30000);auto owned=std::make_unique<FindState>();auto r=owned.get();findStates.push_back(std::move(owned));r->path=base+(relative.empty()?L"":L"\\"+relative)+L"\\*";r->handle=FindFirstFileW(r->path.c_str(),&r->data);need(r->handle!=INVALID_HANDLE_VALUE);
 try{while(true){std::wstring name=r->data.cFileName;if(name!=L"."&&name!=L".."){need(!(r->data.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DEVICE|FILE_ATTRIBUTE_OFFLINE|FILE_ATTRIBUTE_ENCRYPTED|FILE_ATTRIBUTE_SPARSE_FILE)));std::wstring path=relative.empty()?name:relative+L"\\"+name;
   if(r->data.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY){need(dirs.insert(path).second);scanImmutable(path,files,dirs,depth+1);}else need(files.insert(path).second);}
  if(!FindNextFileW(r->handle,&r->data)){need(GetLastError()==ERROR_NO_MORE_FILES);break;}}
 }catch(...){finishFind(r);throw;}finishFind(r);need(r->closed);
}
static void verifyNamespace(){
 DesktopNames wanted,dirs,foundFiles,foundDirs;for(const auto& pin:BOOTSTRAP_PINS)wanted.insert(pin.name);
 for(const auto* extra:{L"ParkWeave.exe",L"launcher\\WebView2Loader.dll",L"launcher\\WebView2-SDK-LICENSE.txt",L"launcher\\Desktop-Runtime-NOTICES.txt",L"launcher\\desktop-build.json",L"payload-manifest.json",L"static-dll-audit.json"})wanted.insert(extra);
 for(const auto& name:wanted){size_t p=0;while((p=name.find(L'\\',p))!=std::wstring::npos){dirs.insert(name.substr(0,p));p++;}}
 scanImmutable(L"",foundFiles,foundDirs);need(exactDesktopNamespace(foundFiles,foundDirs,wanted,dirs));
}
static void verifyBootstrap(){
 need(bootstrapPins.empty());
 // Keep immutable root/ancestor directories and every original source/runtime
 // file held through the child lifetime, before Python can import any code.
 std::vector<std::wstring> dirs;std::wstring root=base;
 while(root.size()>3){dirs.push_back(root);auto pos=root.find_last_of(L"\\");need(pos!=std::wstring::npos);root.resize(pos);}
 for(const auto& item:BOOTSTRAP_PINS){std::wstring name=item.name;size_t p=0;while((p=name.find(L'\\',p))!=std::wstring::npos){std::wstring dir=base+L"\\"+name.substr(0,p);if(std::find(dirs.begin(),dirs.end(),dir)==dirs.end())dirs.push_back(dir);p++;}}
 for(const auto& dir:dirs){HANDLE h=CreateFileW(dir.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);need(h!=INVALID_HANDLE_VALUE);bootstrapPins.push_back(h);remember(h);BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(h,&info)&&(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT));}
 for(const auto& item:BOOTSTRAP_PINS)bootstrapPins.push_back(pin(base+L"\\"+item.name,item.digest));
 verifyNamespace(); // reject unlisted vendor/entry.py before Python imports
}
struct TrustState {std::wstring path;WINTRUST_FILE_INFO file{};WINTRUST_DATA data{};GUID policy=WINTRUST_ACTION_GENERIC_VERIFY_V2;bool closeAttempted=false,closed=false;};
static std::vector<std::unique_ptr<TrustState>> trustStates;
static void signedMicrosoft(HANDLE file,const std::wstring& path){
 auto owned=std::make_unique<TrustState>();auto record=owned.get();trustStates.push_back(std::move(owned));
 record->path=path;auto& f=record->file;f.cbStruct=sizeof(f);f.pcwszFilePath=record->path.c_str();f.hFile=file;
 auto& data=record->data;data.cbStruct=sizeof(data);data.dwUIChoice=WTD_UI_NONE;data.fdwRevocationChecks=WTD_REVOKE_WHOLECHAIN;data.dwUnionChoice=WTD_CHOICE_FILE;data.pFile=&f;data.dwStateAction=WTD_STATEACTION_VERIFY;
 data.dwProvFlags=WTD_CACHE_ONLY_URL_RETRIEVAL|WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT;
 LONG r=WinVerifyTrust(nullptr,&record->policy,&data);bool trusted=false;
 if(r==ERROR_SUCCESS){auto p=WTHelperProvDataFromStateData(data.hWVTStateData);auto s=p?WTHelperGetProvSignerFromChain(p,0,FALSE,0):nullptr;auto c=s?WTHelperGetProvCertFromChain(s,0):nullptr;
  if(c&&c->pCert&&s->csCertChain>=2&&s->csCertChain<=8&&s->dwError==0&&!(s->dwSignerType&0x10)){
   wchar_t name[256]{};char oid[]="2.5.4.10";DWORD n=CertGetNameStringW(c->pCert,CERT_NAME_ATTR_TYPE,0,oid,name,256);trusted=n>1&&std::wstring(name)==L"Microsoft Corporation";
   for(DWORD i=0;i<s->csCertChain;i++){auto cert=WTHelperGetProvCertFromChain(s,i);if(!cert||!cert->pCert||cert->fTestCert||cert->fIsCyclic||cert->dwError||cert->dwRevokedReason){trusted=false;break;}
    if(i+1==s->csCertChain){BYTE digest[32]{};DWORD length=32;bool hashed=CryptHashCertificate2(BCRYPT_SHA256_ALGORITHM,0,nullptr,cert->pCert->pbCertEncoded,cert->pCert->cbCertEncoded,digest,&length);char hex[65];for(int j=0;j<32;j++)sprintf(hex+j*2,"%02x",digest[j]);trusted=trusted&&hashed&&length==32&&std::string(hex)=="847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61";}
   }
  }}
 data.dwStateAction=WTD_STATEACTION_CLOSE;record->closeAttempted=true;LONG closed=WinVerifyTrust(nullptr,&record->policy,&data);record->closed=closed==ERROR_SUCCESS;if(!record->closed)uiUnknown=true;need(trusted&&record->closed);
}
static bool jobPIDs(HANDLE value,std::set<ULONG_PTR>& result){
 alignas(ULONG_PTR) BYTE buffer[4096]{};DWORD used=0;if(!value||!QueryInformationJobObject(value,JobObjectBasicProcessIdList,buffer,sizeof(buffer),&used))return false;
 auto list=(JOBOBJECT_BASIC_PROCESS_ID_LIST*)buffer;if(list->NumberOfAssignedProcesses!=list->NumberOfProcessIdsInList||list->NumberOfProcessIdsInList>256)return false;
 for(DWORD i=0;i<list->NumberOfProcessIdsInList;i++)result.insert(list->ProcessIdList[i]);return true;
}
static bool uiProcessesExited(){
 std::set<ULONG_PTR> all,backend;if(!jobPIDs(uiJob,all)||!jobPIDs(job,backend))return false;
 for(auto pid:all)if(pid!=GetCurrentProcessId()&&!backend.count(pid))return false;
 return true; // no remaining UI Job process outside the original backend Job
}
static bool trustedSID(PSID sid){LPWSTR text=nullptr;need(ConvertSidToStringSidW(sid,&text));std::wstring s=text;LocalFree(text);return s==L"S-1-5-18"||s==L"S-1-5-32-544"||s==L"S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464";}
static void trustedDirectory(const std::wstring& path,bool ancestor){
 HANDLE h=CreateFileW(path.c_str(),FILE_READ_ATTRIBUTES|READ_CONTROL,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);need(h!=INVALID_HANDLE_VALUE);runtimeDirectories.push_back(h);remember(h);
 BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(h,&info)&&(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT));
 PSID owner=nullptr;PACL acl=nullptr;PSECURITY_DESCRIPTOR sd=nullptr;need(GetSecurityInfo(h,SE_FILE_OBJECT,OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,&owner,nullptr,&acl,nullptr,&sd)==ERROR_SUCCESS);
 bool valid=owner&&trustedSID(owner)&&acl&&IsValidAcl(acl);
 for(DWORD i=0;valid&&i<acl->AceCount;i++){void* raw=nullptr;if(!GetAce(acl,i,&raw)){valid=false;break;}auto a=(ACCESS_ALLOWED_ACE*)raw;if(a->Header.AceType!=ACCESS_ALLOWED_ACE_TYPE&&a->Header.AceType!=ACCESS_DENIED_ACE_TYPE){valid=false;break;}
  DWORD writes=0x2|0x4|0x10|0x40|0x100|0x10000|0x40000|0x80000|0x1000000|0x40000000|0x10000000;if(ancestor)writes&=~(0x2|0x4);
  if(a->Header.AceType==ACCESS_ALLOWED_ACE_TYPE&&!(a->Header.AceFlags&INHERIT_ONLY_ACE)&&(a->Mask&writes)&&!trustedSID(&a->SidStart))valid=false;
 }LocalFree(sd);need(valid);
}
static bool registryPresent(HKEY root,const wchar_t* path){HKEY k=nullptr;LONG r=RegOpenKeyExW(root,path,0,KEY_READ,&k);if(r==ERROR_FILE_NOT_FOUND||r==ERROR_PATH_NOT_FOUND)return false;need(r==ERROR_SUCCESS);RegCloseKey(k);return true;}
static void runtime(){
 // Reject overrides, rather than alter system settings or silently use Edge.
 LPWCH block=GetEnvironmentStringsW();need(block);for(LPWCH p=block;*p;p+=wcslen(p)+1){std::wstring row=p;for(auto& c:row)c=towupper(c);if(row.rfind(L"WEBVIEW2_",0)==0||row.rfind(L"COREWEBVIEW2_",0)==0){FreeEnvironmentStringsW(block);need(false);}}FreeEnvironmentStringsW(block);
 for(HKEY k:{HKEY_LOCAL_MACHINE,HKEY_CURRENT_USER}){
  need(!registryPresent(k,L"Software\\Policies\\Microsoft\\Edge\\WebView2"));
  need(!registryPresent(k,L"Software\\Microsoft\\Edge\\WebView2"));
 }
 HKEY key=nullptr;ok(HRESULT_FROM_WIN32(RegOpenKeyExW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",0,KEY_READ|KEY_WOW64_32KEY,&key)));
 wchar_t version[128]{};DWORD bytes=sizeof(version),type=0;LONG r=RegQueryValueExW(key,L"pv",nullptr,&type,(BYTE*)version,&bytes);RegCloseKey(key);need(r==ERROR_SUCCESS&&type==REG_SZ&&bytes>=4&&bytes<=sizeof(version)&&version[(bytes/2)-1]==0);
 std::wstring v=version;need(v!=L"0.0.0.0"&&!v.empty()&&v.find_first_not_of(L"0123456789.")==std::wstring::npos);
 wchar_t program[2048]{};ok(SHGetFolderPathW(nullptr,CSIDL_PROGRAM_FILESX86,nullptr,SHGFP_TYPE_CURRENT,program));
 runtimeFolder=std::wstring(program)+L"\\Microsoft\\EdgeWebView\\Application\\"+v;
 std::wstring current=program;std::wstring ancestor=current;while(ancestor.size()>3){trustedDirectory(ancestor,true);auto pos=ancestor.find_last_of(L'\\');need(pos!=std::wstring::npos);ancestor.resize(pos);}
 std::vector<std::wstring> parts={L"Microsoft",L"EdgeWebView",L"Application",v};for(const auto& part:parts){current+=L"\\"+part;trustedDirectory(current,false);}
 std::wstring exe=runtimeFolder+L"\\msedgewebview2.exe";runtimePin=pin(exe);signedMicrosoft(runtimePin,exe);
 loaderPin=pin(base+L"\\launcher\\WebView2Loader.dll",WEBVIEW_LOADER_SHA256);
 loader=LoadLibraryExW((base+L"\\launcher\\WebView2Loader.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);need(loader);
}

template<class T,class... A>struct Handler final:T{
 std::atomic<ULONG> refs{1};std::function<HRESULT(A...)> fn;Handler(std::function<HRESULT(A...)> f):fn(f){}
 HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out)override{if(!out)return E_POINTER;*out=nullptr;if(IsEqualGUID(id,IID_IUnknown)||IsEqualGUID(id,interfaceID<T>())){*out=static_cast<T*>(this);AddRef();return S_OK;}return E_NOINTERFACE;}
 ULONG STDMETHODCALLTYPE AddRef()override{return ++refs;}ULONG STDMETHODCALLTYPE Release()override{ULONG n=--refs;if(!n)delete this;return n;}
 HRESULT STDMETHODCALLTYPE Invoke(A... args)override{try{return fn(args...);}catch(...){uiUnknown=true;stop();signalBackend(false);return E_FAIL;}}
};
template<class T,class... A>struct Factory{template<class F>static T* make(F f){return new Handler<T,A...>(std::function<HRESULT(A...)>(f));}};
#define CB(T,...) Factory<T,__VA_ARGS__>::make
static void resize(){if(controller){RECT rect;GetClientRect(window,&rect);rect.top=64;controller->put_Bounds(rect);}}
static void showWeb(const std::wstring& profile){
 need(!controller&&!stopping&&!running&&loader);profilePath=profile;environmentPending=true;browserExited=false;
 using Create=HRESULT(STDMETHODCALLTYPE*)(PCWSTR,PCWSTR,ICoreWebView2EnvironmentOptions*,ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*);
 auto create=(Create)GetProcAddress(loader,"CreateCoreWebView2EnvironmentWithOptions");need(create);
 auto env=CB(ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler,HRESULT,ICoreWebView2Environment*)([](HRESULT hr,ICoreWebView2Environment* e)->HRESULT{
  environmentPending=false;if(FAILED(hr)||!e){uiUnknown=true;stop();signalBackend(false);return E_FAIL;}environment=e;e->AddRef();
  ICoreWebView2Environment5* e5=nullptr;ok(e->QueryInterface(interfaceID<ICoreWebView2Environment5>(),(void**)&e5));EventRegistrationToken exitToken{};
  auto exited=CB(ICoreWebView2BrowserProcessExitedEventHandler,ICoreWebView2Environment*,ICoreWebView2BrowserProcessExitedEventArgs*)([](ICoreWebView2Environment*,ICoreWebView2BrowserProcessExitedEventArgs* a)->HRESULT{UINT32 pid=0;ok(a->get_BrowserProcessId(&pid));if(!browserHandle||pid!=browserPID||WaitForSingleObject(browserHandle,0)!=WAIT_OBJECT_0){uiUnknown=true;signalBackend(false);return E_FAIL;}browserExited=true;finishUIStop();return S_OK;});ok(e5->add_BrowserProcessExited(exited,&exitToken));exited->Release();e5->Release();controllerPending=true;
  auto made=CB(ICoreWebView2CreateCoreWebView2ControllerCompletedHandler,HRESULT,ICoreWebView2Controller*)([](HRESULT hr,ICoreWebView2Controller* c)->HRESULT{
   controllerPending=false;if(FAILED(hr)||!c){uiUnknown=true;stop();signalBackend(false);return E_FAIL;}controller=c;c->AddRef();ok(c->get_CoreWebView2(&view));
   ok(view->get_BrowserProcessId(&browserPID));browserHandle=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,browserPID);if(browserHandle)remember(browserHandle);need(browserHandle);BOOL inside=FALSE;need(IsProcessInJob(browserHandle,uiJob,&inside)&&inside);wchar_t image[4096];DWORD count=4096;need(QueryFullProcessImageNameW(browserHandle,0,image,&count));need(_wcsicmp(image,(runtimeFolder+L"\\msedgewebview2.exe").c_str())==0);
   if(stopping){closeView();finishUIStop();return S_OK;}
   ICoreWebView2Settings* settings=nullptr;ok(view->get_Settings(&settings));
   ok(settings->put_AreHostObjectsAllowed(FALSE));ok(settings->put_IsWebMessageEnabled(FALSE));ok(settings->put_AreDevToolsEnabled(FALSE));ok(settings->put_AreDefaultContextMenusEnabled(FALSE));ok(settings->put_AreDefaultScriptDialogsEnabled(FALSE));settings->Release();
   ICoreWebView2Settings4* s4=nullptr;ok(view->QueryInterface(interfaceID<ICoreWebView2Settings4>(),(void**)&s4));ok(s4->put_IsPasswordAutosaveEnabled(FALSE));ok(s4->put_IsGeneralAutofillEnabled(FALSE));s4->Release();
   EventRegistrationToken token{};
   auto nav=CB(ICoreWebView2NavigationStartingEventHandler,ICoreWebView2*,ICoreWebView2NavigationStartingEventArgs*)([](ICoreWebView2*,ICoreWebView2NavigationStartingEventArgs* a)->HRESULT{LPWSTR u=nullptr;ok(a->get_Uri(&u));bool allowed=!stopping&&sameOrigin(u);CoTaskMemFree(u);if(!allowed)ok(a->put_Cancel(TRUE));return S_OK;});
   ok(view->add_NavigationStarting(nav,&token));ok(view->add_FrameNavigationStarting(nav,&token));nav->Release();
   auto popup=CB(ICoreWebView2NewWindowRequestedEventHandler,ICoreWebView2*,ICoreWebView2NewWindowRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2NewWindowRequestedEventArgs* a)->HRESULT{return a->put_Handled(TRUE);});ok(view->add_NewWindowRequested(popup,&token));popup->Release();
   auto permission=CB(ICoreWebView2PermissionRequestedEventHandler,ICoreWebView2*,ICoreWebView2PermissionRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2PermissionRequestedEventArgs* a)->HRESULT{return a->put_State(COREWEBVIEW2_PERMISSION_STATE_DENY);});ok(view->add_PermissionRequested(permission,&token));permission->Release();
   auto failed=CB(ICoreWebView2ProcessFailedEventHandler,ICoreWebView2*,ICoreWebView2ProcessFailedEventArgs*)([](ICoreWebView2*,ICoreWebView2ProcessFailedEventArgs*)->HRESULT{stop();return S_OK;});ok(view->add_ProcessFailed(failed,&token));failed->Release();
   auto requested=CB(ICoreWebView2WebResourceRequestedEventHandler,ICoreWebView2*,ICoreWebView2WebResourceRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2WebResourceRequestedEventArgs* a)->HRESULT{
    ICoreWebView2WebResourceRequest* req=nullptr;ok(a->get_Request(&req));LPWSTR u=nullptr;ok(req->get_Uri(&u));bool allowed=!stopping&&sameOrigin(u);CoTaskMemFree(u);req->Release();
    if(!allowed){ICoreWebView2WebResourceResponse* response=nullptr;ok(environment->CreateWebResourceResponse(nullptr,403,L"Blocked",L"Content-Type: text/plain",&response));ok(a->put_Response(response));response->Release();}return S_OK;});
   ok(view->AddWebResourceRequestedFilter(L"*",COREWEBVIEW2_WEB_RESOURCE_CONTEXT_ALL));ok(view->add_WebResourceRequested(requested,&token));requested->Release();
   ICoreWebView2_18* v18=nullptr;ok(view->QueryInterface(interfaceID<ICoreWebView2_18>(),(void**)&v18));
   auto external=CB(ICoreWebView2LaunchingExternalUriSchemeEventHandler,ICoreWebView2*,ICoreWebView2LaunchingExternalUriSchemeEventArgs*)([](ICoreWebView2*,ICoreWebView2LaunchingExternalUriSchemeEventArgs* a)->HRESULT{return a->put_Cancel(TRUE);});ok(v18->add_LaunchingExternalUriScheme(external,&token));external->Release();v18->Release();
   ICoreWebView2_4* v4=nullptr;ok(view->QueryInterface(interfaceID<ICoreWebView2_4>(),(void**)&v4));
   auto download=CB(ICoreWebView2DownloadStartingEventHandler,ICoreWebView2*,ICoreWebView2DownloadStartingEventArgs*)([](ICoreWebView2*,ICoreWebView2DownloadStartingEventArgs* a)->HRESULT{
    // Only page-requested text exports, stored inside this installation's
    // protected persistent profile; never use the OS Downloads directory.
    ok(a->put_Cancel(TRUE));if(stopping||!running)return S_OK;
    LPWSTR source=nullptr;ok(view->get_Source(&source));bool permitted=sameOrigin(source);CoTaskMemFree(source);if(!permitted)return S_OK;
    ICoreWebView2DownloadOperation* operation=nullptr;ok(a->get_DownloadOperation(&operation));LPWSTR uri=nullptr;ok(operation->get_Uri(&uri));std::wstring u=uri;CoTaskMemFree(uri);operation->Release();if(u.rfind(L"blob:"+origin+L"/",0)!=0)return S_OK;
    std::wstring dir=profilePath+L"\\Downloads";DWORD attr=GetFileAttributesW(dir.c_str());if(attr==INVALID_FILE_ATTRIBUTES)need(CreateDirectoryW(dir.c_str(),nullptr));attr=GetFileAttributesW(dir.c_str());need(attr!=INVALID_FILE_ATTRIBUTES&&(attr&FILE_ATTRIBUTE_DIRECTORY)&&!(attr&FILE_ATTRIBUTE_REPARSE_POINT));
    GUID id{};ok(CoCreateGuid(&id));wchar_t guid[40];need(StringFromGUID2(id,guid,40)>0);std::wstring path=dir+L"\\ParkWeave-"+guid+L".txt";need(GetFileAttributesW(path.c_str())==INVALID_FILE_ATTRIBUTES);
    ok(a->put_ResultFilePath(path.c_str()));ok(a->put_Handled(TRUE));ok(a->put_Cancel(FALSE));status((L"材料文本将保存到本实例受保护目录："+path).c_str());return S_OK;
   });ok(v4->add_DownloadStarting(download,&token));download->Release();v4->Release();
   for(HWND h:startup)ShowWindow(h,SW_HIDE);resize();ok(view->Navigate((origin+L"/").c_str()));running=true;lastAlive=GetTickCount64();status(L"园合 · 本地合成资料工作台　｜　关闭窗口将正常停止本次后台");return S_OK;
  });HRESULT result=e->CreateCoreWebView2Controller(window,made);made->Release();if(FAILED(result)){controllerPending=false;uiUnknown=true;stop();signalBackend(false);}return result;
 });HRESULT r=create(runtimeFolder.c_str(),profile.c_str(),nullptr,env);env->Release();if(FAILED(r)){environmentPending=false;uiUnknown=true;stop();signalBackend(false);ok(r);}
}

static std::string payload(const std::wstring& action){
 std::string body="{\"action\":"+json(action)+",\"instance\":"+json(action==L"status"?L"":text(instanceEdit))+",\"database_port\":";
 auto port=[](HWND h){std::wstring t=text(h);need(!t.empty()&&t.find_first_not_of(L"0123456789")==std::wstring::npos);int n=std::stoi(t);need(n>0&&n<=65535);return std::to_string(n);};
 body+=(action==L"new"?port(portDb):"0");body+=",\"api_port\":"+(action==L"new"?port(portApi):"0");body+=",\"passwords\":{";
 if(action==L"new")for(int i=0;i<6;i++){std::wstring p=text(pass[i]);need(p.size()>=12&&p.size()<=256);if(i)body+=",";body+=json(accounts[i])+":"+json(p);SecureZeroMemory(p.data(),p.size()*sizeof(wchar_t));}
 body+="},\"initialize_profile\":";body+=(action==L"new"||SendMessageW(GetDlgItem(window,3),BM_GETCHECK,0,0)==BST_CHECKED)?"true":"false";return body+"}\n";
}
static void launch(const std::wstring& action){
 need(!child&&!stopping);std::string data=payload(action);clearPasswords();
 verifyBootstrap();
 try{runtime();}catch(...){SecureZeroMemory(data.data(),data.size());stopping=true;status(L"已安装的官方 x64 WebView2 Runtime 缺失或无法核验。不会安装、修复或启动 Edge 浏览器。");return;}
 HANDLE in=nullptr,out=nullptr,thread=nullptr;bool resumeAttempted=false,attributesReady=false;
 STARTUPINFOEXW si{};std::vector<BYTE> attrs;
 auto closeOwned=[](HANDLE& h){closeTracked(h);};
 try{
  // Configure containment before a child exists; retain its original outputs
  // immediately when CreateProcess returns, before every fallible observation.
  job=CreateJobObjectW(nullptr,nullptr);if(job)remember(job);need(job);
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  need(SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits)));
  SECURITY_ATTRIBUTES sa{sizeof(sa),nullptr,TRUE};BOOL first=CreatePipe(&in,&childInput,&sa,0);if(in)remember(in);if(childInput)remember(childInput);need(first);BOOL second=CreatePipe(&childOutput,&out,&sa,0);if(childOutput)remember(childOutput);if(out)remember(out);need(second);
  need(SetHandleInformation(childInput,HANDLE_FLAG_INHERIT,0)&&SetHandleInformation(childOutput,HANDLE_FLAG_INHERIT,0));
  si.StartupInfo.cb=sizeof(si);si.StartupInfo.dwFlags=STARTF_USESTDHANDLES;si.StartupInfo.hStdInput=in;si.StartupInfo.hStdOutput=si.StartupInfo.hStdError=out;
  SIZE_T size=0;InitializeProcThreadAttributeList(nullptr,1,0,&size);need(size>0&&size<65536);attrs.resize(size);si.lpAttributeList=(LPPROC_THREAD_ATTRIBUTE_LIST)attrs.data();
  need(InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&size));attributesReady=true;HANDLE inherited[]={in,out};
  need(UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited,sizeof(inherited),nullptr,nullptr));
  // Keep the original entry's exact console-interpreter contract and real
  // inherited stdin/stdout pipes. CREATE_NO_WINDOW supplies the desktop
  // lifecycle without a console; pythonw may expose None standard streams.
  std::wstring exe=base+L"\\runtime\\python\\python.exe",cmd=L"\""+exe+L"\" -I -B \""+base+L"\\launcher\\desktop_bridge.py\"";
  pythonPin=pin(exe,PYTHON_SHA256);PROCESS_INFORMATION pi{};
  BOOL created=CreateProcessW(exe.c_str(),cmd.data(),nullptr,nullptr,TRUE,CREATE_SUSPENDED|CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,nullptr,base.c_str(),&si.StartupInfo,&pi);
  if(created){child=pi.hProcess;thread=pi.hThread;remember(child);remember(thread);}need(created);
  DeleteProcThreadAttributeList(si.lpAttributeList);attributesReady=false;closeOwned(in);closeOwned(out);
  need(!uiUnknown&&AssignProcessToJobObject(job,child));resumeAttempted=true;need(ResumeThread(thread)!=DWORD(-1));closeOwned(thread);
  terminal=false;EnableWindow(startButton,FALSE);EnableWindow(newButton,FALSE);status(L"正在核验原始安装与运行条件…");
  reader=std::thread([]{std::string line;char c;DWORD n;while(ReadFile(childOutput,&c,1,&n,nullptr)&&n){if(c=='\n'){auto p=new std::string(line);if(!PostMessageW(window,EVENT_LINE,0,(LPARAM)p))delete p;line.clear();}else{line+=c;if(line.size()>16384)break;}}WaitForSingleObject(child,INFINITE);PostMessageW(window,EVENT_EXIT,0,0);});
  DWORD n=0;bool sent=data.size()<=32768&&WriteFile(childInput,data.data(),DWORD(data.size()),&n,nullptr)&&n==data.size();SecureZeroMemory(data.data(),data.size());need(sent);
 }catch(...){
  SecureZeroMemory(data.data(),data.size());if(attributesReady)DeleteProcThreadAttributeList(si.lpAttributeList);closeOwned(in);closeOwned(out);
  // Only a positively never-resumed, originally created suspended child can
  // be terminated here. Resume/stop uncertainty is retained, never retried.
  if(child&&!resumeAttempted){bool ended=TerminateProcess(child,2)&&WaitForSingleObject(child,3000)==WAIT_OBJECT_0;if(ended){closeOwned(thread);closeOwned(child);closeOwned(childOutput);closeOwned(childInput);closeOwned(job);}else{uiUnknown=true;bootstrapPins.push_back(thread);thread=nullptr;}}
  else if(thread){uiUnknown=true;bootstrapPins.push_back(thread);thread=nullptr;}
  if(child){uiUnknown=true;stop();signalBackend(false);}else{closeOwned(childOutput);closeOwned(childInput);closeOwned(job);}
  throw;
 }
}
static void event(const std::string& line){
 if(line=="PW1\tALIVE"){if(stopping)return;need(backendReady);lastAlive=GetTickCount64();return;}
 if(line=="PW1\tSTOPPED"){need(stopping&&stopSent&&browserExited&&!uiUnknown);terminal=true;status(L"本次后台已正常停止，资料与待核对请求均已保留。");if(closeWhenStopped)PostMessageW(window,WM_CLOSE,0,0);return;}
 if(line.rfind("PW1\tREFUSED\t",0)==0){terminal=true;std::wstring reason(line.begin()+12,line.end());status((L"原始入口拒绝："+reason+L"。没有自动初始化、修复或重试。").c_str());return;}
 if(line.rfind("PW1\tRUNNING\t",0)==0){need(!stopping&&!backendReady);auto split=line.find('\t',12);need(split!=std::string::npos);std::string p=line.substr(12,split-12);need(!p.empty()&&p.find_first_not_of("0123456789")==std::string::npos);int port=std::stoi(p);need(port>0&&port<=65535);origin=L"http://127.0.0.1:"+std::to_wstring(port);backendReady=true;lastAlive=GetTickCount64();showWeb(unhex(line.substr(split+1)));return;}
 uiUnknown=true;status(L"本次状态未知，已停止页面通信并保留现场；没有重启或重试。");stop();signalBackend(false);
}
static HWND control(const wchar_t* cls,const wchar_t* label,DWORD style,int x,int y,int w,int h,int id=0){HWND c=CreateWindowExW(0,cls,label,WS_CHILD|WS_VISIBLE|style,x,y,w,h,window,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr);need(c);SendMessageW(c,WM_SETFONT,(WPARAM)GetStockObject(DEFAULT_GUI_FONT),TRUE);startup.push_back(c);return c;}
static LRESULT CALLBACK procedure(HWND h,UINT message,WPARAM w,LPARAM l){try{switch(message){
 case WM_CREATE:{window=h;statusLabel=control(L"STATIC",L"园合 ParkWeave · 独立桌面工作台",0,20,16,1300,40);startup.clear();
 control(L"STATIC",L"已有安装目录（重开只读既有绑定；首次安装必须使用新目录）",0,24,92,900,24);instanceEdit=control(L"EDIT",L"",WS_BORDER|ES_AUTOHSCROLL,24,122,920,32);
 startButton=control(L"BUTTON",L"重开工作台",BS_PUSHBUTTON,24,174,180,38,1);newButton=control(L"BUTTON",L"首次新建安装",BS_PUSHBUTTON,218,174,180,38,2);
 control(L"STATIC",L"首次新建的回环端口（重开使用原保护配置）",0,24,238,800,24);portDb=control(L"EDIT",L"55432",WS_BORDER|ES_NUMBER,24,270,160,30);portApi=control(L"EDIT",L"58761",WS_BORDER|ES_NUMBER,204,270,160,30);
 control(L"BUTTON",L"首次在已有安装使用桌面：独占建立桌面资料目录（不重建数据库）",BS_AUTOCHECKBOX,420,174,830,38,3);
 control(L"STATIC",L"首次新建：六个账号分别设置12–256字符的不同密码；重开无需填写。",0,24,326,1100,24);
 for(int i=0;i<6;i++){std::wstring label=(i<3?L"企业 ":L"专员 ")+std::wstring(1,wchar_t(L'A'+i%3));int x=24+(i%3)*310,y=365+(i/3)*86;control(L"STATIC",label.c_str(),0,x,y,270,24);pass[i]=control(L"EDIT",L"",WS_BORDER|ES_PASSWORD|ES_AUTOHSCROLL,x,y+28,284,32);SendMessageW(pass[i],EM_SETLIMITTEXT,256,0);}
 control(L"STATIC",L"合成样例 · 无真实园区接入。缺运行条件会明确停止，不安装运行库、不改系统安全设置。",0,24,570,1240,48);SetTimer(h,1,500,nullptr);return 0;}
 case WM_COMMAND:if(LOWORD(w)==1)launch(L"reopen");else if(LOWORD(w)==2)launch(L"new");return 0;
 case EVENT_LINE:{auto p=(std::string*)l;std::string line=*p;delete p;event(line);return 0;}
 case EVENT_EXIT:{if(reader.joinable())reader.join();closeTracked(childOutput);closeTracked(child);if(childInput){closeTracked(childInput);}if(job){closeTracked(job);}if(pythonPin!=INVALID_HANDLE_VALUE){closeTracked(pythonPin);}
  closeView();backendReady=false;if(!terminal||uiUnknown){stopping=true;status(L"本次后台退出未获确认：状态未知，保留目录与请求，不自动重开。");}else if(closeWhenStopped)DestroyWindow(h);else{stopping=true;}return 0;}
 case WM_TIMER:finishUIStop();if(child&&!reader.joinable()&&WaitForSingleObject(child,0)==WAIT_OBJECT_0)PostMessageW(window,EVENT_EXIT,0,0);if(backendReady&&!stopping&&GetTickCount64()-lastAlive>4000)stop();if(stopping&&child&&GetTickCount64()-stopStarted>30000){uiUnknown=true;signalBackend(false);status(L"嵌入进程退出未确认：本次保留UNKNOWN，不重试或认作正常停止。");}return 0;
 case WM_SIZE:resize();return 0;
 case WM_GETMINMAXINFO:{auto m=(MINMAXINFO*)l;m->ptMinTrackSize={1040,720};return 0;}
 case WM_CLOSE:if(child){closeWhenStopped=true;stop();return 0;}closeView();DestroyWindow(h);return 0;
 case WM_DESTROY:KillTimer(h,1);PostQuitMessage(0);return 0;
 }}catch(...){clearPasswords();status(L"桌面启动或运行核验失败，已保留现有资料；没有浏览器或安装回退。");if(child)stop();}return DefWindowProcW(h,message,w,l);}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR,int show){
 try{wchar_t path[32768];DWORD n=GetModuleFileNameW(nullptr,path,32768);need(n&&n<32768);base=path;auto p=base.find_last_of(L"\\");need(p!=std::wstring::npos);base.resize(p);SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32);
  ok(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED));SetCurrentProcessExplicitAppUserModelID(L"ParkWeave.Desktop");
  uiJob=CreateJobObjectW(nullptr,nullptr);if(uiJob)remember(uiJob);need(uiJob);JOBOBJECT_EXTENDED_LIMIT_INFORMATION lifetime{};lifetime.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;need(SetInformationJobObject(uiJob,JobObjectExtendedLimitInformation,&lifetime,sizeof(lifetime)));need(AssignProcessToJobObject(uiJob,GetCurrentProcess()));
  WNDCLASSEXW cls{sizeof(cls)};cls.lpfnWndProc=procedure;cls.hInstance=instance;cls.hCursor=LoadCursorW(nullptr,IDC_ARROW);cls.hIcon=LoadIconW(nullptr,IDI_APPLICATION);cls.hIconSm=cls.hIcon;cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);cls.lpszClassName=L"ParkWeaveDesktop";need(RegisterClassExW(&cls));
  RECT area{};SystemParametersInfoW(SPI_GETWORKAREA,0,&area,0);int width=std::min(1440L,area.right-area.left),height=std::min(900L,area.bottom-area.top);
  HWND h=CreateWindowExW(WS_EX_APPWINDOW,cls.lpszClassName,L"园合 ParkWeave · 资料工作台",WS_OVERLAPPEDWINDOW,area.left+(area.right-area.left-width)/2,area.top+(area.bottom-area.top-height)/2,width,height,nullptr,nullptr,instance,nullptr);need(h);ShowWindow(h,show);UpdateWindow(h);
  MSG msg;while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(h,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
  if(environment)environment->Release();if(loader&&!FreeLibrary(loader))uiUnknown=true;closeTracked(loaderPin);closeTracked(runtimePin);CoUninitialize();return uiUnknown?2:0;
 }catch(...){MessageBoxW(nullptr,L"桌面宿主未能启动；不会打开浏览器、自动安装或更改系统设置。",L"ParkWeave",MB_OK|MB_ICONERROR);return 2;}
}
