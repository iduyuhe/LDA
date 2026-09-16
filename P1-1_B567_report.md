# LDA · P1-1 B5/B6/B7 第二独立求解器报告 ⇒ B5、B6 升 Tier-3 严格独立；B7 诚实不升

> 日期：2026-09-16 · 版本：v0.9.81 · 指令：「B5/B6/B7 全写第二独立求解器」
> 结论：**B5、B6 各接第二独立求解器升 `strict_independent`（三分类 60/3/21 → 62/3/19，和=84 不变；独立率 71.4% → 73.8%）；B7 因离线 golden 不可用而诚实不升 —— `design_rule_anchor` 保留，候选脚本随附完整证据链。**

---

## 0. 结论先行

| 锚 | 原类别 | 新类别 | 候选 | golden | 候选值 | \|diff\| | tol | 余量 |
|---|---|---|---|---|---|---|---|---|
| **B5** Y 分支 1×2 分束插入损耗 | `design_rule_anchor` 自证桩 | **`strict_independent`** | `ybranch_eme` | 3.4000 dB | **3.0321 dB** | 0.3679 | 1.0 | 2.7× |
| **B6** 光栅耦合器峰值耦合效率 | `design_rule_anchor` 自证桩 | **`strict_independent`** | `grating_fp` | 0.5000 | **0.3909** | 0.1091 | 0.15 | 1.38× |
| **B7** 波导交叉串扰 | `design_rule_anchor` 自证桩 | 不变（**诚实不升**） | （候选已写，未接线） | −19.7328 dB | −35.36 dB | 15.63 | 5.0 | ❌ golden 不可用 |

- 三分类：**严格独立 62 · 降级 3（E9+E10+B21）· 自证桩 19 · 和 84**；独立率 **73.8%**（62/84）。
- `provenance` 迁移：`independent_cross_check` 60 → **62**；`design_rule_anchor` 3 → **1**（仅余 B7）；`self_authored_closed_form` 低置信 12 道**不变**。
- **CI core 177 条不变**（未新增 smoke；复用既有 `run_benchmark_falsifiability_smoke` 的 84/84 无回归 + 端点 ≡ CLI + JSON 无 numpy 泄漏三判据）。
- 零物理判据改动、零容差放宽、零判决行为改动。

---

## 1. 三道锚的 golden 侧真相（先查事实，再动手）

「第二独立求解器」的前提是 **golden 本身可信且可用**。因此第一步是探测 golden 真实来源（`resolve_field_oracle`），而非直接写候选。

| 锚 | golden 解析路径 | 实测值 | 来源标签 | 可用性 |
|---|---|---|---|---|
| B5 | `_ybranch_overlap`（离线唯象重叠估计 `3.0 + 0.4·(θ_deg/10)²`，θ=10°） | **3.4** | `numpy-overlap-offline` | ✅ 可用（设计守则下限 3.0 为 fallback） |
| B6 | Tidy3D 3D 场级 ORACLE 缺失 ⇒ 回退 | **0.5** | `design-anchor` | ✅ 可用（**唯一真·design_rule 锚**） |
| B7 | `_fdtd2d_crossing`（离线 2D FDTD） | **−19.7328** | `numpy-fdtd-offline` | ❌ **四路诊断全不收敛** |

- 环境 `LDA_MEEP_PY` 未设 ⇒ Meep 子进程不可用 ⇒ 三者均走离线分支。
- 顺带修掉两处「标签≠行为」：`benchmarks.py` 的 B5 `note` 原写「黄金=理想 50/50 下限 3.0 dB」，实际取的是离线重叠估计 **3.4**；B7 `note` 原写「黄金=−40 dB」，实际取的是离线 FDTD **−19.73**。均已按真实来源改写（含 fallback 值与来源标签）。

---

## 2. B5 · 候选 `ybranch_eme`（Y 分支双芯超模 EME）

**方法学**（`_batch_b567_numeric.ybranch_split_loss_dB`，纯 numpy）：

1. **EIM 垂直降维**：解平板 TE0 色散 `u·tan u = √(V²−u²)`（brentq）得 2D 有效折射率 `n_eff`；
2. **双芯亚网格剖面**：两芯中心 `±d_f/2`（`d_f = 2·w_core`），逐格按**重叠面积加权**取折射率（`np.clip(ov,0,h)` 保证芯重叠并集，避免双计）；
3. **逐片完整 Helmholtz 本征解**：每 z 切片解横向本征值问题（`eigh_tridiagonal`），得局部正交模族 `{φ_j}`；
4. **单向传播 + 级联重叠**：`φ_{j+1} ← Σ exp(−iβ·dz)·(φ_{j+1}ᵀφ_j·dx)·φ_j`，逐片累积透射系数；
5. **判决量**：`split_loss_dB = 10·log10(2) − 10·log10(T)`（`T = Σ|c|²`）。

**结果**：`3.0321 dB` vs golden `3.4`，`|diff| = 0.3679 < tol 1.0`（余量 2.7×），`responds=True`，返回 Python 原生 `float`。

> **诚实边界（已写入 `_VMM_OVERRIDES["B5"]`）**：本锚在默认参数邻域**参数判别力弱**（±10% 扰动仅 ~0.005 dB，打不穿 tol 1.0）⇒ **不进 `PERTURB_SPEC` 反向表**（与 B8「T→1 上界锚」同类，非缺陷：物理上 Y 分支插入损耗对参数的敏感度本就低于 tol）。
> `candidate_responds()`（相对候选自身基线，`thresh=1e-12`）已实测 **True**，覆盖「裸桩」判定。

---

## 3. B6 · 候选 `grating_fp`（首原理四因子分解）

**方法学**（`_batch_b567_numeric.grating_coupler_eff`）：

| 因子 | 物理含义 | 默认点取值 |
|---|---|---|
| `η_dir = 1/2` | 辐射对称性（光栅向上/向下各半） | 0.5 |
| `η_ov` | 高斯光纤模场 ⊗ 指数衰减光栅模场**重叠积分**（α 扫描最优） | **0.7846** |
| `F(ff) = \|sin(π·ff)\|` | 占空比衍射效应 | 1.0（ff=0.5） |
| `η_phase = exp(−(Δβ·L_g/2)²)` | 光栅方程相位失配惩罚，`L_g = 20·period` | 0.9964 |

**结果**：`0.3909` vs golden `0.5`，`|diff| = 0.1091 < tol 0.15`（余量 1.38×），`responds=True`，返回 `float`。

> **物理含义（本锚的诚实增量）**：设计守则 `0.5` 是 **`η_ov → 1` 的理想模场匹配上限**；真实均匀光栅（高斯光纤模场 MFD=10.4 µm 对指数光栅模场）可达值 `η_ov = 0.785` ⇒ **守则比真实可达值乐观约 22%**。这是候选给出的**量化结论**，不是数值巧合。
> **诚实边界**：候选不含金属反射镜假设（`η_dir` 固定 1/2）；光纤参数取 SMF-28（MFD=10.4 µm）；已写入 `_VMM_OVERRIDES["B6"]` 与 `candidate_desc`。
> **判别力**：B6 对 period/ff/n_si/wl 的 ±10% 扰动敏感（`η_phase` 指数衰减为 0），判别力充足；但因**默认点残差 0.109 已接近 tol 0.15**（余量 1.38×），未纳入 `PERTURB_SPEC`，避免「扰动信号 < tol」的伪护栏。

---

## 4. B7 · 为何**诚实不升**（golden 侧缺陷，非候选侧缺陷）

### 4.1 候选已写出：CMT/双芯超模法

`_batch_b567_numeric.crossing_crosstalk_dB`：双芯超模 `n_e/n_o` → 耦合系数 `κ = π|n_e−n_o|/λ` → 有效长度 `L_eff = w_core` → `crosstalk = 10·log10(sin²(κ·L_eff))`，实测 **−35.36 dB**。

### 4.2 但 golden 不可用 —— 四路收敛诊断（全部不收敛）

| 诊断维度 | 取值 → 结果 | 收敛？ |
|---|---|---|
| 计算域 | 8 / 12 / 16 µm → −19.73 / −13.25 / −12.43 dB | ❌ 单调漂移 7.3 dB |
| 网格 | 50 / 40 / 25 nm → −19.73 / −17.59 / −14.85 dB | ❌ 单调漂移 4.9 dB |
| 监视器位置 | 1.5 / 2.5 / 3.5 µm → −11.3 / −16.4 / −20.7 dB | ❌ 散射 9.4 dB |
| 时间步数 | 1400 / 2000 / 3000 → −19.73 / −17.25 / −15.00 dB | ❌ 单调漂移 4.7 dB |

能流积分法更直接给出 **+10 ~ +15 dB（>0，非物理）**。

### 4.3 根因（两条，独立成立）

1. **sponge 吸收强度弱约 100×**：`sig_max = 0.06`，而 `dt = dl/(√2)·0.95 ≈ 0.0336` ⇒ 每步吸收 `1−e^{−0.06·0.0336} ≈ 0.2%`；实测需 `sig_max ≳ 1.0` 才饱和 ⇒ **场从未稳态**，结论随步数/域尺寸线性漂移（上表即证）。
2. **2D 下度量不良定义**：B7 的「cross 口」在 2D 截面里用**单点 `Σ|E|²`** 采集，而该点的能量是**交叉区近场辐射**（随监视距离 1.5→3.5 µm 单调衰减 9.4 dB，见上表），**不是垂直波导的导模功率**。2D 交叉结构没有「垂直方向」可承载导模 ⇒ 3D 才良定义的量被压进 2D 截面。

### 4.4 结论：不接线，保留 `design_rule_anchor`

- 两法定量分歧（golden −19.73 vs 候选 −35.36，差 15.6 dB）**本身即证明 golden 不是可用 ORACLE**；硬接会把「golden 缺陷」伪装成「候选残差」⇒ 属**假绿**。
- 正确顺序：**先修 golden**（sponge 强度 ≳1.0 + 改 3D 或改为良定义的度量），再接独立候选。
- 候选函数**保留在库中但未登记**（`crossing_crosstalk_dB` docstring 完整记录本节证据链），供后续 golden 修复后一步接线。
- `_VMM_OVERRIDES["B7"]` **保持 `design_rule_anchor`**；`benchmarks.py` B7 `note` 已按真实来源（离线 FDTD −19.73 + 不可用声明）改写。

---

## 5. 接线（三处）

| 文件 | 改动 |
|---|---|
| `lda/lda_harness/_batch_b567_numeric.py` | **新增 246 行**：`_te0_neff_slab` / `_grid` / `_multicore_profile` / `_slab_modes` / `ybranch_split_loss_dB`(B5) / `_gauss_exp_overlap` / `_best_overlap` / `grating_coupler_eff`(B6) / `crossing_crosstalk_dB`(B7，未接线) |
| `lda/lda_harness/verification_adapters.py` | 追加 `_get_batch_b567()`（双路兜底导入）+ `@_register_candidate("ybranch_eme")` → `_b5_ybranch_eme_candidate` + `@_register_candidate("grating_fp")` → `_b6_grating_fp_candidate` |
| `lda/lda_harness/benchmarks.py` | `BENCHMARK_DEFS["B5"]` 加 `"candidate": "ybranch_eme"` + `candidate_desc` + `note` 订正；`["B6"]` 同理；`_VMM_OVERRIDES["B5"]/["B6"]` provenance `design_rule_anchor` → **`independent_cross_check`**；`["B7"]` note 订正（**override 不变**） |

分类器实测：`_vmm_classify(B5)=strict_independent`、`B6` 同、`B7=self_certified`（`prov=design_rule_anchor`）。

---

## 6. 计数护栏同步（活跃护栏 7 文件 / 23 处）

三分类 60/3/21 → **62/3/19**，独立率 71.4% → **73.8%**，题数 84 不变：

| 文件 | 改动 |
|---|---|
| `README.md` | 新增顶行「本地未发版 · P1-1 B567」块；账本段三分类 60→62 / 21→19；路径① `verified=60/84`→**62/84**（含「独立候选 60/84」串）；VMM 段 `design_rule_anchor（B5/B6/B7）`→`（B7）` |
| `CONTRIBUTING.md` | 顶行账本三分类（版本行维持 `v0.9.79`）；动态真值段同步（tag `v0.9.81`） |
| `ALIGNMENT_REPORT.md`（12 处） | 摘要表 59/3/22→62/3/19；B-3 基线段追加 B567 段；S4 守卫证据；P1① 行 71.4%→73.8%；守卫表 4 行；缺口段 25.0%→22.6%、`B5/B6/B7 待场级 ORACLE`→`B7 待场级 ORACLE（B5/B6 已于 v0.9.81 升严格独立）`；P1-1 状态行 |
| `lda/run_benchmark_falsifiability_smoke.py` | docstring 三分类；**`MIN_INDEPENDENT` 60 → 62** |
| `lda/run_webui_verification_ledger_smoke.py` | docstring 三分类 |
| `lda/run_maturity_baseline_smoke.py` | docstring 三分类 `(60/3/21，和=84)`→**`(62/3/19，和=84)`** |
| `P1-1_self_certified_discipline.md` | 全文刷新为 19 道；design_rule 桶 3→1（B5/B6 结清、B7 增「先修 golden」升级路径）；占比 25.0%→22.6% |

> 未同步（历史快照，按纪律**不改史**）：`P1-1_B16_re_review_report.md`、`P1-1_batchB/B2/B3_report.md`、`LDA_stub_upgrade_ceiling_2026-09-14.md`。已同步活跃纪律文件 `P1-1_self_certified_discipline.md`（非快照，为 PR 评审必查件）。

---

## 7. 验证：计数护栏实跑全绿

| 守卫 smoke | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke` | **6/6 PASS**（README ≡ harness ≡ ledger docstring ≡ CONTRIBUTING = 62/3/19，反向篡改会响） |
| `run_count_consistency_smoke` | **11/11 OK**（引擎 22 / 包 11 / 题 84 / CI core 177） |
| `run_maturity_baseline_smoke` | **M1–M5 PASS**（strict=62 degraded=3 self_certified=19，和=84；低置信 12 道） |
| `run_webui_verification_ledger_smoke` | **15/15 PASS**（端点 62/3/19） |
| `run_three_class_consistency_smoke` | **4/4 PASS**（README ≡ harness ≡ 端点 = 62/3/19，和=84） |
| `run_benchmark_falsifiability_smoke` | **13/13 PASS**（严格 62 / 降级 3 / 自证 19；84/84 无回归；端点 ≡ CLI） |

---

## 8. 诚实边界

- **B5 无参数判别力**（±10% 扰动 ~0.005 dB ≪ tol 1.0）⇒ 不进 `PERTURB_SPEC`；已有 `candidate_responds` 行为判据兜底。
- **B6 余量 1.38× 偏低**（残差 0.109 / tol 0.15），且候选不含镜面假设、光纤参数取 SMF-28 单点值。
- **B7 未升格**：golden 侧缺陷（sponge 弱 ~100× + 2D 度量不良定义），候选已写出但**未登记**；硬接将构成假绿。
- **本次为纯方法学**：不涉及 T2 真值回流（仍为 0 轮 MPW），不改动任何降级锚状态。
- 剩余自证桩 **19 道** = terminal Tier-1 **12** 道（B17/B18/S1-S6/S9-S12，按设计永不升·非缺口）+ `design_rule_anchor` **1** 道（B7，待修 golden）+ `t2_blocked` **6** 道（E1/E3-E7，卡 T2 实测通道）。

---

## 9. 后续

- P1-1 状态：严格独立率 **73.8%（62/84）**；B5/B6 专项**结清**。
- 最高性价比下一步：**E1/E3-E7 共 6 道**（卡 T2 外部实测通道，受 foundry/MPW 现实 KPI）；B7 需先做 golden 修复（sponge ≳1.0 + 度量改 3D/良定义）。
- 生产部署：按既有流程 `scripts/sync_push.py` + `remote_deploy.py --expect-head <commit>` 推送三端并部署。
