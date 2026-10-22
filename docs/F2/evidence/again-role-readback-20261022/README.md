# AT35 工程子门：不同输入采纳与角色持久读回

原规格为 V1 开发计划 §AT-35：首个办理后再次运行，关键状态持久、对应角色可操作、不同输入输出不混淆。双Case完整API链已有历史实现；本片不重复P1/P2/TXT、不称发现缺双Case业务代码，也不签完整正式AT35。

当前新增唯一实际HTTP/PostgreSQL用例1P／10.29s：A五目标与B单材料目标采用各自全新诉求／摘要／目录、Run／Case／preparation／候选／计划；跨Case候选ADOPT409。A的原P1/P2与OFFER/ACCEPT只作角色读取前置；B不继承核验、资源或分派。新Store／TestClient ASGI configured API下owner及专员精确读回两份材料，executor正读A真实分派／真实回执步骤，读B真实preparation的dispatch403，A历史保留。实际完整结果见[本地原件](local-distinct-inputs-fresh-roles.json)，[原测试日志](local-original.log)。它不是浏览器或服务冷重启。

summary修复只将原完整result的导航摘要收敛到32KiB以内，错误超长明确指向原附件；完整result/stdout及既有失败撤回／单时钟保护不变。两大报告PASS/FAIL纯例通过，既有后置summary超时guard1P通过，各自单列，非真实runner上传成功。run21已观测1685k>1024k上传失败的[原记录已更正](../no-model-tail-20261022/run21/README.md)，不为此重跑。

候选run22尚未执行：A18API前置＋B8API＋原DOM OFFER/ACCEPT/第二事项CONFIRM，共26API＋3DOM＝29POST；随后三个全新角色context仅GET读回A/B。executor只读获派A的真实回执步骤，B没有回执时不捏造ID、不用404充权限拒绝；原导航清屏后B /entry403保持空，不冒充403单独触发清屏。仍为同一企业／园区，不签新企业模板、B完整履约或正式来源。

沿原10min免费job／270s工作／360s绝对收尾，40POST／26API／8DOM／400GET／2worker、正常sandbox、固定Noto/OFL私有字体与191包文件安装门。五视口图＋result／wheel／组件日志共8件，预留失败图，10文件／8MiB及凭据扫描不变。无新依赖版本、权限、凭据、费用或真实模型。Windows原生、LIVE、C0实际材料与正式来源仍分别未验。

9520项／405文件全局与四片collection仅收集，不是9520PASS。新单例归既有S3、既有文件分片不动；749原字节指纹、全局/各片精确身份多重集合已核，见[collection原日志](collection-original.log)。原失败为测试fixture、DTO字段、依赖显示状态与UUID归档错误，私有原日志保全，不冒充产品红例。驱动独审发现的合同错配修复后才可运行候选，不自动CI重试。
