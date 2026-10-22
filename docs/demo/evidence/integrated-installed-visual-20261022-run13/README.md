# 当前安装包与界面真实浏览器限定验收

执行源码 `ce0c3fe03ff0a0a86092ac2787da08c07fd0b68d`，run13/attempt1：
https://github.com/T1doo/ParkWeave/actions/runs/39751446120

当前树离线构建、独立安装的 wheel 实际用于 setup/API/两worker，191包文件、48声明资源逐字验真。锁定依赖及已许可固定字体只在原引导阶段获取；构建/安装零下载。37 POST（26准备+8真实页面+3负例/重复），73 GET/HEAD（含14 readiness）。工作28.516秒，through artifact scan 28.998秒，最终step/job成功，原270/360秒与10分钟job上限未改。API/PostgreSQL均正常退出，自有监听停止且无清理错误。

真实页面提出→批准→首次资源交付；故意中断已成功的回执读取，刷新后原键恢复同回执/CONSUMED；重复原提交不重复消费。第二Case在390px实际提出/批准/撤销；跨Case和撤销后提交409。撤销一个自有合成READ授权后，403清除六私有视图；2次403独列，不计成功。初始两Case和NO_MODEL V2候选/首次ADOPT由API准备，不是页面新输入验收。

7张原截图均已读取。绿白卡片、间距与按钮状态显示一致，已摄中文清楚，五个测量视口均无横向溢出。04/05是窄屏滚动后的批准历史尾段，不能代表整页控制全部同屏；长审计编号仍需纵向滚动。03的Failed to fetch来自故意中断；06洋红会话框是既有凭据隐私遮挡。07仅390px导览初始页，未载入会话、未打开办理窗口、零业务写入。截图保留原件，不生成替代图。

artifact.zip、完整API job原日志、result、原JSON元数据和校验均保全；stdout为PENDING_FINALIZATION，仅结果附件PASS与实际步骤/job成功联合为终态依据。step summary正文未独立取回，明确保留该限制。原提交与API发布整树等价关系见publication-final.json。

本次未覆盖来源变更再批准的浏览器链、冷重启、P1–P5/TXT全流程、全部684目标字形像素、整个应用精修/手机实机、外部正式来源AT35、Windows原生授权/安装或真实模型；不转签这些范围。原源码功能30P和前次run12均为历史独立窗口，不重复累计。
