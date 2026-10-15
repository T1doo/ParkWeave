from pathlib import Path
p=Path('src/parkweave/web.html');s=p.read_text()
s=s.replace("if(!pure&&mutates(fn))element[event]=trackedEntryFunction", "if(!pure&&element.id!=='service-release-preflight-save'&&mutates(fn))element[event]=trackedEntryFunction",1)
s=s.replace("const h={schema:1,id:c.id,actor:c.actor,key:crypto.randomUUID(),plan:c.planId,revision:c.revision,sha:v.preflight_sha256};", "try{requireOriginalEntriesSettled();}catch(e){$('service-release-preflight-status').textContent=e.message;return;}const h={schema:1,id:c.id,actor:c.actor,key:crypto.randomUUID(),plan:c.planId,revision:c.revision,sha:v.preflight_sha256};",1)
s=s.replace("(function installOriginalWriteFlows(){", "// Preflight evidence has its own opaque-key lifecycle and writes only its dedicated\n// journal. Its handler checks all existing business-entry gates before retaining a\n// key; it must not acquire a business flow and then reject that same flow.\n(function installOriginalWriteFlows(){",1)
p.write_text(s)
