# 普通合成演示：原页面新诉求与两槽新材料

排重后确认，已准入的 `897fc6949412d41304200cdfa42f121649dd6f95` 已有等价普通页面入口。本片没有另建设置向导、产品页或 API，也没有移植 schema33 隔离 consumer。新增实际 DOM 回归，证明用户可从空白业务记录，经原页面建立新事项、提交新材料并进入 `LOCAL_SYNTHETIC_DEMO` 选择。

测试冻结提交：`9c50ff798fd4c6a78f1756aba75cffac2a8d137a`。相对基础只新增 `tests/test_demo_original_page_intake_browser.py`。两端 `src` Git tree 均为 `6baf7d8442a244e6f213410e76201cffbb120e64`，产品代码逐字不变。交付分支为 `dev/f2-demo-original-page-intake-20261017`，交付说明及证据另提交；实际完整交付 SHA 与远端差异以最终回执为准。

## 原入口如何接续

| 原页面操作 | 复用的原行为 |
| --- | --- |
| 服务 → 查看可选服务与专员 → 开始资料准备 | `#prep-catalog`、`#prep-create` 读取已有目录/专员；POST Run，等待独立普通 worker 完成，再创建 preparation。单独旧 `#intake` 只建 Run，不能替代此完整入口。 |
| 查看此事项四步计划 → 保存诉求与必需目标 | `#plan-prepare`、`#request-intent-form` 保存原 request-intent；没有启用旧固定四步模板。六个目标由原多行输入框明确填写。 |
| 原计划的资料入口 → 逐槽追加材料版本 | `#plan-materials` 回到当前资料；用 `#prep-evidence` 分别提交新 need_summary/material_outline、自述来源及版本，经原 ADD_EVIDENCE 与精确事件读回。 |
| 专员协同列表打开事项 → REVIEW；企业刷新 → CONFIRM | 两个独立浏览器 context 使用安装初态中的不同合法会话，复用原目录、角色、版本、当前来源与授权门。 |
| 查看此 Case 持久步骤计划 → 读取服务能力 → 生成合成候选 → 明确确认采用 | `#service-plan-prepare` 和原选择面板读取当前配置角色/资源；原唯一解算法生成 NO_MODEL 候选，勾选确认后原 ADOPT，不自动执行或创建权限。 |

上述控件及处理函数都已在基础 `src/parkweave/web.html` 中存在。测试没有使用 fetch、requestSubmit、JS 应用导航、清句柄或改全局来完成业务；evaluate/wait 只观察状态、实际读取完成、注入未执行及页面宽度。原忙时门和未知操作恢复门保持原样。

## 本轮实际验证

冻结后两个完整浏览器模块 **3 唯一 PASS，0 FAIL / ERROR / SKIP**：新 DOM 路径的 1200/320 两例，以及既有普通选择/显式采用/重启浏览器一例。736 项源码、测试、脚本与原合同哈希前后零漂移，测试窗口 worktree 净。以 [最终结果](evidence/demo-original-page-intake-20261017/runtime/final-result.json)、[JUnit](evidence/demo-original-page-intake-20261017/runtime/final-pytest.xml) 与 [调用范围](evidence/demo-original-page-intake-20261017/runtime/final-invocation.json) 为准。基础 317 例是此前已准入成绩，没有再次运行或累加进本轮。

每个新例使用实际 Chromium、独立 uvicorn `parkweave.api:configured_app --factory` 进程及独立 `python -B -m parkweave.worker` 普通 LOCAL worker；重启时另建 factory 和新浏览器页面。安装初态仅为原显式隔离合成身份、目录、Grant、资源和精确配置包/journal。普通启动前断言 runs/cases/preparations/evidence/events/run_assignments 全空；没有 API 预建初始业务或材料，没有测试 finish/claim 替代普通 worker。

新 Run、preparation、六目标、两槽正文、REVIEW、CONFIRM、选择及显式采用，随后原资源预检/占位/组合确认/Case 关联与 P1/P2 VERIFY，全部由 DOM 提交。核对实际原事件顺序 CREATE → UPDATE_REQUEST → ADD_EVIDENCE ×2 → REVIEW → CONFIRM、两槽完整正文和精确映射专员；脚本文本只作为材料展示，未执行。源端为 SYNTHETIC，生产元数据为 NO_MODEL。

新 Run **没有 executor assignment**，原专员页显示“此 Run 当前没有可分派的既有合法执行者”，隐藏 offer 表单；数据库仍无该 Run assignment、无 dispatch offer，七项原身份/授权表快照与初态一致。本轮只证明这条 UI 阻断及无写入，没有冒称新测了直接 POST 的 403。新页只完成 P1/P2，六目标整体仍未完成，P3–P5 没有办理。此前另一个 API 全链测试在加载器外添加精确测试 assignment 的事实仍单列，不能迁入本页成绩。

重启后从原协同列表和页面按钮只 GET 读取，同一结果、Case 历史和授权快照不变。`business_POSTs` 是收到响应的 POST 清单，不是丢回复场景的完整网络审计。未新测 lost reply、撤权或并发竞态；既有浏览器负例仍在原模块。

独立只读审查固定提交和测试 blob，0 阻断，见 [独审范围](evidence/demo-original-page-intake-20261017/runtime/independent-review.json)。随后在等字节自有 `/tmp` 镜像独立重跑 width320，一例 PASS（57.57 秒），735 项镜像输入与共享源码/新测试前后零漂移，0 新阻断；见 [单列结果](evidence/demo-original-page-intake-20261017/runtime/independent-runtime-summary.json)。此为同一测试断言的重叠执行，不加根 3 唯一用例。17 个收到响应的 POST 含两条只读资源预检，其余 15 条写入均为 2xx。

## 失败保全及范围限制

开发 v1–v8 各一例失败，v9 两例通过，均不累加最终成绩。v1 是表单内多按钮导致 locator 不唯一；v2 未等原写入核对结束便读计划。v3/v6 材料已保存且事件 verified，但仍留原安全请求记录；v4/v5 点材料提交后未发 POST；v7 CONFIRM 已保存但同样留记录。独审发现辅助取消读取 busy 可截住提交，迟到读错误也可能把当前 flow 标为失败；这些是与观测相容的静态原因，**未捕获首次置位错误，不能声称每次具体根因均已证实**。测试后来等待原辅助 readchain 同 revision、busy 清空及原 flow 结束；没有放宽或清除安全门。v8 已完成 P2，最后结果读取却未等新步骤计划读回，v9补上观察等待。

每轮完整 pytest stdout/XML、原测试版本和输入清单均保留；可取得的 v7/v8/v9 临时诊断、子进程日志和截图也已保全。更早 `/tmp/pytest-of-agent` 目录在归档前已由 pytest 自有保留策略清理，不能把先前工具输出观察称为仍存的 raw 诊断文件。没有打包 PG 数据或会话凭据；公开副本对临时会话候选脱敏并记录 raw/public 哈希，原件留在私有 `.runtime/demo-original-page-intake`。这不是“忙时任意快速点击无拒绝”或零准备一键办理的验收。

归档工具首版还遮住 22 项稳定文件/分支名，已保留私有首版，并仅对已知 tracked 路径与原远端 ref 作排除；最终实际临时会话脱敏 3 处。首个归档校验因仓库 Python 无 PIL 未执行，保留该失败，未安装依赖；改用标准库校验 JSON/XML、PNG 各 chunk CRC、解压及像素字节数。原始证据的空白不修剪，完整 diff-check 告警单列，正文及冻结测试检查通过。

公开 [manifest](evidence/demo-original-page-intake-20261017/manifest.json) 共 127 对 raw/public 映射，逐项复核哈希；53 JSON、11 XML、12 PNG 均通过结构检查，见 [归档校验](evidence/demo-original-page-intake-20261017/validation.json)。继承的 28935 个 F2 证据 Git blob 无覆盖或漂移。完整暂存 diff-check 的 44 处空白告警全在原失败日志/XML；正文及测试通过，见 [交付检查](evidence/demo-original-page-intake-20261017/delivery-checks.json)。两个衍生校验 metadata 位于映射之外，避免递归归档。

## 普通运行仍缺什么

1. 已授权应用 DSN、预安装普通 schema32，以及正确 park/org 的原 SYNTHETIC preparation_catalog 内容哈希和 generation。
2. 已存在有效的企业/专员/执行者会话与原 READ/PREPARE/REVIEW_ASSIGNED/EXECUTE 等权限、两项资源及所需 READ/HOLD。配置包角色/资源映射只是选择约束，不签发身份或权限。
3. 有效期、版本、字段/服务映射均匹配的 pack/journal、绝对路径和 SHA256、私有 journal 权限、精确数据库与目录绑定；见 [原配置合同](LocalSyntheticDemoContract-20261017.md)。
4. 普通 worker 可用；用户通过上述原页输入新诉求/目标和两槽有来源材料，再由原角色分别 REVIEW/CONFIRM。
5. 若继续 P3，必须另有该精确 Run 的既有合法 executor assignment。加载器、页面和本片测试均不创建它。需要受保护资源操作时仍须其原合法批准输入，demo 不代替批准。

原 cold-input 服务实例向导仍未接入此普通 profile，相关接口拒绝保持；NativeRunAccess permit/writer 默认拒绝不变。正式来源尚缺 source-specific 独立验真、当前 head/撤销、Case/Run/方案及当前主体授权绑定、正式资源批准映射等产品代码，也缺来源结构与原信任/授权合同，详见 [正式来源缺项](FormalPreparationEntry-20261017.md)。不能只补凭据、信任自报标签或复用 IsolatedPlanApproval fixture 来称真实接入成功。

完整项目尚未完成。未验 Windows、正式 AT、真实业务或真实模型；没有改 main、强推、部署、新费用或安全网络权限，没有创建真实身份/Grant/分派/目录发布/批准/凭据，未知锁保持。
