# 两件新事项同用途材料复用普通页面链

基线 `6f8167a3e435b6fc198e757f8968c6c56ac27411`，分支 `dev/f2-material-reuse-dom-20261018`。原产品方案 §5.1 要求同企业、同用途的授权材料复用，并保留不同诉求；F2-T01／AT35 的再次使用不能靠预建两件业务事项代替完整入口。本片复用 ENG100 现有实现，不新增算法、provider、批准或跨企业模板。普通页面实跑发现仅复制材料目录而无本次摘要／核对时企业确认按钮仍启用；按原状态机将其限制为当前 owner、REVIEWED 且非 pending。后端原状态／版本／来源校验、恢复与异议安全门保留。实际结果以单独验证报告为准，本合同不预认通过。

两个 viewport（1200／320）的同一完整路径，从零 Run／Case／preparation／材料／assignment 开始。安装身份、Grant、目录、资源明确为启动前 SYNTHETIC fixture，不作为真实授权证明。独立普通 configured_app 和 LOCAL worker 经原页面创建来源事项，提交独立诉求、两份材料，专员 REVIEW、企业 CONFIRM。再经原页面创建同主体同服务的第二事项，通过原来源预览、精确版本／SHA、用途勾选、说明及复制控件，生成新的未核验材料目录。

目标事项仍需本次新诉求摘要、独立 request intent、专员重新 REVIEW 与企业 CONFIRM，不能继承来源核对、确认、目标或权限。下载原资料包并核实际字节。来源随后经原 REOPEN／ADD／REVIEW／CONFIRM 改为 v2；目标保留 v1 副本与原来源历史，显示来源后来更新，包字节不变。两件 Case／Run 不合并。停止首 API／worker／浏览器后，新普通 API 和两个新角色上下文经原列表仅 GET 冷读，下载同一资料包，完整 Case 历史及权限快照不变。

page.evaluate 仅观察当前页面对象／布局；无 JS 业务写入或导航、业务 API 初态、运行时 assignment／Grant、运输注入或原算法重做。记录发送请求和已收到 POST 回应为不同集合，不将回应数等同所有请求数。原连接 2 秒、DROP 5000ms、ordinary 启动循环 15 秒及 health HTTP 15 秒预算、owned diagnostics 和原失败全部保留；不自动重跑或为成绩全量刷数。

仅验证 SYNTHETIC／LOCAL／Linux PG／Chromium。本片不是正式 AT35，也不是新企业模板 AT08。真实模型、正式来源／批准／业务、Windows11 原生与正式 AT 均未验。普通运行仍需已有合法会话、READ／EXECUTE、case.create 动作权限、PREPARE／REVIEW_ASSIGNED、精确 preparation_catalog、原业务记录；执行者路径另需原精确 Run assignment，缺失准确拒绝。正式五证明、主体映射／专用采纳适配仍受 [来源合同缺项](ReceiptSubmitRecovery-20261018.md) 限制；NativeRunAccess permit／writer 默认拒绝，IsolatedPlanApproval 不进入普通批准。

父级指出既有 SUBMIT overlap 两分支都旧回复先到、80ms 不证明 settled，尚未覆盖“新回复先完成、旧 200／403 最后到”。本片已开始完整独立价值流程，先完成此片；不顺带扩充回执／防重范围，不将本片通过写成该并发缺口已修。先前连接／清理／启动失败底因仍 UNKNOWN，后来 PASS 不解释原失败。
