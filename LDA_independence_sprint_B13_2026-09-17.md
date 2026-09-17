# LDA 独立率冲刺 · Batch B-13 报告（v0.9.93）

> 生成日期：2026-09-17 · 仓库 `D:/agent_LDA` · 锚库 B1-B232（250 道）。
> **状态**：✅ **已部署生产**（2026-09-17 · `--expect-head 6581e9c` · ledger `229/3/18/250` · `HEAD_MATCH=True`）——本地完成项：选族 / 同源体检 / 数值核 / 真 harness 验证 / 账本同步 / 护栏复跑。

---

## 1. 摘要

| 项目 | B-12 后 | **B-13 后** |
| --- | --- | --- |
| 版本 | v0.9.92 | **v0.9.93** |
| 锚总数 N | 234（B1-B216） | **250（B1-B232）** |
| strict 独立 | 213 | **229** |
| degraded 降级 | 3 | 3（E9/E10/B21，不动） |
| 自证桩 | 18 | 18（棘轮 `MAX_SELF_CERTIFIED=18` 守） |
| **独立率** | 91.0%（213/234） | **91.6%（229/250）** |
| **天花板** | 94.87%（(234−12)/234） | **95.2%（(250−12)/250）** |
| CI core smoke | 178 条 | 178 条（**不变**） |

**结论**：本轮 16 道（B217-B232）全部落 `strict_independent`，四族互不同源（选族前**实际 grep 全仓**核验）。真 harness 路径实测 `build_harness_specs()` = 250 specs、三分类 **229/3/18（和 250）**、B217-B232 **16/16 strict**、`candidate_responds` **16/16 True**。

---

## 2. 选族与同源体检

### 2.1 选族（四族 · 均为全新数值方法类 / 算子类 / 变分类 / 积分方程类）

| 族 | 名称 | 锚 | golden | candidate |
| --- | --- | --- | --- | --- |
| **A** | 分数阶微积分 · Grünwald–Letnikov 数值分数阶导数 | B217-B220 | Riemann–Liouville 初等闭式 `D^α[t^p]=Γ(p+1)/Γ(p+1−α)·t^{p−α}` | GL 卷积差分 `h^{−α}·Σ w_k f(t−kh)`（`w_0=1`、`w_k=w_{k−1}(k−1−α)/k`）——**非局部算子**、O(h) 一阶 |
| **B** | 矩阵指数 scaling–squaring + 截断 Taylor | B221-B224 | `−sin t` / `−sin(2.5t)` / `e^{−t}` / `2e^{−t}−e^{−2t}` | `[Σ_{k≤n}(At/2^s)^k/k!]^{2^s}`（s=8） |
| **C** | 变分极值 · 固定步长梯度下降 | B225-B228 | `−a/4` / `2√a` / `−e^{b−1}` / `c−c·ln c` | `x_{k+1}=x_k−η·f′(x_k)` 迭代 k 步后取 `f(x_k)` |
| **D** | 第二类 Volterra 积分方程 · 分块梯形递推 | B229-B232 | `[1−λe^{−(1−λ)x}]/(1−λ)` / `[2−λe^{−(2−λ)x}]/(2−λ)` / `cosh(√λ·x)` | 均匀网格 `h=x/n` 分块梯形（含 `k=j` 隐式项移项后前向递推）——O(h²) |

**定档**：A `n=3200`；B `n=3`；C `k=12`；D `n=1024`。**统一 tol=0.01**（诚实、未放宽）。

### 2.2 同源体检（三条红线 · **实际 grep 全仓**，非凭记忆）

**① 数值同源（已占用特殊函数）**：`ai_zeros`（B-6 三角阱 Airy 零点）、`jv/yv/spherical_jn/yn`（B-5 圆波导 / B-8 2D 类氢 / Mie）、`voigt_profile`（B-11）、`mathieu_a/b`（B-10）、`hypergeom`+`roots_jacobi`（B-12）、`elliprd/elliprf`（B-10 被否）、`erfc`/`gamma` 族（B30）。
**全仓 grep 命中**：`fredholm|volterra|nystrom|积分方程|grunwald|caputo|fractional|矩阵指数|scaling_squaring|expm|talbot|stehfest|inverse_laplace|sor_iter|gauss_seidel|solve_poisson|pade|collocation` ⇒ **No matches**（限定 `lda/` 重扫，排除 `lda_cuda_venv`/`node_modules` 第三方噪声）。

**② 结构同源（已占用方程 / 数值方法类）**：本征值问题（B-5/6/7/9/10/11 族 A + B-12 族 C）、时间推进抛物型（B-10 族 D Crank–Nicolson、B-11 族 B RK4）、复合 Simpson 求积（B-10/B-11/B-12 族 A）、连分数有理逼近（B-12 族 B）、₂F₁ 超几何 Euler 积分（B-12 族 D）、2D 泊松 + 迭代解（`drift_diffusion_2d._solve_poisson_drift_diffusion`，T1-B 内核）。
本批四族分别落**新算子类（非局部）** / **新矩阵函数类** / **新优化·变分类** / **新积分方程类** ⇒ 均不撞。

**③ golden 不是截断近似式**：A 为 Riemann–Liouville 初等闭式；B 为三角/指数初等闭式；C 为初等代数/超越闭式；D 为一级指数核初等闭式。
**本批 golden 无一是截断级数 / 微扰展开 / 经验拟合。**

### 2.3 被否候选（8 项，记入台账）

| 候选 | 否决理由 |
| --- | --- |
| Airy 函数 / 线性势本征值 | **数值同源** ≡ B-6 三角势阱（`ai_zeros`） |
| 不完全 Gamma / erfc 族 | **数值同源** ≡ B30（`erfc`） |
| 合流超几何 `M(a,b,z)` | **结构同源** ≡ B-12 族 D（₂F₁ Euler 积分表示） |
| Laplace 逆变换 Talbot / Stehfest | **超收敛** ⇒ 残差沉 round-off 地板，判据 D 不可用 |
| 复步长微分（complex-step） | 残差恒为机器精度 ⇒ **代数恒等型**，判据 D 不成立 |
| Wynn ε / Aitken Δ² 序列加速 | **精确加速** ⇒ 地板 + 与 B-12 族 B（连分数）**结构同源** |
| 2D 泊松五点差分 + SOR/Gauss–Seidel | **结构同源** ≡ `drift_diffusion_2d._solve_poisson_drift_diffusion` |
| 蒙特卡洛积分 | **非确定性** ⇒ 违反报告确定性铁律 |

---

## 3. 逐锚数据（真 harness 路径实测）

| bid | 物理/数学对象 | tol | golden | candidate | \|Δ\| | 余量 |
| --- | --- | --- | --- | --- | --- | --- |
| B217 | `D^0.5[1]=1/√(πt)`，t=1 | 0.01 | 0.564189584 | 0.564167545 | 2.204e-05 | 453.8× |
| B218 | `D^0.5[t]=√2/Γ(1.5)`，t=2 | 0.01 | 1.595769122 | 1.595706788 | 6.233e-05 | 160.4× |
| B219 | `D^0.5[t³]=6/Γ(3.5)`，t=1 | 0.01 | 1.805406667 | 1.805054083 | 3.526e-04 | **28.4×** |
| B220 | `D^0.25[t²]=2/Γ(2.75)`，t=1 | 0.01 | 1.243503145 | 1.243418143 | 8.500e-05 | 117.6× |
| B221 | `exp(At)[0,1]=−sin t`，t=1 | 0.01 | −0.841470985 | −0.841470983 | 2.086e-09 | 4.79e6× |
| B222 | `exp(At)[0,1]=−sin(2.5t)`，t=1 | 0.01 | −0.598472144 | −0.598472085 | 5.866e-08 | 1.70e5× |
| B223 | `exp(At)[0,0]=e^{−t}`，t=1.5 | 0.01 | 0.223130160 | 0.223130157 | 2.819e-09 | 3.55e6× |
| B224 | `exp(At)[0,0]=2e^{−t}−e^{−2t}`，t=1 | 0.01 | 0.600423599 | 0.600423603 | 3.578e-09 | 2.79e6× |
| B225 | `a(x⁴/4−x²/2)` 极小 `−a/4`，a=1 | 0.01 | −0.250000000 | −0.250000000 | 1.933e-10 | 5.17e7× |
| B226 | `a/x+x` 极小 `2√a`，a=1 | 0.01 | 2.000000000 | 2.000167209 | 1.672e-04 | 59.8× |
| B227 | `x ln x−b x` 极小 `−e^{b−1}`，b=0.5 | 0.01 | −0.606530660 | −0.606526841 | 3.819e-06 | 2618.6× |
| B228 | `e^x−c x` 极小 `c−c·ln c`，c=2 | 0.01 | 0.613705639 | 0.613705640 | 6.999e-10 | 1.43e7× |
| B229 | Volterra `K=e^{−(x−t)}`，λ=0.5，x=1 | 0.01 | 1.393469340 | 1.393469397 | 5.651e-08 | 1.77e5× |
| B230 | Volterra `K=e^{−(x−t)}`，λ=0.8，x=1.5 | 0.01 | 2.036727117 | 2.036727637 | 5.200e-07 | 1.92e4× |
| B231 | Volterra `K=e^{−2(x−t)}`，λ=1，x=1 | 0.01 | 1.632120559 | 1.632120931 | 3.727e-07 | 2.68e4× |
| B232 | Volterra `K=x−t`，λ=1，x=1 | 0.01 | 1.543080635 | 1.543080588 | 4.670e-08 | 2.14e5× |

**worst-case**：B219 余量 **28.4×**（本批最小，仍 ≫1）。**16/16 `|Δ|` 非零 within tol**（无一是 0.0 ⇒ 非自证桩）。

**闭式极限自检**（候选在细档下应收敛到 golden 闭式，8/8 全中）：
`D^0.5[1]` n=12800 → 0.564184074 vs `1/√π`=0.564189584；`D^0.5[t³]` → 1.805318515 vs `6/Γ(3.5)`=1.805406667；
`exp(At)[0,1]` n=12 → −0.841470984808 vs `−sin1`；`exp(At)[0,0]` → 0.600423599106 vs `2e^{−1}−e^{−2}`；
`a/x+x` k=40 → 2.000000000000 vs `2√1`；`e^x−2x` → 0.613705638880 vs `c−c ln c`；
Volterra `K=e^{−(x−t)}` n=8192 → 1.393469341170 vs 闭式 1.393469340287；Volterra `K=x−t` → 1.543080634086 vs `cosh1`。

---

## 4. 判据 D（离散参数单调收敛 · 16/16 严格单调）

| bid | 首值 | 末值 | 单调 |
| --- | --- | --- | --- |
| B217 | 1.409e-03 | 2.204e-05 | ✓ |
| B218 | 3.984e-03 | 6.233e-05 | ✓ |
| B219 | 2.243e-02 | 3.526e-04 | ✓ |
| B220 | 5.428e-03 | 8.500e-05 | ✓ |
| B221 | 1.642e-03 | 1.059e-12 | ✓ |
| B222 | 7.414e-03 | 1.509e-10 | ✓ |
| B223 | 9.822e-04 | 3.302e-12 | ✓ |
| B224 | 3.807e-04 | 7.030e-12 | ✓ |
| B225 | 1.007e-03 | 1.933e-10 | ✓ |
| B226 | 1.099e+00 | 1.672e-04 | ✓ |
| B227 | 5.999e-01 | 3.819e-06 | ✓ |
| B228 | 1.362e-01 | 6.999e-10 | ✓ |
| B229 | 9.267e-04 | 5.651e-08 | ✓ |
| B230 | 8.561e-03 | 5.200e-07 | ✓ |
| B231 | 6.127e-03 | 3.727e-07 | ✓ |
| B232 | 7.634e-04 | 4.670e-08 | ✓ |

**收敛阶实证**：族 A 残差链逐次约 **÷2**（`1.41e-03→7.05e-04→3.53e-04…`）⇒ **O(h) 一阶**，与 GL 一阶精度理论一致；族 D 残差链逐次约 **÷4**（`9.27e-04→2.32e-04→5.79e-05…`）⇒ **O(h²) 二阶**，与分块梯形理论一致；族 B 末值降至 1.06e-12（s=8 撕裂档，仍严格单调）；族 C 由 `η` 固定步长保证单调。

**判据 D 红线复核**：末值均 **> 1e-12**（最小 B223 3.302e-12、B221 1.059e-12 —— 二者仍高于 `run_d_criterion_smoke` ③ 的 1e-12 基线门槛；族 A/C/D 末值 1e-4~1e-8 量级，远离地板）；**无一道沉 round-off 地板**。

---

## 5. 反向标定（C5：注册键 ×1.1 信号须 > tol）

| bid | 注册键 | 信号 | 信号/tol |
| --- | --- | --- | --- |
| B217 | alpha | 5.609e-02 | 5.61 |
| B218 | alpha | 5.337e-02 | 5.34 |
| B219 | alpha | 1.016e-01 | 10.16 |
| B220 | alpha | 2.555e-02 | **2.55** |
| B221 | t | 4.974e-02 | 4.97 |
| B222 | t | 2.168e-01 | 21.68 |
| B223 | t | 3.108e-02 | 3.11 |
| B224 | t | 4.548e-02 | 4.55 |
| B225 | a | 2.500e-02 | 2.50 |
| B226 | a | 9.762e-02 | 9.76 |
| B227 | b | 3.110e-02 | 3.11 |
| B228 | c | 1.483e-01 | 14.83 |
| B229 | lam | 4.943e-02 | 4.94 |
| B230 | lam | 1.713e-01 | 17.13 |
| B231 | lam | 9.318e-02 | 9.32 |
| B232 | lam | 5.922e-02 | 5.92 |

**最弱 2.55×（B220）** ⇒ 16/16 均高于「须 >1.4×」门槛（最小者仍留 1.82× 安全裕度）。**`_PERTURB_KEYS` 逐锚登记，无零响应键**（零响应键一律退出 `default_params`，见 §6 血案⑤）。

---

## 6. 本批血案（5 条 · 候选级）

| # | 血案 | 根因 | 处置 |
| --- | --- | --- | --- |
| ① | **格点吸附** | GL 卷积以步长 `h` 采样 `f(t−kh)`；若 `h` 不整除观测点 `t`，残差被 `int(round(x/h))` 的 **O(h) 量化误差**主导 | 步长强制 `h=t/n`（精确整除） |
| ② | **round-off 地板** | 族 B 的 scaling–squaring 以 `2^s`（s=8）平方放大舍入；`n≥5` 时残差沉至 4.77e-15 且**非单调** ⇒ 判据 D 不可用（超收敛型假阴） | 扫描上限收在 `n≤4`，**定档 n=3** |
| ③ | **running-min 平坦段** | 族 C 原设计用黄金分割搜索，「已评估点最小值」序列**每两步才更新** ⇒ 残差链出现平台（B225 初版 1.08e-3, 1.08e-3, …）⇒ 判据 D **严格**单调不成立 | **改固定步长梯度下降**（沿负梯度确定性迭代 ⇒ 链可证单调） |
| ④ | **隐式项漏移项** | 族 D 分块梯形含 `k=j` 项，而核 `K(0)≠0` ⇒ 该项含未知 `φ_j`，必须移项后前向递推 | `φ_j=(1+λh·s)/(1−½λh·K(0))`，显式递推 |
| ⑤ | **零响应键** | B218 原设 `t=1` 且只扰 `α` ⇒ 信号仅 **0.07×tol**，反向判据无判别力 | 改 `t=2.0` ⇒ 信号放大至 **5.34×tol** |

---

## 7. 护栏

### 7.1 七道核心计数护栏

| 护栏 | 结果 |
| --- | --- |
| `run_p0_count_guard_sync_smoke.py`（P0 计数护栏同步） | **6 tests OK** |
| `run_count_consistency_smoke.py`（账本 ≡ pyproject ≡ README） | **11 tests OK** |
| `run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点） | **4/4 PASS**（229/3/18，和=250） |
| `run_self_certified_lock_smoke.py`（棘轮 + 锁语义） | **4/4 PASS**（棘轮 `=18` 守住；分布 `{t2_blocked:6, terminal_tier1:12}`；反向测试 neg/pos 均 True） |
| `run_maturity_baseline_smoke.py`（VMM 底线 M1-M5） | **PASS**（M5 口径 229/3/18，和=250；低置信 12） |
| `run_webui_verification_ledger_smoke.py`（端点 ≡ 冒烟口径） | **15 PASS / 0 FAIL** |
| `run_statistical_anchor_smoke.py`（S 类统计锚） | **34 PASS / 0 FAIL**（题库 `总=250 B=227 E=10 S=13`，check 名含 `Batch B-13 十六锚`） |

**七道全绿**。⚠️ `run_statistical_anchor_smoke` **首跑 rc=1**（本次账本同步的**括号闭合位错位**触发 `IndentationError`），即时修复后复跑 **34/0 全绿** —— 记入 §8 工具级血案。

另 `run_d_criterion_smoke.py` 的普查项确认「**已接线候选 229/229 全部登记（动态）**」——B217-B232 全在，且该断言的计数已由 `len(...)` 动态推导（无需手改）。

### 7.2 三道既有红灯（承接 B-9/B-10/B-11/B-12，**非本批引入**）

| 既有红灯 | 结果 | B-13 影响 | 归属 |
| --- | --- | --- | --- |
| `run_d_criterion_smoke.py` ③ 基线残差 > 1e-12 | **9 PASS / 1 FAIL** —— 失败清单 = **B65/B66/B67/B68/B73/B74/B79/B81/B82/B83/B84/B87/B88（13 道 B-4 锚）** | **无** | 承接 B-9..B-12（逐字同清单） |
| `run_benchmark_falsifiability_smoke.py` ⑨ 路径② JSON 序列化 | **12/13 PASS** —— numpy bool 泄漏（8 道 golden 返回 `np.float64`/`bool`）；同 smoke 已如实披露「严格独立 229 · 降级 3 · 自证桩 18/250」 ✅ | **无** | 承接 B-10..B-12 |
| `run_coverage_deadzone_closure_smoke.py` | **31 PASS / 2 FAIL** —— B5/B6 `class=strict`（v0.9.81 已升 strict、该 smoke 期望陈旧） | **无** | 承接 B-9..B-12 |

**结论：B-13 零新回归**（16 道新锚定档基线残差最小 **1.933e-10**（B225）≫ 1e-12 门槛，无一撞地板；族 B 三档最浅末值 1.059e-12 亦高于门槛）。本批**未修**上述三道（超范围，且会触碰既有锚语义）。

---

## 8. 账本变更（26 处原子替换 · FAILS=0）

| 文件 | EOL | 变更 |
| --- | --- | --- |
| `README.md` | **CRLF** | 插入新顶行 v0.9.93（B-13 四族 + 血案 5 + 被否 8 + 91.6%/95.2%）；原 v0.9.92 行转「上一版」；原 v0.9.91 行转「✅ 已部署生产（…B-11 扩基详情…）」；题数 234→250（B1-B216→B1-B232）；三分类 213/3/18 和 234 → **229/3/18 和 250**；路径① `verified=213/234`→`229/250`（含「独立候选 213/234」串）；路径② `2/234`→`2/250`（余 232→248）；`213（路径①）`→`229（路径①）` |
| `CONTRIBUTING.md` | LF | L5 v0.9.92→v0.9.93 / 234→250 道锚 / 213→229；L62 真值块 v0.9.93 / P1-1 B-13 扩基 / 229 / 3 / 18 / 和 250 |
| `pyproject.toml` | **CRLF** | `version = "0.9.92"` → `"0.9.93"` |
| `lda/run_count_consistency_smoke.py` | LF | docstring 234→250 题（B1-B216=211→B1-B232=227）；宣传串同改；版本注释补 B-13；`len(b_ids)==211`→`227`；max B `"B216"`→`"B232"`；`assertIn("B1-B216")`→`"B1-B232"` |
| `lda/run_statistical_anchor_smoke.py` | LF | docstring 234→250 题（B1-B216=211→B1-B232=227）；`expected_b` **追加** `[B217..B232]`；check 名改 B1-B232 + `Batch B-13 十六锚` |
| `lda/run_webui_verification_ledger_smoke.py` | LF | docstring 三分类 213 / 和 234 → 229 / 和 250 |
| `lda/run_maturity_baseline_smoke.py` | LF | M5 docstring `213/3/18，和=234`→`229/3/18，和=250`；批次尾巴补 B-13 |

**未改**（实测确认无需改）：
- `lda/run_benchmark_falsifiability_smoke.py` —— 唯一硬编码 `MIN_INDEPENDENT = 63`，strict 229 ≥ 63 ✅；
- `lda/run_self_certified_lock_smoke.py` —— `MAX_SELF_CERTIFIED = 18` 不动（本批无毕业，**纯新增**）；
- `lda/run_p0_count_guard_sync_smoke.py` / `run_three_class_consistency_smoke.py` / `run_d_criterion_smoke.py` / `run_coverage_deadzone_closure_smoke.py` —— 计数**全部动态推导**（grep 全量 `run_*smoke.py` 实测：硬编码计数仅存在于上面两行已同步文件）；
- `CHANGELOG.md` —— 5 处数字命中均为历史快照（CPO 250k / T2 1.234e-5 / `+211 行` / B1–B28），**非账本计数串**；且 v0.9.78 起 CHANGELOG 未逐批追加（B-4..B-12 均未加），**本批亦不破例**；
- `ALIGNMENT_REPORT.md` / `P1-1_self_certified_discipline.md` —— 滚动扫描 **hits=0**；
- 兵库 `_VMM_OVERRIDES` —— B-13 新锚走 DEFAULT 推导，**均为 strict**，无需覆写。

**EOL 加固**：README 初版插入用了裸 `\n` ⇒ `git ls-files --eol` 报 **`w/mixed`**（index=CRLF 而工作树混行）。已归一为纯 CRLF，复验 `i/crlf w/crlf` ✅（此即 B-10 血案的同一类陷阱，见 `IRONLAWS §六`）。

**🔴 本轮账本同步工具级血案 2 条（自伤 · 首跑护栏抓出）**：

| # | 血案 | 根因 | 处置 |
| --- | --- | --- | --- |
| ① | README 插入新版块后 `git ls-files --eol` 报 **`w/mixed`**（index=CRLF 而工作树混行） | 拼接**新行 + `"\n"` + 旧行**时，分隔符用了裸 LF，而 README 全文件是 CRLF | 归一为纯 CRLF（`\r\n→\n→\r\n`），复验 `i/crlf w/crlf` ✅。**这是 B-10 EOL 血案的同类复发** —— 任何对 README 的「插入行」操作都必须用 CRLF 分隔符 |
| ② | `run_statistical_anchor_smoke.py` 首跑 **`IndentationError: unexpected indent`** | 追加 `[B217..B232]` 行时，**把外层 `)` 留在了上一行**（`range(201,217)**)**]`），使表达式在 B-12 行提前闭合，新行成为孤儿缩进行 | 去掉上一行多余的 `)`（`range(201,217)]`）⇒ 复跑 **34 PASS / 0 FAIL**。**教训：向多行括号表达式追加行时，必须把闭合括号一起搬到新的末行** |

> 两条均**由护栏即时抓出、当轮修复**，未流入提交 —— 这正是「加锚后必跑全量护栏」的价值所在。

---

## 9. 提交、推送与部署

- **提交**：`249e455`「P1-1 B-13 扩基 16 锚（v0.9.93）：独立率 91.0%→91.6%、天花板 94.87%→95.2%」——
  **12 文件 +1192 / −22**，新增 `lda/lda_harness/_batch_b13_numeric.py` 与 `LDA_independence_sprint_B13_2026-09-17.md`；
  `dist/store.json` **未动**；提交前闸门校验「白名单外零变更」通过。
- **推送三端**（`scripts/sync_push.py D:/agent_LDA`）：

| 远端 | 结果 |
| --- | --- |
| `gitee` | `dd9fd9c..249e455  main -> main` · **exit=0**（直连） |
| `github` | `dd9fd9c..249e455  main -> main` · **exit=0**（直连，proxy 已清空 ⇒ **未退回 SOCKS5**） |

  `[CLEAN] store 已删除`；**三端 HEAD 一致 = `249e455`**。
- **本地工作树**：`git status` clean（回填本行后产生的文档提交另计）。
- **✅ 生产部署**（2026-09-17 授权后执行，`remote_deploy.py --expect-head 6581e9c`）：
  `SSH_OK` → `git pull` `2f879a1..6581e9c` **fast-forward（14 文件 +1219 / −25）** →
  `pip install --force-reinstall --no-deps .` **`lda-design 0.9.92 → 0.9.93`**（消除 `/api/health` 版本串滞后）→
  `dist/store.json` **未动**（2072 B）→ `systemctl restart lda-webui` rc=0 → `HEAD_MATCH=True`，`is-active → active`。
  生产实测验收（内网 `127.0.0.1:3006` 与 nginx 域名一致）：

  | 检查项 | 实测值 | 期望 | 判定 |
  | --- | --- | --- | --- |
  | `/api/health` version / benchmarks | `0.9.93` / `250` | 0.9.93 / 250 | ✅ |
  | `vmm.tiers` | strict **229** / degraded **3** / self_certified **18** | 229 / 3 / 18 | ✅ |
  | `judgment_paths.derived.totals` | anchors 250 / 229 / 3 / 18 | 250 / 229 / 3 / 18 | ✅ |
  | `honest_note` 独立候选判出数 | **229** 道 | 229 | ✅ |
  | `anchors.by_kind['physical-law'].ids` | count **238**，含 `B217` / `B232` | 含 B232 | ✅ |
  | `anchors.dispatch_ids` | count **241** | 241（227 B + 13 S + 遗留 B35） | ✅ |
  | `anchors.total` | **251** | 241 + 10 E | ✅ |
  | `ci_core.count` | **178**（`stale=false`） | 178（不变） | ✅ |
  | `/api/shelf` count | **75** | 75 | ✅ |

  （`anchors.total`/`physical-law.count` 比题库口径各多 1，系 `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` 历史遗留键 `B35`——结构性、非缺陷；核新批次号以 `physical-law.ids` 出现 `B232` 为准。）

---

## 10. 结论与下一步

- 腿①「扩基加锚（稀释 terminal）」再上一档：**独立率 91.0% → 91.6%（229/250）**，**天花板 94.87% → 95.2%**。
- terminal Tier-1 **恒 12 道**（永不升）；自证桩 **恒 18**（棘轮只减不增）；本批**纯新增**，零毕业、零判决行为改动、零 tol 放宽、零新增 CI smoke。
- **剩余三冲刺腿态势**：①扩基加锚（纯内部，仍可继续 —— B-13 后剩余可扩空间按「天花板 − 独立率」计为 3.6 pt）②degraded 3→strict（纯内部，3 道：E9/E10/B21）③T2 解锁 6（外部 KPI，需 MPW 回流，见 `P1-E_T2_unlock_plan.md`）。
- **✅ 已部署生产**：授权后 `remote_deploy.py --expect-head 6581e9c` 部署成功（`HEAD_MATCH=True`）——生产 `vmm.tiers` = strict **229** / degraded **3** / stub **18** / total **250**（独立率 **91.6%**）、`honest_note` **229**、`benchmarks` **250**、`dispatch_ids` **241**、`physical-law.ids` 含 `B232`、`ci_core` **178** 条不变。
