# ENG039 有界安全 GitHub annotations

基线3016589140b77acc62d7371b657b019abbac08e3。用户采用ENG038只读诊断方案，授权本地实现/独立审查/提交，不push、新发CI、下载日志或增加权限。Windows run37420887816仍FAIL，具体根因UNKNOWN；本轮不是根因修复，也未验证GitHub端实际新通知发布。

## 精确代码变化

仅4份源码：scripts/windows_ci/publish_summary.py在既有current-run绑定与安全project之后新增annotations白名单重建/有界整批构造/独立二进制出口；tests/test_safe_annotations.py新增真实本地CLI、注入/类型/数量/字节/故障及Windows换行模拟；tests/test_summary_publication.py将JSON读取限定为stdout首文档；scripts/windows_ci/diagnostic-test-ids.json同步新增14函数，合计411。原console安全JSON和Job Summary内容保留，stdout在JSON后追加notice，因此不再是单个JSON文档，消费者应先解码首JSON或按固定notice前缀逐行读。

只使用固定title的notice，不使用error命令。全批先验证所有case，再构造一个发布头与最多7个FAIL/NOT_RUN摘要，PASS计入头部计数。最多8条；每条完整UTF-8命令含末尾LF≤2048字节；整批≤16384字节；全批最多25个测试ID。少写整条case/ID时返回明确annotation_cases_omitted/annotation_ids_omitted，保留来源ids_truncated，不截字符串、JSON或ID。来源case最多32且既有报告64KiB限制保持。

字段只含固定kind/state、report_state/active_phase、case_counts、case/status/exit_code/phase/category/reason、counts/counts_state、diagnostic_state/failed_test_ids、工程case计数及遗漏标记。当前精准测试白名单再次核验，ID转换为test_module::test_function，去掉tests/及.py和参数；没有file/line位置属性或路径。未知字段不投影，非法枚举/数值/身份范围/ID整批关闭。不会输出run环境值、cluster路径、用户内容、凭据、异常正文或原始日志。JSON采用ASCII序列化，百分号先编码，再处理CR/LF；标题不是输入。构造异常仅固定ANNOTATIONS_UNAVAILABLE；二进制短写/写/flush或其它Exception返回publisher1，不吐异常文字，不吞KeyboardInterrupt/SystemExit。

annotations出口先flush原JSON，再写sys.stdout.buffer的UTF-8/LF字节，绕过Windows文本CRLF转换。旧console失败仍尝试Job Summary；新annotations失败也不抑制先前独立出口。publisher成功仅表示安全发布步骤成功，不能把原Test失败改为成功；native_suite、workflow、contents:read、always发布后Stop顺序均未改。不新建checks写权限、token入口、artifact或日志上传，也不扩大环境白名单。

## 实际验证及独立审查

初次61相关例PASS；两位独立只读审查同时找到CRLF计数P2，均确认修复后无剩余实质阻断。主代理独立本地模拟证实旧文本8条×声明2048实际每条2049/整批16392超限；二进制精确边界为每条2048/整批16384。最终冻结4份源码相关169PASS/0FAIL/0SKIP/1既有WARN（8.63s），包含真实CLI原始字节、整批先验证/注入/跨总量25ID/完整项裁剪、发布读写故障及原失败结果/清理回归。reviewer未运行测试/网络，成绩由实现者取得。

23份原保护文件保持hash，唯一授权变化是publisher；所有ENG037业务src hash保持，原837最终冻结及拒绝路径证明保留，不把837称本轮重新全量回归。当前GitHub端annotations送达、原生Server/Win11及整项36AT6EX仍NOT_RUN，F1/F2未签收、R4关闭、真实模型/预算0。

## 输出示例

以下仅本地SYNTHETIC例，不能作为run37420887816的失败case/根因。完整stdout仍先有原安全JSON；新两条annotation如下：

```text
::notice title=ParkWeave safe diagnostics::{"kind":"publication","state":"SUMMARY_AVAILABLE","report_state":"COMPLETED","active_phase":"UNKNOWN","case_counts":{"PASS":0,"FAIL":1,"NOT_RUN":0},"annotation_cases_omitted":0}
::notice title=ParkWeave safe diagnostics::{"kind":"case","case":"full_engineering_regression","status":"FAIL","exit_code":1,"phase":"regression_run","category":"AssertionError","counts":{"PASS":0,"FAIL":1,"SKIP":0},"diagnostic_state":"AVAILABLE","failed_test_ids":["test_lifecycle::test_config_write_is_exclusive_and_no_secret_fields"],"test_cases_seen":1,"failed_cases":1,"unknown_failed_cases":0,"ids_truncated":false,"annotation_ids_omitted":0}
```

具体冻结hash、界限及审查范围见[evidence](evidence/eng039-safe-annotations.json)。精确代码补丁由本次本地commit与基线3016589比较生成到.runtime/eng039-annotations-code.patch。未来是否普通push及运行既有标准CI由用户另行决定；本轮未触发。
