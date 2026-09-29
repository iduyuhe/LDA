# S5 规模对标基线 · LDA 超导征程 vs Google Sycamore / IBM 处理器

> 阶段：S5 规划第一轮（「规模对标基线」+「平台缺口清单」两件事之一）
> 日期：2026-09-29
> 口径：LDA 红线 = 纯几何 + 闭式物理（零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则）。
> 对标来源：Arute et al. Nature 574, 505 (2019)；IBM Quantum Summit 2023；arxiv 2410.00916 / 2410.00917；quantumaireport 2026 硬件对比。

---

## 0. 目的与诚实边界（先讲清能比什么）

LDA 超导征程（S1–S4）已能**设计 + 几何签核**超导 transmon 芯片的全链路：
单比特（D-133）→ 耦合对（D-134）→ N 比特阵列 P&R（D-135）→ 读出/控制线路 + 串扰/损耗预算（D-136）。

**本基线的可比范围**：版图几何、拓扑、耦合/读出/控制结构、串扰与损耗的**设计预算口径**。
**不可比（红线之外）**：量子线路仿真、门保真度实测/XEB、退相干实测、封装与 Foundry PDK——
这些是 LDA 故意不做的（纯几何 + 闭式物理），需外部或伙伴补齐，详见 `S5_platform_gap.md` §3。

---

## 1. LDA 当前超导能力快照（S1–S4，函数级）

| 征程 | 模块 / 函数 | 能力 | 验收（已闭环） |
|---|---|---|---|
| S1 (D-133) | `sc_layout.py`：`transmon_cell` / `transmon_gds` / `run_sc_drc`(4则) / `sc_lvs_signoff` | 单 transmon 单元真 GDS（层 10/11/12）+ 几何 DRC/LVS | 物理双验证 Koch f01↔对角化 rel=0.42%，f01=4.887GHz，α=−0.356 |
| S2 (D-134) | `sc_coupler.py`：`coupled_pair_cell` / `coupled_pair_physics` / `sc_pair_lvs_signoff`(6判据) | 耦合 transmon 对（控制+目标+固定电容耦合器）+ 多网 LVS | J 双验证（coupler_solver 严格对角化↔解析闭式 rel≤5%）；cross_resonance ω_CR=2.59MHz，t_CR=1.21µs，σ_zz=0.21MHz |
| S3 (D-135) | `sc_array.py`：`array_cell` / `array_gds` / `run_sc_array_drc`(5则) / `sc_array_lvs_signoff`(6判据) / `array_physics` | N 比特**2D 网格阵列 P&R**（最近邻耦合路由）+ 整框地 + 逐边物理签核 | demo 2×2 / 3×3 全闭环 PASS |
| S4 (D-136) | `sc_readout.py`：`readout_array_cell` / `readout_gds` / `run_readout_drc`(9则) / `readout_lvs_signoff`(9判据) / `crosstalk_budget` / `loss_budget` / `readout_physics` | 阵列 + 读出谐振腔 + 行馈线 + 控制桩几何；全 pair ZZ 串扰 + 控制串扰 + per-qubit 损耗双预算 | demo 2×2&3×3 PASS（max_stray_zz=0.876≤1.0MHz，min_t1=46.13≥20µs） |

**拓扑事实（关键）**：`array_cell` 生成 `rows×cols` 网格，含**横向 in-row + 纵向 inter-row 最近邻耦合器**
⇒ 原生拓扑 = **2D 方阵、4 邻居连通** = Google Sycamore 的矩形点阵。IBM 的 **heavy-hex（2–3 邻居）**
LDA 当前**不生成**（缺口见 `S5_platform_gap.md` G2）。

**当前验证上限**：闭闭环仅跑到 **3×3 = 9 qubit**；`array_cell` 接受任意 `rows/cols`，但 9 以上未做规模压力验证。

---

## 2. 国际对标基线（事实表，含出处）

| 指标 | Google Sycamore (SYC-53, 2019) | IBM Eagle (2021) | IBM Osprey (2022) | IBM Condor (2023) | IBM Heron r3 (2025–26) | Google Willow (2024) |
|---|---|---|---|---|---|---|
| 物理 qubit 数 | 53（设计 54，1 失效） | 127 | 433 | 1121 | 133→156 | 105 |
| 拓扑 | 2D 方阵 4 邻居 | heavy-hex（2–3 邻居） | heavy-hex | heavy-hex | heavy-hex + 可调耦合器 | 2D 方阵（表面码格） |
| 耦合器 | 可调耦合器（fSim） | 交叉共振（固定） | 交叉共振 | 交叉共振 | **可调耦合器** | 可调耦合器 |
| 1Q 门误差 | ~0.10–0.20% | — | — | — | — | — |
| 2Q 门误差 | ~0.7–0.9%（隔离）/ ~1.4%（并行）·√iSWAP | — | — | 可比 Osprey（非最优） | **~0.3%（2Q 保真 99.7%）** | **~0.15%（2Q 保真 99.85%）** |
| T1 | ~15–20 µs | ~200 µs | ~200 µs | ~200 µs | **~300 µs** | ~70 µs |
| 读出误差 | ~3.8%（\|1⟩） | — | — | — | 优 | — |
| 门速 | 1Q~25ns / 2Q~32ns | — | — | — | — | — |
| 读出方式 | 频分复用（resonator mux） | mux | mux | mux | mux | mux |
| 控制线 | 每 qubit XY + Z(flux) + 耦合器 flux（277 DAC） | 每 qubit XY+Z | 同 | 同（>1 mile 低温线） | 同 | 同 |
| 标志性成果 | RCS 优越性（200s vs 经典 1e4 年） | 破百比特 | 433 比特 | 破千比特（产率/规模演练） | 性能旗舰 | **below-threshold QEC**（距离↑错误率↓） |

出处：Sycamore 表（Nature 574:505, 2019；arxiv 2410.00917 Table I）；IBM 线路（IBM Quantum Summit 2023；arxiv 2410.00916）；2026 硬件对比（quantumaireport 2026）。

---

## 3. LDA 当前能力 ↔ 对标逐项映射

| 对标维度 | LDA 现状（S1–S4） | 离 Sycamore 53 的距离 | 离 IBM 千比特级的距离 |
|---|---|---|---|
| **拓扑** | 2D 方阵 4 邻居（= Sycamore）✅ 拓扑对齐 | 已对齐 | heavy-hex 未生成（缺口 G2） |
| **单元几何 / 真 GDS** | transmon 单元 + 耦合对 + 阵列全真 GDS（层 10/11/12）✅ | 单元级已对等 | 单元级对等；阵列规模未压 |
| **耦合器** | S2 固定电容耦合器（Cc=0.007，解析闭式锚） | Sycamore/IBM 用**可调**耦合器 ⇒ 缺可调耦合器几何（G3） | 同 G3 |
| **读出** | S4 每 qubit 1 读出谐振腔 + 行馈线（几何） | Sycamore **频分复用**多谐振腔/线 ⇒ 缺 mux 调度（G4） | 同 G4 |
| **控制线** | S4 每 qubit 1 控制桩（fringe 串扰预算） | 真实芯片 XY+Z+耦合器 flux 三线分离 ⇒ 缺多线几何+逐线串扰（G5） | 同 G5 |
| **串扰预算** | 全 pair ζ_zz（Blais 2004 二阶微扰闭式）+ 控制 fringe 串扰 ✅ 方法论对齐 | 缺**频率碰撞/拥挤**模型（53 qubit 频率分配避撞，G6） | 同 G6（千比特更尖锐） |
| **损耗预算** | per-qubit 参与比 + Purcell（D-88 闭式）✅ 方法论对齐 | 缺阵列级 + 封装/辐射损耗（G8） | 同 G8（千比特级封装损耗主导） |
| **DRC/LVS 规模** | 规则 9 则 / LVS 9 判据，验证到 9 qubit | 未压到 53（G7 规模压力） | 未压到 1000+（G7） |
| **签核自动化** | 手动 demo（S3/S4） | 缺批量签核（G9） | 同 G9 |
| **门保真/退相干实测** | ❌ 红线之外（无量子 SDK） | 不可自验，仅设计预算 | 同（诚实边界） |
| **QEC 表面码布局** | ❌ 未做 | 几何可放但逻辑验证超红线 | 同 |

---

## 4. 结论：LDA 现在能设计到什么规模、卡在哪

1. **拓扑已对齐 Sycamore**：2D 方阵 4 邻居是 LDA 原生拓扑，对标 Sycamore 无需改拓扑；对标 IBM heavy-hex 需新增拓扑生成器（G2）。
2. **方法论已对齐**：串扰（ζ_zz 闭式）、损耗（参与比+Purcell 闭式）、DRC/LVS（几何）三套签核方法学
   与国际设计实践同口径，扩到 53/1000+ 是**规模工程量**，不是方法论缺口。
3. **真实卡点（按影响排序）**：
   - **规模压力未验证**（G7）：9 qubit → 53/1000+ 的 DRC/LVS/预算运行时与元素数未压。
   - **可调耦合器几何缺失**（G3）：Sycamore/IBM 都用可调耦合器，LDA 仅固定 Cc。
   - **读出频分复用缺失**（G4）：单谐振腔/线 ≠ 真实 mux 架构。
   - **控制多线 + 频率避撞缺失**（G5/G6）：真实芯片三线分离 + 频率分配避撞。
4. **红线守得住**：上述缺口全部落在「几何 + 闭式物理」范围内（平台内可补）；
   只有门保真实测 / QEC 逻辑验证属于红线之外，需外部伙伴，不计入 LDA 自身缺口。

→ 下一步见 `S5_platform_gap.md`：把上述 G1–G9 落成带 D 编号、优先级、红线校验的缺口清单与 S5 候选落地顺序。
