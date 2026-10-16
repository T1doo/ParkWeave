from pathlib import Path
import json,hashlib
R=Path('.runtime/unified-propagation-root');F=Path('.runtime/unified-propagation-final');A=Path('.runtime/unified-propagation-oracle/final')
load=lambda p:json.loads(p.read_text())
f=load(R/'freeze.json');v=load(R/'final-regression-verification.json');c=load(A/'coverage.json');h=load(A/'html.json');close=load(A/'closure.json')
review=load(Path('.runtime/unified-propagation-review/frozen-'+f['source_sha'][:12]+'/review.json'))
assert v['status']==review['status']=='PASS' and all(x['source_sha']==f['source_sha'] for x in [v,c,h,close,review])
assert v['modules']==107 and v['new_passes']==88 and review['counts']==dict(PASS=66,FAIL=0,SKIP=0,ERROR=0)
assert len(c['rows'])==36 and len(h['modes'])==4 and h['python_control_http_total']=='NOT_RECORDED'
text=f'''# 有限多来源统一依赖传播与原局部修订

基线 `e0ffc81f2d29dbfd498c1a9a93206e689bd0b310`；冻结源码 `{f['source_sha']}`。开发分支 `dev/f3-unified-source-propagation-20261016`，root为唯一共享源码与Git写者；独立设计、候选、测试和审查各在私有目录进行。原V1产品§8与F3-T03范围不变，本片为有限工程增量，不是正式AT-25—27签收。实际交付提交由最后远端核对及交付消息给出。

原图按步骤重复表示来源，不能直接把共享节点的变化向所有消费者扇出。本片将原材料包、事实用途、服务/资源规则及集合等固定类别归一为Case/plan/type/facet稳定节点，每个步骤仍保留独立before/current观察、原字段、hash与日期证据。仅变化观察边产生根，再经原PRECEDES传播，保留每个受影响步骤的实际路径。P1已核当前版本而P2仍旧版本时，只传播P2–P5；仅P5旧观察变化时只传播P5，禁止回扇到P1/P2。

图仍是原注册快照的聚合来源，不倒填材料ID、断言正文或一般语义关系。节点含步骤最多96、观察96、边128；原P1–P5保持。事实确认改变准备版本仍可能使五步全部重验，来源归一不缩小原业务分区。无历史/集合不完整/未解释依赖扩大本Case、保留空并拒绝采纳；日期缺证据仅保留日期UNKNOWN，不擅自把整个影响判未知。

显式 `dependency_scope=BOUNDED_MULTI_SOURCE_V1` 复用原机会卡plan-revision GET与原ADOPT，不增加逐字段端点。独立 `dependency_propagation` schema2和source-change v4绑定原卡/当前计划、版本、原源快照及epochs；历史固定重建后仍走原v2全部校验。默认source_impact schema1、source-change v1/v2与员工专用v3协议不变；scope互斥，去掉scope降级/重hash伪造不能授权。机会提示不是事实或权限，刷新不复活失效、撤回或UNKNOWN来源。

实际混合材料/事实/资源集合/回执经本人明确确认、原ADOPT、必要原业务补正和受影响VERIFY回到六目标证据及清单。原MANUAL冲突、KEEP_AND_CONTINUE/DEFER、显式UNLOCK、原锁/正文/UUID/历史保全均复用旧协议。目录合同source revision与材料/事实混合变化，图确定影响五步，但原CATALOG_CHANGED仍拒绝局部ADOPT且无业务写入；不能用统一图绕过显式替换规则。

## 同一冻结源码的实际检查

{len(f['source_paths'])}个源码/测试/脚本路径、{len(f['all_tracked_sha256'])}个原跟踪文件及4个辅助文件在各正式窗前后哈希一致。最终所选107个完整相关模块、**{v['unique_passes']}个唯一pytest项PASS**，0FAIL/ERROR/SKIP；不是全仓。新增88项已包含在总数，不再相加。独审重新运行3完整纯模块66PASS（含1pytest内8受控客户端分支），与主集合重叠；7个原协议模块字节、11个关键函数AST相对基线保持。

|正式窗口|完整模块|PASS|
|---|---:|---:|
'''
for n,row in v['windows'].items():text+=f"|{n}|{row['modules']}|{row['passes']}|\n"
text+=f'''
原2秒资源时序测试所属完整30项从调度开始即安排recovery-solo，在其他pytest全部结束后一次运行，预算和断言未改。主窗完整模块/节点无交叠；实际collection与JUnit逐身份一致。[完整回归统计](evidence/unified-source-propagation-20261016/unified-propagation-root/final-regression-verification.json)和[实际选择](evidence/unified-source-propagation-20261016/unified-propagation-final/selection.json)。原CI元数据完整12模块432PASS/1FAIL/14SKIP：0.6秒超时子进程返回预期124但stdout尚空，失败在原预期合成print断言；原件完整保留。所有其他pytest结束后，仅一次空闲重跑相同完整12模块，原预算/断言/源码均不改，各窗collection/JUnit逐身份一致；跨窗446个原始ID相同，既有cluster_id参数由收集时uuid4()生成的唯一ID按固定函数/参数位置一对一对应，保留两原值，未泛化归一其他ID。最终有效CI元数据12完整模块：{v['separate_ci']['counts']['PASS']}PASS/{v['separate_ci']['counts']['SKIP']}原Windows/PowerShell前提SKIP，独立于主集合；本分支无既有远端CI触发，未新增dispatch或修改workflow。

4条完整原HTML由Node机械DOM驱动，native fetch→真实HTTP/ASGI→自有PostgreSQL，共{h['actual_native_fetch_total']}次页面请求；不是真实浏览器。正向和真实提交后受控丢回执各只有一次原ADOPT、5个不同步骤原VERIFY及六目标/清单读取；当前403清理、迟到403身份ABA保留新Case。Python控制额外办理的HTTP总数NOT_RECORDED，不混入页面请求统计。

|页面模式|native fetch|POST|真实403|
|---|---:|---:|---:|
'''
for row in h['modes']:text+=f"|{row['mode']}|{row['actual_native_fetch_count']}|{row['methods']['POST']}|{row['actual_403_reads']}|\n"
text+='\n丢回执后原键冷GET精确匹配唯一ADOPT，沿原prepare/release核对再继续VERIFY；恢复句柄无正文或图。真实跨tenant/owner/角色、撤权恢复拒旧预览、两提交ABA、同键异参、受影响锁需原解锁、未影响锁原对象保全及v4后默认v2非粘性均有实际回执。[独立HTML逐条核对](evidence/unified-source-propagation-20261016/unified-propagation-oracle/final/html.json)。\n\n'
text+='## 独立字面预期与覆盖边界\n\n[36行原设计](UnifiedSourcePropagationOracle-20261016.json)始终保留DESIGN_ONLY_NOT_EXECUTED；下表为实际原回执分层映射，不能将设计行数、重复读取记录或受控分支数相加当pytest项或真实闭环数。纯字面明确比较affected/preserved/UNKNOWN，不代表HTTP或全部direct根列均实测。\n\n|证据层级|设计行|\n|---|---:|\n'
for kind,count in c['counts'].items():text+=f'|{kind}|{count}|\n'
text+='\nUP09实际多源变化与设计仅P1直接变化不完全同初态，额外HTTP记录只算变体；UP25实际保留三锁与设计单锁有范围差异；UP33/34的v4→默认v2不能单独代替所有v1/v2/v3历史分派检查。旧协议另由原相关完整模块及冻结独审验证。逐行literal与实际identity见[覆盖映射](evidence/unified-source-propagation-20261016/unified-propagation-oracle/final/coverage.json)。\n\n'
text+=f"最终日志记录分组为 `{close['record_counts']}`；这些是读取/断言记录，不是唯一业务场景数。[闭环分类](evidence/unified-source-propagation-20261016/unified-propagation-oracle/final/closure.json)。\n\n"
text+='''## 保留的开发失败与原件

后端私有首纯窗24FAIL/17PASS为oracle相对路径错误，修正测试路径后41PASS，模块未改。独测WIP首完整45项34PASS/11FAIL：9项先改准备来源再REOPEN旧回执，原绑定正确409；2项撤员工字段READ后错误期待通用入口403。修正原办理顺序和撤原READ capability，不为新scope新增权限。

第二WIP完整45项40PASS/5FAIL：3个API实际CATALOG_CHANGED阻塞，2个HTML未发ADOPT POST；旧HTML轨迹没有记录preview blockers，不从API反填HTML原因。第三WIP完整46PASS仅作预检，不迁冻结分母。所有日志、JUnit、不同候选源和分析均保留。

独审另实证初版客户端接受重算总hash后的额外字段、非规范ID和重复来源组；服务端精确历史重建仍拒绝，未证实授权绕过。已补精确keys、稳定ID规范、唯一分组及UNKNOWN原因/分区推导，冻结源码8受控分支和实际HTML重新验证。见[发现闭环](evidence/unified-source-propagation-20261016/unified-propagation-review/frozen-62865b43c470/finding-closure.json)。

导出只替换已知合成会话值和pytest夹具repr行，JSON/XML保持可解析；私有原件不变，数据库/缓存/私有会话集合不导出。主档逐项记录原件/导出路径、字节和SHA；独立终门从原件重新转换、核对完整inventory及前后稳定。基线5070个此前原件和80个旧远端分支保持；原四份Plan/Log/关键路径文档旧历史逐字保留。[主档索引](evidence/unified-source-propagation-20261016/index.json) · [独立终门](evidence/unified-source-propagation-audit-20261016/final-gate.json)。

## 未执行与下一关键路径

仅Linux本地工程证据。Windows/Win11、真实浏览器、正式AT、人工语义、真实模型B0–B2、正式治理/Approval、现实履约和生产未执行；本分支远端CI未触发。本地六目标仅LOCAL_OUTPUTS_VERIFIED，清单recorded_states_only=true/evidence_verified=false/case_goal_completed=false，不是现实目标完成。

本片限已有Case和编译来源族，未实现任意图或自动语义裁判。继续一周目标，后续补更多明确来源的独立验证、复杂在途升级/F5-T04、备份恢复及正式治理/运行前提。main和旧分支只读，未强推、部署、新增费用/凭据/安全权限或绕拒绝；真实产品模型调用0。
'''
p=Path('docs/F2/UnifiedSourcePropagation-20261016.md');p.write_text(text);print(str(p),hashlib.sha256(p.read_bytes()).hexdigest())
