# LDA L0 · 统一中间表示（IR）开放标准规范

> 文档编号：LDA-STD-001
> 版本：v0.3（2026-08-23 定稿 · D-76 标准化发布）
> 状态：**开放标准（open spec）**——社区共建起点，任何 agent / 工具 / PDK 均可按此规范接入
> 配套：`docs/ir_schema.json`（JSON Schema draft-07 机器可读，与本规范零漂移）
> 编制：AI（LDA 工程团队，按杜先生授权代行技术/工程决策）
> 红线：LLM 不进判决路径——IR 只描述"要造什么、约束是什么、目标谱长什么样、想落在哪个 foundry"，物理判定由物理定律锚（PhysicsAnchor）确定性完成

---

## 1. 定位与设计原则

LDA L0 是架构分层最底层的地基（主权策略 C 级：第一天自主），是**设计意图的统一机器语言**（machine-first DSL）：

- **机器优先**：一切结构可序列化为纯 dict / JSON，便于 agent 间传递、经 L1 传输、落库 diff；不绑定任何商业 EDA 格式（GDSII/OASIS 属 A 级，永不借）。
- **双域统一**：同一套数据模型表达**光子**（靠折射率/几何）与**量子**（靠约瑟夫森/充电能）器件——"设计意图→IR→桥接→设计闭环→物理定律锚验证"链路完全一致。
- **零外部依赖**：仅标准库，离线可跑、主权可控。
- **意图显式**：目标谱形（SpectrumSpec）、多 foundry 落点（FoundryPlan）、物理定律锚（PhysicsAnchor）都是 IR 一等字段。

## 2. 顶层模型（IRModel）

```jsonc
{
  "schema_version": "0.3",        // 受控升级：0.2 遗留仍可校验；未知版本拒绝
  "domain": "photon",             // "photon" | "quantum" | "hybrid"
  "name": "ring-fsr-design",
  "components": [ ... ],          // 器件实例（见 §3）
  "nets": [ ... ],                // 网表连接（见 §4.2）
  "pdk_ref": "noeic::std",        // 倾向 foundry::node；null=不限定
  "foundry_plan": { ... },        // 多 foundry 落点意图（见 §4.4）
  "objectives": [ ... ],          // 设计目标/硬约束（见 §4.1）
  "spectrum": { ... },            // 目标谱形（见 §4.3）
  "notes": ""
}
```

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `schema_version` | string | ✅ | 现行 `"0.3"`；`"0.2"` 遗留兼容；其它拒绝 |
| `domain` | enum | ✅ | `photon` / `quantum` / `hybrid` |
| `name` | string | – | 设计名（可读标签） |
| `components` | array | ✅ | 器件实例列表（≥1） |
| `nets` | array | – | 网表连接 |
| `pdk_ref` | string\|null | – | foundry::node 引用 |
| `foundry_plan` | object\|null | – | 落点意图 |
| `objectives` | array | 见 §6-7 | 目标/约束 |
| `spectrum` | object\|null | 见 §6-7 | 目标谱形 |
| `notes` | string | – | 自由备注 |

**设计意图完整性**：`spectrum` 与 `objectives` **至少其一**必须存在，否则桥接层无意图可执行（校验规则 7 拦截）。

## 3. 组件模型（Component）

```jsonc
{
  "id": "ring1",
  "kind": "RingResonator",          // 见 §5 Kind 注册表
  "params": { "R": 10.0, "Q": 1e4, "kappa": 0.05 },
  "param_bounds": { "R": [8.0, 12.0], "Q": [1000.0, 100000.0] },
  "ports": [ { "name": "in", "directed": false }, ... ],
  "foundry_hints": [],
  "physics": {                       // D-40 一等字段：物理定律锚（round-trip 必须保留）
    "bid": "B9",
    "kind": "transmon-f01",
    "spec_params": { "E_J": 20.0, "E_C": 0.3 },
    "anchor": "Koch2007 解析色散近似 f01=√(8·E_J·E_C)−E_C"
  }
}
```

| 字段 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `id` | string | ✅ | 器件唯一标识（网表引用依据） |
| `kind` | string | ✅ | Kind 注册表内（§5） |
| `params` | object | ✅ | 几何/工艺/物理参数名值对 |
| `param_bounds` | object | – | 可调参数及其工艺窗口 `[lo, hi]` |
| `ports` | array | – | 端口列表（`name` + `directed`） |
| `foundry_hints` | array | – | 给 agent 的软提示 |
| `physics` | object\|null | – | 物理定律锚（bid/kind/spec_params/anchor） |

## 4. 子对象

### 4.1 ObjectiveSpec（设计目标/约束）

```jsonc
{ "bid": "B11", "weight": 1.0, "target": 0.0, "tol": 0.05, "role": "objective" }
```

- `bid`：harness 标准题号，形如 `B<数字>`（宽松校验）；
- `role`：`objective`（agent 优化命中 target±tol）/ `constraint`（必须 PASS，不过整体 FAIL）。

### 4.2 Net（网表连接）

```jsonc
{ "id": "net1", "connects": ["ring1.in", "wg1.out"] }
```

- `connects` 每项引用 `component_id.port_name`，必须在 components 中存在（校验规则 2）。

### 4.3 SpectrumSpec（目标谱形）

```jsonc
{ "kind": "ring_fsr", "target_fsr_nm": 9.15, "wl0_um": 1.55, "n_g": 4.2, "primary_param": "R" }
```

- `kind`：`ring_fsr`（环形 FSR 目标，metric=FSR_c 与 golden.b11 同式）；`lorentz_comb`（预留）；
- `primary_param`：驱动谱形的主几何参数，须在主器件 params/param_bounds 内（校验规则 4）。

### 4.4 FoundryPlan（多 foundry 落点意图）

```jsonc
{ "mode": "all" }                          // 或 { "mode": "list", "foundries": ["noeic", "cumec"] }
```

- `mode`：`all`（跨全部已注册 foundry）/ `list`（仅指定列表，列表须非空）。

### 4.5 PhysicsAnchor（物理定律锚，D-40 一等字段）

```jsonc
{ "bid": "B12", "kind": "resonator-f0", "spec_params": {...}, "anchor": "λ/4 闭式 f0=1/(4l√(L′C′))" }
```

- `bid`：已知物理锚题号集合 `{B9, B12, B13}`；
- `kind`：物理模型名（`transmon-f01` / `resonator-f0` / `coupler-J` 等）；
- `spec_params`：物理规范参数（供严格求解器消费，**非空**）；
- `anchor`：人类可读的确定性定律说明。

**物理锚是"LLM 不进判决路径"的载体**：下游验证裁判按 `physics.bid` 直接算确定性真值并比对（光子靠折射率/几何，量子靠约瑟夫森/充电能），路径与光子完全一致。

## 5. Kind 注册表（9 kind）

### 5.1 光子子集（6 kind）

| kind | 关键参数 | 端口 | 物理锚 |
|---|---|---|---|
| `RingResonator` | R, Q, kappa(, n_g, target_fsr_nm) | in/out/drop | B11 谱形 |
| `Waveguide` | width | in/out | B1/B4 场级 |
| `GratingCoupler` | period, duty | fib/wg | B6 耦合效率 |
| `Splitter` | length, width | in/out1/out2 | 自成像对称 |
| `DirectionalCoupler` | gap, Lc | in1/in2/out1/out2 | CMT 耦合 |
| `SymmetricYBranch` | width, split_angle, arm_length | in/out1/out2 | 对称性定理 |

### 5.2 量子子集（3 kind，全部挂确定性物理锚）

| kind | 关键参数 | 端口 | 物理锚 |
|---|---|---|---|
| `Transmon` | E_J, E_C(, target_f01) | control/readout | **B9** f01=√(8·E_J·E_C)−E_C（Koch2007；严格侧=D-35 对角化） |
| `Resonator` | Lp, Cp, l, Q | in/out | **B12** f0=1/(4l√(L′C′))（λ/4 闭式；严格侧=D-39 离散 TL 本征值） |
| `Coupler` | g, E_J1/E_C1/E_J2/E_C2, Cc, C1, C2 | a/b | **B13** J=Jc·n01₁·n01₂（Koch 类；严格侧=D-39 441 维对角化） |

> 新 kind 接入 = 在 `lda_ir/photon.py` 或 `quantum.py` 注册构造器 + 加入 Kind 清单（§7 扩展指南）。

## 6. 校验规则（validate，7 项）

| # | 规则 | 语义 |
|---|---|---|
| 0 | schema 版本受控 | 0.3 现行 / 0.2 兼容 / 未知拒绝 |
| 1 | component id 唯一 | 重复即非法 |
| 2 | net 连接闭合 | `comp.port` 引用必须存在 |
| 3 | objective/constraint bid 合法 | 形如 `B<数字>` |
| 3b | physics 物理锚合法 | bid∈{B9,B12,B13} 且 spec_params 非空 |
| 4 | spectrum 规格合法 | kind 已知、target>0、primary_param 在主器件内 |
| 5 | params 落在 param_bounds | 当前值越界即非法 |
| 6 | foundry_plan 合法 | mode∈{all,list}，list 时 foundries 非空 |
| 7 | 设计意图完整 | spectrum 或 objectives 至少其一 |

校验返回**全部**错误列表（非首个即停），便于 agent 一次性修复。

## 7. 扩展指南（新 kind 接入三步）

1. **代码注册**：在 `lda_ir/photon.py`（或 `quantum.py`）添加构造器（kind/params/param_bounds/ports，量子须挂 PhysicsAnchor），并入 KNOWN_KINDS。
2. **Schema 同步**：`docs/ir_schema.json` 的 `kind` enum 追加；`docs/ir_spec.md` §5 注册表补行。
3. **零漂移验证**：跑 `run_ir_spec_smoke.py`（文档-代码漂移检测 + 新 kind 示例 conforms）。

## 8. 向后兼容（0.2 → 0.3 受控升级）

- `schema_version=0.3` 新增 `Component.physics`（物理锚一等字段）；序列化契约补齐（D-76 修复：physics 经 round-trip 保留）。
- `schema_version=0.2` 遗留模型（无 physics）仍可校验通过（validate 规则 0 放行）；消费方按 `physics` 缺失优雅降级。
- 未知版本（如 `0.4`）明确拒绝——不允许静默演进。

## 9. 序列化契约

- `to_dict(m)` / `from_dict(d)`：纯 dict ↔ IRModel 双向 round-trip，**零信息损失**（含 physics）；
- `dumps(m)` / `loads(s)`：JSON 字符串互转（agent 间标准机器语言）；
- `to_dsl(m)`：单向人类可读渲染（调试/人审，**不回灌**）。

## 10. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.1 | 阶段 1 | 光子子集草案（Waveguide/Ring/Splitter/Bragg 等） |
| 0.2 | 2026-08-20 | 补全方向耦合器/对称 Y 分支字段；量子子集骨架字段 |
| 0.3 | 2026-08-21 | **PhysicsAnchor 一等字段**（B9/B12/B13 确定性物理锚）；schema 受控升级（0.2 兼容） |
| 0.3（定稿） | 2026-08-23 | **D-76 标准化发布**：开放 spec 文档 + JSON Schema draft-07 + 零漂移校验；修复 physics 序列化 round-trip 缺陷（此前 round-trip 丢物理锚） |

---

*本规范与 `docs/ir_schema.json` 保持机器可校验的零漂移；与《LDA 技术白皮书》架构分层、`docs/design_package_spec.md` 设计包规范配套。社区/第三方按本规范接入 = 共建 L0 标准。*
