# LDA L0 统一 IR 草案 · 光子子集

> **版本**：v0.1.0-draft · 2026-08-14
> **定位**：LDA 架构 **L0 层**（统一中间表示）的光子子集草案——**机器优先 DSL**，是 agent 间 / agent 与内核间的"机器语言"
> **性质**：阶段 1 第一块真地基（属 MEMORY「基础工作量力而行原则」①类）；草案，由验证 harness 反馈与设计迭代演进
> 配套：机器可读契约 `LDA_L0_IR_光子子集_schema.json`、《LDA 技术白皮书》§12（系统设计哲学）、《LDA 领域文献与工具知识基线》（模块1 L0 字段来源）

---

## 0. 为什么 L0 必须是"机器优先 DSL"

依据《白皮书》§12 的系统设计哲学——LDA **为人结果负责设计**，不是**为人操作设计**。旧工具（gdsfactory/Meep 等）的 GUI、逐步点击、给人看的报表，对 LDA 是无用的交互壳。因此 L0 的定位是：

- agent 之间交换"设计意图"的**机器语言**（非人读 GUI 配置）；
- agent 与 L3 求解内核之间的**确定性接口**（批处理、可验证、无交互）；
- 验证 harness 的**比对对象**（每个组件挂 `sim_ref` → 确定性 harness 算误差 → 判 pass/fail）。

人类 DSL 仅是 L0 的一层可选视图，由 L1 协议层翻译；**L0 本体是 JSON**（本草案），未来可加 Proto 二进制以提升 agent 间吞吐。

---

## 1. 设计原则

1. **机器优先、可序列化**：JSON（Schema 2020-12 校验），非人读优先。
2. **最小完备**：覆盖"组件定义 → 电路网表 → 工艺绑定 → 验证挂载"闭环，不堆冗余。
3. **可验证**：每个组件/电路可挂 `sim_ref` + `verification.benchmarks`，直接咬合验证 harness（B1–B10）。
4. **可扩展**：`@extensions.quantum` 预留量子字段（EPR/T1-T2/门保真度），光子子集不填——后期统一 IR 复用同一 schema 主干。
5. **借鉴不重造**：字段直接来自业界验证过的 gdsfactory `Component/Netlist/PDK`、KQCircuits `Element/refpoints`、EDA-Q `fab_process/device_map`。

---

## 2. 顶层设计（顶层对象）

| 字段 | 必填 | 含义 |
|---|---|---|
| `lda_version` | ✓ | IR 语义版本（破坏性变更升 major） |
| `schema` | ✓ | 子集标识：`photon-subset`（未来 `quantum-subset`/`unified`） |
| `process` | ✓ | 工艺绑定（foundry / pdk / layers / design_rules / material_stack） |
| `library` | ✓ | 参数化组件库（`components` map，PCell 原生） |
| `netlist` | ✓ | 电路网表（instances / connections / 顶层 ports） |
| `layout` | — | 版图生成指令（交 L3 / gdsfactory 类执行） |
| `verification` | — | 验证 harness 挂载点（benchmarks 绑定 B1–B10） |
| `@extensions` | — | 量子扩展预留位 |

---

## 3. 核心类型（摘要，完整见 schema.json）

- **process**：`foundry` + `pdk_name` + `layers`（逻辑层→GDS layer/datatype）+ `design_rules` + `material_stack`（含折射率 `index`，供解析基准 B2）。
- **component**：`type`（waveguide/ring/grating_coupler/ydc/mzi/taper/crossing…）+ `params`（参数化几何）+ `ports`（命名 IO）+ `refpoints`（KQCircuits 式自动定位）+ `sim_ref`（指向求解器/ORACLE）。
- **sim_ref**：`solver`（meep/mpb/sax/tidy3d/ai_fdtd/analytical）+ `golden`（对应 B1–B10）+ `license_note`（GPL 仅外部调用 / Apache 可深度集成）。
- **netlist**：`instances`（引用 library 组件 + params_override）+ `connections`（`from`/`to` 端口连接）+ `ports`（顶层 IO）。
- **verification**：`benchmarks`（`id`/`metric`/`target`/`tol`/`oracle`），确定性 harness 据此算误差判 pass/fail。

---

## 4. 完整示例（SOI 波导 B2 + add-drop 环形谐振器 B4）

```json
{
  "lda_version": "0.1.0-draft",
  "schema": "photon-subset",
  "metadata": {
    "project": "LDA-demo-ring",
    "author": "LDA-agent",
    "created": "2026-08-14T09:30:00+08:00",
    "target_foundry": "CUMEC-130nm-SOI",
    "notes": "光子子集草案示例：SOI 波导 + add-drop 环形谐振器"
  },
  "process": {
    "foundry": "CUMEC",
    "pdk_name": "CUMEC-130-SOI",
    "layers": {
      "wg_core": { "gds_layer": 1, "gds_datatype": 0, "purpose": "硅波导芯" },
      "clad":    { "gds_layer": 2, "gds_datatype": 0, "purpose": "氧化硅包层" }
    },
    "design_rules": { "min_width": 0.12, "min_gap": 0.12, "min_radius": 5, "units": "um" },
    "material_stack": {
      "si":   { "material": "Si",   "thickness": 0.22, "index": 3.48 },
      "sio2": { "material": "SiO2", "thickness": 2.0,  "index": 1.44 }
    }
  },
  "library": {
    "components": {
      "wg_1550": {
        "type": "waveguide",
        "params": { "width": 0.5, "height": 0.22, "wavelength": 1.55 },
        "ports": [
          { "name": "in",  "position": [0, 0],  "orientation": 0,   "layer": "wg_core", "mode": "TE0" },
          { "name": "out", "position": [10, 0], "orientation": 0,   "layer": "wg_core", "mode": "TE0" }
        ],
        "sim_ref": { "solver": "analytical", "model": "EIM", "golden": "B2", "license_note": "解析基准，零成本" }
      },
      "ring_r10": {
        "type": "ring",
        "params": { "radius": 10, "wg_width": 0.5, "gap": 0.2 },
        "ports": [
          { "name": "in",  "position": [0, 0],  "orientation": 0,   "layer": "wg_core", "mode": "TE0" },
          { "name": "out", "position": [0, 20], "orientation": 180, "layer": "wg_core", "mode": "TE0" }
        ],
        "sim_ref": { "solver": "sax", "model": "ring_theory", "golden": "B4", "license_note": "SAX 电路级确定性 ORACLE（Apache-2.0 可深度集成）" }
      }
    }
  },
  "netlist": {
    "instances": {
      "wg1": { "component": "wg_1550" },
      "R1":  { "component": "ring_r10" }
    },
    "connections": [ { "from": "wg1.out", "to": "R1.in" } ],
    "ports": ["wg1.in", "R1.out"]
  },
  "verification": {
    "benchmarks": [
      { "id": "B2", "metric": "n_eff", "target": 2.44, "tol": 0.01, "oracle": "analytical" },
      { "id": "B4", "metric": "FSR_nm", "target": 9.15, "tol": 0.5, "oracle": "sax" }
    ]
  }
}
```

> 说明：B2（`n_eff≈2.44`）走解析真值（零成本）；B4（FSR≈9.15nm @ R=10μm, n_g≈4.18）走 SAX 确定性 ORACLE。两者恰好印证知识基线模块4"P0 先搭解析/确定性真值 harness"的选型。

---

## 5. 与 L1 / L3 / 验证 harness 的衔接

| 层 | 如何用 L0 |
|---|---|
| **L1 agent 协议层** | Interpreter/Designer/Layout/Verification 四个 agent 的**输入输出皆为 L0 实例**；L1 的"人操作壳→agent 操作接口"翻译，本质是把自然语言/旧 GUI 配置**编译成 L0**，再把 L0 **反序列化为 L3 调用** |
| **L3 求解内核 / ORACLE** | `component.sim_ref` 告诉 L3「这个组件用哪个求解器算、golden 是 B 几」；AI 写的内核与 Meep/SAX 等 ORACLE 都通过 L0 这个统一句柄被调度 |
| **验证 harness** | 读 `verification.benchmarks` → 跑对应 ORACLE/解析解 → 算 metric 与 `target` 的误差 → 对照 `tol` 输出 pass/fail + 偏差量 → 人据此验收 |

**闭环**：自然语言 →(L1 Interpreter)→ L0 草稿 →(L1 Designer)→ L0 定稿（含 sim_ref/benchmarks）→(L3 + ORACLE 执行)→ 结果 →(验证 harness)→ pass/fail → 人验收。L0 贯穿全程，是 agent 协作的"通用语"。

---

## 6. 量子扩展预留（`@extensions.quantum`）

光子子集不填，但 schema 预留：
```json
"@extensions": {
  "quantum": {
    "epr": { "participation_ratio": 0.0 },
    "t1_us": null, "t2_us": null,
    "gate_fidelity": { "single_q": null, "two_q_cz": null }
  }
}
```
后期统一 IR 复用同一 `process/library/netlist` 主干，仅在此扩展量子物理字段——避免 EDA-Q 所指出的"每类量子路线重写工具链"碎片化。

---

## 7. 演进说明（草案，非终稿）

- 本 schema 为 **v0.1.0-draft**，破坏性变更升 major；由「LDA 领域研究室」结合验证 harness 实际反馈持续演进。
- 下一步校准项：① 组件 `type` 枚举随逆设计需求扩充；② `sim_ref` 增加 AI 快内核（ai_fdtd）的置信度字段；③ 统一 IR 合并量子子集时的字段对齐。
- **不追求一次完美**：L0 是复利资产，先竖切光子子集跑通闭环（MVP），再横切统一——符合"先单点、后统一"决议与技术复利原则。

---

*本草案为 LDA 阶段 1 真地基首块，配套机器可读契约 `LDA_L0_IR_光子子集_schema.json`。*
