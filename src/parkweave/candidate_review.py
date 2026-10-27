"""Three-field structured projections; no arbitrary document parser/provider call.
All input excerpts are explicitly synthetic, supplied claims, not verified documents.
"""
import hashlib
import json
from datetime import datetime
from .domain import ModelCandidate

class MockCandidateModel:
    mode='OFFLINE_MOCK_MODEL'
    def propose(self,evidence):
        return json.dumps([item.model_dump(exclude={'origin'})|{'origin':'MODEL_CANDIDATE','verification':'UNVERIFIED'} for item in evidence],ensure_ascii=False)

def fingerprint(document):
    return hashlib.sha256(json.dumps(document,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def project(evidence,model):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate projection key')
            result[key]=value
        return result
    raw=model.propose(evidence)
    if type(raw) is not str or len(raw.encode())>32768:raise ValueError('candidate projection size')
    parsed=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite candidate')))
    if not isinstance(parsed,list) or len(parsed)>len(evidence):raise ValueError('candidate projection count')
    candidates=[ModelCandidate.model_validate(x).model_dump() for x in parsed]
    # Model cannot invent a source/field/excerpt/validity or relabel a source as verified.
    bindings=[x.model_dump(exclude={'value','origin'}) for x in evidence]
    for item in candidates:
        if {k:v for k,v in item.items() if k not in ('value','origin','verification')} not in bindings:
            raise ValueError('candidate source binding changed')
    return [x.model_dump()|{'verification':'UNVERIFIED'} for x in evidence]+candidates

LABELS={'region':'地区','employees':'员工人数','service_need':'服务诉求'}
def document(fields,projections,assertions,now):
    results=[];questions=[]
    for field in fields:
        evidence=[x for x in projections if x['field']==field]
        for row in assertions:
            if row['field_name']==field:
                evidence.append({'field':field,'value':row['value'],'unit':row['unit'],'source_ref':row['source_ref'],
                    'source_excerpt':row['source_excerpt'],'validity':{'valid_from':row['valid_from'].isoformat(),'valid_until':row['valid_until'].isoformat(),'timezone':'UTC'},
                    'origin':'USER_STATEMENT','verification':'UNVERIFIED','fact_id':str(row['id']),'fact_revision':row['revision'],'fact_fingerprint':row['fingerprint']})
        valid=[x for x in evidence if datetime.fromisoformat(x['validity']['valid_from'])<=now<datetime.fromisoformat(x['validity']['valid_until'])]
        values={json.dumps([x['value'],x['unit']],ensure_ascii=False) for x in valid}
        reason='MISSING' if not evidence else 'EXPIRED' if not valid else 'CONFLICT' if len(values)>1 else 'UNVERIFIED'
        results.append({'field':field,'state':'UNKNOWN','reason':reason,'evidence':evidence})
        questions.append({'field':field,'reason':reason,'required':True,'prompt':LABELS[field]+('：请补充自述及来源版本。' if reason=='MISSING' else '：请补充有效来源。' if reason=='EXPIRED' else '：来源不一致，请说明并提供依据。' if reason=='CONFLICT' else '：已有候选尚未核实，请提供可授权核查的依据。')})
    return {'schema_version':'parkweave/candidate-review/1','source':'SYNTHETIC_CANDIDATE_REVIEW','model_mode':'OFFLINE_MOCK_MODEL',
        'assessed_at':now.isoformat(),'results':results,'necessary_questions':questions,'qualification_decision':'NOT_EVALUATED',
        'verification':'UNVERIFIED','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}
