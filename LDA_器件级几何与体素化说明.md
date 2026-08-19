# LDA · 器件级几何与体素化（voxel_field）说明

> 文档编号：LDA-VX-001
> 版本：v0.1（首稿，已实跑验证）
> 编制：AI（按杜先生授权代行技术决策）
> 密级：内部 · 暂不对外
> 关联：阶段1 任务 1.3 端到端闭环；配套《LDA_L0_IR_光子子集草案》§7/§9

---

## 0. 本文用途

把"agent 出设计结果"从**参数化层 stack**推进到**真实版图驱动仿真**：Designer 产出器件版图（机器优先掩模）→ Layout 把它体素化为 3D 折射率场 → Solver 跑已验证 FDTD 核 → Verifier 对物理定律锚验收。这是阶段1 咽喉任务 1.3「端到端打通」的关键拼图，也是 L0 IR `geometry.voxel_field` 原语从"规划"落地为"已验证"的实证。

一句话结论：**「版图→体素→FDTD→ORACLE 验收」链路已打通并验证——stack 退化与原 stack 入口逐位一致（max rel diff = 0.0），真 2D 矩形掩模体素化已实现（器件雏形）。当前唯一诚实边界：真 2D 器件需另建真 2D ORACLE 方可接验收闭环。**

---

## 1. 机器优先版图表示

`lda/lda_solver/voxel_field.py` 定义 `LayoutLayer`（机器优先、非 GUI）：

```
LayoutLayer:
  material_ref: str          # 引用 materials 库的折射率 n
  x0, x1: float (um)         # 沿 x 的起止（器件纵向，正入射传播方向）
  y0, y1: Optional[float]    # 横向掩模；None = 该轴全宽（stack 退化用）
  z0, z1: Optional[float]    # 竖向掩模；None = 全宽
  comment: str
```

设计哲学（见 L0 IR §5 / 协作哲学）：版图层是 **agent 间机器语言**，不是给人看的 GUI；凡"给人操作方便"的壳一律不在此层。GDSII 仅为该表示的**可选序列化通道**（gdsfactory，B 级 fork 副本），缺失时体素化与 FDTD 完全不受影响。

---

## 2. 体素化引擎（两个入口）

| 函数 | 用途 | 状态 |
|---|---|---|
| `voxelize_stack(layers, dl, buf, sponge)` | stack 退化：复用已验证 `_build_interior` 把 1D 层状 prof 复制到 y/z 维 → 3D 折射率体素场（含 n²） | ✅ 与 `solve_spectrum` 逐位一致 |
| `voxelize_rectangular(layers, materials, grid)` | 真 2D 矩形掩模 → 3D 体素场（先填背景再覆盖，后者覆盖前者） | ✅ 已实现（器件雏形），待接真 2D ORACLE |
| `to_gdsii` / `from_gdsii` | GDSII 序列化适配器 | 🟡 gdsfactory 缺失时友好降级报错 + 预留接口 |

**关键工程决策（诚实）**：stack 退化体素场**不重新实现**几何吸附逻辑，而是直接复用 `fdtd3d._build_interior`（已验证、selfcheck 5/5），仅把得到的 1D prof 复制到 y/z 维。这样构造出的 `eps` 与 `solve_spectrum` 入口（`_run_planewave`）**逐位相同**——voxel 管线零引入几何误差。

---

## 3. 与求解器 / 闭环的接口

`lda/lda_solver/fdtd3d.py` 新增两个公共入口，均复用已验证的 `_run_field_core`（3D 全 Yee propagator，三铁律 + 梯度海绵 + 参考跑归一化）：

- `solve_spectrum_field(spec)`：消费**任意** 2D/3D 体素场（固定 `dl`，适合真 2D 器件几何不随 λ 变）。
- `solve_spectrum_field_stack(layers, ...)`：stack 退化专用，每波长经 `voxelize_stack` 体素化后调核心，**与 `solve_spectrum` 平行 → 逐位等价**（验证入口）。

L1 协议层（`lda/lda_agent/l1_protocol.py`）扩展：

- `L0IR.geo_kind`：`"stack"` | `"voxel_field"`（机器优先几何原语选择）。
- `LayoutAgent`：把 L0IR 几何意图转成体素场（预览/调试用单波长体素化）。
- `SolverAgent.solve`：若 `geo_kind=="voxel_field"`，走 `solve_spectrum_field_stack`（当前仅 numpy 内核）；否则原 `solve_spectrum`。
- 后端回退：当前沙箱仅装 numpy，`load_solver` 在 numba/torch 不可用时自动回退 numpy 并打印——保证闭环在任意环境可复现，不在判决路径引入不确定性。

闭环调用链（`design_loop.py`）：
```
Interpreter → DesignTarget
loop (有界):
  Designer → L0IR(geo_kind)
  if voxel_field: LayoutAgent(体素化预览) → SolverAgent → solve_spectrum_field_stack
  else:          SolverAgent → solve_spectrum
  Verifier → 对 TMM 物理定律锚比对（死代码判，LLM 不进判决路径）
  if 达标 → break
→ DesignOutcomeReport
```
运行器 `run_demo.py` 新增 `--geo {stack,voxel_field}`；默认 `backend=numpy`（当前环境唯一可用）。

---

## 4. 实跑实证（2026-08-16 · numpy 后端，当前沙箱可复现）

验证脚本 `lda/lda_agent/verify_voxel_pipeline.py`，布拉格镜 λ0=1.55µm、Si/SiO2：

| 几何原语 | threshold | accepted | R(FDTD) | |ΔR| (对 TMM) | 墙钟 |
|---|---|---|---|---|---|
| stack | 0.95 | ✅ | 0.98448 | 2.32e-02 | 12.9s |
| voxel_field | 0.95 | ✅ | 0.98448 | 2.32e-02 | 12.8s |
| stack | 0.99 | ✅ | 0.99754 | 1.04e-02 | 17.1s |
| voxel_field | 0.99 | ✅ | 0.99754 | 1.04e-02 | 17.2s |

- **双 PASS**：两种几何原语均对 TMM 物理定律锚 PASS（R≥threshold 且 |ΔR|≤公差）。
- **逐位一致**：stack 与 voxel_field 最终 R 之差 = `0.00e+00`（BIT-EQUIV）。
- **直接谱比对**：布拉格 D 题 `solve_spectrum` vs `solve_spectrum_field_stack` 的 T 谱 max rel diff = `0.00e+00`（BIT-EQUIV）。
- 结论：voxel 管线**零引入误差**，"版图→体素→FDTD→验收"链路成立。

> 诚实说明：当前沙箱仅 numpy 后端（numba/gdsfactory 未装），故墙钟为 numpy 参考值；生产默认仍 numba-cpu（据前期实测 ≈43× 快于纯 numpy）。验证结论（逐位一致、双 PASS）与后端无关。

---

## 5. 边界与诚实标注

| 项 | 状态 | 说明 |
|---|---|---|
| stack 退化 voxel 场 | 🟢 已验证 | 与 `solve_spectrum` 逐位一致 |
| 真 2D 矩形掩模体素化 | 🟢 已实现 | `voxelize_rectangular` 可产出器件横截面体素场，但**暂未接验收**（无真 2D ORACLE） |
| 真 2D 器件验收闭环 | ⚪ 待建 | 需建真 2D ORACLE（本征模求解 / 解析近似，如条形波导 neff、分束器 S 参数） |
| GDSII 序列化 | 🟡 可选 | gdsfactory 缺失时友好降级；不阻塞体素化与 FDTD |
| voxel 模式求解后端 | 🟡 仅 numpy | `solve_spectrum_field(_stack)` 当前 numpy 内核；numba/torch 变体为后续（需移植核心到 JIT/torch，复用 `_run_field_core` 同算法） |
| 验收判据 | 🟢 不变 | 高反射镜用设计度量 R 的**绝对误差** |ΔR|（高 R 时 T→0，rel_T 失真不可用） |

---

## 6. 文件清单

| 文件 | 角色 |
|---|---|
| `lda/lda_solver/voxel_field.py` | 机器优先版图表示 + 体素化引擎 + GDSII 适配器预留 |
| `lda/lda_solver/fdtd3d.py` | 新增 `_run_field_core`（通用核心）/ `solve_spectrum_field` / `solve_spectrum_field_stack` |
| `lda/lda_agent/l1_protocol.py` | `L0IR.geo_kind` / `LayoutAgent` / `SolverAgent` voxel 分支 / 后端回退 |
| `lda/lda_agent/design_loop.py` | `DesignAgent` 支持 `geo_kind` |
| `lda/lda_agent/run_demo.py` | 新增 `--geo` 参数、默认 numpy 后端 |
| `lda/lda_agent/verify_voxel_pipeline.py` | 双 PASS + 逐位一致验证脚本 |
| `LDA_L0_IR_光子子集草案.md` | §7 覆盖度 / §9 更新 |

---

## 7. 下一步（待确认顺序）

1. **真 2D ORACLE**：建本征模/解析近似 ORACLE（波导 neff、分束器 S 参数），接 `voxelize_rectangular` 器件横截面的验收闭环 —— 这是垂直场景（波导分束器）端到端的关键。
2. **voxel 模式 numba/torch 后端**：把 `_run_field_core` 移植到 JIT/torch（同算法、逐位等价），恢复生产级速度。
3. **GDSII 真链路**：在已装 gdsfactory 主权副本的环境，启用 `to_gdsii/from_gdsii`，形成"L0 IR → GDSII → 体素 → FDTD"完整版图闭环。
4. **端到端自然语言入口**：Interpreter 从自然语言意图 → DesignTarget（当前为结构化 dict 输入，接口已留扩展点）。

---

*本文与《LDA_L0_IR_光子子集草案》《LDA_L1_agent与闭环说明》配套。阶段1 任务 1.1（L0 IR）/ 1.2（L1 agent+闭环）/ 1.3（器件级几何 voxel_field）首稿均已交付并实跑验证。*
