"""Finalize independently derived coverage, manuscript scope and archive gate."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,subprocess
from audit_typed_archive import ROOT,OUT,ARCHIVE,SHA,load,record,frozen_sources,expected_windows,private_sets

report=load(OUT/'archive-independent-pairs-checkpoint.json')
assert report['source_sha']==SHA and report['status']=='ARCHIVE_PAIR_CHECKS_PASS_FINAL_GATE_REVIEW_PENDING'
assert report['checks']=={'files':135,'export_bytes':18029669,'xml':17,'json':44,'python':12,'javascript':3,'jsonl':20}
assert report['redactions']=={'exact_private_value':0,'fixture_repr_line':6}
assert report['known_private_residuals']==0 and not report['unclassified_token_candidates']
assert all(row['syntax_exit']==0 for row in report['javascript_syntax'])
indexed=load(ARCHIVE/'index.json')['entries'];indexed_raw={e['raw_path'] for e in indexed}
required_failures={
 '.runtime/typed-source-impact/ui-first.xml':{'PASS':63,'FAIL':11},
 '.runtime/typed-source-impact-backend/scalar-red.xml':{'FAIL':2},
 '.runtime/typed-source-impact-independent/development2.xml':{'PASS':28,'FAIL':1},
 '.runtime/typed-source-impact-independent/localcheck-repro.xml':{'FAIL':1},
}
for path,counts in required_failures.items():
    assert path in indexed_raw and report['historical_xml_statuses'][path]==counts
    assert path[:-4]+'.log' in indexed_raw
assert '.runtime/typed-source-impact/syntax-first-tool-output.log' in indexed_raw
assert '.runtime/typed-source-impact/syntax-first-failure.log' in indexed_raw
assert report['historical_xml_statuses']['.runtime/typed-source-impact/ui-second.xml']=={'PASS':74}
assert report['historical_xml_statuses']['.runtime/typed-source-impact-backend/final-focused.xml']=={'PASS':24}
assert report['historical_xml_statuses']['.runtime/typed-source-impact-independent/localcheck-green.xml']=={'PASS':1}
windows,root_nodes,regular,all_nodes=expected_windows()
assert Counter(root_nodes.values())=={'PASS':1689} and Counter(regular.values())=={'PASS':2004}
assert len(set(m for w in windows if w['label']!='independent-mixed' for m in w['modules']))==62
coverage=load(ROOT/'.runtime/typed-source-impact/final-coverage.json')
assert coverage['source_sha']==SHA and coverage['complete_module_count']==62 and coverage['unique_collected_testcases']==2004
assert coverage['disjoint_module_windows'] and not coverage['one_whole_repository_run'] and coverage['all_frozen_tracked_source_hashes_match']
assert coverage['tracked_source_files']==591 and coverage['separate_mixed_probes']['PASS']==3 and coverage['separate_mixed_probes']['source_sha']==SHA
names={'root-1':'root-shard-1','root-2':'root-shard-2','independent-formal':'independent-formal','review-extra':'independent-review-extra8'}
for claim in coverage['windows']:
    actual=next(w for w in windows if w['label']==names[claim['name']])
    assert claim['modules']==actual['modules'] and claim['source_sha']==SHA and claim['collection_junit_exact']
    assert Counter(actual['nodes'].values())=={k:v for k,v in claim['counts'].items() if v}
freeze=load(ROOT/'.runtime/typed-source-impact/freeze.json')['files'];assert len(freeze)==591
for name in ('root-1-v1','root-2-v1'):
    for suffix in ('before','after'):assert load(ROOT/f'.runtime/typed-source-impact/{name}-{suffix}.json')==freeze
for suffix in ('before','after'):
    review=load(ROOT/f'.runtime/typed-source-impact-review/extra-a5d9da25-{suffix}.json');assert len(review)==596 and all(review[p]==value for p,value in freeze.items())
all_frozen=frozen_sources();assert len(all_frozen)==11596
for name in ('formal','mixed'):
    for suffix in ('before','after'):
        files=load(ROOT/f'.runtime/typed-source-impact-independent/freeze-a5d9da2-{name}-{suffix}.json')['files']
        assert len(files)==11596 and files=={p:x['sha256'] for p,x in all_frozen.items()}
oracles=load(OUT/'oracle-html-recount.json');assert oracles['status']=='RECOUNTED_PASS' and len(oracles['html_runs'])==6
formal=oracles['oracle_windows'][0]['recomputed_statistics'];assert formal==coverage['literal_oracle'] or all(coverage['literal_oracle'][k]==v for k,v in formal.items())
for path,old in load(OUT/'archive-raw-snapshot.json').items():assert record(ROOT/path)==old
for path,old in load(OUT/'archive-export-snapshot.json').items():assert record(ROOT/path)==old
_,private=private_sets();assert private==report['private_sets']
assert record(ARCHIVE/'index.json')['sha256']==report['index_sha256']
metadata={name:record(ARCHIVE/name) for name in ('.gitattributes','README.md','audit.json','index.json')}
readme=(ARCHIVE/'README.md').read_text();assert '135 indexed' in readme and '18029669' in readme and 'not one whole-repository execution' in readme and 'prepared original verify script is not claimed executed' in readme
root_audit=load(ARCHIVE/'audit.json');assert root_audit['status']=='ROOT_HASH_STRUCTURE_RESIDUAL_PASS_INDEPENDENT_REBUILD_PENDING' and root_audit['prepared_legacy_verify_script_executed'] is False
assert root_audit['counts']=={'files':135,'bytes':18029669,'xml':17,'json':44,'python':12,'javascript':3,'jsonl':20}
public=ROOT/'docs/F2/TypedSourceImpact-20261015.md';text=public.read_text();public_before=record(public)
assert SHA in text and '@@' not in text and 'ROOT_RESULT' not in text and 'REVIEW_RESULT' not in text
for claim in ('900 PASS','789 PASS','53 PASS','262 PASS','1020.69s','1122.36s','220.35s','185.87s','37.59s','不是单次全仓回归','不是跨 Case 统一源实体','现每 Case 按钮尚未实现此反向发现','旧 v1','build_v1/GROUPS_V1','正式 AT','真实浏览器','远端 CI NOT_RUN','第二园区冷输入及有限模板结构增强已交付','6 条完整原 HTML','非当时重定向得到的原始文件'):
    assert claim in text,'missing accurate scope/count statement: '+claim
assert public_before==record(public)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
assert not subprocess.check_output(['git','diff','--name-only',SHA],cwd=ROOT,text=True).strip()
report.update(status='PASS',scope='Independent frozen source/primary archive/redaction/coverage/final-document audit; bounded Linux synthetic engineering evidence',delivery_engineering_gate='PASS_BOUNDED_LINUX_SYNTHETIC',external_acceptance='NOT_SIGNED_OFF',finished_final_gate_utc=datetime.now(timezone.utc).isoformat(),remaining_blockers=[],primary_indexed_pairs=135,independently_rebuilt_pairs=135,complete_module_count=62,unique_complete_module_tests=2004,single_whole_repository_run=False,mixed_probes_separate=3,final_window_counts=[{'name':w['label'],'modules':len(w['modules']),'counts':dict(Counter(w['nodes'].values())),'seconds':w.get('reported_elapsed_seconds',w.get('junit_seconds'))} for w in windows],original_failure_windows_retained=required_failures,all_before_after_source_manifests_match_frozen=True,full_tracked_scope={'count':11596,'bytes':sum(x['bytes'] for x in all_frozen.values()),'tracked_source_files':591,'reviewer_extra_editable_metadata':5,'reviewer_full_tracked_subwindow_timing_preserved':True},source_sha_at_final_audit=SHA,known_private_set_scope_note='13,591 distinct synthetic values are from explicitly designated test-generated private registries, including shared earlier template test registries. Registry use is redaction coverage, not exclusive per-window execution evidence. No private value is emitted.',oracle_html_recount=oracles,public_delivery_document={'path':str(public.relative_to(ROOT)),**public_before,'scope_and_remaining_gaps_accurate':True,'unfilled_result_placeholders':False},supplemental_metadata=metadata,optimization_differential=load(OUT/'redaction-differential-result.json'),optimization_proof='fast-redaction-equivalence.md',auditor_retries=[],limitations=['Linux synthetic engineering evidence only; VM DOM over real loopback HTTP/ASGI/owned PostgreSQL is not a real browser','Windows, formal AT24-27, real models, production and remote CI not executed','General dynamic/semantic graph and reverse source-to-all-authorized-Cases discovery not implemented in this finite per-Case slice','Earlier v1 compatibility conversion is a clearly labeled test fixture, not newly invented historical business evidence','Developmental/WIP windows remain historical and are not relabeled final-SHA executions','Separate sibling audit appendix export/commit/push remains root integration work; primary is unchanged'])
(OUT/'archive-independent-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
summary='''# Independent archive and final gate audit

**PASS within bounded Linux synthetic engineering scope.** Frozen source: `a5d9da251c223e3a64e20d3d47987d5b58fcdb6f`. No remaining blocker found in this slice.

Independently rebuilt135 raw/export pairs,18,029,669 bytes. All raw/export SHA256 and byte lengths match; all originals and exports remain unchanged. Six fixture repr lines are precisely redacted; exact-private replacements0. All13,591 designated synthetic43-character URL-safe values have zero residuals; no unclassified43-character candidates. XML17/JSON44/JSONL20/Python12/JS3 preserve structures and all testcase identities/statuses; all3 JS syntax checks pass. Root producer/verifier code was not imported.

The fast algorithm first passed17 differential tests and200 deterministic random cases, including edge boundaries, embedded and adjacent values, overlap/order fallback and structured formats. The original preparation slow script is preserved at its original hash. Actual135-pair rebuilding took6.48s; original producer output is unchanged.

Exact same-invocation collections/JUnit prove four disjoint complete-module windows: root27modules900PASS, root25modules789PASS, new2modules53PASS, review8modules262PASS. The union is62modules/2004 unique tests; it is not one whole-repository run. Runtime mixed3PASS is separate. Independently recounted formal11 and mixed3 literal oracles have zero missed/wrong/preservation differences; intentional unknown expansion remains distinct. All6 full original HTML VM/HTTP/ASGI/owned-PG traces match their stated action/denial counts.

Frozen source manifests match all591 tracked source/test/script/pyproject paths; reviewer also retains5 editable metadata paths. All11,596 frozen tracked files/248,128,564 bytes still match Git. Reviewer all-tracked static subwindow timing is accurately distinguished from its full-test source manifest. All original UI11FAIL, canonical2FAIL, developer1FAIL and separate1FAIL repro windows, their logs and followup results remain in primary evidence.

The completed public delivery document accurately states aggregate/stable per-Case group identity, old v1/new v2 frozen-schema proof compatibility, exact formal counts, retained failures, and remaining reverse cross-Case/general graph work. Previously implemented limited Release/ParkInstance/second-park/structural strengthening is not relisted missing. The unfinished @@TEST_TABLE@@ runtime template is explicitly excluded as non-execution drafting material. No primary export or source/Git was changed by this auditor.

Windows, actual browser, formal AT, real models, production and remote CI remain NOT_RUN. Root must export this audit separately as the sibling appendix, then perform documentation-only integration and authorized normal development-branch push. Those integration steps are not claimed completed here.

Detailed report: `archive-independent-audit.json`. Supporting evidence includes the preserved slow auditor, equivalence proof, differential log/result, raw/export snapshots, coverage recomputation and oracle/HTML recount.
'''
(OUT/'final-gate.md').write_text(summary)
print(json.dumps({'status':report['status'],'source_sha':SHA,'gate':report['delivery_engineering_gate'],'pairs':135,'unique_complete_module_tests':2004,'modules':62,'mixed_probes_separate':3,'remaining_blockers':[]},ensure_ascii=False))
