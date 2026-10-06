"""Controlled PowerShell metadata doubles only; no Get/Set real Windows ACL."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FutureTimeout
import pytest
from test_lifecycle import lifecycle
from test_windows_ci_preparation import module,ROOT

SID='S-1-5-21-1000'
POISON='SYNTHETIC private path credential never published'


def powershell_fixture(tmp_path,fault,script):
    pwsh=ROOT/'.cache/powershell/bin/pwsh'
    if os.name=='nt' or not pwsh.exists():pytest.skip('portable PowerShell fixture only; actual PS5/ACL validation separate')
    private=tmp_path/'private';private.mkdir(exist_ok=True);(private/'synthetic-sessions.json').write_text('SYNTHETIC')
    fixture=r'''
$script:Fault=__FAULT__
$script:CurrentSid='S-1-5-21-1000'
function Make-Identity([string]$Value,[bool]$Broken=$false) {
 $r=[pscustomobject]@{Value=$Value;Broken=$Broken}
 $r | Add-Member ScriptMethod Translate {param($Type) if($this.Broken){throw 'SYNTHETIC translate failure'};return [pscustomobject]@{Value=$this.Value}}
 return $r
}
function New-Object {param($TypeName) return (Make-Identity $script:CurrentSid ($script:Fault -eq 'owner_read'))}
function Get-Acl {
 param($LiteralPath,$ErrorAction)
 $root=$LiteralPath -eq $env:PARKWEAVE_ACL_ROOT
 if(!$root -and $script:Fault -eq 'read_error'){Write-Error 'SYNTHETIC read failure';return $null}
 $owner=if(!$root -and ($script:Fault -eq 'owner_mismatch' -or ($script:Fault -eq 'config_owner' -and (Split-Path -Leaf $LiteralPath) -eq 'windows-config.json'))){'S-1-5-21-2000'}else{$script:CurrentSid}
 $a=[pscustomobject]@{Owner='SYNTHETIC unresolvable display name';OwnerSid=$owner;AreAccessRulesProtected=($script:Fault -ne 'inheritance');Root=$root}
 $a | Add-Member ScriptMethod GetOwner {
  param($Type)
  if($Type -ne [System.Security.Principal.SecurityIdentifier]){throw 'unexpected owner type'}
  if(!$this.Root -and $script:Fault -eq 'owner_read'){throw 'SYNTHETIC owner read failure'}
  return [pscustomobject]@{Value=$this.OwnerSid}
 }
 $a | Add-Member ScriptMethod GetAccessRules {
  param($Explicit,$Inherited,$Type)
  if(!$Explicit -or !$Inherited -or $Type -ne [System.Security.Principal.SecurityIdentifier]){throw 'unexpected rule query'}
  if(!$this.Root -and $script:Fault -eq 'rule_read'){throw 'SYNTHETIC rules read failure'}
  if($script:Fault -eq 'empty_rules'){return ,@()}
  $values=@([pscustomobject]@{AccessControlType='Allow';IdentityReference=(Make-Identity $script:CurrentSid)})
  if(!$this.Root -and $script:Fault -in @('allow_unknown','stale_sid')){$values+=[pscustomobject]@{AccessControlType='Allow';IdentityReference=(Make-Identity 'S-1-5-21-2000' ($script:Fault -eq 'stale_sid'))}}
  if($script:Fault -eq 'system_admin') {foreach($sid in @('S-1-5-18','S-1-5-32-544')){$values+=[pscustomobject]@{AccessControlType='Allow';IdentityReference=(Make-Identity $sid)}}}
  return ,$values
 }
 $a | Add-Member ScriptProperty Access {return $this.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])}
 return $a
}
'''.replace('__FAULT__',"'"+fault+"'")
    identity='[System.Security.Principal.WindowsIdentity]::GetCurrent().User'
    assert script.count(identity)==1
    code=fixture+'\n'+script.replace(identity,"[pscustomobject]@{Value=$script:CurrentSid}")
    path=tmp_path/'fixture.ps1';path.write_text(code,encoding='utf-8')
    from parkweave.process_env import minimal_environment
    env=minimal_environment(os.environ,PARKWEAVE_ACL_ROOT=str(private),XDG_CACHE_HOME=str(tmp_path/'cache'),XDG_CONFIG_HOME=str(tmp_path/'config'),XDG_DATA_HOME=str(tmp_path/'data'))
    return subprocess.run([str(pwsh),'-NoProfile','-NonInteractive','-File',str(path)],env=env,capture_output=True,text=True,timeout=10)


@pytest.mark.parametrize('fault,expected',[('valid',0),('system_admin',0),('empty_rules',0),('owner_mismatch',2),('allow_unknown',3),('inheritance',4),('read_error',5),('owner_read',5),('rule_read',5),('stale_sid',3)])
def test_readonly_acl_script_direct_SIDs_and_fail_closed(tmp_path,fault,expected):
    result=powershell_fixture(tmp_path,fault,lifecycle.acl_check_command())
    assert result.returncode==expected and result.stderr==''
    assert result.stdout==('' if expected==0 else ('ROOT\n' if fault=='inheritance' else 'SESSIONS\n'))
    source=lifecycle.acl_check_command()
    assert 'Set-Acl' not in source and 'SetOwner' not in source and 'SetAccessRule' not in source


@pytest.mark.parametrize('code,reason',[(2,'ACL_OWNER_MISMATCH'),(3,'ACL_ALLOW_REFUSED'),(4,'ACL_INHERITANCE_REFUSED'),(5,'ACL_INSPECTION_FAILED'),(1,'ACL_INSPECTION_FAILED'),(-1,'ACL_INSPECTION_FAILED')])
def test_acl_return_branches_use_existing_bounded_protocol_without_private_output(tmp_path,monkeypatch,code,reason):
    import lifecycle_diagnostics as diagnostic
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)
    commands=[]
    def run(command,**kwargs):commands.append(command);return type('R',(),{'returncode':code,'stdout':POISON,'stderr':POISON})()
    monkeypatch.setattr(lifecycle.subprocess,'run',run)
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.native_acl_check(tmp_path)
    assert diagnostic.failure(error.value)['boundary_reason']==reason and POISON not in diagnostic.command('setup',error.value)
    assert len(commands)==1 and 'Set-Acl' not in commands[0][-1]


def test_setup_checks_created_config_and_sessions_without_acl_repair(tmp_path,monkeypatch,capsys):
    from parkweave.store import Store
    runtime=tmp_path/'.runtime';runtime.mkdir();sessions=runtime/'synthetic-sessions.json';sessions.write_text('{"fixture-a":"SYNTHETIC"}')
    original=sessions.read_bytes();python=tmp_path/'.venv-windows/Scripts/python.exe';python.parent.mkdir(parents=True);python.write_text('SYNTHETIC')
    monkeypatch.setattr(lifecycle,'REPO',tmp_path);monkeypatch.setattr(lifecycle,'RUNTIME',runtime);monkeypatch.setattr(lifecycle,'CONFIG',runtime/'windows-config.json');monkeypatch.setattr(lifecycle.sys,'executable',str(python))
    monkeypatch.setattr(lifecycle,'check_python',lambda *args:None);monkeypatch.setattr(lifecycle,'check_dsn_scope',lambda *args,**kwargs:None);monkeypatch.setattr(lifecycle,'needed_environment',lambda name:'SYNTHETIC')
    (tmp_path/'src/parkweave').mkdir(parents=True);(tmp_path/'src/parkweave/roles.sql').write_text('-- SYNTHETIC fixture')
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):pass
    monkeypatch.setattr(Store,'migrate',lambda *args:None);monkeypatch.setattr(Store,'connect',lambda *args:Connection())
    # Native owner creation is separately tested; this fixture checks the final ACL boundary.
    monkeypatch.setattr(lifecycle,'create_synthetic_config_file',lambda path:Path(path).open('x',encoding='utf-8'))
    calls=[]
    monkeypatch.setattr(lifecycle,'protect_private_root',lambda root:calls.append('precheck'))
    def final_check(root):
        assert lifecycle.CONFIG.exists() and sessions.read_bytes()==original
        calls.append('final_check')
        raise lifecycle.BoundaryError(POISON,'ACL_OWNER_MISMATCH')
    monkeypatch.setattr(lifecycle,'native_acl_check',final_check)
    with pytest.raises(lifecycle.BoundaryError):lifecycle.setup()
    assert calls==['precheck','final_check'] and 'Setup candidate complete' not in capsys.readouterr().out
    assert sessions.read_bytes()==original and json.loads(lifecycle.CONFIG.read_text())['project']=='ParkWeave'


def test_acl_reparse_root_refused_without_launch(tmp_path,monkeypatch):
    if os.name=='nt':pytest.skip('portable symlink oracle; Windows junction separate')
    target=tmp_path/'owned';target.mkdir();link=tmp_path/'link';link.symlink_to(target,target_is_directory=True)
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)
    monkeypatch.setattr(lifecycle.subprocess,'run',lambda *args,**kwargs:pytest.fail('must not launch'))
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.native_acl_check(link)
    assert error.value.parkweave_lifecycle_reason=='REPARSE_REFUSED'


@pytest.mark.parametrize('flush,visible',[(False,False),(True,True)])
def test_real_marker_before_buffer_flush_race_is_ordering_not_indefinite_wait(tmp_path,flush,visible):
    marker=tmp_path/'ready';release=tmp_path/'release';log=tmp_path/'stdout';code='import pathlib,time;print("SYNTHETIC child",flush='+str(flush)+');pathlib.Path('+repr(str(marker))+').write_text("ready");release=pathlib.Path('+repr(str(release))+');\nwhile not release.exists():time.sleep(.005)'
    from parkweave.process_env import minimal_environment
    with log.open('wb') as stream:
        process=subprocess.Popen([sys.executable,'-c',code],env=minimal_environment(os.environ),stdout=stream,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+3
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.005)
            assert marker.exists() and ('SYNTHETIC child' in log.read_text())==visible
            release.write_text("release");process.wait(timeout=2)
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=2)


def test_future_timeout_does_not_bound_executor_exit_controlled_release():
    release=threading.Event();entered=threading.Event();timer=threading.Timer(.3,release.set);start=time.monotonic();observed=False
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(lambda:entered.set() or release.wait(5));assert entered.wait(1)
            try:future.result(timeout=.02)
            except FutureTimeout:observed=True;timer.start()
        elapsed=time.monotonic()-start
        assert observed and elapsed>=.2 and future.done() and release.is_set()
    finally:
        release.set()
        if timer.ident is not None:timer.join(timeout=1)


# Exact readonly checker from d76354d; metadata/identity are synthetic doubles.
LEGACY_CHECKER="$p=$env:PARKWEAVE_ACL_ROOT; $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; $paths=@($p); foreach($name in @('files','synthetic-sessions.json','windows-config.json','windows-processes.json','windows-services.log')) { $q=Join-Path $p $name; if(Test-Path -LiteralPath $q){$paths+=$q} }; foreach($q in $paths){$acl=Get-Acl -LiteralPath $q; $owner=New-Object System.Security.Principal.NTAccount($acl.Owner); if($q -eq $p -and -not $acl.AreAccessRulesProtected){exit 4}; if($owner.Translate([System.Security.Principal.SecurityIdentifier]).Value -ne $sid.Value){exit 2}; foreach($rule in $acl.Access){if($rule.AccessControlType -eq 'Allow'){ $id=$rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value; if($id -notin @($sid.Value,'S-1-5-18','S-1-5-32-544')){exit 3} } } }; exit 0"

@pytest.mark.parametrize("fault,closed",[("read_error",5),("owner_read",5),("stale_sid",3)])
def test_legacy_metadata_error_can_report_success_while_new_checker_refuses(tmp_path,fault,closed):
    old=powershell_fixture(tmp_path,fault,LEGACY_CHECKER)
    new=powershell_fixture(tmp_path,fault,lifecycle.acl_check_command())
    assert old.returncode==0 and new.returncode==closed
    assert new.stdout=='SESSIONS\n' and new.stderr==''
