from pathlib import Path
# Executed only after the first frozen test window has fully closed.
for name in ['case_cancellation_offline.js','case_cancellation_reconciliation_offline.js']:
 p=Path('tests')/name;s=p.read_text()
 marker="  const dcode=html.slice(html.indexOf('function renderDispatch(')" if name=='case_cancellation_offline.js' else "   const block=html.slice(html.indexOf('function renderDispatch(x,catalog)')"
 at=s.index(marker)
 code="  vm.runInContext(html.slice(html.indexOf('let dispatchAcceptHandle='),html.indexOf('function dispatchAcceptControls(')),context);\n"
 s=s[:at]+code+s[at:]
 s=s.replace("context.dx={preparation_id:","context.dx={actor_ref:'a'.repeat(64),preparation_id:",1) if name=='case_cancellation_offline.js' else s.replace("context.dx={dispatch_id:","context.dx={actor_ref:'a'.repeat(64),dispatch_id:",1)
 p.write_text(s)
