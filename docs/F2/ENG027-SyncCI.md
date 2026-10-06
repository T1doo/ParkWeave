# ENG027 普通同步与标准Windows Server CI

功能及已验证源码基线54fad8c704e8834b6f23979ef952f24830a83e8b。用户已解除ENG026时为避免盲目重复触发旧失败设置的临时push/newCI暂停，恢复定期普通push及现有标准Windows Server CI。本轮仅正常同步dev/f1-foundation；不forcepush、不merge main、不付费runner、不加Secrets、0LIVE/预算，不备份/导出/上传Library或正式部署。

## 推送前事实

默认沙箱初次只读ls-remote未能连现有代理8080；通过执行工具正式批准的同一命令网络权限后，使用原origin/default代理与身份成功读取实时dev/f1-foundation为6ff160abe979f9d1c28d0e7804fda668daf72cf5，未改代理/凭据/策略。它是54fad8c的祖先，完整11个连续本地提交可正常快进；普通push仍会保护并发远端变更，拒绝时不覆盖。

工作树初始干净；82个变更路径未含.runtime/.cache/.venv、私有恢复包/附件/运行期文件，凭据模式扫描无命中。当前121个冻结src/test/script hash与ENG026实测一致，594PASS/0FAIL/1WindowsSKIP；静态/独立审查及真实合成渲染证据见[ENG026](ENG026-SyncReadiness.md)。本轮只补必要准确文档，不修改已验证产品/测试源码。旧ENG026文档/JSON是当时未推送及暂停的历史快照，不充当当前GitHub状态。

## CI证据边界

推送只触发现有windows-server-engineering标准workflow。精确推送SHA、验证远端HEAD与新run终态在本轮取得后记；当前不预填CI通过。只读取获准状态与已有可读summary，不重试此前被拒的日志下载、不换身份绕过；具体case没有取得就明确UNKNOWN。

旧9a8cbc的CI37324704568唯一已知事实仍PreparePASS、native_suite78.094秒exit1，失败case/根因UNKNOWN。本轮可运行修订后的新回归，无需以猜测补旧日志。新Server结果也不是Win11验收；F1/F2未签收、R4关闭、36AT6EX NOT_RUN和真实业务/模型边界不变。

## 已同步与新CI实际终态

普通push成功，第一次源码同步后的实时远端HEAD精确验证为1baa2cf93f795dbf3036245b8f2ea2ec2ce15e56，包含全部已验证54fad8c及11个积累提交，再加仅授权说明的文档提交；此后结果文档提交不改变产品/测试源码。追加审计12个提交的192个历史变更blob，凭据模式0命中、运行期/私有包/附件0，121源码hash仍与594项本地通过时相同。成果已经在dev分支可见，不再称纯本地未推。

现有标准[Windows Server CI37414981257](https://github.com/T1doo/ParkWeave/actions/runs/37414981257)对精确1baa2cf源码头完成，conclusion=failure。Prepare成功；native_suite79.235秒exit1、未超时、direct child cleanup NOT_NEEDED；仅停止自有临时cluster步骤成功。没有变更runner/Secrets/主分支/安全门，也没有通过猜测做源码修复或盲目重复触发。

允许读取的check summary/text均为空；19条注释只提供阶段元数据/通用退出码和Actions提示，未提供case表或工程计数。实际失败case、case counts、根因仍UNKNOWN。未访问此前被拒的actions日志下载或换身份；不能把API摘要未提供说成Job Summary一定不存在。已请求用户提供本次新run Job Summary中的FAIL/NOT_RUN行（case/status/exit_code/category/counts，勿含凭据或原始私有日志）。旧37324704568的根因依旧未知，不以两个相近耗时/exit1猜根因。

完整[evidence/eng027-sync-ci.json](evidence/eng027-sync-ci.json)。当前已完成的是安全普通源码同步和标准CI终态核实；CI仍红，不能宣称Windows修复/原生通过或F1F2签收。后续只有取得实际失败case证据才能判断可恢复修复；R4关闭、Win11/36AT6EX NOT_RUN、0LIVE/部署/备份/导出/Library/真实模型预算保持。最后只追加准确结果文档并普通同步，workflow paths不含这些docs，不以文档提交制造新源码回归。
