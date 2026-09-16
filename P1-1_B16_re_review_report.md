# LDA · P1-1 B16 重审报告：rib-MMI 严格求解器接入 ⇒ 升 Tier-3 严格独立

> 日期：2026-09-16 · 版本：v0.9.80 · 指令：「B16 重审：实现 rib-MMI 严格求解器，接独立候选升 strict（纯方法学，无阻塞）」
> 结论：**B16 由 `self_certified` 升 `strict_independent`。三分类 59/3/22 → 60/3/21（和=84 不变）；独立率 70.2% → 71.4%。**

---

## 1. 动机：为什么 B16 是唯一「该升而未升」的物理题

- B16 = **脊形 MMI（rib-MMI）1×2 自成像长度**，golden 为 Soldano & Pennings (1995) 抛物线色散闭式：
  `L = (9/4)·n_eff·W_e²/λ = (9/8)·L_π^wg`，`tol = 3.0 µm`，`default_params = {W_e: 2.0, n_eff: 2.4, wl: 1.55}`。
- 前序曾尝试以 `mmi_eme`（symmetric-slab EME 本征模展开）接线，**被否决**，根因是**对象错配**——symmetric-slab 建模的是对称平板，与器件的 rib（脊形）波导不是同一物理对象，导致 ~13% 系统偏差。
- B16 因此长期留桩，是「B-3 收官后 22 道自证桩」中最典型的一道「**路径明确、纯方法学、无外部阻塞**」题（`re_review` 锁类型唯一实例）。

---

## 2. 对象一致性铁律（B21 教训的正面复用）

> **独立求解器必须建模同一物理对象。** 设备给定的是基模有效折射率 `n_eff`，而非芯层材料折射率 `n_c`。

据此，本候选不另设 slab 结构，而是**由器件给定的 `n_eff` 反演**对称平板 core 折射率 `n_c`，使平板基模 **≡** 器件 MMI 基模：

- 同对象约束 ⇒ 平板基模有效折射率 = 器件给定 `n_eff`（默认 2.4）；包层固定 SiO₂ `n_clad = 1.444`。
- 反演方程即 TE 偶模本征方程 `h·tan(h·a) = √(K²−h²)`，其中 `a = W_e/2`、`K = k₀√(n_c²−n_clad²)`、`h = k₀√(n_c²−n_eff²)`。

---

## 3. 候选方法学（`rib_mmi_selfimaging_length`）

四步，全程纯 numpy、C 级自主、零商业/A 级依赖：

1. **`_invert_core_index`**：解 `h·tan(h·a)=q` 反演 `n_c`，使平板基模 ≡ 器件 `n_eff`。
2. **`_slab_mode_effs`**：精确解 TE 平板本征方程，取**全部导模**（`n_modes=200` 上限）。🔴 求根区间须按 `h·a ∈ (mπ, mπ+π/2)` 即 **`h ∈ (mπ/a, (mπ+π/2)/a)`** 分区间二分；遗漏 `/a` 会漏掉基模并坍缩到伪根（见第 7 节血案）。
3. **`_slab_mode_fields` + 全场重构**：输入场按全部导模展开 `ψ(x,z)=Σ_m a_m·ψ_m(x)·exp(iβ_m z)`，沿 z 精确传播。
4. **双度量联合定位 1×2 首像**（本报告关键创新）：
   - 度量① `ov(z)` = 输出强度与理想双像（两峰位于 ±a/2）的归一化重叠；
   - 度量② `M(z) = min(I(−a/2), I(+a/2)) / I(0)`（双瓣高 × 中心零深）。
   - 取「**首个同时满足 `ov ≥ 95%·max(ov)` 且 `M ≥ 40%·max(M)` 的 z**」→ 局部细扫。

> **为何「不要求局部极大」**：`ov` 峰位与 `M` 峰位存在微小错开（如 W=2.0 时 14.163 vs 14.428 µm），若强加「同点局部极大」则无解、会跳到晚期像（z≈38 µm）。改为「首个双阈值穿越」后，细化步骤自然落到真峰，全宽度域一次通过。

---

## 4. 方法学独立性论证（为何是「验证」而非「自洽」）

| 维度 | golden（抛物线闭式） | candidate（全场模态重构） |
|---|---|---|
| 数学路线 | 抛物线色散近似 `β ≈ β₀ − (π λ /(4 n_eff W_e²))` 下的闭式解 | 精确本征方程 + 全模态叠加传播，**不套任何成像因子** |
| 是否同源 | — | 与 golden **不同源**（无共同中间量） |
| 残差性质 | — | = 抛物线近似的**固有误差**（有界、物理、非零、随参数单调变化） |

- 残差 `|diff| ≠ 0` ⇒ 满足可证伪判据（⑧ strict 锚必须 `|diff|≠0`）；
- 反向 10% 扰动必 FAIL ⇒ 判据 D 响应（已由 `run_benchmark_falsifiability_smoke` 13/13 覆盖）；
- 非代数恒等 ⇒ `run_d_criterion_smoke` 10/10 PASS（60/60 已接线候选 0 道代数恒等）。

---

## 5. 实测残差（跨全宽度域，诚实披露）

| W_e (µm) | golden L (µm) | candidate L (µm) | \|diff\| (µm) | tol=3.0 | 余量 |
|---|---|---|---|---|---|
| 2.0 | 13.935 | 14.191 | **0.256** | PASS | 11.7× |
| 2.4 | 20.067 | 20.316 | **0.249** | PASS | 12.0× |
| 2.8 | 27.314 | 27.851 | **0.537** | PASS | 5.6× |
| 3.2 | 35.667 | 36.587 | **0.920** | PASS | 3.3× |
| 3.6 | 45.135 | 46.615 | **1.480** | PASS | 2.0× |
| 4.0 | 55.720 | 57.930 | **2.210** | PASS | **1.36×** |

- `n_eff` / `λ` 变体残差均 <1 µm。
- ⚠️ **诚实边界**：残差随 `W_e` 单调增长（0.26→2.21 µm），因抛物线近似在大宽度下误差累积；`W_e=4.0` 余量仅 **1.36×**（偏低但在 tol 内）。已写入 `note` 与 `_VMM_OVERRIDES`，**不掩盖**。

---

## 6. 接线（三处）

| 文件 | 改动 |
|---|---|
| `lda/lda_harness/_batch_b16_rib_mmi.py` | **新增**：`_invert_core_index` / `_slab_mode_effs` / `_slab_mode_fields` / `rib_mmi_selfimaging_length`（主入口，返回 Python 原生 `float`） |
| `lda/lda_harness/verification_adapters.py` | 追加 `_get_batch_b16()` 惰性加载器 + `@_register_candidate("rib_mmi_recon", ...)` 注册进 `BENCHMARK_CANDIDATES` |
| `lda/lda_harness/benchmarks.py` | `BENCHMARK_DEFS["B16"]` 加 `"candidate": "rib_mmi_recon"` + `candidate_desc` + note；`_VMM_OVERRIDES["B16"]` provenance 由 `self_authored_closed_form` → **`independent_cross_check`** |

分类器 `_vmm_classify(B16)` = `strict_independent`；`candidate_responds=True`；返回类型 `float`（无 numpy 标量泄漏）。

### 派生计数变化（低置信集）
- `self_authored_closed_form` 低置信锚：**13 → 12 道**（B16 迁出）。
- `independent_cross_check`：2 → 3 道。

---

## 7. 🔴 血案：求根区间漏 `/a` 致基模丢失

- 首版 `_slab_mode_effs` 偶模区间误写为 `h ∈ (mπ, mπ+π/2)`（漏 `/a`），导致基模 `h=1.028`（对应 `n_eff=2.4`）被漏检，二分坍缩到伪根 —— `W_e=2.8` 时基模错误返回 `2.382`（≠ 2.4）。
- 修复：区间改为 `h ∈ (mπ/a, (mπ+π/2)/a)`（奇模 `h ∈ ((mπ+π/2)/a, (m+1)π/a)`）⇒ 基模正确返 2.4，导模数由 5 升至 7。
- 教训（并入项目铁律）：**超越方程分区间求根，区间必须带物理尺度 `/a`；否则静默漏根且不报错** —— 属「值≠行为」类陷阱的求根版本。

---

## 8. 计数护栏同步（全仓 23 处）

三分类 59/3/22 → **60/3/21**，独立率 70.2% → **71.4%**，题数 84 不变：

| 文件 | 改动 |
|---|---|
| `README.md` | 顶行三分类 59→60 / 22→21；B16 备注；低置信备注；路径① `verified=59/84`→**60/84**；残留 stale 串「独立候选 59/84」→ 60/84 |
| `CONTRIBUTING.md` | 顶行账本三分类 59/3/22→60/3/21（版本行维持 `v0.9.79`）；动态真值段同步（B16 重审 tag `v0.9.80`） |
| `ALIGNMENT_REPORT.md`（10 处） | 三分类和 56→84；严格 31→60 / 自证 22→21；独立率 70.2%→71.4%；端点/守卫表/缺口段全同步；真候选 7 道→**6 道**；P1-1 状态行 |
| `lda/run_benchmark_falsifiability_smoke.py` | docstring 三分类 59→60 / 22→21；`MIN_INDEPENDENT` 59→**60** |
| `lda/run_webui_verification_ledger_smoke.py` | docstring 三分类；**低置信 13→12**；`_DOC_LOW_CONF` 13→12 |
| `lda/run_maturity_baseline_smoke.py` | docstring 三分类 `(28/1/23，和=53)`→**`(60/3/21，和=84)`** |
| `P1-1_self_certified_discipline.md` | 全文刷新为 21 道（B16 结清、re_review 无实例、真候选 6 道） |

---

## 9. 验证：全量守卫 8/8 PASS

| 守卫 smoke | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke` | **6/6 PASS**（README ≡ harness ≡ ledger ≡ CONTRIBUTING = 60/3/21，反向篡改会响） |
| `run_three_class_consistency_smoke` | **4/4 PASS**（60/3/21，和=84） |
| `run_count_consistency_smoke` | **11/11 PASS**（引擎 22 / 包 11 / 题 84 / CI core 177） |
| `run_webui_verification_ledger_smoke` | **15/15 PASS**（端点 60/3/21；低置信 12） |
| `run_maturity_baseline_smoke` | **M1–M5 PASS**（strict=60 degraded=3 self_certified=21；低置信 12 道） |
| `run_d_criterion_smoke` | **10/10 PASS**（60/60 已接线候选 0 道代数恒等） |
| `run_benchmark_falsifiability_smoke` | **13/13 PASS**（严格 60 / 降级 3 / 自证 21；84/84 无回归；端点 ≡ CLI verified=60/60；JSON 无 numpy 泄漏；桩反向自检 3/3） |
| `run_ci_coverage_gate_smoke` | **6/6 PASS**（190 smoke；core=177；豁免 18，理由齐备） |

> 全绿，且守卫均带**反向自检**（篡改 ⇒ 必响），非假绿。

---

## 10. 诚实边界

- 残差是**抛物线近似的固有误差**，不是候选缺陷；`W_e=4.0` 余量 1.36× 偏低，已在代码 note 明示。
- B16 升 strict 后，22 道自证桩 → **21 道**；其中 **6 道为真候选（E1/E3-E7，卡 T2 外部实测通道）**，**12 道为 terminal Tier-1（定义/算术自检，按设计永不升，非缺口）**，**3 道为 design_rule 锚（B5/B6/B7，待场级 ORACLE）**。
- 本次为**纯方法学**升格，**不涉及 T2 真值回流**（仍为 0），不改变任何降级锚状态。

---

## 11. 后续

- P1-1 状态：严格独立率 **71.4%（60/84）**，B16 专项**结清**；`re_review` 锁类型当前无实例。
- 剩余可升级自证桩 = **E1/E3-E7 共 6 道**，全部卡 T2 实测通道（受 foundry/MPW 现实 KPI）。
- 生产部署：本次代码已落地并全绿，按既有流程 `sync_push.py` + `remote_deploy.py --expect-head <commit>` 推送三端并部署。
