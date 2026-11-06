// CI-only UIAutomation client for the actual packaged EXE. Never a product
// entry, authority issuer, script injector, browser fallback or network client.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define INITGUID
#include <windows.h>
#include <uiautomation.h>
#include <uiautomationcoreapi.h>
#include <wincodec.h>
#include <bcrypt.h>
#include <objbase.h>
#include <string>
#include <vector>
#include <set>
#include <sstream>
#include <thread>
#include <mutex>
#include <atomic>
#include <stdexcept>
#include <cstdio>
#include <algorithm>
#include <memory>

static void need(bool b){if(!b)throw std::runtime_error("OWN_UI_UNKNOWN");}
static std::string phase="OPEN",failureCode="NOT_RECORDED";
struct UIAError{HRESULT code;};
static void ok(HRESULT r){if(FAILED(r)){char value[9];sprintf(value,"%08x",unsigned(r));failureCode=value;throw UIAError{r};}}
template<class T>struct Ref{T* p=nullptr;Ref()=default;Ref(const Ref&)=delete;Ref& operator=(const Ref&)=delete;Ref(Ref&& other)noexcept:p(other.p){other.p=nullptr;}~Ref(){if(p)p->Release();}T** put(){need(!p);return &p;}T* operator->(){need(p);return p;}};
static ULONGLONG deadline=0,cleanupDeadline=0;static void guard(){need(GetTickCount64()<deadline);}
static std::string readLine(HANDLE h){std::string s;char c;DWORD n;while(ReadFile(h,&c,1,&n,nullptr)&&n){if(c=='\n')return s;need(s.size()<32768&&c!='\r');s+=c;}throw std::runtime_error("PIPE_UNKNOWN");}
static void writeLine(HANDLE h,const std::string& s){DWORD n=0;need(s.size()<32768&&WriteFile(h,(s+"\n").data(),DWORD(s.size()+1),&n,nullptr)&&n==s.size()+1);}
static std::vector<std::string> split(const std::string& s){std::vector<std::string> v;std::istringstream input(s);std::string x;while(std::getline(input,x,'\t'))v.push_back(x);return v;}
static std::wstring wide(const std::string& s){need(s.size()%4==0&&s.size()<=16384);std::wstring w;for(size_t i=0;i<s.size();i+=4){auto hex=[](char c){need(c>='0'&&c<='9'||c>='a'&&c<='f');return c<='9'?c-'0':c-'a'+10;};unsigned lo=hex(s[i])*16+hex(s[i+1]),hi=hex(s[i+2])*16+hex(s[i+3]);w+=wchar_t(lo+(hi<<8));}need(w.find(L'\0')==std::wstring::npos);return w;}
static std::string hex(const std::wstring& w){std::string s;char b[5];for(auto c:w){sprintf(b,"%02x%02x",unsigned(c)&255,unsigned(c)>>8);s+=b;}return s;}
struct PrivateLine{std::string s;~PrivateLine(){SecureZeroMemory(s.data(),s.size());}};
static HANDLE job=nullptr,process=nullptr,hostInput=nullptr,hostOutput=nullptr;
static bool childCreated=false,resumeAttempted=false,suspendedCleanupAttempted=false;
static HWND hwnd=nullptr;static DWORD hostPID=0;static ULONGLONG hostBirth=0;static bool ambiguousWindow=false;
static std::atomic<bool> ack{false},pipeUnknown{false},heartbeatStop{false};
static std::atomic<bool> startupDone{false};
static std::string startupFailure;
static std::thread heartbeat,reader;static std::mutex writing;
static std::string nonce;static IUIAutomation* automation=nullptr;
struct OwnedHandle{HANDLE value;bool attempted=false,closed=false;};
static std::vector<std::unique_ptr<OwnedHandle>> ownedHandles;
static void remember(HANDLE h){if(h&&h!=INVALID_HANDLE_VALUE)ownedHandles.push_back(std::make_unique<OwnedHandle>(OwnedHandle{h}));}
static void closeKnown(HANDLE& h){if(h){OwnedHandle* original=nullptr;for(auto i=ownedHandles.rbegin();i!=ownedHandles.rend();++i)if((*i)->value==h&&!(*i)->closed){original=i->get();break;}need(original&&!original->attempted);original->attempted=true;original->closed=CloseHandle(h);if(original->closed)h=nullptr;need(original->closed);}}
static ULONGLONG birth(HANDLE h){FILETIME c{},e{},k{},u{};need(GetProcessTimes(h,&c,&e,&k,&u));return (ULONGLONG(c.dwHighDateTime)<<32)|c.dwLowDateTime;}
static void identity(){guard();need(process&&GetProcessId(process)==hostPID&&birth(process)==hostBirth&&WaitForSingleObject(process,0)==WAIT_TIMEOUT);BOOL inside=FALSE;need(IsProcessInJob(process,job,&inside)&&inside);if(hwnd){DWORD pid=0;need(IsWindow(hwnd)&&GetWindowThreadProcessId(hwnd,&pid)&&pid==hostPID);}}
static BOOL CALLBACK findWindow(HWND w,LPARAM){DWORD pid=0;GetWindowThreadProcessId(w,&pid);wchar_t cls[80]{};GetClassNameW(w,cls,80);if(pid==hostPID&&std::wstring(cls)==L"ParkWeaveDesktop"&&IsWindowVisible(w)){if(hwnd&&hwnd!=w){ambiguousWindow=true;return FALSE;}hwnd=w;}return TRUE;}
static ULONG active(){JOBOBJECT_BASIC_ACCOUNTING_INFORMATION i{};need(QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&i,sizeof(i),nullptr));return i.ActiveProcesses;}
static void start(const std::wstring& exe,HANDLE profile,unsigned port){
 guard();need(port&&port<=65535&&GetFileType(GetStdHandle(STD_INPUT_HANDLE))==FILE_TYPE_PIPE);
 job=CreateJobObjectW(nullptr,nullptr);remember(job);need(job);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;need(SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits)));
 HANDLE input=nullptr,output=nullptr,parent=nullptr;SECURITY_ATTRIBUTES sa{sizeof(sa),nullptr,TRUE};
 BOOL piped=CreatePipe(&input,&hostInput,&sa,0);remember(input);remember(hostInput);need(piped);
 piped=CreatePipe(&hostOutput,&output,&sa,0);remember(hostOutput);remember(output);need(piped);
 need(SetHandleInformation(hostInput,HANDLE_FLAG_INHERIT,0)&&SetHandleInformation(hostOutput,HANDLE_FLAG_INHERIT,0));
 BOOL duplicated=DuplicateHandle(GetCurrentProcess(),GetCurrentProcess(),GetCurrentProcess(),&parent,SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,TRUE,0);remember(parent);need(duplicated);
 need(SetHandleInformation(profile,HANDLE_FLAG_INHERIT,HANDLE_FLAG_INHERIT));
 STARTUPINFOEXW si{};si.StartupInfo.cb=sizeof(si);si.StartupInfo.dwFlags=STARTF_USESTDHANDLES;si.StartupInfo.hStdInput=input;si.StartupInfo.hStdOutput=output;si.StartupInfo.hStdError=parent;
 SIZE_T bytes=0;InitializeProcThreadAttributeList(nullptr,1,0,&bytes);need(bytes&&bytes<65536);std::vector<BYTE> attrs(bytes);si.lpAttributeList=(LPPROC_THREAD_ATTRIBUTE_LIST)attrs.data();need(InitializeProcThreadAttributeList(si.lpAttributeList,1,0,&bytes));
 HANDLE inherited[]={input,output,parent,profile};need(UpdateProcThreadAttribute(si.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited,sizeof(inherited),nullptr,nullptr));
 std::wstring command=L"\""+exe+L"\" --ci-trial-view";PROCESS_INFORMATION pi{};
 BOOL created=CreateProcessW(exe.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_SUSPENDED|EXTENDED_STARTUPINFO_PRESENT,nullptr,nullptr,&si.StartupInfo,&pi);
 process=pi.hProcess;remember(process);remember(pi.hThread);hostPID=pi.dwProcessId;childCreated=created;need(created); // retain even failed-return outputs, never infer ownership success
 DeleteProcThreadAttributeList(si.lpAttributeList);closeKnown(input);closeKnown(output);closeKnown(parent);
 need(AssignProcessToJobObject(job,process));hostBirth=birth(process);resumeAttempted=true;need(ResumeThread(pi.hThread)!=DWORD(-1));closeKnown(pi.hThread);
 BYTE random[16];need(BCryptGenRandom(nullptr,random,16,BCRYPT_USE_SYSTEM_PREFERRED_RNG)==0);char part[3];for(auto c:random){sprintf(part,"%02x",c);nonce+=part;}
 char parentBirth[17];sprintf(parentBirth,"%016llx",(unsigned long long)birth(GetCurrentProcess()));
 writeLine(hostInput,"PWUI1\tSTART\t"+std::to_string(port)+"\t"+std::to_string((ULONG_PTR)profile)+"\t"+std::to_string(GetCurrentProcessId())+"\t"+parentBirth+"\t"+nonce);
 heartbeat=std::thread([]{try{while(!heartbeatStop){std::this_thread::sleep_for(std::chrono::milliseconds(500));if(!heartbeatStop){std::lock_guard<std::mutex> lock(writing);writeLine(hostInput,"PWUI1\tALIVE\t"+nonce);}}}catch(...){pipeUnknown=true;}});
 reader=std::thread([]{try{
  auto first=readLine(hostOutput);
  if(first!="PWUI1\tVIEW_READY\t"+nonce){
   auto prefix="PWUI1\tVIEW_FAILED\t"+nonce+"\t";
   need(first.rfind(prefix,0)==0);
   startupFailure=first.substr(prefix.size());
   auto details=split(startupFailure);
   auto hexCode=[](const std::string& code){return code.size()==8&&code.find_first_not_of("0123456789abcdef")==std::string::npos;};
   need(!details.empty()&&hexCode(details[0]));
   auto stage=std::stoul(details[0],nullptr,16);need(stage>=1&&stage<=27);
   if(stage>=20&&stage<=24)need(details.size()==3&&details[1].size()==1&&details[1][0]>='0'&&details[1][0]<='7'&&hexCode(details[2]));
   else need(details.size()==1);
   startupDone=true;return;
  }
  startupDone=true;
  need(readLine(hostOutput)=="PWUI1\tVIEW_RELEASED\t"+nonce);ack=true;heartbeatStop=true;if(heartbeat.joinable())heartbeat.join();std::lock_guard<std::mutex> lock(writing);closeKnown(hostInput);
 }catch(...){pipeUnknown=true;}});
 while(!hwnd){identity();EnumWindows(findWindow,0);need(!ambiguousWindow);if(!hwnd)Sleep(100);}identity();
 phase="OPEN_WAIT_VIEW";
 auto startupEnd=std::min(deadline,GetTickCount64()+45000);
 while(!startupDone){identity();need(!pipeUnknown&&GetTickCount64()<startupEnd);Sleep(100);}
 if(!startupFailure.empty()){phase="OPEN_VIEW_FAILED";failureCode=startupFailure;need(false);}
 identity();need(!pipeUnknown);
 ok(CoCreateInstance(CLSID_CUIAutomation,nullptr,CLSCTX_INPROC_SERVER,IID_IUIAutomation,(void**)&automation));
}
static Ref<IUIAutomationElement> root(){identity();Ref<IUIAutomationElement> value;ok(automation->ElementFromHandle(hwnd,value.put()));return value;}
static std::wstring name(IUIAutomationElement* element){BSTR s=nullptr;ok(element->get_CurrentName(&s));std::wstring value=s?s:L"";SysFreeString(s);need(value.size()<=8192);return value;}
static std::wstring automationId(IUIAutomationElement* element){
 BSTR value=nullptr;ok(element->get_CurrentAutomationId(&value));
 std::wstring id=value?value:L"";SysFreeString(value);need(id.size()<=8192);return id;
}
static IUIAutomationElement* find(const std::wstring& wanted,CONTROLTYPEID type,bool prefix=false,bool includeOffscreen=false,bool byId=false){
 auto base=root();
 VARIANT kind{};kind.vt=VT_I4;kind.lVal=type;
 Ref<IUIAutomationCondition> typeFilter,nameFilter,combined;
 ok(automation->CreatePropertyCondition(UIA_ControlTypePropertyId,kind,typeFilter.put()));
 if(!prefix){
  VARIANT label{};label.vt=VT_BSTR;label.bstrVal=SysAllocStringLen(wanted.data(),UINT(wanted.size()));need(label.bstrVal);
  HRESULT result=automation->CreatePropertyCondition(byId?UIA_AutomationIdPropertyId:UIA_NamePropertyId,label,nameFilter.put());
  SysFreeString(label.bstrVal);ok(result);
  ok(automation->CreateAndCondition(typeFilter.p,nameFilter.p,combined.put()));
 }
 Ref<IUIAutomationElementArray> values;
 ok(base->FindAll(TreeScope_Descendants,prefix?typeFilter.p:combined.p,values.put()));
 int count=0;ok(values->get_Length(&count));need(count>=0&&count<4000);
 Ref<IUIAutomationElement> match;
 for(int i=0;i<count;i++){
  Ref<IUIAutomationElement> e;ok(values->GetElement(i,e.put()));
  auto text=byId?automationId(e.p):name(e.p);if(prefix?text.rfind(wanted,0)!=0:text!=wanted)continue;
  BOOL off=TRUE,enabled=FALSE;ok(e->get_CurrentIsOffscreen(&off));ok(e->get_CurrentIsEnabled(&enabled));
  if((off&&!includeOffscreen)||!enabled)continue;
  need(!match.p);match.p=e.p;e.p=nullptr;
 }
 auto result=match.p;match.p=nullptr;return result;
}
static IUIAutomationElement* await(const std::wstring& wanted,CONTROLTYPEID type,bool prefix=false,bool scroll=false,ULONGLONG end=0,bool byId=false){
 if(!end)end=std::min(deadline,GetTickCount64()+15000);
 bool scrolled=false;
 const auto originalPhase=phase;
 while(true){
  identity();need(GetTickCount64()<end);
  Ref<IUIAutomationElement> target;
  try{
   auto visible=find(wanted,type,prefix,false,byId);
   if(visible){phase=originalPhase;failureCode="NOT_RECORDED";return visible;}
   if(scroll&&!scrolled)target.p=find(wanted,type,prefix,true,byId);
  }catch(const UIAError& error){
   if(error.code!=UIA_E_ELEMENTNOTAVAILABLE)throw;
   Sleep(100);continue;
  }
  if(target.p){
    phase="SCROLL_CONTROL";
    Ref<IUIAutomationScrollItemPattern> item;
    ok(target->GetCurrentPatternAs(UIA_ScrollItemPatternId,IID_IUIAutomationScrollItemPattern,(void**)item.put()));
    ok(item->ScrollIntoView());scrolled=true;phase="SCROLL_VISIBLE";
  }
  Sleep(100);
 }
}
static void set(const std::wstring& selector,std::wstring& value){Ref<IUIAutomationElement> e;e.p=await(selector,UIA_EditControlTypeId,false,true);Ref<IUIAutomationValuePattern> p;ok(e->GetCurrentPatternAs(UIA_ValuePatternId,IID_IUIAutomationValuePattern,(void**)p.put()));BOOL ro=TRUE;ok(p->get_CurrentIsReadOnly(&ro));need(!ro);BSTR data=SysAllocStringLen(value.data(),UINT(value.size()));need(data);HRESULT result=p->SetValue(data);SecureZeroMemory(data,SysStringLen(data)*sizeof(wchar_t));SysFreeString(data);SecureZeroMemory(value.data(),value.size()*sizeof(wchar_t));ok(result);}
static void click(const std::wstring& selector,bool prefix){
 auto end=std::min(deadline,GetTickCount64()+15000);
 while(true){
  phase="CLICK_FIND";Ref<IUIAutomationElement> e;e.p=await(selector,UIA_ButtonControlTypeId,prefix,true,end);
  phase="CLICK_PATTERN";Ref<IUIAutomationInvokePattern> p;
  HRESULT result=e->GetCurrentPatternAs(UIA_InvokePatternId,IID_IUIAutomationInvokePattern,(void**)p.put());
  if(result==UIA_E_ELEMENTNOTAVAILABLE&&GetTickCount64()<end){Sleep(100);continue;}
  ok(result);identity();need(GetTickCount64()<end);
  phase="CLICK_INVOKE";ok(p->Invoke());return;
 }
}
static void select(const std::wstring& selector,const std::wstring& option,bool byId=false){
 phase=byId?"SELECT_ID_CONTROL":"SELECT_CONTROL";
 Ref<IUIAutomationElement> e;e.p=await(selector,UIA_ComboBoxControlTypeId,false,true,0,byId);
 phase="SELECT_EXPAND";
 Ref<IUIAutomationExpandCollapsePattern> expand;ok(e->GetCurrentPatternAs(UIA_ExpandCollapsePatternId,IID_IUIAutomationExpandCollapsePattern,(void**)expand.put()));ok(expand->Expand());
 phase="SELECT_OPTIONS";
 VARIANT label{};label.vt=VT_BSTR;label.bstrVal=SysAllocStringLen(option.data(),UINT(option.size()));need(label.bstrVal);
 Ref<IUIAutomationCondition> exactName;
 HRESULT filter=automation->CreatePropertyCondition(UIA_NamePropertyId,label,exactName.put());
 SysFreeString(label.bstrVal);ok(filter);
 VARIANT kind{};kind.vt=VT_I4;
 Ref<IUIAutomationCondition> listItem,menuItem,itemType,condition;
 kind.lVal=UIA_ListItemControlTypeId;ok(automation->CreatePropertyCondition(UIA_ControlTypePropertyId,kind,listItem.put()));
 kind.lVal=UIA_MenuItemControlTypeId;ok(automation->CreatePropertyCondition(UIA_ControlTypePropertyId,kind,menuItem.put()));
 ok(automation->CreateOrCondition(listItem.p,menuItem.p,itemType.put()));
 ok(automation->CreateAndCondition(exactName.p,itemType.p,condition.put()));
 Ref<IUIAutomationElement> chosen;
 auto optionEnd=std::min(deadline,GetTickCount64()+15000);
 while(!chosen.p){
  identity();need(GetTickCount64()<optionEnd);
  Ref<IUIAutomationElementArray> items;ok(e->FindAll(TreeScope_Descendants,condition.p,items.put()));
  int count=0;ok(items->get_Length(&count));need(count>=0&&count<=1);
  if(count==1)ok(items->GetElement(0,chosen.put()));
  else Sleep(100);
 }
 phase="SELECT_ITEM";
 BOOL enabled=FALSE;ok(chosen->get_CurrentIsEnabled(&enabled));need(enabled&&name(chosen.p)==option);
 Ref<IUIAutomationSelectionItemPattern> pattern;ok(chosen->GetCurrentPatternAs(UIA_SelectionItemPatternId,IID_IUIAutomationSelectionItemPattern,(void**)pattern.put()));ok(pattern->Select());
 phase="SELECT_CONFIRM";
 BOOL selected=FALSE;ok(pattern->get_CurrentIsSelected(&selected));need(selected);
 ExpandCollapseState state;ok(expand->get_CurrentExpandCollapseState(&state));
 if(state!=ExpandCollapseState_Collapsed)ok(expand->Collapse());
}
static std::wstring referenceAt(unsigned revision){
 need(revision>=1&&revision<=64);auto end=std::min(deadline,GetTickCount64()+15000);std::wstring suffix=L" · 版本 "+std::to_wstring(revision);
 while(true){identity();need(GetTickCount64()<end);Ref<IUIAutomationElement> e;e.p=find(L"事项 ",UIA_TextControlTypeId,true);if(e.p){auto value=name(e.p);if(value.size()>=suffix.size()&&value.compare(value.size()-suffix.size(),suffix.size(),suffix)==0)return value;}Sleep(50);}
}
static void visible(const std::wstring& selector,CONTROLTYPEID type){Ref<IUIAutomationElement> e;e.p=await(selector,type);RECT r{};ok(e->get_CurrentBoundingRectangle(&r));RECT area{};need(GetWindowRect(hwnd,&area)&&r.right>r.left&&r.bottom>r.top&&r.left>=area.left&&r.top>=area.top&&r.right<=area.right&&r.bottom<=area.bottom);}
static void screenshot(const std::wstring& path,unsigned width,unsigned height){
 identity();need((width==1366&&height==768)||(width==1440&&height==900));RECT screen{};need(SystemParametersInfoW(SPI_GETWORKAREA,0,&screen,0)&&screen.right-screen.left>=(LONG)width&&screen.bottom-screen.top>=(LONG)height);
 need(SetWindowPos(hwnd,nullptr,screen.left,screen.top,width,height,SWP_NOZORDER|SWP_SHOWWINDOW));need(SetForegroundWindow(hwnd));Sleep(250);identity();need(GetForegroundWindow()==hwnd);
 visible(L"我的事项",UIA_TextControlTypeId);visible(L"材料与来源",UIA_ButtonControlTypeId);visible(L"重开资料准备",UIA_ButtonControlTypeId);
 {Ref<IUIAutomationElement> secret;secret.p=find(L"密码",UIA_EditControlTypeId);need(!secret.p);}
 RECT r{};need(GetWindowRect(hwnd,&r)&&r.right-r.left==(LONG)width&&r.bottom-r.top==(LONG)height);
 HDC dc=GetWindowDC(hwnd),copy=CreateCompatibleDC(dc);need(dc&&copy);HBITMAP bitmap=CreateCompatibleBitmap(dc,width,height);need(bitmap);HGDIOBJ old=SelectObject(copy,bitmap);need(old&&BitBlt(copy,0,0,width,height,dc,0,0,SRCCOPY|CAPTUREBLT));
 std::set<COLORREF> samples;for(unsigned y=80;y<height;y+=19)for(unsigned x=0;x<width;x+=19){COLORREF c=GetPixel(copy,x,y);need(c!=CLR_INVALID);samples.insert(c);}need(samples.size()>32); // reject blank/unrendered capture
 Ref<IWICImagingFactory> factory;ok(CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_IWICImagingFactory,(void**)factory.put()));Ref<IWICBitmap> image;ok(factory->CreateBitmapFromHBITMAP(bitmap,nullptr,WICBitmapIgnoreAlpha,image.put()));
 IStream* stream=nullptr;ok(CreateStreamOnHGlobal(nullptr,TRUE,&stream));Ref<IWICBitmapEncoder> encoder;ok(factory->CreateEncoder(GUID_ContainerFormatPng,nullptr,encoder.put()));ok(encoder->Initialize(stream,WICBitmapEncoderNoCache));Ref<IWICBitmapFrameEncode> frame;ok(encoder->CreateNewFrame(frame.put(),nullptr));ok(frame->Initialize(nullptr));ok(frame->SetSize(width,height));WICPixelFormatGUID format=GUID_WICPixelFormat24bppBGR;ok(frame->SetPixelFormat(&format));ok(frame->WriteSource(image.p,nullptr));ok(frame->Commit());ok(encoder->Commit());
 HGLOBAL memory=nullptr;ok(GetHGlobalFromStream(stream,&memory));STATSTG stat{};ok(stream->Stat(&stat,STATFLAG_NONAME));need(stat.cbSize.HighPart==0&&stat.cbSize.LowPart<16*1024*1024);void* bytes=GlobalLock(memory);need(bytes);HANDLE f=CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);need(f!=INVALID_HANDLE_VALUE);DWORD used=0;need(WriteFile(f,bytes,stat.cbSize.LowPart,&used,nullptr)&&used==stat.cbSize.LowPart&&FlushFileBuffers(f));need(CloseHandle(f));GlobalUnlock(memory);stream->Release();
 SelectObject(copy,old);need(DeleteObject(bitmap)&&DeleteDC(copy)&&ReleaseDC(hwnd,dc));
}
static void stop(){identity();need(PostMessageW(hwnd,WM_CLOSE,0,0));while(WaitForSingleObject(process,0)!=WAIT_OBJECT_0){guard();need(!pipeUnknown);Sleep(50);}need(ack&&!pipeUnknown);if(reader.joinable())reader.join();DWORD code=2;need(GetExitCodeProcess(process,&code)&&code==0);while(active()!=0){guard();Sleep(50);}if(automation){automation->Release();automation=nullptr;}closeKnown(hostOutput);closeKnown(process);closeKnown(job);}
static void abortSuspended(){
 // A child not yet assigned to our Job is not killed by closing that Job.
 // Only TRUE CreateProcess and no attempted Resume establish this exact case.
 if(!childCreated||resumeAttempted||suspendedCleanupAttempted)return;
 suspendedCleanupAttempted=true;
 if(GetTickCount64()>=cleanupDeadline)return;
 if(TerminateProcess(process,2)){auto now=GetTickCount64();if(now<cleanupDeadline)WaitForSingleObject(process,DWORD(std::min<ULONGLONG>(5000,cleanupDeadline-now)));}
 // This is abnormal cleanup, never VIEW_RELEASED or a successful UI receipt.
}
int main(){
 try{ok(CoInitializeEx(nullptr,COINIT_MULTITHREADED));PrivateLine initial{readLine(GetStdHandle(STD_INPUT_HANDLE))};auto fields=split(initial.s);need(fields.size()==7&&fields[0]=="OPEN"&&fields[6]=="TRIAL_ONLY");deadline=std::stoull(fields[4]);cleanupDeadline=std::stoull(fields[5]);auto now=GetTickCount64();need(now<deadline&&deadline-now<=180000&&cleanupDeadline>=deadline&&cleanupDeadline-now<=960000);start(wide(fields[1]),(HANDLE)(ULONG_PTR)std::stoull(fields[2]),unsigned(std::stoul(fields[3])));writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tOK");
  while(true){PrivateLine request{readLine(GetStdHandle(STD_INPUT_HANDLE))};auto f=split(request.s);need(!f.empty());guard();
   if(std::set<std::string>{"SET","CLICK","ITEM","SELECT","REFERENCE","WAIT","CAPTURE","CLOSE"}.count(f[0]))phase=f[0];
   if(f[0]=="SET"){need(f.size()==3);auto value=wide(f[2]);set(wide(f[1]),value);}
   else if(f[0]=="CLICK"){need(f.size()==2);click(wide(f[1]),false);}
   else if(f[0]=="ITEM"){need(f.size()==2);click(wide(f[1]),true);}
   else if(f[0]=="SELECT"){need(f.size()==3);select(wide(f[1]),wide(f[2]));}
   else if(f[0]=="SELECT_MATERIAL"){need(f.size()==2);select(L"slot",wide(f[1]),true);}
   else if(f[0]=="REFERENCE"){need(f.size()==2);writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tOK\t"+hex(referenceAt(std::stoul(f[1]))));continue;}
   else if(f[0]=="WAIT"){need(f.size()==3);Ref<IUIAutomationElement> e;e.p=await(wide(f[1]),std::stoi(f[2]));}
   else if(f[0]=="CAPTURE"){need(f.size()==4);screenshot(wide(f[1]),std::stoul(f[2]),std::stoul(f[3]));RECT client{};need(GetClientRect(hwnd,&client));writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tOK\t"+std::to_string(client.right)+"\t"+std::to_string(client.bottom)+"\t"+std::to_string(GetDpiForWindow(hwnd))+"\t"+std::to_string(hostPID)+"\t"+std::to_string(hostBirth));continue;}
   else if(f[0]=="CLOSE"){stop();writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tOK\tCLOSED_ORIGINAL_HOST_AND_UI_JOB_ZERO");CoUninitialize();return 0;}
   else need(false);writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tOK");
  }
 }catch(...){abortSuspended();try{writeLine(GetStdHandle(STD_OUTPUT_HANDLE),"UI1\tUNKNOWN\t"+phase+"\t"+failureCode);}catch(...){}ExitProcess(2);}
}
