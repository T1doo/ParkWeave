# 两企业两园区普通新办理：范围合同

基线：`a396f63eed027d4ccf8dc1ed6f591766915449ae`。先读原`docs/分阶段开发计划.md` F1-T03、F2-T06及AT04/08/35：至少两个企业和两个园区配置；新企业冷会话和新材料产生独立Case/结果，不复制旧数据/身份。这里只交付已有Linux依赖下的普通SYNTHETIC入口，不声称完整模板审核/发布、Windows、正式AT35或真实业务完成。

在全新自有setup里明确提供两套固定合成范围：原演示企业/园区与第二演示企业/园区各有自己的企业经办人、专员、执行者、独立随机会话、同scope PREPARE/REVIEW_ASSIGNED、园区资料目录、两资源及本企业READ/HOLD。角色、能力和SQL权限种类不扩大，不生成Run assignment、Case、材料、计划、分派或批准初态。第二套目录/资源来源明确SYNTHETIC，不是正式目录发布。

复用原初始化live receipt、Store.migrate32、目录/权限/普通规划与P1–P5。用户在私有sessions.json按明确范围/角色键选择会话，使用原页面，不增加自动选择/登录或包装页面；专员、执行者和资源从原当前会话目录读取。第一套原键保留，第二套使用second_enterprise、second_specialist、second_executor。两套配置元数据绑定到新state schema，serve对缺失/篡改的范围绑定在启动PG前拒绝。旧一范围状态不迁移、不补seed，使用原冻结源码运行；本次只新增全新自有状态。

最小验证须实际CLI setup起空业务库、原API与真实worker：第一范围的一个Case用作跨范围隔离对照；物理停库重启后，第二范围第一次冷会话、新诉求与新材料独立办理，明确REVIEW/CONFIRM/ADOPT及P1–P5和下载。两范围同一时段使用各自资源；Run/Case/preparation/plan/dispatch/evidence均新建。原Case历史和TXT保持。新范围不得用旧Run建立资料、选择旧专员/执行者、读取旧Run/Case/材料/目标结果/回执/资源占用、关联旧资源组合或采纳旧source proof；双向越界都须准确拒绝且不改变原业务状态。不能用旧Case或旧验证结果冒充第二次新办理。对照不是重复同企业A/B计分。

证据记录实际源码SHA、collection/setup/call/teardown/JUnit、输入和导入来源、真实API/worker/PG生命周期、权限初态/结果与原始失败；独审按实际节点去重，不叠加上一片14项。先冻结独立原文oracle后读实现；独审只写私有.runtime，不写受控产品/Git。本线程为唯一受控文件/Git写入者。

禁止改main、强推、部署、真实身份/Grant/分派/目录发布/批准/凭据/模型/费用及生产或安全网络权限扩大；不改原provider互斥、不接管未知锁/PID、不删除失败现场。保留有界重试和原截止/占位期限；不得为了测试数量重跑同企业A/B全矩阵。Windows/WSL、安装器、真实浏览器和正式AT/真实业务另列NOT_RUN；外部协议不阻塞本独立合成项。
