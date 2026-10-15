from pathlib import Path
p=Path('src/parkweave/web.html');s=p.read_text()
marker='<section id="opp-plan-preview" hidden>'
section='''<section id="material-package-panel" class="combination-panel"><h4>明确确认双槽材料包并保留人工正文</h4><p>读取仅显示原捕获材料、当前实际材料和本人正文。明确提交后，本计划启用双槽检查；任一材料槽或人工正文变化后须重新确认。诉求摘要仅确认上下文；目录发生变化时仍按原文条件承载。不判断语义义务、事实或资格。</p><p>从上方选择本次当前机会；P1有锁先沿原入口解锁。确认后仍须分别执行原局部采纳与受影响核验。</p><button id="material-package-read" type="button">读取双槽材料包与人工正文</button><button id="material-package-recover" type="button">只读核对原双槽确认</button><p id="material-package-status" role="status" aria-live="polite"></p><div id="material-package-result"></div><label>保留原文的追加合并稿<textarea id="material-package-note" maxlength="4000"></textarea></label><label>本次确认说明<textarea id="material-package-reason" maxlength="1000"></textarea></label><label><input id="material-package-confirm" type="checkbox">我已核对两槽实际版本和当前人工正文，明确启用或更新本计划的双槽确认</label><button id="material-package-keep" type="button" disabled>保留当前正文并明确确认双槽材料包</button><button id="material-package-merge" type="button" disabled>保存追加合并稿并明确确认双槽材料包</button></section>'''
assert s.count(marker)==1;s=s.replace(marker,section+marker)
marker="const fbStorage='parkweave.case-fact-bundle-recovery.v1.';"
assert s.count(marker)==1;s=s.replace(marker,Path('.runtime/multifield-source-root/material-package-ui.js').read_text()+'\n'+marker)
repls=[
("function clearPlanSourceConflict(){planSourceConflictGeneration++;", "function clearPlanSourceConflict(){clearMaterialPackage();planSourceConflictGeneration++;"),
("servicePlanRecoveryHandle||planSourceConflictPending()||localCaseLocked()", "servicePlanRecoveryHandle||planSourceConflictPending()||materialPackagePending()||localCaseLocked()"),
("if(owns('planSourceConflictWrite',planSourceConflictPending()))return true;", "if(owns('planSourceConflictWrite',planSourceConflictPending())||owns('materialPackageWrite',materialPackagePending()))return true;"),
("if(planSourceConflictPending()&&kind!=='planSourceConflictWrite'", "if(materialPackagePending()&&kind!=='materialPackageWrite'&&!(kind==='boundedPlanning'&&args[0]!==true)){const e=Error('原双槽确认待GET核对，禁止另一写入');e.independentEntryRefusal=true;if(handler)pageError(e);throw e;}\n if(planSourceConflictPending()&&kind!=='planSourceConflictWrite'"),
("const originals={planSourceConflictWrite,generateServiceSelection", "const originals={materialPackageWrite,planSourceConflictWrite,generateServiceSelection"),
(" planSourceConflictWrite=trackedEntryFunction(originals.planSourceConflictWrite", " materialPackageWrite=trackedEntryFunction(originals.materialPackageWrite,'materialPackageWrite',new Set(['materialPackageWrite']));\n planSourceConflictWrite=trackedEntryFunction(originals.planSourceConflictWrite")
]
for a,b in repls:
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
p.write_text(s)
