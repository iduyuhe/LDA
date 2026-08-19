# LDA 竞争格局态势报告

> 文档编号：LDA-MC-002
> 版本：v1.0（动态竞争态势与监控稿）
> 编制日期：2026-08-14
> 数据检索日期：2026-08-14（WebSearch / WebFetch 实证）
> 配套文档：《LDA 市场竞争与赛道分析》（MC-001，赛道格局视角）
> 密级：内部 · 暂不对外
> 编制说明：本报告定位为 MC-001 的**动态、战术补件**——聚焦玩家最新动作、威胁演化、真空格守卫与可月度追踪的监控指标。所有数据均附可访问来源 URL；未核实者标「待补」，严禁编造。

---

## 1. 执行摘要

光子芯片设计（PDA）+ 量子芯片设计（QEDA）的竞争版图在 **2025 年内发生了三件结构性突变**，使本报告比 MC-001 更具"动态战术"价值：

1. **巨头阵营重组**：Synopsys 以约 350 亿美元完成对 Ansys 的收购（2025-07-17 交割），**Lumerical 现归 Synopsys**；作为监管附带条件，Synopsys 又把光学解决方案事业群（含 **RSoft**、CODE V、LightTools）卖给 **Keysight**（2025-10-17 交割）。MC-001 中"三巨头"的份额分布（Synopsys 23% / Ansys 16% / Cadence 9%）已被实质性改写——光子仿真 IP 被拆成 **Lumerical（Synopsys）vs RSoft（Keysight）** 两截。
2. **国产 PDA 出现"主权玩家"**：**广立微（Semitronix, 301095.SZ）于 2025-08-12 以 4000 万欧元收购 Luceda（IPKISS）100% 股权**。这意味着一款源自 imec、覆盖多材料平台的 PDA 全流程工具，已落入中国上市公司之手——既是 LDA"主权优先"叙事的盟友，也是潜在的商业竞品。
3. **Agentic 威胁从论文走向产品**：PhIDO（arXiv:2508.14123，多伦多/马普/gdsfactory/MIT）证明"自然语言→GDSII 掩模"可行，但作者自己把"standardized knowledge representations（统一知识表示）"列为下一步——**这正是 LDA 的 L0 IR 真空格**。Cadence JedAI / Synopsys AgentEngineer（Autopilot）则把 agentic 做成**封闭商业工具的编排层**，结构性不会做开放标准。

**核心判断**：LDA 的真空格（统一 IR + Agentic + 国产自主 + 光子/量子融合）在 2025 年后不仅未被填，反而因巨头重组、国产玩家成型、PhIDO 验证需求而**更清晰、更紧迫**。窗口约 12–24 个月，关键动作是先用 RFC + PDK 联盟 + 基准 harness 锁死开放标准。

**最该喂给战略/融资防御的 3 条**：
- BIS 在 2025-05 至 2025-07 真实上演了"对华 EDA 断供→恢复"的**周期性扭曲**，LDA 主权 thesis 已被实证背书（见 §4.2）。
- 巨头 agentic 路线是**封闭工具之上的编排层**（JedAI / AgentEngineer），不做中立开放 IR，存在商业模式自噬（见 §4.1、§5）。
- 广立微+Lucida 是中国主场最现实的 PDA 对手/伙伴变量，需在 BD 中主动定位（见 §2.1、§5）。

---

## 2. 竞争态势矩阵

> 标注：`[S]`=已核实份额/收入；`[A]`=已核实最新动作；`[待补]`=未检索到实证的字段。所有来源见各单元格末 URL。

### 2.1 PDA 巨头与专业商

| 玩家 | 定位 | 份额/体量 | 最新动作（2025–2026） | 对 LDA 含义 |
|---|---|---|---|---|
| **Synopsys** | OptoCompiler（唯一"电子+光子"统一设计平台）+ OptSim；光子器件仿真原 RSoft | [S] MC-001 估 ~23%；2024 中国营收占其总营收 **16%** | 2025-07-17 完成收购 **Ansys（≈350 亿美元，EDA 史最大并购）**，**Lumerical 现归 Synopsys**；2025-10-17 将光学事业群（RSoft/CODE V/LightTools）剥离给 **Keysight**。Agentic：发布 **AgentEngineer™**（五级路线图，L5=Autopilot），DAC 2025 首发基于 Microsoft Discovery 的原型 | 光子仿真 IP 被拆家；agentic 封闭化、与商业工具强绑定，不做开放 IR |
| **Cadence** | Virtuoso 光子扩展 + 全栈 EDA 老大 | [S] MC-001 估 ~9%；2024 中国营收占 **12%** | Agentic 平台 **JedAI**（统一数据/AI 框架，支持 MCP/A2A、本地开源权重）+ **AgentStack**（ChipStack/InnoStack/ViraStack、**Cerebrus AI Studio=L4** 代理式物理设计）。CadenceLIVE China 2025：SVP Paul Cunningham 称 **>50% 芯片设计已用 AI agent，预计 2 年内 >80%**；Q2 2025 积压订单 64 亿美元 | 最激进的封闭 agentic 编排者；用 MCP/A2A 但锁死自家工具，不中立 |
| **Ansys Lumerical** | FDTD / INTERCONNECT / CML Compiler 光子求解 | [S] MC-001 估 ~16%（已并入 Synopsys） | 随 Ansys 被 Synopsys 收购（2025-07-17），**Lumerical 现为 Synopsys 资产**；Ansys Engineering Copilot（GenAI 仿真助手）已随收购并入 Synopsys | 不再独立玩家；MC-001"被美单独点名剥离"表述需修正——剥离的是 RSoft（→Keysight），非 Lumerical |
| **Luceda（IPKISS）** | 全流程 PDA（Python），imec 系，多材料平台 | [S] 2024 营收 380 万欧元、2025 营收 420 万欧元；**2025-08-12 被广立微以 4000 万欧元收购 100%** | 最新 **Luceda 2025.12**（2025-12 发布）：PDK 快速构建、Signal Tracer、P&R 增强、dummy fill。PDK 覆盖 imec iSiPP、AMF、CompoundTek、GF Fotonix、AIM、IHP 等 | **中国上市公司控股的 PDA 工具**——主权叙事盟友，亦是商业竞品；非 agentic、非开放 IR |
| **PhotonD** | PIC 设计自动化初创（PhotonDelta 生态） | [待补] | 最新融资/产品动态待补 | 欧洲光子生态玩家，BD 需跟踪 |
| **VPIphotonics** | 系统级+器件级光子仿真（德国，25+ 年） | [待补] 商业；中国由**凌云光（Luster, 688400.SH）**代理 | **Design Suite v11.6**（OFC 2025 发布）、**v11.7**（2025）聚焦 800G/1.6T DCI、TFLN、相干系统；与 Keysight 仪表联仿 | 系统仿真强、布局弱；与 LDA 可互补（仿真后端），不占 IR 层 |

**战略含义**：PDA 商业版图正从"Synopsys/Cadence/Ansys 三足"演化为"**Synopsys（含 Lumerical）+ Cadence + Keysight（含 RSoft）+ 广立微-Luceda（中国）**"四极。LDA 不与任一在"工具功能"上正面对抗，而做它们的**中立编排标准层**。

### 2.2 开源生态

| 玩家 | 定位 | 许可证 | 最新动作（2025–2026） | 对 LDA 含义 |
|---|---|---|---|---|
| **gdsfactory** | Python 版图/PDK/DRC/LVS，开源布局层基座 | MIT | **9.14.2（2025-09-12）**，更新线已至 **9.42.0**；**2M+ 下载、81 贡献者、25 PDK**；已扩展至 Photonics/Analog/Quantum/MEMS。GDSFactory+ 订阅提供 NDA PDK | LDA 的 L3 实现层基础设施；**PhIDO 即构建于 gdsfactory 之上**（Joaquin Matres 为共同作者） |
| **Meep** | 开源 FDTD 电磁求解 | GPL-2.0 | 持续维护（MC-001 已载）；作为 LDA MVP 期 ORACLE | GPL 红线：仅外部进程调用，不进研发产品代码 |
| **KLayout** | 版图查看/编辑 | GPL-3.0 | 稳定；KQCircuits 构建于其上 | GPL 红线同上 |
| **SAX** | 基于 JAX 的 S 参数电路仿真+可微优化 | Apache-2.0 | **0.16.6（2026-02）**，活跃（479 commits）；支持 autograd/XLA、与 gdsfactory 联动 | Apache 许可可 vendor 进商业；可作 LDA 电路级求解/可微优化后端 |
| **Nazca** | 开源 PIC 版图（荷兰 Bright Photonics，基于 KLayout/OpenAccess） | [待补] | 版本/许可证待补 | 布局层同类，LDA 可借力，非竞品 |

**战略含义**：开源已"挤占"商业布局层毛利——gdsfactory 2M+ 下载 + SAX 可微优化说明**版图/电路仿真这一层正快速商品化**。这正是巨头不愿下沉、而 LDA 应站在肩上做标准层的原因。

### 2.3 QEDA（量子芯片设计自动化）

| 玩家 | 定位 | 性质 | 最新动作（2025） | 对 LDA 含义 |
|---|---|---|---|---|
| **EDA-Q** | 全栈超导量子芯片 EDA（拓扑→等效电路→版图→器件映射→布线→工艺映射→仿真） | 学术/国产（作者中国团队；arXiv:2502.15386，2025-04-17 v5；**IEEE TCAD 2025-06-17 发表**） | 对比表显示其为**唯一覆盖"器件映射 + 工艺映射"**的 QEDA 工具；"Origin Unit"平台同表出现（指向本源） | 验证 MC-001"全栈空白被补齐"判断；但**非 agent-native、非开放 IR、非光子融合** |
| **本源坤元** | 国产量子芯片 Q-EDA（本源科仪/本源量子全资子公司） | 商业/国产 | **第 5 次迭代（2025-05-30）**：72 比特版图 6 分 50 秒；千万级网格建模；覆盖**超导+半导体**双体系 | 国产 QEDA 标杆；潜在伙伴（主权协同），但封闭、非 agentic |
| **量旋天乙（SpinQ Tianyi）** | Web 端超导量子芯片 EDA | 商业/国产（量旋科技） | 参数化器件 + 自动布线，研发周期缩短 **40%**；覆盖 20+ 比特"少微"芯片 | 轻量化 QEDA，教育/原型场景；非全栈、非开放 |
| **Qiskit Metal（现 Quantum Metal）** | IBM 开源量子器件设计→哈密顿量 | 开源（仍 alpha） | 更名 Quantum Metal；Python API + 可选 GUI；渲染至 Ansys HFSS/Gmsh；社区 Quantum Device Consortium 托管 | 国际开源 QEDA 基座；LDA 量子侧可借力，非竞品（无 agentic 编排） |
| **KQCircuits** | IQM 开源量子版图（基于 KLayout） | 开源（IQM） | 图形化版图强；EDA-Q 对比表列为局部覆盖工具 | 版图层同类 |
| **IQM** | 芬兰量子硬件公司 + KQCircuits | 商业/开源混合 | 持续扩展量子处理器；与晶圆厂合作 | 硬件为主，QEDA 为其配套 |

**战略含义**：QEDA 全球仍处"局部工具 + 少数全栈雏形"阶段，**无一家做 agent-native + 光子/量子统一 IR**。EDA-Q 补了全栈但非 agentic；本源/量旋是国产但封闭。LDA 量子侧真空格未被占。

### 2.4 Agentic 新锐（最核心威胁层）

| 玩家 | 定位 | 开放性 | 最新动作 | 对 LDA 真空格的威胁评级 |
|---|---|---|---|---|
| **PhIDO**（arXiv:2508.14123） | 多智能体框架：自然语言→GDSII 掩模 | 论文（学术，构建于 **gdsfactory**） | 多伦多+马普+**gdsfactory（Joaquin Matres）**+MIT+Axiomatic_AI；单器件成功率 **91%**，≤15 组件 ~**57%**；作者把"**standardized knowledge representations**"列为下一步 | **高（最接近）**：证明需求真实，但**光子-only、薄私有 YAML、非量子融合、非中立开放 IR** |
| **Cadence JedAI / AgentStack** | 商业工具之上的 agentic 编排层 | 封闭（锁自家工具） | JedAI 支持 MCP/A2A 但仅连 Cadence 产品；Cerebrus AI Studio=L4 | **低（非真空格）**：商业模式决定不做中立开放标准 |
| **Synopsys AgentEngineer / Autopilot** | 商业工具之上的多智能体（L5=Autopilot） | 封闭（锁自家工具） | DAC 2025 与 Microsoft Discovery 首发原型；五级路线图 | **低（非真空格）**：同上，且已与 Ansys 深度绑定 |

**威胁评级小结**：唯一可能侵占 LDA 真空格的是 **PhIDO 类学术 agentic 框架**——但它们自己点名缺"统一知识表示"，恰是 LDA 的 L0。巨头 agentic 因"商业模式自噬"结构性不会做开放 IR（详见 §5）。

---

## 3. 份额与收入态势

### 3.1 光子 EDA 收入集中度（动态修正 MC-001）
- MC-001 沿用"三巨头占光子 EDA 收入 ~52%（Synopsys 23% / Ansys 16% / Cadence 9%）"。
- **2025 重组后**：Ansys（含 Lumerical）并入 Synopsys → Synopsys 光子相关份额实质升至 ~39%；RSoft 系剥离给 Keysight；Cadence 维持 ~9%。**集中度不降反升，且光子仿真求解被拆为 Lumerical(Synopsys) 与 RSoft(Keysight) 两截**，客户集成成本上升。
- 全球 EDA 总盘（2024）：Synopsys 31% / Cadence 30% / Siemens 13% = **74%**（来源：TrendForce，经财新/南方都市报转引，2025-07）。
- 中国 EDA 市场：三大外资曾占 **>80%**；国产 EDA 份额从 2020 年 ~11.5% 升至 **>20%**（来源：赛迪智库/芯智讯，2025-07）。**LDA 主权叙事的市场基础正在扩大**。

### 3.2 开源如何挤压商业空间（可量化信号）
- **gdsfactory：2M+ 下载、81 贡献者、25 PDK、版本 9.42.0**——版图/PDK/DRC/LVS 这一层已商品化，商业 PDA 的"布局层毛利"被持续侵蚀（来源：PyPI 9.8.1/9.14.2 页，2025）。
- **SAX（Apache-2.0，0.16.6）** 提供可微 S 参数电路优化，进一步把"电路级仿真"开源化。
- **结论**：商业 PDA 被迫向两头退守——**上游卖求解器内核（Lumerical/RSoft 物理深度）+ 下游卖 NDA PDK 与签核合规**（如 gdsfactory 的 GDSFactory+ 订阅）。中间布局/电路层正被开源吞掉。**这正是 LDA 应占的"标准编排层"两侧：上接开源求解、下接晶圆厂 PDK，自己定义中立 IR。**

### 3.3 产业牵引（光子器件高增长的战略价值）
- 硅光市场：Yole 预测 **2024 年 14 亿美元 → 2031 年 61 亿美元，CAGR 22.4%**（来源：eet-china 广立微收购 Luceda 报道，2025-08）。
- 受 AI 数据中心 800G/1.6T 拉动，硅光器件 2025 增速 37%+（MC-001 已载，与产业报道一致）。

---

## 4. 动态威胁监控

### 4.1 巨头 Agentic 路线会占 LDA 真空格吗？——**不会，结构性不能**
- **证据**：Cadence JedAI / AgentStack、Synopsys AgentEngineer 均为**自家商业工具之上的编排层**（JedAI 用 MCP/A2A 但只接 Innovus/Tempus/Jasper/Xcelium/Virtuoso 等 Cadence 产品；AgentEngineer 绑定 Synopsys+Ansys 栈）。其 agentic 价值主张是"在真实约束下优化、验证、执行"——**前提是用户已被锁在商业工具内**。
- **商业模式自噬**：若巨头做"中立、可插拔、能调所有现存工具"的开放 IR（即 LDA 的 L0/L1），等于**把自家工具的差异化毛利商品化**，与license 收入模型冲突。因此巨头只会做"封闭 agentic"，不会做"开放标准层"。
- **结论**：巨头 agentic 是 LDA 的**下游被编排对象**，不是真空格竞争者。监控重点是"巨头是否突然转向开放 IR"——概率低但破坏力大（见 §7 指标 4）。

### 4.2 美国 BIS 出口管制对竞争的周期性扭曲（**已被 2025 实证**）
- **时间线**：
  - 2025-05-23/29：BIS 向 Synopsys、Cadence、Siemens EDA 发"Is informed"函，要求对华出口 EDA 软件（ECCN **3D991 / 3E991**）须申领许可，实质上**断供约 5 周**（来源：商务部口径/财新/凤凰网，2025-07）。
  - 2025-07-02 至 07-04：BIS 撤销限制，三家**全面恢复对华供应**（来源：同上）。
- **对竞争的扭曲效应**：
  - 断供期：A 股 EDA（华大九天/广立微/概伦）反向大涨；恢复后回落——说明**政策风险已被市场定价为"国产替代催化剂"**。
  - Synopsys 2024 中国营收占 16%、Cadence 占 12%——**任何反复都会重创其中国收入，同时加速国产/开源替代**。
- **对 LDA 的含义**：LDA"主权优先、不借美系商业工具"的 thesis 不是假设，是**已被 2025 事件验证的刚需**。BIS 风险是 LDA 融资防御的 strongest narrative。

### 4.3 政策与主权风险清单
| 风险 | 状态 | 来源 | LDA 应对 |
|---|---|---|---|
| BIS 对华 EDA 许可反复 | 2025 已上演"断→恢复"，未来可能再发 | 财新/凤凰网 2025-07 | 主权依赖 A/B/C 分级已落地（白皮书 §7）；B 级 fork/镜像/冷备 |
| GitHub/PyPI 对华可及性 | 间歇性不可达（本 Agent 沙盒已实测） | LDA 白皮书 §7.2 | 本地为根 + Gitee 门面，已建 i4hub 仓 |
| 信创/自主可控目录纳入 | 政策鼓励国产 EDA | MC-001/白皮书 | 主权叙事对齐，争取目录/补贴 |
| 广立微-Luceda 国产 PDA 成型 | 已发生（2025-08） | eet-china | 主动 BD：伙伴 or 差异定位（见 §5） |

---

## 5. LDA 真空格守卫

### 5.1 真空格定义（四要素交集）
**统一开放 IR（L0） + Agentic 原生（L1） + 国产自主可控 + 光子/量子融合** —— 四个条件的交集，当前无人占。

### 5.2 为何巨头结构性不能做（商业模式自噬，展开论证）
1. **Synopsys/Cadence/Keysight** 的收入来自**商业 license + NDA PDK + 签核合规**。开放、中立、可插拔的 IR 会让用户用脚投票离开其工具栈 → 自断财源。**它们只会把 agentic 做成"锁定层"，不会做成"标准层"**（§4.1 证据）。
2. **光子/量子融合**对巨头是"非核心交叉小市场"：Synopsys 光子是电子 EDA 延伸，量子不是其战略主线；做统一 IR 投入大、回报不确定，且会得罪各自独立的产品线（光子组 vs 量子组 vs 系统组）。
3. **国产自主**与美系巨头地缘立场根本冲突——它们恰恰是 BIS 管制对象，不可能为"去美系依赖"建标准。

### 5.3 为何开源（gdsfactory 等）未占
- gdsfactory 是**布局层**，已成熟且 MIT 友好，但**定位是"版图引擎"不是"知识表示标准"**；其 YAML 是私有序列化，非跨光子+量子的开放 IR。
- PhIDO 已点名"standardized knowledge representations"为下一步缺口——**gdsfactory 自己没补，PhIDO 也没补（仍薄私有 YAML）**。

### 5.4 国产玩家（广立微-Luceda、本源坤元、量旋）为何未占
- **广立微-Luceda**：商业闭环、封闭 license、非 agentic、非量子融合。它是 LDA 在"PDA 主权"上的**盟友/潜在竞品**，但商业模式使其不会做开放 IR。
- **本源坤元/量旋天乙**：量子侧、封闭、非 agent-native、非光子融合。
- **EDA-Q**：全栈但学术、非 agentic、非开放 IR、非融合。

### 5.5 守卫战术（actionable）
- **抢标准**：以 RFC 流程先发锁定 L0 IR 草案 + L1 协议（白皮书 §9 已规划）；把"光子+量子统一"作为不可协商的差异化。
- **抢生态**：用 PDK 联盟（NOEIC/CUMEC/SITRI）把"自主可控"牌打穿；广立微-Luceda 可作为**主权伙伴**而非敌人——推动其 IPKISS PDK 接入 L0 IR 而非另起炉灶。
- **抢信任墙**：基准 harness + 反向悬赏（白皮书 §6.3）——这是巨头和学术框架都懒得建的"苦活"，却是 LDA 护城河。
- **抢时间**：12–24 个月窗口内，任何"PhIDO 类框架 + 某开源 IR"的组合都可能抢标。LDA 必须先发布**可被社区引用的 L0 IR 标准**。

---

## 6. 竞争态势演化预测（未来 1–3 年）

| 时间窗 | 预期演化 | LDA 应对窗口 |
|---|---|---|
| **0–12 月** | PhIDO 类学术 agentic 框架增多（光子-only）；Cadence/Synopsys agentic 产品化（封闭）；广立微-Luceda 开始中国化整合；BIS 管制可能再反复 | **锁 L0 IR RFC + 首个 PDK 承诺 + 基准 harness v1** |
| **12–24 月** | 可能出现"PhIDO + 某开源 IR"的开放标准竞争者，或巨头被迫部分开放接口（防御性）；国产 QEDA（本源/量旋/EDA-Q）走向工程化；硅光器件 CAGR 22% 拉动 PDA 需求 | **L2 PDK Registry 成型 + 量子侧 L0 子集启动 + 社区网络效应** |
| **24–36 月** | 光子/量子融合设计需求随光量子/光电共封装（CPO）升温；若 LDA 未锁标准，标准话语权可能旁落（巨头防御性开放 or 学术联盟） | **阶段 2 统一跨域 IR + 商业化认证版（红帽模式）** |

**关键不确定性**：① BIS 是否再发管制（高影响、不可控）；② 广立微-Luceda 是否自建 agentic 层（中影响、可 BD 化解）；③ PhIDO 类是否抢先定义开放 IR（高影响、靠先发压制）。

---

## 7. 监控指标体系（供「LDA 领域研究室」月度追踪）

> 对接《LDA 领域研究室章程》§3.1 四类专项追踪。每条指标标注**数据来源建议**与**预警阈值**。

### 指标 1 · 份额与收入变动
- 1.1 Synopsys/Cadence/Siemens/Keysight 光子 EDA 相关营收与对华占比（财年披露）→ 来源：各公司 10-K/财报、TrendForce。
- 1.2 gdsfactory 累计下载量/贡献者数/PDK 数（PyPI、GitHub）→ 阈值：贡献者 <70 或版本停滞超 3 月则标黄。
- 1.3 广立微-Luceda 整合进展（公告、营收）→ 来源：301095 年报/互动易。
- 1.4 国产 EDA 在华份额（赛迪/半导体协会）→ 阈值：>25% 为 LDA 利好信号。

### 指标 2 · 新融资 / IPO
- 2.1 光子/量子 EDA 初创融资（PhotonD、PhotonDelta 组合、国内 PDA 初创）→ 来源：Crunchbase、IT 桔子、新闻。
- 2.2 相关 IPO 进度：曦智（2026 IPO）、图灵量子（拟 A 股）等 → 来源：交易所公告、招股书。
- 2.3 LDA 自身融资/社区指标（stars、contributor、PDK 承诺数）→ 内部。

### 指标 3 · 政策更新
- 3.1 BIS EDA 管制函（ECCN 3D991/3E991）任何新增/撤销 → 来源：BIS 官网、商务部口径、路透/财新。
- 3.2 信创/自主可控目录纳入动态 → 来源：工信部、地方工信厅。
- 3.3 GitHub/PyPI/arXiv 对华可及性（自动化探测）→ 来源：本 Agent 沙盒探测 + 公开状态页。
- **预警**：任一 BIS 新函 → 触发研究室"事件加急"简报（章程 §3.4）。

### 指标 4 · Agentic 新品发布
- 4.1 Cadence JedAI / AgentStack 新模块（尤其是否出现"开放接口/跨厂商"信号）→ 来源：CadenceLIVE、EE Times、Cadence 新闻。
- 4.2 Synopsys AgentEngineer / Autopilot 进展（是否开放标准）→ 来源：Synopsys 博客、DAC、SNUG。
- 4.3 PhIDO 及同类（多伦多组、MIT、Axiomatic_AI）新论文/开源 → 来源：arXiv（photonic IC design automation + agent）。
- 4.4 **关键预警**：任何"PhIDO 类 + 开放 IR 标准"组合出现 → 最高优先级，立即报主任。

### 指标 5 · 许可证变更
- 5.1 gdsfactory（MIT / GDSFactory+ NDA 模式是否收紧）→ 来源：PyPI、gdsfactory 许可页。
- 5.2 Meep / KLayout（GPL 是否升级或被替换）→ 来源：GitHub license、changelog。
- 5.3 SAX（Apache-2.0 是否变更）→ 来源：PyPI。
- 5.4 Luceda（广立微控股后许可是否对华友好/收紧）→ 来源：Luceda 公告。
- **预警**：GPL→更严 or MIT/Apache→闭源 → 触发主权策略复核（白皮书 §7）。

### 指标 6 · LDA 自身真空格健康度（每月自查）
- 6.1 L0 IR RFC 采纳数 / 外部贡献 PR 数。
- 6.2 接入 L0 IR 的晶圆厂 PDK 承诺数（NOEIC/CUMEC/SITRI）。
- 6.3 基准 harness 考题数 / 被外部引用次数。
- 6.4 竞品是否引用或兼容 L0 IR（生态话语权信号）。

---

## 附：数据置信度与待补清单
- **已实证（高置信）**：Synopsys-Ansys 收购与 RSoft→Keysight 剥离、BIS 2025 断供-恢复、广立微收购 Luceda、PhIDO(arXiv:2508.14123)、EDA-Q(arXiv:2502.15386 / IEEE TCAD)、gdsfactory 9.42.0/2M+下载、SAX 0.16.6、本源坤元第 5 迭代、量旋天乙、Cadence JedAI/AgentStack、Synopsys AgentEngineer、VPIphotonics 11.6/11.7。
- **待补（查无实证，需后续追踪）**：PhotonD 最新融资/产品动态；Nazca 版本与许可证；VPIphotonics 股权归属（是否被收购待核）；EDA-Q 作者具体机构归属（疑为本源量子系，待核实）；光子 EDA 软件 2025 精确收入（MC-001 估 13 亿美元，待第三方报告佐证）。
- 所有"份额"数值中，MC-001 沿用估计值在 2025 重组后已部分失效，本报告 §3.1 已做动态修正；**精确份额请以 TrendForce/赛迪年度报告为准**。

*本报告与《LDA 市场竞争与赛道分析》(MC-001)、《LDA 技术白皮书》、《LDA 发展里程碑与路线图》、《LDA 领域研究室章程》配套，供战略规划与融资防御使用。*
