from pathlib import Path
import json
OUT=Path('.runtime/frontier-repair-ui')
def registry(f):
 OUT.mkdir(parents=True,exist_ok=True);p=OUT/'redaction-browser-fixtures.private.json';rows=json.loads(p.read_text()) if p.exists() else [];rows.append(f[2]);p.write_text(json.dumps(rows));p.chmod(0o600)
def capture(page,kind):
 OUT.mkdir(parents=True,exist_ok=True)
 value=page.evaluate("""()=>({active_flow:activeEntryWriteFlow?.kind??null,request_count:entryWriteRequests.size,requests:[...entryWriteRequests.values()].map(x=>({path:x.path,stage:x.stage,observed:x.observed})),read_allowed:entryReadAllowed('bounded-planning-read'),plan_id:planId,preview:!!(typeof dispatchExecutionPreviewView!=='undefined'&&dispatchExecutionPreviewView),receipt_preview:!!(typeof receiptExecutionPreviewView!=='undefined'&&receiptExecutionPreviewView),feedback:document.getElementById('page-feedback').textContent,bounded_error:document.getElementById('bounded-planning-error').textContent})""")
 p=OUT/(kind+'-open-states.json');rows=json.loads(p.read_text()) if p.exists() else [];rows.append(value);p.write_text(json.dumps(rows,indent=2))

def change_case_with_pending_preview(page,p,kind):
 # Controlled component setup via the same original loadPlan GET used by open_page.
 # This does not claim UNKNOWN UI navigation is allowed: the bounded-read click
 # must still be refused, and the exact original flow/opaque storage retained.
 storage=page.evaluate('JSON.stringify({...localStorage})')
 assert storage!='{}'
 flow=page.evaluate_handle('activeEntryWriteFlow')
 assert page.evaluate('(flow)=>flow!==null&&activeEntryWriteFlow===flow',flow)
 page.evaluate('(id)=>loadPlan(id)',p['preparation_id'])
 page.wait_for_function('(id)=>planView!==null&&planId===id',arg=p['preparation_id'])
 assert page.evaluate("entryReadAllowed('bounded-planning-read')") is False
 assert page.evaluate('(flow)=>activeEntryWriteFlow===flow',flow)
 assert page.evaluate('JSON.stringify({...localStorage})')==storage
 requests=[]
 def observe(request):requests.append(request.method+' '+request.url)
 page.on('request',observe)
 try:
  page.locator('#bounded-planning-read').click()
  assert page.evaluate("entryReadAllowed('bounded-planning-read')") is False
  assert page.evaluate('(flow)=>activeEntryWriteFlow===flow',flow)
  assert page.evaluate('JSON.stringify({...localStorage})')==storage
  assert page.evaluate(kind+'ExecutionPreviewView===null')
  assert '尚未确定' in page.locator('#page-feedback').inner_text()
  assert requests==[]
 finally:page.remove_listener('request',observe);flow.dispose()
 capture(page,kind+'-controlled-case')
