# ENG-005 冻结映射（执行前）

来源：V1产品§7/§9权限交集、outbox及逻辑文件ID边界，开发计划F1-T01/T02/T03/T04；本轮新建，不是收到的验收包。基线8abf48f276a0b991f215cde996eba7593884dfad。仅现有Run闭环，不增加F2办理、资源预约或业务消息渠道。

| 固定工程子集 | 初态/动作 | 独立oracle | 任务/AT |
| --- | --- | --- | --- |
| 角色与范围交集 | 三企业两园区；四角色；owner显式授予单Run状态读，再撤回；客户端伪造角色 | 委派只有状态，不能读receipt/材料/控制/建单；其他org/park即使错配Grant也拒绝；DB业务/效果数不变 | F1-T03 / AT-04、19（AT-12仅未来F2） |
| 排队授权 | HTTP入队后撤执行能力，正常CLIworker领取 | FAILED_SAFE，无Case/fixture效果；重复key/缓存不恢复授权 | F1-T03/T04 / AT-19 |
| outbox当前授权 | 同事务事件，ack前故障、新旧乱序、撤READ后消费；已交付后撤权并再消费 | 事件不重复；陈旧不覆盖；撤权不交付，旧delivery清空/撤回；API当前读403 | F1-T04 / AT-16、19 |
| 文件逻辑ID | owner登记合成UTF8 text/plain≤16KiB；真实HTTP按UUID下载；猜别家ID/路径/根symlink/内容篡改 | 无路径入口；拒绝前无文件读取/业务副作用；危险文字仅attachment纯文本；hash失败不返回内容 | F1-T01/T02/T03 / AT-03、04、05、19 |
| Windows边界 | Linux测试拒绝盘符/UNC/ADS/相对穿越字符串；原生Windows重解析点/路径语义 | 字符串拒绝只计Linux工程证据；原生Windows NOT_RUN | AT-05 Windows子门 |

真实模型调用0；INTERN身份大小写兼容仅登记后续真实链要求：intern-s2/Intern-S2视同一已知型号，其他型号仍拒绝。当前不新增LIVE调用。完整36AT/6EX仍NOT_RUN；仅本文件冻结工程子集。

执行审查补充（同范围）：能力/动作Grant绑定park/org，身份改属不能沿用旧Grant；非企业角色的旧本地inbox交付也拒绝/撤回。Schema5仅对本轮未发布schema4原型作增量字段补齐，保留active/业务历史，不重置测试数据库。新增覆盖AT-04/19及AT-27迁移工程子集，完整AT状态不变。
