from pathlib import Path
from datetime import datetime,timezone
import json,os,re
spec=[('note-template-carry-final','root-1-v2'),('note-template-carry-final','root-2-v2'),('note-template-carry-final','common-v2'),('note-template-carry-backend-formal-v2','formal'),('note-template-carry-independent-formal-v2','note-carry-v2'),('note-template-carry-independent-formal-v2','prior-manual-v2'),('note-template-carry-review-formal-v2','freeze-f686ada-extra-v2')]
rows=[]
for folder,name in spec:
 p=Path('.runtime')/folder/(name+'.log');s=p.read_text(errors='replace') if p.exists() else ''
 progress=''.join(re.findall(r'(?m)^([.FEsxX]+)(?:\s+\[\s*\d+%\])?\s*$',s))
 rows.append(dict(name=name,progress_dots=progress.count('.'),failure_letters=progress.count('F'),error_letters=progress.count('E'),bytes=len(s.encode()),last_line=s.splitlines()[-1][-120:] if s.splitlines() else 'RUNNING/no flushed output'))
r=dict(utc=datetime.now(timezone.utc).isoformat(),loadavg=os.getloadavg(),windows=rows,progress_counts_are_not_final_pass=True)
with Path('.runtime/note-template-carry-root/formal-monitor-v3.jsonl').open('a') as stream:stream.write(json.dumps(r)+'\n')
print(json.dumps(dict(utc=r['utc'],progress={x['name']:[x['progress_dots'],x['failure_letters'],x['error_letters']] for x in rows},note='running progress only; final scores require JUnit'))) 
