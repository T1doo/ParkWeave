# F1 真实日志

## 2026-10-05 DOC-001

仓库 origin=https://github.com/T1doo/ParkWeave.git；初始31e7acb7e53bb1ab6465b9daae59de28757f7583，work干净；新分支dev/f1-foundation。仓库与工作区没有可读AGENTS.md或相关技能文件。没有访问Sim2Act或用户电脑。

完整Library read：454行44220字节、410行31271字节；has_more=false。文本响应均少一个末尾LF；补一个LF后精确匹配元数据，哈希见sources/V1/manifest.json。原件不可修改，工作正文追加授权小修。

新增验收规格由全文转录，未收到原JSON/DocumentReview等原包附件；初态与执行器待实现，全部NOT_RUN。文档完整性核对PASS，仅为文档检查；产品测试NOT_RUN。模型/Windows/真实园区主张BLOCKED。代码提交：本记录随文档提交，实际SHA在下一日志记录。

## 2026-10-05 ENG-001（首个有界工程增量）

文档基线提交00f1d8a317e6676c9139cb8d9f6702ee504617a5，已push并用git ls-remote核对一致。本记录随首个工程提交；实际提交SHA通过Git历史/交付链接关联，执行代码逐文件hash见evidence/engineering-manifest.json。

变更：自建Python包/API/独立worker/PostgreSQL迁移及应用角色权限、严格0.1契约投影、有限三值函数、可信case.create/1、事务Operation/Receipt/outbox、租约fencing、当前授权锁、暂停取消、三工作区骨架；全部合成，本地建单不推进业务履约。没有访问或复用Sim2Act代码，没有调用真实模型API。

实际环境：Linux云x86_64，Python3.12.14，PostgreSQL16.2（pgserver0.1.4测试分发），其他精确版本见requirements-linux-evidence.txt。API/worker端口/PID、运行/操作ID、输入hash及状态见evidence/http-smoke.json；它们是本次历史进程证据，不代表一直在线。Windows精确版本尚未测。

失败与修复：
- 默认uv缓存/home/agent/.cache只读→失败；指定工作区缓存后安装成功。
- 第一次pytest：10 FAIL / 11 PASS。身份表FOR SHARE要求UPDATE权限，与最小角色冲突；改为共享advisory授权锁，owner撤权同键独占锁，不给应用身份修改权限。第二次21 PASS，最终21 PASS，见pytest-final.txt。
- 浏览器默认socket目录只读→指定XDG_RUNTIME_DIR；后续缺少容器沙箱参数失败→每次明确Chromium及--no-sandbox（仅测试容器）。初始UI刷新验证失败；点击轨迹显示布局切换后点击落在html根节点，补页面快照与语义定位后流程通过。另修复UI吞掉错误，显示请求错误。临时诊断和截图未纳入交付。

实际命令：uv venv/uv pip install；python -m pytest -q --tb=short；python scripts/linux_fixture_server.py（启动独立API/worker）；agent-browser0.38.2本机Chromium验证，由scripts/browser_smoke.py复现。浏览器open/页面内容/三入口/受理及状态读取PASS，错误为空；实际HTTP202、Case NEEDS_INPUT、Run LOCAL_CASE_CREATED、跨园区403，工程PASS。均仅Linux合成工程结果；未映射整个AT为PASS。

剩余：完整AT/EX NOT_RUN；AT-01/02/34的Windows/真实模型门BLOCKED，真实园区效果BLOCKED。资格自动判断、资源预约、文件导入、多角色/字段Grant、外部结果不明、长任务心跳、共享总限流/成本都未完成。Schema0.1仅当前投影，不宣称V1全契约已实现。C0模板正文/关联作品政策/截止时刻仍BLOCKED，用户当前报名和提交日期2026-11-05。

所有依赖为安装的上游包，不复制依赖源码/二进制进仓库；Linux测试包pgserver不作Windows运行依赖。当前未开展开源许可证发布选择，不宣称整个仓库已有开源许可。提交前排除.venv/.cache/.runtime/egg-info；审查差异及高置信秘密模式，原件hash重验。合成会话、数据库文件、访问日志与截图不提交。

下一步候选：补V1完整领域契约与事实冲突；增加作用域Grant与各角色；独立FAULT_INJECTION外部未知结果账本。Windows及模型条件未满足前保持对应门BLOCKED，不自动进入F2真实办理。
