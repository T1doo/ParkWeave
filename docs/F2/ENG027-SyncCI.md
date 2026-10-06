# ENG027 普通同步与标准Windows Server CI

功能及已验证源码基线54fad8c704e8834b6f23979ef952f24830a83e8b。用户已解除ENG026时为避免盲目重复触发旧失败设置的临时push/newCI暂停，恢复定期普通push及现有标准Windows Server CI。本轮仅正常同步dev/f1-foundation；不forcepush、不merge main、不付费runner、不加Secrets、0LIVE/预算，不备份/导出/上传Library或正式部署。

## 推送前事实

默认沙箱初次只读ls-remote未能连现有代理8080；通过执行工具正式批准的同一命令网络权限后，使用原origin/default代理与身份成功读取实时dev/f1-foundation为6ff160abe979f9d1c28d0e7804fda668daf72cf5，未改代理/凭据/策略。它是54fad8c的祖先，完整11个连续本地提交可正常快进；普通push仍会保护并发远端变更，拒绝时不覆盖。

工作树初始干净；82个变更路径未含.runtime/.cache/.venv、私有恢复包/附件/运行期文件，凭据模式扫描无命中。当前121个冻结src/test/script hash与ENG026实测一致，594PASS/0FAIL/1WindowsSKIP；静态/独立审查及真实合成渲染证据见[ENG026](ENG026-SyncReadiness.md)。本轮只补必要准确文档，不修改已验证产品/测试源码。旧ENG026文档/JSON是当时未推送及暂停的历史快照，不充当当前GitHub状态。

## CI证据边界

推送只触发现有windows-server-engineering标准workflow。精确推送SHA、验证远端HEAD与新run终态在本轮取得后记；当前不预填CI通过。只读取获准状态与已有可读summary，不重试此前被拒的日志下载、不换身份绕过；具体case没有取得就明确UNKNOWN。

旧9a8cbc的CI37324704568唯一已知事实仍PreparePASS、native_suite78.094秒exit1，失败case/根因UNKNOWN。本轮可运行修订后的新回归，无需以猜测补旧日志。新Server结果也不是Win11验收；F1/F2未签收、R4关闭、36AT6EX NOT_RUN和真实业务/模型边界不变。
