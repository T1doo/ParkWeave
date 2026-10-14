import hashlib,json,pathlib,subprocess,sys,time
root=pathlib.Path.cwd();out=root/'.runtime/preview-namespace-20261014';name=sys.argv[1];modules=sys.argv[2:]
def manifest():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','src','tests','scripts'],text=True).splitlines()
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names if (root/n).is_file()}
before=manifest();(out/(name+'-before.json')).write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
start=time.monotonic()
with (out/(name+'.log')).open('w') as log:
    result=subprocess.run(['/workspace/ParkWeave/.venv/bin/python','-m','pytest',*modules,'-q','--junitxml='+str(out/(name+'.xml'))],stdout=log,stderr=subprocess.STDOUT,env={**__import__('os').environ,'PYTHONPATH':'src'})
after=manifest();(out/(name+'-after.json')).write_text(json.dumps(after,sort_keys=True,indent=2)+'\n');(out/(name+'.exit')).write_text(str(result.returncode)+'\n')
summary=dict(exit=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),file_count=len(before),changed=[n for n in before.keys()|after.keys() if before.get(n)!=after.get(n)],modules=modules)
(out/(name+'-window.json')).write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n');print(json.dumps(summary));print((out/(name+'.log')).read_text()[-5000:]);sys.exit(result.returncode)
