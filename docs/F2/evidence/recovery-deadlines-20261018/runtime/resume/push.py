from pathlib import Path
import subprocess,json,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/ttl-template-resume-20261018'
verification=json.loads((r/'delivery-verification.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==verification['delivery_sha']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
argv=['git','push','origin','HEAD:refs/heads/dev/f2-demo-original-page-intake-20261017'];started=time.time()
p=subprocess.run(argv,cwd=root,capture_output=True,text=True)
(r/'push.stdout').write_text(p.stdout);(r/'push.stderr').write_text(p.stderr)
(r/'push-result.json').write_text(json.dumps(dict(argv=argv,exit_code=p.returncode,started=started,elapsed=time.time()-started,delivery_sha=verification['delivery_sha']),indent=2)+'\n')
print(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)))
raise SystemExit(p.returncode)
