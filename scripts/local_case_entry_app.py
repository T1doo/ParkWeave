"""Ordinary configured product API plus read-only local launch diagnostics."""
from fastapi import Header
from fastapi.responses import HTMLResponse
from parkweave.api import configured_app
from parkweave.store import Store, Denied
import os

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>本地事项入口</title>
<style>body{max-width:800px;margin:32px auto;padding:16px;font:17px/1.7 system-ui}input,button{font:inherit;max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>隔离合成本地事项入口</h1><p>本入口可创建、明确确认并保存本地待补件记录；不证明六目标完成、外部受理或真实履约。</p>
<p>首次 setup 仅创建固定合成身份和原本地权限。日常启动不补权限、分派或批准。重启保留结果，/tmp 清理或机器销毁会丢失，重要结果须另行保存。</p>
<label>已有本机合成会话 <input id="session" type="password" autocomplete="off"></label>
<button id="check">只读核对当前范围</button><pre id="scope" role="status"></pre>
<p>在 setup 输出目录的 .runtime/synthetic-sessions.json 中本机私下读取 fixture-a 会话，勿粘贴到日志或 URL。此页不保存会话。</p>
<a href="/">打开原确认与办理页面</a>
<ol><li>在原页面输入同一会话和本次目标，点击“创建本地办理记录”。</li><li>点击前核对目标；“创建本地办理记录”会提交原本地动作，随后记录原运行编号。</li><li>重启后重新输入会话，使用“找回我的本地办理记录”或原运行编号读取；读取不重复提交。</li></ol>
<h2>当前阻断</h2><p>完整新 Case 的获派执行者、可信服务目录和计划批准跨进程接线尚无普通运行时路径。不会借用测试 fixture、自动 assignment、重建 issued 证明或把 Mock 批准当事实。完整 P1–P5 与正式 AT-35 仍未签收。Windows、浏览器全链、真实模型、生产均未由本启动器验收。</p>
<script>let generation=0;const token=document.getElementById('session'),out=document.getElementById('scope');token.oninput=()=>{generation++;out.textContent='';};document.getElementById('check').onclick=async()=>{const g=++generation;out.textContent='正在读取';try{const r=await fetch('/api/local-entry/scope',{headers:{Authorization:'Bearer '+token.value}});if(g!==generation)return;if(!r.ok)throw Error('当前会话或权限不可用；保持阻断');const x=await r.json();if(g===generation)out.textContent='角色：'+x.role+'；本地创建：'+(x.can_submit_local_case?'当前授权允许，原提交仍会复核':'当前不可用')+'；完整办理：阻断；目标完成：未证明';}catch(e){if(g===generation)out.textContent=e.message;}};</script></html>'''


def app():
    application = configured_app()
    # Same explicit restricted DSN as configured_app; no owner/issued state.
    store = Store(os.environ['PARKWEAVE_DSN'], mode='LOCAL')

    @application.get('/local-entry', response_class=HTMLResponse)
    def entry():
        return PAGE

    @application.get('/api/local-entry/scope')
    def scope(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith('Bearer '):
            from fastapi import HTTPException
            raise HTTPException(401, 'session required')
        with store.connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            p = store.auth(c, authorization[7:], lock=True)
            store.check_capability(c, p, 'READ')
            allowed = False
            try:
                store.check_capability(c, p, 'EXECUTE')
                allowed = p['role'] == 'enterprise_operator' and bool(c.execute(
                    "SELECT 1 FROM action_grants WHERE principal_id=%s AND action='case.create' AND park_id=%s AND org_id=%s AND active",
                    (p['id'], p['park_id'], p['org_id'])).fetchone())
            except Denied:
                pass
        return dict(role=p['role'], can_submit_local_case=allowed,
                    scope='ISOLATED_SYNTHETIC_LOCAL_CASE_ONLY', case_goal_completed=False,
                    full_chain='BLOCKED_NO_RUNTIME_ASSIGNMENT_CATALOG_APPROVAL',
                    assignment_written=False, approval_enabled=False, production_execution=False)

    return application
