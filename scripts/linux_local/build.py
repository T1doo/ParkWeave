"""Offline candidate from one full Git commit + exact official locked wheels.

No dependency fetch, database, setup credentials, runtime execution or release.
"""
import argparse
from hashlib import sha256
import io,json,subprocess,tarfile,gzip
from pathlib import Path


def build(root,commit,wheels,output,*,branch='dev/local-product-runtime-20261028'):
    assert subprocess.check_output(['git','rev-parse',commit+'^{commit}'],cwd=root,text=True).strip()==commit and len(commit)==40
    def source(path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root)
    lock=json.loads(source('scripts/linux_local/wheel-lock.json'))
    payload={'install.py':source('scripts/linux_local/manage.py'),
        'requirements.lock':source('scripts/linux_local/requirements.lock'),
        'wheel-lock.json':source('scripts/linux_local/wheel-lock.json'),
        'START_HERE.txt':source('docs/demo/LinuxOfflineCandidate.txt')}
    bundle=output.parent/(output.name+'.source.bundle')
    assert not bundle.exists() and not output.exists()
    # Bundle the named branch at the exact reviewed commit, no working-tree or
    # runtime/private files. Explicit --branch also makes offline cloning stable.
    assert type(branch) is str and branch.startswith('dev/')
    subprocess.run(['git','check-ref-format','--branch',branch],cwd=root,check=True,stdout=subprocess.DEVNULL)
    ref='refs/heads/'+branch
    assert subprocess.check_output(['git','rev-parse',ref],cwd=root,text=True).strip()==commit
    subprocess.run(['git','bundle','create',str(bundle),ref],cwd=root,check=True)
    payload['source.bundle']=bundle.read_bytes()
    for row in lock['wheels']:
        path=wheels/row['file'];raw=path.read_bytes()
        assert len(raw)==row['bytes'] and sha256(raw).hexdigest()==row['sha256']
        payload['wheelhouse/'+row['file']]=raw
    manifest=dict(schema='parkweave-linux-offline-candidate/1',source_commit=commit,
        branch=branch,scope='LINUX_SYNTHETIC_ONLY',usable_product=False,
        format='SOURCE_AND_LOCKED_WHEELS_WITH_USER_INSTALLER',external_prerequisites=['Linux x86_64 glibc>=2.34','Python3.12 with venv/ensurepip','Git','non-root user','short writable private user destination'],
        native_windows_executed=False,browser_pixels_verified=False,dependencies='OFFICIAL_PYPI_HASHED_WHEELS_OFFLINE_INSTALL_ONLY',
        files={n:dict(bytes=len(b),sha256=sha256(b).hexdigest()) for n,b in sorted(payload.items())})
    payload['candidate.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    # Deterministic timestamps/UIDs and gzip header, no absolute build path.
    with output.open('xb') as stream:
        with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name,raw in sorted(payload.items()):
                    item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o600;item.mtime=0
                    archive.addfile(item,io.BytesIO(raw))
    return dict(source_commit=commit,file=output.name,bytes=output.stat().st_size,
        sha256=sha256(output.read_bytes()).hexdigest(),manifest_sha256=sha256(payload['candidate.json']).hexdigest(),
        wheels=len(lock['wheels']),wheel_bytes=sum(row['bytes'] for row in lock['wheels']),
        kind='LINUX_RESTRICTED_CANDIDATE_NOT_WINDOWS_INSTALLER',usable_product=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commit',required=True)
    p.add_argument('--branch',default='dev/local-product-runtime-20261028')
    p.add_argument('--wheels',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(Path(__file__).resolve().parents[2],a.commit,a.wheels,a.output,branch=a.branch),indent=2))

if __name__=='__main__':main()
