# 两份新输入的同一 Case 最小业务链

接续有限接收的 `996afdbd055f7428e16183c6a393adce22342b9a`。冻结源码 **fa755b5f514e8087d690613bc91ca0f5c3fe1274**。完整原页面实测每份仅从prep-create生成一个Run和Case；没有前演示Run，也没有将不同Case拼成同一生命周期。

两份全新诉求、摘要和目录各自走通：材料提交→专员要求补件→企业补交→原专员审核→企业确认→精确Run访问申请/独立审批→专员分派→执行者本人接单→人工合成回执→企业核验→两个原资源占位及组合确认→关联当前Case→显式重新校验→本地关闭→重开。两个不同Case均到第2轮，关闭时Case仍WAITING_CONFIRMATION、目标未完成；原资源保持占用。

首次材料POST已在真实PG提交后丢响应。原页面只用原key GET及当前资料历史核对，再明确结束恢复；没有重发ADD_EVIDENCE。实测发现原同页UNKNOWN只保留重试入口，未hydrate已有持久句柄，GET恢复也被内存pending挡住。最小修复仅接通原句柄；live pending须UNKNOWN、原key/身份/事项/动作/版本一致且原事件COMMITTED并精确在当前历史中，才清内存pending。NOT_OBSERVED和异常证明不解除live pending；句柄仍由原明确结束按钮处理。

测试使用完整原HTML handlers和真实owned PG/进程内ASGI，不手工写业务库、assign_status、pending或替换业务入口。原页面DOM、存储及定时器为替身，HTTP全部接真实API；使用既有合成身份。访问流程复用现有IsolatedRunAccessBridge及已签发的临时库证明、临时SQLite审批日志和PG受管理投影，只有该owned临时库使用原managed_access列初始化；没有新principal、Grant或native registry，权限快照前后相同。这不是ordinary默认访问启用或生产授权；不使用其不支持的native原key恢复。

原页面整链 **103断言、277次HTTP请求、44次POST**（其中4次资源纯预检，不全称业务写），包括两份新输入及一次丢响应。后置只读PG核验回执绑定同一Case/Run/资料、每份2次材料追加事件与3次本地生命周期事件、原组合和4条资源占位仍CONFIRMED。现有claim/finish仅推进原合成Run worker，不调用模型。

最终唯一回归计数、独审分窗及原件见 [results.json](evidence/full-owned-lifecycle-20261013/results.json)。原FAIL/ERROR未覆盖；fixture导入/命名、DOM缺失、测试字段/SQL错误及读取桥缓冲超时与真实同页恢复产品缺口逐一分列于failure-qualifications.json，不把脚手架失败伪称产品缺陷或把阶段PASS加总。含识别到的fixture会话repr原失败日志/XML只公开显式脱敏导出，私有原件hash/字节及原结果保留。

两安全approval仍false/null/null；浏览器、安全探针、Windows、AT08/35及现实履约均NOT RUN/未签收，不部署、不迁移生产、不改保护分支。下一步为父级复核这个完整最小合成本地业务链；DOM替身不等于浏览器验收。

最终唯一相关回归 **558 PASS / 0 FAIL / 0 ERROR / 0 SKIP / 2 WARN，183.90秒**，整链作为1项包含其中，不再加总103内部断言或两份输入。独审完整owned PG窗口1PASS/2WARN、103页面断言与恢复负例8模式/153断言同一冻结hash，分窗展示；负例初始补充GET故意500，不冒称健康完整冷链。

源码diff检查PASS；初次归档暂存diff检查实际FAIL/rc2，48处原失败输出尾空白保留，原检查输出也归档，不裁剪。根18份及独审4份fixture repr导出均显式标记，私有原件保留。归档助手/检查器失败均留原件，不能作为产品测试结果。
最终暂存检查仍FAIL/rc2，共96处（48原输出加48原检查回显）；最终检查留runtime，避免递归归档。
