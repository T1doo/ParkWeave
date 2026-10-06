# 截图证据可复验性

本轮在8e2195a恢复后检查全部docs JSON/Markdown中可解析的.runtime PNG引用和已登记hash；清单见[evidence/eng024-screenshot-audit.json](evidence/eng024-screenshot-audit.json)，由scripts/audit_screenshot_evidence.py只读生成。文件存在不等于其历史截图仍可复验；只有已登记hash匹配才能确认对应字节。

- ENG020的17张命名阶段图、ENG021的5张命名阶段图仍存在且原hash一致，均保留；不改图或用新图替代。
- ENG023的10张回执命名图仍可按原hash复验。
- 历史准备browser固定输出.runtime/f2-before.png、f2-confirmed.png、f2-final.png先前已被覆盖，原字节无法恢复，明确NOT_REPRODUCIBLE_LEGACY_OVERWRITTEN。ENG014/015/018/019相应报告已追加截图限制；保留原运行成绩，不将当前同名图冒充历史图。
- ENG016个人待办使用独立task输出，不错误归入上述固定准备截图。其报告没有截图hash，未补造旧hash。
- ENG023报告中的.runtime/eng023-preparation-ui目录本次恢复后缺失，三张已报告截图也不可复验；在原报告追加NOT_REPRODUCIBLE_MISSING_FROM_RESUMED_WORKSPACE。不得用通用同名图或本轮新图替代。

本轮新截图只用于ENG024当前验收，独立目录并记录实际hash/流程ID；不回填旧图。原始阶段文档和22张命名证据保持。本地图片不导出或上传；用户视觉签收、原生Win11/真实设备仍未完成。未登记具体路径/hash的旧报告只可复核文字运行结果，不能据此认定旧截图字节已验证。

## ENG025 增量

最终14张新图使用唯一eng025-ui-verified目录，记录真实流程ID及SHA256；首轮图仍本地保留，但不充当最终冻结结果。55张登记图hash匹配（旧41+本片14），原3通用覆盖/3恢复缺图仍不可复验，详见[evidence/eng025-screenshot-audit.json](evidence/eng025-screenshot-audit.json)。未导出/上传/备份；用户视觉签收、真实设备和Win11仍未完成。


## ENG033 增量

8张真实三角色本地Case记录截图存于唯一`.runtime/eng033-screenshots-36b208acfdaa`目录，路径与SHA256见[evidence](evidence/eng033-local-case-acceptance.json)。目录创建要求不存在，旧图不覆盖、不回填。已目视核对最终桌面与320详情；仅Linux Chromium模拟viewport，不是Win11/手机实机或用户视觉签收。旧覆盖/恢复缺图限制仍保留；本轮未导出或上传。
