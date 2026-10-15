"""Small deterministic differential tests; uses invented local strings only."""
import importlib.util
import json
from pathlib import Path
import random
import string
import sys
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fast_known_redaction import KnownTokenRedactor, PLACEHOLDER, reference_replace


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
slow=module('preserved_slow_auditor',HERE/'redaction_slow_reference.py')
fast=module('optimized_independent_auditor',HERE/'redaction_reconstruct.py')
A='a'*42+'X';B='b'*42+'Y';C='c'*42+'Z'


class DifferentialTests(unittest.TestCase):
    def check(self,text,values):
        redactor=KnownTokenRedactor(values)
        self.assertEqual(redactor.replace(text),reference_replace(text,values))
        self.assertEqual(redactor.has_residual(text),any(value in text for value in values))
        changed=reference_replace(text,values)[0]
        self.assertEqual(redactor.has_residual(changed),any(value in changed for value in values))
        return redactor

    def test_empty_pool(self):self.check(A+' plain',[])
    def test_empty_text(self):self.check('',[A,B])
    def test_exact_start_end(self):
        for text in (A,A+'!', '!'+A,'!'+A+'!',A+' '+B):self.check(text,[A,B])
    def test_embedded_in_long_urlsafe_word(self):self.check('prefix'+A+'suffix',[A,B])
    def test_adjacent_nonoverlap(self):
        r=self.check(A+B+C,[C,A,B]);self.assertEqual(r.stats['fast_calls'],1);self.assertEqual(r.stats['exact_replacements'],3)
    def test_duplicate_known_values(self):self.check(A+' '+A,[A,A,B])
    def test_42_and_44_boundaries(self):
        self.check(A[:-1],[A]);self.check(A+'Q',[A]);self.check('Q'+A,[A])
    def test_no_false_positive_unknown_43_value(self):self.check(C,[A,B])
    def test_unicode_and_newline_boundaries(self):self.check('汉字'+A+'\n'+B+'🙂',[A,B])
    def test_same_value_overlapping_occurrences(self):
        r=self.check('A'*86,['A'*43]);self.assertEqual(r.stats['fallback_overlap_calls'],1)
    def test_different_value_overlaps_preserve_reference_order(self):
        text='a'*42+'bc';p='a'*42+'b';q='a'*41+'bc'
        x=self.check(text,[p,q]);y=self.check(text,[q,p]);self.assertEqual(x.stats['fallback_overlap_calls'],1);self.assertEqual(y.stats['fallback_overlap_calls'],1)
        self.assertNotEqual(reference_replace(text,[p,q]),reference_replace(text,[q,p]))
    def test_invalid_length_pool_uses_reference(self):
        r=self.check('short '+A,['short',A]);self.assertEqual(r.stats['fallback_pool_calls'],1)
    def test_invalid_charset_pool_uses_reference(self):
        v='?'+'x'*42;r=self.check(v+' '+A,[v,A]);self.assertEqual(r.stats['fallback_pool_calls'],1)
    def test_placeholder_does_not_introduce_matching_token(self):self.check('a'*30+A+'a'*30+' '+PLACEHOLDER,[A,'a'*43])
    def test_deterministic_random_differential(self):
        rng=random.Random(20261015);alphabet=string.ascii_letters+string.digits+'_-'
        for _ in range(200):
            pool=[''.join(rng.choices(alphabet,k=43)) for _ in range(rng.randrange(1,9))]
            pieces=[rng.choice(pool) if rng.randrange(3)==0 else ''.join(rng.choices(alphabet+'\n🙂 ',k=rng.randrange(90))) for _ in range(rng.randrange(15))]
            self.check(''.join(pieces),pool)
    def test_structured_formats_match_preserved_slow_auditor(self):
        failure="fixture = (<parkweave.store.Store object at 0x123>, {'fixture-a': '"+A+"'})\nassert actual == expected\n"
        tree=ET.Element('testsuites');suite=ET.SubElement(tree,'testsuite',tests='1',failures='1');case=ET.SubElement(suite,'testcase',classname='tests.test_sample',name='sample');ET.SubElement(case,'failure').text=failure
        cases=[('.xml',ET.tostring(tree)),('.json',(json.dumps({'message':failure,'nested':[A,B,17,True,None],'unrelated':'kept'})+'\n').encode()),('.jsonl',(json.dumps({'token':A})+'\n'+json.dumps({'message':failure})+'\n').encode()),('.log',(A+'\n'+failure+B).encode())]
        for suffix,raw in cases:
            r=KnownTokenRedactor([A,B]);self.assertEqual(fast.reconstruct(raw,suffix,[A,B],r),slow.reconstruct(raw,suffix,[A,B]))
    def test_structured_formats_overlap_fallback_matches_slow(self):
        values=['A'*43];raw=json.dumps({'tokens':['A'*86,'A'*44]}).encode();r=KnownTokenRedactor(values)
        self.assertEqual(fast.reconstruct(raw,'.json',values,r),slow.reconstruct(raw,'.json',values));self.assertEqual(r.stats['fallback_overlap_calls'],2)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DifferentialTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'randomized_cases':200,'real_private_values_used':False,'actual_archive_audit':'NOT_RUN'}
    (HERE/'redaction-differential-result.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value));sys.exit(not result.wasSuccessful())
