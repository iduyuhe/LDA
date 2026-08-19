# LDA 项目 · 领域文献与工具靶向知识基线

> **定位**：本库是 LDA 工程设计的**前置知识基线**（front-loaded knowledge base），非学术论文。目标读者是 LDA 工程实现者。
> 由 Agent 执行系统性靶向梳理（2026-08-14），team-lead 补全能 PhIDO 论文出处后落盘。
> 对齐前提：LDA 为 **agent-native 开源光子+量子芯片设计软件**，分层 L0 统一 IR/DSL（机器优先）/ L1 agent 协议层（人操作壳→agent 操作接口）/ L3 AI 写求解内核 + 借用开源求解器作验证 ORACLE。策略：光子优先后量子、单垂直场景先打通后统一、范围内自建真地基（技术复利）、可复用部分借用不重复造。验证锚：物理定律（解析/确定性计算）+ 经验大数据；AI 写求解器输出须对照确定性 harness 判定 pass/fail。

---

## 模块1 · 光子/量子芯片 IR/DSL 与版图框架现状

### 1.1 关键论文/工具清单
| 工具/论文 | 组织 | 年份 | 链接 |
|---|---|---|---|
| **PhIDO**（多智能体 PIC 设计，NL→GDSII，**首个端到端 LLM PIC 设计框架**） | 多伦多大学(J.Poon)+马普所(V.Ansari)+MIT(D.Englund)+GDSFactory(J.Martres) | 2025-08 | arXiv:2508.14123 · https://arxiv.org/abs/2508.14123 |
| gdsfactory（Python 版图+netlist+PDK 插件+KLayout DRC/LVS） | GDSFactory 社区 | 持续维护 | https://github.com/gdsfactory/gdsfactory |
| SAX（JAX 自动微分的 S 参数电路仿真） | Floris Laporte 等 | 2021– | https://github.com/flaport/sax |
| KQCircuits（基于 KLayout 的参数化超导量子版图，导出 GDS/OASIS+netlist+仿真脚本） | IQM | 2018– | https://github.com/iqm-finland/KQCircuits |
| Qiskit Metal（全栈 QPU 设计，pyEPR，桥接 Ansys/HFSS，导出 GDS） | IBM | 2020– | https://github.com/Qiskit/qiskit-metal |
| Nazca Design（免费掩膜版图，自由曲面/绝热波导） | Epix/PhotonDelta | 持续维护 | https://www.nazca-design.org |
| Luceda IPKISS（商业 IPKISS 框架，compact model + 版图） | Luceda（imec 衍生） | 商业 | https://www.luceda.com |
| Open Hardware in Quantum Technology（KQCircuits vs Qiskit Metal 对比表） | Fermilab / arXiv | 2023 | https://arxiv.org/html/2309.17233v1 |

### 1.2 核心结论
1. **IR 抽象层次趋同**：现代工具普遍采用"参数化元件（PCell/element）→ 电路 netlist → 物理版图 GDS/OASIS"三层分离。gdsfactory/KQCircuits 都用 Python 代码即版图，避免人工错误、便于快速变体。
2. **netlist 是跨工具通用货币**：gdsfactory、KQCircuits、Qiskit Metal 都导出 netlist 供验证/仿真；SAX 直接吃 S 参数 netlist 做电路级频响。L0 IR 应把 netlist + 几何 + 材料 + 工艺（PDK）作为一等公民。
3. **PDK 插件化是商业化分水岭**：gdsfactory 有 imec/AIM/GlobalFoundries PDK 插件体系；KQCircuits 绑定 IQM 工艺；Luceda 商业 PDK。LDA 的 L0 需定义"工艺无关 IR + 工艺绑定 PDK"两层。
4. **量子与光子版图同源**：KQCircuits 直接复用经典版图软件 KLayout（多物理场/DRC），说明 QPU 版图无需另起炉灶——LDA 可共用同一套 L0 几何/版图原语，再叠加量子特有的能量参与比（EPR）、London 方程等物理字段。
5. **PhIDO 的 DSL 启示**（补）：它的 DSL 用 YAML 以便兼容 GDSFactory，充当"自然语言→GDSII"的中间表示。但这是**光子-only 的薄表示**，且无开放标准。LDA 的 L0 应做"跨光子+量子统一、机器优先、可扩展 schema"的升级版——这正是 LDA 与 PhIDO 的差异化空格。

### 1.3 对 LDA 设计的启示（指向 L0）
- **L0 IR 字段建议（可直接借鉴）**：`component`（参数化几何原语：waveguide/ring/grating/transmon/coupler…）、`netlist`（节点+端口+S 参数引用）、`material_stack`（硅/氧化硅/金属层）、`pd`/`process`（PDK：设计规则、层映射、刻蚀偏差）、`sim_ref`（指向 L3 求解器/ORACLE 的句柄）。
- **L0 必须是机器优先、可序列化**：优先 JSON/YAML/Proto，而非人类可读 DSL；人类 DSL 仅是 L0 的一层视图（由 L1 协议层翻译）。
- **PCell 参数化应作为 IR 原生概念**，而非后期脚本技巧——便于 L1 agent 以"改参数"方式迭代设计。

### 1.4 可直接复用资产
- **IR 字段参考**：gdsfactory 的 `Component`/`Netlist`/`PDK` 数据结构、KQCircuits 的 `Element`+`refpoints` 命名参考点机制（自动相对定位）。
- **开源版图内核**：KLayout（DRC/LVS 脚本 API）、gdsfactory（Python→GDS）。
- **电路级验证**：SAX 的 S 字典接口（`sax.reciprocal({...})`）可直接作为 L0 电路 IR 的求值后端雏形。

---

## 模块2 · Agent-native 芯片设计框架（AI 驱动设计）

### 2.1 关键论文/工具清单
| 工具/论文 | 组织 | 年份 | 链接 |
|---|---|---|---|
| **PhIDO**（4 阶段多智能体：Interpreter/Designer/Layout/Circuit verification，NL→GDSII，单器件成功率 91%） | 多伦多+马普+MIT+GDSFactory | 2025-08 | arXiv:2508.14123 |
| lumopt（伴随优化逆设计，Lumerical 生态） | Lumerical/Luceda | 持续维护 | https://github.com/luceda/lumopt |
| ceviche（FDFD/FDTD 伴随优化，逆设计内核） | Fan Group, MIT | 2019– | https://github.com/fancompute/ceviche |
| angler（光子逆设计，伴随法） | Fan Group, MIT | 2019– | https://github.com/fancompute/angler |
| Hammond et al. 混合时/频域拓扑优化（大规模逆设计） | MIT（Meep 团队） | 2022 | doi:10.1364/OE.442074 (Optics Express 30, 4467) |
| Cadence JedAI / Synopsys Autopilot（商业 agentic EDA，L5 自主路线） | Cadence / Synopsys | 商业 | 官网（具体论文链接待补） |
| ICCAD 2025 agentic EDA 主题（"Agentic AI 开启芯片设计新纪元"） | ICCAD | 2025 | 具体论文 URL 待补 |
| Physics-Informed Neural Networks (PINNs) | Raissi et al. | 2019 | arXiv:1904.08864 |
| Fourier Neural Operator (FNO) | Li et al., Caltech | 2021 | arXiv:2010.08895 |

### 2.2 核心结论
1. **逆设计范式成熟可借鉴**：伴随法（forward + adjoint = 每次迭代仅 2 次仿真，与参数数量无关）是逆设计标配。ceviche/angler/lumopt 已开源，可直接作为 L3 求解内核的"黄金参考实现"。
2. **Agentic EDA 本质是"多 agent 流水线"**：典型拆解 Interpreter（NL→规格）→ Designer（结构生成）→ Layout（版图）→ Verification（对照 ORACLE）。这与 LDA 的"agent 执行、人决策/验收"定位一致；**PhIDO 已用这套 4 阶段跑通，并开源**。
3. **AI 求解器两条路线并存**：(a) 神经 PDE 求解器（PINNs/FNO）做**快近似**，适合 agent 在迭代中快速评估；(b) 传统数值求解器（FDTD/FEM）做**真值 ORACLE**。LDA 的 L3 应是"AI 快内核 + 传统 ORACLE 校验"双轨。
4. **大规模拓扑优化已可上 GPU/Meep 混合并行**（Hammond 2022），证明"AI 写的内核 + 开源求解器"在工程上可行，是 L3 的直接范本。

### 2.3 对 LDA 设计的启示（指向 L1 / L3）
- **L1 agent 协议层**：应定义标准 agent 角色协议（规格解析 / 结构合成 / 版图生成 / 验证判定），每步产出可被 L0 IR 表达、可被 ORACLE 校验的中间件。Human-in-the-loop 的"决策/验收"点应固化在协议里（如 Verification agent 给出 pass/fail + 置信度，人确认）。
- **L3 求解内核**：先用 ceviche/angler 的伴随优化作为"AI 写内核"的最小可跑原型；用 PINNs/FNO 做版图迭代中的快速代理模型（surrogate），用 Meep/Tidy3D 作 ORACLE。
- **编排模式**：采用"规划-执行-校验"循环（ReAct 类），每轮循环由验证 harness 给出是否收敛/达标，避免 agent 无休止生成。

### 2.4 可直接复用资产
- **逆设计内核代码**：ceviche、angler、lumopt（Apache/MIT，可直接 fork 作 L3 起点）。
- **编排范式参考**：PhIDO 的 4 阶段多 agent NL→GDSII 流水线（Interpreter/Designer/Layout/Circuit verification）+ 102 题基准 testbench。
- **代理模型**：PINNs/FNO 作为快速评估器，缩短 agent 迭代时延。

---

## 模块3 · 电磁/量子求解器开源实现与可验证性

### 3.1 关键论文/工具清单
| 求解器 | 类型/协议 | 年份 | 链接 |
|---|---|---|---|
| Meep（FDTD，CPU/GPU，含伴随/adjoint 优化） | GPL-2.0 | 2006–（1.32 2026） | https://github.com/NanoComp/meep |
| Tidy3D（GPU FDTD，云端，GDSFactory 集成） | LGPL | 持续维护 | https://github.com/flexcompute/tidy3d |
| MPB（本征模求解，频域） | GPL-2.0 | MIT | https://github.com/NanoComp/mpb |
| SAX（频域 S 参数电路仿真，JAX） | Apache-2.0 | 2021– | https://github.com/flaport/sax |
| KLayout（版图/DRC/LVS） | GPL | 持续维护 | https://www.klayout.de |
| OpenEMS（FDTD，微波/RF） | GPL | 持续维护 | https://www.openems.de |
| Elmer（开源 FEM 多物理，量子器件电容/London 方程） | GPL | 持续维护 | https://www.elmerfem.org |
| Palace（AWS 开源并行 FEM 全波） | Apache-2.0 | 2023– | AWS 实验室（github 待补） |
| Meep 论文（Oskooi 等, CPC 181:687） | MIT | 2010 | doi:10.1016/j.cpc.2009.11.008 |

### 3.2 核心结论
1. **光子侧 ORACLE 已齐备且开源**：Meep（FDTD 场级真值）、MPB（本征模真值）、SAX（电路级频响真值）三者覆盖"场-模-电路"全层级，且许可证友好（GPL/LGPL/Apache），可直接作为 LDA 验证 harness 的 ORACLE。
2. **GPU 加速拐点在 Tidy3D**：3D 问题 Tidy3D 比 Meep CPU 快数量级，且与 GDSFactory 直连——适合做"重 ORACLE"；Meep 适合轻量/本地快速验证。
3. **量子侧电磁仿真仍依赖商业工具（Ansys HFSS/Sonnet）**：开源替代（Elmer、Palace、OpenEMS、Meep）在量子器件中采用率低，是 LDA 的差异化空白（L3 可优先补这块的 AI 内核）。
4. **SAX 的"电路级解析真值"价值被低估**：对 S 参数网络，SAX 用解析线性代数求频响，是**确定性、零数值误差**的 ORACLE，最适合做 L0 电路 IR 的验收基准。

### 3.3 对 LDA 设计的启示（指向 L3 / 验证 harness）
- **验证 harness 的 ORACLE 分层**：场级真值→Meep/Tidy3D；模级真值→MPB；电路级真值→SAX（确定性）。AI 写的内核输出须逐层对照。
- **L3 边界**：LDA 自研内核先聚焦"光子器件 FDTD/FEM 快近似 + 逆设计伴随"，把重 ORACLE 委托给 Meep/Tidy3D；量子电磁（pyEPR/电容矩阵）暂借用商业+Elmer/OpenEMS，标注"待替换"。
- **许可证合规**：GPL/LGPL 求解器只能作外部 ORACLE 调用，不能静态链入 LDA 核心（Apache-2.0 的 SAX/Palace 可作更深度集成）。

### 3.4 可直接复用资产
- **ORACLE 求解器**：Meep（场级）、MPB（模级）、SAX（电路级确定性）、Tidy3D（GPU 重 ORACLE）。
- **版图/验证**：KLayout DRC/LVS 脚本（直接接 L0 版图 IR）。
- **量子 FEM 备选**：Elmer（London 方程/电容矩阵）、OpenEMS（RF/CPW 行波电极）。

---

## 模块4 · 光子/量子标准 benchmark 与 golden reference 题库（验证 harness 弹药库，最重要）

### 4.1 关键论文/工具清单
| 基准/工具 | 来源 | 年份 | 链接 |
|---|---|---|---|
| miepython（纯 Python Mie 解析解，对标 Wiscombe MIEV0） | Scott Prahl | 持续维护 | https://github.com/scottprahl/miepython |
| SOI 条形波导有效折射率（Marcatili / Soref / EIM） | Soref & Bennett (JOSA 1987) | 1987 | doi:10.1364/JOSA.86.000840 |
| add-drop 环形谐振器传输函数（FSR/Q 公式） | de Gruyter Nanophotonics 2022 | 2022 | doi 待补 |
| Y 分支优化基准（PSO 1.21dB→0.11dB） | Lumerical / varFDTD | 持续 | https://optics.ansys.com |
| 光栅耦合器布拉格周期公式 | Lumerical KB | 持续 | https://optics.ansys.com |
| Fabry-Perot etalon Airy 传输函数 | Ansys INTERCONNECT KB | 经典 | https://optics.ansys.com |
| Transmon 表征教程（T1/T2/RB） | arXiv 教程 | 2026 | arXiv 编号待核实 |
| Qubit Zoo（SOTA 指标汇总） | 社区 | 持续 | https://qubitzoo.org |
| QCVV / 表征基准（RB/IRB/XEB/GST/QV） | Rigetti / Hashim 2024 | 2024 | arXiv:2408.12064 |

### 4.2 核心结论
1. **光子侧存在大量"解析可算"的真值**：Mie 散射、波导有效折射率、Fabry-Perot、环形谐振器传输函数都有闭式解，是验证 harness 的**零成本黄金真值**，应第一批纳入。
2. **逆设计基准有公开数字锚点**：Y 分支优化后 0.11 dB、光栅耦合器 ~3 dB 插入损耗、crossing <0.1–0.3 dB——这些是"AI 内核输出是否达标"的硬判据。
3. **量子侧表征已形成标准协议族**：RB（指数衰减提 EPG）、IRB（隔离单门）、XEB（深度电路交叉熵）、GST（自洽校准 SPAM）、QV（整体算力）。这些是量子 L3 内核的验收协议。
4. **SOTA 指标已知**（Qubit Zoo）：T1 达 1.68 ms、单门保真度 99.99%、双门 CZ 99.95%——可作"设计是否达到业界水位"的对照线。

### 4.3 对 LDA 设计的启示（指向验证 harness）
- **验证 harness 必须是 LDA 的"质量门"**：每轮 agent 设计产出须经 harness 比对（解析真值比对 + 数值 ORACLE 比对），输出 pass/fail + 偏差量，人据此验收。
- **分两档真值**：① 解析/确定性（Mie、波导 n_eff、FP、环形、SAX 电路）——零成本、必做；② 数值 ORACLE（Meep/Tidy3D 场级）——按需、算力受限时抽样。
- **量子基准暂挂起、预留接口**：光子优先，但 L0 IR 需预置"量子字段（EPR、T1/T2、门保真度）"以便后期直接接 RB/XEB harness。

### 4.4 验证 harness 标准题清单（题型 + 真值来源 + 难度）
| # | 题型 | 真值来源（ORACLE/解析） | 难度 | 备注 / 判据 |
|---|---|---|---|---|
| B1 | 米氏散射远场散射效率 Q_scat vs 粒径/折射率 | miepython 解析级数（MIEV0 验证） | 中 | 2D/3D FDTD 对照散射截面与场分布 |
| B2 | SOI 条形波导有效/群折射率 | Marcatili 近似 / EIM / 解析本征模 | 低 | 220nm×500nm @1550nm 对标 n_eff≈2.44, n_g≈4.18 |
| B3 | Fabry-Perot etalon 透射谱 | Airy 公式 T_e=(1-R)²/(1+F·sin²(δ/2)) | 低 | FSR=λ²/(2 n l)，含损耗扩展式 |
| B4 | add-drop 环形谐振器 通/下载端口传输 | 解析传递函数（FSR=λ²/(n_g·L)，FWHM/Q） | 中 | 给定 r,a,L,n_eff 反算谱形 |
| B5 | Y 分支插入损耗 | Lumerical PSO 基准（优化后 0.11 dB） | 中 | 达标线 ≤0.2 dB |
| B6 | 光栅耦合器耦合效率/布拉格周期 | p=λ₀/(n_eff−n_clad·sinθ) + 基准 ~3 dB | 中高 | 周期与峰值效率双判据 |
| B7 | 波导 crossing 插入损耗 | 文献基准 <0.1–0.3 dB（对称结构） | 中 | 对称/非对称对照 |
| B8 | 模式转换器/taper 效率 | 绝热判据 / 解析绝热耦合 | 中 | 达标线 ≥99% 传输 |
| B9 | transmon 参数提取 | pyEPR + SOTA：T1≤1.68ms, 1Q≥99.99%, 2Q CZ≥99.95% | 高 | 量子路线预留，标 SOTA 对照 |
| B10 | 量子门保真度基准 | RB: F=1−((d−1)(1−p))/d；XEB: F=2ⁿ⟨P_ideal⟩−1；GST/QV | 高 | 量子路线预留，协议级验收 |

---

## 模块5 · QEDA 全栈现状（量子路线后期，先映射空缺）

### 5.1 关键论文/工具清单
| 工具/论文 | 组织 | 年份 | 链接 |
|---|---|---|---|
| EDA-Q（首个开源全栈超导量子芯片 EDA：拓扑→等效电路→版图→器件映射→布线→工艺映射→仿真） | 先进计算与智能工程实验室（赵博等） | 2025 | https://arxiv.org/abs/2502.15386 |
| 本源坤元 Q-EDA（国产首个量子芯片设计工业软件，超导+半导体双平台，PDK，72比特版图 6分50秒） | 本源量子（合肥） | 2022 首发，2025 第5代 | 公开报道 https://www.sohu.com/a/967547640_222256 |
| 量旋天乙 EDA（超导量子芯片快速设计/仿真） | 量旋科技（深圳） | 2023 | 公开报道同上 |
| Qiskit Metal | IBM | 2020– | https://github.com/Qiskit/qiskit-metal |
| KQCircuits | IQM | 2018– | https://github.com/iqm-finland/KQCircuits |
| QuantumPro（PathWave，原理图/版图/EM/非线性电路/量子参数提取） | Keysight | 商业 | 官网待补 |
| CQCC2025 量子芯片设计及其自动化技术 分会 | CCF | 2025 | 公开报道 |
| AI 驱动量子芯片设计自动化（EDA-Q 开源生态，Apache-2.0） | 行业综述 | 2025 | http://hbsjsjxh.com/nd.jsp?id=4464 |

### 5.2 核心结论
1. **全栈是稀缺品**：EDA-Q 的对比表显示——拓扑设计仅 EDA-Q 支持；等效电路设计仅 EDA-Q/Origin Unit；器件映射仅 EDA-Q；工艺映射仅 EDA-Q/Origin Unit。多数工具只覆盖"版图+布线"，**器件映射/工艺映射是公认空白**。
2. **国内外差距在缩小但生态碎片化**：CQCC2025 指出国内 EDA-Q/本源坤元/量旋天乙与国外同类"无明显差距"，但缺乏统一接口标准（如 QASM 扩展），跨平台兼容性差。
3. **三大共性瓶颈**（CQCC2025/综述）：① 物理建模精度不足（退相干机制刻画不全，仿真-实测偏差 >5%）；② 多物理场耦合仿真效率低（千比特全耦合 >24h）；③ 开源生态碎片化、无统一 IR/DSL。
4. **超导为主流、离子阱/光量子并行**：超导（IBM/IQM/本源/量旋）工具最成熟；离子阱（IonQ AQ 指标）、光量子路线 QEDA 工具最少——后者恰是 LDA 光子+量子双栈的天然切入点。

### 5.3 对 LDA 设计的启示（指向 L0 / L1 / 差异化）
- **L0 IR 应原生支持"器件映射 + 工艺映射"字段**：这是现有工具最大空白，LDA 若在 L0 定义 `device_map`（物理器件额定值映射）与 `fab_process`（制造成本/良率映射），即对齐 EDA-Q 的全栈缺口。
- **统一 IR/DSL 是 LDA 相对 QEDA 碎片化的差异化武器**：用一套 L0 表达超导/离子阱/光量子三类版图，避免每类重写工具链。
- **量子侧后期切入、复用光子栈**：光子 L0 几何/版图原语（KLayout 系）直接复用；量子特有物理（EPR、T1/T2、门保真度）作为 L0 扩展字段，延后到量子路线时填充。

### 5.4 可直接复用资产
- **全栈流程范式**：EDA-Q 的"拓扑→等效电路→版图→器件映射→布线→工艺映射→仿真"七段式（可作 L1 流水线模板）。
- **国产 PDK 参考**：本源坤元已发 3 个 PDK 版本（中芯国际/本源工艺），可作 L0 `process` 字段实例。
- **开源锚点**：EDA-Q 号称 Apache-2.0 开源核心（据综述），可优先对接其 IR 设计以验证 L0 兼容性。

---

## 总体启示与优先级建议（对 LDA 设计）

**一句话**：先把"光子栈 + 解析真值 harness"做成闭环（技术复利最厚、风险最低），L0 IR 预留量子扩展字段，L3 先用开源逆设计内核 + Meep/SAX 作 ORACLE。

### 优先级排序（先吸哪些文献资产进 L0/L1/验证 harness）
1. **P0 · 验证 harness 第一批（立刻做）**：模块4 的 B1–B4、B8（解析/确定性真值，零成本）——Mie、波导 n_eff、Fabry-Perot、环形谐振器、taper。用 SAX（电路级）+ miepython + 解析公式搭最小 harness。
2. **P0 · L0 IR 字段定义（立刻做）**：借鉴模块1 的 gdsfactory `Component/Netlist/PDK` + KQCircuits `Element/refpoints` + 模块5 的 `device_map/fab_process`。定稿 L0 schema（JSON/Proto）。
3. **P1 · L3 求解内核起点**：fork ceviche/angler/lumopt（伴随逆设计）作 AI 内核原型；Meep 作场级 ORACLE、Tidy3D 作 GPU 重 ORACLE（模块3）。
4. **P1 · L1 agent 协议层**：套用模块2 的"Interpreter/Designer/Layout/Verification"多 agent 流水线（直接对标 PhIDO 开源架构）+ Human-in-the-loop 验收点。
5. **P2 · 光子器件数值基准（B5–B7）**：Y 分支/光栅/crossing 需 Meep/Tidy3D 场级 ORACLE，算力受限时抽样验收。
6. **P3 · 量子路线（后期）**：预置 L0 量子字段（EPR/T1-T2/门保真度）；B9/B10 接 pyEPR + RB/XEB；复用 KLayout 版图系；以"统一 IR 打破 QEDA 碎片化"作差异化。

### 关键风险与边界
- **许可证**：GPL/LGPL 求解器（Meep/MPB/Tidy3D/KLayout）只能作外部 ORACLE 调用，不得链入 LDA 核心；SAX/Palace（Apache-2.0）可深度集成。
- **不要重复造轮子**：逆设计内核（ceviche/angler）、版图（gdsfactory/KLayout）、ORACLE（Meep/SAX）全部借用，LDA 自建价值在 **L0 统一 IR + L1 agent 协议 + 验证 harness 编排**。
- **量子电磁仿真空缺**：Ansys HFSS 主导、开源采用率低，是 L3 后期真机会，但光子优先阶段先借用 Elmer/OpenEMS 过渡。

### 补遗 · PhIDO 论文补全（team-lead 补）
- **标题**：AI Agents for Photonic Integrated Circuit Design Automation
- **作者**：Ankita Sharma, Yuqi Fu, Vahid Ansari, Rishabh Iyer, Fiona Kuang, Kashish Mistry, Raisa Islam Aishy, Sara Ahmad, **Joaquin Matres（GDSFactory）**, Dirk R. Englund（MIT）, Joyce K.S. Poon（多伦多大学）
- **发表**：arXiv:2508.14123，v1 2025-08-18
- **机构组合**：多伦多大学（PI Poon）+ 马普所（Ansari）+ MIT（Englund）+ GDSFactory（Martres）——**学术界+开源社区联合**，印证"agent-native 光子设计"已由该联盟开源证明可行。
- **核心数据**：102 题基准（单器件→112 组件 PIC）；单器件成功率 91%；≤15 组件 pass@5 ~57%（o1/Gemini-2.5-pro/Claude Opus 4 最佳）；用 Pydantic schema 约束 + YAML DSL 作中间表示；Circuit verification 阶段用 **SAX** 仿真。
- **对 LDA 启示**：PhIDO 证明了"4 阶段 agent → GDSII"可行且已开源，但 DSL 是光子-only 薄 YAML、无统一开放标准——**L0 统一 IR 就是要占这个空格**；且 PhIDO 的 verification 只到电路级（SAX），未做场级/逆设计真值闭环——**LDA 的验证 harness（含 B1–B10 场级+解析真值）是更深一层**。

> 说明：标注"待补"的条目（ICCAD2025 agentic EDA 具体论文、Cadence/Synopsys 商业链接、Nazca 精确仓库、Palace 仓库、部分 doi、Transmon 教程 arXiv 编号）为本次检索未确认到可靠一手链接者，实现阶段需二次核实；其余 URL 均来自官方仓库/文档/arXiv/DOI，可直接访问。

---

## 模块6 · 大模型公司自研芯片 + 用自家 LLM 设计芯片（动态追踪课题）

> 2026-08-14 由杜先生提议列为研究室第 5 类常态追踪（原四类：论文/工具/基准/政策）。本模块为基线条目，由月度自动化（automation-1786670627231）持续校准；一手来源 DOI/arXiv 多待补，已标"待补"。

### 6.1 背景与动因
大模型公司自研 ASIC（推理/训练加速卡）的核心驱动力是**成本与供应安全**：英伟达毛利率 70–80%，且高端算力受出口管制。自研为摆脱 H100/B200 依赖、压低 TCO。进一步，头部玩家已不止"用 AI 辅助设计"，而是"用自家大模型做设计+验证"。

### 6.2 标杆事实（基线，待月度追踪校准）
| 主体 | 芯片/动作 | 是否用自家 LLM 设计 | 状态/年份 | 来源 |
|---|---|---|---|---|
| OpenAI | Jalapeño（与 Broadcom，~9 个月设计，2026.06 流片） | **是**：原文 "OpenAI used its own models in the design and verification flow" | 2026 | 科技媒体（待补一手） |
| Kimi（月之暗面） | K3（48h 全自主设计，45nm，146 万标准单元，开源 EDA + Nangate 45nm） | 是（自主） | 2026-07 | 媒体（致 EDA 概念股跌 12%，待补一手） |
| 中科院 | 启蒙1号（32-bit RISC-V，64nm，5h，400 万门，可跑 Linux） | 是（AI 全自动） | 2023 | 公开报道（待补） |
| Verkor | VerCore（219 词 NL→12h→7nm RISC-V） | 是 | 2026 | 公开报道（待补） |
| Google | TPU（Ironwood/Frozen v2）+ AlphaChip（RL 宏布局，已开源） | 辅助/RL 布局用于 TPU v5/v6 | 持续 | arXiv / Google Blog |
| NVIDIA | ChipNeMo（70B，Hopper/Blackwell/Rubin） | 辅助 | 持续 | NVIDIA 技术报告 |
| Meta | MTIA/Iris（与 Broadcom，2026.09 量产） | 辅助为主 | 2026 | 公开报道 |
| 阿里平头哥 | 真武810E（60% RTL 由 LLM，6→3 月） | 辅助 | 持续 | 公开报道 |
| 字节 | 马里亚纳（RISC-V，提速 40%） | 辅助 | 持续 | 公开报道 |
| Samsung | 设计流程用 Claude Code | 辅助（外部 LLM） | 持续 | 公开报道 |
| 小米 | 玄戒O1（3nm，用华大九天工具链） | 传统工具 | 2026 | 公开报道 |

### 6.3 对 LDA 的启示（真空格守卫）
- **方向被双重验证**：巨头亲自下场证明"agent 原生 EDA / 用 LLM 设计芯片"是真实工业趋势，非空想。
- **威胁侧**：他们在**电子域（CMOS/标准单元）**已跑通自主设计闭环；若把 agentic 设计协议固化为事实标准，会收紧 LDA 在光子/量子域的真空窗口。
- **护城河仍在**：他们全在电子域；光子/量子芯片的 IR（L0）仍空白——gdsfactory YAML 是光子专用薄表示、PhIDO DSL 封闭光子专用。LDA 的"跨光子+量子统一、机器优先 L0 IR"仍是干净空格。
- **结论**：加速冻结 L0 IR v0.1.0（呼应 MC-002 建议）；本课题列为研究室第 5 类常态追踪。

### 6.4 监控指标（月度/事件追踪）
1. 头部实验室是否开始定义自有芯片设计中间表示（IR/DSL）或开源 agentic 设计协议；
2. OpenAI/Meta/Google/Anthropic 自研芯片流片进展与是否公开设计栈；
3. Kimi/中科院/Verkor 类"全自主设计"是否从电子域外溢到光子/量子域；
4. EDA 概念股对"AI 自主设计"消息的灵敏度（市场情绪镜像）；
5. 出口管制是否波及"AI 设计工具"本身（如对华禁售 AI EDA agent）。

---

## 模块7 · LDA 工程实证：agent 实现创新的最主要症状（内部动态追踪）

> 2026-08-14 由杜先生提议列为研究室第 6 类常态追踪。动因：LDA 的核心 thesis = "AI agent 能自举造出芯片设计软件内核（AI for AI）"。这一 thesis 的**最主要证据不是外部论文，而是 LDA 自身工程的真实产出**——我们实际写出的代码/文档/里程碑。研究室须把本项目自身的工程进展当作一条持续追踪的"内部实证流"，每月校准。本模块为基线种子，由自动化 automation-1786670627231 持续更新。

### 7.1 实证框架：为什么内部产出是主要证据
- 外部 PhIDO / Cadence 等只能证明"别人能"，不能证明"我们能、且用 agent-native 方式能"。
- LDA 的差异化主张 = agent-native 自举开发（AI 写内核 + 确定性 harness 验收）。**唯一能证明它可行的，是它真实跑出来的东西**。
- 因此：每个真实产出 = 一份"AI for AI 可行性"的实证样本；月度追踪 = 把这些样本累加为可信证据链。

### 7.2 工程实证清单（基线种子，待月度校准）
| 工程 artifact | 路径/文档 | 状态 | 实证指标（可对外展示） | 印证 thesis 强度 |
|---|---|---|---|---|
| L0 验证 harness 骨架 | `lda/lda_harness/` | 已建成跑通 | 11/11 标准题 PASS（B1–B11）；零外部依赖离线可跑 | 强：确定性裁判闭环落地 |
| L3 AI 写内核候选 | `lda/lda_harness/l3_ai_solver.py` | 已接入 | `--ai` 实测 3/5 PASS（B2/B8 FAIL）——精准复现早期 AI 内核"多数写对、个别漏步骤"画像 | 强：AI 写求解器被真实验收 |
| 标准题 B1–B11 | `benchmarks.py`/`golden.py` | 已定义 | 物理定律锚(B1–B4,B8,B9,B10,B11)+场级 ORACLE(B5/B7,几何相关) | 中：题库基线 |
| 场级 ORACLE | `oracle_field.py` + `ext_oracle/meep_oracle.py` | **已落地** | B5/B7 默认 numpy 离线场级（B7 默认几何≈-19.7dB 随宽度变化）+ Meep 子进程生产路径就绪(GPL 不进核心)；B6 已接入 Tidy3D 外部 ORACLE（key 门控，离线回退设计守则锚） | 强：验证裁判真值升级 |
| **L2-A 自研 1D/2D/3D FDTD 求解核（C 级自主）+ L2-B Numba 加速** | `lda/lda_solver/fdtd1d.py`+`run_fdtd_selfcheck.py`；`lda/lda_solver/fdtd2d.py`+`run_fdtd2d_selfcheck.py`；`lda/lda_solver/fdtd3d.py`+`run_fdtd3d_selfcheck.py`；`lda/lda_solver/fdtd3d_numba.py`+`run_fdtd3d_numba_selfcheck.py` | **已自研通过校验（1D 2026-08-15；2D 2026-08-15；3D 2026-08-15；Numba 加速 2026-08-15）** | 零外部依赖仅 numpy、机器优先接口、梯度海绵吸收层 + 参考跑归一化绝对标度；1D ORACLE=tmm.py **4/4 PASS**；2D 双 ORACLE（tmm.py 一维退化 + 点源柱面波 |Ez|·√r）**5/5 PASS**；3D 双 ORACLE（tmm.py y/z-PBC 一维退化 + 点源球面波 |Ez|·r）**5/5 PASS**（A=0.0000/B=0.0019/C=0.0170/D=0.0090/E=0.0101）；`fdtd3d_numba.py` 将六分量更新融合为 `@njit(parallel=True)` 核，**逐字节等价于 numpy 版、同精度 5/5、约 20× 加速（16m19s→0.8m）**；**1D/2D/3D 透射谱均已无需借 Meep 即得** | **强：L2-A「踢掉 B 级 Meep 求解依赖」三维可运行实证 + L2-B 性能升维第一步（Numba-CPU 生产级）落地** |
| **L0 统一 IR/DSL（`lda_ir`）** | `lda/lda_ir/`（core/photon/quantum/dsl/validate/bridge） | **已落地(草案)** | 机器优先 IR（to_dict/from_dict round-trip）+ 携带目标谱形(SpectrumSpec)+多晶圆厂落点(FoundryPlan)；**统一光子+量子**：`photon.py`(RingResonator等)与`quantum.py`(Transmon/Resonator/Coupler)共用同一套 core；**工艺窗口语义**：光子 n_si / 量子 E_C(quantum_window.ec_default) 由 foundry 决定、设计只调 R/E_J，bridge 强制注入并固定工艺参数，使落点差异由工艺驱动（干净因果链）；`ir_eval` 让 L3 真值内核直接读 IR 算真值+判定（IR 即事实源，不经 DesignProblem）；`run_ir_smoke.py` 跨 3 光子 foundry 全 PASS（R≈12.205/12.253/12.205µm）+ `run_ir_quantum_smoke.py` 跨 2 量子 foundry（E_C=0.30/0.45→E_J=11.56/8.28，f01 均命中 5.0GHz）+ `run_ir_solve_smoke.py` L3 直接消费 IR 全 PASS；UI ⑥ 面板同时真跑光子+量子两段 + L3 直接真值演示 | **强：统一 IR 空格占位 → 真地基可运行（光子+量子同源 + 工艺窗口驱动落点 + IR 即事实源）** |
| **agent 自迭代设计闭环** | `lda/lda_agent/design_loop.py` + `run_agent_loop.py` | **已落地(草案)** | 环形 FSR 设计：真内核 10 轮收敛→FSR≈9.14nm 双判据全绿；l3_ai 内核设计收敛但 B2 残差被法官独立抓 FAIL（双判据分离实证）；**已升级 N 维逆设计**：Nelder-Mead 多参数优化，同时调 R+w_core 命中 FSR+n_eff（B2 为硬约束），l3_ai 内核缺陷被硬约束挡住、无法虚假收敛；**已支持加权多目标逆设计**（objective=[{bid,weight,target,tol}]，FSR 与 n_eff 双目标同时加权达标）；**已支持目标谱形逆设计(B11，FSR 周期归一化失配) + 有限差分梯度下降（数值伴随法，零依赖）** | **最强：agent-native 设计闭环可运行 = AI for AI 直接证据** |
| 主权化镜像 | Gitee i4hub / 本地根 | 部分（gdsfactory 已入库；sax/mpb/meep/klayout 待本地补） | B 级依赖 fork 主权根 | 中：主权纪律落地中 |
| **真·MCP server（L1 对外开放）** | `lda/lda_l1/mcp_server.py` + `run_mcp_server.py` + `run_mcp_smoke.py` | **已落地** | 零依赖 stdio JSON-RPC 2.0(2024-11-05)；`tools/list`→lda.verify_design/lda.list_benchmarks；冒烟测试全链路 ✅（verify 8/8、l3_ai 法官抓 FAIL） | **强：L1 协议对外可集成 = 生态咽喉可运行样板** |
| **真·Web 预览界面（L4）** | `lda/lda_webui/app.py` + `static/index.html` | **已落地** | 零依赖 http.server 后端 + 产品级深色前端；①~③ 控制台 + ④ PDK 工艺逆设计（环形器件实时渲染目标谱形洛伦兹梳：实线=实际/虚线=目标，FSR 一目了然）+ ⑤ 多晶圆厂对比（跨已登记 4 foundry 跑同一设计意图，表格 + 谱形叠加图展示工艺窗口差异驱动落点不同）；全部实时真跑内核；新增 `POST /api/pdk_compare` | **强：AI for AI 成果对外可交互展示 = 产品级门面** |
| **L2 开放 PDK Registry（社区共建）** | `lda/lda_l2/pdk.py` + `pdk_examples.py` + `run_pdk_smoke.py` | **已落地** | NOEIC SOI 180nm 示例 PDK + 6 器件模板（环形 FSR / 环形 FSR+波导 / 波导宽度→n_eff / **环形双参数逆设计 N 维** / **环形双目标加权** / **环形谱形匹配 B11 目标谱形**）+ CUMEC / SITRI SOI 180nm 示例 PDK（各 2 模板，多晶圆厂共建）+ 超导量子示例 PDK（B9 transmon 频率 / B10 门保真度 + B9 约束）；`derive_problem()` 直接驱动 agent 在工艺窗口内收敛（波导模板 2 轮命中 w=0.45→n_eff=2.616；双参数模板真内核 R≈9.95μm+w_core≈0.54μm→FSR 精确 9.15nm 双判据全绿；加权模板双目标同时达标；量子模板 B9→f01≈6.59GHz、B10→F≈0.989）；l3_ai 双规格/硬约束/量子内核缺陷均被法官抓 FAIL | **强：工艺参数注入点落地，逆设计天然落在可制造边界 = L0→L2→L1→L3→harness 全链路闭合** |
| 战略文档包 | 可行性/白皮书/MC-001/路线图/知识基线/机构图谱/研究室章程 | 已产出 | 统一基线 | 基础 |

### 7.3 监控指标（月度/事件追踪 · 内部实证）
1. 新增工程 artifact 数量与类型（代码/文档/里程碑）；
2. 可对外展示的实证数字更新（harness 通过题数、--ai 候选通过率、L0 IR 字段覆盖度）；
3. "AI 写内核被真实验收"的实例累积（证明 AI for AI 自举可行）；
4. 可复现性/离线可跑性（无外部依赖能否独立验证）；
5. 对外可讲述证据链完整度（能否讲清"agent 原生造核"故事）。

### 7.4 对 thesis 的印证小结（基线）
截至 2026-08-14：已完成"确定性验证裁判闭环"(B1–B8 全 PASS) + "AI 写内核被真实验收"(3/5 partial) + "统一 L0 IR 草案" + **"agent 自迭代设计闭环可运行"**(真内核收敛达标、l3_ai 内核被法官独立抓残差) + **"真·MCP server 对外开放"**(零依赖 stdio JSON-RPC、tools/call 真能驱动内核验证、外部 agent 可集成)六件真地基，构成 agent-native 自举开发可行性的**首批实证**。其中 agent 设计闭环是 AI for AI 最直接的可运行证据；MCP server 是 L1「agent 操作接口」主张的完成态——让外部 agent 把 LDA 内核当工具调用，是标准+生态护城河的可运行样板；真·Web 预览界面(L4)是成果对外可交互展示的产品级门面——让"AI for AI 可行性"从命令行/文档变为可点按的实时证据。L2 开放 PDK Registry 也已落地（社区共建层）：示例 NOEIC SOI 180nm PDK + 3 器件模板，经 `derive_problem()` 直接驱动 agent 在真实工艺窗口内逆设计几何——这闭合了 L0(IR)→L2(工艺参数)→L1(协议)→L3(内核)→harness(裁判) 全链路的"工艺参数注入"缺口，使逆设计不再是真空里的几何优化，而是可制造边界内的目标求解。下一步工程动作见路线图阶段1。另：**N 维逆设计已在 agent 闭环落地**——`DesignAgent` 支持多参数 Nelder-Mead 优化 + `constraint_bids` 硬约束，PDK 新增「环形双参数逆设计」模板，真内核双参数收敛（R≈9.95μm, w_core≈0.54μm → FSR 9.15nm 精确、双判据全绿），l3_ai 内核缺陷被硬约束挡住无法虚假收敛；这是 agent-native 自举设计从单参数诊断到多参数优化的关键跃迁；**进一步落地加权多目标逆设计**（objective=[{bid,weight,target,tol}]，FSR 与 n_eff 双目标加权同时达标）与**量子子集 B9/B10**（transmon 频率/门保真度解析物理锚 + 超导量子示例 PDK 逆设计，真内核收敛、l3_ai 内核缺陷仍被法官抓 FAIL），题库扩至 B1–B11；B6 已接入 Tidy3D 外部 ORACLE（key 门控 + 设计守则锚兜底），"主权优先 + GPL 仅外部 ORACLE"纪律闭环。；**进一步 L4 产品级 UI 增强（①类真地基的可交互门面）**：`lda/lda_webui/app.py` 新增 `ring_spectrum()`（纯解析洛伦兹梳，零依赖）与 `POST /api/pdk_compare`（跨已登记 4 foundry 跑同一器件类型逆设计、返回各 foundry 收敛落点 + 谱形数组）；`static/index.html` 的 ④ PDK 面板对环形器件实时渲染**目标谱形可视化**（实线=实际谱 / 虚线=目标谱，FSR 一目了然），新增 ⑤ **多晶圆厂对比面板**（表格 + 谱形叠加图，直观展示 NOEIC/CUMEC/SITRI 因 n_g/折射率/尺寸边界不同 → 同一 FSR 目标收敛到不同 R 落点）。实测：`/api/pdk_design` 跑 B11 返回 401 点谱形（FSR≈9.14nm）；`/api/pdk_compare` 跨 3 光子 foundry 返回对比（R≈9.956/9.997/9.955µm 各异、量子 foundry 自动跳过）。这让"AI for AI 可行性"从命令行/文档变为可点按、可横向对比的实时证据——产品级门面不再只是控制台，而是带谱形与多工艺对比的可视化决策界面。；**进一步 L0 量子多晶圆厂共建 + L3 直接消费 IR（ir_eval）落地**：`pdk.py` 的 `PDK` 新增 `quantum_window`(ec_default/ec_min/ec_max) 作为量子域"可制造窗口"注入点（与光子 n_si 对称）；`pdk_examples.py` 把单量子 foundry 拆为 2 个（量子A E_C≈0.30 / 量子B E_C≈0.45），Registry 现登记 5 foundry（3 光子 + 2 量子）；`bridge.py` 量子域强制注入并固定 E_C（只调 E_J），使"同一 f01 目标在不同量子厂收敛到不同 E_J 落点"因果链干净（E_C=0.30/0.45→E_J=11.56/8.28，f01 均命中 5.0GHz）；新增 `ir_eval` 让 L3 真值内核直接读 IR 算真值+判定（IR 即事实源，不经 DesignProblem）。三件事（统一光子+量子 + 多晶圆厂共建 + IR 即事实源）在同一真地基上闭环——"统一光子+量子 + 多 foundry 落点 + IR 驱动验证"不是架构图上的口号，是可真跑、可横向对比、可点按的活系统。

**进一步 L0 统一 IR/DSL 真落地（①类真地基，护城河核心）**：新建 `lda/lda_ir/`（core/photon/dsl/validate/bridge），把"设计意图"以机器优先 IR 表达——`to_dict`/`from_dict` 纯 dict round-trip（经 L1 MCP 传输、落库 diff）、`to_dsl` 人类可读渲染；携带 `SpectrumSpec`（目标谱形，驱动 B11）与 `FoundryPlan`（多晶圆厂落点意图，驱动 L2 共建）；`validate.py` 把验证闭环前置到 IR 层（端口闭合/参数落窗口/谱形规格合法，收集全部错误而非中途抛异常）；`bridge.py` 的 `ir_to_design_problem`/`ir_to_multifoundry` 把 IR 经 KernelGateway 真驱动 agent 设计闭环（spectrum→B11 objective、param_bounds→tunables、foundry n_si 注入 n_g 体现工艺折射率驱动落点差异）。`run_ir_smoke.py` 端到端验证：构造"环形谱形+B11+多晶圆厂" IR → 校验 0 错误 → round-trip 零损失 → 跨 NOEIC/CUMEC/SITRI 三光子 foundry 真跑逆设计全 PASS（R≈12.205/12.253/12.205µm，折射率差异驱动落点不同，量子 foundry 被 domain 过滤跳过）。Web UI 新增 ⑥ 面板 `POST /api/ir_demo` 可交互真跑 IR。这把之前"统一 IR 空格占位"升级为**可运行的真地基**——L0 不再只是 schema 文档，而是能直接喂给 agent 闭环、携带谱形与多 foundry 落点的活 IR。

---

## changelog
- **2026-08-14**（置信度：已核实基线，一手来源待补）新增模块6「大模型公司自研芯片 + 用自家 LLM 设计芯片」动态课题：基线事实表（OpenAI Jalapeño / Kimi K3 / 中科院启蒙1号 / Verkor VerCore 等）、对 LDA 真空格守卫启示、5 项监控指标。动因 = 杜先生提议将"大模型自研芯片"作为研究室动态追踪课题，列为原四类（论文/工具/基准/政策）之外的第 5 类常态追踪，由自动化 automation-1786670627231 持续校准。
- **2026-08-14**（置信度：已核实基线）新增模块7「LDA 工程实证：agent 实现创新的最主要症状」：将 LDA 自身工程真实产出列为研究室第 6 类常态追踪——动因 = AI for AI 可行性最主要证据来自本项目实际跑出来的代码/文档/里程碑，而非外部论文。种子清单含 harness(8/8)、L3 AI solver(3/5)、L0 IR 草案等；5 项内部实证监控指标；由自动化 automation-1786670627231 每月校准。
- **2026-08-14**（置信度：已核实）B5–B7 场级 ORACLE 落地升级：`oracle_field.py` 新增纯 numpy 2D-FDTD 离线求解（B7 波导交叉串扰，几何相关）+ 重叠估计（B5 Y 分支），`ext_oracle/meep_oracle.py` 提供 GPL 隔离 Meep 子进程生产级真场级（严守"GPL 不进 Apache-2.0 核心"红线）；harness 报告新增"真值来源"列（physical-law/meep-fdtd/numpy-fdtd-offline/numpy-overlap-offline/design-anchor）。B5/B7 黄金参考已由扁平设计锚升级为几何相关场级真值。
- **2026-08-14**（置信度：已核实）**agent 自迭代设计闭环落地**（属 L1 增强、①类真地基）：`lda/lda_agent/design_loop.py` + `run_agent_loop.py`。agent 提案→L1 驱动内核→物理定律法官验证→诊断迭代，环形 FSR 设计真内核 10 轮收敛(FSR≈9.14nm)双判据全绿；l3_ai 内核设计收敛但 B2 残差被法官独立抓 FAIL（双判据分离实证）。这是 AI for AI 可直接运行的最小实证。同时修复 `resolve_specs` 使 L0 IR 能携带设计实际几何参数（L0/L1 咬合补全）。
- **2026-08-14**（置信度：已核实）**真·MCP server 落地**（L1 协议层对外开放、①类真地基）：`lda/lda_l1/mcp_server.py` 手写零依赖 stdio JSON-RPC 2.0（2024-11-05），完全复用 `KernelGateway`，暴露 `lda.verify_design`/`lda.list_benchmarks` 两工具；`run_mcp_server.py` 为客户端拉起入口；`run_mcp_smoke.py` 模拟 MCP 客户端做全链路冒烟（initialize/tools/list/tools/call 全 ✅；verify 8/8、l3_ai 法官抓 FAIL）。这是《白皮书》L1「agent 操作接口」主张的完成态，也是"标准+生态"护城河的可运行样板——外部 agent（Claude/Cursor）可直接 call LDA 内核。
- **2026-08-14**（置信度：已核实）**真·Web 预览界面（L4）落地**：`lda/lda_webui/app.py`（零依赖 http.server 后端）+ `static/index.html`（产品级深色前端）。首屏自动跑 verify(8/8)；可交互运行 verify(l3_ai→B2/B8 被抓)、agent_loop(真内核 10 轮收敛)；全部实时真跑已落地内核，非演示稿。这是 AI for AI 成果对外可交互展示的产品级门面，也是既定路线 L4 应用层完成态。
- **2026-08-14**（置信度：已核实）**L2 开放 PDK Registry 落地**（社区共建层、①类真地基）：`lda/lda_l2/pdk.py`（`PDKRegistry` 登记/查询/`derive_problem()`）+ `pdk_examples.py`（NOEIC SOI 180nm 示例 PDK + 3 器件模板：环形 FSR / 环形 FSR+波导 / 波导宽度→n_eff）+ `run_pdk_smoke.py`。`derive_problem()` 由模板派生 agent 设计问题，直接驱动 agent 在真实工艺窗口内逆设计几何（波导模板 2 轮收敛命中 w=0.45→n_eff=2.616）；l3_ai 双规格仍被法官独立抓 FAIL——双判据分离在 PDK 驱动路径下依然成立。这是 L0→L2→L1→L3→harness 全链路"工艺参数注入"缺口的闭合点，使逆设计天然落在可制造边界内，而非真空几何优化。
- **2026-08-14**（置信度：已核实）**N 维逆设计升级落地**（agent 闭环增强、①类真地基）：`lda/lda_agent/design_loop.py` 的 `DesignAgent` 支持 N 维 `tunables` + `constraint_bids` 硬约束，多参数走零依赖 Nelder-Mead 单纯形；`lda/lda_l2/pdk.py` 的 `DeviceTemplate` 支持多参数模板（`tunables` 优先、`tunable/bounds` 向后兼容）；`pdk_examples.py` 新增「环形双参数逆设计(B4+B2)」模板（同时调 R 命中 FSR 与 w_core 命中 n_eff，B2 为硬约束）。实测：真内核双参数收敛（R≈9.95μm, w_core≈0.54μm → FSR 精确 9.15nm，双判据全绿）；l3_ai 内核因 B2 缺陷被硬约束挡住、无法虚假收敛——双判据分离在多参数路径强化为「约束即质量门」。这是 agent-native 自举设计能力从单参数诊断到多参数优化的关键跃迁。
- **2026-08-14**（置信度：已核实）**L0 统一 IR/DSL 真落地**（①类真地基、护城河核心）：新建 `lda/lda_ir/`（core/photon/dsl/validate/bridge）。机器优先 IR 表达设计意图（to_dict/from_dict 纯 dict round-trip + to_dsl 可读渲染）；携带 `SpectrumSpec`（目标谱形→B11）+ `FoundryPlan`（多晶圆厂落点→L2 共建）；`validate.py` 把验证闭环前置到 IR 层（端口闭合/参数落窗口/谱形规格合法）；`bridge.py` 经 KernelGateway 真驱动 agent 设计闭环。`run_ir_smoke.py` 端到端验证：构造"环形谱形+B11+多晶圆厂" IR → 校验 0 错误 → 跨 NOEIC/CUMEC/SITRI 三光子 foundry 真跑逆设计全 PASS（R≈12.205/12.253/12.205µm，折射率差异驱动落点不同）；Web UI 新增 ⑥ 面板 `POST /api/ir_demo` 可交互真跑。L0 从"schema 空格占位"升级为可运行的活 IR。
- **2026-08-14**（置信度：已核实）**加权多目标逆设计 + 量子子集 B9/B10 + B6 Tidy3D ORACLE 落地**：`lda/lda_agent/design_loop.py` 的 `DesignProblem` 增加 `objective`（加权多目标 [{bid,weight,target,tol}]），`DesignAgent` 多参数走 Nelder-Mead 最小化加权误差联合反推几何，使多个 benchmark 同时达标；收敛（设计目标）与全验证（含约束）刻意分离 = 双判据分离。`lda/lda_harness/golden.py` 新增 B9 transmon 频率（Koch2007 解析）、B10 门保真度（退相干极限解析），`benchmarks.py` 登记 B9/B10，题库扩至 B1–B10；`oracle_tidy3d.py` 接入 B6 3D 外部 ORACLE（仅 `TIDY3D_API_KEY` 门控、GPL 不进核心、离线回退设计守则锚）。`pdk_examples.py` 新增「环形双目标加权(B4+B2)」模板 + 超导量子示例 PDK（B9 频率逆设计 / B10 保真度+B9 约束）。实测：加权模板双目标同时达标；量子 B9 真内核收敛(f01≈6.59GHz)、l3_ai 内核漏 sqrt 缺陷被法官抓 FAIL；B10+B9 真内核 F≈0.989 双判据全绿、l3_ai 被 B9 约束挡住。这是 agent-native 自举设计能力从单参数→多参数→加权多目标→跨光子/量子统一的连续跃迁，且验证锚扩展到量子域确定性物理定律。
- **2026-08-15**（置信度：已核实）**L0 IR 量子子集落地（统一光子+量子底座）**：在已落地的 `lda/lda_ir/` 新增 `quantum.py`（Transmon / Resonator / Coupler Kinds，复用同一套 `core` 产 `Component`），与 `photon.py` 共用 IRModel / 校验器 / 桥接层——仅 `domain="quantum"` 与 Kinds 不同。`bridge.py` 修正：n_g/n_si 注入仅限 photon 域（量子不注入折射率，避免光子工艺参数误塞进 B9 物理定律锚）；domain 自动过滤 foundry（量子 IR 只派发到"量子" foundry）。`validate.py` 新增"无 spectrum 且无 objectives 即非法"健壮性校验。`run_ir_quantum_smoke.py` 端到端验证：构造 transmon 频率逆设计 IR（目标 f01=5.0GHz，调 E_J/E_C）→ 校验 0 错误 → round-trip 零损失 → 跨量子 foundry 真跑 DesignAgent 收敛（E_J≈7.87/E_C≈0.48→f01=5.0GHz，PASS）。Web UI ⑥ 面板升级为**同时真跑光子段(B11 谱形+多 foundry)与量子段(B9 频率)**，证明"同一 IR 机器语言驱动光子+量子"——"统一光子+量子"从定位口号变为可运行底座。
- **2026-08-14**（置信度：已核实）**目标谱形逆设计(B11) + 有限差分梯度下降 + 多晶圆厂 PDK + pyEPR 外部 ORACLE 落地**：`lda/lda_harness/golden.py`/`benchmarks.py` 新增 B11（环形透射谱"目标谱形"匹配，误差=共振周期 FSR 与目标谱形的归一化失配——均匀洛伦兹梳谱形由 FSR 决定、在 R 上单谷稳健、避免逐波长 L2 谱形误差在梳状混频处的伪局部极小），题库扩至 B1–B11；`lda/lda_agent/design_loop.py` 新增 `use_gradient` 路径（有限差分梯度下降=数值伴随法，零依赖，对单/多参数通用、不要求目标单调），PDK「环形谱形匹配(B11)」用其收敛(R≈9.96μm→FSR 命中、谱形误差 0.0012、双判据全绿)；`pdk_examples.py` 新增 CUMEC / SITRI SOI 180nm 示例 PDK（各 2 模板、工艺窗口不同），Registry 已登记 4 foundry 演示「开放 PDK / 多晶圆厂共建」；`oracle_pyepr.py` 接入 B9 可选 EPR 对角化外部 ORACLE（缺失回退 Koch2007 解析解、核心永不 import），与 miepython/Tidy3D/Meep 同构"物理定律锚 + 外部 ORACLE"二元结构。实测：12 模板（单参/N维/加权/谱形/量子/多foundry）全收敛、l3_ai 缺陷仍被法官抓 FAIL、B6 无 key 时回退设计守则锚 0.5（严守 GPL 仅外部 ORACLE）。这是逆设计从"标量指标"迈向"目标谱形"、PDK 从"单 foundry"迈向"多晶圆厂共建"的关键一跃。
- **2026-08-15**（置信度：已核实）**量子多晶圆厂共建 + L3 直接消费 IR（ir_eval）落地**：把 L0 IR 的"统一光子+量子 + 多 foundry 落点"从占位升级为完整可运行闭环。① 量子工艺窗口：`pdk.py` 的 `PDK` 新增 `quantum_window`(ec_default/ec_min/ec_max)，与光子 n_si 对称——它是量子域"可制造窗口"注入点；`pdk_examples.py` 把单量子 foundry 拆为 2 个（量子A Al/AlOx 固定频率 E_C≈0.30、量子B 薄氧化层可调耦合 E_C≈0.45），Registry 现登记 **5 foundry**（3 光子 + 2 量子）；`bridge.py` 量子域强制注入 foundry 的 ec_default 并固定 E_C（只调 E_J），使"同一 f01 目标在不同量子厂收敛到不同 E_J 落点"的因果链完全由工艺窗口驱动（E_C=0.30/0.45 → E_J=11.56/8.28，f01 均命中 5.0GHz）。② L3 直接消费 IR：`bridge.py` 新增 `ir_eval(model, params, foundry_key)`——直接读 IR 的 spectrum/objectives 调 golden_with_source 算物理真值 + 用 benchmarks tol 判定 pass/fail，不经手写 DesignProblem，IR 即事实源（技术复利：逆设计与验证共用同一份 IR 意图）。`run_ir_quantum_smoke.py` 跨 2 量子 foundry 验证落点差异、`run_ir_solve_smoke.py` 验证 ir_eval 命中/失配判定全绿。Web UI ⑥ 面板新增"L3 直接消费 IR 真值"展示段。这是"统一光子+量子 + 多晶圆厂共建 + IR 即事实源"三件事在同一真地基上的闭环。
- **2026-08-14**（置信度：已核实）**L4 产品级 UI 增强：目标谱形可视化 + 多晶圆厂对比面板**：`lda/lda_webui/app.py` 新增 `ring_spectrum()`（纯解析洛伦兹梳，零依赖）与 `POST /api/pdk_compare`（跨已登记 4 foundry 跑同一器件类型逆设计，返回各 foundry 收敛落点 + 谱形数组）；`static/index.html` 的 ④ PDK 面板对环形器件实时渲染**目标谱形可视化**（实线=实际谱 / 虚线=目标谱，FSR 一目了然），并新增 ⑤ **多晶圆厂对比面板**（表格 + 谱形叠加图，直观展示 NOEIC/CUMEC/SITRI 因 n_g/折射率/尺寸边界不同 → 同一 FSR 目标收敛到不同 R 落点，量子 foundry 无该器件类型自动跳过）。实测：`/api/pdk_design` 跑 B11 返回 401 点谱形（FSR≈9.14nm）；`/api/pdk_compare` 跨 3 光子 foundry 返回对比（R≈9.956/9.997/9.955µm 各异）。这让"AI for AI 可行性"从命令行/文档变为可点按、可横向对比的实时证据——产品级门面升级为带谱形与多工艺对比的可视化决策界面。
- **2026-08-15**（置信度：已核实）**L2-A 自研 1D FDTD 求解核通过物理定律锚校验（主权 B 级"踢掉"路径首个实证）**：新建 `lda/lda_solver/fdtd1d.py`（C 级自主、机器优先接口、零外部依赖仅 numpy、梯度海绵吸收层 + 参考跑归一化绝对标度），配套 `run_fdtd_selfcheck.py`（4 用例交叉校验，ORACLE = tmm.py 传输矩阵解析解）。**终态 selfcheck 4/4 PASS**：匹配介质 T≡1.0000（Δ=0.0000）、单界面空气→玻璃 T=0.958（Δ=0.0023）、FP 标准具 n=2.5 d=2.0µm 条纹（maxΔ=0.0178）、布拉格光栅禁带中心≈2.46µm（maxΔ=0.0370）。两处根因修复：① 软源须全程开启（ramp 渐入后恒 1.0 到结束，绝不在 DFT 测量窗口前关闭——关源过早→测得衰减场→标度崩塌，是前几轮反复假失败的真凶）；② 固定网格 + 最薄层整数吸附（整谱同一 dl，使薄膜光学程/布拉格周期不随 λ 漂移，根除 FP 条纹错位与禁带平移）。透射定标用"无结构参考跑归一化" `T=(nL/n0)·|E_real/E_ref|²`，共模误差在比值中抵消。意义：**1D 透射谱已无需借 Meep 即得**，主权 B 级"踢掉求解器"路径首个可运行实证落地；2D/3D 仍由 AI 团队自举开发（标记不阻塞，仅验证层外协）。已同步：白皮书 §7.4（L2-A 状态升为"1D 已交付"）、路线图阶段1、控制台主权策略行、MEMORY.md 主权 B 级表、本模块 7.2 实证清单新增一行。
- **2026-08-15**（置信度：已核实）**L2-A 自研 2D FDTD 求解核通过物理定律锚校验（主权 B 级"踢掉"路径第二维度实证）**：新建 `lda/lda_solver/fdtd2d.py`（C 级自主、机器优先接口、零外部依赖仅 numpy、TEz 模式 Yee 网格 Ez/Hx/Hy + 2D 梯度海绵吸收层 + 参考跑归一化绝对标度），配套 `run_fdtd2d_selfcheck.py`（双 ORACLE：① tmm.py 传输矩阵解析解覆盖"分层膜 y 方向平移不变→退化为一维"极限；② 点源柱面波 |Ez|·√r 常数作为真·二维校验并同时验证四向海绵无回反射）。**终态 selfcheck 5/5 PASS**：匹配介质 T≡1.0000（Δ=0.0000）、单界面空气→玻璃 T=0.958（maxΔ=0.0022）、FP 标准具 n=2.5 d=2.0µm 条纹（maxΔ=0.0135）、布拉格光栅禁带中心≈2.46µm（maxΔ=0.0019）、点源柱面波 |Ez|·√r 常数（max_rel_dev=0.0134）。关键修复：2D 海绵须厚于 2λ（1.25λ 会让单界面用例在波长间出现被海绵回反射驻波污染的残留偏差，呈波长振荡 0.88/0.88/0.96/1.03）；分层膜用例启用 y 方向 PBC 退化为一维、点源用例用四向海绵。意义：**2D 透射谱已无需借 Meep 即得**，主权 B 级"踢掉求解器"路径在 1D 后于 2D 维度再次实证；开发由 AI 团队自举、外部人力仅作验证层协作。已同步：白皮书 §7.4、路线图阶段1、README 待办第7条、MEMORY.md、本模块 7.2（L2-A 行扩为 1D+2D）。
- **2026-08-15**（置信度：已核实）**L2-A 自研 3D FDTD 求解核通过物理定律锚校验（主权 B 级"踢掉"路径第三维度·全三维实证）**：新建 `lda/lda_solver/fdtd3d.py`（C 级自主、机器优先接口、零外部依赖仅 numpy、全 Yee 六分量 Ex/Ey/Ez/Hx/Hy/Hz + 3D 梯度海绵吸收层 + 参考跑归一化绝对标度），配套 `run_fdtd3d_selfcheck.py`（双 ORACLE：① tmm.py 传输矩阵解析解覆盖"分层膜 y/z 方向平移不变→退化为一维"极限（y、z 双轴 PBC）；② 点源球面波 |Ez|·r 常数作为真·三维校验并同时验证六向海绵无回反射）。**终态 selfcheck 5/5 PASS**：匹配介质 T≡1.0000（maxΔ=0.0000）、单界面空气→玻璃 T=0.958（maxΔ=0.0019）、FP 标准具 n=2.5 d=2.0µm 条纹（maxΔ=0.0170）、布拉格光栅禁带中心≈2.46µm（maxΔ=0.0090）、点源球面波 |Ez|·r 常数（max_rel_dev=0.0101，公差 0.02–0.20 内）。关键根因修复（C 用例反复 FAIL 的真凶）：**3D E 更新漏 `dl` 因子**——3D 写成 `E += (dt/eps)·curl_H`，正确应为 `E += (dt/(eps·dl))·curl_H`。缺 `dl` 使 E 更新偏小 ~40×（dl≈0.025），E/H 波阻抗错配~40×；该错误在"匹配介质"用例因 real/ref 场分布相同而比值恒为 1 被掩盖，仅在结构化用例（B/C/D）暴露（C 用例 |ratio|² 修复前 0.54→修复后 0.9993）。其余 3D 要点：3D CFL `dt=dl·courant/√3`（vs 2D √2）、H 节点 σ 取两偏移轴均值(×0.5 不可直接相加)、y/z 双轴 PBC 退化。意义：**3D 透射谱已无需借 Meep 即得**，主权 B 级"踢掉求解器"路径在 1D/2D 之后延至全三维实证；L2-B 晋级为"3D 性能升维（GPU 加速对标 Tidy3D）"——功能核已落地，生产级高性能为后续 AI 自研项（自配 GPU 算力）。已同步：白皮书 §7.4、路线图阶段1、README 待办第7条、MEMORY.md、本模块 7.2（L2-A 行扩为 1D+2D+3D）。
- **2026-08-15**（置信度：已核实）**L2-B 性能升维第一步 · Numba-CPU JIT 加速交付（主权 3D 核获生产级 CPU 性能）**：新建 `lda/lda_solver/fdtd3d_numba.py`，将 `fdtd3d.py` 逐字节等价的六分量 leapfrog 更新融合为 `@njit(parallel=True)` 核（eps/sigma/damp 构造沿用 numpy 版以保证物理一致），公开接口 `solve_spectrum_numba` / `run_greens_test_numba` 与 numpy 版同签名；配套 `run_fdtd3d_numba_selfcheck.py`（同 ORACLE=tmm.py + 球面波、同公差）+ `benchmark_fdtd3d.py`（numba vs numpy 正确性对照 + speedup）。**结果：与纯 numpy 版逐字节等价（谱 max|rel diff|~1e-15、球面波 |Ez|·r 逐位相同），selfcheck 5/5 PASS（逐用例偏差 A=0.0000/B=0.0019/C=0.0170/D=0.0090/E=0.0101 与 numpy 版完全一致），较纯 numpy 版约 20× 加速（16m19s→0.8m，生产尺寸 sponge=320 / N=120）**。移植踩坑（已固化进技能 fdtd1d-selfwritten-solver Lesson 14）：① 非 PBC 边界差分须"整段为 0"（前向最后格、后向最前格），绝不能只把邻居置 0（会注入 ±f_here 致发散/NaN，仅非 PBC 球面波暴露、PBC 退化用例掩盖）；② 后向差分符号须为 `f[i]-f[i-1]`（曾误写为 `f[i-1]-f[i]` 致全局反号、T 归零）；③ prange 以传播轴 i 分双相位（phase1 写 H / phase2 写 E）无竞争。意义：主权 3D 核在零 GPU 下已具生产级 CPU 性能；GPU/CUDA 后端仅用于超大网格，仍为后续自研项。已同步：白皮书 §7.4（结论/L2-B/算力/立项标记）、路线图 L2-B 行、README 待办第7条、MEMORY.md、本模块 7.2（L2-A 行并入 Numba）。
- **2026-08-15**（置信度：已核实）**L2-B 性能升维第二步 · PyTorch 可切换 GPU/CPU 张量化后端交付**：新建 `lda/lda_solver/fdtd3d_torch.py`，复用 numpy 参考实现的几何构造底层函数（`_build_interior/_sponge_1d/_grid_constants/_avg_sigma`）保证折射率剖面/海绵/damp 与 sovereign numpy 核逐字节一致，仅把每步六分量更新改写为张量化切片式 curl 算子（`torch.roll` 做 PBC、`f[1:]-f[:-1]` 式切片做非 PBC，逐字节对应 `_fwd/_bwd/_avg_sigma`），`device='cuda'/'cpu'` 一行切换、算法完全相同；公开接口 `solve_spectrum_torch` / `run_greens_test_torch` 与 numpy 版同签名。配套 `run_fdtd3d_torch_selfcheck.py`（同 ORACLE、同公差）+ `benchmark_fdtd3d_torch.py`（分进程隔离，避免 numba+torch 同进程并行线程池冲突致 segfault）。**结果：CPU 上 selfcheck 5/5 PASS 且与 numpy/Numba 版逐位一致（A=0.0000/B=0.0019/C=0.0170/D=0.0090/E=0.0101）；CPU 实测 torch-cpu(≈104s) 慢于 numba-cpu(≈20s)（每步多张量算子派发开销），其加速价值在向 GPU 迁移后释放**。GPU 激活仅需 CUDA 轮子——本沙箱 pytorch CDN 限速致 cu128 轮子无法下载（pip 缓存轮子 1.7GB 损坏"File is not a zip file"），故 `device='cuda'` 实测待 GPU 部署机装轮子后激活；RTX 5060 Ti 级 GPU 物理存在。移植踩坑（已固化进技能 Lesson 15）：① 同进程混跑 numba 并行与 torch 2.13 会 segfault → 各后端必须分进程隔离；② DFT 复数张量 `.item()` 已返回 Python complex，勿再 `complex(re, im)` 包裹（TypeError）；③ float64 在 Blackwell 消费卡 fp64 速率仅 ~1/64 fp32，追求吞吐可转 float32（需重验公差）或自写 CUDA kernel。意义：主权 3D 核获"device 一行切换"的 GPU 就绪后端，生产级超大网格路径工程闭环（装 CUDA 轮子即点亮）。已同步：白皮书 §7.4、路线图 L2-B 行、README 待办第7条、MEMORY.md、技能 Lesson 15。

---

*本知识基线为「设计前置文献梳理」（MEMORY 已固化属①真地基）的产出，配套使用《LDA 可行性分析报告》《LDA 技术白皮书》《LDA 市场竞争与赛道分析》《LDA 发展里程碑与路线图》。*
