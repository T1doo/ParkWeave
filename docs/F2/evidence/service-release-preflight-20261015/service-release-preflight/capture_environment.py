import subprocess,json,datetime,os
from pathlib import Path
out=Path('.runtime/service-release-preflight/environment.json')
def run(args):
 r=subprocess.run(args,text=True,capture_output=True);return dict(argv=args,code=r.returncode,stdout=r.stdout,stderr=r.stderr)
x=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cwd=os.getcwd(),branch=run(['git','branch','--show-current']),head=run(['git','rev-parse','HEAD']),worktrees=run(['git','worktree','list','--porcelain']),status=run(['git','status','--short']),remote=run(['git','ls-remote','origin','refs/heads/main','refs/heads/dev/f3-shared-source-cases-20261015','refs/heads/dev/f2-worklist-entry-isolation-20261013']),main_ancestor=run(['git','merge-base','--is-ancestor','31e7acb7e53bb1ab6465b9daae59de28757f7583','HEAD']),source_ancestor=run(['git','merge-base','--is-ancestor','731529bc409041f255742e11756ebc4084bb9319','HEAD']),python=run(['.venv/bin/python','--version']),node=run(['node','--version']),network='default network; git ls-remote successful only if exit0; no deployment/real model calls',single_integrator='/root; isolated allowed agent paths only; no old task resumed')
out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(out)
