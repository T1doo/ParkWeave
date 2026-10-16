"""Independently implement finite task-evidence inventory and clone pruning."""
from pathlib import Path
import os
ROOT=Path('/workspace/ParkWeave')
RAW_DIRS=['plan-reapproval-'+n for n in ('root','oracle','backend','independent','review','final')]
EXTENSIONS={'.log','.xml','.json','.jsonl','.txt','.exit','.py','.js','.md','.patch','.diff','.html'}
EXCLUDED_NAMES={'archive-index.json','archive-audit.json','archive-independent-audit.json','delivery-draft.md','delivery-report-template.md','critical-path-draft.md','archive-readme-draft.md'}
EXCLUDED_PARTS={'__pycache__','.pytest_cache','pytest-cache','node_modules','.git','.venv','venv','xdg-cache','tmp','temp','data','pgdata','postgres','screenshots'}
FILES={tuple(('src/parkweave/'+n).split('/')) for n in ('api.py','case_resource_delivery.py','case_resources.py','resource_plan_binding.py','service_plan_approval.py','web.html')}
FILES|={('tests',n) for n in ('test_plan_reapproval_client.py','test_plan_source_reapproval.py','test_plan_source_reapproval_candidate.py','test_plan_source_reapproval_chromium.py','test_plan_source_reapproval_independent.py','plan_reapproval_client_probes.js','plan_source_reapproval_real_html.js')}

BROWSER_FIXES={'test_case_resource_delivery_browser.py','test_new_enterprise_local_chain_browser.py'}
FILES.update({('tests',name) for name in BROWSER_FIXES})

def clone(name):return name in ('project','candidate') or name.startswith(('candidate-','private-tree','private-worktree','source-wip','worktree'))

def allowed(parts,directory=False):
    dirs=parts if directory else parts[:-1]
    if any(n in EXCLUDED_PARTS or n.startswith(('parkweave-pg','pgsql_tmp')) or 'screenshot' in n for n in parts):return False
    if any(n.startswith('pytest-') for n in dirs) and 'unredirected-legacy-artifacts' not in parts:return False
    if not directory:
        name=parts[-1]
        if name in EXCLUDED_NAMES or '.private.' in name or name.endswith('private.json') or Path(name).suffix not in EXTENSIONS:return False
    for i,name in enumerate(dirs):
        if not clone(name):continue
        tail=tuple(parts[i+1:])
        if not tail and directory:continue
        if directory and tail==('.runtime',):continue
        if len(tail)>=2 and tail[0]=='.runtime' and tail[1] in RAW_DIRS:continue
        if directory and any(f[:len(tail)]==tail for f in FILES):continue
        if not directory and tail in FILES:continue
        if not directory and name=='candidate' and i>0 and dirs[i-1]=='browser-repair' and len(tail)==1 and tail[0] in BROWSER_FIXES:continue
        return False
    return True

def inventory():
    selected=[]
    for name in RAW_DIRS:
        root=ROOT/'.runtime'/name
        if not root.exists() or root.is_symlink():continue
        for here,dirs,names in os.walk(root,followlinks=False):
            here=Path(here)
            dirs[:]=[n for n in dirs if not (here/n).is_symlink() and allowed((here/n).relative_to(root).parts,True)]
            for name in names:
                path=here/name
                if path.is_symlink() or not path.is_file():continue
                if allowed(path.relative_to(root).parts):selected.append(str(path.relative_to(ROOT)))
    return sorted(selected)

def selftest():
    checks={
      ('browser-repair','candidate','test_case_resource_delivery_browser.py'):True,
      ('browser-repair','candidate','test_new_enterprise_local_chain_browser.py'):True,
      ('browser-repair','candidate','test_other.py'):False,
      ('browser-repair','baseline','project','tests','test_case_resource_delivery_browser.py'):True,
      ('browser-repair','fixed','project','tests','test_new_enterprise_local_chain_browser.py'):True,
      ('browser-repair','fixed','project','tests','test_unrelated.py'):False,
      ('attempt1','project','docs','old.md'):False,
      ('attempt1','project','src','parkweave','api.py'):True,
      ('candidate','tests','test_service_plan_approval.py'):False,
      ('candidate-manifest-v1.json',):True,
      ('attempt2','project','.runtime','old-task','a.json'):False,
      ('attempt2','project','.runtime','plan-reapproval-independent','artifacts','a.json'):True,
      ('attempt2','project','.runtime','plan-reapproval-independent','candidate','tests','test_plan_source_reapproval.py'):True,
      ('attempt2','project','.runtime','plan-reapproval-independent','candidate','docs','x.md'):False,
      ('attempt2','project','.runtime','plan-reapproval-independent','pgdata','x.json'):False,
      ('redaction.private.json',):False,
      ('notes','screenshot-result.json'):False,
      ('tests','pytest-cluster','x.json'):False,
      ('unredirected-legacy-artifacts','pytest-cluster','x.json'):True,
    }
    assert all(allowed(p)==want for p,want in checks.items())
    assert allowed(('attempt1','project','src'),True) and not allowed(('attempt1','project','docs'),True)
    return len(checks)+2
