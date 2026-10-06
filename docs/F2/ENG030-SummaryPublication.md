# ENG030 本地安全诊断的独立发布

基线c6c40ef571e7e5723197fb6ff5df151633eb1980。新指示暂停F2分派并优先验证诊断通路；F2只进行了原设计/既有权限合同审查，没有新增业务代码可丢失。此轮只本地测试/commit，不push、重跑Windows、导出或LIVE。父线程已告诉用户暂不用再翻截图。

## 能证实和不能证实的事实

实际run37417713362仍FAIL：Prepare/owned PG StopPASS，native_suite623.032秒exit1、外层timeoutFalse。用户截图显示Engineering.ps1:21的wrapper throw，没有新安全JSON；它不能证明JobSummary不存在，也不能证明内部regression超时。具体case/counts/category和根因仍UNKNOWN。

源码数据路径：native_command.py对native_suite使用env=None，确实继承GITHUB_STEP_SUMMARY；把全部stdout/stderr写私有普通文件。Test无Capture，Invoke-Checked非0先throw；即便加Capture，也仅成功退出才捕获、非0先throw，不能修通。native_suite在末尾持久化report、stdout及StepSummary；现有workflow只有Stop always，没有独立读报告发布。实际本地子进程控制证明，wrapper退出1且stdout未透传时，套件仍可直接写StepSummary；不把截图或REST check summary/text为空当“未写”证据。

## 最小修复

在Test后Stop前增加if:always()独立publisher：纯stdlib，只读取明确RunnerTemp直接子parkweave-server-ci-UUID/engineering.json，不读任何private stdout/stderr，不跑PG或外部请求。验证格式schema1、本次run/attempt/SHA/cluster UUID绑定，严格UTF8与JSON重复字段/非有限值拒绝、canonical路径及symlink/junction/reparse拒绝，再从固定case/status/phase/category/reason、测试ID/counts/清理类别重建输出。原Test/Stop代码、退出码、900/600秒上限、权限、角色、环境白名单、SQL及应用功能未改。现有Stop仍always，即便publisher失败也不跳过。

公开最多64KiB、32行、25个预批准test ID、6个清理类别；数值0—10000，未知phase/category只UNKNOWN/OTHER，未知测试名字不输出。绑定/env/路径、原始异常、traceback、材料和任意额外键均不发布。报告missing/invalid/unreadable只输出SUMMARY_MISSING/INVALID/UNREADABLE及空cases；缺计数或诊断字段给固定MISSING/INVALID，绝不猜原因。发布器自己的失败只增加该步骤失败，不改变原Test结果或清理。

报告持久化与两个公开出口分别尝试，一边失败不会阻止另一边；所有错误出口固定处理。套件保存原子IN_PROGRESS阶段检查点和COMPLETED报告，API/restart/native_browser等入口及时更新阶段。若中途被终止，publisher只展示最后实际记录的阶段与已观察行，不把部分记录称完整结果。browser内部只在真实异常时使用原细分phase；外层中断checkpoint仅标native_browser。

## 本地验证与限制

最终定向130PASS/0FAIL/1既有WARN（2.26s），真实本地NativeCommand子进程覆盖exit1、直接子进程timeout124、报告missing和清理失败，随后独立CLI发布；原exit及cleanup值保持。恶意字段、错误版本/本次绑定、大小/行数/ID数、UTF16、深JSON、重复键/NaN、链接/循环、不可读及两个公开出口故障均有回归；CLI stderr为空。初轮3FAIL/123PASS是测试fixture用monkeypatch替换Python环境映射未更新C环境，改patch.dict真实环境后通过，不认定为CI缺陷。

同工作区只读审查修复异常出口与阶段快照一致性后通过，审查者未运行测试。静态13份PowerShell AST、4个Linux拒绝守卫与YAML政策PASS，不能替代Windows。最终129份源码及工作流冻结源全量681PASS/0FAIL/1WindowsSKIP/2既有WARN（178.67s）、exit0，运行后129/129哈希保持；结果见[evidence](evidence/eng030-summary-publication.json)。下面公开样例是真实函数处理本地合成输入所得，非实际Windows失败诊断。

## F2合同安全保存点

F2-T04原方案允许专员有原因调整责任方；现有run_assignment是访问授权，不是业务派单。已只读列出建议与分歧：当前获派资料专员在现有READ/REVIEW_ASSIGNED范围分派给同tenant已有Run访问的执行者；拒绝后重派，接受后锁定并接现有receipt，旧receipt兼容且新流程不可旁路。权限映射/接受后转派/陈旧offer拒绝与撤回语义待父线程确认；没有实施、赋权、通知或外部履约。原方案/安全边界保持，F1/F2未签收、R4关闭、真实模型预算0、Win11/36AT6EX NOT_RUN。

```json
{
  "sample_kind": "SYNTHETIC_FUNCTION_OUTPUT_NOT_ACTUAL_WINDOWS_CI",
  "samples": {
    "synthetic_failure_and_cleanup": {
      "scope": "WINDOWS_SERVER_ENGINEERING_NOT_WIN11",
      "publication_state": "SUMMARY_AVAILABLE",
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
          "phase": "native_browser",
          "category": "TimeoutExpired",
          "owned_browser_cleanup_failures": [
            "PermissionError"
          ],
          "cleanup_failures_count": 1,
          "cleanup_categories_truncated": false
        }
      ],
      "real_model_calls": 0,
      "real_budget": 0,
      "production_R4": "DISABLED",
      "whole_AT_EX": "NOT_RUN",
      "Win11": "NOT_RUN",
      "report_state": "COMPLETED",
      "active_phase": "UNKNOWN"
    },
    "synthetic_interrupted_checkpoint": {
      "scope": "WINDOWS_SERVER_ENGINEERING_NOT_WIN11",
      "publication_state": "SUMMARY_AVAILABLE",
      "cases": [],
      "real_model_calls": 0,
      "real_budget": 0,
      "production_R4": "DISABLED",
      "whole_AT_EX": "NOT_RUN",
      "Win11": "NOT_RUN",
      "report_state": "IN_PROGRESS",
      "active_phase": "regression_run"
    },
    "missing_report": {
      "scope": "WINDOWS_SERVER_ENGINEERING_NOT_WIN11",
      "publication_state": "SUMMARY_MISSING",
      "cases": [],
      "real_model_calls": 0,
      "real_budget": 0,
      "production_R4": "DISABLED",
      "whole_AT_EX": "NOT_RUN",
      "Win11": "NOT_RUN"
    },
    "invalid_report": {
      "scope": "WINDOWS_SERVER_ENGINEERING_NOT_WIN11",
      "publication_state": "SUMMARY_INVALID",
      "cases": [],
      "real_model_calls": 0,
      "real_budget": 0,
      "production_R4": "DISABLED",
      "whole_AT_EX": "NOT_RUN",
      "Win11": "NOT_RUN"
    }
  }
}
```
