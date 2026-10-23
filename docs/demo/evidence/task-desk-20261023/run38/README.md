# Run38 回访＋协同合并验证：来源绑定候选，尚未运行

受审产品直接父冻结 `86bd185ddc33da4e617e2ebaa540d074d000e454`。普通页 SHA256 `9711354a500e0940f1be9677b38e9d35d68e03a5485aa0ba4c9bd8d43ab30aa2`，导览页 SHA256 `1d1aefb15eda9ef9107220e8c72e8a1b864d0eac1b6a46c0e3203cca7508163e`。两页与该产品版本逐字一致，本片只替换验证场景与来源绑定，没有新产品改动。

正常只读 GitHub 元数据实读最新 workflow 为 run37、`39974655252`、source `cf76736d050cef96265c1009753cfb0980968de9`、completed/success。因此下一候选为38；不是已创建的run。提交前／实际投递前必须重核最新编号，若不同先重新绑定独审，不能放宽为任意run或重跑旧run。旧run34–36拒绝路径没有读取。

## 准备提交与执行分离

候选仅封存在普通开发审查分支 `dev/ui-return-collaboration-run38-review-20261023`。已只读核全部现有 `.github/workflows/*.yml` 的 push 都使用精确分支白名单，该审查分支不匹配任何一条。原执行分支 `dev/fictional-park-browser-once-20261020` 保持86bd；本轮不推送会触发CI的ref，不创建PR、发布或部署。后续父级复核与执行条件确认后，仍需核原执行分支未动，再决定是否将已审候选正常快进；本轮不执行。

运行门：repo `T1doo/ParkWeave`、公开hosted Linux、精确原执行ref、push、attempt1／run38；环境source必须等于真实checkout完整HEAD。driver主／worker、workflow与字体helper同步绑定38。`HEAD^`须恰等86bd；页hash及逐字比对同时成立；精确变更白名单只有workflow、driver、字体helper、ENG057 manifest及本目录README/preflight/SHA256SUMS七路径。未知／重复／缺路径、页面变化、脏或未跟踪工作区都拒绝。

## 唯一8图及观测

1. `01-service-entry-1200.png`：宽屏回访入口、首办主任务与原警告。
2. `02-service-entry-390.png`：窄屏首办动作和快捷条，记录首动作实际y，不能预先称未被压低。
3. `03-native-existing-390.png`：原资料定位目标与完整警告／输入／按钮。
4. `04-native-formal-390.png`：正式来源条件与完整独立证明警告。
5. `05-collaboration-empty-1200.png`：原分派GET空响应后的主待办／分区层次。
6. `06-collaboration-records-1200.png`：原分派GET／renderer的长中文同名、不同精确键；取景到lane并要求两卡所在items完整可见。
7. `07-collaboration-records-390.png`：原回执GET／renderer的局部纵向视口，首卡及警告必须完整可见；第二卡另实际滚动核几何和字体，不另PNG，不能宣称第二卡像素已看。没有clamp、缩字或隐藏警示来凑图。
8. `08-collaboration-denied-390.png`：当前403响应，原拒绝文案与空列表、原按钮焦点。

回访两宽度分别用真实mouse和链接focus后Enter，观测fragment、原生目标activeElement、随后真实Tab到原输入／按钮，再真实Back回原hash。不会设置hash或target.focus制造通过；同document须非空对象引用与外部UUID双重匹配。Back不预设浏览器恢复哪个activeElement。每步核请求增量0。

390再植入透明 `UI_STATE_FIXTURE`：原prep UNKNOWN允许纯定位，精确原pending／body／context、草稿、Map／op／flow引用与内容保持；activeflow、retainedlease、receiptUNKNOWN由原capture阻默认，hash/history不变。正常／prepUNKNOWN／flow／lease点击原epoch各+1，receipt早拦均0；链接自身可以得焦，不能据此误判拒绝失败。仅在引用和快照相同后精确释放自己夹具，不清全局Map或改capture。DOM快照只排除三个明确预期反馈节点，未排除其他状态或警告。

协同受控HTTP夹具仅精确GET `/api/service-dispatches`、`/api/executor-receipts`，无业务后端／DB。现有合法结构的合成同名不同键／长中文、未知状态与取消／暂停警告由原renderer呈现，不直接调render或伪造正式主体／授权。原读取会相互清理列表，1200只拍分派READY、390只拍回执READY；不拼造两列表同时有记录的产品状态。

拒绝证明限实际顺序：READY两卡→点击刷新时原LOADING先清空列表／已有view→服务器当前403→DENIED保持空。`pre_response`明确记录清空已发生，不能把原本为空的三个view或加载预清屏签成独立403撤权清屏。

899／900仅核协同单列／双列和按钮归属；1060仅核横向导航、current、几何不重叠。均恢复viewport／scroll并核请求增量0。夹具标识在每张图可见；原生落点／Tab观测先完成，随后移动唯一标识和滚动仅为截图取景，两种观测在result单列。

## 安全与预算不变

正常Chrome sandbox与原CSP；固定原Noto commit／文件blob／大小／OFL，私有目录与既有许可不变；无新依赖、权限、凭据、费用、用户电脑、业务POST或真实模型。仅页面、精确列表、run-access禁用状态与favicon GET；其他路径404会最终失败。服务端与浏览器GET各<40，POST0（两侧同批不相加）。8PNG+result=9文件，失败图预留后最多10文件／8MiB，凭据扫描和原发布最终化保留。

原job10分钟／依赖3分钟；工作清理总90秒／worker85秒、发布360秒绝对时钟、原15／30秒等待不缩短。沿原supervisor归属、TERM/KILL及退出核验，不改sandbox或杀未知PID。预估正常流程约45–65秒（不是实测）：原启动和字体约10–20、两context和native交互约10–15、8图及实际节点字体约15–20、收尾余量；不能保证每次完成，时间不足必须保全FAIL并清理，不自动重跑。临时目录删除／断电耐久／真实设备流畅度不在本片证明范围。

## 本轮实际离线检查

`preflight.json`记录实际纯来源门正反例、两页指纹／字节漂移拒绝、内嵌JS编译但不调用、390同横边界几何归属替身反例、实际sentinel纯谓词空值／替换／错UUID拒绝；不是pytest、浏览器或效果测试。原owned_browser、require_operation_time、worker_main/main（除精确run号）逐字保留；workflow只运行编号／阶段名、font只私有目录／编号同步，不改资产或预算。真实原生／像素／运行耗时仍未验，尚无run38 PNG/result或新的官方run/job/artifact。

取得新原件时执行器仅报告正常元数据ID/name/size/digest/expiry/source。父级选择已有正常授权消费者读取；不自动尝试历史Forbidden下载方式或换路径取旧包。
