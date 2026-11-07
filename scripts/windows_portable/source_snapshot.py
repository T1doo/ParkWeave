"""Explicit source-byte snapshots for uncommitted Windows candidates; no Git mutation."""
from hashlib import sha256
from pathlib import Path, PurePosixPath
import stat
import zipfile


def load_snapshot(path, expected):
    raw=path.read_bytes()
    if len(expected)!=64 or sha256(raw).hexdigest()!=expected:
        raise ValueError('SOURCE_SNAPSHOT_HASH')
    result={};folded=set();total=0
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name=item.filename;p=PurePosixPath(name)
            if (item.is_dir() or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name
                    or str(p)!=name or not (name=='pyproject.toml' or name.startswith(('src/parkweave/','scripts/')))):
                raise ValueError('SOURCE_SNAPSHOT_PATH')
            if name.casefold() in folded:raise ValueError('SOURCE_SNAPSHOT_DUPLICATE')
            if stat.S_IFMT(item.external_attr>>16) not in (0,stat.S_IFREG):
                raise ValueError('SOURCE_SNAPSHOT_OBJECT')
            total+=item.file_size
            if item.file_size>64*1024*1024 or total>256*1024*1024:raise ValueError('SOURCE_SNAPSHOT_LIMIT')
            folded.add(name.casefold());result[name]=archive.read(item)
    return result


def write_snapshot(root,output):
    """Freeze current allowed source bytes, including new source files, without commit."""
    root=root.resolve();files={};total=0
    candidates=[root/'pyproject.toml']
    for base in ('src/parkweave','scripts'):
        candidates.extend(p for p in (root/base).rglob('*') if p.is_file()
                          and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
    for p in candidates:
        if p.is_symlink() or p.resolve()!=p.absolute():raise ValueError('SOURCE_SNAPSHOT_ALIAS')
        name=p.relative_to(root).as_posix();raw=p.read_bytes();total+=len(raw)
        if len(raw)>64*1024*1024 or total>256*1024*1024:raise ValueError('SOURCE_SNAPSHOT_LIMIT')
        files[name]=raw
    if output.absolute().is_relative_to(root/'src') or output.absolute().is_relative_to(root/'scripts'):
        raise ValueError('SOURCE_SNAPSHOT_OUTPUT_INSIDE_SOURCE')
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name,date_time=(2000,1,1,0,0,0));info.external_attr=0o100644<<16
                info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,raw)
    digest=sha256(output.read_bytes()).hexdigest()
    if load_snapshot(output,digest)!=files:raise ValueError('SOURCE_SNAPSHOT_READBACK')
    return {'source_snapshot_sha256':digest,'files':len(files),'bytes':output.stat().st_size,
            'source_commit':None,'scope':'LOCAL_SOURCE_BYTES_NOT_PRODUCT_ACCEPTANCE'}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(write_snapshot(args.root,args.output),indent=2))
