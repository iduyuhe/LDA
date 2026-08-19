# LDA · L0 开放中间表示（IR/DSL）草案 · 光子子集

> 文档编号：LDA-L0-001
> 版本：v0.1（光子子集首稿，待评审）
> 编制：AI（按杜先生授权代行技术决策）
> 密级：内部 · 暂不对外
> 关联：阶段1 关键任务 1.1；配套《LDA 阶段性总结与剩余工作》§5.1.1

---

## 0. 为什么先写 L0 IR（且先做光子子集）

战略纪要已定：L0（开放 IR/DSL）是护城河起点——**标准 + 生态 + 带可信基准套件的开放内核**，而 PhIDO 只有薄私有 YAML 且光子-only。我们要的 L0 必须：

1. **机器优先（machine-first）**：agent 间 / agent 与内核间的机器语言，不是人看的 GUI。凡"给人操作方便"的壳一律剥离。
2. **光子+量子统一命名空间**：本次先做**光子子集**，但字段与命名空间必须为后续量子子集预留（不推翻重来）。
3. **可被已验证求解核直接消费**：本草案字段直接从已自举落地的 FDTD 核（1D/2D/3D selfcheck 5/5）反推，保证"设计即能跑"，而非空中楼阁。

---

## 1. 设计原则

- **P1 单一真相源**：一份 L0 文档 = 一次完整仿真/设计任务的确定性描述；不依赖 GUI 状态、不依赖交互式逐步调参。
- **P2 内核无关（backend-agnostic）**：L0 描述"物理意图"，不描述"怎么算"。后端（numpy / numba-cpu / torch-cpu / torch-cuda）由 `solver` 字段选择，算法由内核决定。
- **P3 可验证内嵌**：L0 文档本身携带 `verification` 段——指定 ORACLE（物理定律/大数据）、公差、验收判据。裁判不读 L0 之外的"默契"。
- **P4 版本化命名空间**：`lda.ir.photon.v0` 命名空间；向后兼容由 schema version 控制，破坏性变更升主版本。
- **P5 最小完备**：光子子集先覆盖"已证明可解"的题类（层状堆叠透射谱、均匀介质点源格林函数、规则几何器件），不贪全。

---

## 2. 文档拓扑（顶层对象）

```yaml
lda.ir.photon.v0:
  meta:        # 文档元数据
  domain:      # 仿真域（维度、网格、边界）
  materials:   # 材料库（按 ref 引用）
  geometry:    # 几何布局（引用 materials，体素/参数化）
  sources:     # 激励源（类型、位置、频谱、上升）
  monitors:    # 探针/监视器（场采样点、透反监视器）
  solver:      # 求解后端选择与数值参数
  verification:# ORACLE + 公差 + 验收判据
```

---

## 3. 字段规范（光子子集 · 类型伪代码）

### 3.1 `meta`
```
meta:
  schema: "lda.ir.photon.v0"
  doc_id: str            # 唯一文档标识（UUID/语义URI）
  author: agent|human   # 产出者（agent 操作执行，人决策）
  created: ISO8601
  units: { length: "um", time: "s", freq: "Hz" }   # 默认 um；频率可经 wavelength_um 表达
```

### 3.2 `domain`
```
domain:
  dimensionality: 1|2|3
  grid:
    method: "uniform"            # v0 仅支持均匀正交网格
    dl: float                    # 单元尺寸 um（或 dx/dy/dz 分别指定）
    size: [Nx, Ny, Nz]           # 网格数（或 physical_size: [Lx,Ly,Lz] 推导）
  cfl:
    courant: 0.95                # < 1/sqrt(dimensionality)；3D 默认 0.95/√3≈0.548 由内核强制
  boundaries:
    # 每个轴：pbc（周期）| pml（吸收，需 sponge 厚度）| pec|pmc
    x: "pml"
    y: "pbc"                     # 当前内核：横向轴默认 PBC
    z: "pbc"
    sponge:                      # 仅 pml 轴需要
      thickness_cells: int       # 吸收层厚度（单元数），整层整数
      sigma_max: float           # 最大电导率（梯度/插值海绵）
```

### 3.3 `materials`
```
materials:
  - ref: "sio2"
    model: "dielectric"
    n: 1.44                      # 折射率（实部）；或 eps、或 eps+sigma（有耗）
  - ref: "si"
    model: "dielectric"
    n: 3.48
  - ref: "air"
    model: "vacuum"
    n: 1.0
```

### 3.4 `geometry`
光子子集 v0 支持两种布局原语（覆盖已验证题类）：

```
geometry:
  # 原语 A：层状堆叠（沿某轴的一维折射率分布，横向 PBC）
  stack:
    axis: "z"
    layers:                     # 自上而下（或从入射面起）
      - { material: "air", thickness_um: inf }   # inf = 半空间（自由空间边界）
      - { material: "si",  thickness_um: 0.25 }
      - { material: "sio2",thickness_um: 0.25 }
      - ... (重复单元) ...
      - { material: "air", thickness_um: inf }
  # 原语 B：体素场（任意 2D/3D 折射率图，未来器件布局用）
  voxel_field:                  # 与 stack 二选一；v0 内核暂仅完全支持 stack
    source: "gdsii"|"numpy_array"|"parametric"
    ref: "<指向 L2 PDK 或布局 agent 产出>"
```

### 3.5 `sources`
```
sources:
  - id: "src0"
    type: "plane_wave" | "point" | "mode"   # v0 内核支持 plane_wave（stack 透射）/ point（greens）
    location: [ix, iy, iz]                  # 单元索引或物理坐标
    spectrum:
      kind: "wavelengths_um"
      values: [1.3, 1.4, 1.5, 1.6]          # 扫频点（透射谱）
      # 或 kind: "omega_range" + ramp
    ramp_steps: 400                         # 软源上升步数（三铁律①：软源全程开）
```

### 3.6 `monitors`
```
monitors:
  - id: "T"
    type: "transmission"        # 透射监视器（stack 题）
    axis: "z"
    position: "after_last_layer"
  - id: "probe_r"
    type: "field_sample"        # 场采样（greens 题）：在给定半径取 |Ez|
    field: "Ez"
    radii: [10, 20, 40, 80]     # 距点源单元数
    norm: "spherical"           # |Ez|*r 应常数（球面波判据）
```

### 3.7 `solver`
```
solver:
  backend: "numpy"|"numba_cpu"|"torch_cpu"|"torch_cuda"   # device 一行切换
  dtype: "float64"               # 主权核默认 float64（物理定律锚要求逐位精度）
  reference_run:                 # 三铁律③：参考跑归一化
    enabled: true
    T_norm: "|(E_real/E_ref)|^2 * (nL/n0)"
```

### 3.8 `verification`（裁判段，不可移除）
```
verification:
  oracle:
    type: "tmm_analytic"        # 物理定律锚：传输矩阵解析解
    # 或 "measured_dataset"(实证大数据锚) / "meep_numeric"(降级实现)
  tolerance:
    max_rel_T: 0.12             # 按题类分级（匹配介质 0.02 / FP 0.08 / 布拉格 0.12）
  acceptance:
    rule: "pass = all(metric < tolerance)"   # 死代码判，LLM 不进判决路径
```

---

## 4. 示例：把已验证的 3D 布拉格光栅考题写成 L0 IR

（对应 `fdtd3d.py` selfcheck 用例 D，已 selfcheck 5/5 PASS，maxΔ=0.0090）

```yaml
lda.ir.photon.v0:
  meta:
    schema: "lda.ir.photon.v0"
    doc_id: "bragg-24cell-2026"
    author: agent
    units: { length: "um" }
  domain:
    dimensionality: 3
    grid: { method: "uniform", dl: 0.05, size: [320, 320, 320] }
    cfl: { courant: 0.548 }
    boundaries: { x: "pml", y: "pbc", z: "pbc", sponge: { thickness_cells: 28, sigma_max: 0.8 } }
  materials:
    - { ref: "air",  model: "vacuum", n: 1.0 }
    - { ref: "sih",  model: "dielectric", n: 3.48 }
    - { ref: "silo", model: "dielectric", n: 1.44 }
  geometry:
    stack:
      axis: "z"
      layers:
        - { material: "air", thickness_um: inf }
        - { material: "sih",  thickness_um: 0.25 }
        - { material: "silo", thickness_um: 0.25 }   # ×24 单元
        - ... (重复 24 次) ...
        - { material: "air", thickness_um: inf }
  sources:
    - { id: "src0", type: "plane_wave", location: [160,160,20],
        spectrum: { kind: "wavelengths_um", values: [1.9,2.2,2.46,2.7,3.0] }, ramp_steps: 400 }
  monitors:
    - { id: "T", type: "transmission", axis: "z", position: "after_last_layer" }
  solver:
    backend: "torch_cuda"        # 或 numba_cpu / torch_cpu
    dtype: "float64"
    reference_run: { enabled: true }
  verification:
    oracle: { type: "tmm_analytic" }
    tolerance: { max_rel_T: 0.12 }
    acceptance: { rule: "pass = all(metric < tolerance)" }
```

> 该文档可被 `solve_spectrum_torch(spec, device=...)` 直接消费（内核已实现 `layers` + `wavelengths_um` 子集）；`backend: torch_cuda` 即触发今日已激活的 GPU 路径。

---

## 5. 与 L1 agent 的接口映射

L0 是 agent 间机器语言，各 L1 agent 的读写边界：

| L1 agent | 读 L0 段 | 写 L0 段 |
|---|---|---|
| Interpreter | 自然语言意图 | `meta` / 顶层 schema 骨架 |
| Designer | `materials` / `domain` | `geometry` / `sources` |
| Layout | `geometry.voxel_field` | GDSII / 参数化布局（未来） |
| Verifier | 全文 | `verification` 结果 JSON（标量指标，**不碰场矩阵**） |
| Solver-agent（AI-dev 自举） | `geometry` / `sources` / `solver` | 候选求解核（进开放内核） |

**铁律**：L1 只消费/产出 L0 结构化字段；任何"给人操作方便"的 GUI 壳不在 L0/L1 范畴。

---

## 6. 与验证锚（ORACLE）的绑定

- `verification.oracle.type` 直接决定裁判 ground：
  - `tmm_analytic` → 物理定律锚（已验证，主权可信）。
  - `measured_dataset` → 实证大数据锚（雷③ 缓解工程，待建开放题库 + 众包语料）。
  - `meep_numeric` → 降级实现（断供不影响主流程，仅降真 3D 精度）。
- 判据 `acceptance.rule` 由死代码执行，`max_rel_T` 标量比对；LLM 仅读 JSON 摘要，不进判决路径（排雷①② 已排空）。

---

## 7. 当前求解器覆盖度（诚实标注）

| L0 段 | 内核已实现 | 状态 |
|---|---|---|
| `geometry.stack` + `sources.plane_wave` + `monitors.transmission` | ✅ 完整 | 1D/2D/3D selfcheck 5/5 |
| `sources.point` + `monitors.field_sample`（greens） | ✅ 完整 | 球面波 \|Ez\|·r 常数 5/5 |
| `solver.backend` 四选一 | ✅ 完整 | numpy/numba/torch-cpu/torch-cuda |
| `geometry.voxel_field`（器件级版图→体素） | 🟢 已验证（退化等价） | stack 退化经 `voxelize_stack` 与原 `solve_spectrum` 逐位一致（max rel diff=0.0）；真 2D 矩形掩模 `voxelize_rectangular` 已实现（器件雏形），待接真 2D ORACLE（下一步）；GDSII 为可选序列化适配器（gdsfactory 缺失时友好降级） |
| `sources.mode`（波导模式源） | ⚪ 规划 | 垂直场景（波导分束器）需要 |
| `verification.oracle.measured_dataset` | ⚪ 待建 | 实证大数据锚工程 |

> 即：L0 的"已证明可解"子集已与内核对齐；"器件级/模式源/实测锚"是下一迭代。

---

## 8. 量子子集预留（不推翻重来）

命名空间已留 `lda.ir.quantum.v0`（未来）。光子子集的 `materials.model`、`sources.type`、`monitors.type` 设计为**可扩展枚举**——量子侧新增 `model: "superconducting_transmon"`、`type: "hamiltonian_drive"`、`monitor: "energy_spectrum"` 即可挂入同一 L0 框架，共享 `domain`/`solver`/`verification` 机制。

---

## 9. 下一步迭代（待评审）

1. **评审本草案**：杜先生/退休专家对字段粒度、命名空间、枚举项拍板。
2. **对齐 L1**：把 §5 的 agent 读写边界落成 L1 协议草稿。
3. **内核回填**：将 stack/plane_wave 的"隐式 spec"显式升级为完整 L0 解析器（当前 `solve_spectrum` 接收的是 L0 子集的窄接口，需泛化）。
4. **器件级几何（首稿已交付 ✅）**：`geometry.voxel_field` 原语 + `voxelize_stack`（stack 退化，与 `solve_spectrum` 逐位一致）+ `voxelize_rectangular`（真 2D 矩形掩模，器件雏形）+ GDSII 可选序列化适配器（gdsfactory 缺失时友好降级）。闭环已支持 `geo_kind=voxel_field`：Designer→Layout(体素化)→Solver(`solve_spectrum_field_stack`)→Verifier(TMM) 全程 agent 驱动。**下一步**：真 2D 器件（波导/分束器横截面）需建真 2D ORACLE（本征模/解析近似），方可接验收闭环。

---

*本草案是阶段1 任务 1.1 的首稿，从已验证 FDTD 核反推，保证"设计即能跑"。后续与 L1 协议、端到端闭环联动推进。*
