"""Read-only old evidence/ref preservation; no fetch, writes, or permission changes."""
from pathlib import Path
import argparse,hashlib,json,subprocess


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,default=Path('.runtime/plan-reapproval-root/baseline.json'))
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();raw=args.baseline.read_bytes();baseline=json.loads(raw)
    old=baseline['prior_raw_sha256'];refs=baseline['refs']
    assert len(old)==5749 and len(refs)==81,'baseline scope differs from reviewed task startup'
    for path,expected in old.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected,path
    lines=subprocess.check_output(['git','ls-remote','--heads','origin'],text=True,timeout=60).splitlines()
    remote={line.split()[1]:line.split()[0] for line in lines}
    for ref,expected in refs.items():assert remote.get(ref)==expected,ref
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    assert branch and branch!='main','normal development branch required'
    extras=set(remote)-set(refs);assert extras<={'refs/heads/'+branch},'unrelated new remote refs appeared'
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    main=subprocess.check_output(['git','rev-parse','refs/heads/main'],text=True).strip()
    assert main==refs['refs/heads/main']==remote['refs/heads/main'],'main changed'
    subprocess.run(['git','merge-base','--is-ancestor',baseline['source_sha'],head],check=True)
    output=dict(status='PASS',baseline_sha256=hashlib.sha256(raw).hexdigest(),baseline_source_sha=baseline['source_sha'],actual_head=head,branch=branch,
        prior_raw_files=len(old),old_remote_heads=len(refs),main_sha=main,old_remote_heads_unchanged=True,old_raw_unchanged=True,
        additional_remote_heads={ref:remote[ref] for ref in sorted(extras)},baseline_is_ancestor=True,operation='read-only local hashes, git ls-remote and ancestry; no fetch or writes to repository')
    args.out.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))


if __name__=='__main__':main()
