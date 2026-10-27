"""Local YAML/policy + Linux PowerShell AST/guard checks, never starts a runner.
Uses already installed PyYAML and an explicit existing PowerShell executable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import yaml

ROOT=Path(__file__).resolve().parents[1]

def policy(document):
    assert set(document['on'])=={'push'}
    assert document['on']['push']['branches']==['dev/f1-foundation']
    assert document['permissions']=={'contents':'read'}
    assert document['concurrency']['cancel-in-progress']=='false'
    assert len(document['jobs'])==1
    job=document['jobs']['server-engineering'];assert job['runs-on']=='windows-2025' and int(job['timeout-minutes'])<=25
    assert job['defaults']['run']['shell']=='pwsh'
    actions=[step for step in job['steps'] if 'uses' in step]
    assert len(actions)==2 and actions[0]['uses']=='actions/checkout@v4'
    assert actions[0]['with']=={'persist-credentials':'false','fetch-depth':'1'}
    assert actions[1]['uses']=='actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065'
    assert actions[1]['with']=={'python-version':'3.12','architecture':'x64'}
    assert job['steps'].index(actions[1]) < next(i for i, step in enumerate(job['steps']) if step.get('run')=='./scripts/windows_ci/Engineering.ps1 -Action Prepare')
    assert job['steps'][-1]['if']=='always()'
    publisher=next(step for step in job['steps'] if step.get('run')=='python scripts/windows_ci/publish_summary.py')
    assert publisher['if']=='always()'
    assert job['steps'].index(publisher)>next(i for i,step in enumerate(job['steps']) if step.get('run')=='./scripts/windows_ci/Engineering.ps1 -Action Test')
    assert job['steps'].index(publisher)<next(i for i,step in enumerate(job['steps']) if step.get('run')=='./scripts/windows_ci/Engineering.ps1 -Action Stop')
    serialized=json.dumps(document)
    assert not any(x in serialized for x in ('secrets.','upload-artifact','actions/cache','larger','workflow_dispatch','pull_request_target'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pwsh',required=True,type=Path);parser.add_argument('--report',required=True,type=Path);args=parser.parse_args()
    workflow=ROOT/'.github/workflows/windows-server-engineering.yml'
    document=yaml.load(workflow.read_text(),Loader=yaml.BaseLoader);policy(document)
    private=ROOT/'.runtime/ci-static';private.mkdir(parents=True,exist_ok=True)
    paths=sorted((ROOT/'scripts/windows').glob('*.ps1'))+sorted(p for p in (ROOT/'scripts/windows_ci').iterdir() if p.suffix in ('.ps1','.psm1'))
    script=private/'parse.ps1'
    script.write_text('$rows=@();foreach($path in '+('@('+','.join("'"+str(p).replace("'","''")+"'" for p in paths)+')')+'){$tokens=$null;$errs=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errs);$rows+=@{name=[IO.Path]::GetFileName($path);errors=@($errs|ForEach-Object{$_.Message})}};@{version=$PSVersionTable.PSVersion.ToString();scripts=$rows}|ConvertTo-Json -Depth 5;if(@($rows|Where-Object{$_.errors.Count -gt 0}).Count -gt 0){exit 1}',encoding='utf-8')
    # OS plumbing only, workspace XDG dirs; no HOME/credential/profile mutation.
    sys.path.insert(0,str(ROOT/'src'));from parkweave.process_env import minimal_environment
    dirs={key:str(private/name) for key,name in [('XDG_CACHE_HOME','cache'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data')]}
    for value in dirs.values():Path(value).mkdir(exist_ok=True)
    env=minimal_environment(os.environ,**dirs)
    parsed=subprocess.run([str(args.pwsh.resolve()),'-NoProfile','-NonInteractive','-File',str(script)],env=env,capture_output=True,text=True,timeout=30)
    assert parsed.returncode==0, 'PowerShell AST failed; private stdout/stderr kept for review'
    ast=json.loads(parsed.stdout);assert all(not item['errors'] for item in ast['scripts'])
    guards=[]
    with tempfile.TemporaryDirectory(prefix='parkweave-ci-guard-') as temporary:
        fixture=Path(temporary)/'uncreated-fixture'
        for name in ('Engineering','ServerFileTest'):
            cmd=[str(args.pwsh.resolve()),'-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/windows_ci'/f'{name}.ps1')]
            if name=='Engineering':cmd+=['-Action','Prepare']
            result=subprocess.run(cmd,cwd=temporary,env=env,capture_output=True,text=True,timeout=30)
            assert result.returncode!=0 and 'NOT_RUN: native' in result.stderr
            guards.append({'script':name+'.ps1','exit_code':result.returncode,'refused_linux':True})
        for name,arguments,expected in [('server_candidate_probe.py',['--fixture-dir',str(fixture)],2),('native_suite.py',['--report',str(fixture/'report.json')],2)]:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/windows_ci'/name),*arguments],cwd=temporary,env=env,capture_output=True,text=True,timeout=15)
            assert result.returncode==expected and 'NOT_RUN: native Server2025' in result.stdout
            guards.append({'script':name,'exit_code':result.returncode,'refused_linux':True})
        assert not fixture.exists()
    report={'status':'PARTIAL_LOCAL_STATIC_ENGINEERING_PASS','environment':'Linux; not Windows native execution','yaml_parser':'PyYAML '+yaml.__version__,
            'workflow_sha256':hashlib.sha256(workflow.read_bytes()).hexdigest(),'workflow_policy':'PASS','powershell':ast,'linux_guards':guards,
            'Actions':'BLOCKED_NOT_RETESTED','workflow_push':'NOT_DONE','runner':'NOT_RUN','Win11':'NOT_RUN','Server_native':'NOT_RUN','real_model_calls':0,'real_budget':0}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'yaml_policy':'PASS','ps_scripts':len(paths),'guards':len(guards),'Server_native':'NOT_RUN'}))

if __name__=='__main__':main()
