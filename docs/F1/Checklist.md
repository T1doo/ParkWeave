# F1逐条交接清单（ENG-011）

本清单区分“源代码/文档已实现”“独立工程尚未做”“需要外部条件才能实际验收”。阶段F1仍IN_PROGRESS；完整36AT/6EX均NOT_RUN。本輪完成后停止新增，供复核，不进入F2。

| F1任务 | 已实现且有工程证据 | 独立未做/边界未启用 | 外部实际验收门 |
| --- | --- | --- | --- |
| T01 原生工程/探针 | API/worker/PG骨架、Linux进程/浏览器；六Windows生命周期候选。新增未启用read-only原生文件候选：官方handle-relative逐级打开、拒reparse/别名/不安全ACL、同handle读取/hash，69 Linux policy/ABI/实参单测；原生专属合成probe与Linux guard | Windows API文件入口仍关闭。候选尚无native DLL执行证据；native通过后dispatcher启用与owner合成注册/写入适配仍需独立代码/审查，不能写成只缺实机测试 | Windows11 x64精确版本/安装权限、native Python/PG/NTFS、ACL/reparse/共享与替换竞态、干净安装/停止重启NOT_RUN；Linux不可替代 |
| T02 Schema/可信动作 | V1最小必备契约、严格结构/大小/受控规则/DAG/依赖锁；可信case.create/facts.assess，未知字段/脚本/路径拒绝；结构校验不发布 | 正式服务发布/组合计划与资源办理未开放，按后续业务阶段实现；本轮不借验收扩F2 | 真实园区规则版本/目录/材料授权未具备，不把结构通过写成真实规则合格 |
| T03 身份/隔离 | 三企业两园区合成身份；四角色可信上限、范围绑定能力/动作/字段Grant、owner或同scope单Run状态指派；队列/缓存/消息重验、审计最小子集 | CaseStep办理、完整生产身份委托/审计及真实资料分享未开放；单Run状态指派不是F2完整协同 | 真实园区账号/企业资料授权/角色配置与用户流程证据尚无 |
| T04 持久任务/账本 | 事务本地Case/回执/outbox、fencing/独立心跳、暂停取消/撤权；正常worker持久未知核对与三次查询限额；LOCAL_INBOX去重/倒序/抑制撤回；失联恢复 | 真实外部适配器、消息渠道、非原子文件产物协议未开放；后续阶段分别实现，当前没有外部效果撤销承诺 | 外部接口幂等/真实回执/在途撤回需授权连接，不能继承FAULT_INJECTION |
| T05 真实书生/预算 | 固定官方HTTP stream传输代码+严格身份/参数/secret echo；持久account级共享窗口/产品上限/角色绑定/usage预留与已发不重发；正常worker显式离线PLAN→当前授权gateway→实际本地receipt→结构化revision1/2，调用ID/回执hash/当前授权读取/原子终态恢复/独立心跳 | 当前CLI只接明确SYNTHETIC MockTransport；ENG010已补R2账号pre-send原子预约、默认30RPM/完成后60秒冷却、代次/未发退款及有界持久延后、时点事件、LIVE默认关闭与纯变量名/授权前提检查。实际安全注入/真实CLI启用未开放归E2；ENG011已补R3三字段来源/mocked候选/集中必要问题与澄清历史；R4native验证后的最小集成仍未做。窗口预算滚动/货币折算/账单校准不在此有界实现 | Park安全注入/账户/预算0/两个真实产品同协调库及账号引用审批、真实AT-02/30链及实际usage/计费/故障验证BLOCKED；其他项目不继承；HTTP代码仅离线验证 |
| T06 固定测试/来源冻结 | 42固定定义完整绑定表/执行器/JUnit独立状态汇总；临时PG/合成fixture重置与独立oracle；原Library完整原件/hash/源台账/痛点假设；工程子集/JUnit证据（各轮计数见Log） | 固定表是各AT的当前工程子集，后续完整业务oracle不在F1实现；真实业务比较/来源许可/效益数据不凭合成重建 | AT-31/32真实案例/公平对照/资料授权/收益尚无，C0模板/跨赛道规则/准确截止待核实；日期仅用户提供2026-11-05 |

当前ENG011最终工程证据见evidence/eng011-acceptance-summary.json；whole36AT/6EX仍NOT_RUN，原阶段/标准不改。有限R1已实现、R2已由ENG010补发送门及安全前提，R3本轮完成合成工程、R4未操作；E1 Windows、E2真实书生/安全注入/预算/共享部署、E3真实来源/C0保留。原Windows候选未启用/源码不变。ENG009的31发送历史失败不改写，当前31st拒绝回归见[AccountRate](AccountRate.md)。真实模型请求/预算0。
