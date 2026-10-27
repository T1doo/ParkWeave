"""Optional Linux PowerShell AST/native-guard check. Does not validate Windows execution."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from parkweave.process_env import minimal_environment

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pwsh',required=True,type=Path)
    parser.add_argument('--report',type=Path,default=ROOT/'docs/F1/evidence/eng006-powershell-parse.json');args=parser.parse_args()
    binary=args.pwsh.resolve()
    private=ROOT/'.runtime';private.mkdir(mode=0o700,exist_ok=True)
    spec=importlib.util.spec_from_file_location('parkweave_lifecycle_ast',ROOT/'scripts/windows/lifecycle.py')
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    commands=[]
    with tempfile.TemporaryDirectory() as d,patch.object(driver,'require_windows',lambda:None),patch.object(driver.subprocess,'run',lambda cmd,**kw:commands.append(cmd[-1]) or type('R',(),{'returncode':0})()):
        driver.protect_private_root(Path(d)/'synthetic-new-root')
    for i,code in enumerate(commands):(private/f'acl-parse-{i}.ps1').write_text(code)
    parse_script=private/'parse-powershell.ps1'
    parse_script.write_text('''$rows=@()
$paths=@(Get-ChildItem -LiteralPath './scripts/windows' -Filter '*.ps1')+@(Get-ChildItem -LiteralPath './.runtime' -Filter 'acl-parse-*.ps1')
foreach($path in $paths){
 $tokens=$null; $parseErrors=$null
 $null=[System.Management.Automation.Language.Parser]::ParseFile($path.FullName,[ref]$tokens,[ref]$parseErrors)
 $rows+=@{name=$path.Name;errors=@($parseErrors|ForEach-Object{$_.Message})}
}
@{environment='Linux PowerShell AST only';version=$PSVersionTable.PSVersion.ToString();scripts=$rows;windows_native='NOT_RUN'}|ConvertTo-Json -Depth 6
if(@($rows|Where-Object{$_.errors.Count -gt 0}).Count -gt 0){exit 1}
''')
    env=minimal_environment(os.environ,XDG_CACHE_HOME=str(ROOT/'.cache'),XDG_CONFIG_HOME=str(ROOT/'.cache/psconfig'),XDG_DATA_HOME=str(ROOT/'.cache/psdata'))
    for name in ('psconfig','psdata'):(ROOT/'.cache'/name).mkdir(parents=True,exist_ok=True)
    result=subprocess.run([str(binary),'-NoProfile','-NonInteractive','-File',str(parse_script)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    report=json.loads(result.stdout)
    report['parser_exit_code']=result.returncode
    report['native_guards']={}
    if os.name!='nt':
        for name in ('Doctor','Setup','Start','Status','Stop','Test'):
            guard=subprocess.run([str(binary),'-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/windows'/f'{name}.ps1')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            report['native_guards'][name]={'exit_code':guard.returncode,'refused_linux':'NOT_RUN: requires native Windows' in guard.stderr}
            assert guard.returncode!=0 and report['native_guards'][name]['refused_linux']
    report['source']='https://github.com/PowerShell/PowerShell/releases/tag/v7.6.6'
    report['artifact_sha256']='ddbc4a2d113bbd46d283cfedcbcd117a70caefd7673f41f2b4e0000badf103bc'
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PowerShell AST/parser '+str(result.returncode)+'; native Windows NOT_RUN; Linux guards checked.')
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
