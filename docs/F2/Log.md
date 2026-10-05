# F2并行工程日志

## ENG014进行中checkpoint（2026-10-05）

用户明确授权GitHub/Windows阻塞期间继续一个有界用户功能，不改F1准入/F1PASS。原F2前置真实模型/Windows与完整基础门仍未通过，切片对应F2-T01/T04/T05/T07工程子集，完整F2/36AT6EX NOT_RUN，R4关闭。基线1828653，dev/f1-foundation；无AGENTS/.agents新指令，无子agent/Sim修改/隐藏凭据读取/真实模型/预算/付费服务。

实现版本化合成企业资料整理服务，链接真实本地Case/Run，企业追加两个材料槽来源/版本，获派专员补正/人工核对当前hash，企业确认本地资料准备或重开；任何新材料使旧review失效、历史不删。qualification始终NOT_EVALUATED、资料真实性UNVERIFIED、external NOT_SUBMITTED/offline NO_EVIDENCE，原Case NEEDS_INPUT。无外部受理或线下成效。显式PREPARE/REVIEW_ASSIGNED Grant+固定角色/同园区企业/owner或精确assignment交集；应用无DDL/Grant修改或历史UPDATE/DELETE。当前API写与不可变事件同事务，版本/幂等/并发保护；GET短行共享锁防止半快照，保持当前授权锁协议。创建锁原Run避免不同key同Case竞态。Schema9为新增业务表；原schema版本断言升级9，未来版本拒绝测试改10，未删oracle。

Linux定向第一次30 PASS/6.22秒，补并发同Case与审核-补件竞态、Grant范围/不重激活等后34 PASS/4.93秒；原基础21 PASS/2.91秒。当前相关三组81 PASS/1 Windows SKIP/2既有WARN/58.86秒。TestClient+实际PG用例均只SYNTHETIC；浏览器用loopback实际API/独立worker/PG16.2 Python3.12.14，cached agent-browser0.38.2/Chromium，无下载/远端连接。

真实浏览器前两次成功走通创建/资料/双角色补正核对确认/重开/reload/字面脚本text，然后320px横向溢出断言失败。首次给select加border-box和button最大宽度尚未解决，继续定位；**browser完整证据仍FAIL、全量回归未冻结**，不把此checkpoint标READY或PASS。两Library原档完整字节/行/hash和files.py/windows_files.py/Win11probe/workflow逐字不变。

用户新提供另一环境GitHub读取恢复线索；本环境尚未证实。先安全保存本地checkpoint，再在原环境/原代理/原身份各一次Actions原target与远端分支状态复核。没有fetch/push/runner前，不声称网络/权限恢复；若Forbidden停依赖不绕过；成功才fetch/比较history，保留双方工作，不force或主分支合并。最终backup待阶段成果仅更新一次，此checkpoint不上传备份。

## ENG014阶段成果：READY_FOR_REVIEW（非F2签收）

修复后诊断确认320px viewport/scroll406且控件盒本身未越界：资料历史中脚本文本长单词溢出。section overflow-wrap:anywhere使完整文本换行，不以隐藏overflow裁切材料。第三次浏览器全链PASS（320/390均等宽）；追加单事项64事件上限后重启实际API/worker，并对冻结最终源重新验证浏览器PASS。原owned harness parent cwd只读检查遭psutil AccessDenied，未发送信号；用精确原argv/相同uid/已记录API+worker均直属父进程的安全交叉校验，再向自己的harness SIGTERM；它退出0/停止自身children，不发现或广泛杀进程，不改策略。

最终新增35项pytest PASS/5.26秒（真实PG/TestClient，包括事务失败rollback、历史权限、版本/并发/撤权）；冻结全量 `.venv/bin/python scripts/run_acceptance.py --report docs/F2/evidence/eng014-acceptance-summary.json`：**388 PASS/0 FAIL/1 Windows SKIP/2既有WARN，108.474秒**，84个src/test/script hash匹配，compileall/diffcheck通过。原schema期望8升级9、未来版本拒绝改10，只随新增迁移合理调整，没有移除旧oracle。

最终Linux Chromium用实际低权限API+独立worker+PG16.2 Python3.12.14、双角色真实表单，不修改数据库完成资料流程。创建→一个槽→专员要求补正→企业追加目录→专员核对当前hash→企业确认本地资料准备→reload→重开→追加版本→拒绝未重新核对的确认；三材料版本/所有人工事件保留。320/390模拟无横滚、页面错误0、脚本文本未执行、切身份清空旧资料。只SYNTHETIC，未收到真实目录/资格证据，不宣称客户或园区试点。实际重启前的Preparation在重启后仍IN_PREPARATION/3材料版本/8事件；最终API回读Run SUCCEEDED但Case NEEDS_INPUT/external NOT_SUBMITTED/offline NO_EVIDENCE，见独立restart-and-case-check证据。

用户新授权的本线程网络复核仅一次：安全checkpoint be5742e之后，原Actions target依旧Get ...: Forbidden/CLI exit1，数值HTTP状态/header/requestID/拒绝层UNKNOWN；Git原origin分支只读查询exit0，5185cf4与基线相同。由此不能称Actions/全部通道恢复；未fetch/push/runner，不新登录/换代理/读token/改权限。完整非敏感错误及结果见eng014-access-recheck.json，官方Work Mode状态调查同源未证实。其他环境/Sim分支线索不继承到Park。

本轮功能切片至此结束：企业资料准备/人工核对有可见可操作闭环，不只辅助测试；F2完整多服务计划/资源/执行者接单与真实回执/模板仍未做。F1 IN_PROGRESS、F2正式准入NOT_PASSED、whole36AT6EX NOT_RUN、R4 DISABLED、Windows/LIVE/真实数据门保留，provider请求及预算0。原V1来源字节/行/hash和R4/Win11 guard/workflow保护保持；低权限Grant与纯文本新API均本地可信代码，不执行任意生成代码，无外部业务写入。FirstUse说明显式合成入口/角色与限制，Plan标注新授权仅替代此前当轮不扩F2限制。

暂存前检查凭据模式无命中、无真实个人数据或private runtime/会话/DSN日志，安全本地commit保留checkpoint历史。阶段成果后仅更新一次用户私有Library恢复备份；不频繁上传，不把备份或恢复验证称Windows业务验收。最终本轮停止，交父任务复核派下一切片。
