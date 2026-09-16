# LDA 独立率冲刺 · 路径 B-9 扩基报告

- **日期**：2026-09-17
- **版本**：v0.9.89（本地；提交 `10f958f`）
- **批次**：Batch B-9（B153-B168，16 道严格独立锚）
- **冲刺腿**：腿①「扩基加锚」——纯内部确定性扩基，继续稀释 terminal Tier-1 权重，**缓抬独立率天花板**
- **前置闸门**：**同源体检**（用户显式要求，本批首次作为强制第一道闸）
- **结论**：独立率 **87.6%（149/170）→ 88.7%（165/186）**；天花板 **92.9% → 93.5%**；零物理判据改动、零 tol 放宽、零判决行为改动、零新增 CI smoke（CI core 仍 178 条）。

---

## 1. 目标与依据

用户指令（2026-09-17）：「**腿① 续 B-9（最稳，但要先过同源体检）**」。

- terminal Tier-1 = **12 道**（B17/B18/S1-S6/S9-S12），按设计永不升，独立率上限 = (N−12)/N。
- 加 16 道 ⇒ (186−12)/186 = **93.5%**（B-8 为 92.9%）。
- 关键纪律：**only 真 strict 才抬指标**。新锚若落成 `self_certified`，会被棘轮 `MAX_SELF_CERTIFIED=18`（只减不增）直接拦死。故本批 16 道全部按「精确闭式/超越方程根 golden × 方法学不同源真实数值法」范式构造，逐道过 C1–C5 + 判据 D。

---

## 2. 🔴 同源体检（本批新增的强制第一道闸）

### 2.1 闸门定义

B-8 轮立的纪律：**新族 golden 必须与既有 170 道锚的「方程 / 本征值问题 / 数值特殊函数」不同源**，否则只是旧锚换名字（分母虚胖、方法学零增量）。三类同源红线：

1. **数值同源**——同一特殊函数零点（如 Bessel J₀ 零点、Airy 零点、球 Bessel 零点已被占用）；
2. **结构同源**——同一算子的换语境（如 Landau 能级 ≡ 1D 平移谐振子）；
3. **golden 本身是截断近似式**——残差被 golden 误差主导 ⇒ 判据 D 不成立（如 x⁴ 微调谐 golden 为微扰级数）。

### 2.2 机械盘点（既有 170 道锚用到的特殊函数/算子）

| 类别 | 已被占用 |
|---|---|
| Bessel | J₀/J 零点（B98/B99 圆波导）、J/Y 交叉积（B141-B144 圆环）、修正 Bessel |
| 正交多项式 | Legendre/连带 Legendre（B105-B110 刚性转子）、Laguerre（氢径向）、Hermite（3D-HO） |
| 超越方程 | tan/cot 匹配（B16/B145-B148）、Koch 色散、Marcatili |
| 其他 | erf、Airy 零点（B115-B117）、球 Bessel 零点（B118-B120） |
| **未被占用** | **Jacobi 多项式、超几何函数、四阶 ODE、含磁场哈密顿量** |

### 2.3 被否候选（体检记录）

| 候选族 | 处置 | 依据 |
|---|---|---|
| **2D 量子圆盘（Bessel J 零点）** | ❌ 否 | `X_01=2.40483` / `X'_01=3.83171` ≡ **B-5 圆波导 B98/B99 数值同源**（同一数学常数换物理标签）。 |
| **Landau 能级（ℏω_c(n+½)）** | ❌ 否 | 可分离为 1D 平移谐振子 ⇒ **≡ 1D HO FD 结构同源**（B-1/B-5 已覆盖）。 |
| **非谐振子 x⁴ 微扰** | ❌ 否 | 无精确闭式，golden 只能取**截断微扰级数** ⇒ 残差被 golden 误差主导。 |

### 2.4 通过体检的四族（全部为**精确闭式/超越方程根**）

| 族 | 新意在何处（与既有 170 道均不同源） |
|---|---|
| **A. Euler-Bernoulli 等截面梁横向振动** | **全新算子阶数**——既有无任何四阶 ODE 锚（全是一/二阶）；golden 是超越方程 `cos(βL)cosh(βL)=1` 根。 |
| **B. Hulthen 势 3D s-wave 束缚态** | **指数屏蔽 Coulomb**（非 1/r、非 sech²）；golden 走超几何/Jacobi 解，而 Jacobi 多项式在既有无占用。 |
| **C. Fock-Darwin 2D 量子点（抛物约束 + 垂直磁场）** | **含磁场哈密顿量**（新算子项：Ω=√(ω₀²+ω_c²/4)≠ω₀，且 L_z 项 (ℏω_c/2)m 打破简并）。 |
| **D. Rosen-Morse II 势（sech² + tanh）** | 含**奇宇称 tanh 项**（B→0 才退化为 Pöschl-Teller）；本批 B=0.4 eV≠0 ⇒ golden 多出 −β²/(4b_n²) 项，**非同一本征值问题**。 |

四族闭式均经 WebSearch 独立核实（Hulthen s-wave 式、Rosen-Morse II 式、Fock-Darwin 式）。

**额外自证完整性凭据（族 B）**：Hulthen 势在 `a→∞` 极限应还原氢原子 1s ⇒ 本模块内做极限自检，实测 `E₁ = −13.605691 eV` vs 氢 1s `−13.605692 eV`（**差 7.2e-7**）⇒ 闭式实现可信。

---

## 3. 设计范式（同 B-1..B-8）

每道锚 = 一个**确定性解析闭式/超越方程根** 对拍 一个**方法学不同源的真实数值法**：

- 残差 = **离散化误差**（持久、随参数变化、判据 D 响应、反向扰动 FAIL）；
- **不是**代数恒等（B28 血案）、**不是**纯数值误差沉底（B10 血案）；
- 数值核纯 numpy/scipy（C 级自主，零商业依赖）：`lda/lda_harness/_batch_b9_numeric.py`。

🔴 **本批前置纪律（承接 B-5..B-8 血案 + 本批新血案见 §6）**

1. 全批**弃用** `scipy.linalg.eigh(subset_by_index=...)`——三对角问题统一 `eigh_tridiagonal(select='a')`（**全谱**、升序）；族 A 用 **Hermite 梁单元 FEM** 的整维稠密广义本征 `eigvalsh(Kf, Mf)`。
2. **弃用 ARPACK `eigsh`**：梁本征量级 ~1e24（h⁻⁴ 放大）下 `which='SA'` 实测 **30001 次迭代 0/8 不收敛**。
3. 势能项**先核单位**（B-6 三角阱漏乘 e 血案）：B/eV 一律先 `*EV` 转焦耳；族 A 频率出口 MHz。
4. **`default_params` 键集必须 ⊆ golden 形参集**（B-7 血案）：态指标（n/n_r/m）收在候选工厂硬编码里，golden 只收 1~3 个标量物理参数。
5. **径向 FD 原点采样体检**（本批新增）：首节点 r₁=h 处 |V(r₁)| 可能 ≫ 动能 t=ℏ²/(2mh²) ⇒ 「格点伪态」抢走最低本征。判据 `t ≫ |V(r₁)|`；本批族 B 取 h=5e-13 m ⇒ t/|V(r₁)| ≈ 8.7，氢 B89-B94 实测 ≈26，均安全。

---

## 4. 四族物理锚（B153-B168）

| 锚 | 物理对象 | golden（解析闭式/超越方程） | 候选（数值法） | tol |
|---|---|---|---|---|
| B153–B156 | **固支-固支 Si 微梁**（E=169 GPa、ρ=2330、b=1 µm、h=0.5 µm、L=5 µm）第 1–4 阶横向振动 | `cos(βL)cosh(βL)=1` 第 n 根 ⇒ f_n=(β_nL)²/(2πL²)·√(E·I/(ρ·A))，I=bh³/12 | **Hermite 梁单元 FEM**（固支，Ne=200）广义本征 K v=μ M v | 0.01 MHz |
| B157–B160 | **Hulthen 势 3D s-wave**（V₀=0.5878 eV、a=1.5277 nm、β²=36）第 1–4 束缚态 | E_n=−V₀[(β²−n²)/(2nβ)]²，β²=2mV₀a²/ℏ² | 3D 径向 FD 本征（ℓ=0，h=5e-13 m，R=12 nm） | 0.01 eV |
| B161–B164 | **Fock-Darwin 2D 量子点**（m*=0.067m₀、ℏω₀=5 meV、B=5 T）(0,2)/(0,3)/(0,4)/(1,2) | ε=ℏΩ(2n_r+\|m\|+1)−(ℏω_c/2)m，Ω=√(ω₀²+ω_c²/4)，ω_c=eB/m* | 2D 径向 FD 本征（ν=\|m\|，V=½m*Ω²r²）+ L_z 项**解析本征**（严格对角，非近似） | 0.01 meV |
| B165–B168 | **Rosen-Morse II 势**（C=4 eV、B=0.4 eV、α⁻¹=1 nm）第 0–3 态 | b_n=√(γ+¼)−n−½、a_n=−β/(2b_n)、E_n=−(ℏ²α²/2μ)(a_n²+b_n²) | 1D FD 本征（x∈(−12,+12) nm Dirichlet，N=20000） | 0.01 eV |

**接线四件套**（同 B-5..B-8）：

1. `lda/lda_harness/benchmarks.py`：import + B153-B168 字典（`golden_fn` 引函数对象、`candidate` 引注册串）+ `BENCHMARK_ORDER` 追加；
2. `lda/lda_harness/golden.py`：import + `_GOLDEN_DISPATCH` + `_PHYSICAL_LAW`（**双表同登铁律**）；
3. `lda/lda_harness/verification_adapters.py`：`_get_batch_b9()` 双路兜底 + 16× `@_register_candidate`；
4. `lda/lda_harness/_batch_b9_numeric.py`：数值核。

---

## 5. 验证证据（真实 harness 路径）

走 `build_harness_specs` + `BENCHMARK_CANDIDATES` + `IndependentCandidateRouter`（即对外 `verified` 所指同源路径）逐道核对四项：

| 锚 | 分类 | golden | cand | \|cand−golden\| | 单位 | 余量×（tol/残差） |
|---|---|---|---|---|---|---|
| B153 | strict_independent | 175.087305682 | 175.087305922 | 2.401e-07 | MHz | 41647.6 |
| B154 | strict_independent | 482.634900216 | 482.634901352 | 1.137e-06 | MHz | 8797.7 |
| B155 | strict_independent | 946.157378379 | 946.157386005 | 7.626e-06 | MHz | 1311.3 |
| B156 | strict_independent | 1564.046208986 | 1564.046236650 | 2.766e-05 | MHz | 361.5 |
| B157 | strict_independent | −5.001359445 | −5.001175878 | 1.836e-04 | eV | **54.5** |
| B158 | strict_independent | −1.045219323 | −1.045207938 | 1.138e-05 | eV | 878.4 |
| B159 | strict_independent | −0.330739403 | −0.330737233 | 2.170e-06 | eV | 4608.0 |
| B160 | strict_independent | −0.102097677 | −0.102097063 | 6.137e-07 | eV | 16294.9 |
| B161 | strict_independent | 11.183271146 | 11.183270164 | 9.824e-07 | meV | 10179.1 |
| B162 | strict_independent | 13.471132224 | 13.471131370 | 8.540e-07 | meV | 11710.2 |
| B163 | strict_independent | 15.758993302 | 15.758992663 | 6.390e-07 | meV | 15648.8 |
| B164 | strict_independent | 24.398369127 | 24.398365432 | 3.696e-06 | meV | 2705.9 |
| B165 | strict_independent | −3.639226624 | −3.639226928 | 3.041e-07 | eV | 32883.8 |
| B166 | strict_independent | −2.936391409 | −2.936392720 | 1.311e-06 | eV | 7627.1 |
| B167 | strict_independent | −2.310849968 | −2.310852809 | 2.840e-06 | eV | 3520.7 |
| B168 | strict_independent | −1.763295935 | −1.763300328 | 4.392e-06 | eV | 2276.8 |

**16/16 全部 `strict_independent`，diff 全非零，全部 within tol**。worst-case 残差 = B157 的 1.836e-04 eV（占 tol 窗口 ~1.8%），留 **~54× 余量**（B-4..B-8 各批最小余量依次 2×、5×、16×、20×、67×，本批 54× 居中）。

判据 D 参数（golden 与 cand 双向 ×1.1 同步偏移）：族 A `L_um×1.1`、族 B `V₀×1.1`、族 C `B_T×1.1`、族 D `B_eV×1.1` —— 均响应（16/16 OK）。

---

## 6. 诚实边界与血案（本批 5 条）

1. **🔴 ARPACK `eigsh(which='SA')` 不收敛（族 A 首次落地即踩）**：梁本征量级 ~1e24（4 阶算子 h⁻⁴ 放大），`scipy.sparse.linalg.eigsh` 实测 **30001 次迭代、0/8 收敛**（`ArpackNoConvergence`）。**处置**：大尺度问题一律走 LAPACK（族 A 最终用稠密广义本征）。
2. **🔴 4 阶中心差分条件数病态（族 A 最大血案）**：4 阶算子 λ∝n⁴、cond~N⁴ ⇒ **加密网格残差反升**——实测 N=4000 时 B153 残差 0.092 MHz、**N=12000 时反而恶化到 5.17 MHz**（B154/B155/B156 同步超标）。**处置**：改 **Hermite 梁单元 FEM**（离散化 ∈ O(h⁴) 且条件数良好），Ne 扫描 {20,50,100,200,400,800} 取 **Ne=200**（4 阶模态残差 2.4e-7/1.1e-6/7.6e-6/2.8e-5 MHz，单调收敛）。**未放宽 tol**。
3. **🔴 Hermite 质量阵符号错误（族 A 插曲）**：初版装配时把标准一致质量阵的 `+54 / +13le` 误写成 `−54 / −13le` 且非对称 ⇒ `eigvalsh` 只读单三角 ⇒ 4 阶模态**整体偏大 1.4349×**（B153 251.23 vs 175.09）。**处置**：对照标准 Hermite 质量阵订正（`[156, 22l, 54, −13l; 22l, 4l², 13l, −3l²; 54, 13l, 156, −22l; −13l, −3l², −22l, 4l²]`）。
4. **🔴 Hulthen 参数标定血案（族 B）**：能量公式乘的是 **V₀**（不是 ℏ²/2ma²）。初版误用后者（V₀=20 eV、a=0.4365 nm）⇒ β²=100 档算出 **E₁=−490 eV**（深束缚、波函数压到 0.009 nm）⇒ 网格分辨率不足、**残差 0.41 eV**。**处置**：改 ℏω₀ 标定法 `V₀=ℏ²/(2ma²β²)`（a=1.5277 nm、β²=36 ⇒ V₀=0.5878 eV、E₁=−5.0 eV），残差降至 1.836e-4 eV（54.5×）。
5. **🔴 Fock-Darwin 质量参数漏传血案（族 C）**：`_radial2d_evals` 初版硬编码电子质量 ⇒ m*=0.067m₀ 下本征偏低 **~4×**（B161: golden 11.18 vs cand −3.51 meV）。**处置**：求解器补 `mass` 形参，族 C 传 `mass=_MSTAR`。

**其他诚实边界**：
- 族 A 的 FEM 残差在 Ne>200 后回落（Ne=800 时首阶 8.0e-4 MHz）——属稠密装配舍入累积，非物理；取 **Ne=200** 为跨 4 阶模态的最优平衡点（判据 D 仍响应）。
- 族 A 只验证**固支-固支**工况（`cos·cosh=1` 与自由-自由同式，rigid-body 模态未纳入）；梁材料参数为 Si 典型值（非特定 PDK），属**方法学锚**不构成流片精度承诺。

---

## 7. 计数护栏（七道全绿）

| 护栏 | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke.py`（README / CONTRIBUTING / ledger docstring 三面同步） | OK（6 tests） |
| `run_count_consistency_smoke.py`（引擎/包/题库/CI core） | OK（11 tests） |
| `run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点） | 4/4 PASS（165/3/18） |
| `run_self_certified_lock_smoke.py`（棘轮 ≤18 + 锁原因） | 4/4 PASS（`{t2_blocked:6, terminal_tier1:12}`） |
| `run_maturity_baseline_smoke.py`（VMM 底线 6 条） | PASS（M5 口径 165/3/18，和=186） |
| `run_webui_verification_ledger_smoke.py`（端点 + 前端接线） | 15 PASS / 0 FAIL |
| `run_statistical_anchor_smoke.py`（题库计数 + 统计一致性） | 33 PASS / 0 FAIL（题库已加 `range(153,169)`） |

另跑 `run_d_criterion_smoke.py`（判据 D 基线残差普查含 16 道新锚）与 `run_benchmark_falsifiability_smoke.py`（反向扰动必 FAIL）——**B-9 自身新增项全 PASS，但两者各暴露一条既有红灯，见 §7.1**。

---

## 7.1 🔴 诚实披露：两道 core smoke 的**既有红灯**（经基线对照确证**非 B-9 引入**）

`run_d_criterion_smoke.py` 与 `run_benchmark_falsifiability_smoke.py` 在本批结束后**各有一条 FAIL**。为区分「B-9 引入」与「既有」，用 `git worktree` 在**改动前的 HEAD `0e7343e`（v0.9.88 / 170 锚）**上原样复跑这两个 smoke 对照：

| smoke 判据 | 基线 `0e7343e`（170 锚） | 本批 v0.9.89（186 锚） | 判定 |
|---|---|---|---|
| 判据 D ③ 基线残差全部 > 1e-12 | ❌ FAIL：B65-B68/B73/B74/B79/B81-B84/B87/B88（13 道，**全为 Batch B-4 切片转移矩阵锚**，默认参数下候选≡闭式到机器精度） | ❌ **同一 13 道、残差逐位一致** | **既有问题** |
| 判据 D ③ 已接线候选全登记（动态） | ✅ 149/149 | ✅ **165/165** | B-9 通过 |
| 可证伪 ⑨ 路径② 报告可 JSON 序列化 | ❌ FAIL：`TypeError: Object of type bool is not JSON serializable`（numpy bool 经 `_cmp_ok` 的 `<=` 泄漏进 `BenchmarkResult.passed`） | ❌ **同一报错** | **既有问题** |
| 可证伪 全量锚无回归 | ✅ 170/170 | ✅ **186/186** | B-9 通过 |
| 可证伪 反向扰动 10% 必 FAIL | ✅ | ✅ | B-9 通过 |
| 可证伪 对外账本三分类一致 | ✅ 149/3/18 | ✅ **165/3/18** | B-9 通过 |
| 可证伪 路径② 口径 ≡ 路径① | ✅ | ✅ | B-9 通过 |

**复现方法**（第三方可独立复核）：`git worktree add <dir> 0e7343e`，在基线树跑这两个 smoke，输出与上表左列逐字一致（日志对照：基线 `_b9_base_dcrit.txt` vs 本批 `_b9_dcrit.txt`）。

**结论**：**B-9 零新回归**。上述两条红灯须**单独立项**修复，本批**未修**（超范围，且会触碰 B-4 锚的 golden/参数，违反「不做超范围改动」纪律）：
1. **B-4 锚默认参数落在「候选 ≡ 闭式」的过度收敛档**（B65-B88 默认参数下切片转移矩阵与解析闭式到 1e-16 一致）⇒ 需换到未收敛参数点（判据 D 双向标定铁律）或重构该批判据；
2. **`BenchmarkResult.passed` / `independent` 出口未做 `bool()` 归一化** ⇒ numpy 标量经比较算子泄漏为 `np.bool_`，`json` 序列化崩（与 v0.9.17 B24 / v0.9.24 B10 同根，**第三次复发**）。🔴 **本批已精确定位泄漏源（8 道锚的 golden 返回 `np.float64`）**：`B70, B71, B79, B80, B88`（Batch B-4）+ `B115, B116, B117`（Batch B-6）——其 `golden_fn` 返回 numpy 标量 ⇒ `abs(np.float64 − float) <= tol` 得 `np.bool_` ⇒ `passed` 非 JSON 可序列化。修复只需在 golden 出口 `float()` 或 `_cmp_ok` 返回 `bool(...)`。

---

## 7.2 🔴 补充披露：第三道既有红灯（覆盖死角闭合护栏）

同法对照基线，`run_coverage_deadzone_closure_smoke.py` 亦为**既有红灯**（基线 `0e7343e` 同样 31 PASS / 2 FAIL，逐字一致）：

| 判据 | 基线 | 本批 | 判定 |
|---|---|---|---|
| `B5` 仍为自证桩（名义守则桩，不被升格） | ❌ FAIL（`class=strict`） | ❌ **同一 FAIL（`class=strict`）** | **既有问题** |
| `B6` 仍为自证桩（名义守则桩，不被升格） | ❌ FAIL（`class=strict`） | ❌ **同一 FAIL（`class=strict`）** | **既有问题** |
| 其余 31 条（含 2 条反向测试） | ✅ | ✅ | 一致 |

**根因**：B5/B6 已于 **v0.9.81（P1-1 B567）升 Tier-3 严格独立**（见 `benchmarks.py::_VMM_OVERRIDES`），但本 smoke 仍断言「B5/B6 仍是自证桩」⇒ 期望值**陈旧未同步**（自 v0.9.81 起即红），与 B-9 无关。

### 7.1/7.2 小结：本批的 red 清单

| # | core smoke | 判据 | 根因 | 与 B-9 关系 |
|---|---|---|---|---|
| 1 | `run_d_criterion_smoke.py` | ③ 基线残差 > 1e-12 | B-4 锚（B65-B88）默认参数过度收敛 | 无 |
| 2 | `run_benchmark_falsifiability_smoke.py` | ⑨ 路径② JSON 可序列化 | 8 道锚 golden 返回 `np.float64`（B70/71/79/80/88/B115/116/117） | 无 |
| 3 | `run_coverage_deadzone_closure_smoke.py` | B5/B6 仍为自证桩 | 期望值陈旧（B5/B6 于 v0.9.81 升 strict） | 无 |

⚠️ 因此 README/CONTRIBUTING 中「CI core 178 条」为**条数账本**（条数不变、由计数护栏守护）；其**全绿性**在上述三条红灯上**不成立**——此为**如实披露**，不作绿，并建议**单开一个「core smoke 既有红灯清算」专项**统一修复（三条各自独立、互不耦合）。

---

## 8. 账本变更

| 项 | 变更前 | 变更后 |
|---|---|---|
| 版本 | v0.9.88 | **v0.9.89** |
| 严格独立 | 149 | **165** |
| 降级量级参考 | 3 | 3 |
| 自证桩 | 18 | 18（棘轮 ≤18 保持） |
| 题数 N | 170 | **186** |
| 独立率 | 87.6% | **88.7%** |
| 天花板 | 92.9% | **93.5%** |
| B 题数 | 147（B1-B152） | **163（B1-B168）** |
| CI core | 178 | 178（不变） |

---

## 9. 提交与推送

- commit：`10f958f`
- push：`scripts/sync_push.py`（gitee 直连 + github 直连→SOCKS5 兜底）
- **部署**：本次**未部署**（用户指令不含「部署」）——完成时报备询问；如需上线：`remote_deploy.py --expect-head 10f958f`。

---

## 10. 下一步候选

- **腿①续（B-10）**：仍最稳——继续选**已过同源体检**的新物理族。候选方向（须先体检，勿直接开工）：
  - 1D 双势阱隧道分裂（超越方程 / 半经典分裂式）；
  - 球壳量子点（球 Bessel + Neumann **交叉积**零点 —— 注意与 B141-B144 的圆柱 Bessel 交叉积区分）；
  - 指数势 V₀e^{−x/a} 束缚态（Bessel 函数谱）；
  - 有限深 2D 方阱（tan/cot 二维匹配 —— 注意与 B16/B145-B148 的 1D/3D 区分）。
  - 🔴 **前置「同源体检」已升为批次第一道闸**，未过不得开工。
- **腿②degraded 3→strict**：纯内部，存量已明确（E10 余量 ~28×最有望先回）。
- **腿③T2 解锁 6 道**：外部 KPI 阻塞（E1/E3-E7），需 MPW 实测回流。
