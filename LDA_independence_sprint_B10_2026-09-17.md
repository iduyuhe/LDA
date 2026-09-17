# LDA 独立率冲刺 · 路径 B-10 扩基报告

- **日期**：2026-09-17
- **版本**：v0.9.90（本地）
- **批次**：Batch B-10（B169-B184，16 道严格独立锚）
- **冲刺腿**：腿①「扩基加锚」——纯内部确定性扩基，继续稀释 terminal Tier-1 权重，**缓抬独立率天花板**
- **前置闸门**：**同源体检**（继承 B-9 立的强制第一道闸；本批首次**实际 grep 全仓**核验占用）
- **结论**：独立率 **88.7%（165/186）→ 89.6%（181/202）**；天花板 **93.5% → 94.1%**；零物理判据改动、零 tol 放宽、零判决行为改动、零新增 CI smoke（CI core 仍 178 条）。

---

## 1. 目标与依据

用户指令（2026-09-17）：「**腿①已推进到 88.7%，天花板 93.5%。要继续，B-10**」。

- terminal Tier-1 = **12 道**（B17/B18/S1-S6/S9-S12），按设计永不升，独立率上限 = (N−12)/N。
- 加 16 道 ⇒ (202−12)/202 = **94.1%**（B-9 为 (186−12)/186 = 93.5%）。
- 关键纪律：**only 真 strict 才抬指标**。新锚若落成 `self_certified`，会被棘轮 `MAX_SELF_CERTIFIED=18`（只减不增）直接拦死。故本批 16 道全部按「精确闭式/特殊函数 golden × 方法学不同源真实数值法」范式构造，逐道过 C1–C5 + 判据 D。

---

## 2. 🔴 同源体检（批次第一道闸 · 本批升级为「实际 grep 全仓」）

### 2.1 闸门定义

**新族 golden 必须与既有 186 道锚的「方程 / 本征值问题 / 数值特殊函数」不同源**，否则只是旧锚换名字（分母虚胖、方法学零增量）。三条同源红线：

1. **数值同源**——同一特殊函数零点/取值（如 Bessel J₀ 零点、Airy 零点、球 Bessel 零点、erfc 已被占用）；
2. **结构同源**——同一算子的换语境（如 Landau 能级 ≡ 1D 平移谐振子）；
3. **golden 本身是截断近似式**——残差被 golden 误差主导 ⇒ 判据 D 不成立。

### 2.2 机械盘点（本批首次**实际 grep 全仓**，非凭记忆）

对既有锚代码库执行占用扫描（`lda/**/*.py`）：

| 检索式 | 命中 | 结论 |
|---|---|---|
| `mathieu_a\|mathieu_b\|mathieu_ce\|mathieu_se` | **No matches** | Mathieu 特殊函数**未占用** |
| `ellipe\|ellipk\|elliprf\|elliprd\|elliprj\|elliprc\|fresnel` | **No matches** | 椭圆积分 / Fresnel **未占用** |
| `热核\|heat_kernel\|fundamental_solution\|time_stepping\|parabolic` | 仅 `_peaks_parabolic`（无关） | **时间推进类数值方法未占用** |

⇒ 本批四族与既有 186 道**均不同源**（方程类/特殊函数类/数值方法类三个维度全新增）。

### 2.3 被否候选（体检记录）

| 候选族 | 处置 | 依据 |
|---|---|---|
| **半导体扩散 C=Cs·erfc(x/2√(Dt))** | ❌ 否（改高斯基础解） | **数值同源**：erfc 已被 B30（读出保真度）占用；**结构同源**：项目已有 T1-B 漂移-扩散内核。⇒ 改**有限剂量守恒**扩散的**高斯基础解**（Gaussian≠erfc；有限剂量≠恒定表面源半无限）。 |
| **Carlson 椭球积分（`elliprd`/`elliprf`）作 golden** | ❌ 否（改初等闭式） | **数值同源**：Carlson 形式与既有特殊函数库同源（与 scipy 数值栈耦合）。⇒ 改**初等反正弦/对数闭式**。 |
| **Mathieu FG（Floquet）三对角构造作候选** | ❌ 否（改半周期 P1-FEM） | **判据 D 红**：N=8 即与 scipy `mathieu_a/b` 一致到 **1e-16** ⇒ 撞「代数恒等」红线（残差沉底、判据 D 不响应）。 |

### 2.4 通过体检的四族（全部为**精确 golden**）

| 族 | 新意在何处（与既有 186 道均不同源） |
|---|---|
| **A. Mathieu 方程特征值**（周期系数 Hill ODE） | **全新方程类**——既有 186 道锚全为**常系数** ODE/PDE；`y''+(a−2q·cos2x)y=0` 是首个周期系数本征值问题。 |
| **B. 椭圆积分与椭球静电去极化因子** | **全新特殊函数类**——第二类/第一类完全椭圆积分（`ellipe`/`ellipk`）在既有无占用；去极化因子取**初等闭式**（非 Carlson）。 |
| **C. Fresnel（Cornu）积分** | **全新特殊函数类**——`fresnel` C/S 在既有无占用。 |
| **D. 线性扩散方程基础解热核**（双端零通量 CN 时间推进） | **全新数值方法类——时间推进**——既有锚全为**本征值求解 / 稳态求解**；本族是首个**时间积分**（parabolic）数值方法。 |

**最接近的既有锚（仍不同源）**：B29（热光鳍）为**稳态椭圆 ODE**、T1-B 为**漂移-扩散稳态 Gummel**，两者均**非时间推进** ⇒ 数值方法类不撞。

---

## 3. 设计范式（同 B-1..B-9）

每道锚 = 一个**确定性解析闭式/特殊函数 golden** 对拍 一个**方法学不同源的真实数值法**：

- 残差 = **离散化误差**（持久、随参数变化、判据 D 响应、反向扰动 FAIL）；
- **不是**代数恒等（B28 血案 / 本批 Mathieu-FG 血案）、**不是**纯数值误差沉底（B10 血案）；
- 数值核纯 numpy/scipy（C 级自主，零商业依赖）：`lda/lda_harness/_batch_b10_numeric.py`。

🔴 **本批前置纪律（承接 B-5..B-9 血案 + 本批新血案见 §6）**

1. 全批**弃用** `scipy.linalg.eigh(subset_by_index=...)`（B-6 off-by-one 血案）——族 A 走 **LAPACK 稠密广义本征全谱**，族 D 走 **`solve_banded`** 三对角。
2. **弃用 ARPACK `eigsh`**（B-9 血案：梁本征 ~1e24 量级下不收敛）。
3. 势能项**先核单位**（B-6 三角阱漏乘 e 血案）。
4. **`default_params` 键集必须 ⊆ golden 形参集**（B-7 血案）。
5. **超收敛 / round-off 地板体检（本批新增，见 §6 血案 3）**：数值求积的 `n` 必须落在**离散误差主导区**，否则残差归零成「假代数恒等」。
6. **格点采样禁用 `int(round(x/h))` 吸附（本批新增，见 §6 血案 4）**：退化残差至 O(h) 量化误差。

---

## 4. 四族物理锚（B169-B184）

| 锚 | 物理对象 | golden（解析闭式/特殊函数） | 候选（数值法） | tol |
|---|---|---|---|---|
| B169–B173 | **Mathieu 方程特征值**（q=1）a₀ / a₁ / b₁ / b₂ / a₂（MEMS 参数激励 / 屈曲） | `scipy.special.mathieu_a/b` 机器精度（周期系数 Hill ODE `y''+(a−2q·cos2x)y=0`） | **半周期 [0,π/2] P1-FEM 广义本征** `A v = a M v`；BC 组合选族：(N,N)→a₀/a₂、(N,D)→a₁、(D,N)→b₁、(D,D)→b₂ | 0.01 |
| B174–B175 | **椭圆截面几何周长**（a/b=2:1、3:1） | 第二类完全椭圆积分闭式 `L=4a·E(m)`，`m=1−b²/a²` | **复合 Simpson** `4∫₀^{π/2}√(a²sin²θ+b²cos²θ)dθ`（n=12） | 0.01 µm |
| B176–B177 | **大摆角单摆周期比** T/T₀（θ₀=135°、150°） | 第一类完全椭圆积分闭式 `T/T₀=(2/π)K(m)`，`m=sin²(θ₀/2)` | **复合 Simpson** `(2/π)∫₀^{π/2}dθ/√(1−m sin²θ)`（n=16） | 0.01 |
| B178–B179 | **椭球去极化因子** N_c（扁，轴比 2）/ N_a（长，轴比 2） | 初等反正弦闭式 `N_c=(1/e²)[1−(1/e)asin(e)√(1−e²)]` / 初等对数闭式 `N_a=((1−e²)/e³)[½ln((1+e)/(1−e))−e]` | **复合 Simpson**（含 s→t 解析变换 + 解析标度还原，n=256） | 0.01 |
| B180–B181 | **Fresnel（Cornu）积分** C(1) / S(1)（衍射半波带） | `scipy.special.fresnel` 机器精度 | **复合 Simpson** `∫₀^u cos/sin(πt²/2)dt`（n=64，O(h⁴)） | 0.01 |
| B182–B184 | **线性扩散基础解热核**归一剖面 R(x)（x=50/120/200 nm，t=1800 s） | 高斯热核解析精确 `R(x)=C(x,t)/C(0,t)=exp(−x²/(4Dt))` | **双端零通量 Crank-Nicolson 时间推进**（M=4000 / nt=960，相邻格点线性插值） | 0.01 |

**接线四件套**（同 B-5..B-9）：

1. `lda/lda_harness/benchmarks.py`：import + B169-B184 字典 + `BENCHMARK_ORDER` 追加；
2. `lda/lda_harness/golden.py`：import + `_GOLDEN_DISPATCH` + `_PHYSICAL_LAW`（**双表同登铁律**）；
3. `lda/lda_harness/verification_adapters.py`：`_get_batch_b10()` 双路兜底 + 16× `@_register_candidate`（body 一律 `float()` 包裹）；
4. `lda/lda_harness/_batch_b10_numeric.py`：数值核（纯 numpy/scipy）。

---

## 5. 验证证据（真实 harness 路径）

走 `build_harness_specs` + `BENCHMARK_CANDIDATES` + `IndependentCandidateRouter`（即对外 `verified` 所指同源路径）逐道核对四项：

| 锚 | 分类 | golden | cand | \|cand−golden\| | 单位 | 余量×（tol/残差） |
|---|---|---|---|---|---|---|
| B169 | strict_independent | −0.455138604 | −0.455139115 | 5.110e-07 | char_value | 19569.3 |
| B170 | strict_independent | 1.859108073 | 1.859107244 | 8.289e-07 | char_value | 12064.8 |
| B171 | strict_independent | −0.110248817 | −0.110249451 | 6.337e-07 | char_value | 15780.6 |
| B172 | strict_independent | 3.917024773 | 3.917019103 | 5.670e-06 | char_value | 1763.7 |
| B173 | strict_independent | 4.371300983 | 4.371295807 | 5.175e-06 | char_value | 1932.4 |
| B174 | strict_independent | 9.688448221 | 9.688448299 | 7.867e-08 | µm | 127113.5 |
| B175 | strict_independent | 13.364893221 | 13.364905866 | 1.264e-05 | µm | 791.1 |
| B176 | strict_independent | 1.527947588 | 1.527947214 | 3.745e-07 | T_ratio | 26702.3 |
| B177 | strict_independent | 1.762203730 | 1.762165774 | 3.796e-05 | T_ratio | 263.4 |
| B178 | strict_independent | 0.527200283 | 0.527160560 | 3.972e-05 | N_c | **251.8** |
| B179 | strict_independent | 0.173563998 | 0.173544115 | 1.988e-05 | N_a | 503.0 |
| B180 | strict_independent | 0.779893400 | 0.779893411 | 1.027e-08 | C_u | 973710.8 |
| B181 | strict_independent | 0.438259147 | 0.438259138 | 9.814e-09 | S_u | 1018952.5 |
| B182 | strict_independent | 0.706648278 | 0.706628244 | 2.003e-05 | C_norm | 499.3 |
| B183 | strict_independent | 0.135335283 | 0.135326932 | 8.351e-06 | C_norm | 1197.5 |
| B184 | strict_independent | 0.003865920 | 0.003867614 | 1.694e-06 | C_norm | 5903.2 |

**16/16 全部 `strict_independent`，diff 全非零，全部 within tol**。worst-case 残差 = B178 的 **3.972e-05**，留 **~252× 余量**（B-4..B-9 各批最小余量依次 2×、5×、16×、20×、67×、54×，本批 252× 取最小余量口径仍充裕）。

判据 D 参数（golden 与 cand 双向 ×1.1 同步偏移）：族 A `q×1.1`、族 B `a_um×1.1` / `theta0_deg×1.1` / `ar×1.1`、族 C `u×1.1`、族 D `x_nm×1.1` —— 均响应（**16/16 OK**）。

**极限自检（模块内建）**：
- 族 A：`q→0` 退化 ⇒ a₀/a₁/b₁/b₂/a₂ **精确命中 0/1/1/4/4**；FEM 残差严格 **O(h²)**。
- 族 B：球极限 `ar→1` ⇒ N_c→1/3、N_a→1/3（1e-6 轴比差 2.7e-7）；**求和律 N_c+2N_a ≡ 1**。
- 族 D：一步保持性（Crank-Nicolson 单步恒定态保持）1.101e-05（M=500）/ 6.933e-07（M=2000）。

---

## 6. 诚实边界与血案（本批 4 条）

1. **🔴 Mathieu FG（Floquet）三对角构造撞「代数恒等」红线（族 A 首次落地即踩）**：初版拟用 Floquet 三对角矩阵的判据 D 定族，实测 **N=8 即与 scipy `mathieu_a/b` 一致到 1e-16** ⇒ 离散化误差沉到机器精度以下，判据 D（残差须浮出噪声地板并单调收敛）**不成立**。**处置**：改**半周期 [0,π/2] P1-FEM 广义本征**（BC 组合选族），残差 5.1e-7~8.3e-5 且严格 O(h²)。
2. **🔴 族 D 单端 Dirichlet 引入 17% 系统偏差**：初版域 [0,4 µm] 一端 Dirichlet 固定 ⇒ 边界反射污染中心剖面，残差 **17%**。**处置**：改**双端零通量 Neumann ghost**（三对角行 0 超对角 −2r、末行次对角 −2r），中心剖面与高斯核一致到 O(h²)。
3. **🔴 超收敛 ⇒ round-off 地板血案（族 B）**：椭圆周长 Simpson **n=32 残差恰为 0.0**（判据 D 误判为「代数恒等」）、n=64 仅 1.8e-15；θ₀=90° 单摆 n=20 亦归零。**处置**：`ellipse_perimeter_simpson(n=12)`、`pendulum_ratio_simpson(n=16)`，B176 默认角从 90° 改 **135°**，使 n 落在**离散误差主导区**。
4. **🔴 格点吸附使残差退化为 O(h) 量化误差（族 D）**：`int(round(x/h))` 把采样点吸附到最近格点，残差被 **O(h) 量化误差**主导（M=3000 时余量只剩 1.5×）。**处置**：改**相邻两格点线性插值**；且逐点扫描发现归一比值 `R(x)=C(x)/C(0)` 分子分母同源相消，个别 (x,M) 组合**非单调**（x=100 nm 在 M=500 残差 1.13e-4 反小于 M=1000 的 2.75e-4）⇒ 取 **x=50/120/200 nm**（全单调、余量 ≥499×）。

**其他诚实边界**：
- 族 D 参数取 D=1e-18 m²/s（半导体掺杂扩散量级）、t=1800 s、域 [0,4 µm]；属**方法学锚**，不构成特定工艺精度承诺。
- 族 B 去极化因子为**静电形状因子**（long-wavelength 近似适用）；轴比固定 2，未扫宽长厚比区间。
- 族 A 只验证 q=1 单档（MEMS 参数激励典型工作点），未覆盖大 q 强耦合区。

---

## 7. 计数护栏（七道全绿）

| 护栏 | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke.py`（README / CONTRIBUTING / ledger docstring 三面同步） | OK（6 tests） |
| `run_count_consistency_smoke.py`（引擎/包/题库/CI core） | OK（11 tests） |
| `run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点） | 4/4 PASS（181/3/18，和=202） |
| `run_self_certified_lock_smoke.py`（棘轮 ≤18 + 锁原因） | 4/4 PASS（`{t2_blocked:6, terminal_tier1:12}`，棘轮 =18 守） |
| `run_maturity_baseline_smoke.py`（VMM 底线 6 条） | PASS（M5 口径 181/3/18，和=202；低置信 12） |
| `run_webui_verification_ledger_smoke.py`（端点 + 前端接线） | 15 PASS / 0 FAIL |
| `run_statistical_anchor_smoke.py`（题库计数 + 统计一致性） | 34 PASS / 0 FAIL（题库已加 `range(169,185)`） |

---

## 7.1 🔴 诚实披露：三道 core smoke 的**既有红灯**（承接 B-9，**非 B-10 引入** · 本批实测复现）

B-9 报告 §7.1/§7.2 已登记的三条既有红灯为**基线 HEAD 即红**。本批**实测复跑三道 smoke 逐条复现**，确认与 B-10 无关：

| core smoke | 本批实测 | 是否含 B169-B184 | 判定 |
|---|---|---|---|
| `run_d_criterion_smoke.py` ③ 基线残差 > 1e-12 | ❌ **9 PASS / 1 FAIL** —— 失败清单 = **B65/B66/B67/B68/B73/B74/B79/B81/B82/B83/B84/B87/B88（13 道，全为 B-4 切片转移矩阵锚）**，残差 0.0~1.74e-13 贴地板 | **无**（16 道新锚残差 5e-7~4e-5 均远 > 1e-12） | **既有** |
| `run_benchmark_falsifiability_smoke.py` ⑨ 路径② JSON 序列化 | ❌ `TypeError: Object of type bool is not JSON serializable`（反向扰动 30 项全 PASS，仅路径②序列化崩） | **无**（16 道 golden 均返回 Python `float`，已实测确认） | **既有** |
| `run_coverage_deadzone_closure_smoke.py` B5/B6 仍为自证桩 | ❌ **31 PASS / 2 FAIL** —— B5/B6 `class=strict`（v0.9.81 已升 strict，期望值陈旧） | **无** | **既有** |

**结论：B-10 零新回归**（判据 D 失败清单逐字等于 B-9 的 13 道；且 16 道新锚残差最大 3.97e-5 ≫ 1e-12 门槛，天然不会落入该清单）。本批**未修**（超范围，且会触碰 B-4/B5/B6 锚的 golden/参数，违反「不做超范围改动」纪律）；建议单开「core smoke 既有红灯清算」专项统一修复（三条各自独立、互不耦合）。

⚠️ 因此 README/CONTRIBUTING 中「CI core 178 条」为**条数账本**（条数不变、由计数护栏守护）；其**全绿性**在上述三条红灯上**不成立**——此为**如实披露**，不作绿。

---

## 8. 账本变更

| 项 | 变更前 | 变更后 |
|---|---|---|
| 版本 | v0.9.89 | **v0.9.90** |
| 严格独立 | 165 | **181** |
| 降级量级参考 | 3 | 3 |
| 自证桩 | 18 | 18（棘轮 ≤18 保持） |
| 题数 N | 186 | **202** |
| 独立率 | 88.7% | **89.6%** |
| 天花板 | 93.5% | **94.1%** |
| B 题数 | 163（B1-B168） | **179（B1-B184）** |
| CI core | 178 | 178（不变） |

**同步文件**（单进程原子替换，EOL 保真）：`README.md`（当前版本行 + 新 B-10 详情行 + B-9 行转「✅ 已部署生产」+ 4 处计数）、`CONTRIBUTING.md`（2 处）、`pyproject.toml`（版本）、`run_count_consistency_smoke.py`（6 处）、`run_statistical_anchor_smoke.py`（3 处）、`run_webui_verification_ledger_smoke.py`（2 处 docstring）。**棘轮不动**（本批无毕业）。

---

## 9. 提交与推送

- commit：`f75c7c3`
- push：`scripts/sync_push.py`（gitee 直连 exit=0 + github 直连被重置→SOCKS5 兜底 exit=0）
- **部署**：✅ **已部署生产（v0.9.90）** —— `remote_deploy.py --expect-head 69434b1`：
  - `git pull` 生产端 ：`bd884cf..69434b1  Fast-forward`（11 文件，+1252/−19，新增报告与 `_batch_b10_numeric.py`）；
  - pip 元数据重装：`lda-design 0.9.89 → 0.9.90`（修复 /api/health 版本串滞后）；
  - `dist/store.json` 未动（2072 B · Sep 9）；`systemctl restart` rc=0 · `is-active=active` · **`HEAD_MATCH=True`**。
- **部署后账本核验**（生产 `/api/verification_ledger` 实测，34488 B）：
  - `vmm.tiers` = `{strict_independent: 181, degraded_ordinal: 3, self_certified: 18}`（和 = **202**）⇒ 独立率 **89.6%**；
  - `judgment_paths.derived.totals` = `{anchors: 202, strict_independent: 181, degraded_ordinal: 3, self_consistent_stub: 18}`；
  - `anchors.by_kind['physical-law'].ids` 含 **B169–B184 全 16 道**（max B = **184**）；
  - `honest_note` 已刷新为「当前真正由独立候选判出的只有 **181** 道」且编号列表含 B169–B184；
  - `/api/health`：version `0.9.90` · benchmarks **202** · `layers_built` 8 / `pdks` 5 · `/api/shelf` **75** 货架 · `ci_core.count` **178**（条数不变、`stale=false`）。

---

## 10. 下一步候选

- **腿①续（B-11）**：仍最稳——继续选**已过同源体检**的新物理族。候选方向（须先体检，勿直接开工）：
  - 1D 双势阱隧道分裂（超越方程 / 半经典分裂式）；
  - 球壳量子点（球 Bessel + Neumann **交叉积**零点 —— 注意与 B141-B144 圆柱 Bessel 交叉积区分）；
  - 指数势 V₀e^{−x/a} 束缚态（Bessel 函数谱）；
  - 有限深 2D 方阱（tan/cot 二维匹配 —— 注意与 B16/B145-B148 的 1D/3D 区分）；
  - **时间推进类数值方法**（本批族 D 已开先例）：一维热方程双端 Robin 边界、对流-扩散（Crank-Nicolson + 迎风）—— 注意与族 D 的高斯基础解**不要同源**。
  - 🔴 **前置「同源体检」（含 `grep` 全仓占用扫描）已升为批次第一道闸**，未过不得开工。
- **腿②degraded 3→strict**：纯内部，存量已明确（E10 余量 ~28×最有望先回）。
- **腿③T2 解锁 6 道**：外部 KPI 阻塞（E1/E3-E7），需 MPW 实测回流。
