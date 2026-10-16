from pathlib import Path
import json
OUT=Path('.runtime/frontier-repair-ui')
def registry(f):
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/'redaction-browser-fixtures.private.json';rows=json.loads(p.read_text()) if p.exists() else [];rows.append(f[2]);p.write_text(json.dumps(rows));p.chmod(0o600)
def capture(page,kind):
 OUT.mkdir(parents=True,exist_ok=True)
 value=page.evaluate("""()=>({active_flow:activeEntryWriteFlow?.kind??null,request_count:entryWriteRequests.size,requests:[...entryWriteRequests.values()].map(x=>({path:x.path,stage:x.stage,observed:x.observed})),read_allowed:entryReadAllowed('bounded-planning-read'),plan_id:planId,preview:!!(typeof dispatchExecutionPreviewView!=='undefined'&&dispatchExecutionPreviewView),receipt_preview:!!(typeof receiptExecutionPreviewView!=='undefined'&&receiptExecutionPreviewView),feedback:document.getElementById('page-feedback').textContent,bounded_error:document.getElementById('bounded-planning-error').textContent})""")
 p=OUT/(kind+'-open-states.json');rows=json.loads(p.read_text()) if p.exists() else [];rows.append(value);p.write_text(json.dumps(rows,indent=2))
