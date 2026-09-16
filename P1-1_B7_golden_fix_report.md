# LDA · P1-1 B7 golden 修复报告 ⇒ golden 语义订正 + 候选接线 ⇒ B7 升 Tier-3 严格独立

> 日期：2026-09-16 · 版本：v0.9.82 · 指令：「B7 需先做 golden 修复（sponge ≳1.0 + 度量改 3D/良定义）」
> 结论：**按「先修 golden 再接候选」路径完成 B7 golden 侧三层缺陷修复与诊断；第三层缺陷「2D 降维 + 模型-器件不匹配」决定性成立（与锚定实证差 20~30 dB）⇒ 经用户拍板订正 golden 语义（撤出已证失真的 2D 离线 FDTD、golden 回设计守则锚 −40 dB）⇒ 接线 CMT 超模法候选，B7 升 `strict_independent`（三分类 62/3/19 → 63/3/18，独立率 73.8% → 75.0%）。诚实披露：残差占 tol 窗口 93%，属边缘通过。**

---

## 0. 结论先行

| 项 | 值 |
|---|---|
| B7 golden（订正后） | **−40.0 dB**（设计守则锚，有 E-SOI-CROSS-XT −41±2 dB 独立实证背书；`dispatch_offline` 不再包含 B7） |
| B7 候选 `crossing_cmt`（CMT 超模法） | **−35.3626 dB** |
| 判决 | `\|diff\| = 4.63741 < tol 5.0` ⇒ **PASS**；`class = strict_independent`；`responds = True`；`type = float` |
| 三分类 | **严格独立 63 · 降级 3（B21/E9/E10）· 自证桩 18 · 和 84**；独立率 **75.0%**（63/84） |
| `provenance` 迁移 | `design_rule_anchor` 1 → **0**（B7 由 `design_rule_anchor` → `independent_cross_check`）；`self_certified` 19 → **18** |
| CI core | **177 条不变**（未新增 smoke；复用既有 `run_b5b7_rollback_floor_smoke` 反向守边界） |
| 诚实边界 | **残差占 tol 窗口 93%，边缘通过**；彻底闭合需 3D 全波 + 真实 taper 版图（T2 级缺口） |
| 零改动 | 零物理判据放宽、零 golden 数值改动（−40 不变）、零容差改动 |

---

## 1. B7 golden 病灶三层缺陷（全部代码级验证）

> 上一轮（v0.9.81）结论：B7 因「离线 2D FDTD golden 四路不收敛」诚实不升，建议「先修 golden（sponge 强度 ≳1.0 + 改 3D 或改为良定义度量）」。本报告即该修复的执行与验证。

### 1.1 第一层：吸收层（sponge）弱约 2 个数量级，且衰减算子不稳定

| 项 | 原实现 | 问题 | 修复 |
|---|---|---|---|
| 强度 | `sig_max = 0.06` | 相对 `dt = dl/(√2)·0.95 ≈ 0.0336` ⇒ `σ·dt ≈ 0.002`，**每步只吸收 0.2%**，场从未稳态 | 项目标准公式 `σ_max = target_exp·3·n_clad²/(dt·pml)`（`target_exp = 12`）⇒ `σ_max ≈ 158.75`，`σ·dt ≈ 5.33` |
| 衰减算子 | `(1 − σ·dt)` | `σ_max` 稍大（≈76）即**变负 ⇒ 迭代发散**——这才是原实现被迫只用弱 σ 的**真实原因**（并非「弱吸收够用」） | 改用稳定算子 **`exp(−σ·dt)`**（恒正、无条件稳定） |

### 1.2 第二层：源注入只覆盖衰减暂态，且横向形状不匹配基模

| 项 | 原实现 | 问题 | 修复 |
|---|---|---|---|
| 注入时长 | `if n < ramp + 400:` ⇒ 只注入 460 步 | 而测量窗 `meas_start = 600` 才开始 ⇒ 累加的是**衰减暂态**而非稳态 | **全程 CW** 注入（`Ez[band, src_x] += 0.5·env·sin(ω·n)·shape`），`ramp` 按光周期缩放（`ramp_cycles = 10`） |
| 横向源形状 | 常数/矩形 | 激发大量高阶模，非器件真实基模激励 | **基模匹配横向源形状** `shape`：先跑一次**参考直波导**（`vertical=False`）取稳态剖面 φ，再投影到完整十字结构作源 |
| 稳态自检 | 无 | 无法判断是否达到稳态 | 新增 `seg_drift` 段漂移自检（稳态后漂移应 → 0） |

### 1.3 第三层：度量不良定义（2D 截面用单点 Σ|E|² 采交叉区辐射近场）

| 项 | 原实现 | 问题 | 修复 |
|---|---|---|---|
| 度量 | `acc += np.sum(Ez[band, mon]**2)`（单点 Σ\|E\|²） | 采集的是**交叉区辐射近场**（随监视距离 1.5→3.0 µm 单调漂移 **9.4 dB**），**不是垂直波导导模功率** | 改**净功率流（Poynting）**：2D TE 下 `S_x = −Ez·Hy`、`S_y = +Ez·Hx` |
| 检波 | 无锁相 | 无法分离行波/驻波 | **锁相检波**得复幅度后 `P = Re(Σ A_Ez·conj(A_H))` ⇒ **对驻波免疫**（行波给净流，驻波给零净流） |
| 端口 | 单点 | 十字结构 x 方向对称 ⇒ 垂直波导两侧各得一半 | 对 **±x 两端求和**：`p_ct = max(p_xp,0) + max(p_xm,0)` |

---

## 2. 修复后收敛实测（度量良定义 + 场稳态 ⇒ 四路收敛）

修复前三路漂移 4.7 / 7.3 / 9.4 dB；修复后同维度全部收敛：

| 收敛维度 | 取值 → 结果 | 修复后跨度 | 原跨度 |
|---|---|---|---|
| **时间步数** | 3000 / 6000 / 12000 → −19.042 / −19.030 / −19.028 dB | **0.015 dB** | 4.7 dB |
| **PML 物理厚度** | 1.2 / 1.5 µm → 仅差 0.16 dB | **0.16 dB** | 7.3 dB |
| **监视面距离** | 1.5 / 2.0 / 2.5 / 3.0 µm → −10.89 / −10.86 / −11.05 / −11.27 dB | **0.4 dB** | 9.4 dB |
| **波长响应** | 1.50 / 1.55 / 1.60 µm → −22.38 / −19.89 / −18.73 dB | **单调**（物理正确） | — |

> 时空两维收敛量级（0.015 dB / 0.16 dB）已达「判据良定义」标准（相对 tol 5.0 dB 余量 > 30×）。
> 监视面距离残差 0.4 dB（含 ±x 求和后的端口定义），亦远小于 tol。

---

## 3. 决定性发现：第三层缺陷「2D 降维 + 模型-器件不匹配」（2D 内不可修复）

修复 sponge 与度量后，**网格与宽度仍不收敛**——这不是数值问题，而是**模型-器件不匹配**：

| 证据 | 结果 |
|---|---|
| **锚定器件实证** | B7 默认几何 `{w_core:0.5, h_core:0.22, n_si:3.48, n_clad:1.44, wl:1.55, gap:0.2}` 与实证语料 **E-SOI-CROSS-XT 完全相同**（Zhang 2013, IEEE PTL 25(13):1225, DOI 10.1109/LPT.2013.2241049），实测 **−41±2 dB** |
| **2D 降维模型给值** | −11 ~ −20 dB ⇒ 与实证**差 20 ~ 30 dB** |
| **加 taper 展宽** | `W_max` 0.5 → 1.5 µm 仅改善 **3.6 dB**（远不足以弥合 20~30 dB） |
| **源位置深扫** | 1.5 / 2.0 / 2.5 / 3.0 / 3.5 / 4.0 µm → −11.13 / −15.53 / −9.56 / −12.43 / −14.13 / −9.01 dB ⇒ **±3 dB 乱跳，无收敛趋势** |
| **受控变量实验** | `pml×src_off`（1.2/1.5 µm × 2.0/3.5 µm）→ −14.13/−14.29/−15.53/−15.46；域 8/12/16 µm（`src_off=L/4`）→ −15.51/−12.43/−9.03（**不收敛**） |
| **修复前网格/宽度** | `dl = 50/40/25 nm` → −19.03/−14.15/−8.85（v2）；`w_core 0.4/0.5/0.6` → −8.37/−19.03/−9.96（**非单调**） |

**根因**：2D 线源辐射不匹配真实 3D 波导激励；2D 截面没有「垂直方向」承载垂直波导导模 ⇒ **串扰（cross-talk）是 3D 才良定义的量**，被压进 2D 截面后只能测到交叉区辐射近场。**属 3D 级缺口，2D 内不可修复**（与上一轮对 E4/E7 的判定「需精确版图 + 3D 全波」完全一致）。

---

## 4. 决策：订正 golden 语义（用户拍板）

| 方案 | 处置 |
|---|---|
| ❌ 硬接候选 | golden −19.73（2D 失真）vs 候选 −35.36 差 15.6 dB ⇒ 会把「golden 缺陷」伪装成「候选残差」= **假绿** |
| ✅ **订正 golden 语义**（采纳） | ① 撤出已证失真的 2D 离线 FDTD：`resolve_field_oracle('B7')` 现返 **`None`**，`dispatch_offline` 不再包含 B7；② 2D 核**降级为机理诊断量** `_fdtd2d_crossing`（保留但不进判决路径）；③ golden 回**设计守则锚 −40 dB**（有 E-SOI-CROSS-XT −41±2 dB 独立实证背书）；④ 接线 **CMT 超模法候选 `crossing_cmt`** |

**判决实测**：

```
B7  golden= -40.00000 cand= -35.36259 |diff|= 4.63741 tol=5.0   PASS class=strict_independent responds=True type=float
```

### 4.1 候选 `crossing_cmt` 参数响应（物理正确、单调）

| 扫描 | 结果 |
|---|---|
| `w_core` 0.4 / 0.5 / 0.6 → | −32.59 / −35.36 / −37.75 dB（宽芯 ⇒ 串扰↓，单调） |
| `gap` 0.1 / 0.2 / 0.3 → | −24.96 / −35.36 / −45.72 dB（间距↑ ⇒ 耦合↓ ⇒ 串扰↓，单调） |

方法学（`_batch_b567_numeric.crossing_crosstalk_dB`，纯 numpy）：双芯超模 `n_e/n_o` → 耦合系数 `κ = π·|n_e−n_o|/λ` → 有效长度 `L_eff = w_core` → `crosstalk = 10·log10(sin²(κ·L_eff))`。

---

## 5. 代码改动

| 文件 | 改动 |
|---|---|
| `lda/lda_harness/oracle_field.py`（CRLF，194 → 292 行） | 删除失真版 `_fdtd2d_crossing`（58–137 行）；新增模块级 `_B7_DIAG` + `_b7_crossing_core(...)`（修复版求解核，含 `exp(−σdt)` 稳定吸收、全程 CW + 基模匹配源、净功率流度量、`vertical` 开关供参考直波导取 φ）+ 新 `_fdtd2d_crossing(params)`（诊断量）；`resolve_field_oracle` 的 `dispatch_offline` **撤出 `"B7"`**；模块头 docstring 声明 B7 不再作 golden |
| `lda/lda_harness/benchmarks.py`（LF，2000 → 2021 行） | B7 定义块加 `"candidate": "crossing_cmt"` + `candidate_desc` + `oracle` 口径；`note` 重写（守则锚 −40 + 实证背书 + 边缘通过披露 + T2 级缺口）；`_VMM_OVERRIDES["B7"]`：`design_rule_anchor` → **`independent_cross_check`** |
| `lda/lda_harness/verification_adapters.py`（LF，2547 → 2591 行） | 追加 `@_register_candidate("crossing_cmt")` → `_b7_crossing_cmt_candidate(spec, oracle_value)`，调用 `m.crossing_crosstalk_dB(...)`；docstring 含 4 条诚实边界 |
| `lda/lda_harness/_batch_b567_numeric.py`（LF） | 段头注释 `本批不接线` → `v0.9.82 接线`；`crossing_crosstalk_dB` docstring 全文重写（golden 语义订正 + 四路证据 + 4 条诚实边界），函数体不变 |
| `lda/lda_harness/golden.py`（CRLF） | `b7_crossing_crosstalk_dB` docstring 重写：明示回退锚 −40 dB 有 E7 实证背书（DOI），v0.9.82 起原「numpy 2D-FDTD 离线」通道撤出 golden 调度、CI 路径恒定返回 −40 dB |
| `lda/run_b5b7_rollback_floor_smoke.py`（LF，111 → 125 行） | `[A]` 段 B7 断言由「离线近似路径可用」改为反向守边界：①`resolve_field_oracle('B7') is None`；②`golden_value("B7",params)==B7_DESIGN_ANCHOR`；③诊断量 `_b7_crossing_core` 为有限负 dB 且与守则锚相差 >15 dB |

---

## 6. 计数护栏同步（活跃护栏 9 文件）

三分类 62/3/19 → **63/3/18**，独立率 73.8% → **75.0%**，题数 84 不变：

| 文件 | 改动 |
|---|---|
| `README.md` | 新增顶行「本地未发版 · P1-1 B7 golden 语义订正」块；账本段三分类 62→63 / 19→18；路径① `verified=62/84`→**63/84**（含「独立候选 62/84」串同步为 63/84） |
| `CONTRIBUTING.md` | 顶行账本三分类（62→63 / 19→18）；动态真值段同步（tag `v0.9.81`→`v0.9.82`） |
| `ALIGNMENT_REPORT.md`（10 处） | 摘要表 62/3/19→63/3/18；基线链追加 v0.9.82 段；S4 守卫证据 4 行；`d_criterion` 行 62/62→63/63；P1① 行 73.8%→75.0%；缺口段 22.6%→21.4%、`B7 待场级 ORACLE`→`B7 已 v0.9.82 语义订正升严格独立`；P1-1 状态行 |
| `lda/run_benchmark_falsifiability_smoke.py` | docstring 三分类；**`MIN_INDEPENDENT` 62 → 63** |
| `lda/run_webui_verification_ledger_smoke.py` | docstring 三分类 62→63 / 19→18 |
| `lda/run_maturity_baseline_smoke.py` | docstring 三分类 `(62/3/19，和=84)`→**`(63/3/18，和=84)`** |
| `P1-1_self_certified_discipline.md` | 全文刷新为 18 道；`design_rule_anchor` 桶 1→0（B7 结清）；占比 22.6%→21.4%；计数护栏同步行 84/62/3/19→84/63/3/18 |
| `docs/self_certified_anchor_inventory.md` | 快照免责声明中的当前口径 62/19→63/18 |
| `P1-E_T2_unlock_plan.md` | 天花板 73.8%（62/84）→75.0%（63/84）；目标 62→68 / 19→13→**63→69 / 18→12、75.0%→82.1%** |

> 未同步（历史快照，按纪律**不改史**）：`P1-1_B567_report.md`、`P1-1_B16_re_review_report.md`、`P1-1_batchB/B2/B3_report.md`、`CHANGELOG.md`、`docs/lda_strategic_audit_2026-09-03.md`。

---

## 7. 验证：计数护栏实跑全绿

| 守卫 smoke | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke` | **6/6 OK**（README ≡ harness ≡ ledger docstring ≡ CONTRIBUTING = 63/3/18；含反向篡改会响） |
| `run_three_class_consistency_smoke` | **4/4 PASS**（README ≡ harness ≡ 端点 = 63/3/18，和=84；含 C4 反向篡改必须 FAIL） |
| `run_webui_verification_ledger_smoke` | **15 PASS / 0 FAIL**（端点 63/3/18） |
| `run_count_consistency_smoke` | **11/11 OK**（引擎 22 / 包 11 / 题 84 / CI core 177） |
| `run_maturity_baseline_smoke` | **M1–M5 PASS**（strict=63 degraded=3 self_certified=18，和=84；低置信 12 道） |
| `run_benchmark_falsifiability_smoke` | **13/13 PASS**（严格独立 63 · 降级 3 · 自证桩 18/84；`verified=63`；端点 ≡ CLI 口径） |
| `run_d_criterion_smoke` | **10 PASS / 0 FAIL**（63/63 已接线候选 **0 道代数恒等**） |
| `run_ci_coverage_gate_smoke` | **6 PASS / 0 FAIL**（门禁无静默缺口） |
| `run_b5b7_rollback_floor_smoke` | **ALL PASS 11/11**（B7 回退下限精确 = −40.0 dB 且 `source=design-anchor`；反向守「ORACLE 在场绕开下限」） |

> 另有独立分类直查：`IndependentCandidateRouter` 实测 **strict=63 / degraded=3 / stub=18 / 总 84**；`B7` → `strict_independent`；`provenance=independent_cross_check`；`maturity_tier=strict_independent`；`crossing_cmt` 已登录 `BENCHMARK_CANDIDATES`。

---

## 8. 诚实边界

- **B7 边缘通过**：`|diff| = 4.63741 / tol 5.0` ⇒ **残差占窗口 93%**，余量仅 1.08×。已在 README 顶行块、`benchmarks.py` B7 `note`、`_VMM_OVERRIDES["B7"]`、候选 docstring 四处**显著披露**。
- **golden 是设计守则锚（非 3D 全波）**：−40 dB 为设计守则值，其可用性来自 E-SOI-CROSS-XT 独立实证（−41±2 dB）背书，**非** 3D 全波复算值。
- **2D 降维缺口未闭合**：网格/宽度仍不收敛（`dl`、`w_core` 响应非单调），归因于模型-器件不匹配 + 2D 线源激发高阶模 ⇒ **属 3D 全波 + 真实 taper 版图级缺口**（T2），已在 B7 `note` 与候选 docstring 标出。
- **候选参数边界**：`L_eff = 芯宽` 为量级估计；`gap` 语义在原守则锚中未定义（候选按双芯中心距解释）。
- **本次为纯方法学 + golden 语义订正**：不涉及 T2 真值回流（仍为 0 轮 MPW），不改动任何降级锚状态。
- 剩余自证桩 **18 道** = terminal Tier-1 **12** 道（B17/B18/S1-S6/S9-S12，按设计永不升·非缺口）+ `t2_blocked` **6** 道（E1/E3-E7，卡 T2 实测通道）；`design_rule_anchor` 桶**清零**。

---

## 9. 后续

- P1-1 状态：严格独立率 **75.0%（63/84）**；B7 专项**结清**（golden 侧修复 + 语义订正 + 候选接线）。
- 最高性价比下一步：**E1/E3-E7 共 6 道**（卡 T2 外部实测通道，受 foundry/MPW 现实 KPI）；B7 的 3D 全波彻底闭合绑定 T2 外部通道。
- 生产部署：按既有流程 `scripts/sync_push.py` + `remote_deploy.py --expect-head <commit>` 推送三端并部署。
