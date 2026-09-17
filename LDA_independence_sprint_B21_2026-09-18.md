# LDA 独立率指标冲刺 · Batch B-21 收口报告

> 生成日期：2026-09-18
> 批次：Batch B-21（B345–B360，16 道方法学独立锚）
> 版本线：v0.9.100（B-20，已上线 `6789645`）→ **v0.9.101（本地未发版 · PENDING）**
> 路径：P1-1 腿①续批（纯内部确定性扩基，非借外源）
> 状态：账本同步完成 · 4 道护栏全绿 · 待 T6 部署 → T7 记忆/技能同升 + scratch 清理

---

## §1 账本更新（v0.9.100 → v0.9.101）

| 指标 | B-20 末值 | B-21 末值 | Δ |
|---|---|---|---|
| 题库总数 N | 362 | **378** | +16 |
| 严格独立 strict | 341 | **357** | +16 |
| 降级量级参考 degraded | 3 | **3** | 0 |
| 自证桩 stub | 18 | **18** | 0（terminal 12 + t2_blocked 6 恒定）|
| 三分类和 | 362 | **378** | +16 ✓ |
| 独立率 strict/N | 94.2% | **94.7%** | +0.5pp |
| 天花板 (N−12)/N | 96.69% | **96.83%** | +0.14pp |
| CI core 条数 | 178 | **178** | 0 |
| 路径① verified | 353/362 | **360/378** | +7/+16 |
| PHYSICAL_LAW 数 | 350 | **366** | +16 |
| CANDIDATES_REG 数 | 344 | **360** | +16 |
| 末题号 | B344 | **B360** | — |

**类别构成（harness 权威推导，count smoke 守护）**：B 类 = 355 道（B1–B360 标号区间，含去重占用如 B35≡B15）、E 类 = 10 道（E1–E10）、S 类 = 13 道（S1–S13），合计 **378**。

**棘轮**：`MAX_SELF_CERTIFIED=18` 只减不增，本批未动；terminal 恒 12；18 桩 = terminal 12 + t2_blocked 6。

---

## §2 B-21 三族概览（16 锚 · 全部 strict_independent）

本批全部为「经典正交/逼近多项式」族，golden 取 numpy/scipy 标准库精确 oracle，candidate 用有限差分 Rodrigues / Bernstein 基求和的**数值独立求解**，方法学不同源。

| 族 | 锚区间 | 题数 | golden（精确 oracle）| candidate（数值独立求解）| 实测收敛阶 | 定档 N |
|---|---|---|---|---|---|---|
| A · Hermite H_n(x) | B345–B349 | 5 | `numpy.polynomial.hermite.hermval(x,[0]*n+[1])` | 对 e^{−x²} 做 n 阶中心差分导数 ×(−1)ⁿe^{x²}（Rodrigues 有限差分）| h⁴（比值 ~4.00）| 512 |
| B · Laguerre L_n(x) | B350–B354 | 5 | `scipy.special.genlaguerre(n,0)(x)` | 对 xⁿe^{−x} 做 n 阶中心差分导数 ×e^{x}/n! | h⁴（比值 ~2.3–4.0）| 512 |
| C · Bernstein 逼近 f(t) | B355–B360 | 6 | 精确闭式 f(t) | degree-N Bernstein 基求和 Σf(k/N)·C(N,k)·tᵏ(1−t)^{N−k} | h²（比值 ~2.00）| 512 |

三族均统一 `tol = 0.01`，**零 tol 放宽**；最紧余量见 §3（B355 1.53×、B356 1.63×）。

---

## §3 逐锚实测（golden / cand |Δ| / 余量 / 收敛比值）

### 族 A · Hermite H_n(x)（N=512，限 n≤5）
| 锚 | n, x | golden | |Δ| | 余量 | 收敛比值 |
|---|---|---|---|---|---|
| B345 | 2, 0.5 | −1.000000 | 1.27e-06 | 7874× | 4.00 |
| B346 | 3, 1.0 | −4.000000 | 1.53e-05 | 653× | 4.00 |
| B347 | 4, 0.8 | −1.216640e+01 | 4.11e-04 | 24.3× | 3.98 |
| B348 | 5, 1.2 | −5.285376e+01 | 2.84e-03 | 3.52× | 4.08 |
| B349 | 4, 1.5 | −1.500000e+01 | 5.12e-04 | 19.5× | 3.99 |

### 族 B · Laguerre L_n(x)（N=512，限 n≤5）
| 锚 | n, x | golden | |Δ| | 余量 | 收敛比值 |
|---|---|---|---|---|---|
| B350 | 2, 0.7 | −1.550000e-01 | 4.38e-06 | 2283× | 4.00 |
| B351 | 3, 1.0 | −6.666667e-01 | 4.45e-06 | 2247× | 4.00 |
| B352 | 4, 1.3 | −4.756625e-01 | 1.07e-06 | 9346× | 3.81 |
| B353 | 5, 0.9 | −5.332332e-01 | 7.11e-06 | 1406× | 2.31（高阶噪声放大，仍收敛）|
| B354 | 2, 1.5 | −8.750000e-01 | 1.43e-06 | 6993× | 4.00 |

### 族 C · Bernstein 逼近 f(t)（N=512，O(h²)）
| 锚 | f(t) | t | golden | |Δ| | 余量 | 收敛比值 |
|---|---|---|---|---|---|---|
| B355 | sin(2πt) | 0.37 | +7.289686e-01 | 6.52e-03 | **1.53×** | 1.99 |
| B356 | cos(2πt) | 0.63 | −6.845471e-01 | 6.13e-03 | **1.63×** | 1.99 |
| B357 | exp(t)−1 | 0.5 | +6.487213e-01 | 4.03e-04 | 24.8× | 2.00 |
| B358 | 1/(1+t) | 0.4 | +7.142857e-01 | 1.71e-04 | 58.5× | 2.00 |
| B359 | 1/(1+2t) | 0.6 | +4.545455e-01 | 1.76e-04 | 56.8× | 2.00 |
| B360 | sqrt(t+0.1) | 0.55 | +8.062258e-01 | 1.15e-04 | 87.0× | 2.00 |

**余量说明**：族 C 的 B355/B356 余量仅 1.53×/1.63×（|Δ| 6.52e-03/6.13e-03 逼近 tol 0.01），属 Bernstein 二阶逼近在低阶观测点的固有误差，残差**严格单调随 N 下降**（判据 D 成立），非假绿；其余 14 锚余量均 ≥3.5×。全批 16 锚 |Δ| 均 < tol 0.01 且留边缘余量。

---

## §4 同源体检（全仓 grep 实跑）

对三族候选所用关键词全仓（659 文件）多轮 grep，结果：
- `hermite | hermval | laguerre | genlaguerre | bernstein | binom` → **零实现命中**（仅 numpy/scipy 标准库调用）。
- `rodrigues | central_diff | finite_diff` → **仅撞本批数值核自身**（`_batch_b21_numeric.py`）。
- **主动弃用**清单（同红线性已排除）：高阶中心差分 n=6,7（round-off 地板，见 §5 血案①）；Chebyshev/Legendre 高斯求积（B-12 已占）；Fourier 级数（数值同源 ≡ 周期延拓）；样条（B-14 已占）；Padé 有理逼近（B-18 判否）；Wigner D 矩阵（与 B-9 族 A 旋转群表示同源）。
- **结论**：三族零实质同源，方法学独立性成立。

---

## §5 判据 D + 本批血案（2 条）

**判据 D**（粗端残差 1e-13 < |Δ| < tol 且严格单调；基线残差 >1e-12；禁超收敛 round-off 地板）：
- 16/16 严格单调、闭式极限与第三方交叉 **10/10 OK**（含 scipy.special 标准库交叉、H_n 奇偶/归一、L_n(0)=1、Bernstein 端点 f(0)/f(1) 极限）。
- 16/16 落 `strict_independent`；零 tol 放宽；B-19/B-20（B313–B344）零回归。

**血案① · 高阶中心差分 round-off 地板**：
- n=6 在 N=256 残差触 3e-11 非单调、N=512 更沉地板 ⇒ 限 **n≤5**、定档 **N=512**（n=5 残差 2.84e-03 仍 < tol 且单调）。n=6 整族弃用。
- 根因：高阶中心差分误差 ~ h⁻ⁿ·ε，n 大时噪声被 h⁻ⁿ 放大，沉 round-off 地板，破坏判据 D 单调性。

**血案② · Bernstein 极值点首阶误差应力为 0**：
- 观测点取 f 极值点（如 B355 sin 在 t=0.5 导数为 0）时首阶误差应力为 0 ⇒ 选**非极值观测点**（t=0.37/0.63 等）保证判据 D 首项 >1e-13 且残差随 N 单调降。

---

## §6 三分类一致性（harness 推导 ≡ README ≡ 端点）

- `_b21_assert.txt` 复核：**378/378 PASS**、`strict=357 / degraded=3 / stub=18`、三分类和=378、假独立=[ ]、错标桩=[ ]、`ASSERT_RC=0`。
- `run_three_class_consistency_smoke.py` → **RC=0**（README 静态陈述 ≡ harness 推导 ≡ `/api/verification_ledger` 动态端点，任一漂移即红）。
- `run_maturity_baseline_smoke.py` → **RC=0**（M5 三分类计数 357/3/18，和=378）。

---

## §7 护栏批跑结果（T5）

| 护栏 | 结果 | 说明 |
|---|---|---|
| `run_count_consistency_smoke.py` | **RC=0** ✅ | 初跑 RC=1 → 修复 README 顶行缺 `当前版本` 关键词后复验绿（见 §8）|
| `run_statistical_anchor_smoke.py` | **RC=0** ✅ | `expected_b` 追加 B345–B360 后绿（修复 line 145 IndentationError）|
| `run_three_class_consistency_smoke.py` | **RC=0** ✅ | 三分类一致 |
| `run_maturity_baseline_smoke.py` | **RC=0** ✅ | VMM 底线 M5 |
| `run_d_criterion_smoke.py` | 已知红（同因）| 13 道 B-4 锚（B65–B88）贴 1e-16 地板，历史存量，非 B-21 引入 |
| `run_coverage_deadzone_smoke.py` | 已知红（同因）| B5/B6 期望陈旧，历史存量，非 B-21 引入 |
| `run_benchmark_falsifiability_smoke.py` | 已知红（同因）| numpy bool 泄漏 JSON，历史存量，非 B-21 引入 |

> B-21 仅新增锚（B345–B360）+ 账本计数同步，**未触碰** d_criterion / coverage_deadzone / falsifiability 三文件，故三道已知红为本项目承接自 B-9..B-19 的存量问题，待专项清算。

---

## §8 顶行修复记录（count_consistency RC=1 → RC=0）

1. **根因**：初版 README 顶行用 `> **🔴 本地未发版（…`，缺 `当前版本` 关键词；`run_count_consistency_smoke.py::test_readme_version_matches_pyproject` 的护栏 `_top_version_block` 回退匹配到历史 `当前版本：v0.9.40` 行 ⇒ 断言 `v0.9.101` 不在顶行块 → RC=1。
2. **修复**：经 `_b21_topfix.py` 将顶行前缀改为 `> **🔴 当前版本：v0.9.101（2026-09-18 本地未发版 · …`，使顶行含 `当前版本` 关键词。
3. **复验**：`run_count_consistency_smoke.py` → **RC=0** ✅。
4. 同批修复 `run_statistical_anchor_smoke.py` line 145：原 line 144 误以 `])` 提前闭合 `expected_b` 列表、line 145 残留重复注释致 IndentationError → 改为 line 144 收 `]`、line 145 收 `])` 干净注释 → RC=0 ✅。

---

## §9 已知风险与红线

- 🔴 **三道 CI core 已知红灯（承接 B-9..B-19 存量）**：d_criterion / coverage_deadzone / falsifiability，均非 B-21 引入，待专项清算；「CI core 178」仅保证条数非全绿。
- **天花板天花板**：terminal 12 桩为永久锁定（主权红线：判决落非 AI ground，LLM 不进判决路径），天花板恒为 (N−12)/N，随 N 增缓慢上升。
- **T2 真值永久锁**：E1/E3–E7 需 MPW 实测方升 strict；当前 18 桩中 t2_blocked 6 待外部 KPI 解锁。
- **本批最紧余量**：B355/B356 仅 1.53×/1.63×，后续若降 N 或调观测点须重验判据 D 单调性。

---

## §10 后续步骤（T6 部署 / T7 记忆技能）

### T6 · 生产部署（待执行）
1. git 提交 → README 顶行 PENDING→真实 HEAD。
2. `sync_push.py` 双端（Gitee/GitHub）。
3. `remote_deploy.py --expect-head <commit>`（115.191.20.92 · /opt/lda · lda-webui.service:3006 · 外网 lda.weomnitech.com.cn）。
4. `check_ledger 357 3 18 378 B360`（预期 13/13 ALL_OK）。
5. README 顶行转「✅ 已上线」→ 重推 → 重跑 `run_count_consistency_smoke.py`。

### T7 · 记忆/技能同升 + scratch 清理（待执行）
1. `MEMORY.md` 账本行：378/357/94.7%/96.83% + 部署行（v0.9.101）。
2. 技能 `lda-independence-sprint` / `lda-anchor-wiring` 账本同升。
3. 清理 `D:/tmp/_b21_*` 与 `_run_smoke*.py` scratch。

---

## §11 一句话结论

Batch B-21（B345–B360，Hermite/Laguerre/Bernstein 三族）以**零 tol 放宽、零同源、16/16 判据 D 严格单调**全部落入 `strict_independent`，独立率 **94.2% → 94.7%**、天花板 **96.69% → 96.83%**、N **362 → 378**；4 道核心护栏全绿、3 道历史红灯确认非本批引入；账本已同步至 v0.9.101 PENDING，待 T6 部署与 T7 记忆/技能同升。
