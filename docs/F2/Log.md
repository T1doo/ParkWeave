# F2并行工程日志

## ENG014进行中checkpoint（2026-10-05）

用户明确授权GitHub/Windows阻塞期间继续一个有界用户功能，不改F1准入/F1PASS。原F2前置真实模型/Windows与完整基础门仍未通过，切片对应F2-T01/T04/T05/T07工程子集，完整F2/36AT6EX NOT_RUN，R4关闭。基线1828653，dev/f1-foundation；无AGENTS/.agents新指令，无子agent/Sim修改/隐藏凭据读取/真实模型/预算/付费服务。

实现版本化合成企业资料整理服务，链接真实本地Case/Run，企业追加两个材料槽来源/版本，获派专员补正/人工核对当前hash，企业确认本地资料准备或重开；任何新材料使旧review失效、历史不删。qualification始终NOT_EVALUATED、资料真实性UNVERIFIED、external NOT_SUBMITTED/offline NO_EVIDENCE，原Case NEEDS_INPUT。无外部受理或线下成效。显式PREPARE/REVIEW_ASSIGNED Grant+固定角色/同园区企业/owner或精确assignment交集；应用无DDL/Grant修改或历史UPDATE/DELETE。当前API写与不可变事件同事务，版本/幂等/并发保护；GET短行共享锁防止半快照，保持当前授权锁协议。创建锁原Run避免不同key同Case竞态。Schema9为新增业务表；原schema版本断言升级9，未来版本拒绝测试改10，未删oracle。

Linux定向第一次30 PASS/6.22秒，补并发同Case与审核-补件竞态、Grant范围/不重激活等后34 PASS/4.93秒；原基础21 PASS/2.91秒。当前相关三组81 PASS/1 Windows SKIP/2既有WARN/58.86秒。TestClient+实际PG用例均只SYNTHETIC；浏览器用loopback实际API/独立worker/PG16.2 Python3.12.14，cached agent-browser0.38.2/Chromium，无下载/远端连接。

真实浏览器前两次成功走通创建/资料/双角色补正核对确认/重开/reload/字面脚本text，然后320px横向溢出断言失败。首次给select加border-box和button最大宽度尚未解决，继续定位；**browser完整证据仍FAIL、全量回归未冻结**，不把此checkpoint标READY或PASS。两Library原档完整字节/行/hash和files.py/windows_files.py/Win11probe/workflow逐字不变。

用户新提供另一环境GitHub读取恢复线索；本环境尚未证实。先安全保存本地checkpoint，再在原环境/原代理/原身份各一次Actions原target与远端分支状态复核。没有fetch/push/runner前，不声称网络/权限恢复；若Forbidden停依赖不绕过；成功才fetch/比较history，保留双方工作，不force或主分支合并。最终backup待阶段成果仅更新一次，此checkpoint不上传备份。
