# ENG042 单次标准诊断CI终态及有据后续范围

用户授权普通推送ENG041并仅运行一次既有标准Windows CI。实时远端cc4d7ba5d711c8da50908f23edcc9cd877d5a3cc为本地98012592da107a26c1aa9a06b9b29a1f7a595874祖先，远端独有0/本地1，工作树干净、10份最终诊断hash一致。普通push与ls-remote精确验证成功，无冲突、force或reset。

唯一标准[run37444794329](https://github.com/T1doo/ParkWeave/actions/runs/37444794329)，attempt1，head9801259；job/check112206907402。正常API最终确认completed/failure及同head唯一run，未dispatch/rerun。原生PG/Python准备成功，native_suite exit1、timed_out=False、684.516s；独立发布器与owned临时PG停止步骤success。原600s/900s、工作流、runner、权限及环境过滤未改。

## 实际原因码与阶段

| 实际harness项 | 正常API白名单字段 |
|---|---|
| Doctor_native | FAIL、exit1、BoundaryError、private_acl、ACL_REFUSED |
| Start_native | FAIL、exit1、BoundaryError、private_acl、ACL_REFUSED |
| API_browser_restart | NOT_RUN、START_FAILED |
| full_engineering_regression | FAIL、regression_run、TimeoutExpired、counts_state=MISSING、regression_phase=pytest_call |

新字段真实送达：5条notice、最大223/总978 UTF8字节含LF、0测试ID，字段与数量/字节/ID白名单均核验。头部report_state=COMPLETED、active_phase=UNKNOWN、harness5PASS/3FAIL/1NOT_RUN、零case省略。它们不是pytest成绩或AT签收；没有具体测试ID、最终JUnit数量或某测试死锁证据。

Start同head代码在配置/Python/应用DSN角色/进程记录/端口检查后才检查私有根，成功检查后才创建API/worker。其实际private_acl/ACL_REFUSED因此定位到服务创建前的ACL检查子进程非零。Doctor也被同一检查拒绝。不能把该码解释为缺依赖、DB连接失败或已知子进程退出原因，不能追溯断言旧CI相同根因。

ACL_REFUSED目前合并所有非零分支：exit2为受检对象owner不等于当前SID；exit3为非白名单Allow主体；exit4为root未保护继承；其他可能为PowerShell执行或身份转换错误。本次没有这些子返回码，**具体违规条件仍UNKNOWN**，不把“新文件默认owner可能不符”当作已证明事实。

完整回归为内部600s对子run_acceptance的等待超时，外层900s没有超时。pytest_call仅是读取时最后成功记录的阶段，不能保证超时瞬间仍在该阶段、具体测试或挂住与正常累计耗时；它也不能证明ACL拒绝造成回归超时。

清理：pg_status exit0/无超时/0.031s，pg_stop exit0/无超时/0.234s，workflow owned PG Stop success。native_suite cleanup=NOT_NEEDED仅指外层未需超时回收；app final_Stop未单列，不据缺行填PASS，不以PG停止证明所有测试后代退出。

## 后续有据修复范围（本轮未实施）

1. **ACL检查/初始化**：Setup先保护并检查root，之后才创建sessions/config；Doctor将这些新文件加入检查，故Setup成功不证明新文件owner/ACL满足后续严格合同。优先核对这两条受控创建路径和现有检查实现，按已证明的owner、Allow、继承或PowerShell分支分别修复。保留当前SID owner及允许主体要求，不放宽检查，不重写既有用户ACL，不凭当前合并码实施权限变更。当前证据尚不足以安全选择哪一种原生修复。
2. **回归等待**：只审计并复现已有具体调用路径的SQL等待、线程池退出或自有子进程生命周期；取得具体触发证据后修该路径。当前pytest_call无ID/最终计数，不能选定某业务测试修复。保持600s，不新增泛化诊断层或靠提高期限掩盖问题。
3. **独立待修项 OWNED_REGRESSION_DESCENDANTS：OPEN**。本地SYNTHETIC实验已证明直接父超时后自有后代仍活；当前探针随后受限终止/回收。产品回收尚未修，后续只处理本次受控启动且身份绑定的测试后代，保留无关进程及PG独立Stop。Linux实验subreaper不是Windows修复；不把这个已知本地生命周期问题当成本次Windows超时原因。

两位独立只读复核确认上述证据限制和拆分，未修改源码/ACL/权限或读取网络日志。完整正常API证据见[evidence](evidence/eng042-single-diagnostic-ci.json)。本轮没有新修复代码，没有额外运行或日志/artifact下载；终态记录仅本地保存，未再push。

原环境、备份及先前证据保留；0真实模型调用/预算，R4关闭，F1/F2未签收、Server不是Win11、36AT6EX NOT_RUN。此CI结果只对应9801259源码，后续本地结果文档提交不声称经过该CI。
