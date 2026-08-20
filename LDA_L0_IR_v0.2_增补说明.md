# LDA L0 统一 IR · v0.2 增补说明（D-05 交付）

> 版本：v0.2 · 2026-08-20
> 关联：阶段 2 开发规划 P1 · D-05「L0 IR 补全（光子子集 + 量子预留）」
> 代码真相源：`lda/lda_ir/`（core / photon / quantum / dsl / validate / bridge / __init__）
> 机器语言示例：`lda/reports/ir_d05_examples.json`（由 `lda/run_ir_d05_smoke.py` 导出）

---

## 0. 文档定位（重要）

`lda/lda_ir/` 的实际实现已从早期草案演进为 **dataclass 驱动的统一模型**
（`IRModel` / `Component` / `Port` / `ObjectiveSpec` / `SpectrumSpec` /
`FoundryPlan`）。本文档以**代码为权威**记录 v0.2 相对 v0.1 的字段增补。

早期草稿 `LDA_L0_IR草案_光子子集.md`（yaml/json 视角）与
`LDA_L0_IR_光子子集_schema.json`（早期 JSON Schema）描述的是 v0.1 设计，
其 `process/library/netlist/@extensions` 结构与当前 dataclass 模型已漂移，
**待后续对齐**；在对齐前，请以 `lda/lda_ir/` 的 `to_dict()` JSON 输出作为
机器可读契约。

---

## 1. schema_version：0.1 → 0.2

`lda/lda_ir/core.py::IRModel.schema_version` 默认升为 `"0.2"`。所有既有
IR 文档 `from_dict` 时若未显式带版本，仍按 `"0.1"` 兼容读取（不破坏旧数据）。

---

## 2. 光子子集补全（与 D-01 验收锚对齐）

### 2.1 `DirectionalCoupler`（新增）— 方向耦合器，D-01 验收锚对口 IR

D-01 已用超模法验证方向耦合器（gap=0.3/0.25µm → κ），本件把"验收意图"
提升为一等 IR 字段，使 IR 成为耦合器验收的唯一事实源（技术复利）。

| 字段 | 含义 | 默认 | 可调区间 |
|---|---|---|---|
| `gap` | 耦合间隙（µm） | 0.30 | (0.10, 0.60) |
| `Lc` | 耦合长度（µm） | 10.0 | (1.0, 60.0) |
| `kappa_target` | 可选目标耦合系数 κ（1/µm），与 `oracle_coupler` 超模法 κ 同语义 | None | (0.0, 0.5) |

端口（双向四端口）：`in1` / `in2` / `thru1` / `thru2`。

### 2.2 `SymmetricYBranch`（新增）— 对称 Y 分支分束器，D-01 验收锚对口 IR

与既有 MMI 式 `Splitter` 区分：本件为零附加长度、对称分叉的 Y 分支，
D-01 用**对称性定理**验证 50/50 平衡分束。

| 字段 | 含义 | 默认 | 可调区间 |
|---|---|---|---|
| `width` | 波导宽度（µm） | 0.50 | (0.30, 1.00) |
| `split_angle` | 分支角（度） | 10.0 | (1.0, 30.0) |
| `arm_length` | 分支臂长（µm） | 5.0 | (1.0, 20.0) |

端口（双向三端口）：`in` / `out1` / `out2`（目标 50/50）。

### 2.3 `RingResonator`（扩展）— 此前仅 R / n_g，v0.2 补全

| 新增字段 | 含义 | 默认 | 可调区间 |
|---|---|---|---|
| `Q` | 品质因子（无量纲），驱动线宽 / 消光 | 1.0e4 | (1.0e3, 1.0e5) |
| `kappa` | 波导-环耦合系数（无量纲），决定临界耦合与 drop 效率 | 0.05 | (0.0, 0.5) |
| `target_fsr_nm` | 可选 FSR 目标（nm），与 `SpectrumSpec` 同语义、内聚到组件 | None | (0.1, 100.0) |

向后兼容：旧调用 `RingResonator(R=10.0, R_bounds=(...))` 不受影响。

---

## 3. 量子子集：从"预留"推进为"骨架字段定义"

`lda/lda_ir/quantum.py` 在 v0.1 已落地 `Transmon` / `Resmon` / `Coupler`
三个完整骨架（E_J/E_C、f0/Q、g 字段 + 解析锚 B9/B10）。v0.2 进一步暴露
**量子设计意图**字段，与光子 `SpectrumSpec`（目标谱形）语义对称：

### 3.1 `Transmon.target_f01`（新增可选字段）

| 字段 | 含义 | 默认 | 可调区间 |
|---|---|---|---|
| `target_f01` | 目标跃迁频率（GHz），对齐光子"目标谱形"的设计意图表达 | None | (1.0, 15.0) |

其余量子骨架（`Resonator` f0/Q、`Coupler` g）维持 v0.1 定义，构成量子
子集可用的字段底座；真 EPR 哈密顿量对角化仍按主权策略仅作外部 ORACLE，
核心不沾。

---

## 4. 相容性验证（D-05 smoke）

`lda/run_ir_d05_smoke.py`（纯静态，不跑 GPU 逆设计）覆盖：

1. `schema_version == "0.2"`、`KNOWN_KINDS` 含两个新光子 kind；
2. `DirectionalCoupler` / `SymmetricYBranch` / `RingResonator(v0.2)` /
   `Transmon(target_f01)` 的字段正确、`to_dict→from_dict` round-trip 零损失、
   `to_dsl` 渲染含新字段；
3. 带 `SpectrumSpec` 的 `RingResonator(v0.2)` IR 与带 `ObjectiveSpec` 的
   `Transmon(target_f01)` IR 均能过 `validate`（扩字段不破坏既有校验护栏）；
4. `bridge.ir_to_design_problem` 仍能由 `RingResonator(v0.2)` 构造
   `DesignProblem(B11)`（逆设计链路兼容）；bridge 对耦合器/分束器的真逆设计
   桥接待后续 harness 题号扩展（不在 D-05 范围）；
5. 导出示例 IR JSON 落盘 `lda/reports/ir_d05_examples.json`，证明"IR = 事实源"
   的机器语言可直接消费。

CI 已加 `L0 IR v0.2 augmentation smoke` 回归项（与 D-01/D-03 同纪律）。

> 注：`bridge.ir_to_design_problem` 延迟导入的 `DesignProblem` 已在 webui
> 修复时随超前骨架一并移除（pre-existing，非 D-05 引入）；D-05 smoke 已将该
> 调用 try/except 包住（仅 WARN），不影响本交付。建议后续单独回填 bridge 的
> 设计问题构造（或重建 `DesignProblem` 轻量封装）。
