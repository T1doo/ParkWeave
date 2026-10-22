# run22 实际失败原件及动态字体验收器修复

[官方run22](https://github.com/T1doo/ParkWeave/actions/runs/39783602539)，attempt1，job `119840861546`，受测完整SHA `75d8661ffb6c6d804c4f93f378c0ff30ed320c9f`。**终态FAIL**：`FRESH_SPECIALIST_READ_ONLY` 的实际字体核验报 `actual participating font union misses visible node CJK`。没有自动重跑或转签旧run21。

实际29POST全部成功＝26API＋3DOM（原OFFER、本人ACCEPT、B企业本人CONFIRM）；A/B两份不同诉求、材料、候选、计划均已分别ADOPT，目标数5／1。owner和专员新context各读回两份资料，owner另读两份精确计划。A首次业务历史保全比较仅从global cases排除新建B一行，其他命名投影完全比较；不是原始全对象或全DB不变。B独立CONFIRM原key对应唯一preparation SQL event，A OFFER／ACCEPT原key对应唯一真实事件与主体，ACCEPT原键正常GET恢复COMMITTED。完整原件见[result](result.json)。

**尚未执行**：executor的新context A真实回执正读／B分派403、导航后拒绝保持空、全部角色结束后的双Case最终投影比较。因此本次不签三角色浏览器通过或正式AT35。没有P3–P5 VERIFY、第二事项完整履约、TXT或服务冷重启。

实际102 GET/HEAD＝83主流程＋19就绪，主流程79×200＋4次fact-clarifications403单列；403不计成功。两个worker exit0；单代API/PG及wrapper exit0，marker消失、监听关闭、无清理错误。191包文件逐字对应受测Git树，wheel仅在官方ZIP内；原许可固定字体仍私有使用，未归档字体二进制。原job10min／270s工作／360s绝对收尾和40POST等门未变。

已由原诊断及独审确认失败为**验收器假阴性**：`#prep-materials > article:nth-child(1) > p:nth-child(2)` 的CDP实际报告Noto8 glyph＋DejaVu14 glyph，来源无非法项；原Noto charset覆盖“培、纲、训”。三字不在静态684字符集，旧`covered_codepoints`仅保存该静态交集，却被误当动态正文的完整charset。见[无实际执行的原诊断回放](dynamic-font-diagnosis.json)；压缩诊断原件及完整raw charset保留在result，未删缺字断言。

最小修复从每个实际CDP唯一可信face的原raw charset，对当前真实节点字符重算覆盖，并记录`covered_visible_codepoints`；静态覆盖、字体路径／许可、唯一来源／custom拒绝、CDP与原5秒share全保留。新增受控CDP回归：原版本[1FAIL／0.10s](dynamic-font-before-original.log)，修后[1PASS／0.06s](dynamic-font-after-original.log)，真实缺“训”分支仍精确拒绝。它不是浏览器重验，没有新字体下载、安装、权限或费用；本轮实际执行已停止，修后浏览器尚未运行。

[01](01-new-input-confirmed.png)实际视口落在来源摘要区，不能作为材料确认的视觉证据；确认有真实DOM响应及SQL原key证明。[02](02-owner-distinct-plans.png)只显示B计划视口，并非A/B并排展示；两计划独立性由完整JSON支撑。[03](03-specialist-distinct-materials.png)及[失败原图](failure-source-restart.png)中B“培训大纲”中文可读。四张都是1200px原图，无390px或全部字形像素结论。

[完整decoded API job日志](ci-original.log)、[官方ZIP](artifact.zip)、[run](run-api.json)／[job](job-api.json)／[artifact](artifact-metadata.json)元数据、[离线核验脚本](archive_run22.py)、[限定回执](validation.json)、[源码等价映射](source-publication-map.json)、[校验和](checksums.sha256)均保留。原ZIP1567900B、7成员，SHA256 `1d1cc4bad9e84838e1efa9a00799aeb778dbfd704caac538a213c7d96e2edd31`；原日志811595B，SHA256 `2b1f30b067674bc7c05912f36398d6a3252678189226bf147b955251bca6f3c2`。stdout PENDING规范化与最终FAIL相等，不当PASS。旧summary超限报错本轮未出现，但summary正文／上传未独读，不能以无该报错冒充完整最终化验收。

正式外部来源、Windows原生、LIVE／真实模型、真实线下履约、C0材料与正式总验收仍分别未验；不把本地来源或合成两输入当外部系统成功。

修后冻结源 `fe0e5f098214d584f9f187f89f4085dede76080e` 的精确collection为9521项／405文件，四片2420／2323／2438／2340，754原字节指纹与稳定身份多重集合精确吻合，见[修后collection原日志](font-fix-collection-original.log)。仅collect，不是9521PASS或新浏览器执行。
