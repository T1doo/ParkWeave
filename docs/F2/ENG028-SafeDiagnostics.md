# ENG028 本地安全诊断与确定性UTF-8读取

基线aae63a5018fa1ce49e3519b5c2eea5df690fdf4d。仅本地提交、待父线程核对SHA及样例后决定push/新CI；未改workflow、系统码页、代理、身份、权限守卫、环境白名单或数据库SQL字节。真实模型/预算0。

## 修改与公开输出边界

native_suite从本次唯一报告及私有JUnit提取固定名单test ID，参数后缀、异常消息、traceback、stdout/stderr、环境、会话、材料及私有路径不公开。只允许固定phase/category/状态及有界counts；未知test只计数不输出名称。最多25个ID，最多10000个testcase、4MiB XML、512KiB report、6个清理类别；截断和不可用使用固定状态标记。XML只接受UTF-8文本，拒绝NUL、DTD/entity、非UTF8声明、路径穿越和链接。名单是仓库312个固定函数ID，测试核对与AST严格一致；名单更新不会自动接受来自JUnit的名称。

原子进程exit1继续FAIL；报告解析失败追加固定regression_report FAIL，不替换原退出行。missing/invalid/oversize/allowlist不可用不伪造test ID。配置初始化及生命周期/浏览器异常加固定阶段；原清理异常仍保留，不把主异常吞掉。Linux守卫仍在任何suite写入前拒绝。

规格/绑定JSON、web.html、schema/migration/roles SQL、报告JSON读写明确UTF-8。SQL与HTML内容未变；进程环境白名单未加入PYTHONUTF8/PYTHONIOENCODING。自包含控制只定点恢复原隐式read_text，用CP1252默认Path.open模拟，不依赖Git历史、不改系统locale。实际HTTP请求比较控制500与修复200/UTF-8 charset/完整HTML原字节；这是条件性缺陷验证，不是实际Windows码页或CI根因证据。

## 本地验证

定向99PASS/0FAIL/1既有WARN（2.53s），包含XML编码/实体/路径/大小、名单不可用、未知与超长字段、截断、报告类型/大小、输出不泄漏、原exit1保留及实际中文HTTP。独立同环境只读审查修复浅克隆旧对象依赖与UTF16扫描绕过两阻塞后通过；审查者没有运行测试。

最终冻结125个源文件含诊断manifest；全量644PASS/0FAIL/1WindowsSKIP/2既有WARN（176.05s），exit0，运行后125/125哈希保持。静态13份PowerShell AST、4个Linux拒绝守卫、YAML策略PASS，均不是Windows原生运行。详细结果由[evidence](evidence/eng028-safe-diagnostics.json)记录。此前失败测试日志保留在本地私有.runtime，最终成绩只取最终冻结源。下面样例与JSON均标为模拟，不代表Windows CI实际失败项。

## 待确认的原生结果

最近真实Server run37414981257（1baa2cf）仍completed/failure：PreparePASS、native_suite79.235秒exit1/no timeout、owned cluster StopPASS。FAIL/NOT_RUN cases、回归counts、实际码页及根因UNKNOWN；不读取被拒日志、不以本地控制推断。Server不是Win11。F1/F2未签收、R4关闭、36AT/6EX NOT_RUN，无自动资格或外部履约。

公开样例（模拟，非真实CI case）：

```json
{
  "sample_kind": "SYNTHETIC_SHAPE_NOT_ACTUAL_CI_CASE",
  "cases": [
    {
      "case": "full_engineering_regression",
      "status": "FAIL",
      "exit_code": 1,
      "counts": {
        "PASS": 0,
        "FAIL": 1,
        "SKIP": 0
      },
      "whole_AT_EX": "NOT_RUN",
      "failure_diagnostics": {
        "state": "AVAILABLE",
        "failed_test_ids": [
          "tests/test_lifecycle.py::test_config_write_is_exclusive_and_no_secret_fields"
        ],
        "test_cases_seen": 1,
        "failed_cases": 1,
        "unknown_failed_cases": 0,
        "ids_truncated": false
      }
    },
    {
      "case": "lifecycle_exception",
      "status": "FAIL",
      "phase": "browser_driver_binding",
      "category": "RuntimeError"
    },
    {
      "case": "full_engineering_regression",
      "status": "FAIL",
      "exit_code": 1,
      "failure_diagnostics": {
        "state": "REPORT_MISSING",
        "failed_test_ids": []
      }
    }
  ]
}
```
