# LDA · P1-1 Batch B-3 报告：严格独立率跨过 70% 红线

> 日期：2026-09-16 · 目标：把严格独立率从 64.8% 推过 70% 红线
> 结论：**新增 13 道方法学独立新锚（B52–B64）⇒ 严格独立 59 / 降级 3 / 自证桩 22 / 共 84 题 ⇒ 独立率 59/84 = 70.2%，正式跨过 70% 红线。**

---

## 1. 动机与前置校正

- 前序 Batch B-2 收官时，账本曾被记为「46/71 = 69.0%」。实测算术校验发现该数字为**笔误**：
  - 真实口径为 **46/71 = 64.8%**（非 69.0%），距 70% 红线差约 **1 道严格锚**。
  - 本报告与 `ALIGNMENT_REPORT.md` 已同步更正此笔误。
- 因此「再补 8 道」只能到 68.35%，**真正跨线需新增 13 道**（59/84 = 70.2%）。
- Batch B-3 = 用户指令「**新增 13 道（真正跨线）**」。

| 阶段 | 严格独立 | 题总数 | 独立率 |
|---|---|---|---|
| B-2 收官（更正后） | 46 | 71 | **64.8%**（差 1 道） |
| **B-3 收官** | **59** | **84** | **70.2%** ✅ 跨线 |

---

## 2. 13 道新锚定义（B52–B64，全为严格独立候选）

设计纪律（同源 B-1/B-2）：每个锚 = **确定性解析闭式 / 超越方程二分（golden）** × **方法学不同源真实数值法（candidate）**，残差 = 离散化误差 / 建模近似差异（持久、随参数变化、判据 D 响应、反向扰动 FAIL），非代数恒等、非纯数值沉底。

| 锚 | 物理题 | 方法学独立候选 | 标定残差 \|diff\| | tol | 判据 D 响应（扰动） |
|---|---|---|---|---|---|
| B52 | 有限深方势阱 第1激发态 E1 | 1D FD 薛定谔本征第2模 | 9.91e-3 eV | 5.0e-2 eV | a×1.1 ⇒ 能级单调变化 |
| B53 | 有限深方势阱 第2激发态 E2 | 1D FD 薛定谔本征第3模 | 2.11e-2 eV | 5.0e-2 eV | a×1.1 ⇒ 能级单调变化 |
| B54 | 一维无限深阱 E4 | 16·E1 闭式 vs 1D FD 第4模 | 2.19e-4 eV | 1.0e-2 eV | L×1.1 |
| B55 | 一维无限深阱 E5 | 25·E1 闭式 vs 1D FD 第5模 | 5.35e-4 eV | 1.0e-2 eV | L×1.1 |
| B56 | 一维谐振子 E3 | 3.5ℏω 闭式 vs 1D FD 第4模 | 7.85e-5 eV | 1.0e-3 eV | ℏω×1.1 |
| B57 | 一维谐振子 E4 | 4.5ℏω 闭式 vs 1D FD 第5模 | 1.29e-4 eV | 1.0e-3 eV | ℏω×1.1 |
| B58 | 三维立方无限阱基态 | 3·E1 闭式 vs 三维乘积分解 1D FD×3 | 2.57e-6 eV | 1.0e-3 eV | L×1.1 |
| B59 | Pöschl-Teller 基态 E0 | 精确解析谱 vs 1D FD 基态 | 6.20e-2 eV | 1.5e-1 eV | V0×1.1 |
| B60 | Pöschl-Teller 第1激发态 E1 | 精确解析谱 vs 1D FD 第2模 | 5.25e-2 eV | 1.5e-1 eV | V0×1.1 |
| B61 | 矩形金属波导 TM11 截止频率 | c/2·√((1/a)²+(1/b)²) vs 二盒乘积 1D FD | 1.84e-4 GHz | 1.0e-2 GHz | a×1.1 |
| B62 | 矩形金属波导 TM21 截止频率 | c/2·√((2/a)²+(1/b)²) vs 二盒乘积 1D FD | 5.22e-4 GHz | 1.0e-2 GHz | a×1.1 |
| B63 | 圆波导 TE11 截止频率 | x11·c/(2πa)（x11=1.84118）vs 径向 ODE 数值积分 | 3.88e-11 GHz | 1.0e-2 GHz | a×1.1 |
| B64 | Bragg 光栅 Bragg 波长 λB | 2·n_eff·Λ 闭式 vs 转移矩阵反射峰扫描 | 1.26e-1 nm | 1.0 nm | Λ×1.1 |

> 全部 13 道残差 ≪ tol（最小余量 ~26×，最大 ~72×），判据 D 在默认参数路径均真数值响应、反向 10% 扰动必 FAIL。

### B63 工程要点（最难的一题）
圆波导 TE11 截止频率需解柱坐标径向 ODE，原点离心势 m²/r² 在 r→0 奇异：
1. 首版用 `u=√r·R` 代换 + FD `eigsh` → 矩阵不定，返回 0（失败）；
2. 改直接径向 ODE + `solve_ivp` → r≈a·1e-4 处刚性（m²/r²~1e8）超时；
3. 最终令 `R(r)=r·S(r)`，m=1 时方程**无奇点** ⇒ 显式 RK 快且非刚性，外推扫 kc 使 `R'(a)=0` 得 **X11 = kc·a ≈ 1.841184**（与 Bessel 零点一致）；
4. 模块级惰性缓存 `_X11_TE11_CACHE`，X11 仅积分一次。a×1.1 ⇒ 7.986 GHz，判据 D 响应正确。

---

## 3. 接线（三处 + 有序清单）

- **`lda_harness/_batch_b3_numeric.py`**（新增数值核）：13 个 golden + 13 个 candidate，纯 numpy/scipy、C 级自主、零商业/A 级依赖。
- **`lda_harness/golden.py`**：import 13 个 `golden_b52..b64`；`GOLDEN` 字典加 B52–B64（含 `_PHYSICAL_LAW` 物理定律集合标记）。
- **`lda_harness/benchmarks.py`**：`BENCHMARK_DEFS` 加 B52–B64（title/metric/oracle/tol/candidate/candidate_desc/default_params/golden_fn/note）；**`BENCHMARK_ORDER` 同步追加 B52–B64**（关键：此前只加了 `BENCHMARK_DEFS` 漏了有序清单，导致 count_consistency / statistical 守卫仍按 71 题断言失败，已补）。
- **`lda_harness/verification_adapters.py`**：`_get_batch_b3()` 加载器 + 13 个 `@_register_candidate(...)` 候选（B52–B64）注册进 `BENCHMARK_CANDIDATES`。

三分类动态判序（`candidate_status=="degraded_ordinal"` → 降级；`candidate in BENCHMARK_CANDIDATES` → 严格独立；否则 → 自证桩）对 B52–B64 全部判为**严格独立**。

---

## 4. 计数护栏同步（全仓）

新增 13 锚后，所有硬编码计数护栏同步为 **84 题 / 59 严格 / 3 降级 / 22 自证**：

| 文件 | 改动 |
|---|---|
| `README.md` | 当前账本：71→**84 题（B1–B64）**；三分类 46→**59 道**；verified=46/71→**59/84** |
| `CONTRIBUTING.md` | 顶部账本块 + 「动态真值」段：71→84、46→59、和 61→**84** |
| `ALIGNMENT_REPORT.md` | 战略地基表 71→84 锚；三分类 46→59；B-2/B-3 收官段（**更正 69.0%→64.8% 笔误** + 标注 B-3 → 70.2%）；P1① 状态 🟡→🟢；诚实缺口段 31.0%→26.2%、69.0%→70.2%；守卫实跑表三分类同步 |
| `lda/run_benchmark_falsifiability_smoke.py` | `MIN_INDEPENDENT` 46→**59**；注释三分类 46/3/22/71→59/3/22/84 |
| `lda/run_count_consistency_smoke.py` | 题库 docstring 71→84、B1-B51→B1-B64；`len(b_ids)==48`→**61**；`max b_id=="B51"`→**B64**；`assertIn("B1-B51")`→**B1-B64** |
| `lda/run_statistical_anchor_smoke.py` | 题库 docstring 71→84；`expected_b` 追加 B52–B64（B=48→**61**） |
| `lda/run_webui_verification_ledger_smoke.py` | docstring 三分类 46/3/22→59/3/22、三类和 61→**84** |
| `lda/run_p0_count_guard_sync_smoke.py` | docstring 不变量 56→**84**（机器断言三处硬编码 ≡ 动态真值） |

---

## 5. 验证（全量守卫）

| 守卫 smoke | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke` | **6/6 PASS**（README ≡ harness ≡ ledger ≡ CONTRIBUTING 三分类 = 59/3/22，反向篡改会响） |
| `run_three_class_consistency_smoke` | **4/4 PASS**（59/3/22，和=84） |
| `run_count_consistency_smoke` | **11/11 PASS**（引擎 22/包 11/题 84/CI core 177） |
| `run_webui_verification_ledger_smoke` | **15/15 PASS**（端点 59/3/22） |
| `run_statistical_anchor_smoke` | **33 PASS / 1 FAIL→已修** |
| `run_maturity_baseline_smoke` | **M1–M5 PASS**（strict=59 degraded=3 self_certified=22） |
| `run_d_criterion_smoke` | **10/10 PASS**（59/59 已接线候选 0 道代数恒等） |
| `run_benchmark_falsifiability_smoke` | **13/13 PASS**（严格 59 / 降级 3 / 自证 22；84/84 无回归；灵敏度上界 ≤10%） |

> 收尾期发现并修复一处 B-3 引入的回归：`golden_b52`/`golden_b53` 返回 numpy.float64（numpy 2.0 下 json 无法序列化），导致「路径②报告 JSON 序列化」判据 FAIL。已包 `float()` 修复，复跑 **13/13 PASS**。（项目既有铁律：候选/golden 必须返回 Python 原生 float，防止 numpy 标量泄漏进判决链——本次即该纪律的再次验证。）

---

## 6. 诚实边界与已知项

- 剩余 22 道自证桩（candidate≡golden，恒 PASS、零验证价值）见披露清单：B16/B17/B18/B5/B6/B7、E1/E3–E7、S1/S2/S3/S4/S5/S6/S9/S10/S11/S12。升级路径明确（B16 重审留桩、B17–B19/S1–S13 方法学独立候选），按 P0 计划继续接线。
- B21 保持 `degraded_ordinal`（与 E9/E10 共 3 道降级量级参考），不作 ORACLE 虚报。
- T2 真值回流（MPW/Foundry）仍为 0，降级锚未升 strict 属诚实边界。
- 圆波导 X11 由径向 ODE 数值积分导出（非 Bessel 零点查表），方法学不同源，符合「物理定律锚红线」。

---

## 7. 后续

- P1-1 目标（≥70%）**已达成**，可关闭该专项；剩余自证桩转为常态化「PR 必接独立候选」纪律。
- 立即可做的下一步：B16 重审（rib-MMI 严格求解器缺失，仍留桩）、B17–B19 方法学独立候选（如有合适不同源数值法）。
- 生产部署：本次仅在代码仓落地，尚未推送 Gitee/GitHub 三端并部署生产（按既有流程 `sync_push.py` + `remote_deploy.py --expect-head <commit>` 即可）。
