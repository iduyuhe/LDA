# LDA 统一设计包规范（Design Package Specification）

**版本**：v0.1（2026-08-21，D-44 交付）
**状态**：现行标准 · 机器可校验（配套 JSON Schema：`docs/design_package_schema.json`）
**范围**：LDA 所有设计闭环（光子/量子/混合系统）产出的**统一交付格式**

---

## 1. 目的与原则

LDA 的定位是"产出**可用的设计结果（design outcome）**，而非辅助人设计的软件"。
无论用户/agent 设计的是单个器件还是多器件系统，交付物都是**同一份 DesignPackage**
——格式一致、机器可校验、可汇总对比、可被第三方工具/流程消费。

三条硬原则：

1. **verification.passed 是唯一验收门**。是否可用由**死标量比对**（物理定律锚 /
   严格数值 vs 解析契约）决定；**LLM 不进判决路径**。
2. **每个包都回溯到设计意图 IR**（L0 统一中间表示，`ir` 字段），保证可审计、
   可复现。
3. **honest_notes 必填**。模型的假设、数据的来源、哪些是解析近似、哪些是严格
   数值、哪些是预计算/演示数据，必须诚实标注。

## 2. 顶层结构

```
DesignPackage = {
  package_id        : string    # 唯一 ID，如 "wdm-4ch"
  schema_version    : "0.1"
  kind              : string    # 设计包类型（§4 注册表）
  domain            : "photon" | "quantum" | "hybrid"
  title             : string
  created_at        : string    # ISO 8601
  ir                : object    # 设计意图回溯（§5）
  design            : object    # 目标 + 参数 + 反解（§6）
  verification      : object    # 验收（§7）
  artifacts         : object    # 产物（§8）
  honest_notes      : string    # 诚实标注（必填）
}
```

字段一览：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_id` | string | ✅ | 唯一标识（kind + 关键参数编码） |
| `schema_version` | string | ✅ | 必须为 `"0.1"` |
| `kind` | string | ✅ | 必须 ∈ §4 注册表 |
| `domain` | string | ✅ | 必须 ∈ `{photon, quantum, hybrid}` |
| `title` | string | ✅ | 人类可读标题 |
| `created_at` | string | ✅ | ISO 8601 时间戳 |
| `ir` | object | ✅ | 设计意图（schema 版本/器件/网表/校验） |
| `design` | object | ✅ | targets / params / inverse_design / metrics |
| `verification` | object | ✅ | checks / passed / verdict |
| `artifacts` | object | 按 kind | SVG / 谱 / GDS / 预算等 |
| `honest_notes` | string | ✅ | 诚实标注（非空） |

## 3. 设计包与 LDA 分层的关系

```
L0 IR（lda_ir，schema v0.3）── 设计意图事实源（PhysicsAnchor 物理锚）
   │
   ▼ 设计闭环（D-36~D-43：设计→验证引擎 / 逆设计 / 系统级）
DesignPackage ── 交付物（本规范）
   │
   ▼ 消费方
agent（L1 协议）/ 人（验收）/ 第三方工具 / CI 自动化
```

- `ir` 字段与 L0 IR 一一对应（schema_version / domain / 器件数 / 网表数 / 校验错误）。
- `verification.checks` 与 harness 基准题（B1–B13）同语义：死标量比对明细。
- 第三方对接只需消费 DesignPackage 这一个格式，无需理解内部各闭环。

## 4. kind 注册表（v0.1 · 6 kind）

| kind | 来源 | domain | targets 典型键 | params 典型键 | artifacts 典型键 |
|---|---|---|---|---|---|
| `add_drop` | D-37 环形 add-drop 产品链路 | photon | `fsr_nm` | `R` `gap` `wg_width` | `layout_svg` `spectrum` `gds` `budgets` |
| `quantum` | D-41 量子 agent 逆设计闭环 | quantum | `transmon`/`resonator`/`coupler`（目标 GHz） | `E_J` `E_C` / `Lp` `Cp` `l` / `Cc` … | `numerical` `analytic` |
| `wdm` | D-42 WDM 多环级联系统设计 | photon | `channels_nm` | `ring_radii_um` `gap_um` `wg_width_um` | `layout_svg` `spectrum` `gds` |
| `readout_chain` | D-43 光子-量子混合链路 | hybrid | `f01_ghz` `f_r_ghz` `g_ghz` `kappa_r_ghz` | `E_J` `l_m` `Cc` `Q_ext` | `verification_detail` |
| `multiqubit` | D-46 N-qubit 频率复用读出 | hybrid | `f01s_ghz` `delta_ghz` `g_ghz` | `readout_freqs_ghz` `kappa_r_ghz` `kappa_ext_ghz` `kappa_i_ghz` `chi_ghz` `qubits[]` | `spectrum`（力线透射谱）`dip_resolvability` |
| `readout_fidelity` | D-47 单发读出保真度预算 | hybrid | `f01_ghz` `delta_ghz` `g_ghz` `kappa_r_ghz` | `T1_us` `nbar` `eta` `N_amp` `t_m_star_ns` `budget` | `sweep`（SNR/保真度随 t_m 扫描） |

> 新增 kind 指南见 §10。

## 5. `ir`（设计意图回溯）

```json
{
  "schema_version": "0.3",
  "domain": "photon",
  "n_components": 4,
  "n_nets": 5,
  "validate_errors": []
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | L0 IR schema 版本（当前 0.3） |
| `domain` | string | IR domain（photon/quantum/hybrid） |
| `n_components` | int | IR 器件数 |
| `n_nets` | int | IR 网表连接数 |
| `validate_errors` | string[] | IR 静态校验错误（空 = 合法） |

## 6. `design`（设计内容）

```json
{
  "targets": { "fsr_nm": 17.5 },
  "params": { "R": 5.2023, "gap": 0.3 },
  "inverse_design": { "formula": "..." },
  "metrics": { "il_drop_db": [...], "xt_min_db": [...] }
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `targets` | object | ✅ | 设计目标（用户/agent 给定的规格） |
| `params` | object | ✅ | 设计出的参数（闭式反解或搜索最优） |
| `inverse_design` | object | 按 kind | 反解公式/说明 |
| `metrics` | object | 按 kind | 中间性能指标（如 WDM 信道 IL/串扰） |

## 7. `verification`（验收 —— 唯一验收门）

```json
{
  "checks": [
    { "name": "每信道 drop IL ≤ 3dB", "ok": true, "detail": "..." }
  ],
  "passed": true,
  "verdict": "WDM 4 信道级联系统设计 PASS：..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `checks` | object[] | ✅ | 逐项死标量比对（name/ok/detail） |
| `passed` | boolean | ✅ | **唯一验收门**：全部 checks.ok 才为 true |
| `verdict` | string | ✅ | 人类可读判定（含关键数值） |

**判定铁律**：`passed` 由死标量比对决定（物理定律锚：解析解/闭式 ↔ 严格数值
对角化/离散本征值/真实 FDTD）；**LLM 不进判决路径**。消费者应以 `passed` 为
唯一可用性判定，不依赖 `verdict` 文本。

## 8. `artifacts`（产物）

按 kind 可选，常见键：

| 键 | 类型 | 说明 |
|---|---|---|
| `layout_svg` | string | 版图/系统 SVG（内联） |
| `spectrum` | object | 谱数据（wavelengths + drop/thru 等） |
| `gds` | object | GDSII 摘要（libname/元素数/层/字节数） |
| `budgets` | object | 耦合/损耗预算表（add_drop） |
| `numerical` / `analytic` | object | 严格数值 vs 解析契约明细（quantum） |
| `verification_detail` | object | 器件级双验证明细（readout_chain） |
| `dip_resolvability` | object[] | 相邻读出 dip 可分辨检查（multiqubit） |
| `sweep` | object[] | SNR/保真度随 t_m 扫描预算表（readout_fidelity） |

## 9. 机器校验规则（validate_package）

配套 `lda_design/design_package.py::validate_package(pkg)`，规则：

1. 必填字段齐全：`package_id` `schema_version` `kind` `domain` `title`
   `created_at` `design` `verification` `honest_notes`
2. `schema_version == "0.1"`
3. `kind ∈ {add_drop, quantum, wdm, readout_chain, multiqubit, readout_fidelity}`
4. `domain ∈ {photon, quantum, hybrid}`
5. `verification.passed` 存在（验收门）
6. `honest_notes` 非空（诚实标注必填）

> 机器可读形式：`docs/design_package_schema.json`（JSON Schema draft-07）。

## 10. 扩展指南（注册新 kind）

1. 在 `lda_design/design_package.py` 的 `_BUILDERS` 注册打包器
   `package_from_<kind>(...)`：包装对应设计闭环的产物 → 统一 schema。
2. `_DEFAULTS` 提供该 kind 的默认参数。
3. 在 `_REQUIRED` 校验不变的前提下，`design`/`artifacts` 按 kind 自由扩展。
4. 更新 `PACKAGE_KINDS` 与本文档 §4 注册表。
5. 跑 `run_design_package_smoke.py` 全绿后交付。

## 11. 示例（完整包，WDM 4 信道）

见 `reports/packages/wdm.json`（构建产物，与 `build_all()` 同源）。
以下为结构示意：

```json
{
  "package_id": "wdm-4ch",
  "schema_version": "0.1",
  "kind": "wdm",
  "domain": "photon",
  "title": "WDM 4 信道多环级联系统设计",
  "created_at": "2026-08-21T14:00:00+08:00",
  "ir": { "schema_version": "0.3", "domain": "photon",
          "n_components": 4, "n_nets": 5, "validate_errors": [] },
  "design": { "targets": { "channels_nm": [1550.0, 1552.5, 1555.0, 1557.5] },
              "params": { "ring_radii_um": [9.9851, 10.0012, 10.0173, 10.0334],
                          "gap_um": 0.3 },
              "inverse_design": { "formula": "R=m·λ/(2π·n_g)（谐振对齐闭式）" },
              "metrics": { "il_drop_db": [0.002, 0.034, 0.052, 0.115],
                           "xt_min_db": [18.41, 21.32, 21.37, 53.16] } },
  "verification": { "checks": [ { "name": "邻信道串扰 XT ≥ 15dB",
                                  "ok": true, "detail": "18.4/21.3/21.4/53.2dB" } ],
                    "passed": true,
                    "verdict": "WDM 4 信道级联系统设计 PASS：..." },
  "artifacts": { "layout_svg": "<svg ...>", "spectrum": { "...": "..." },
                 "gds": { "libname": "LDA-WDM", "size_bytes": 4560 } },
  "honest_notes": "级联传递为解析物理模型（D-37 add-drop 传递函数，bus 串联）；..."
}
```

## 12. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 0.1 | 2026-08-21 | 初始发布（D-44）：schema + 4 类 kind + 校验规则 + JSON Schema |
| 0.1.1 | 2026-08-21 | kind 注册表扩展至 6 类（D-48 配套）：新增 `multiqubit`（D-46 N-qubit 频率复用读出）与 `readout_fidelity`（D-47 单发读出保真度预算）；§7 artifacts 常见键补充 `dip_resolvability` / `sweep`；§9 机器校验规则 kind 枚举同步更新 |
