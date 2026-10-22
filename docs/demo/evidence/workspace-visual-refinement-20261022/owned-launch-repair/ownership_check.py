"""Pure ownership boundary checks; no subprocess/browser/network execution."""
from scripts.visual_owned_launch import owned_basis,stable_owned_binding
import json
owner=10;sid=20
row=dict(pid=30,ppid=owner,session=sid,start_ticks=100)
def change(**kw):return dict(row,**kw)
cases=[
 ('direct_child',row,row,row,True),
 ('private_session_member',change(ppid=21),change(ppid=21),change(ppid=22),True),
 ('adopted_setsid_child',change(session=30),change(session=30),change(session=30),True),
 ('stale_candidate_reused_pid',row,change(start_ticks=101),change(start_ticks=101),False),
 ('pid_reused_after_open',row,row,change(start_ticks=101),False),
 ('stale_ancestor_is_not_authority',change(ppid=21,session=40),change(ppid=21,session=40),change(ppid=21,session=40),False),
 ('lost_direct_parent_same_birth',change(session=40),change(session=40),change(ppid=99,session=40),False),
 ('lost_private_session_same_birth',change(ppid=21),change(ppid=21),change(ppid=21,session=40),False),
 ('ownership_basis_changed_between_reads',change(session=40),change(session=40),change(ppid=21),False),
 ('candidate_pid_changed',row,change(pid=31),change(pid=31),False),
]
for name,candidate,before,after,want in cases:
 assert stable_owned_binding(candidate,before,after,owner,sid)==want,name
assert not owned_basis(change(ppid=21,session=40),owner,None)
print(json.dumps({'status':'PASS','pure_ownership_cases':len(cases),'cases':[x[0] for x in cases],'browser_runs':0,'CI_runs':0},indent=2))
