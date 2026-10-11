# Fact 历史泄露 oracle 修正证据

最终冻结测试源码：`8e3e2f23d9380333f21e37b157d1d7d8c132e976`。父候选：`b1beff467dbc54c77eea985ca2b7208f70b202ec`。候选分支：`acceptance/fact-history-leakage-oracle-20261011`。本片源改动仅 `tests/test_fact_history_read_source.py`，生产 `src` Git tree 与父候选完全相同。

旧 oracle 将事实整数17转换成字符串，在整个JSON中搜索，误中允许返回的source_sha256。新 oracle 使用闭合输出字段白名单、精确str键/值类型和完整允许值；摘要须等于根据合成输入独立计算的预期摘要。输出无法用新增字段、允许标量/列表或摘要槽携带事实值、原片段、来源ID；合法摘要中数字子串不代表返回了该事实值。准确输出字段等值断言保留。

固定合成UUID1003–1013的实际projection摘要为 `1ab214b54e972ae2231da520785615e66a899c101a448b4c8b963508627d5717`，包含员工数文本17。正对照确认接受；事实内容注入、合法64hex替换、公共flags类型混淆与私有键别名负对照确认拒绝。根最终 oracle 控制87项通过，是最终339项中的子集。

输入不变检查拆成独立收集的测试，在projection的finally中运行精确递归类型和值比较；字典键必须精确str，序列类型/长度及标量类型和值须保留。负控覆盖int17→float17.0、int1→boolTrue、boolTrue→int1，在projection返回或抛异常后均检测突变；无突变时不吞掉原异常。输出断言失败不会遮蔽该独立测试。

独审发现并复现了初步oracle的两处遗漏：字符串子类键能冒充白名单键但序列化私有片段；原输入普通等值比较漏过同值类型突变。根已补强，历史源码c78c4922和失败探针保留，不能把初步77通过当最终保护证明。

最终独立审查限定通过，48项新建私人合成探针全部通过，确认未降低保护且无剩余阻断。证据存入 `independent/`，含初步漏洞的2failed原始日志及冻结源码导出；文件按审查manifest逐项核验复制。

独审manifest SHA256：`45e7852259ff4ed00c6af46a2e8815caf9fe588610f6b197d04f37f3053aa277`。根manifest记录控制/扩大日志、JUnit及验证摘要；初步控制按各自源码SHA标注，最终结果不混用旧版本。

根在最终独审通过后，实际执行原三个文件的扩大范围：`tests/test_history_registration_contract.py`150、`tests/test_history_summary.py`46、`tests/test_fact_history_read_source.py`143，共339通过、0失败/错误/跳过。原251项范围增加87项oracle控制及1项独立输入检查。原始结果见 `root/expanded.log`、`root/expanded.xml`，运行次序与范围见 `root/verification.json`。既有Starlette/httpx弃用警告保留，依赖未变。

两个历史扩大失败保持在父证据 `../history-registration-contract/root/final.log` 和 `../history-registration-contract/root/verified.log`，各250通过/1失败；其摘要记录在根verification中，原字节未变。旧失败后的输入不变断言没有执行，不能用这次结果倒签旧运行。独审历史失败日志保留pytest尾随空白，未为格式检查改动证据字节；测试、Markdown、JSON格式检查通过。

仅测试/必要证据候选提交，不改变生产授权、registry、loader、凭据或OS权限。不使用真实PG、模型、浏览器或网络listener。原浏览器 `data: ERR_BLOCKED_BY_ADMINISTRATOR` 继续暂停。真实独立当前代际、维护隔离、持久登记和完整退出恢复仍未验收，测试数量不能替代可信安装锚。本组完成后收束。
