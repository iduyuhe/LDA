# LDA 设计能力成熟度模型（DMM · Design Maturity Model）

> 🔴 **本文件由 `lda/run_dmm_scorecard_smoke.py --write-doc` 自动生成，请勿手工编辑**（手改必被该门禁的「重新生成 == 磁盘文件」断言判红）。
> 真相源：`lda/lda_harness/dmm_scorecard.py`（能力表 + 事实采集 + 判级函数）。

## 它是什么

DMM 是 **VMM（`docs/verification_maturity_model.md`）的姊妹模型**：VMM 回答「某个物理量算得对不对」，DMM 回答「**平台能设计什么、这项能力在第几级、怎么升级**」。
两级共用同一套纪律：诚实标注 · 每项必写升级路径 · 不得越级谎报。

## 级别定义（D0–D5）

| 级 | 名称 | 判定标准（**本仓机器化口径**） |
|---|---|---|
| D0 | 不存在 | 模块缺失，或模块在但**无入口符号** |
| D1 | 能跑 | 模块存在 + 入口符号存在 |
| D2 | 可复现 | D1 + 其门禁登记进 `CORE_SMOKES` |
| D3 | 可自证 | D2 + **反向证据**（探针／自身门禁反向断言／其所引用证据门禁的反向断言） + 引用 ≥1 个**独立证据门禁** |
| D4 | 可交付 | D3 + **交付三要素**：① G4 几何回提**硬开** ② 单命令链存在 ③ 该能力在其准入表内 |
| D5 | 可外签 | 真 foundry deck 签认／流片实测回流 —— **外部，本模型永不自动判达** |

## 当前打分（**机器推导**，非手写）

| 项 | 值 |
|---|---|
| 能力总数 | 25 |
| 各级分布 | **D3 22** · **D4 3** |
| **D4 能力数（M2 指标）** | **3**（出口判据 ≥3 ⇒ ✅ 达成） |
| D3 及以上 | 25 / 25 |
| 一致性审计 | ✅ 零违规 |

| id | 能力 | 级 | 实现模块 | 门禁 | 反向证据来源 | 探针（最近实跑） | 交付链 |
|---|---|---|---|---|---|---|---|
| C01 | 器件级设计搜索 → GDS 单命令交付（lda build） | **D4** | `lda/lda_design/goal_build.py` | `run_cli_build_smoke.py` | own_smoke/independence_guard | — | `lda build <goal.json> --out DIR · 单条命令` |
| C02 | 链路装配 → GDS + DRC/LVS 签核（lda check） | **D4** | `lda/lda_l2/chip_layout_export.py` | `run_lvs_smoke.py` | independence_guard | — | `lda check <link.json> --out DIR · 单条命令` |
| C03 | WebUI 设计闭环端到端（设计包 → 可下载 GDS + 同源签核） | **D4** | `lda/lda_webui/routes.py` | `run_webui_tapeout_drc_smoke.py` | own_smoke/independence_guard | — | `POST /api/design_tapeout + GET /api/design_gds · 一次点击` |
| C04 | G4 器件参数几何回提（版图↔原理图 尺寸一致） | **D3** | `lda/lda_l2/lvs_geom.py` | `run_lvs_geom_smoke.py` | own_smoke/independence_guard | — | — |
| C05 | 横向交叉验证网（跨求解器 ≥2 方法互验） | **D3** | `lda/run_cross_solver_matrix_smoke.py` | `run_cross_solver_matrix_smoke.py` | probe | `scripts/p3_matrix_probe.py`（9 格 · 判据 D 7 格（convergent）） | — |
| C06 | MZI 网格 P&R（mesh_pnr） | **D3** | `lda/lda_layout/mesh_pnr.py` | `run_wdm_mesh_pnr_smoke.py` | own_smoke/independence_guard | — | — |
| C07 | WDM × 2D 共享网格（U1） | **D3** | `lda/lda_layout/wdm_shared_mesh_pnr.py` | `run_wdm_shared_mesh_smoke.py` | own_smoke/independence_guard | — | — |
| C08 | 编译器 / AI 框架前端（U5） | **D3** | `lda/lda_l2/compiler_frontend.py` | `run_compiler_frontend_smoke.py` | own_smoke/independence_guard | — | — |
| C09 | 微环 κ_c FDTD 标定（U3） | **D3** | `lda/lda_l2/ring_kappa_calib.py` | `run_ring_kappa_calib_smoke.py` | own_smoke/independence_guard | — | — |
| C10 | 微环权重库 MRR（U4） | **D3** | `lda/lda_l2/ring_weight_bank.py` | `run_ring_weight_bank_smoke.py` | own_smoke/independence_guard | — | — |
| C11 | 损耗感知编译（U7） | **D3** | `lda/lda_l2/loss_aware_compile.py` | `run_loss_aware_compile_smoke.py` | own_smoke/independence_guard | — | — |
| C12 | 良率 / 容错映射（U6） | **D3** | `lda/lda_l2/yield_fault_tolerance.py` | `run_yield_fault_tolerance_smoke.py` | own_smoke/independence_guard | — | — |
| C13 | 非易失权重后端（U8） | **D3** | `lda/lda_l2/nonvolatile_weight_backend.py` | `run_nonvolatile_weight_backend_smoke.py` | own_smoke/independence_guard | — | — |
| C14 | 校准固件协议（U10） | **D3** | `lda/lda_l2/calibration_protocol.py` | `run_calibration_protocol_smoke.py` | own_smoke/independence_guard | — | — |
| C15 | G20 光域 Pareto（T6.1） | **D3** | `lda/lda_l2/optical_pareto.py` | `run_optical_pareto_smoke.py` | probe/own_smoke/independence_guard | `scripts/p6_probe.py`（7/7 会响） | — |
| C16 | WDM 信道规划 K 提升（T6.2） | **D3** | `lda/lda_layout/wdm_channel_plan.py` | `run_wdm_channel_plan_smoke.py` | probe/own_smoke/independence_guard | `scripts/t62_probe.py`（11/11 会响） | — |
| C17 | 瓦片档位化（T6.3） | **D3** | `lda/lda_l2/mesh_tiling.py` | `run_mesh_tiling_smoke.py` | probe/own_smoke/independence_guard | `scripts/t63_probe.py`（12/12 会响） | — |
| C18 | EIC 行为级（T6.4） | **D3** | `lda/lda_l2/eic_behavioral.py` | `run_eic_behavioral_smoke.py` | probe/own_smoke/independence_guard | `scripts/t64_probe.py`（8/8 会响（含跨文件 T8）） | — |
| C19 | 真 PML / CFS-PML（G11） | **D3** | `lda/lda_solver/cpml.py` | `run_cpml_absorber_smoke.py` | probe/independence_guard | `scripts/p4_cpml_probe.py`（10/10 会响（2D 779.6× / 3D 152.4×）） | — |
| C20 | 任意多边形栅格化（G16） | **D3** | `lda/lda_solver/voxel_field.py` | `run_verify_voxel_pipeline_smoke.py` | probe/independence_guard | `scripts/p4_polygon_probe.py`（10/10 会响） | — |
| C21 | 时域色散 / 各向异性 / 非线性（G13） | **D3** | `lda/lda_solver/dispersive.py` | `run_dispersive_smoke.py` | probe/independence_guard | `scripts/p4_g13_probe.py`（10/10 会响） | — |
| C22 | 全矢量模式求解（G12-H/A/B） | **D3** | `lda/lda_solver/full_vector_mode_solver.py` | `run_full_vector_mode_smoke.py` | probe/own_smoke/independence_guard | `scripts/g12b_probe.py`（6/6 会响（G12-A 另有 g12a_probe 6/6）） | — |
| C23 | SPICE 网表导出 | **D3** | `lda/lda_l2/spice_netlist.py` | `run_spice_netlist_smoke.py` | own_smoke/independence_guard | — | — |
| C24 | gdsfactory 单向桥（gf → LDA） | **D3** | `lda/lda_l1/gdsfactory_bridge.py` | `run_gdsfactory_bridge_smoke.py` | independence_guard | — | — |
| C25 | 实证锚库与 M6 口径（T5.3） | **D3** | `lda/lda_harness/empirical_m6.py` | `run_empirical_anchor_smoke.py` | probe/own_smoke/independence_guard | `scripts/p5_probe.py`（10/10 会响） | — |

## 🔴 诚实边界（必须与分数同读）

1. 本表判的是**「事实代理」**，不是「能力质量」的最终裁判 —— 质量由所引用的**门禁/探针**承担；本表只保证「该能力宣称的级别所依赖的事实确实存在」，缺一即**降级**。
2. **探针「会响」是运行期事实** ⇒ 不入判级（探针不进 `CORE_SMOKES`），只在表中记为「最近一次实跑」。
3. **D5 恒不可达**：内部判据只能到 D4（规划 §2.2：「D4 是内部能达到的上限」）。
4. 级别**累积**：D(n) 需 D(n−1) 全部条件成立。
5. **D4 的「可交付」≠「foundry 能收」**：真 deck 对齐是 D5（外部）。
6. `G4` 的独立是**代码路径级**（版图几何独立测量 vs IR 声明），非物理方法级。

