"""Mechanical independent mapping only; never imports product code or runs tests."""
import argparse,hashlib,json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave')
SCOPE='EMPLOYEES_USER_ASSERTION_V1'
TARGET='18145586c90c394b0022721f114eac36a0893504'
I='tests/test_employees_fact_provenance_independent.py::'
B='tests/test_employees_fact_provenance.py::'
R='tests/test_employees_fact_provenance_review.py::'
# An exact match means its frozen literal partition was asserted over actual HTTP.
MAP={
 'FP01':('BOUNDED_HTTP_LITERAL', [I+'test_exact_historical_selection_read_without_card_is_pure']),
 'FP02':('BOUNDED_HTTP_LITERAL', [I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[employees-FP02]']),
 'FP03':('BOUNDED_HTTP_LITERAL', [I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[same_value-FP03]']),
 'FP04':('NOT_RUN',[]),
 'FP05':('VARIANT_MULTIPLE_SOURCE_FIELDS_CHANGED',[I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[employees-FP02]']),
 'FP06':('NOT_RUN',[]),
 'FP07':('VARIANT_MULTIPLE_SOURCE_FIELDS_CHANGED',[I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[employees-FP02]']),
 'FP08':('BOUNDED_HTTP_LITERAL',[I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[unselected-FP08]']),
 'FP09':('BOUNDED_HTTP_LITERAL',[I+'test_actual_fact_confirmation_then_explicit_original_adopt_verify[region-FP09]']),
 'FP10':('BOUNDED_HTTP_LITERAL',[I+'test_resource_change_preserves_original_p1_lock_and_verify_evidence']),
 'FP11':('NOT_RUN',[]),
 'FP12':('BOUNDED_HTTP_LITERAL',[I+'test_receipt_change_preserves_three_original_locks']),
 'FP13':('NOT_RUN',[]),
 'FP14':('BOUNDED_HTTP_LITERAL',[I+'test_missing_or_wrong_original_confirmation_history_stays_unknown[missing_historical_event]',I+'test_missing_or_wrong_original_confirmation_history_stays_unknown[missing_receipt]']),
 'FP15':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[wrong_sha]']),
 'FP16':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[descriptor_sha]']),
 'FP17':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[source_sha]']),
 'FP18':('VARIANT_PURE_SCOPE_REJECTION_AND_HTTP_REQUEST_DENIAL',[B+'test_historical_detail_is_never_filled_from_current[wrong_owner]',I+'test_cross_tenant_owner_and_role_never_receive_private_provenance']),
 'FP19':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[duplicate_choice]']),
 'FP20':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[missing_row]']),
 'FP21':('VARIANT_PURE_TYPE_AND_REVISION_REJECTION',[B+'test_historical_detail_is_never_filled_from_current[bad_revision]']),
 'FP22':('NOT_RUN',[]),
 'FP23':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[duplicate_row]']),
 'FP24':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[wrong_field]']),
 'FP25':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[unsupported_source]']),
 'FP26':('VARIANT_HTTP_UNKNOWN_MALFORMED_LEDGER',[I+'test_missing_or_wrong_original_confirmation_history_stays_unknown[missing_historical_event]']),
 'FP27':('NOT_RUN',[]),
 'FP28':('PURE_REJECTION_ONLY',[B+'test_historical_detail_is_never_filled_from_current[scalar_snapshot]',B+'test_historical_detail_is_never_filled_from_current[bad_value]',B+'test_historical_detail_is_never_filled_from_current[bad_row_keys]']),
 'FP29':('LEGACY_PURE_LITERAL_ONLY',['tests/test_typed_source_impact.py::test_unknown_field_is_hashed_and_expands_this_case_without_echo_or_authority']),
 'FP30':('VARIANT_LEGACY_REQUEST_SERIALIZATION',[B+'test_optional_request_extension_preserves_legacy_serialization']),
 'FP31':('NOT_RUN',[]),
 'FP32':('BOUNDED_HTTP_LITERAL',[I+'test_resource_change_preserves_original_p1_lock_and_verify_evidence']),
 'FP33':('BOUNDED_HTTP_LITERAL',[I+'test_affected_lock_requires_original_explicit_unlock']),
 'FP34':('NOT_RUN',[]),
 'FP35':('VARIANT_CURRENT_ADOPT_AUTHORITY_DENIAL',[I+'test_revoke_then_restore_does_not_revive_old_preview']),
 'FP36':('VARIANT_REAL_TWO_COMMIT_ABA_BOUNDARY',[I+'test_source_row_aba_between_preview_and_original_adopt_refuses']),
 'FP37':('VARIANT_COMMITTED_RESPONSE_LOSS_AND_COLD_GET',[I+'test_full_original_html_explicit_employees_adoption_and_authority[lost_ack]',I+'test_same_key_changed_scope_parameters_and_cold_original_get']),
 'FP38':('VARIANT_ORIGINAL_KEY_PARAMETER_CONFLICT',[I+'test_same_key_changed_scope_parameters_and_cold_original_get']),
 'FP39':('VARIANT_NEW_V3_THEN_LEGACY_V2_AND_COLD_GET',[I+'test_enhanced_history_then_default_adopt_is_nonsticky_and_cold_readable']),
 'FP40':('VARIANT_COMBINATION_REJECTS_WITH_LEGACY_PREVIEW',[I+'test_existing_manual_or_package_combination_refuses_only_new_scope[MATERIAL_PACKAGE]']),
}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('xml',nargs='+');ap.add_argument('--output',required=True);ap.add_argument('--source-sha',required=True);args=ap.parse_args()
 cases={};inputs=[]
 for arg in args.xml:
  p=Path(arg);r=ET.parse(p).getroot();inputs.append(dict(path=str(p.resolve()),sha256=sha(p)))
  for c in r.findall('.//testcase'):
   identity=c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name']
   status='FAIL' if c.find('failure') is not None or c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
   cases.setdefault(identity,[]).append(dict(xml=str(p.resolve()),identity=identity,status=status))
 oracle=ROOT/'docs/F2/EmployeesFactProvenanceOracle-20261015.json';rows=[]
 for row in json.loads(oracle.read_text())['rows']:
  kind,ids=MAP[row['id']];evidence=[x for id in ids for x in cases.get(id,[])]
  all_present=bool(ids) and all(id in cases for id in ids)
  passed=all_present and all(x['status']=='PASS' for x in evidence)
  execution='PASS' if passed else 'NOT_RUN' if not evidence else 'INCOMPLETE_OR_FAILED'
  rows.append(dict(id=row['id'],scenario=row['scenario'],literal_expected=row['expected'],coverage_kind=kind,
     execution=execution,exact_literal_http_pass=passed and kind=='BOUNDED_HTTP_LITERAL',evidence=evidence,
     limitation=None if kind=='BOUNDED_HTTP_LITERAL' else 'This evidence does not execute the entire design row as a real HTTP literal partition scenario.'))
 counts={}
 for r in rows:counts[(r['coverage_kind'] if r['execution']=='PASS' else r['execution'])]=counts.get((r['coverage_kind'] if r['execution']=='PASS' else r['execution']),0)+1
 result=dict(schema=1,scope=SCOPE,source_sha=args.source_sha,oracle_sha256=sha(oracle),evidence_xml=inputs,
   status='MECHANICAL_MAPPING_NOT_AN_ADDITIONAL_TEST',counts=counts,rows=rows,
   note='Pure rejection proves no facade partition, VARIANT is explicitly partial, same testcase may support multiple design rows. Do not sum40 rows as tests. Windows/browser/AT/models/production NOT_RUN.')
 Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(rows=len(rows),counts=counts)))
if __name__=='__main__':main()
