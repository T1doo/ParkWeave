"""Compile the actual host input functions; controlled controls, no Windows run."""
import json
from pathlib import Path
import shutil
import subprocess
import re
import pytest
from scripts.windows_portable import desktop_bridge,native_web_login


@pytest.fixture(scope='module')
def startup_binary(tmp_path_factory):
    compiler=shutil.which('g++')
    if compiler is None:pytest.skip('portable C++ compiler unavailable; not Windows evidence')
    host=Path('scripts/windows_desktop/host.cpp').read_text()
    inputs=host[host.index('enum class DesktopInputProblem'):host.index('static void launch(')]
    actual_json=host[host.index('static std::string json('):host.index('static void clearPasswords(')]
    accounts=next(x for x in host.splitlines() if x.startswith('static const wchar_t* accounts[]'))
    sample_accounts=next(x for x in host.splitlines() if x.startswith('static const wchar_t* sampleAccounts[]'))
    sample_selected=next(x for x in host.splitlines() if x.startswith('static bool sampleSelected()'))
    units=int(re.search(r'SendMessageW\(pass\[i\],EM_SETLIMITTEXT,(\d+),0\)',host).group(1))
    root=tmp_path_factory.mktemp('host-startup-inputs');source=root/'inputs.cpp'
    source.write_text(r'''
#include <string>
#include <map>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
using HWND=int;
HWND instanceEdit=1,portDb=2,portApi=3,pass[6]={10,11,12,13,14,15},window=0;
std::map<int,std::wstring> values;
int passwordReads=0;size_t wiped=0;bool sampleMode=false;
void* watched=nullptr;size_t watchedSize=0;bool messageWiped=false;
std::wstring text(HWND h){if(h>=10)++passwordReads;auto result=values.at(h);if(h>=10&&result.size()>EDIT_UNITS)result.resize(EDIT_UNITS);return result;}
void* SecureZeroMemory(void* data,size_t size){wiped+=size;std::memset(data,0,size);if(data==watched&&size==watchedSize){messageWiped=true;for(size_t i=0;i<size;i++)if(((char*)data)[i])messageWiped=false;}return data;}
int GetDlgItem(int,int id){return id;}
constexpr int BM_GETCHECK=0,BST_CHECKED=1;
int SendMessageW(int id,int,int,int){return id==4&&sampleMode?BST_CHECKED:0;}
'''.replace('EDIT_UNITS',str(units))+accounts+'\n'+sample_accounts+'\n'+sample_selected+'\n'+actual_json+'\n'+inputs+r'''
int main(int argc,char** argv){
 int mode=std::atoi(argv[1]);values[1]=L"E:\\Software\\public-synthetic-instance";values[2]=L"55432";values[3]=L"58761";
 for(int i=0;i<6;i++)values[10+i]=L"SYNTHETIC_PASSWORD_"+std::to_wstring(i);
 std::wstring action=L"new";
 if(mode==13||mode==14)sampleMode=true;
 if(mode==14)action=L"reopen";
 if(mode==1)values[3]=values[2];
 if(mode==2)values[12]=values[10];
 if(mode==3)values[10]=L"short";
 if(mode==4){values[10].clear();for(int i=0;i<6;i++){values[10]+=wchar_t(0xd83d);values[10]+=wchar_t(0xde00);}}
 if(mode==5||mode==6){values[10].clear();for(int i=0;i<(mode==5?12:256);i++){values[10]+=wchar_t(0xd83d);values[10]+=wchar_t(0xde00);}}
 if(mode==7){values[10]=std::wstring(11,L'a');values[10]+=wchar_t(0xd83d);}
 if(mode==8)values[2]=L"9999999999999999999999999999";
 if(mode==9){action=L"reopen";values[2]=L"garbage";values[3]=L"garbage";for(int i=0;i<6;i++)values[10+i]=L"bad";}
 if(mode==10)values[1]=L"";
 if(mode==11)values[2]=L"00000000000000000000055432";
 if(mode==12){try{DesktopMessage message{payload(action)};watched=message.bytes.data();watchedSize=message.bytes.size();throw std::runtime_error("BOOTSTRAP_BEFORE_INNER_TRY");}catch(...){return messageWiped?0:95;}}
 try{std::string result=payload(action);if(action==L"new"&&!wiped)return 90;if(action==L"reopen"&&passwordReads)return 91;std::puts(result.c_str());return 0;}
 catch(const DesktopInputError& error){
  if(!inputHint(error.problem)||!*inputHint(error.problem))return 92;
  if((mode==1||mode==8||mode==10)&&passwordReads)return 93;
  if((mode==2||mode==3||mode==4||mode==7)&&!wiped)return 94;
  return 20+int(error.problem);
 }catch(...){return 99;}
}
''')
    binary=root/'startup-inputs'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra',str(source),'-o',str(binary)],capture_output=True,text=True,check=True,timeout=30)
    return binary


@pytest.mark.parametrize('mode,expected',[(1,21),(2,23),(3,22),(4,22),(7,22),(8,21),(10,20)])
def test_host_refuses_user_errors_before_native_launch_with_specific_hint_and_secret_copy_wipe(startup_binary,mode,expected):
    result=subprocess.run([str(startup_binary),str(mode)],capture_output=True,text=True,timeout=5)
    assert result.returncode==expected and result.stdout==''


@pytest.mark.parametrize('mode,characters',[(0,None),(5,12),(6,256),(9,None),(11,None)])
def test_actual_host_payload_and_python_boundary_agree_including_utf16_and_reopen(startup_binary,mode,characters):
    result=subprocess.run([str(startup_binary),str(mode)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0
    import io
    row=desktop_bridge.request(io.BytesIO(result.stdout.encode()))
    if mode==9:
        assert row['action']=='reopen' and row['passwords']=={} and row['database_port']==row['api_port']==0
    else:
        assert row['database_port']==55432 and row['api_port']==58761
        # Constructor only checks original password inputs; no tokens/DPAPI/native enrollment.
        assert type(native_web_login.NativeLoginEnrollment(row['passwords'])) is native_web_login.NativeLoginEnrollment
        if characters is not None:assert len(row['passwords']['fixture-a'])==characters


def test_form_validation_is_before_runtime_and_specific_error_handler_does_not_start_recovery():
    host=Path('scripts/windows_desktop/host.cpp').read_text()
    launch=host.split('static void launch(',1)[1].split('static void event(',1)[0]
    assert launch.index('payload(action)')<launch.index('verifyBootstrap()')<launch.index('runtime()')<launch.index('CreateProcessW(')
    assert 'DesktopMessage message{payload(action)};auto& data=message.bytes;' in launch
    assert int(re.search(r'SendMessageW\(pass\[i\],EM_SETLIMITTEXT,(\d+),0\)',host).group(1))>=512
    handler=host.split('catch(const DesktopInputError& error)',1)[1].split('catch(...)',1)[0]
    assert 'clearPasswords();status(inputHint(error.problem));return 0;' in handler
    assert not any(x in handler for x in ('launch(', 'runtime(', 'stop(', 'signalBackend(', 'CreateProcess', 'READY'))


def test_serialized_message_is_wiped_on_bootstrap_exception_before_inner_launch_try(startup_binary):
    result=subprocess.run([str(startup_binary),'12'],capture_output=True,text=True,timeout=5)
    assert result.returncode==0 and result.stdout==''


@pytest.mark.parametrize('mode',[13,14])
def test_actual_desktop_explicit_sample_serializes_four_accounts_and_reopen_without_passwords(startup_binary,mode):
    import io
    from scripts.windows_portable.local_preparation_identity import PreparationProfile
    result=subprocess.run([str(startup_binary),str(mode)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    row=desktop_bridge.request(io.BytesIO(result.stdout.encode()))
    assert row['sample_collaboration'] is True
    if mode==13:
        value=native_web_login.NativeLoginEnrollment(row['passwords'],profile=PreparationProfile.SAMPLE)
        assert value.profile is PreparationProfile.SAMPLE and len(row['passwords'])==4
    else:assert row['passwords']=={} and row['action']=='reopen'


def test_web_login_can_enter_the_hosts_full_256_codepoint_non_bmp_password():
    # HTML maxlength uses UTF-16 units; native validation uses codepoints.
    page=Path('src/parkweave/local_preparation_web.html').read_text()
    password=re.search(r'<input[^>]+id="password"[^>]+>',page).group(0)
    assert int(re.search(r'maxlength="(\d+)"',password).group(1))==512
    assert len(native_web_login.password_bytes('😀'*256))==1024
    with pytest.raises(Exception):native_web_login.password_bytes('😀'*257)
