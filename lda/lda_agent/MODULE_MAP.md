# LDA · `lda_agent` 模块地图（MODULE_MAP）

> 用途：模块 → 职责映射 + **闭环（loop）重复膨胀点**标注 + 关键跨模块契约。
> 本文件是 2026-09-14 `lda_agent` 复评（见 `LDA_lda_agent_code_review_2026-09-14.md`）
> 的 **P1(a) 缓解项**：09-11 评审建议建图未建，导致 loop 重复无法被一眼定位。
> 角色依据文件名 + 模块 docstring 推断，未逐文件通读；聚焦 loop 家族与契约两项高价值信息。
> 维护铁律：新增 `lda_agent` 模块须在此登记一行；删/重构模块须同步更新。

---

## 1. 编排与流程（Orchestration）

| 模块 | 职责 |
|---|---|
| `orchestrator.py` | 顶层调度：把用户意图拆分为 agent 任务图并驱动执行 |
| `agent_planner.py` | 规划 agent：把设计目标分解为子任务 / 锚分配 |
| `design_pipeline.py` | 设计流水线装配：串起 interpreter→designer→solver→verifier |
| `pipeline_realize.py` | 把设计结果落地为版图 / GDS / 可制造交付物 |
| `run_demo.py` | 演示入口（Scripted 可信候选离线跑，强隔离关闭） |

## 2. 核心 Agent（Core agents）

| 模块 | 职责 |
|---|---|
| `agents.py` | agent 基类 / 注册表（含 `SandboxExecutor` 委托，见 `sandbox.py`） |
| `agent_layout.py` | 版图 agent：布局生成 |
| `agent_synthesis.py` | 综合 agent：网表/拓扑综合 |
| `agent_verify.py` | **验证 agent：链路级物理定律锚（B19）+ 级联死标量锚**；消费 `lda_chain.link_harness.link_physics_harness` 返回 dict（见 §4 契约） |
| `l1_protocol.py` | L1 协议 agent：`InterpreterAgent` / `DesignerAgent` / `SolverAgent` |

## 3. 闭环家族（Design-loop family）⚠️ 重复膨胀点（P1）

所有「**propose → simulate/eval → verify → accept/reject**」模式的模块。
铁律共性：**LLM 不进判决路径；PASS 由死标量比对决定**。

### 3.1 已收敛（统一框架）
| 模块 | 角色 |
|---|---|
| `spectrum_loop.py` | **统一谱形逆设计框架** `SpectrumInverseDesignAgent`（engine/metric/oracle/target/bounds 五件插槽）。已收敛 D-03 布拉格镜、D-11 环形两套近重复闭环 |
| `ring_loop.py` | D-11 环形谱形逆设计 = `spectrum_loop` 的**薄包装**（engine=环形传递函数） |
| `multiband_loop.py` | D-03 多波长/宽带闭环 = `spectrum_loop` 的**薄包装**（engine=布拉格镜 TMM） |

### 3.2 仍独立实现（重复膨胀待收敛）⚠️
| 模块 | 闭环形态 | 与框架的差异 / 收敛建议 |
|---|---|---|
| `design_loop.py` | 1D 堆叠设计→TMM 仿真谱→物理锚验收 | 最老闭环；候选生成走 `llm_proposer` 钳制 + 纯网格降级。**建议抽 `LoopEngine` 共享 propose/eval/verify** |
| `coupler_loop.py` | D-01 多端口耦合器件验收（DC/YB，FDFD 超模 vs FDTD 投影） | 验收范式（oracle+candidate+tol 交叉对拍）与框架同构；**可实例化为 `spectrum_loop` 的耦合器件 engine** |
| `coupler_band_loop.py` | D-23 耦合器件**多波长**验收（D-01 扩展） | 多波长扫描必须固定网格 dl（实测踩坑已修）；与 `coupler_loop` 仅差单/多波长，**应合并为一个带 band 开关的耦合闭环** |
| `waveguide_loop.py` | 真 2D 波导横截面验收（FDTD neff vs FDFD ORACLE） | 与 `design_loop` 互补（2D 几何，TMM 不适用）；同 propose/eval/verify 骨架 |
| `drc_fix_loop.py` | D-18 DRC 回读整改闭环（死代码判定，LLM 不进路径） | 闭环形态（for it: drc→fix→break）与上面不同类，但仍是「迭代收敛」骨架，可共享 `IterateUntil(cond, step)` |

**重复根因**：`design_loop`/`coupler_loop`/`coupler_band_loop`/`waveguide_loop` 各自重写了
（a）候选生成、（b）确定性 eval、（c）物理定律 verdict、（d）accept/reject 四段，
而非共享一个 `LoopEngine`。`spectrum_loop` 已证明收敛可行（ring/multiband 薄包装）。
**下一步收敛优先级**：`coupler_loop` + `coupler_band_loop` 合并（单/多波长开关）→ 再抽 `LoopEngine` 供 `design_loop`/`waveguide_loop` 复用。

## 4. 独立器件求解 / 设计（Standalone solvers & designs）

光子侧：`adjoint_design.py` `adjoint3d_design.py` `inverse_design.py` `spectral_inverse_design.py`
`hybrid_design.py` `primitives_design.py` `gc_design.py` `directional_coupler.py`
`ring_adddrop.py` `splitter_readout.py` `tunable_wdm.py` `wdm_coupler.py` `wdm_splitter.py`
`wdm_system.py` `sparams_design.py` `sparams_3d_design.py` `port_acceptance.py`
`calibrate_kappa_grid.py` `large_scale_bench.py`

量子侧（QEDA）：`quantum_design.py` `qeda_topology.py` `qeda_depth_design.py`
`multiqubit_fidelity.py` `multiqubit_readout.py` `qubit_readout_chain.py`
`qubit_resonator_design.py` `readout_fidelity.py` `mixed_system.py`

多目标 / 系统：`multi_objective_design.py` `verify_voxel_pipeline.py` `verify_waveguide_2d.py`

## 5. 安全 / 红线（Safety & red lines）

| 模块 | 职责 |
|---|---|
| `sandbox.py` | **强隔离执行器**（unshare --net + setpriv nobody + rlimit）；在线 LLM 候选 Windows 硬拒、强推 Linux strong |
| `solver_writer.py` | 把候选落成求解器脚本，经 `SandboxExecutor` 隔离跑；`allow_weak_isolation=offline` 仅限可信 Scripted |
| `llm_proposer.py` | **红线**：仅钳制参数（finite + 四维边界），失败降级纯网格；无 `shell=True`/`eval`/`exec` |
| `redteam_proposer.py` | 红队：尝试越界提案以验证 proposer 钳制护栏 |

## 6. 跨模块契约（Cross-module contract）⚠️ P1(b) 已加守护

### 6.1 `agent_verify` ↔ `link_physics_harness` 字典契约
- 生产者：`lda_chain/link_harness.py::link_physics_harness(link, sim, blocked)`
  返回 dict（key 见 `link_harness.py:138-147`）：`status / b19 / energy_conservation /
  no_missing_models / routing_complete / missing_models / blocked_nets / anchor /
  empirical_anchor / honest_note`。
- 消费者：`agent_verify.py:96,105-108` 按 **dict key** 取
  `status` / `b19` / `energy_conservation` / `no_missing_models` / `routing_complete`。
- **风险**：任一侧改名/删 key → 运行时 `KeyError`（仅端到端跑才暴露）。
- **守护**：`lda/run_agent_verify_link_contract_smoke.py` 结构断言——生产者返回 dict
  **必须 ⊇ 消费者消费的 key 集**，否则 FAIL。改名即两道 smoke 同时报警。

### 6.2 计数护栏契约（见 ② 入档）
- 三分类计数（strict_independent / degraded_ordinal / self_certified）在全仓守卫中
  **动态推导**（`BENCHMARK_DEFS × BENCHMARK_CANDIDATES`），无写死三元组。
- `run_three_class_consistency_smoke.py` 守护 README≡harness≡端点三面一致。
