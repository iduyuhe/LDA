# LDA 投资人路演 PPT · 叙事逻辑（STORY）

> 风格分支：命中「商务咨询」预设风（投行/IPO 路演、风投行研）。视觉依据直接采用 `designs/design-principle.consulting.md`，不另生成 DESIGN.md。配色微调为科技蓝变体：Navy `#061F32` 主 + `#001965` 皇家蓝 + `#08A6F6` Cyan 强调 + `#99BDED` 浅蓝 + 中性灰；字体 `Arial, "Microsoft YaHei", "PingFang SC", sans-serif`。

## 一、意图块（5 问）

- **目标受众**：投资人（VC / 产业资本）、潜在企业客户（光模块 / CPO / 量子芯片厂商）、生态合作伙伴。场合 = 对外路演 + 宣传。
- **核心目标**：讲完后投资人相信——光子 / 量子设计软件正处范式拐点，LDA 以「开源 + Agent 原生 + 验证可证伪 + 主权自主」占据现有商业工具的结构性空白，是具备护城河的长期机会；并愿意进入下一步沟通（试用 / 对接 / 投资）。
- **PPT 长度**：16 页（Hero 占比 4/16 = 25%，落在 20–30%）。
- **视觉调性**：权威、数据驱动、科技克制、可信（consulting 风 + 科技蓝）。
- **内容边界**：
  - 必讲：范式拐点 / 工具空白 / 产品定位 / 验证红线（可信核心）/ 核心账目 / 全球对比差异化 / 主权纪律 / 市场机会 / 商业模式与路线图 / 团队与联系。
  - **禁碰**：不对外暴露内部「0 成交」硬事实（对外讲开源获客 + 生态播种路径）；不吹「求解精度已超越 Lumerical / Qiskit」——诚实标注差异化在「维度」而非「精度」，成熟度仍低于商业标杆、未流片。

## 二、页面骨架（目录 ↔ 章节扉页契约）

目录声明 **4 章**，全篇 **恰好 4 个 `type: section` 扉页**，编号 01–04 连续，与目录逐字一致：

| 目录章节 | 章节扉页页号 | 标题 | 页码区间 |
|---|---|---|---|
| 01 机会与痛点（Why Now） | 03 | 机会与痛点 | 04–05 |
| 02 LDA 是什么（产品与技术） | 06 | LDA 是什么 | 07–09 |
| 03 为什么是我们（差异化与可信） | 10 | 为什么是我们 | 11–12 |
| 04 市场 · 商业 · 团队 | 13 | 市场 · 商业 · 团队 | 14–16 |

- **Hero 页**：01 封面、07 LDA 定位、14 市场机会、16 团队联系 → 4 页（25%）。任意两 Hero 间隔 ≥1 个 Supporting（01→07 隔 02–06；07→14 隔 08–13；14→16 隔 15）。✅
- **rhythm**：peak = 01/07/14/16；valley = 04/05/09/11/12/15；transition = 02/03/06/10/13。无连续 ≥3 页 valley（04–05 后接 06 transition 打破）。✅
- **非对称版式预算**：04/05/07/08/09/12/15/16 共 8 页非对称 = 50% ≥ 40%。对称/专用页：01 封面、02 目录、03/06/10/13 章节扉页、11 图表、14 图表。✅
- **相邻版式不重复**：04 巨型数字→05 左标题右内容→06 section→07 非对称双栏→08 上大图下卡→09 巨型数字→10 section→11 图表→12 左大图右文→13 section→14 图表→15 非对称双栏→16 左标题右内容。✅
- **N 卡片横排**：全篇 0 页使用（KPI 用巨型数字、结构用 SVG/Box 图）。✅

## 三、页面大纲（16 页）

### 01 · 封面
- title：LDA —— 开源、Agent 原生的光子与量子芯片设计平台
- type：cover / role：hero / rhythm：peak / layout：全屏视觉+大标题
- visual：L1 满版 Navy 底 + 左侧 Cyan 光子波导几何线条（SVG 线性装饰，占左 40%）；主标 + 副标 + 版权方
- visual_role：anchor / density：字数约 60 / 图片 0 / 留白约 35%
- anti_pattern：禁止居中海报、禁止金红剪影、禁止满版照片
- description：主标「LDA · 光子与量子芯片的 Agent 原生设计大脑」；副标「开源 · 验证可证伪 · 主权自主 —— 对标 EDA 的下一代设计基础设施」；落款「上海杜特企业管理咨询有限公司 · 杜玉河 · v0.9.40」。

### 02 · 目录
- title：本次汇报的四个部分
- type：catalog / role：supporting / rhythm：transition / layout：目录（4 条目）
- visual：L3 仅页码 / density：字数约 120 / 留白约 30%
- anti_pattern：禁止圆球编号、禁止书法繁体、禁止单列大目录
- description：01 机会与痛点（Why Now）｜02 LDA 是什么（产品与技术）｜03 为什么是我们（差异化与可信）｜04 市场 · 商业 · 团队。每条含编号 + 章节名 + 一句话摘要。

### 03 · 章节扉页 01
- title：机会与痛点
- type：section / role：transition / rhythm：transition / layout：章节扉页（巨字 01 + 标题）
- visual：满铺 `#062032` + 左侧 160–320px 低透明白字「01」 / density：字数约 20
- anti_pattern：禁止图片、渐变、金色、Cyan 装饰
- description：英文副标「Why Now — 光子与量子设计的范式拐点」。

### 04 · 光子与量子设计正处范式拐点
- title：AI 算力把光子与量子设计推上指数曲线，工具链却仍是旧范式
- type：content / role：supporting / rhythm：valley / layout：巨型数字+洞察
- visual：大数字 CAGR 组合（≥48px）+ 右侧洞察；visual_role：anchor
- density：字数约 200 / 留白约 20%
- anti_pattern：禁止等宽卡片横排；禁止把核心数字塞进图表卡角落
- description：数据落点——① 光子 EDA 软件市场 2025 约 18 亿美元，2026–2034 CAGR 13.5%，其中量子计算应用子段 22.4% 最快；② CPO 模块市场 2025 5.6 亿美元 → 2032 326.8 亿美元（CAGR 76.5%）。**判断**：这不是线性增长，而是算力需求驱动的范式切换；工具链需求将同步爆发，但现有工具仍是「人写脚本 + 商业求解器黑盒」的旧范式，供给与需求错配。Source：Dataintelo / PMarketResearch 2026。

### 05 · 现有工具留下三道结构性空白
- title：现有光子 / 量子设计工具存在三道无法靠补丁填补的空白
- type：content / role：supporting / rhythm：valley / layout：左标题+右内容（右为 SVG 问题树 ⑨c）
- visual：右侧 SVG 问题树（1 核心问题 → 3 空白叶子），Navy 单色阶 + Cyan 高亮；visual_role：evidence
- density：字数约 180 / 留白约 22%
- anti_pattern：禁止四卡片预览；禁止铺满正文段落
- description：三道空白——① 验证不独立：PASS/FAIL 由商业求解器黑盒或人判断，不可证伪；② 非 Agent 原生：设计靠专家手写脚本，AI 只做辅助而非设计主体；③ 主权依赖：高端求解器（Lumerical/Tidy3D）受许可与地缘约束，国产替代缺「自主可验」底座。**判断**：这三点是结构性空白，不是功能缺口，现有商业工具的架构决定其补不上。

### 06 · 章节扉页 02
- title：LDA 是什么
- type：section / role：transition / rhythm：transition / layout：章节扉页（巨字 02）
- visual：满铺 `#062032` + 低透明白字「02」
- anti_pattern：禁止图片、渐变、金色、Cyan
- description：英文副标「Product & Technology — Agent 原生的光子 + 量子 PDA」。

### 07 · LDA：Agent 原生的光子+量子 PDA（Hero）
- title：LDA 是开源、Agent 原生的光子与量子芯片设计平台，设计闭环全程可验
- type：content / role：hero / rhythm：peak / layout：非对称双栏（左 60% 架构闭环图，右 40% 文字）
- visual：左 SVG 闭环图（设计→仿真→版图→DRC/LVS→工艺角→几何寄生，Navy 节点 + Cyan 回路）；visual_role：anchor
- density：字数约 160 / 留白约 25%
- anti_pattern：禁止 50:50 等分双栏；禁止把架构图缩小为 200×70
- description：一句话定位——「LDA = 光 PDA + 量 QEDA，开源优先、Agent 原生、核心由 AI 自写」。右栏三句：① 覆盖光子（15+ 引擎）与量子（7 引擎）双栈；② 22 类引擎 + 11 包，口径=设计品类；③ 闭环每一步都落到可量化判据。**判断**：别人卖「工具」，LDA 交付「可证伪的设计闭环」。

### 08 · 验证红线：结果由物理定律与大数据锚定
- title：验证红线：PASS/FAIL 由物理定律锚与实证大数据锚判定，大模型不进判决路径
- type：content / role：supporting / rhythm：peak（视觉强）/ layout：上大图+下方卡片（上 SVG 闭环判据图，下 3 卡）
- visual：上 SVG 双路径判据图（物理定律锚 / 实证大数据锚 → 死标量比对 → PASS/FAIL）；下 3 卡（不进判决 / 双向标定 / 全绿≠无失真）；visual_role：evidence
- density：字数约 190 / 留白约 22%
- anti_pattern：禁止把判据图做成整张 PNG；禁止装饰性竖条悬空
- description：核心可信叙事——① LLM 只做生成与对话，判决落「非 AI ground」（物理定律 + 实证锚），死标量比对定 PASS/FAIL；② 判据 D（v0.9.27）：残差≡0 且扰动无响应、双向标定，杜绝「假独立」自证桩；③ 全绿≠无失真（v0.9.10 漏算 3.01dB 在 84 全绿下溜过），故设反向测试护栏。**判断**：可信比聪明重要——这是投资人敢信账本的前提。

### 09 · 核心账目：50 锚 · 22 引擎 · 97 CI
- title：账本即证据：50 道验证锚、22 类引擎、97 条 CI 全绿，构成可审计底座
- type：content / role：supporting / rhythm：valley / layout：巨型数字+洞察（4 组 KPI 大数）
- visual：大数字 KPI：50 锚 / 22 引擎 / 97 CI core / 58 货架；visual_role：anchor
- density：字数约 150 / 留白约 20%
- anti_pattern：禁止等宽卡片横排；禁止小字号堆数据
- description：数据落点——50 锚（25 严格独立 / 0 降级 / 25 自证桩，双路径披露）；22 引擎（光 15 + 量 7）+ 11 包 = 33 类；97 条 CI core 冒烟全绿、0 SKIP/0 FAIL；58 货架超市。**判断**：这不是 demo 数量，而是「每句能力宣称都有锚点背书」的工程纪律，是开源社区与 B 端客户信任的硬基础。

### 10 · 章节扉页 03
- title：为什么是我们
- type：section / role：transition / rhythm：transition / layout：章节扉页（巨字 03）
- visual：满铺 `#062032` + 低透明白字「03」
- anti_pattern：禁止图片、渐变、金色、Cyan
- description：英文副标「Differentiation & Credibility — 现有工具补不上的空白」。

### 11 · 全球对比：开源+Agent 原生+验证独立是别家没有的
- title：对比全球工具，LDA 占据「验证独立 + 主权自主 + Agent 原生」的结构性空白
- type：content / role：supporting / rhythm：valley / layout：图表+洞察（Table 对比矩阵 + 右侧洞察）
- visual：Table 7 行（LDA / gdsfactory / Meep / Luceda / Lumerical / Tidy3D / COMSOL）×维度（开源 / Agent 原生 / 验证独立 / 主权 / 成熟度）；visual_role：evidence
- density：字数约 170 / 留白约 20%
- anti_pattern：禁止红绿装饰对比；禁止把表做成图片
- description：数据落点——LDA 在「开源 + Agent 原生 + 验证独立 + 主权自主」4 维全 ✅，商业标杆（Lumerical/Tidy3D）在验证独立/主权维度受限；gdsfactory/Meep 开源但不验证独立、非 Agent 原生。**判断（诚实）**：LDA 列第 1 不是精度超越商业标杆（成熟度仍低、未流片），而是「验证独立 + 主权自主 + Agent 原生」是现有工具的结构性空白——这是差异化维度，不是精度维度。商业求解器定位为外部 ORACLE 基准而非黑盒真理。

### 12 · 主权纪律：求解器自主可控，不卡别人脖子
- title：主权纪律：高端求解器要么自主、要么隔离外挂，绝不让许可卡住设计闭环
- type：content / role：supporting / rhythm：valley / layout：左大图+右侧文字（左 SVG 三级依赖图 A/B/C，右文字）
- visual：左 SVG 三级依赖图（A 级永不借 / B 级借今踢后 / C 级第一天自主）+ Meep GPL 隔离、Tidy3D ORACLE 锁标注；visual_role：evidence
- density：字数约 170 / 留白约 22%
- anti_pattern：禁止把依赖图做整张位图；禁止 50:50 等分
- description：数据落点——A 级（核心求解/判决）永不借外部；B 级（gdsfactory/KLayout/SAX）借今踢后；C 级（Tidy3D 仅外部 ORACLE）第一天自主；Meep=GPL v2 已隔离（subprocess 只回标量）。**判断**：在出口管制与许可风险下，「自主可验」是国产光量子设计底座的刚需，LDA 从架构第一天就为此设计。

### 13 · 章节扉页 04
- title：市场 · 商业 · 团队
- type：section / role：transition / rhythm：transition / layout：章节扉页（巨字 04）
- visual：满铺 `#062032` + 低透明白字「04」
- anti_pattern：禁止图片、渐变、金色、Cyan
- description：英文副标「Market · Business · Team — 机会与路径」。

### 14 · 市场机会：AI 算力把光子 EDA 推向指数曲线（Hero）
- title：市场拐点已至：光子 EDA 与 CPO 同步爆发，开源 + 云交付正重写获客规则
- type：content / role：hero / rhythm：peak / layout：图表+洞察（左 Chart 柱/组合，右洞察）
- visual：左 Chart（光子 EDA 市场 2025→2034 柱 + CPO 模块 2025→2032 线，双轴示意）；visual_role：evidence
- density：字数约 170 / 留白约 22%
- anti_pattern：禁止 3D 饼图；禁止数据无 Source
- description：数据落点——① 光子 EDA 软件 2025 约 18 亿美元、CAGR 13.5%，量子应用子段 22.4% 最快；② CPO 模块 2025 5.6 亿 → 2032 326.8 亿美元（CAGR 76.5%）；③ 云交付把永久许可 15–50 万美元 → 2500 美元/座/月，用户 2022–2025 +42%，开源（GDSFactory/KLayout）已成商业厂商结构性威胁（镜像 OpenROAD 颠覆电子 EDA 低端）。**判断**：LDA 站在这三条曲线（算力需求 / 开源替代 / 云交付）的交叉点，获客与变现逻辑被重写。Source：Dataintelo / PMarketResearch / 中研普华 2026。

### 15 · 商业模式与路线图
- title：商业模式：开源核心建生态护城河，企业版与 PDK 服务变现；路线图直指真实流片
- type：content / role：supporting / rhythm：valley / layout：非对称双栏（左商业模式 3 卡，右时间轴路线图 ⑨h）
- visual：左 3 卡（开源核心 / 企业版+服务 / 生态市场）；右 SVG 横向时间轴（A 期已发布 → B 期生态播种 → C 期真实 PDK/流片）；visual_role：evidence
- density：字数约 190 / 留白约 22%
- anti_pattern：禁止等宽卡片横排堆砌；禁止路线图画成图片
- description：数据落点——商业模式对标 Red Hat / HashiCorp「开源核心 + 企业订阅」：核心求解与设计链 Apache-2.0 开源获客，企业版（私有部署 / 合规 / SLA）+ PDK/工艺服务变现。路线图：A 期（已发布 v0.9.40，50 锚/97 CI）；B 期（生态播种、真实 PDK 接入）；C 期（真实流片闭环、商业客户 Pilot）。**判断**：护城河 = 标准 + 生态 + PDK 供给，开源是获客引擎而非盈利终点。

### 16 · 团队与联系（结束页 / Hero）
- title：与 LDA 一起，定义光子与量子芯片设计的下一代基础设施
- type：ending / role：hero / rhythm：peak / layout：左标题+右内容（右联系卡）
- visual：左大标 + 光子电路几何；右联系卡（公司 / 联系人 / 电话 / 微信 / 邮箱 / 仓库）；visual_role：anchor
- density：字数约 140 / 留白约 28%
- anti_pattern：禁止居中海报；禁止装饰过度
- description：落款——版权所有：上海杜特企业管理咨询有限公司；联系人：杜玉河；电话 13311602075；微信 gongyhlw；邮箱 duyuhe@shdute.cn；仓库 gitee.com/i4hub/LDA · github.com/iduyuhe/LDA；白皮书可下载。邀请：试用 / 对接 / 投资，欢迎联系。
