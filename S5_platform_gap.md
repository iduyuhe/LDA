# S5 平台缺口清单 · 达 53+/千比特级超导芯片 LDA 还缺什么

> 阶段：S5 规划第一轮（「规模对标基线」+「平台缺口清单」两件事之二）
> 日期：2026-09-29
> 配套：`S5_scale_baseline.md`（对标基线）
> 红线：纯几何 + 闭式物理（零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则）。

---

## 0. 分类法

- **A 类 · 平台内可补**（几何 + 闭式物理，不破红线）：LDA 自建模块即可闭环，建议落 D 编号。
- **B 类 · 架构/外部依赖**（破/超红线，需伙伴或外部）：量子线路仿真、门保真实测、封装、Foundry PDK、QEC 逻辑验证。
  这类**不是 LDA 的缺口**，是「LDA 设计产出 → 外部分发」的接口，列出仅为诚实边界。

优先级：**P0** = 规模上路必经（不做则无法到 53+）；**P1** = 对标真实架构必备；**P2** = 完善项。

---

## 1. A 类缺口清单（平台内可补 · 建议 D 编号）

| # | 缺口 | 影响（对标基线§3 对应项） | 建议模块 / D 编号 | 优先级 | 破红线？ | 落地抓手（复用现有） |
|---|---|---|---|---|---|---|
| G1 | **大 N P&R + 布线路由沟道** | 9→53/1000+ 阵列排布 + 馈线/控制走线走廊未系统化 | `sc_array.py` 扩 `array_cell` 或新 `sc_routing` · D-137 | P0 | 否 | 复用 `array_cell` 网格 + `readout_array_cell` 沟道地范式 |
| G2 | **heavy-hex 拓扑生成器** | IBM 全系 heavy-hex（2–3 邻居），LDA 仅方阵 | 新 `sc_topology` · D-138 | P1 | 否 | 复用 `sc_array` 的平移/耦合重组 + DRC/LVS 同口径 |
| G3 | **可调耦合器几何** | Sycamore/IBM 用可调耦合器；LDA S2 仅固定 Cc | `sc_coupler.py` 扩可调耦合器单元 · D-139 | P1 | 否 | 复用 `coupled_pair_cell` + `coupler_solver`（J 双验证纪律） |
| G4 | **读出频分复用几何 + 调度** | 真实 mux：多谐振腔/馈线、频率分配避撞 | 新 `sc_readout_mux` · D-140 | P1 | 否 | 复用 `sc_readout.readout_array_cell` + `crosstalk_budget` 的 f_i 派生 |
| G5 | **控制多线几何 + 逐线串扰预算** | 真实 XY+Z+耦合器 flux 三线分离 + 逐线串扰 | `sc_readout.py` 扩控制桩 / 新 `sc_control` · D-141 | P1 | 否 | 复用 `sc_readout._control_xtalk`（fringe 闭式）扩到三线 |
| G6 | **频率碰撞/拥挤分配器** | 53+ qubit 频率避撞（ζ_zz 依赖 Δ=f_j−f_i） | 新 `sc_freq_alloc` · D-142（纯 numpy 组合优化） | P0 | 否 | 复用 `crosstalk_budget` 的 E_J→f_i（koch_f01）+ 约束求解 |
| G7 | **DRC/LVS/预算规模压力验证** | 规则/LVS/预算在 9→53/1000+ 的运行时与元素数未压 | `run_schip_s5_smoke.py`（规模压力门禁）· D-143 | P0 | 否 | 复用 S3/S4 smoke 结构 + `run_ci_regression.CORE_SMOKES` 接线 |
| G8 | **阵列级 + 封装/辐射损耗预算** | per-qubit 损耗未扩到阵列 + 封装/辐射项 | `sc_readout.loss_budget` 扩 `array_loss_budget` · D-144 | P1 | 否 | 复用 `loss_budget`（参与比+Purcell，D-88 闭式） |
| G9 | **批量签核 / CI at scale** | 当前手动 demo，缺批量多配置签核 | `examples/lda_schip_s5.py` 批量 demo + 门禁 | P1 | 否 | 复用 `lda_schip_s4.py` 闭环范式 |

---

## 2. B 类（架构/外部依赖 · 非 LDA 自建，列作诚实边界）

| # | 能力 | 为何超红线 | 外部接口建议 |
|---|---|---|---|
| B1 | 量子线路仿真 / Statevector / XEB | 需量子 SDK（Strawberry Fields/PennyLane/QuTiP），破红线 | 分发 GDS + 设计参数给外部 Qiskit/Qutip 流程 |
| B2 | 门保真度实测 / 退相干实测（T1/T2 量测） | 需实测仪表 + 实测 PDK，非设计规则 | 分发设计给 Foundry/测试厂；LDA 只出设计预算（G8） |
| B3 | 低温封装 / 布线（>1 mile 低温线） | 集成工程，非版图 | 分发封装规格给系统厂 |
| B4 | Foundry PDK / 实测材料参数（tanδ、ε_eff 真值） | D5 外部真值，走 `CalibrationWindow` | 外部标定后回填 `loss_budget` 参数 |
| B5 | QEC 表面码逻辑验证 | 需线路仿真（B1），超红线 | 几何可放表面码格（借 G1/G2 拓扑），逻辑验证外部 |

---

## 3. 红线校验（每条 A 类缺口都守得住）

- **零量子 SDK**：G1–G9 全部是几何 P&R + 闭式物理（ζ_zz、fringe 电容、参与比、Purcell、频率分配组合优化），不引任何量子仿真库。✅
- **LLM 不进判决路径**：所有签核走 `make_check` + 闭式 golden（Blais 2004、D-88），与 S1–S4 同纪律。✅
- **DRC 限值为设计规则**：G7 规模压力验证仍用既有 9 则 DRC / 9 判据 LVS 限值（可覆盖、非实测 golden）。✅
- **突变探针纪律**：G7 门禁须配进程内突变探针（同 S3/S4 打法），每条必红还原复绿，防假绿。✅

---

## 4. S5 候选落地顺序（建议）

**第一波（规模上路 · P0）**：G1（大 N P&R）→ G6（频率避撞）→ G7（规模压力门禁）。
这三项不做，连「把 53 qubit 阵列出全 + 签核」都跑不通。

**第二波（对标真实架构 · P1）**：G3（可调耦合器）→ G4（读出 mux）→ G5（控制多线）→ G8（阵列损耗）→ G9（批量签核）→ G2（heavy-hex，对标 IBM）。

**第三波（完善）**：G2 若优先对标 IBM 可提前；heavy-hex 与方阵拓扑共用 DRC/LVS 框架。

> 注意：B1–B5 不在 S5 实现范围。S5 的交付物是「能设计 + 几何签核 53+/千比特级芯片的版图与预算」，
> 门保真/逻辑验证由外部伙伴承接——LDA 在超导征程的定位与 LOQC 征程一致：**吃狗粮检阅平台，产出可制造版图 + 设计预算**，不自证量子性能。

---

## 5. 规模数学（S5 上路前的量级直觉）

- **元素数标度**：N qubit 方阵 ≈ N(transmon) + 2N−2(耦合器) + N(读出) + N(控制) + 地框 ≈ **6N 元素**；
  N=53 ⇒ ~320 元素，N=1000 ⇒ ~6000 元素。LDA 自写 GDS 编码器（`gds_export`）需确认此量级运行时（G7）。
- **串扰 pair 数**：N qubit 全 pair = N(N−1)/2；N=53 ⇒ 1378 pair，N=1000 ⇒ 499500 pair。
  `crosstalk_budget` 当前 O(N²) 全 pair 遍历，N=1000 需规模压测（G7）。
- **频率避撞**：N=53 需 53 个不碰撞 transmon 频率（E_J 分配），N=1000 是组合优化（G6 纯 numpy 可解）。
- **损耗**：per-qubit 参与比 + Purcell 在 N=1000 时封装/辐射项主导（G8），设计预算口径（非实测 golden）。
