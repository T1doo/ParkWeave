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
#include <sstream>
#include "desktop_pins.h"
#include "namespace_guard.h"
#include "webview_settings.h"
#include "startup_html.h"
#include "startup_policy.h"

static HWND window, statusLabel, instanceEdit, portDb, portApi;
static HWND pass[6], passLabels[6], startButton, newButton;
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
static bool crtRevocationUnknown=false;
static bool startupView=false;
static bool startupProbe=false,probeReported=false,startupMessageProbe=false,probeMessageSent=false,startupCapture=false;
static ULONGLONG probeStarted=0;
static const wchar_t* startupPhase=L"程序启动";
static std::wstring startupProfile,startupRefusal,pendingWorkspaceProfile;
static bool workspaceSwitch=false;
static ULONGLONG workspaceSwitchAt=0;
static void launchRequest(std::string data);
static std::vector<HANDLE> bootstrapPins;
static std::vector<HANDLE> runtimeDirectories;
static std::vector<HANDLE> retainedFilePins;
static void need(bool b);
struct OwnedHandle {HANDLE value;bool attempted=false,closed=false;};
static std::vector<std::unique_ptr<OwnedHandle>> ownedHandles;
static OwnedHandle* remember(HANDLE h){need(h&&h!=INVALID_HANDLE_VALUE);auto r=std::make_unique<OwnedHandle>();r->value=h;auto p=r.get();ownedHandles.push_back(std::move(r));return p;}
static void closeTracked(HANDLE& h){if(!h||h==INVALID_HANDLE_VALUE)return;OwnedHandle* r=nullptr;for(auto i=ownedHandles.rbegin();i!=ownedHandles.rend();++i)if((*i)->value==h&&!(*i)->closed){r=i->get();break;}if(!r)r=remember(h);if(r->attempted){uiUnknown=true;h=nullptr;return;}r->attempted=true;if(CloseHandle(h))r->closed=true;else uiUnknown=true;h=nullptr;}
static std::thread reader;
// Explicit CI-only, unprivileged viewer attachment. Native trial capabilities,
// database, passwords and profile authority stay in the source-bound parent.
static bool trialView=false,trialAttached=false,trialAck=false,trialEof=false;
static HANDLE trialInput=nullptr,trialOutput=nullptr,trialParent=nullptr,trialProfile=nullptr;
static std::string trialNonce;
static bool trialStartupReported=false;
static unsigned trialStage=1; // START frame and profile validation
static constexpr UINT EVENT_LINE=WM_APP+1, EVENT_EXIT=WM_APP+2;
static constexpr UINT TRIAL_EOF=WM_APP+3;
static const wchar_t* accounts[]={L"fixture-a",L"fixture-b",L"fixture-c",L"prep-specialist-fixture-a",L"prep-specialist-fixture-b",L"prep-specialist-fixture-c"};
static const wchar_t* sampleAccounts[]={L"fixture-a",L"prep-specialist-fixture-a",L"sample-executor-a",L"sample-resource-admin-a"};
static bool sampleSelected(){return SendMessageW(GetDlgItem(window,4),BM_GETCHECK,0,0)==BST_CHECKED;}
static void sampleInputs(){
 bool selected=sampleSelected();const wchar_t* labels[]={L"企业",L"专员",L"执行者",L"资源管理员"};
 for(int i=0;i<6;i++){SetWindowTextW(pass[i],L"");ShowWindow(pass[i],selected&&i>=4?SW_HIDE:SW_SHOW);ShowWindow(passLabels[i],selected&&i>=4?SW_HIDE:SW_SHOW);
  std::wstring label=selected&&i<4?std::wstring(labels[i]):(i<3?L"企业 ":L"专员 ")+std::wstring(1,wchar_t(L'A'+i%3));SetWindowTextW(passLabels[i],label.c_str());}
}
static void need(bool b){if(!b)throw std::runtime_error("DESKTOP_REFUSED");}
static void ok(HRESULT h){need(SUCCEEDED(h));}
static void reportTrialStartup(bool ready){
 if(!trialView||trialStartupReported||trialNonce.empty())return;
 trialStartupReported=true;
 std::string line=ready?"PWUI1\tVIEW_READY\t":"PWUI1\tVIEW_FAILED\t";line+=trialNonce;
 if(!ready){char code[9];sprintf(code,"%08x",trialStage);line+="\t";line+=code;}
 line+="\n";DWORD used=0;
 if(!WriteFile(trialOutput,line.data(),DWORD(line.size()),&used,nullptr)||used!=line.size())uiUnknown=true;
}
static void reportStartupProbe(const wchar_t* result){
 if(!startupProbe||probeReported)return;probeReported=true;std::wstring value=result?result:L"null";if(value.size()>2048)value=L"null";
 int count=WideCharToMultiByte(CP_UTF8,0,value.c_str(),int(value.size()),nullptr,0,nullptr,nullptr);std::string data(count,'\0');WideCharToMultiByte(CP_UTF8,0,value.c_str(),int(value.size()),data.data(),count,nullptr,nullptr);data="{\"event\":\"STARTUP_PROBE\",\"result\":"+data+"}\n";DWORD written=0;WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),data.data(),DWORD(data.size()),&written,nullptr);PostMessageW(window,WM_CLOSE,0,0);
}
static void status(const wchar_t* text){SetWindowTextW(statusLabel,text);}
static std::wstring text(HWND control){int n=GetWindowTextLengthW(control);need(n<=2048);std::wstring s(n+1,L'\0');GetWindowTextW(control,s.data(),n+1);s.resize(n);return s;}
static std::string json(const std::wstring& s){std::string out="\"";char h[7];for(wchar_t c:s){sprintf(h,"\\u%04x",unsigned(c));out+=h;}return out+"\"";}
static void clearPasswords(){for(HWND h:pass)SetWindowTextW(h,L"");}
static void closeView(){if(controller){if(FAILED(controller->Close()))uiUnknown=true;controller->Release();controller=nullptr;}if(view){view->Release();view=nullptr;}running=false;}
static void signalBackend(bool confirmed){if(stopSent||!childInput)return;stopSent=true;DWORD n=0;const char b=confirmed?'S':'U';if(!WriteFile(childInput,&b,1,&n,nullptr)||n!=1)uiUnknown=true;closeTracked(childInput);}
static bool uiProcessesExited();
static void finishUIStop(){if(stopping&&!environmentPending&&!controllerPending&&browserExited&&!uiUnknown&&uiProcessesExited()){
 if(trialView){if(!trialAttached){uiUnknown=true;return;}if(!trialAck){std::string ack="PWUI1\tVIEW_RELEASED\t"+trialNonce+"\n";DWORD used=0;trialAck=WriteFile(trialOutput,ack.data(),DWORD(ack.size()),&used,nullptr)&&used==ack.size();if(!trialAck)uiUnknown=true;}}
 else if(startupView&&!child){if(closeWhenStopped)DestroyWindow(window);}
 else signalBackend(true);
}}
static void stop(){if(stopping)return;stopping=true;stopStarted=GetTickCount64();closeView();status(L"正在等待本窗口嵌入进程退出，再正常停止后台…");finishUIStop();}
static bool sameOrigin(const std::wstring& u){return !origin.empty()&&(u==origin||u.rfind(origin+L"/",0)==0);}
static std::wstring unhex(const std::string& s){need(s.size()<=8192&&s.size()%4==0);std::wstring out;auto nib=[](char c)->int{if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("HEX");};for(size_t i=0;i<s.size();i+=4){unsigned lo=nib(s[i])*16+nib(s[i+1]),hi=nib(s[i+2])*16+nib(s[i+3]);need(lo||hi);out.push_back(wchar_t(lo+hi*256));}return out;}

// Fixed official loader hash, retained HANDLE denies replacement/deletion.
static HANDLE pin(const std::wstring& path,const char* expected=nullptr,bool systemRuntime=false){
 HANDLE h=CreateFileW(path.c_str(),GENERIC_READ|(systemRuntime?READ_CONTROL:0),FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);need(h!=INVALID_HANDLE_VALUE);
 retainedFilePins.push_back(h); // retain immediately, even on metadata/hash failure
 remember(h);
 BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(h,&info)&&(info.nNumberOfLinks==1||(systemRuntime&&info.nNumberOfLinks>0))&&!(info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY)));
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
 if(r==CRYPT_E_REVOCATION_OFFLINE||r==CRYPT_E_NO_REVOCATION_CHECK||r==CERT_E_REVOCATION_FAILURE)trialStage=13;
 else if(r==CERT_E_REVOKED||r==CRYPT_E_REVOKED)trialStage=14;
 else if(r!=ERROR_SUCCESS)trialStage=15;
 if(r==ERROR_SUCCESS){auto p=WTHelperProvDataFromStateData(data.hWVTStateData);auto s=p?WTHelperGetProvSignerFromChain(p,0,FALSE,0):nullptr;auto c=s?WTHelperGetProvCertFromChain(s,0):nullptr;
  trialStage=16;
  if(c&&c->pCert&&s->csCertChain>=2&&s->csCertChain<=8&&s->dwError==0&&!(s->dwSignerType&0x10)){
   wchar_t name[256]{};char oid[]="2.5.4.10";DWORD n=CertGetNameStringW(c->pCert,CERT_NAME_ATTR_TYPE,0,oid,name,256);trusted=n>1&&std::wstring(name)==L"Microsoft Corporation";
   for(DWORD i=0;trusted&&i<s->csCertChain;i++){auto cert=WTHelperGetProvCertFromChain(s,i);if(!cert||!cert->pCert||cert->fTestCert||cert->fIsCyclic||cert->dwError||cert->dwRevokedReason){trialStage=17;trusted=false;break;}
    if(i+1==s->csCertChain){
     BYTE digest[32]{};DWORD length=sizeof(digest);
     trusted=CryptHashCertificate2(BCRYPT_SHA256_ALGORITHM,0,nullptr,cert->pCert->pbCertEncoded,cert->pCert->cbCertEncoded,digest,&length)&&length==sizeof(digest);
     if(trusted){char hex[65];for(int j=0;j<32;j++)sprintf(hex+j*2,"%02x",digest[j]);trusted=std::string(hex)=="847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61";}
     if(!trusted)trialStage=18;
    }
   }
  }}
 data.dwStateAction=WTD_STATEACTION_CLOSE;record->closeAttempted=true;LONG closed=WinVerifyTrust(nullptr,&record->policy,&data);record->closed=closed==ERROR_SUCCESS;if(!record->closed){trialStage=19;uiUnknown=true;}need(trusted&&record->closed);
}
static bool jobPIDs(HANDLE value,std::set<ULONG_PTR>& result){
 alignas(ULONG_PTR) BYTE buffer[4096]{};DWORD used=0;if(!value||!QueryInformationJobObject(value,JobObjectBasicProcessIdList,buffer,sizeof(buffer),&used))return false;
 auto list=(JOBOBJECT_BASIC_PROCESS_ID_LIST*)buffer;if(list->NumberOfAssignedProcesses!=list->NumberOfProcessIdsInList||list->NumberOfProcessIdsInList>256)return false;
 for(DWORD i=0;i<list->NumberOfProcessIdsInList;i++)result.insert(list->ProcessIdList[i]);return true;
}
static bool uiProcessesExited(){
 std::set<ULONG_PTR> all,backend;if(!jobPIDs(uiJob,all)||(!trialView&&!jobPIDs(job,backend)))return false;
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
// System runtime files may be hard-linked by the Microsoft installer. The
// opened file object remains deny-write/deny-delete pinned; every alias shares
// its security descriptor. Never extend this rule to private payload files.
static void trustedRuntimeFile(HANDLE h){
 PSID owner=nullptr;PACL acl=nullptr;PSECURITY_DESCRIPTOR sd=nullptr;
 need(GetSecurityInfo(h,SE_FILE_OBJECT,OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,&owner,nullptr,&acl,nullptr,&sd)==ERROR_SUCCESS);
 bool valid=owner&&trustedSID(owner)&&acl&&IsValidAcl(acl);
 for(DWORD i=0;valid&&i<acl->AceCount;i++){void* raw=nullptr;if(!GetAce(acl,i,&raw)){valid=false;break;}auto ace=(ACCESS_ALLOWED_ACE*)raw;
  if(ace->Header.AceType!=ACCESS_ALLOWED_ACE_TYPE&&ace->Header.AceType!=ACCESS_DENIED_ACE_TYPE){valid=false;break;}
  DWORD writes=FILE_WRITE_DATA|FILE_APPEND_DATA|FILE_WRITE_EA|FILE_WRITE_ATTRIBUTES|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_WRITE|GENERIC_ALL;
  if(ace->Header.AceType==ACCESS_ALLOWED_ACE_TYPE&&!(ace->Header.AceFlags&INHERIT_ONLY_ACE)&&(ace->Mask&writes)&&!trustedSID(&ace->SidStart))valid=false;
 }LocalFree(sd);need(valid);
}
static bool registryPresent(HKEY root,const wchar_t* path){HKEY k=nullptr;LONG r=RegOpenKeyExW(root,path,0,KEY_READ,&k);if(r==ERROR_FILE_NOT_FOUND||r==ERROR_PATH_NOT_FOUND)return false;need(r==ERROR_SUCCESS);RegCloseKey(k);return true;}
static void runtime(){
 // Reject overrides, rather than alter system settings or silently use Edge.
 startupPhase=L"WebView2 环境设置";trialStage=3;
 LPWCH block=GetEnvironmentStringsW();need(block);for(LPWCH p=block;*p;p+=wcslen(p)+1){std::wstring row=p;for(auto& c:row)c=towupper(c);if(row.rfind(L"WEBVIEW2_",0)==0||row.rfind(L"COREWEBVIEW2_",0)==0){FreeEnvironmentStringsW(block);need(false);}}FreeEnvironmentStringsW(block);
 for(HKEY k:{HKEY_LOCAL_MACHINE,HKEY_CURRENT_USER}){
  need(!registryPresent(k,L"Software\\Policies\\Microsoft\\Edge\\WebView2"));
  need(!registryPresent(k,L"Software\\Microsoft\\Edge\\WebView2"));
 }
 startupPhase=L"WebView2 安装登记";trialStage=4;
 HKEY key=nullptr;ok(HRESULT_FROM_WIN32(RegOpenKeyExW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",0,KEY_READ|KEY_WOW64_32KEY,&key)));
 wchar_t version[128]{};DWORD bytes=sizeof(version),type=0;LONG r=RegQueryValueExW(key,L"pv",nullptr,&type,(BYTE*)version,&bytes);RegCloseKey(key);need(r==ERROR_SUCCESS&&type==REG_SZ&&bytes>=4&&bytes<=sizeof(version)&&version[(bytes/2)-1]==0);
 std::wstring v=version;need(v!=L"0.0.0.0"&&!v.empty()&&v.find_first_not_of(L"0123456789.")==std::wstring::npos);
 wchar_t program[2048]{};ok(SHGetFolderPathW(nullptr,CSIDL_PROGRAM_FILESX86,nullptr,SHGFP_TYPE_CURRENT,program));
 runtimeFolder=std::wstring(program)+L"\\Microsoft\\EdgeWebView\\Application\\"+v;
 startupPhase=L"WebView2 目录身份";trialStage=5;
 std::wstring current=program;std::wstring ancestor=current;while(ancestor.size()>3){trustedDirectory(ancestor,true);auto pos=ancestor.find_last_of(L'\\');need(pos!=std::wstring::npos);ancestor.resize(pos);}
 std::vector<std::wstring> parts={L"Microsoft",L"EdgeWebView",L"Application",v};for(const auto& part:parts){current+=L"\\"+part;trustedDirectory(current,false);}
 std::wstring exe=runtimeFolder+L"\\msedgewebview2.exe";startupPhase=L"WebView2 程序文件身份";trialStage=6;runtimePin=pin(exe,nullptr,true);trustedRuntimeFile(runtimePin);startupPhase=L"WebView2 微软签名与吊销信息";trialStage=7;signedMicrosoft(runtimePin,exe);
 startupPhase=L"WebView2 Loader 文件校验";trialStage=8;
 loaderPin=pin(base+L"\\launcher\\WebView2Loader.dll",WEBVIEW_LOADER_SHA256);
 startupPhase=L"WebView2 Loader 加载";
 loader=LoadLibraryExW((base+L"\\launcher\\WebView2Loader.dll").c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_SYSTEM32);need(loader);
}

template<class T,class... A>struct Handler final:T{
 std::atomic<ULONG> refs{1};std::function<HRESULT(A...)> fn;Handler(std::function<HRESULT(A...)> f):fn(f){}
 HRESULT STDMETHODCALLTYPE QueryInterface(REFIID id,void** out)override{if(!out)return E_POINTER;*out=nullptr;if(IsEqualGUID(id,IID_IUnknown)||IsEqualGUID(id,interfaceID<T>())){*out=static_cast<T*>(this);AddRef();return S_OK;}return E_NOINTERFACE;}
 ULONG STDMETHODCALLTYPE AddRef()override{return ++refs;}ULONG STDMETHODCALLTYPE Release()override{ULONG n=--refs;if(!n)delete this;return n;}
 HRESULT STDMETHODCALLTYPE Invoke(A... args)override{try{return fn(args...);}catch(...){reportTrialStartup(false);uiUnknown=true;stop();signalBackend(false);return E_FAIL;}}
};
template<class T,class... A>struct Factory{template<class F>static T* make(F f){return new Handler<T,A...>(std::function<HRESULT(A...)>(f));}};
#define CB(T,...) Factory<T,__VA_ARGS__>::make
static void resize(){RECT rect{};GetClientRect(window,&rect);if(statusLabel)MoveWindow(statusLabel,16,12,std::max(1L,rect.right-32),40,TRUE);if(controller){rect.top=std::min(64L,rect.bottom);controller->put_Bounds(rect);}}
static void captureStartup(const std::wstring& metadata){
 IStream* stream=nullptr;ok(CreateStreamOnHGlobal(nullptr,TRUE,&stream));
 auto captured=CB(ICoreWebView2CapturePreviewCompletedHandler,HRESULT)([stream,metadata](HRESULT hr)->HRESULT{
  try{ok(hr);STATSTG info{};ok(stream->Stat(&info,STATFLAG_NONAME));need(info.cbSize.QuadPart>0&&info.cbSize.QuadPart<8*1024*1024);HGLOBAL memory=nullptr;ok(GetHGlobalFromStream(stream,&memory));void* bytes=GlobalLock(memory);need(bytes);DWORD count=DWORD(info.cbSize.QuadPart),written=0;std::string header="{\"event\":\"STARTUP_IMAGE\",\"bytes\":"+std::to_string(count)+"}\n";bool sent=WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),header.data(),DWORD(header.size()),&written,nullptr)&&written==header.size();if(sent)sent=WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),bytes,count,&written,nullptr)&&written==count;GlobalUnlock(memory);stream->Release();if(!sent){reportStartupProbe(L"{\"capture_write_failed\":true}");return S_OK;}WriteFile(GetStdHandle(STD_OUTPUT_HANDLE),"\n",1,&written,nullptr);reportStartupProbe(metadata.c_str());return S_OK;}catch(...){stream->Release();reportStartupProbe(L"{\"capture_failed\":true}");return S_OK;}
 });HRESULT result=view->CapturePreview(COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG,stream,captured);captured->Release();if(FAILED(result)){stream->Release();reportStartupProbe(L"{\"capture_request_failed\":true}");}
}
static void startupReply(const wchar_t* state,const std::wstring& message){if(!startupView||!view)return;if(startupMessageProbe&&std::wstring(state)==L"REFUSED"&&startupRefusal==L"DESKTOP_REQUEST_INVALID"){reportStartupProbe(L"{\"backend_refused_original_request\":true,\"child_closed\":true}");return;}std::string data="{\"protocol\":\"PARKWEAVE_STARTUP_V1\",\"state\":"+json(state)+",\"message\":"+json(message)+"}";std::wstring wide(data.begin(),data.end());ok(view->PostWebMessageAsJson(wide.c_str()));}
static void showWeb(const std::wstring& profile){
 trialStage=9; // WebView2 environment
 need(!controller&&!stopping&&!running&&loader);profilePath=profile;environmentPending=true;browserExited=false;
 using Create=HRESULT(STDMETHODCALLTYPE*)(PCWSTR,PCWSTR,ICoreWebView2EnvironmentOptions*,ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler*);
 auto create=(Create)GetProcAddress(loader,"CreateCoreWebView2EnvironmentWithOptions");need(create);
 auto env=CB(ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler,HRESULT,ICoreWebView2Environment*)([](HRESULT hr,ICoreWebView2Environment* e)->HRESULT{
  environmentPending=false;if(FAILED(hr)||!e){reportTrialStartup(false);uiUnknown=true;stop();signalBackend(false);return E_FAIL;}environment=e;e->AddRef();trialStage=10;
  ICoreWebView2Environment5* e5=nullptr;ok(e->QueryInterface(interfaceID<ICoreWebView2Environment5>(),(void**)&e5));EventRegistrationToken exitToken{};
  auto exited=CB(ICoreWebView2BrowserProcessExitedEventHandler,ICoreWebView2Environment*,ICoreWebView2BrowserProcessExitedEventArgs*)([](ICoreWebView2Environment*,ICoreWebView2BrowserProcessExitedEventArgs* a)->HRESULT{UINT32 pid=0;ok(a->get_BrowserProcessId(&pid));if(!browserHandle||pid!=browserPID||WaitForSingleObject(browserHandle,0)!=WAIT_OBJECT_0){uiUnknown=true;signalBackend(false);return E_FAIL;}browserExited=true;finishUIStop();return S_OK;});ok(e5->add_BrowserProcessExited(exited,&exitToken));exited->Release();e5->Release();controllerPending=true;
  auto made=CB(ICoreWebView2CreateCoreWebView2ControllerCompletedHandler,HRESULT,ICoreWebView2Controller*)([](HRESULT hr,ICoreWebView2Controller* c)->HRESULT{
   controllerPending=false;if(FAILED(hr)||!c){reportTrialStartup(false);uiUnknown=true;stop();signalBackend(false);return E_FAIL;}controller=c;c->AddRef();trialStage=11;ok(c->get_CoreWebView2(&view));
   ok(view->get_BrowserProcessId(&browserPID));browserHandle=OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,browserPID);if(browserHandle)remember(browserHandle);need(browserHandle);BOOL inside=FALSE;need(IsProcessInJob(browserHandle,uiJob,&inside)&&inside);wchar_t image[4096];DWORD count=4096;need(QueryFullProcessImageNameW(browserHandle,0,image,&count));need(_wcsicmp(image,(runtimeFolder+L"\\msedgewebview2.exe").c_str())==0);
   if(stopping){closeView();finishUIStop();return S_OK;}
   configureDesktopSettings<ICoreWebView2Settings,ICoreWebView2Settings4>(view,interfaceID<ICoreWebView2Settings4>(),ok);
   EventRegistrationToken token{};
   if(startupView){ICoreWebView2Settings* settings=nullptr;ok(view->get_Settings(&settings));HRESULT enabled=settings->put_IsWebMessageEnabled(TRUE);settings->Release();ok(enabled);
    auto message=CB(ICoreWebView2WebMessageReceivedEventHandler,ICoreWebView2*,ICoreWebView2WebMessageReceivedEventArgs*)([](ICoreWebView2* sender,ICoreWebView2WebMessageReceivedEventArgs* args)->HRESULT{
     if(!startupView||sender!=view||stopping||child||workspaceSwitch||(startupProbe&&!startupMessageProbe))return S_OK;
     LPWSTR source=nullptr,current=nullptr;ok(args->get_Source(&source));ok(view->get_Source(&current));bool trusted=source&&current&&std::wstring(source)==DESKTOP_STARTUP_URI&&std::wstring(current)==DESKTOP_STARTUP_URI;CoTaskMemFree(source);CoTaskMemFree(current);if(!trusted)return S_OK;
     LPWSTR raw=nullptr;if(FAILED(args->TryGetWebMessageAsString(&raw))||!raw){startupReply(L"REFUSED",L"启动请求格式无法识别。");return S_OK;}
     size_t length=wcslen(raw);int count=length<=32768?WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,raw,int(length),nullptr,0,nullptr,nullptr):0;
     std::string data;if(count>0&&count<32768){data.resize(count);WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,raw,int(length),data.data(),count,nullptr,nullptr);}SecureZeroMemory(raw,length*sizeof(wchar_t));CoTaskMemFree(raw);
     if(data.empty()){startupReply(L"REFUSED",L"启动请求过长或包含无效字符。");return S_OK;}data+='\n';startupReply(L"STARTING",L"正在核对原工作台启动条件…");
     try{launchRequest(std::move(data));}catch(...){if(!child)startupReply(L"REFUSED",L"请求未能启动，请保留目录并核对启动条件。");else{startupReply(L"UNKNOWN",L"启动结果尚未确认，请勿重复提交。");stop();signalBackend(false);}}return S_OK;
    });ok(view->add_WebMessageReceived(message,&token));message->Release();
   }
   auto nav=CB(ICoreWebView2NavigationStartingEventHandler,ICoreWebView2*,ICoreWebView2NavigationStartingEventArgs*)([](ICoreWebView2*,ICoreWebView2NavigationStartingEventArgs* a)->HRESULT{LPWSTR u=nullptr;ok(a->get_Uri(&u));bool allowed=!stopping&&(startupView?desktopStartupNavigation(u):sameOrigin(u));if(!allowed&&startupView){std::wstring scheme=u;scheme=scheme.substr(0,scheme.find(L':'));status((L"启动页面导航被限制，协议："+scheme).c_str());}CoTaskMemFree(u);if(!allowed)ok(a->put_Cancel(TRUE));return S_OK;});
   ok(view->add_NavigationStarting(nav,&token));ok(view->add_FrameNavigationStarting(nav,&token));nav->Release();
   if(trialView){
    auto ready=CB(ICoreWebView2NavigationCompletedEventHandler,ICoreWebView2*,ICoreWebView2NavigationCompletedEventArgs*)([](ICoreWebView2* sender,ICoreWebView2NavigationCompletedEventArgs* args)->HRESULT{
     if(trialStartupReported)return S_OK;
     BOOL success=FALSE;ok(args->get_IsSuccess(&success));
     LPWSTR source=nullptr;ok(sender->get_Source(&source));
     bool original=source&&std::wstring(source)==origin+L"/";CoTaskMemFree(source);
     reportTrialStartup(success&&original&&!stopping);
     return S_OK;
    });ok(view->add_NavigationCompleted(ready,&token));ready->Release();
   }
   auto completed=CB(ICoreWebView2NavigationCompletedEventHandler,ICoreWebView2*,ICoreWebView2NavigationCompletedEventArgs*)([](ICoreWebView2*,ICoreWebView2NavigationCompletedEventArgs* a)->HRESULT{if(!startupView)return S_OK;BOOL success=FALSE;COREWEBVIEW2_WEB_ERROR_STATUS error{};ok(a->get_IsSuccess(&success));ok(a->get_WebErrorStatus(&error));if(!success){status((L"启动页面未完成，错误代码："+std::to_wstring(int(error))).c_str());return S_OK;}auto inspected=CB(ICoreWebView2ExecuteScriptCompletedHandler,HRESULT,LPCWSTR)([](HRESULT hr,LPCWSTR value)->HRESULT{if(FAILED(hr)){status(L"页面已导航，内容检查失败。");return S_OK;}if(startupProbe){if(startupMessageProbe&&!probeMessageSent){probeMessageSent=true;auto sent=CB(ICoreWebView2ExecuteScriptCompletedHandler,HRESULT,LPCWSTR)([](HRESULT hr,LPCWSTR)->HRESULT{ok(hr);return S_OK;});HRESULT posted=view->ExecuteScript(L"window.chrome.webview.postMessage(JSON.stringify({protocol:'PARKWEAVE_STARTUP_V1',request:{action:'reopen',instance:'',database_port:0,api_port:0,passwords:{},initialize_profile:false,unexpected:true}}))",sent);sent->Release();ok(posted);}else if(!startupMessageProbe){if(startupCapture)captureStartup(value?value:L"null");else reportStartupProbe(value);}return S_OK;}std::wstring result=value?value:L"null";if(result.size()>240)result.resize(240);status((L"启动页面检查："+result).c_str());return S_OK;});HRESULT result=view->ExecuteScript(L"({state:document.readyState,workspace:document.body.dataset.workspaceDesign,dialog:!!document.querySelector('.desktop-startup-panel:modal'),nodes:document.body?document.body.children.length:0,bytes:document.documentElement.outerHTML.length})",inspected);inspected->Release();ok(result);return S_OK;});ok(view->add_NavigationCompleted(completed,&token));completed->Release();
   auto popup=CB(ICoreWebView2NewWindowRequestedEventHandler,ICoreWebView2*,ICoreWebView2NewWindowRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2NewWindowRequestedEventArgs* a)->HRESULT{return a->put_Handled(TRUE);});ok(view->add_NewWindowRequested(popup,&token));popup->Release();
   auto permission=CB(ICoreWebView2PermissionRequestedEventHandler,ICoreWebView2*,ICoreWebView2PermissionRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2PermissionRequestedEventArgs* a)->HRESULT{return a->put_State(COREWEBVIEW2_PERMISSION_STATE_DENY);});ok(view->add_PermissionRequested(permission,&token));permission->Release();
   auto failed=CB(ICoreWebView2ProcessFailedEventHandler,ICoreWebView2*,ICoreWebView2ProcessFailedEventArgs*)([](ICoreWebView2*,ICoreWebView2ProcessFailedEventArgs*)->HRESULT{stop();return S_OK;});ok(view->add_ProcessFailed(failed,&token));failed->Release();
   auto requested=CB(ICoreWebView2WebResourceRequestedEventHandler,ICoreWebView2*,ICoreWebView2WebResourceRequestedEventArgs*)([](ICoreWebView2*,ICoreWebView2WebResourceRequestedEventArgs* a)->HRESULT{
    ICoreWebView2WebResourceRequest* req=nullptr;ok(a->get_Request(&req));LPWSTR u=nullptr,method=nullptr;ok(req->get_Uri(&u));ok(req->get_Method(&method));bool localDocument=!stopping&&startupView&&desktopStartupDocumentRequest(u,method);bool allowed=!stopping&&!startupView&&sameOrigin(u);CoTaskMemFree(u);CoTaskMemFree(method);req->Release();
    if(localDocument){HGLOBAL memory=GlobalAlloc(GMEM_MOVEABLE,sizeof(STARTUP_HTML)-1);need(memory);void* bytes=GlobalLock(memory);if(!bytes){GlobalFree(memory);need(false);}CopyMemory(bytes,STARTUP_HTML,sizeof(STARTUP_HTML)-1);GlobalUnlock(memory);IStream* stream=nullptr;HRESULT created=CreateStreamOnHGlobal(memory,TRUE,&stream);if(FAILED(created)){GlobalFree(memory);ok(created);}ICoreWebView2WebResourceResponse* response=nullptr;HRESULT made=environment->CreateWebResourceResponse(stream,200,L"OK",L"Content-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff",&response);stream->Release();ok(made);HRESULT assigned=a->put_Response(response);response->Release();ok(assigned);return S_OK;}
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
   for(HWND h:startup)ShowWindow(h,SW_HIDE);resize();
   if(startupView){ok(view->Navigate(DESKTOP_STARTUP_URI));status(L"正在加载园合工作台…");return S_OK;}
   trialStage=12;ok(view->Navigate((origin+L"/").c_str()));running=true;lastAlive=GetTickCount64();status(trialView?L"TRIAL_ONLY · 真实界面试验附件　｜　后台权限仍由原试验持有，未获产品准入":L"园合 · 本地合成资料工作台　｜　关闭窗口将正常停止本次后台");return S_OK;
  });HRESULT result=e->CreateCoreWebView2Controller(window,made);made->Release();if(FAILED(result)){controllerPending=false;uiUnknown=true;stop();signalBackend(false);}return result;
 });HRESULT r=create(runtimeFolder.c_str(),profile.c_str(),nullptr,env);env->Release();if(FAILED(r)){environmentPending=false;uiUnknown=true;stop();signalBackend(false);ok(r);}
}

static std::wstring makeStartupProfile(){
 HANDLE token=nullptr;need(OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&token));std::vector<BYTE> raw(65536);DWORD used=0;
 BOOL queried=GetTokenInformation(token,TokenUser,raw.data(),DWORD(raw.size()),&used);CloseHandle(token);need(queried&&used<=raw.size());
 auto user=(TOKEN_USER*)raw.data();LPWSTR sid=nullptr;need(ConvertSidToStringSidW(user->User.Sid,&sid));std::wstring subject=sid;LocalFree(sid);
 std::wstring sddl=L"O:"+subject+L"D:P(A;OICI;FA;;;"+subject+L")(A;OICI;FA;;;SY)";PSECURITY_DESCRIPTOR sd=nullptr;need(ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(),SDDL_REVISION_1,&sd,nullptr));
 wchar_t temp[32768]{};DWORD length=GetTempPathW(32768,temp);if(!length||length>=32768){LocalFree(sd);need(false);}GUID id{};ok(CoCreateGuid(&id));wchar_t name[40]{};need(StringFromGUID2(id,name,40)>0);std::wstring path=std::wstring(temp)+L"ParkWeave-startup-"+name;
 SECURITY_ATTRIBUTES attributes{sizeof(attributes),sd,FALSE};BOOL created=CreateDirectoryW(path.c_str(),&attributes);LocalFree(sd);need(created);
 HANDLE directory=CreateFileW(path.c_str(),FILE_READ_ATTRIBUTES|READ_CONTROL,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);need(directory!=INVALID_HANDLE_VALUE);remember(directory);runtimeDirectories.push_back(directory);BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(directory,&info)&&(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT));return path;
}
static void openStartup(){try{startupPhase=L"程序文件校验";verifyBootstrap();startupPhase=L"WebView2 运行环境";runtime();startupPhase=L"启动页面目录";startupProfile=makeStartupProfile();startupView=true;startupPhase=L"WebView2 页面创建";showWeb(startupProfile);}catch(...){std::wstring message=L"无法打开工作台："+std::wstring(startupPhase)+L"未通过。未创建业务数据，请保留此窗口用于定位。";status(message.c_str());}}

enum class DesktopInputProblem{INSTANCE,PORTS,PASSWORD_LENGTH,PASSWORD_DUPLICATE};
struct DesktopInputError{DesktopInputProblem problem;};
static const wchar_t* inputHint(DesktopInputProblem problem){switch(problem){
 case DesktopInputProblem::INSTANCE:return L"请填写安装目录；重开使用已有目录，首次新建使用尚不存在的目录。";
 case DesktopInputProblem::PORTS:return L"首次新建需要两个不同的回环端口，均须为1–65535的整数。";
 case DesktopInputProblem::PASSWORD_LENGTH:return L"所选模式每个账号的密码均须为12–256个有效字符；尚未开始安装。";
 case DesktopInputProblem::PASSWORD_DUPLICATE:return L"所选模式每个账号须使用互不相同的密码；尚未开始安装。";
 }return L"请检查启动输入。";}
static unsigned desktopPort(const std::wstring& value){
 if(value.empty())throw DesktopInputError{DesktopInputProblem::PORTS};unsigned n=0;
 for(wchar_t c:value){if(c<L'0'||c>L'9'||n>6553)throw DesktopInputError{DesktopInputProblem::PORTS};n=n*10+unsigned(c-L'0');if(n>65535)throw DesktopInputError{DesktopInputProblem::PORTS};}
 if(!n)throw DesktopInputError{DesktopInputProblem::PORTS};return n;
}
static void desktopPasswordLength(const std::wstring& value){
 // Python's password_bytes counts Unicode characters, not UTF-16 code units.
 size_t count=0;for(size_t i=0;i<value.size();i++){unsigned c=unsigned(value[i]);
  if(c>=0xd800&&c<=0xdbff){if(i+1==value.size()||unsigned(value[i+1])<0xdc00||unsigned(value[i+1])>0xdfff)throw DesktopInputError{DesktopInputProblem::PASSWORD_LENGTH};++i;}
  else if((c>=0xdc00&&c<=0xdfff)||c>0x10ffff)throw DesktopInputError{DesktopInputProblem::PASSWORD_LENGTH};
  if(++count>256)throw DesktopInputError{DesktopInputProblem::PASSWORD_LENGTH};}
 if(count<12)throw DesktopInputError{DesktopInputProblem::PASSWORD_LENGTH};
}
struct DesktopInputPasswords{std::wstring values[6];~DesktopInputPasswords(){for(auto& value:values)SecureZeroMemory(value.data(),value.size()*sizeof(wchar_t));}};
struct DesktopMessage{std::string bytes;~DesktopMessage(){SecureZeroMemory(bytes.data(),bytes.size());}};
static std::string payload(const std::wstring& action){
 std::wstring instance=action==L"status"?L"":text(instanceEdit);if(action!=L"status"&&instance.empty())throw DesktopInputError{DesktopInputProblem::INSTANCE};
 unsigned db=0,api=0;DesktopInputPasswords passwords;bool sample=sampleSelected()&&action!=L"status";int count=sample?4:6;
 if(action==L"new"){
  db=desktopPort(text(portDb));api=desktopPort(text(portApi));if(db==api)throw DesktopInputError{DesktopInputProblem::PORTS};
  for(int i=0;i<count;i++){passwords.values[i]=text(pass[i]);desktopPasswordLength(passwords.values[i]);
   for(int j=0;j<i;j++)if(passwords.values[i]==passwords.values[j])throw DesktopInputError{DesktopInputProblem::PASSWORD_DUPLICATE};}
 }
 // Validate every field before constructing a pipe message or starting native work.
 std::string body="{\"action\":"+json(action)+",\"instance\":"+json(instance)+",\"database_port\":"+std::to_string(db);
 body+=",\"api_port\":"+std::to_string(api)+",\"passwords\":{";
 if(action==L"new")for(int i=0;i<count;i++){if(i)body+=",";body+=json(sample?sampleAccounts[i]:accounts[i])+":"+json(passwords.values[i]);}
 body+="},\"initialize_profile\":";body+=(action==L"new"||SendMessageW(GetDlgItem(window,3),BM_GETCHECK,0,0)==BST_CHECKED)?"true":"false";
 if(sample)body+=",\"sample_collaboration\":true";return body+"}\n";
}
static void launchRequest(std::string input){
 need(!child&&!stopping);DesktopMessage message{std::move(input)};auto& data=message.bytes;clearPasswords();
 if(bootstrapPins.empty())verifyBootstrap();
 try{if(!loader)runtime();}catch(...){SecureZeroMemory(data.data(),data.size());stopping=true;status(L"已安装的官方 x64 WebView2 Runtime 缺失或无法核验。不会安装、修复或启动 Edge 浏览器。");return;}
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
static void launch(const std::wstring& action){launchRequest(payload(action));}
static void event(const std::string& line){
 if(trialView){
  if(line=="PWUI1\tALIVE\t"+trialNonce&&trialAttached){if(!stopping)lastAlive=GetTickCount64();return;}
  need(!trialAttached&&!stopping&&line.rfind("PWUI1\tSTART\t",0)==0);
  std::vector<std::string> fields;std::istringstream input(line);std::string field;while(std::getline(input,field,'\t'))fields.push_back(field);need(fields.size()==7);
  need(fields[2].find_first_not_of("0123456789")==std::string::npos&&!fields[2].empty());unsigned port=std::stoul(fields[2]);need(port&&port<=65535);
  need(fields[3].find_first_not_of("0123456789")==std::string::npos&&!fields[3].empty());trialProfile=(HANDLE)(ULONG_PTR)std::stoull(fields[3]);remember(trialProfile);
  need(std::stoul(fields[4])==GetProcessId(trialParent)&&WaitForSingleObject(trialParent,0)==WAIT_TIMEOUT);
  FILETIME created{},exited{},kernel{},user{};need(GetProcessTimes(trialParent,&created,&exited,&kernel,&user));char birth[17];sprintf(birth,"%08x%08x",created.dwHighDateTime,created.dwLowDateTime);need(fields[5]==birth);
  need(fields[6].size()==32&&fields[6].find_first_not_of("0123456789abcdef")==std::string::npos);trialNonce=fields[6];
  BY_HANDLE_FILE_INFORMATION info{};need(GetFileInformationByHandle(trialProfile,&info)&&(info.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(info.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT));
  wchar_t profile[4096]{};DWORD count=GetFinalPathNameByHandleW(trialProfile,profile,4096,0);need(count>7&&count<4096&&std::wstring(profile).rfind(L"\\\\?\\",0)==0&&profile[5]==L':'&&profile[6]==L'\\');
  trialStage=2;verifyBootstrap();runtime();origin=L"http://127.0.0.1:"+std::to_wstring(port);trialAttached=true;backendReady=true;lastAlive=GetTickCount64();showWeb(std::wstring(profile+4));return;
 }
 if(line=="PW1\tALIVE"){if(stopping)return;need(backendReady);lastAlive=GetTickCount64();return;}
 if(line=="PW1\tSTOPPED"){need(stopping&&stopSent&&browserExited&&!uiUnknown);terminal=true;status(L"本次后台已正常停止，资料与待核对请求均已保留。");if(closeWhenStopped)PostMessageW(window,WM_CLOSE,0,0);return;}
 if(line=="PW1\tUNKNOWN\tSYSTEM_CRT_REVOCATION_EVIDENCE_UNAVAILABLE"){terminal=true;uiUnknown=true;crtRevocationUnknown=true;stop();signalBackend(false);status(L"无法使用现有离线信息完成证书吊销核验，请由系统维护方检查。本次状态未确认，请保留现场。");return;}
 if(line.rfind("PW1\tREFUSED\t",0)==0){terminal=true;std::wstring reason(line.begin()+12,line.end());startupRefusal=reason;status((L"原始入口拒绝："+reason+L"。没有自动初始化、修复或重试。").c_str());return;}
 if(line.rfind("PW1\tRUNNING\t",0)==0){need(!stopping&&!backendReady);auto split=line.find('\t',12);need(split!=std::string::npos);std::string p=line.substr(12,split-12);need(!p.empty()&&p.find_first_not_of("0123456789")==std::string::npos);int port=std::stoi(p);need(port>0&&port<=65535);origin=L"http://127.0.0.1:"+std::to_wstring(port);backendReady=true;lastAlive=GetTickCount64();if(startupView){pendingWorkspaceProfile=unhex(line.substr(split+1));workspaceSwitch=true;workspaceSwitchAt=GetTickCount64();closeView();if(environment){environment->Release();environment=nullptr;}status(L"后台已就绪，正在进入工作台…");}else showWeb(unhex(line.substr(split+1)));return;}
 uiUnknown=true;status(L"本次状态未知，已停止页面通信并保留现场；没有重启或重试。");stop();signalBackend(false);
}
static HWND control(const wchar_t* cls,const wchar_t* label,DWORD style,int x,int y,int w,int h,int id=0){HWND c=CreateWindowExW(0,cls,label,WS_CHILD|WS_VISIBLE|style,x,y,w,h,window,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr);need(c);SendMessageW(c,WM_SETFONT,(WPARAM)GetStockObject(DEFAULT_GUI_FONT),TRUE);startup.push_back(c);return c;}
static LRESULT CALLBACK procedure(HWND h,UINT message,WPARAM w,LPARAM l){try{switch(message){
 case WM_CREATE:{window=h;statusLabel=control(L"STATIC",L"园合 ParkWeave · 独立桌面工作台",0,24,16,960,40);startup.clear();
 control(L"STATIC",L"已有安装目录（重开只读既有绑定；首次安装必须使用新目录）",0,24,92,900,24);instanceEdit=control(L"EDIT",L"",WS_BORDER|ES_AUTOHSCROLL,24,122,920,32);
 startButton=control(L"BUTTON",L"重开工作台",BS_PUSHBUTTON,24,174,144,32,1);newButton=control(L"BUTTON",L"首次新建安装",BS_PUSHBUTTON,180,174,144,32,2);
 control(L"STATIC",L"首次新建的回环端口（重开使用原保护配置）",0,24,266,800,24);portDb=control(L"EDIT",L"55432",WS_BORDER|ES_NUMBER,24,298,160,32);portApi=control(L"EDIT",L"58761",WS_BORDER|ES_NUMBER,204,298,160,32);
 control(L"BUTTON",L"首次在已有安装使用桌面：独占建立桌面资料目录（不重建数据库）",BS_AUTOCHECKBOX,24,218,960,32,3);
 control(L"BUTTON",L"首次新建完整合成样例：四角色（重开读取原模式）",BS_AUTOCHECKBOX,400,298,584,32,4);
 control(L"STATIC",L"首次新建：所选账号分别设置12–256字符的不同密码；重开无需填写。",0,24,358,960,24);
 for(int i=0;i<6;i++){std::wstring label=(i<3?L"企业 ":L"专员 ")+std::wstring(1,wchar_t(L'A'+i%3));int x=24+(i%3)*310,y=397+(i/3)*86;passLabels[i]=control(L"STATIC",label.c_str(),0,x,y,270,24);pass[i]=control(L"EDIT",L"",WS_BORDER|ES_PASSWORD|ES_AUTOHSCROLL,x,y+28,284,32);SendMessageW(pass[i],EM_SETLIMITTEXT,512,0);}
 control(L"STATIC",L"合成样例 · 无真实园区接入。缺运行条件会明确停止，不安装运行库、不改系统安全设置。",0,24,602,960,48);SendMessageW(GetDlgItem(h,4),BM_SETCHECK,BST_CHECKED,0);sampleInputs();SetTimer(h,1,500,nullptr);return 0;}
 case WM_COMMAND:if(trialView)return 0;if(LOWORD(w)==4){sampleInputs();return 0;}if(LOWORD(w)==1)launch(L"reopen");else if(LOWORD(w)==2)launch(L"new");return 0;
 case EVENT_LINE:{auto p=(std::string*)l;std::string line=*p;delete p;event(line);return 0;}
 case EVENT_EXIT:{if(reader.joinable())reader.join();closeTracked(childOutput);closeTracked(child);if(childInput){closeTracked(childInput);}if(job){closeTracked(job);}if(pythonPin!=INVALID_HANDLE_VALUE){closeTracked(pythonPin);}
  if(startupView&&!backendReady&&terminal&&!uiUnknown&&!closeWhenStopped&&!stopping&&view&&!startupRefusal.empty()){stopping=false;stopSent=false;terminal=false;startupReply(L"REFUSED",L"当前启动条件未通过，未进入办理："+startupRefusal);startupRefusal.clear();return 0;}
  closeView();backendReady=false;if(!terminal||uiUnknown){stopping=true;if(crtRevocationUnknown)status(L"无法完成系统运行库的离线吊销核验。本次状态未确认，保留目录与请求，不自动重开或更改信任设置。");else status(L"本次后台退出未获确认：状态未知，保留目录与请求，不自动重开。");}else if(closeWhenStopped)DestroyWindow(h);else{stopping=true;}return 0;}
 case TRIAL_EOF:trialEof=true;if(reader.joinable())reader.join();if(!trialAck){uiUnknown=true;stop();}if(trialAck&&!uiUnknown){closeTracked(trialInput);closeTracked(trialOutput);closeTracked(trialParent);closeTracked(trialProfile);DestroyWindow(h);}return 0;
 case WM_TIMER:
  if(workspaceSwitch&&!stopping){if(browserHandle&&WaitForSingleObject(browserHandle,0)==WAIT_OBJECT_0&&uiProcessesExited()){workspaceSwitch=false;startupView=false;browserExited=true;closeTracked(browserHandle);browserPID=0;auto profile=pendingWorkspaceProfile;pendingWorkspaceProfile.clear();showWeb(profile);}else if(GetTickCount64()-workspaceSwitchAt>30000){workspaceSwitch=false;uiUnknown=true;stop();signalBackend(false);status(L"界面交接未确认，保留原工作台与请求。");}}
  if(startupProbe&&!probeReported&&GetTickCount64()-probeStarted>30000){reportStartupProbe(L"{\"timeout\":true}");}finishUIStop();if(trialView&&trialParent&&WaitForSingleObject(trialParent,0)!=WAIT_TIMEOUT){uiUnknown=true;stop();}if(child&&!reader.joinable()&&WaitForSingleObject(child,0)==WAIT_OBJECT_0)PostMessageW(window,EVENT_EXIT,0,0);if(backendReady&&!stopping&&GetTickCount64()-lastAlive>4000)stop();if(stopping&&(child||trialView)&&GetTickCount64()-stopStarted>30000){uiUnknown=true;signalBackend(false);status(L"嵌入进程退出未确认：本次保留UNKNOWN，不重试或认作正常停止。");}return 0;
 case WM_APP+90:openStartup();return 0;
 case WM_SIZE:resize();return 0;
 case WM_GETMINMAXINFO:{auto m=(MINMAXINFO*)l;m->ptMinTrackSize=controller?POINT{360,360}:POINT{1040,720};return 0;}
 case WM_CLOSE:
  // No backend has been launched in the startup view. There is no business
  // request to reconcile; do not wait forever for an idle WebView process.
  if(startupView&&!child&&!trialView){stopping=true;closeView();if(environment){environment->Release();environment=nullptr;}DestroyWindow(h);return 0;}
  if(child||trialView){closeWhenStopped=true;stop();return 0;}closeView();DestroyWindow(h);return 0;
 case WM_DESTROY:KillTimer(h,1);PostQuitMessage(0);return 0;
 }}catch(const DesktopInputError& error){clearPasswords();status(inputHint(error.problem));return 0;}
 catch(...){reportTrialStartup(false);clearPasswords();status(L"桌面启动或运行核验失败，已保留现有资料；没有浏览器或安装回退。");if(child||trialView){uiUnknown=true;stop();}}return DefWindowProcW(h,message,w,l);}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,LPWSTR arguments,int show){
 try{startupMessageProbe=arguments&&std::wstring(arguments)==L"--startup-message-probe";startupCapture=arguments&&std::wstring(arguments)==L"--startup-capture";startupProbe=startupCapture||startupMessageProbe||(arguments&&std::wstring(arguments)==L"--startup-probe");if(startupProbe){need(GetFileType(GetStdHandle(STD_OUTPUT_HANDLE))==FILE_TYPE_PIPE);probeStarted=GetTickCount64();show=SW_HIDE;}wchar_t path[32768];DWORD n=GetModuleFileNameW(nullptr,path,32768);need(n&&n<32768);base=path;auto p=base.find_last_of(L"\\");need(p!=std::wstring::npos);base.resize(p);SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32);
  ok(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED));SetCurrentProcessExplicitAppUserModelID(L"ParkWeave.Desktop");
  uiJob=CreateJobObjectW(nullptr,nullptr);if(uiJob)remember(uiJob);need(uiJob);JOBOBJECT_EXTENDED_LIMIT_INFORMATION lifetime{};lifetime.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;need(SetInformationJobObject(uiJob,JobObjectExtendedLimitInformation,&lifetime,sizeof(lifetime)));need(AssignProcessToJobObject(uiJob,GetCurrentProcess()));
  WNDCLASSEXW cls{sizeof(cls)};cls.lpfnWndProc=procedure;cls.hInstance=instance;cls.hCursor=LoadCursorW(nullptr,IDC_ARROW);cls.hIcon=(HICON)LoadImageW(instance,MAKEINTRESOURCEW(1),IMAGE_ICON,GetSystemMetrics(SM_CXICON),GetSystemMetrics(SM_CYICON),LR_SHARED);cls.hIconSm=(HICON)LoadImageW(instance,MAKEINTRESOURCEW(1),IMAGE_ICON,GetSystemMetrics(SM_CXSMICON),GetSystemMetrics(SM_CYSMICON),LR_SHARED);need(cls.hIcon&&cls.hIconSm);cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);cls.lpszClassName=L"ParkWeaveDesktop";need(RegisterClassExW(&cls));
  RECT area{};SystemParametersInfoW(SPI_GETWORKAREA,0,&area,0);int width=std::min(1440L,area.right-area.left),height=std::min(900L,area.bottom-area.top);
  HWND h=CreateWindowExW(startupCapture?WS_EX_TOOLWINDOW:WS_EX_APPWINDOW,cls.lpszClassName,L"园合 ParkWeave · 本地工作台",WS_OVERLAPPEDWINDOW,area.left+(area.right-area.left-width)/2,area.top+(area.bottom-area.top-height)/2,width,height,nullptr,nullptr,instance,nullptr);need(h);ShowWindow(h,startupCapture?SW_SHOWNOACTIVATE:show);if(startupCapture)SetWindowPos(h,HWND_BOTTOM,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);UpdateWindow(h);
  if(arguments&&*arguments&&!startupProbe){need(std::wstring(arguments)==L"--ci-trial-view");trialView=true;
   wchar_t value[256]{};need(GetEnvironmentVariableW(L"GITHUB_ACTIONS",value,256)&&std::wstring(value)==L"true");need(GetEnvironmentVariableW(L"GITHUB_JOB",value,256)&&std::wstring(value)==L"native-business-trial");
   trialInput=GetStdHandle(STD_INPUT_HANDLE);trialOutput=GetStdHandle(STD_OUTPUT_HANDLE);trialParent=GetStdHandle(STD_ERROR_HANDLE);
   need(GetFileType(trialInput)==FILE_TYPE_PIPE&&GetFileType(trialOutput)==FILE_TYPE_PIPE&&GetProcessId(trialParent));remember(trialInput);remember(trialOutput);remember(trialParent);
   for(HWND c:startup)ShowWindow(c,SW_HIDE);SetWindowTextW(window,L"园合 ParkWeave · TRIAL_ONLY 界面验收");status(L"TRIAL_ONLY · 等待原试验提供已核工作台；未获生产准入");
   reader=std::thread([]{std::string line;char c;DWORD used=0;while(ReadFile(trialInput,&c,1,&used,nullptr)&&used){if(c=='\n'){auto p=new std::string(line);if(!PostMessageW(window,EVENT_LINE,0,(LPARAM)p)){delete p;break;}line.clear();}else{line+=c;if(line.size()>1024)break;}}PostMessageW(window,TRIAL_EOF,0,0);});
  }
  if(!trialView){for(HWND c:startup)ShowWindow(c,SW_HIDE);status(L"正在打开园合工作台…");PostMessageW(window,WM_APP+90,0,0);}
  MSG msg;while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(h,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
  if(environment)environment->Release();if(loader&&!FreeLibrary(loader))uiUnknown=true;closeTracked(loaderPin);closeTracked(runtimePin);CoUninitialize();return uiUnknown?2:0;
 }catch(...){if(startupProbe){reportStartupProbe(L"{\"host_error\":true}");return 2;}MessageBoxW(nullptr,L"桌面宿主未能启动；不会打开浏览器、自动安装或更改系统设置。",L"ParkWeave",MB_OK|MB_ICONERROR);return 2;}
}
