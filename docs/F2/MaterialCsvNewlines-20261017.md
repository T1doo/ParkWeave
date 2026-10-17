# CSV字段换行保真修补

父线程对 `b6a862f6414e16915c0da6c79326851434d1590a` 追加独审发现P2：CSV解析前的全文CRLF/CR→LF会改变带引号单元格内容。原197项未覆盖该场景，b6未获本次最终准入；原源码、全部窗口和证据保留。本修补在独立正常开发分支接续。

先新增4个红例，实际4FAIL：字段内CRLF、独立CR、实际API候选→原ADD→factory重启，以及实际选文件→原ADD→普通进程重启。原字段 `first\r\nsecond\rthird` 曾变为 `first\nsecond\nthird`。

解析器仅在非CSV格式继续原全文换行处理。CSV原解码文本交给 `csv.reader(StringIO(text,newline=''))` 区分外部记录与带引号字段；`csv.writer(QUOTE_ALL,lineterminator='\n')` 仅规范外部记录分隔，字段内CRLF/CR/LF、空格、字面反斜杠、引号和Unicode逐项保留。

浏览器textarea本身会规范CR，因此含字段CR的CSV在候选全文和原表单采用明确的JSON字符串转义显示；例如 `\r` 代表CR、`\n` 代表LF。用户可直接提交，或保留外层引号和转义编辑可见文字，也可修改原文件重导入。原ADD构造正文前只解码一次，随后使用原身份/状态/未知操作门、key、pending body、保存、审核和恢复链。编辑模式纳入草稿指纹，与正文共同清除；同事项刷新保留完整草稿。普通无字段CR的CSV和其他三种文件继续原编辑方式。

转义显示最大24002单位，仅是4000正文单位的最坏`\uXXXX`表示空间；原文件8192字节、实际正文4000 UTF-16单位、API请求16384字节、CSV32列/100数据行及所有身份/来源门不变。解码失败、非字符串、空白、正文超限、NUL/非法控制符/孤立surrogate在生成key或POST前拒绝。

## 冻结与实际验证

冻结源码：`320c0692615ef15feef230bde02719355d6c469f`；分支：`dev/f2-material-csv-newlines-20261017`；基础：`b6a862f6414e16915c0da6c79326851434d1590a`。727个源/测试/脚本/配置哈希，724个既有文件（包括原后端保存算法和全部权限/迁移配置）字节不变。本次完整 **207PASS / 0FAIL / 0ERROR / 0SKIP**，JUnit 548.431秒（pytest548.44秒）。完整10模块包含原197项和本修补10项；不同窗口不相加。新10项涵盖逐单元格相等、原ADD网络body/DB/hash、手工编辑、字面转义不双解码、4000正文边界、实际下载及普通进程重启回读、8类非法编辑零key/零POST、刷新/身份ABA/实际HTTP403清私有草稿。

丢响应场景先让原ADD成功，再故障注入丢失200；原UNKNOWN门仍禁用编辑。测试明确用客户端DOM故障注入修改禁用框后重试，验证只发送原精确pending.body和同key，未提交的新草稿保留；这不是普通用户可越过禁用门的流程。下载仍用原材料文本包算法，JSON引号内正文还原后与数据库精确相等。

## 全部窗口与审查说明

red-v1：4FAIL/22.744秒（预期红例）；green-v1：4PASS/20.50秒。edge-v1：8PASS/2FAIL/131.288秒，测试尝试编辑原UNKNOWN禁用框及未等待异步填入；保留原门并改为明确故障注入/等待。edge-v2：5PASS/5FAIL/59.465秒，一次受保护文案替换断言中止后仍启动新预览断言，补丁未落位导致4红；另1项过早把加载时隐藏当成403完成。全部原件和对应失败源码快照保留。edge-v3：10PASS/111.61秒。

审查曾认为换行提示有双反斜杠，根代理通过实际执行及码点[92,114,20195]证实运行时是单反斜杠；独审确认这是工具JSON表示层误判，标记FALSE_POSITIVE，源码文案未降转义。独审首次hash命令误列不存在的`test_material_csv_newlines_browser.py`返回1，随后按实际合并测试模块完整前后核对均0；这不是产品或测试失败。受保护替换的AssertionError同样保留，不以错误“修复”破坏原正确提示。

## 范围与后续用户功能

本片仍为本机隔离SYNTHETIC样例，真实性UNVERIFIED，不证明资格、外部受理、现实履约或Case完成。没有新增实际身份/Grant/分派/目录/批准/凭据、真实模型、安全网络权限、部署或Actions查询；NativeRunAccess默认拒绝permit/writer、正式来源入口保持原边界。Windows原生正式AT及真实业务未验，完整项目尚未完成。运行前提继续见[原文件导入报告](MaterialFileImport-20261017.md)，缺少合法输入时准确拒绝。

已并行只读核下一项：当前多目标办理证据只有在线展示和原步骤导航，唯一下载仅材料TXT；可复用原goal-results生成“本事项办理记录核对包”，包含全部必需目标、当前实际本地输出引用、原核验事件、未达成原因及明确合成快照范围，不新增模型或授权。原方案依据为产品§5.2/§5.5和F2-T02/T04/T07；源码依据为`case_goal_results.py:139–211`、API `goal-results`、`readGoalResults`及当前唯一Blob材料下载。此项尚未写产品代码，等待当前修补最终准入后接续。

完整[证据门](evidence/material-csv-newlines-20261017/gate.json)、[最终JUnit](evidence/material-csv-newlines-20261017/final-v1.xml)、[冻结727清单](evidence/material-csv-newlines-20261017/freeze.json)、[独审](evidence/material-csv-newlines-20261017/independent-review.json)、[所有失败记录](evidence/material-csv-newlines-20261017/failure-ledger.json)、[原件与导出映射](evidence/material-csv-newlines-20261017/public-pairs.json)及[下一用户功能只读核查](evidence/material-csv-newlines-20261017/next-readonly-audit.json)。导出只脱敏随机合成会话，JSON键、JUnit节点和实际远端ref逐字保留；原件在`.runtime/material-csv-newlines`与本窗口`/tmp/parkweave-material-csv-*`。

新精确交付SHA、实际远端差异与工作区结果在推送后记录于最终回复及`.runtime/material-csv-newlines/delivery-verification.json`；父线程最终准入仍待这次修补交付后的只读独审。

归档原pytest失败trace的尾空白原样保留，整包`git diff --check`返回2；精确排除上述6份原日志/XML后其余交付文件检查0，冻结源码检查0，未为消除空白提示改写原证据。
