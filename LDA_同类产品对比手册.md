# LDA 同类产品对比手册

> 版本：v1.0（2026-08-25）· 配套 LDA v0.6.x
> 用途：生态伙伴 / 院校 / 投资 / 内部决策 快速理解 LDA 在市场上的位置
> 数据来源：公开信息检索（2026-08-25 多机构报告与厂商公开资料）；仅作客观对比参考，**不构成采购建议**

---

## 0. 阅读说明与诚实声明

- **本手册对比的是"公开能力/定位"，不贬损任何产品**；各家在各自定位上都是成熟工具
- LDA 栏按真实状态填写：**开源 · 设计级（非签核级）· 自研求解器**——不宣称与商业签核工具同等精度
- 商业工具信息来自厂商公开资料与行业报告，可能滞后于最新版本；具体以厂商官方为准
- 对比维度聚焦：**定位 / 光子器件仿真 / 电路级 / 版图 / PDK / 逆设计 / 量子 / 验证体系 / Agent 原生 / 许可形态**

---

## 1. 对比对象清单（四类）

| 类别 | 产品 | 一句话定位 |
|---|---|---|
| 商业端到端 | **Synopsys OptoCompiler** | 电子-光子统一 IC 设计（PIC 布局/仿真/验证） |
| | **Ansys Lumerical**（母公司 Synopsys） | 光子器件级 FDTD/MODE → 电路级 INTERCONNECT 全流程 |
| | **Cadence EPDA**（Virtuoso 基础） | 原理图驱动光子版图 + 电光协同 |
| | **Siemens EDA**（L-Edit Photonics + Calibre） | 光子版图 + 验证（Calibre DRC/LVS） |
| | **Keysight Photonic Designer**（2025 发布） | 光子电路设计/仿真/PDK，验证速度导向 |
| 商业专业厂商 | **Luceda IPKISS**（比利时） | 参数化 PIC 设计 + PDK 集成（2026 加验证/DRC/SPICE） |
| | **Optiwave / VPIphotonics / COMSOL / Silvaco** | 光电器件仿真 / 系统级建模 / 多物理场 / TCAD |
| 开源与云 | **gdsfactory**（全球最流行开源） | 光子/量子/模拟芯片参数化布局框架（已商业化 GDSFactory+） |
| | **Meep / SAX / MPB / KLayout / Nazca** | 开源求解器与布局工具生态 |
| | **Tidy3D**（Flexcompute，云） | 云端 FDTD（GPL 前端 + 美属云） |
| 量子 Q-EDA | **IBM Qiskit Metal**（开源） | 超导量子芯片版图设计 |
| | **本源坤元**（本源量子，国内首个 Q-EDA） | 超导/半导体量子芯片版图自动化（72 比特 6'50"） |
| | **LDA（本系统）** | 开源 · Agent 原生 · 光子+量子 器件设计验证闭环 |

---

## 2. 核心对比矩阵

### 2.1 商业端到端平台（签核级）

| 维度 | Synopsys OptoCompiler | Ansys Lumerical | Cadence EPDA | Siemens EDA | Keysight Photonic Designer |
|---|---|---|---|---|---|
| 光子器件仿真 | ✅（FDTD 联动） | ✅ FDTD/MODE 行业标杆 | ✅ | ✅ | ✅ |
| 电路级仿真 | ✅ INTERCONNECT | ✅ INTERCONNECT | ✅ | ✅ | ✅ |
| 版图 | ✅ 统一版图 | 🔶（联动） | ✅ Virtuoso 原理图驱动 | ✅ L-Edit | ✅ |
| PDK 集成 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 逆设计 | ✅ PID | ✅ PID（超透镜 20× 缩小案例） | 🔶 | 🔶 | 🔶 |
| 多物理场 | ✅ 电光热 | ✅ 光-电-热-量子阱 | ✅ | ✅ | ✅ |
| 签核/良率 | ✅ 工艺公差 | ✅ 3σ 工艺波动/良率 | ✅ | ✅ Calibre | ✅ |
| 量子 | 🔶 光子量子电路 | ✅ 量子光子电路（Xanadu 案例） | 🔶 | 🔶 | 🔶 |
| Agent/AI | 🔶 AI 助手级 | ✅ Engineering Copilot | 🔶 | 🔶 | 🔶 |
| 许可 | 商业授权 | 商业授权（按模块） | 商业授权 | 商业授权 | 商业授权 |

### 2.2 开源与云生态

| 维度 | gdsfactory / GDSFactory+ | Meep / SAX / KLayout | Tidy3D | **LDA** |
|---|---|---|---|---|
| 许可 | MIT 开源（+商业 SaaS） | MIT/GPL 开源 | GPL 前端 + 美属云 | **MIT 开源** |
| 光子器件仿真 | 🔶（插件集成 Tidy3D/Meep） | ✅ Meep FDTD | ✅ 云端 FDTD | ✅ 自研 1D/2D/3D FDTD |
| 电路级 | ✅ SAX | ✅ SAX | 🔶 | 🔶（器件级为主） |
| 版图 | ✅ 最强开源布局框架 | ✅ KLayout | 🔶 | 🔶 基元几何生成 |
| PDK | ✅ 43+ PDK | 🔶 | ✅ | 🔶 管道已建（评审流接入） |
| 逆设计 | 🔶（插件） | ✅ lumopt 等 | ✅ | ✅ 谱形/3D adjoint（15.68× 实测） |
| 量子 | ✅ 通用布局（KQcircuits） | 🔶 | 🔶 | ✅ QEDA 器件级严格求解（transmon/ZZ） |
| **验证锚体系** | 🔶 DRC/LVS（GDSFactory+） | 🔶 | 🔶 | ✅ **物理定律锚+实证锚 双 ground，LLM 不进判决** |
| **Agent 原生** | ✅ agent-native 布局 | 🔶 | 🔶 | ✅ **L1 协议 + Agent 自迭代闭环** |
| 形态 | 本地/商业云 | 本地 | 云 | 本地 + WebUI 57 面板 |

### 2.3 量子 Q-EDA

| 维度 | IBM Qiskit Metal | 本源坤元 | **LDA（QEDA 栈）** |
|---|---|---|---|
| 定位 | 超导量子芯片**版图** | 量子芯片**版图自动化**（超导/半导体） | 量子**器件级设计验证**（transmon 等） |
| 版图 | ✅ | ✅（72 比特 6'50"） | 🔶（几何基元） |
| 器件物理仿真 | 🔶 | ✅ 集成 TCAD/电路仿真 | ✅ **严格对角化 + 色散读出** |
| 验证 | 🔶 | 🔶 | ✅ **χ/n_crit/Purcell 死标量验收** |
| 许可 | Apache 开源 | 商业/云 | **MIT 开源** |
| 与光子统一 | ❌ | ❌ | ✅ **统一 L0 IR（PDA+QEDA）** |

---

## 3. 分类详述

### 3.1 商业端到端（Synopsys / Ansys / Cadence / Siemens / Keysight）

- **共同点**：签核级、全流程（器件→电路→版图→验证→良率）、多物理场、电光协同（EPDA）、PDK 深度集成、商业授权（量级数万美元/模块/年）
- **趋势（2025-2026）**：巨头整合加速（Ansys 并入 Synopsys 生态、Lumerical 与 OptoCompiler 直接桥接、Verilog-A CML 电光联合仿真、Keysight 2025 发布 Photonic Designer）；AI 助手入场（Lumerical Engineering Copilot）
- **对 LDA 的意义**：这些是"端到端整合+签核"路线——**结构上不可能开放内核**（收入依赖授权），正是 LDA"开放内核"的空白位

### 3.2 商业专业厂商（Luceda / Optiwave / VPI / COMSOL / Silvaco）

- **Luceda IPKISS**：参数化 PIC 设计 + PDK 集成标杆；2026.03 版扩展验证/DRC/dummy/SPICE——**"PDK 编排"成为 2025 后市场争夺焦点**（Wave Photonics 也推出 PDK 管理平台）
- 其余厂商分别在系统级（VPI）、多物理场（COMSOL）、TCAD（Silvaco）、器件电路（Optiwave）细分

### 3.3 开源与云生态

- **gdsfactory**：全球最流行开源芯片布局框架（光子/量子/模拟），43+ PDK、20+ 工具集成，**已商业化（GDSFactory+）且 agent-native**——光子布局侧 LDA 的最直接参考系
- **Meep/SAX/KLayout 等**：单点工具生态，分散
- **Tidy3D**：云端 FDTD 代表（GPL 前端+美属云），性能强但主权/数据受美属云约束

### 3.4 量子 Q-EDA

- **Qiskit Metal**（IBM，Apache 开源）：超导量子芯片版图
- **本源坤元**（本源量子）：国内首个 Q-EDA，2022 首发 → 2025 第五次迭代（72 比特全自动版图 6'50"、千万级网格建模）；已被列为中国"未来产业"半导体四大机会之一
- **市场特征**：玩家稀少、偏版图自动化；**器件级物理验证（色散读出/串扰定量）仍是空白**——LDA 的切入角

---

## 4. LDA 的定位结论（差异化五条）

| # | 差异化 | 说明 | 谁能跟 |
|---|---|---|---|
| 1 | **开放内核**（MIT 自研求解器） | 商业巨头结构上做不了（收入靠授权）；开源生态只做布局/单点 | 暂无 |
| 2 | **验证锚体系**（物理定律+实证锚双 ground，LLM 不进判决） | 可追溯、防"纯 AI 互证"；行业报告明确"AI 须与可信求解器+人工评审集成"——LDA 是先行实践 | 商业工具无此透明承诺 |
| 3 | **Agent 原生**（L1 协议+自迭代闭环） | 与行业"AI 驱动设计"趋势吻合，且把验证裁判独立于 AI | gdsfactory agent-native 布局（光子侧） |
| 4 | **光子+量子统一 L0 IR** | 双栈同一中间表示；光子准红海、量子相对蓝海 | 无同构 |
| 5 | **主权友好**（B 级镜像、数据不出域、A/B/C 分级） | 面向中国晶圆厂/院校的采购与合规叙事 | 美属云工具天然劣势 |

**一句话定位**：LDA = **商业工具的"开放内核"空白位 + gdsfactory 未覆盖的"验证锚体系" + Q-EDA 未覆盖的"器件级物理验证"**——三个空白交叉点。

**诚实边界（务必记住）**：
- LDA 光子仿真为 2D/3D FDTD **设计级**，无商业工具的**多物理场（电/热/量子阱）与签核级良率分析**
- LDA **无电路级仿真**（INTERCONNECT 类）与**完整版图编辑器**（gdsfactory 布局更强）
- LDA 量子侧是**器件级**（transmon 色散/ZZ），**非芯片版图**（Qiskit Metal/本源坤元更强）
- 真实 PDK/签核数据待发动期联动（D-62），管道已建

---

## 5. 数据来源与时效

- 2026-08-25 检索：PhotonDelta、PW Consulting、360iResearch、Global Info Research、HTF Market Insights、Ansys/Lumerical 公开资料、gdsfactory.com、本源坤元公开资料
- 市场行情速览（详见《市场行情》讨论）：光电子 EDA 工具 2025 约 $3.5-17 亿（口径差异），CAGR 6-10%（PDA 细分 19% 最快）；量子 Q-EDA 入中国"未来产业"清单
- 本手册为快照，建议每半年刷新；厂商信息以官方为准

---

*本手册由 LDA 项目整理，公开信息客观对比，不构成采购建议或投资依据。*
