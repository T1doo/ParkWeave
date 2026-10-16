from pathlib import Path
html=Path('src/parkweave/web.html').read_text();start=html.index('async function unifiedDependencyPropagationCheck(');end=html.index('function renderUnifiedDependencyPropagation(',start);s=html[start:end]
old=""" const ids=g.step_endpoints.map(s=>s.id),affected=g.unknown_scope?ids:ids.filter(id=>reached.has(id)),preserved=g.unknown_scope?[]:ids.filter(id=>!reached.has(id));
 if(!same(paths,g.propagation_paths)||!same(g.changed_node_ids,g.nodes.filter(n=>n.changed).map(n=>n.id))||!same(g.changed_observation_ids,g.observations.filter(o=>o.changed).map(o=>o.id))||!same(g.affected,affected)||!same(g.preserved,preserved)||!same(g.affected,v.affected)||!same(g.preserved,v.preserved)||!same(g.affected,old.affected)||!same(g.preserved,old.preserved)||!Array.isArray(g.unknown_reasons)||g.unknown_scope!==null&&g.unknown_scope!=='THIS_CASE')fail();
"""
new=""" const ids=g.step_endpoints.map(s=>s.id),reachedIds=ids.filter(id=>reached.has(id)),unreachedIds=ids.filter(id=>!reached.has(id)),reasons=[...old.unknown_reasons];
 if(!old.unknown_scope&&(!same(old.affected,reachedIds)||!same(old.preserved,unreachedIds)))reasons.push('SOURCE_PARTITION_UNEXPLAINED');
 const expectedReasons=[...new Set(reasons)].sort(),unknown=!!(old.unknown_scope||expectedReasons.length),expectedUnknown=unknown?'THIS_CASE':null,affected=unknown?ids:reachedIds,preserved=unknown?[]:unreachedIds;
 if(!same(paths,g.propagation_paths)||!same(g.changed_node_ids,g.nodes.filter(n=>n.changed).map(n=>n.id))||!same(g.changed_observation_ids,g.observations.filter(o=>o.changed).map(o=>o.id))||!same(g.affected,affected)||!same(g.preserved,preserved)||!same(g.affected,v.affected)||!same(g.preserved,v.preserved)||!unknown&&(!same(g.affected,old.affected)||!same(g.preserved,old.preserved))||!same(g.unknown_reasons,expectedReasons)||g.unknown_scope!==expectedUnknown)fail();
"""
assert s.count(old)==1;s=s.replace(old,new)
Path('.runtime/unified-propagation-review/strict-unknown-checker-candidate.js').write_text(s)
import difflib
Path('.runtime/unified-propagation-review/strict-unknown-checker-candidate.patch').write_text(''.join(difflib.unified_diff(html[start:end].splitlines(True),s.splitlines(True),fromfile='web.html:current',tofile='private-strict-unknown-candidate')))
p=Path('.runtime/unified-propagation-review/unified_dependency_client_probes.js');js=p.read_text().replace("const code=html.slice(html.indexOf('async function unifiedDependencyPropagationCheck('),html.indexOf('function renderUnifiedDependencyPropagation('));", "const code=process.env.REVIEW_CHECKER?fs.readFileSync(process.env.REVIEW_CHECKER,'utf8'):html.slice(html.indexOf('async function unifiedDependencyPropagationCheck('),html.indexOf('function renderUnifiedDependencyPropagation('));")
js=js.replace("process.stdout.write(JSON.stringify({evidence_kind:", "results.push(await scenario('rehashed_invented_unknown_reason',g=>{g.unknown_reasons=['UNRECORDED_PRIVATE_REASON']},false));\n process.stdout.write(JSON.stringify({evidence_kind:")
p.write_text(js)
p=Path('.runtime/unified-propagation-review/test_unified_dependency_client_probes.py');p.write_text(p.read_text().replace("==7 and", "==8 and"))
