# 已取消旧Case → 全新输入的独立新Case

冻结源码 `78022b3c30d8d66404cbb165a660ff484bdcf31e`；接续交付 `57c19eeeb059c36f6a066332752a545b27706222`，开发分支 `dev/f3-cancelled-case-new-request-20261016`。只增加原页面的明确导航，不增加后端、迁移、克隆、恢复或自动继续接口。

## 用户流程及原方案依据

原方案§7.4规定取消保留已发生事实、资源释放独立受权；新输入产生独立Case且不复制旧资料/授权。现有ParkInstanceConsumer五阶段冷输入、服务选择GENERATE/ADOPT、原审批、容量、接单及P1–P5完整链已经存在，本片复用。

已实际接单且尚无首次回执的旧Case，经当前owner原明确取消与原key核对结束后，页面显示“用新输入另建独立事项”。预览明确旧Case保持CANCELLED、原历史/接单责任/资源占用保留；用户再次确认后仅GET重验原取消范围、owner/Case/版本/来源和当前上下文，再导航原新输入入口并清空输入，不发送创建/释放命令，也不携带旧方案、审批、材料或资源。任何原未知句柄、未结束操作、陈旧上下文或403仍保留原守卫。原cold provider未开启或新建权限不足时仍拒绝；旧Case的READ不授予新Case创建权限。

新事项由用户重读当前配置、填写全新诉求/两槽材料/六目标，逐阶段独立确认原请求。产生不同Run、Case、preparation、plan、approval、组合、接单及回执ID；随后仍须原明确采用、审批、容量重验、接单与履约。此片服务definition没有升级，不声称同一已接单Case的来源版本迁移。

旧CONFIRMED占位继续占容量；旧组合因Case claim不能给新Case复用。测试在同窗申请quantity2且已有quantity1/capacity2时实际409；经原资源权限独立明确取消旧bundle后，再创建新hold、新组合并重验，才可交付。释放权限撤回或他企业操作403；取消Case本身不释放资源。剩余可用容量仍遵守原计算，不宣称所有同资源新预订都必须先释放。

## 实际验证与时间边界

| 完整模块窗口 | 唯一通过项 | 原件 |
|---|---:|---|
| 原取消/前沿客户端、原完整cold HTML及新导航五模块 | 161 | [JUnit](evidence/cancelled-case-independent-input-20261016/new-case-root/client-development-2.xml) |
| 原cold完整HTML→ASGI→自有PG模块 | 7 | [JUnit](evidence/cancelled-case-independent-input-20261016/new-case-root/old-cold-actual-v2.xml) |
| 新独立Case原链及两项资源释放授权拒绝 | 3 | [JUnit](evidence/cancelled-case-independent-input-20261016/new-case-root/chain-development-2.xml) |
| 冻结HEAD实际安装Chromium同页用户流程 | 1 | [JUnit](evidence/cancelled-case-independent-input-20261016/new-case-root/frozen-browser.xml) |

**8个完整直接相关模块，172唯一项PASS，0FAIL/ERROR/SKIP**。独立冻结2模块28项（PG/ASGI3、纯HTML25）全部通过，与主集合重叠不加分；独审4个Node模式也不追加。693个tracked src/tests/scripts/pyproject输入逐字节核对，后端Python/SQL与57交付版一致。[冻结清单](evidence/cancelled-case-independent-input-20261016/new-case-root/freeze.json)、[最终门](evidence/cancelled-case-independent-input-20261016/new-case-root/final-gate.json)、[冻结独审](evidence/cancelled-case-independent-input-20261016/new-case-review/frozen-review.md)、[独测](evidence/cancelled-case-independent-input-20261016/new-case-oracle/frozen-v1/outcome.json)。主早期窗口使用与最终冻结版相同源码字节，独测28及最后Chromium1实际运行冻结HEAD；不重签较早执行的Git时点。

Chromium实际操作为：原reason+checkbox取消旧Case→GET核对且原key/entry lease结束→新导航确认→全新输入、六目标、原五stage逐项prepare/send→明确GENERATE→未勾原采用确认时点击ADOPT仍无POST且plan为空→勾选后明确ADOPT。浏览器验证到新计划，不称全履约都在浏览器完成。原worker、独立新Run executor assignment、资料REVIEW/CONFIRM由Python原命令/明确夹具设置完成；ASGI全链另用原issued证明配置覆盖原/新preparation的IsolatedPlanApproval审批桥，独立业务批准仍经原PROPOSE/APPROVE。均不是新产品赋权或全程仅端用户操作。规划使用既有离线替身，真实模型调用0。

完整ASGI组合场景另走独立新Approval、实际容量拒绝、独立受权释放、新hold/组合交付、P1–P5业务与VERIFY、真实ACCEPT、manual SUBMIT/ACK、原本地重核关闭，最后读取六目标及工作清单。旧Case全过程保持CANCELLED、原历史/责任不变，唯一允许变化是独立释放原占位；不借旧approval/receipt或复活旧占用。本地记录仍不代表真实线下履约、机构受理或原诉求整体完成。

## 统计更正、失败保全与剩余范围

先行更正提交 `f635d806659265899616396ffb9a047d2a600af3`：57交付批次“旧99模块全未执行”过宽；旧集合中before_receipt107、reconciliation141已经完整执行，故该批实际剩97模块/原基线2407节点。其335早期PG证据只适用于后端，最终web由133客户端和5浏览器接续覆盖，原封存证据不改签。

本批再完整补跑原cold模块7项后，**当前剩96模块/原基线2400节点未重跑**。上批508和本批172不相加宣称全仓通过；独测窗口自身仅执行两个新模块，其“旧97未在该窗口执行”的原记录不能替代根的本批汇总。[逐模块更正依据](evidence/cancelled-case-independent-input-20261016/new-case-review/remaining-module-correction.json)及最终门保留完整名单。

开发失败原件全部保留：首次Git认证失败仅有观察副本，随后一次有界只读复查恢复；新Run分工安排在ADOPT后导致原P3 gate拒绝，移至采纳前的明确夹具准备后重跑；旧NodeVM缺标准classList补DOM语义后整模块重跑；浏览器响应观测、用户实际目标顺序、原ADOPT按钮可用性断言等测试错误均保留。未放宽产品门、容量、权限、原确认或预算。进程已结束时的停止探测无匹配而拒绝，未发送信号。[失败原件hash账本](evidence/cancelled-case-independent-input-20261016/new-case-root/failure-ledger.json)、[本轮primary封印](evidence/cancelled-case-independent-input-20261016/new-case-delivery/public-primary-seals.json)、[旧封印复核](evidence/cancelled-case-independent-input-20261016/new-case-delivery/previous-seals-verification.json)。私有登记、完整失败原件及数据库仅本地保留，公档为有界文本证据及原件hash，按完整登记值处理合成令牌。归档复核见[独立审计](evidence/cancelled-case-independent-input-20261016-audit/final-audit.json)。

Windows及其浏览器、广覆盖浏览器、正式AT、真实模型、生产、跨进程恢复及CI均NOT_RUN；未验证服务definition升级、同Case已接单迁移或更广已有P4/P5效果的继续合同。下一关键路径仍是原方案内已接单来源变更的明确收束/独立重批/继续履约与回执后核对，F5恢复及正式AT前提另列。main只读，无强推、部署、新费用、凭据、安全权限或绕访问拒绝。
