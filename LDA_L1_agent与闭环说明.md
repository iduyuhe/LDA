# LDA · L1 agent 协议层 + 端到端设计闭环（说明）

> 文档编号：LDA-L1-001
> 版本：v0.1（阶段1 任务 1.2 首稿，待评审）
> 编制：AI（按杜先生授权代行技术决策）
> 关联：L0 IR 草案（LDA-L0-001）§5；《LDA 阶段性总结与剩余工作》§5.1

---

## 0. 为什么现在做 L1 + 闭环（且做最小可运行首稿）

战略纪要定了人机协作哲学：**agent 负责操作执行，人负责决策（结果责任人）**。
L0 IR 草案已从已验证 FDTD 核反推出机器优先字段；但 L0 只是"描述语言"，
要证明"agent 出设计结果、非辅助软件"，必须把 agent 角色 + 内核驱动 + 验证
焊成一条**可运行的端到端链路**。本首稿即为此：打通"设计目标 → 迭代 → 验证 → 出结果"。

---

## 1. L1 角色边界（确定性函数，非自由 LLM —— 排雷①② 已排空 AI 进判决路径）

见 `lda/lda_agent/l1_protocol.py`：

| L1 agent | 输入 | 输出 | 对应 L0 段 |
|---|---|---|---|
| Interpreter | 半结构化意图 dict | `DesignTarget` | meta / 顶层骨架 |
| Designer | `DesignTarget` + 迭代状态 | `L0IR`（geometry / sources） | materials / domain / geometry |
| SolverAgent | `L0IR` | `SolveResult`（透射谱） | geometry / sources / solver |
| Verifier | `L0IR` + `SolveResult` | `VerifyResult`（对 TMM 比对） | verification（只读，产出标量） |

**铁律（沿用 L0 IR §5）**：L1 只消费/产出 L0 结构化字段；判据由死代码执行
（标量比对），LLM 不进判决路径。任何"给人操作方便"的 GUI 壳不在 L0/L1 范畴。

---

## 2. 机器优先接口（无 GUI 翻译损耗）

- **L0 IR → 求解器 spec 适配器**：`L0IR.to_solver_spec()` 把 `geometry.stack`
  + `sources.spectrum` 编译成已验证内核直接消费的 `spec`
  （`{"layers":[(th,n)...], "wavelengths_um":[...]}`）。
- **后端一行切换**：`load_solver(backend)` 分发 `numpy` / `numba_cpu` /
  `torch_cpu` / `torch_cuda`，三者 `solve_spectrum(spec, ...)` 同签名、同返回
  （`{wavelengths_um, transmission, source, note}`），算法由内核决定，L1 只转发。
- **物理定律锚 ORACLE**：`load_oracle()` 返回 `tmm.solve_spectrum`（解析解，非 AI 判决）。

---

## 3. 端到端闭环（design_loop.py · DesignAgent）

```
Interpreter → DesignTarget
loop (有界 max_iterations):
    Designer    → L0IR（布拉格四分之一波堆，当前 periods 数）
    SolverAgent → 跑已验证 FDTD 核（默认 numba-cpu，43× 加速）
    Verifier    → 对 TMM 比对：R = 1 - T（无损）；判 R≥阈值 且 |ΔR|≤公差
    if 达标 → break（设计结果已出）
    else   → periods += 1（布拉格 R 随周期数单调升，必然收敛）
→ DesignOutcomeReport（给「人」的决策摘要，非操作手册）
```

**验收判据的重要修正（诚实工程）**：首版用 `max_rel_T`（透射相对误差）作验收，
发现高反射镜 T→0 时该量失真（爆炸），而设计真正关心的是反射率 R。已改为以
**设计度量 R 的绝对误差 |ΔR|** 为验收判据，`max_rel_T` 降为诊断量。

---

## 4. 实证（run_demo.py 实跑结果）

目标：λ0=1.55µm、Si/SiO2 布拉格镜，R ≥ 0.99；后端 numba-cpu；dl_factor=60、sponge=60。

| 迭代 | 周期 N | R(FDTD) | R(TMM) | |ΔR| | 达标 |
|---|---|---|---|---|---|
| 1 | 1 | 0.5109 | 0.5007 | 2.47e-2 | 否 |
| 2 | 2 | 0.8933 | 0.8893 | 1.82e-2 | 否 |
| 3 | 3 | 0.9808 | 0.9801 | 1.02e-2 | 否 |
| 4 | 4 | 0.9967 | 0.9966 | 4.81e-3 | **是 ✅** |

- 闭环墙钟 **8.8s**（含 numba JIT 预热；稳态单步更快）。
- 结论：设计达标，结果已可由「人」验收。落盘 `design_outcome_report.json`。

**这证明了什么**：agent 不是"帮人调参的辅助软件"——它接收设计目标，自主迭代
几何、驱动主权求解核、对照物理定律锚验收，最终产出可验收的**设计结果**。这正是
LDA 与 Synopsys/Cadence/gdsfactory 的根本区别（那些为"人操作"设计）。

---

## 5. 当前边界（诚实标注，下迭代）

- 几何原语仅 `stack`（层状堆叠）；器件级 `voxel_field` + GDSII→体素管线未接（任务 1.3）。
- 仅布拉格镜一类 Designer 策略；AR 镀膜 / FP 标准具等策略待扩（同框架）。
- 单 agent 串行编排；多 agent 并发 / MCP-A2A 风格消息总线为后续（L1 扩展）。
- 验证锚仅 `tmm_analytic`；`measured_dataset`（实证大数据锚）待建（雷③ 缓解工程）。

---

## 6. 文件清单

| 文件 | 作用 |
|---|---|
| `lda/lda_agent/l1_protocol.py` | L1 角色 + L0→solver 适配器 + 后端分发 |
| `lda/lda_agent/design_loop.py` | DesignAgent 端到端闭环编排器 |
| `lda/lda_agent/run_demo.py` | 演示运行器（确定性、批处理、无交互） |
| `lda/lda_agent/design_outcome_report.json` | 实跑报告落盘 |

*本说明是阶段1 任务 1.2 首稿，与 L0 IR 草案、验证 harness 联动；下迭代接器件级几何与多 agent 编排。*
