from pathlib import Path
p=Path('src/parkweave/web.html');s=p.read_text()
html='''<button id="service-release-preflight-read" type="button" class="secondary" hidden>只读预检此Case服务版本兼容性</button><section id="service-release-preflight-panel" hidden><h3>ServiceRelease 单Case兼容预检</h3><p>原采用版本来自冻结历史；目标须当前已审且属于同一服务谱系。合同差异与此Case当前来源分列，UNKNOWN不能判兼容。此入口只比较并可明确记录预检证据，不发布、迁移、回滚、采纳或办理。</p><label>原采用版本<select id="service-release-preflight-original"></select></label><label>当前目标实例<select id="service-release-preflight-target"></select></label><button id="service-release-preflight-preview" type="button" class="secondary">只读比较所选精确版本</button><div id="service-release-preflight-result"></div><label>预检记录说明<textarea id="service-release-preflight-reason" maxlength="1000"></textarea></label><label><input id="service-release-preflight-confirm" type="checkbox">我已核对此Case和精确版本，仅记录这份预检及拒绝原因</label><button id="service-release-preflight-save" type="button">明确记录预检证据</button><button id="service-release-preflight-recover" type="button" class="secondary" hidden>只GET核对原预检记录</button><p id="service-release-preflight-status" role="status" aria-live="polite"></p></section>'''
s=s.replace('<button id="service-selection-read"',html+'<button id="service-selection-read"',1)
s=s.replace('function clearServiceCasePlan(){','function clearServiceCasePlan(){clearServiceReleasePreflight();',1)
s=s.replace('function renderServiceCasePlan(x){','function renderServiceCasePlan(x){clearServiceReleasePreflight();',1)
s=s.replace('planCandidateControls();serviceSelectionControls();\n}', 'planCandidateControls();serviceSelectionControls();serviceReleasePreflightControls();\n}',1)
insert=Path('.runtime/service-release-preflight/ui.js').read_text()
s=s.replace('let planCandidateGeneration=0,',insert+'\nlet planCandidateGeneration=0,',1)
p.write_text(s)
