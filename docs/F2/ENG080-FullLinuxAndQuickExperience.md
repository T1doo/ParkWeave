# ENG080 当前源码完整 Linux 回归与快速体验

本轮以父提交 `d288466caf5b346bae3f5828d212801b0295fe03` 的产品源码为基线；没有增加产品功能，也没有改动owner、权限、Windows workflow或业务API。补充现有浏览器复验脚本，修正三项仍要求旧完整workflow的测试断言，并同步当前文档。最终本地Git提交可通过本说明所在提交定位；未push或启动新CI。

## 回归结论

最终完整Linux回归：**1454PASS / 0FAIL / 9原生WindowsSKIP，2个既有警告，299.57秒**。首轮实际1451PASS/3FAIL/9SKIP，299.29秒；三个失败分别为job_budget、safe_annotations、windows_ci_preparation中旧workflow步骤断言。修正后相关定点114PASS；最终全量结果单独记录，不用定点覆盖首轮失败。

断言现在严格要求已授权的单windows-2025、25分钟job/2分钟测量step、四个步骤、contents:read、原并发组、不持久化凭据及固定Python；禁止执行Engineering.ps1、owner/ACL、旧failure-oracles、依赖安装或描述符入口。原工程helper预算与notice边界继续检查，原Publish→Stop顺序在保留的可逆补丁中验证。没有恢复旧完整workflow，也没有删用例或增加skip。

1463用例的精确集合与ENG077相同，四片345/345/349/424精确覆盖；53测试及33实现指纹匹配。collection与执行分开。9个原生Windows用例在Linux跳过；Linux不是Windows验收。当前workflow嵌入PowerShell仅用已缓存程序做AST解析PASS，未执行其Server动作。首次默认进程CoreCLR退出-6，无解析结果；最小OS环境与已授权本地执行权限下解析成功。

## 当前实际用户体验

只使用保留Case `0b76ab4c-e429-4313-ace2-25d3522ed09b`、Run `e6c2bddf-8fb8-4848-b45e-8f4ffda6b8c6` 和已有合法assignment。无seed/migrate/assign或grant变更；所有业务改动经正常企业/执行者UI与当前API完成，没有fixture owner直接写业务结果。

| 场景 | 实际结果 |
|---|---|
| 回执读取失败与恢复 | 无效合成会话真实403可见；受控浏览器断连有固定连接提示；成功刷新列表/原回执清除提示 |
| 跨身份迟到返回 | 真实成功GET被延迟到切换身份后，不回填旧内容；旧请求受控拒绝迟到，不覆盖新身份反馈 |
| 提交已落库但响应丢失 | 实际POST成功后只在浏览器丢弃该响应；保留原输入重试，revision和版本均只新增一次 |
| 修改后的重新核对 | 企业重开ACK回执、要求纠错，执行者提交新版；企业核对新版后旧Case snapshot失效，关闭禁用；显式重验后才能本地关闭 |
| 收起计划并返回 | 从同Case打开固定计划后“收起计划”，返回同Case；revision、轮次与当前校验不变，没有创建模板或业务撤单 |
| reload | 原Case、本轮记录与回执版本持久保留；最终Case仍等待真实确认，目标未完成 |
| 桌面与手机 | 错误提示、当前回执、Case在1200/390/320宽度分别测量，无横向溢出；人工查看关键PNG，文字与按钮换行可读 |

初次修改走查在旧资源时段结束时被正确阻塞：Case重开至cycle5/revision14，RESOURCE_WINDOW_ENDED使重验禁用。保留该结果，未伪称通过或修改时间/规则。之后通过已有企业UI正常预检、占位、确认新的两资源组合，再为同Case显式保存资源关联v2；原关联历史保留，规则/容量/grants不变。旧组合没有被自动释放，新有效组合仍保留为本地合成记录，后续使用时须重新检查时段。

继续原第5轮走查，最终本地记录revision17、回执revision18、版本5→7；Case WAITING_CONFIRMATION、case_goal_completed=false，资格NOT_EVALUATED、外部NOT_SUBMITTED、线下NO_EVIDENCE。没有真实模型请求、预算0、R4关闭。此处“收起并返回”只是界面导航，不能称为撤销已提交回执、资源或真实履约。

实际查看的截图及源码绑定见[证据](evidence/eng080-full-linux-and-product.json)。手机宽度是Chromium viewport检查，不是实体手机或用户视觉签收。实际业务与只读两条浏览器脚本均通过，无browser errors；每轮API/worker通过自有Popen句柄SIGTERM/wait（-15/-15），PG STOPPED，无广泛kill。原环境、数据库、已有Case及历史截图保留。

## 本会话最短复验

在项目目录使用已有安装与保留fixture自动只读复验：

```bash
PYTHONPATH=src /workspace/ParkWeave-restored/.venv/bin/python .runtime/eng080-read-only-replay.py
```

该harness依赖本会话保留PG、私有会话、合法assignment及缓存Chromium，调用交付源码中的 `scripts/receipt_read_browser_smoke.py`，结束后停止自有服务。每次运行生成独立报告/截图目录，不覆盖已有证据；环境重置后不能假设路径仍可用。不调用ENG073的新Case/赋权脚本替代本轮复用范围。

人工体验：在已运行的本机环境进入“协同”，企业/执行者使用各自已有合法会话选择同一事项。失败时先看可见提示，连接恢复后刷新列表再读取；已经提交但响应不确定时保留原输入重试或刷新持久状态。企业要求纠错后由执行者提交新版本，企业重新核对当前版本，再进入同Case显式重验。若资源/资料依赖不满足，先按原业务入口处理，不能强行关闭。打开计划后“收起计划”回原Case，不创建模板。当前本地关闭仅表示合成记录整理完成。

本轮修改走查脚本 `scripts/receipt_correction_browser_smoke.py` 增加显式 `--exercise-write-retry` 和 `--continue-reopened-case` 复验选项；它会追加同Case业务历史，不是只读入口。资源有效与已有assignment仍是前置，不自动准备授权。64事件边界仍保留，不清空历史绕过。

## 阶段与Windows真实状态

F1未签收，F2仅并行探索，R4关闭，模型预算0。最新完整工程Windows证据仍是ENG071失败与S4缺口；ENG078独立run37545785486/attempt1/source381a20a success仅为隔离Job测量，具体membership/signal/unrelated cleanup JSON未取得。job-log GET流程Forbidden，HTTP状态及API/重定向拒绝位置未保存；不再读取或换路线。owner保持暂停，完整CI未恢复，描述符目标未选，Win11/完整36AT6EX/真实履约未验。

Plan/Log/FirstUse/快速体验/V1Status顶部已指向本轮，以下旧ENG记录保留为各自历史快照，不能用其中“当前”“未推送”文字覆盖最新状态。最后已核实的远端是381a20a，之后本地提交未推送；本轮不联网确认实时远端。
