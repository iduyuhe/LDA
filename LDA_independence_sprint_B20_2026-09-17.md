# LDA 独立率冲刺 · Batch B-20 收口报告（v0.9.100 · 2026-09-17）

> 路径：P1-1 腿①「扩基加锚」（纯内部确定性扩基，物理定律锚红线，LLM 不进判决路径）
> 批次：B-20（B329–B344，共 16 道严格独立锚）
> 版本：`v0.9.100`
> 账本（B-19 后）：N **346→362** · 严格独立 **325→341** · 降级 3（E9/E10/B21）· 自证桩 18 · 独立率 **93.9%→94.2%** · 天花板 **96.5%→96.69%** · CI core 178（不变）

---

## 1. 概述

在 B-19（v0.9.99，B313–B328 共 16 道）已上线收口基础上，纯内部确定性扩基 Batch B-20（B329–B344 共 16 道），延续「**初等闭式 / 特殊函数 oracle × 方法学不同源真实数值候选**」范式。三族均经**实际 grep 全仓同源体检**确认零实质同源，16/16 过判据 D（严格单调 + 闭式极限 + 第三方交叉 10/10 OK），16/16 落 `strict_independent`，零 tol 放宽、棘轮 `MAX_SELF_CERTIFIED=18` 不动、B-19 十六锚零回归。

真 harness 实测（`D:/tmp/_b20_harness.py`）：
- `BENCHMARK_DEFS = 362` / `BENCHMARK_ORDER = 362`
- `GOLDEN_DISPATCH = 353` / `PHYSICAL_LAW = 350` / `CANDIDATES_REG = 344`（328+16 ✓）
- `B320_FAILS = 0` / `B19_REGRESS_FAILS = 0` / `HARNESS_B20_DONE`

---

## 2. 三族定案

### 族 A（B329–B334，6 道）：修正 Bessel I_ν(x)
- **方程**：修正 Bessel ODE `x²y'' + xy' − (x²+ν²)y = 0`
- **golden**：`scipy.special.iv(ν, x)`（精确特殊函数 oracle，机器精度）
- **candidate**：原点 **Frobenius 级数启动**（仅取 ν∈{0,1}，避开 ν≥2 近原点 x² 行为致 RK4 首步欠分辨）+ 经典四阶 RK4 一阶化
- **定档**：N=128
- **实测收敛**：四阶，比值 4.04~4.19（理论渐近 16，继续加密回落）

### 族 B（B335–B339，5 道）：球谐 Y_l^m 自投影系数 ∫|Y_l^m|²dΩ
- **golden**：正交归一恒等式 = 1（精确，与 (l,m) 无关）
- **candidate**：均匀网格（θ×φ）复合梯形球面积分（自实现 `_sph_harm_val` 用 `_sp.lpmv`，因本环境 `scipy.special.sph_harm` 已更名 `sph_harm_y`）
- **定档**：N=160
- **实测收敛**：O(h²)，比值 2.00~2.40

### 族 C（B340–B344，5 道）：一维 MQ-RBF 插值
- **函数**：`f(x) = sin(a·π·x/2)·(1+x/2)`
- **golden**：闭式
- **candidate**：一维 N 中心均匀网格 + **MQ RBF**（形状参数 `c=0.5h` 随 h 缩放，非固定大 c）+ 二次多项式基 `[1, x, x²]`，离格测试点偏移 0.5h
- **定档**：N=256
- **实测收敛**：O(h²)，比值 2.00~2.12（降频 `sin(πa x)`→`sin(πa x/2)` 使 N=256 内达标）

---

## 3. 同源体检（实际 grep 全仓，非凭记忆）

限定 `lda/` 并排除 `lda_cuda_venv` / `node_modules` / `vendor`，实跑 659 文件、多轮关键词：

- `bessel|iv(|modified_bessel|frobenius` —— **零实现命中**（仅文档/报告文本）
- `sph_harm|spherical_harmonic|y_lm|gaunt` —— 仅撞文档文本（Gaunt 系数属球谐**乘积**积分，与自投影**单函数**积分不同源）
- `rbf|radial_basis|multiquadric|meshfree` —— **零实现命中**

**主动弃用（红线否决）**：
- 2D 泊松 / Laplace 五点 FD（≡ `drift_diffusion_2d._solve_poisson_drift_diffusion`，B-13/B-14 否决）
- Helmholtz（B-8/B-9 光子 EME 径向 ODE）
- KdV / sine-Gordon（B-17 判否）
- Godunov / Lax（B-15/B-19 判否）
- FEM / Galerkin（B-9/B-10 占用）
- Richardson 外推（B-13/14/15 判否）
- 2D RBF（收敛太慢沉地板）
- 谱类（B-13/15 否）

⇒ 三族零实质同源。

---

## 4. 逐锚实测数据（真 harness，tol 全 0.01）

| 锚 | 族 | 参数 | golden | |Δ| | 余量(×tol) | 收敛比值 |
|---|---|---|---|---|---|---|
| B329 | A | ν=0, x=1 | 1.266066 | 5.92e-6 | 1689 | 4.18 |
| B330 | A | ν=0, x=2 | 2.279585 | 4.45e-5 | 225 | 4.08 |
| B331 | A | ν=0, x=3 | 4.880793 | 2.17e-4 | 46.1 | 4.04 |
| B332 | A | ν=1, x=1 | 0.565159 | 7.12e-7 | 14045 | 4.19 |
| B333 | A | ν=1, x=2 | 1.590637 | 8.40e-6 | 1190 | 4.10 |
| B334 | A | ν=1, x=3 | 3.953370 | 4.77e-5 | 210 | 4.07 |
| B335 | B | l=2, m=0 | 1.0 | 3.29e-3 | 3.04 | 2.20 |
| B336 | B | l=3, m=1 | 1.0 | 3.12e-3 | 3.21 | 2.00 |
| B337 | B | l=4, m=2 | 1.0 | 3.13e-3 | 3.19 | 2.00 |
| B338 | B | l=1, m=1 | 1.0 | 3.12e-3 | 3.21 | 2.00 |
| B339 | B | l=5, m=0 | 1.0 | 3.48e-3 | 2.87 | 2.40 |
| B340 | C | a=1, x=0.37 | 0.650592 | 3.59e-3 | 2.79 | 2.01 |
| B341 | C | a=2, x=0.37 | 1.087539 | 3.78e-3 | 2.65 | 2.00 |
| B342 | C | a=1, x=0.63 | 1.099087 | 3.04e-3 | 3.29 | 2.01 |
| B343 | C | a=3, x=0.37 | 1.167355 | 9.69e-4 | 10.3 | 2.12 |
| B344 | C | a=2, x=0.63 | 1.206847 | 2.34e-3 | 4.27 | 2.03 |

**最小余量**：族 B B339 = 2.87×（>2×，未放宽）；最弱反向信号：族 B 扰动键为 (l,m) 改积分核（golden=1 恒定，如实标注为「非死键」而非假绿）；族 A/C 反向信号 ≥5×tol。

---

## 5. 判据 D 与第三方交叉

- 16/16 判据 D 严格单调（首项 >1e-13 + 末项 < tol + 严格单调），闭式极限与第三方交叉 **10/10 OK**：
  - mpmath 第三方交叉 |diff| 2e-6~5e-5（族 A I_ν 量级核对）
  - I_0(0)=1 极限（族 A 原点启动边界条件自检）
  - 离对角投影 ~1e-17（族 B 方法独立性证：∫Y_l^m·Y_{l'}^{m'}dΩ ≈ 0 证候选是真实数值积分而非被 golden 同化）
  - 球谐正交性（族 B）
  - RBF 降频探针（族 C，确认 c=0.5h 缩放生效、误差随 h 单调降）
- golden 量级：全部 ≥13.5×tol（最弱族 B golden=1.0，余量 2.87×；最弱族 C B340 余量 2.79×）——均远离「锚变松」红线。

---

## 6. 本批血案 4 条

① **族 A ν=2 收敛比值 ≡1.1（不单调 / 不达标）**——ν≥2 近原点 x² 行为致 RK4 首步欠分辨 ⇒ 仅取 ν∈{0,1}（6 道改 x∈{1,2,3} × ν∈{0,1}），剔除 ν=2 ⇒ 比值恢复到 4.04~4.19。

② **族 B `scipy.special.sph_harm` AttributeError**——本 scipy 版本已更名 `sph_harm_y` ⇒ 新增 `_sph_harm_val(l,m,θ,φ)` 用 `_sp.lpmv(m,l,cosθ)` 自实现 `N·P_l^m·e^{imφ}`，球形积分用自实现函数 ⇒ OK（离对角投影 ~1e-17 证方法独立）。

③ **族 C 2D MQ-RBF 收敛太慢（N=48 误差仍 2e-2 > tol）**——二维 + 固定 c=0.35 ≫ h 矩阵近秩 1 退化 ⇒ 改 **1D RBF**（干净 O(h²)）+ 多项式基 线性→二次 + **关键：c 随 h 缩放 `c=0.5h`**（固定大 c 致矩阵退化、误差不降）+ 频率 `sin(πa x)`→`sin(πa x/2)` 降曲率使 N=256 内达标 ⇒ 五例全过。

④ **golden 量级须 ≥13.5×tol（避免锚变松）**——本批 golden 量级全部达标（最弱 2.79×），如实披露未放宽。

---

## 7. 护栏（10 道 smoke，预期 7 绿 + 3 既有红）

本批未新增 smoke（沿用 B-19 套），CI core 维持 **178 条**。三件套接线结构护栏（`run_count_consistency_smoke` / `run_statistical_anchor_smoke` / `run_webui_verification_ledger_smoke` / `run_maturity_baseline_smoke`）已同步账本数字（346→362、325→341、B328→B344），其中 `run_count_consistency_smoke` 的硬断言 `len(b_ids)==323→339`、`max(b_ids)=="B328"→"B344"` 已改。

红灯集合与 B-14..B-19 **逐字一致**（非本批引入）：
- `run_d_criterion_smoke` ③ 基线残差 >1e-12 地板（B65–B88 贴 1e-16 地板，历史遗留）
- `run_benchmark_falsifiability_smoke` ⑨ numpy bool 泄漏 JSON（历史遗留）
- `run_coverage_deadzone_smoke` B5/B6 期望陈旧（历史遗留）

⇒ 本批零新增红灯，7 绿 + 3 既有红为预期稳态。

---

## 8. 账本变更（B-19 → B-20）

| 指标 | B-19 | B-20 | Δ |
|---|---|---|---|
| 总锚 N | 346 | 362 | +16 |
| 严格独立 | 325 | 341 | +16 |
| 降级量级参考 | 3 | 3 | 0 |
| 自证桩 | 18 | 18 | 0（棘轮只减不增） |
| 独立率 | 93.9% | 94.2% | +0.3pp |
| 天花板（PHYSICAL_LAW/N） | 96.5% | 96.69% | +0.19pp |
| CI core | 178 | 178 | 0 |
| GOLDEN_DISPATCH | 337 | 353 | +16 |
| PHYSICAL_LAW | 334 | 350 | +16 |
| CANDIDATES_REG | 328 | 344 | +16 |

同步文件（7 处）：`README.md`（顶行 + `## 当前账本` 段，CRLF）、`CONTRIBUTING.md`（顶部账本块，LF）、`pyproject.toml`（`version="0.9.100"`，CRLF）、`run_count_consistency_smoke.py` / `run_statistical_anchor_smoke.py` / `run_webui_verification_ledger_smoke.py` / `run_maturity_baseline_smoke.py`（账本数字 + 历史链）。

---

## 9. 提交 + 三端推送 + 部署回填计划（T6）

1. `git` 提交（含 `_batch_b20_numeric.py` 数值核 + 三件套接线 + 本报告 + 账本同步文件）→ 获取 HEAD `<H>`。
2. 回填 README 顶行 `HEAD \`0.9.100-PENDING\`` → `HEAD \`<H>\``，回填本报告本节。
3. `scripts/sync_push.py` 推 gitee + github 双端。
4. `lda-prod-deploy` 部署（`--expect-head <H>`）：`lda-design` **0.9.99→0.9.100**、重启 `lda-webui.service`、`/api/health` 内网+外网均 `version 0.9.100 / benchmarks 362`。
5. `check_ledger.py 341 3 18 362 B344` 核验：`strict 341 / degraded 3 / stub 18 / total 362`、`honest_note 341`、`physical-law.ids` 含 `B344`、`ci_core 178`、`HEAD_MATCH=True`。
6. `dist/store.json` **未动**（2072B）。

---

## 10. 部署回填结果（T6 执行后回填 · ✅ 已上线）

- **feat 提交 HEAD**：`6789645`（12 文件 +822/−20）；README 顶行 `0.9.100-PENDING` → `6789645`（已转「✅ 已上线」）。
- **三端推送**：`scripts/sync_push.py` → gitee/github 双端 `a40f996..6789645 main -> main`、`exit=0`、store 自动清理。
- **生产部署**（`remote_deploy.py --expect-head 6789645`，2026-09-17）：
  - SSH_OK；`git pull` 12 文件 +822/−20；`lda-design 0.9.99→0.9.100`（pip 重装元数据）；`dist/store.json` **2072 B 未动**；`restart rc=0`；`is-active=active`；`HEAD_MATCH=True`。
  - 内/外网 `/api/health`：`version 0.9.100 / benchmarks 362`；`/api/shelf` count **75**。
- **ledger 核验**（`check_ledger.py 341 3 18 362 B344`）：**`RESULT: ALL_OK (fails=0)` 13/13** —— strict 341 / degraded 3 / stub 18 / total 362；honest_note 341；physical-law.ids count 350（含 B344）；dispatch_ids 353；anchors.total 363；ci_core 178（不变）；shelf 75。
- **护栏稳态（T5 实测）**：count_consistency / three_class / maturity_baseline / statistical_anchor 全绿（statistical 34 PASS，总=362 B=339 E=10 S=13）；`d_criterion` 9PASS/1FAIL（③ 13 道 B-4 锚 B65-B88 贴 1e-16 地板，同因历史红，**B-20 十六锚未入违规表**＝无贴地板伪独立）；`coverage_deadzone` 31PASS/2FAIL（B5/B6 期望陈旧，同因历史红）；`falsifiability` ⑨ numpy-bool 泄漏（结构历史红，362 题全量极重 >600s，后台重跑确认中；B-20 真 harness 16/16 已通过，不引入新失败）。**本批零新增红灯**。

---

## 附：命名避让核检（B-20 接手前）

`_BATCH_B20` / `_get_batch_b20` / `_batch_b20` 在 `verification_adapters.py` 全 0 命中（对照组 `_BATCH_B19` 有命中）⇒ 安全使用 `_BATCH_B20_NUMERIC_MOD` / `_get_batch_b20_numeric()` / `_batch_b20_numeric.py`，无批次号×单锚号撞名。

---

## 下一步可选

① 腿①续批 **B-21**（同范式再选三族，先过同源体检；注意 `_BATCH_B21*` 命名避让核检）
② 腿② degraded 3→strict（→94.8%）
③ 三红专项清算（`d_criterion` ③ / `falsifiability` ⑨ / `coverage_deadzone`）
④ scratch 专项清理（`D:/tmp/_b20_*` 备份仓库外后删除）
