import pathlib,json,hashlib,re,datetime,sys
O=pathlib.Path(__file__).parent;B=pathlib.Path('/workspace/ParkWeave/docs/F2/evidence/at-service-cold-entry-20261014');H=lambda b:hashlib.sha256(b).hexdigest();initial=(O/'audit284-result.json').read_bytes();r=json.loads(initial);idx=(B/'export-index.json').read_bytes();d=json.loads(idx);errors=[]
# Each identifier hash was individually reviewed in its actual surrounding raw
# bytes. No candidate values are copied to this audit artifact.
reviewed={
'164cecceaf49b46af09c338f75475d55bc3391cad6bbf549b7f3af2bebbba026':'manifest basename .json (nodevm observed traffic)',
'f4f8d3cd250f9258d5ded9ea79b232a671a6b0ecac85ccbe612fe29bedc513a0':'manifest basename .json (full-chain isolation outcome)',
'f925bbc79b48a2150bfb8a1174fac755c9f0aeb9d6b747bfd3746a5b1c252e3e':'fixed uppercase service scope metadata',
'3549e75dc22e122ce2179f8b733040e2f0e34bf224ffd609bcb08395c3b4d9d2':'test module basename in source hash manifest; same identifier in old audit',
'c2505a39426457dc72e13cd096bb9925d03f32e7b2959f446491b01fa13aeb98':'pytest testcase function identifier',
'3e3e24a7731c51338b47593240fb46f57a4e905d13de6bed2fe6e9c4dee9321e':'pytest testcase parameter identifier (entry isolation)',
'b68d86f2564336514735499487e50e908abe9a9e195d39cca53d144960629fa7':'pytest testcase parameter identifier (reconciliation state)',
'988fb665d75ef50f02474ae04277073d344f35b491e32146a8322d22f46590ca':'old audit explicitly classified test identifier metadata',
'c0aa00bb52fd26f57688c095aca6d6831da8fd8c6ee1fbbf7271b5db94bd89a2':'old audit explicitly classified test identifier metadata',
'518ab9c882cb25c63d46bee0eec663723947b5bf1ae1d89a604e7ae167ef0c7d':'old audit explicitly classified test identifier metadata',
'5ae6ebe1d50fdbc3f2f2337eae3e404a2d2c4f64408c40571f2f2b2e783ec697':'old audit explicitly classified test identifier metadata',
'64efaf742d6b31f833da0e0e58fb7501a98025436943fa6bd8e6dcc45f81235e':'fixed oracle JSON boolean key (not a value)'}
if set(reviewed)!={x['sha256'] for x in r['actual_session_candidates']}:errors.append('reviewed set mismatch')
if r['errors']!=[['unreviewed session clues',12,0]]:errors.append('unexpected initial mechanical/scanner error')
allowed_auth={"                        options=message['options'];assert options['headers']['Authorization']=='Bearer SYNTHETIC_NODE_API_SESSION'", "                        actual_headers={**options['headers'],'Authorization':'Bearer '+tokens['fixture-c']}"}
if {x['masked_context'] for x in r['authorization_clues_for_context_review']}!=allowed_auth:errors.append('unreviewed authorization context')
if H(idx)!=r['index_sha256']:errors.append('index drift')
for e in d['entries']:
 raw=pathlib.Path(e['original']).read_bytes();out=(B/e['export']).read_bytes()
 if raw!=out or H(raw)!=e['raw_sha256'] or H(out)!=e['export_sha256'] or len(raw)!=e['raw_bytes'] or len(out)!=e['export_bytes']:errors.append([e['export'],'bytes/hash/length changed'])
 for m in re.finditer(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])',out):
  v=m.group()
  if H(v) not in reviewed and not (v.startswith(b'test_') and re.fullmatch(rb'[a-z_]+',v)):errors.append([e['export'],'new opaque candidate',H(v)])
report=pathlib.Path('/workspace/ParkWeave/docs/F2/ATServiceColdEntry-20261014.md').read_text()
report_checks={'source_full_sha_correct':d['source_sha'] in report,'AT07_bounded': '真实模型效果/LIVE未验，不签完整AT' in report,'AT14_not_claimed_full':'完整预览写后对照LIVE命名空间' in report,'AT33_business_ABC_distinction':'A/B/C是三类业务，不是Case编号' in report,'CI_NOT_RUN':'CI NOT RUN' in report,'other_environments_NOT_RUN':'Windows、真实模型、付费调用、生产迁移/部署均NOT RUN' in report,'old_test_counts_not_new':'不重跑或转签新源码' in report}
if not all(report_checks.values()):errors.append(['report scope',report_checks])
result={'status':'FAIL' if errors else 'PASS','run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':d['source_sha'],'index_sha256':H(idx),'initial_conservative_scanner_result_preserved_sha256':H(initial),'initial_exit':'1; unresolved context clues, not actual session confirmation','exports':284,'raw_export_byte_equality':284,'unique_export_paths':r['unique_export_paths'],'unique_original_paths':r['unique_original_paths'],'directory_set_exact':not r['unindexed_files'] and not r['missing_files'],'hash_length_and_end_stability':not errors,'actual_session_values_detected':0,'literal_replacements':0,'reviewed_opaque_shape_candidates':reviewed,'all_43char_unique_candidates':len(r['all_43char_candidates']),'authorization_clues':'Only fixed offline placeholder and source variable concatenation; no literal actual session','retained_nonzero_exit_file_count':len(r['retained_nonzero_exit_files']),'retained_nonzero_exit_files':r['retained_nonzero_exit_files'],'report_scope_checks':report_checks,'limits':'Independent archive bytes and context review, not a rerun/signoff of full AT, models, Windows, browser or CI. Scan covers all 43-char URL-safe candidates plus sensitive JSON keys and session/Bearer literals; not a universal credential detector.','errors':errors}
(O/'audit284-context-reviewed-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(bool(errors))
