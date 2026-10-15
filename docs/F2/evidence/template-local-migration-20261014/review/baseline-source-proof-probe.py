"""Independent source proof probes; own synthetic fixture fault injection only."""
from test_template_upgrade import *
import json
from parkweave.template_candidate import canonical, sha


def test_rehashed_target_description_must_match_original_review_publish_anchors(upgrade_case):
    u=upgrade_case
    row,_=instance(u)
    target=publication(u,name='Original independently reviewed description')
    with sqlite3.connect(u['engine'].repository.path) as c:
        original=c.execute('SELECT payload FROM template_releases WHERE id=?',(target['release_id'],)).fetchone()[0]
        document=json.loads(original)
        document['definition']['name']='SYNTHETIC unreviewed injected description'
        document['definition_sha256']=sha(document['definition'])
        document['review']['definition_sha256']=document['definition_sha256']
        c.execute('DROP TRIGGER immutable_template_release_payload')
        c.execute('UPDATE template_releases SET payload=?,payload_sha=? WHERE id=?',(canonical(document),sha(document),target['release_id']))
        c.execute(u['engine'].repository.TRIGGERS['immutable_template_release_payload'])
    changed={**target,'release_sha256':sha(document)}
    response=check(u,row,changed)
    assert response.status_code in (403,409), response.text
