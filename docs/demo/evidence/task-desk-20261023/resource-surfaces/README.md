# 资源页暖橙功能分区候选（尚未渲染）

直接基线 `566fbf0b6d675cb2046e0fd8d12dad3782f44a61`。本片沿原资源预检／占位／组合／Case交付能力，仅改展示，不新增业务或宠物。无浏览器／CI／PG／真实HTTP／真实模型／用户电脑执行，没有读取旧拒绝附件。

## 实际产品改动

原资源页在一块连续白板中依次放预检表单、我的占位、两资源组合、多会话组合、复杂Case交付及组合记录。现新增四个纯展示容器（暖棕header、奶油预检区、蓝灰已有占位区、两资源组合包裹），增加“我的占位记录”h3，并在原combination容器加展示class。原顺序不变；900及以上pair／bundle并列，Case交付与组合记录全跨，390单列、动作可换行／全宽。

确定源码布局缺口：原resource-form为两列grid，直属替代时段fieldset没有全跨规则，默认仅占一格。本次只用scoped CSS补grid-column:1/-1、min-width:0及边框／间距／legend换行，表单内部字节不变。真实computed宽度和窄屏防溢出尚未验。

预检主区保留原步骤、合成／外部未受理／占位不保证／缓冲冲突警告；已有记录保留“刷新为准、不能靠切页撤回”。Case交付的原资格、来源再批准、旧占用保留、不自动释放等说明全部常显，未新增折叠。只将明确只读动作置为次级视觉，原disabled／hidden门保留；未把错误、未知、过期或占位状态一律刷橙。

## 精确保全与实际检查

- web SHA256 `7798e0e5c08462fd98cc20382d9e429a57a58ca61bbe95513c32065c7d755884`；完整业务script SHA256 `b6e5c87e2fcea5c3c7370318a39550d004c139b54495d3a4b27183c67d50adc5`，未变。
- 反向移除精确CSS／四容器／标题／展示class后整页逐字等父版。原754 ID及顺序、34 form／84 input／52 textarea／34 select／255 button子树一致；resource-form、bundle、delivery、plan-approval、状态和原服务／协同区域全部逐字保留。
- 四个既有Node场景在当前源码实际执行exit0：choose_fills_only、current_403_clears、unknown_bundle_controls、original_flow_explicit。原命令／源hash／stdout／stderr保存在node-original.json。8／4／6／11为场景内断言数，不加计为29测试，不累加旧5P／17来源检查／12取景检查。
- Node执行实际整页JS，DOM及fetch为受控替身，没有真实HTTP／API／DB；其中显式预检／占位／确认仅合成响应流程，不是当前浏览器、权限或业务验收。未跑pytest、全collection，未新增测试ID。
- 两项独立只读源码终审通过；未运行检查或代签像素。新scoped说明选择器未命中原有role／aria-live／data-tone／status节点；预检warning/neutral、组合error/warning/neutral、占位状态、蓝focus和强制色保留。

## 导览一致性与未验项

独立导览park_demo_web.html字节未改，SHA256 `1d1aefb15eda9ef9107220e8c72e8a1b864d0eac1b6a46c0e3203cca7508163e`。已只读确认其最终header渐变、主按钮及面板仍为绿色，与当前暖橙工作台不一致；作为下一页面缺口，不在资源切片混改行为或宣称全站完成。

父级已独立核run39原8PNG/result，给旧回访／协同有限像素ACK：GET两侧各8／POST0、cleanup18.379s、CLOSED／REFUSED／worker0及自有树退出；06整体38px修正、原生回访及guard／断点有限通过。此前原始metadata的未读状态是当时快照，本片明确补父级来源，不冒称执行器下载或亲看。该ACK不覆盖当前资源改版；390第二卡仅几何／字体，Forward、短屏实机、全WCAG仍未验。390×1000首办y752–797也不外推短屏。

本片不准备新运行编号、不改旧39绑定或启动CI。后续需先审本候选，再决定资源有目录／原表单／已有占位／组合交付的必要原生图，维持原合成、请求、文件／时钟与授权门。当前资源页1200／390实际布局、字段组宽度、长内容／空错加载和像素尚未验；源门、Windows／OWNER／真实来源／LIVE／正式AT35不因此解除。
