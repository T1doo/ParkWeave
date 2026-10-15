"""Read-only independent raw/export, source manifest, wheel audit. Private output only."""
from pathlib import Path
import collections, hashlib, io, json, re, subprocess, sys, tokenize, zipfile

def digest(b): return hashlib.sha256(b).hexdigest()
def readj(p): return json.loads(Path(p).read_text())
def eligible(p, directory, c):
    rel=p.relative_to(directory)
    return (p.is_file() and p.suffix in c['suffixes']
            and not any(part.endswith('-stage') or part.startswith(tuple(c.get('excluded_part_prefixes',[]))) or part in c['excluded_parts'] for part in rel.parts)
            and '.private.' not in p.name and p.name not in c['excluded_names']
            and not p.name.startswith(tuple(c['excluded_prefixes'])))

def audit(c):
    root=Path(c['root']);index=Path(c['index']);base=index.parent;idx=readj(index)
    errors=[];values=set();pool_reports=[]
    for pool in c['pools']:
        p=Path(pool);items=readj(p)
        assert isinstance(items,list) and all(isinstance(v,str) and v for v in items),str(p)
        values.update(v.encode() for v in items)
        pool_reports.append({'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p.read_bytes()),'values':len(items)})
    entries=idx['entries'];mapped={e['export']:e for e in entries}
    if len(mapped)!=len(entries): errors.append('duplicate export paths')
    expected={}
    for area,d in c['areas'].items():
        if area in c.get('skip_areas',[]):continue
        directory=Path(d)
        for p in directory.rglob('*'):
            if eligible(p,directory,c): expected[str(Path(area)/p.relative_to(directory))]=str(p)
    missing=sorted(expected.keys()-mapped.keys());extra=sorted(mapped.keys()-expected.keys())
    disk={str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()}
    disk_missing=sorted(mapped.keys()-disk);disk_extra=sorted(disk-set(mapped)-{'export-index.json'})
    actual_remaining=[];nonzero=[];replacements=0;semantics=collections.defaultdict(list)
    source_words=set()
    for folder in ['src','tests','scripts']:
        for p in (root/folder).rglob('*'):
            if p.is_file() and p.suffix in {'.py','.js','.html'}:
                if p.suffix=='.py':
                    try:
                        source_words.update(t.string.encode() for t in tokenize.tokenize(io.BytesIO(p.read_bytes()).readline) if t.type==tokenize.NAME and len(t.string)==43)
                    except (tokenize.TokenError,IndentationError): pass
    resolutions=c.get('semantic_resolutions',{})
    known_semantic=collections.Counter();unknown_semantic={}
    for rel,e in mapped.items():
        original=Path(e['original']);target=base/rel
        if rel in expected and str(original)!=expected[rel]:errors.append([rel,'raw path mismatch'])
        if not original.is_file() or not target.is_file():errors.append([rel,'missing raw/export']);continue
        raw=original.read_bytes();actual=target.read_bytes();wanted=raw;n=0
        for value in sorted(values):
            n+=wanted.count(value);wanted=wanted.replace(value,b'[REDACTED_SYNTHETIC_FIXTURE_SESSION]')
        replacements+=n
        checks={'raw_sha256':digest(raw),'export_sha256':digest(actual),'raw_bytes':len(raw),'export_bytes':len(actual),'redaction_occurrences':n}
        if checks!={k:e[k] for k in checks}:errors.append([rel,'index hash/size/redaction mismatch'])
        if wanted!=actual:errors.append([rel,'non-exact export mutation'])
        if any(v in actual for v in values):actual_remaining.append(rel)
        if '.private.' in rel:errors.append([rel,'private file exported'])
        if target.suffix=='.exit':
            try:
                code=int(actual.strip())
                if code:nonzero.append({'export':rel,'exit':code})
            except ValueError:errors.append([rel,'noninteger exit'])
        for m in re.finditer(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])',actual):
            token=m.group();h=digest(token);context=actual[max(0,m.start()-65):min(len(actual),m.end()+65)].replace(token,b'[43_CANDIDATE]').decode('utf8','replace')
            semantics[h].append({'export':rel,'context_masked':context})
            if token in source_words:known_semantic[h]+=1
            elif h in resolutions:known_semantic[h]+=1
            else:unknown_semantic.setdefault(h,{'occurrences':0,'examples':[]})['occurrences']+=1;unknown_semantic[h]['examples']=semantics[h][:3]
    if idx.get('exports')!=len(entries):errors.append('index export count mismatch')
    if idx.get('session_values')!=len(values):errors.append('index session value count mismatch')
    if idx.get('literal_replacements')!=replacements:errors.append('index replacement count mismatch')
    source=idx['source_sha']
    resolved=subprocess.check_output(['git','rev-parse',source],cwd=root,text=True).strip()
    if resolved!=source:errors.append('index source is not full SHA')
    source_files={}
    for rel in subprocess.check_output(['git','ls-tree','-r','--name-only',source,'--','src','tests','scripts','pyproject.toml'],cwd=root,text=True).splitlines():
        source_files[rel]=digest(subprocess.check_output(['git','show',f'{source}:{rel}'],cwd=root))
    manifests=[]
    for pair in c.get('manifest_pairs',[]):
        before=readj(pair[0]);after=readj(pair[1]);same=before==after
        exact=before==source_files
        manifests.append({'before':pair[0],'after':pair[1],'equal':same,'source_commit_exact':exact,'manifest_files':len(before),'source_files':len(source_files)})
        if not same:errors.append(['source manifest drift',pair])
        if not exact:errors.append(['source manifest differs frozen commit',pair])
    wheel_reports=[]
    for name in c.get('wheels',[]):
        p=Path(name)
        with zipfile.ZipFile(p) as z:
            actual={n:digest(z.read(n)) for n in z.namelist() if n.startswith('parkweave/') and not n.endswith('/')}
        expected_pkg={rel[4:]:h for rel,h in source_files.items() if rel.startswith('src/parkweave/')}
        report={'path':str(p),'sha256':digest(p.read_bytes()),'source_package_files':len(expected_pkg),'wheel_package_files':len(actual),'missing':sorted(expected_pkg.keys()-actual.keys()),'extra':sorted(actual.keys()-expected_pkg.keys()),'changed':sorted(k for k in expected_pkg.keys()&actual.keys() if expected_pkg[k]!=actual[k])}
        wheel_reports.append(report)
        if report['missing'] or report['extra'] or report['changed']:errors.append(['wheel mismatch',name])
    completeness={'expected':len(expected),'actual':len(mapped),'missing':missing,'extra':extra,'disk_missing':disk_missing,'disk_extra':disk_extra}
    status='PASS' if not (errors or missing or extra or disk_missing or disk_extra or actual_remaining or unknown_semantic) else 'FAIL'
    return {'status':status,'source_sha':source,'index':str(index),'index_sha256':digest(index.read_bytes()),'exports':len(entries),'areas':dict(collections.Counter(rel.split('/')[0] for rel in mapped)),'errors':errors,'raw_candidate_completeness':completeness,'private_pool_metadata':pool_reports,'session_values':len(values),'actual_session_occurrences_remaining':actual_remaining,'literal_replacements':replacements,'semantic_43_occurrences':sum(map(len,semantics.values())),'semantic_known_source_symbols_or_reviewed':dict(known_semantic),'unknown_semantic_candidates':unknown_semantic,'semantic_resolutions':resolutions,'nonzero_exit_files_preserved':nonzero,'manifest_checks':manifests,'wheels':wheel_reports,'raw_files_modified':False,'archive_files_modified':False,'scope':'Independent integrity audit; execution windows retain their own status. No raw/export/source mutation.'}

if __name__=='__main__':
    config=readj(sys.argv[1]);report=audit(config);out=Path(config['output']);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','source_sha','exports','literal_replacements']}))
    sys.exit(0 if report['status']=='PASS' else 1)
