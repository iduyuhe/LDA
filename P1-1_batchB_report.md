# P1-1 自证桩升级 · Batch B-1 报告（路径 B：新增方法学独立锚扩基）

> 日期：2026-09-16 · 执行人：助理 · 关联：`lda_harness/_batch_b_numeric.py` · 决策来源：用户「先B」

## 0. 结论速览

- **策略**：用户选择路径 B —— 不纠结原清单（B17–B19/S1–S13 多为 `_VMM_OVERRIDES` 锁死的 terminal Tier-1 或早已严格独立，按原清单冲刺 70% 数学上不可达，净增量 = 0），改为**新增带真独立候选的物理锚把分母做大**。
- **本批交付**：5 道双方法严格独立新锚（B34 / B36 / B37 / B40 / B41），全部 = 确定性解析闭式 golden 对拍 方法学不同源真实数值候选。
- **新独立率**：**36 / 61 = 59.0%**（基线 31 / 56 = 55.4%，+3.6pp）。
- **护栏**：README / CONTRIBUTING / ledger docstring 三分类已同步为 (36/3/22/和61)；`run_count_consistency_smoke`、`run_p0_count_guard_sync_smoke`、`run_statistical_anchor_smoke`、`run_benchmark_falsifiability_smoke` 全绿（可证伪性 13/13、全量 61 锚无回归）。
- **距 70% 缺口（反算）**：`(36+k)/(61+k)=0.7 ⇒ k≈22.3` → 仍需约 **23 道**方法学独立新锚方能达 70%。本批 5 道仅推进 ~3.6pp，路径 B 的代价是持续新增高质量物理锚。

## 1. 锚定义（每道 = 闭式 golden ↔ 不同源数值候选）

| 锚 | 物理量 | golden（闭式） | candidate（数值·方法学不同源） | 判据 D |
|----|--------|----------------|-------------------------------|--------|
| B34 | 条形介质波导 TE0 n_eff | Marcatili 1969 等效宽度近似 | 严格横向谐振超越方程 tan(κt/2)=γ/κ 二分求根 | 不适用（无离散参数，同 B9 先例） |
| B36 | 矩形波导 TE10 截止 | c/(2a) | 1D Dirichlet 盒 FD 本征取基模（w[-1]） | 由 B12/B22 已证 |
| B37 | 矩形波导 TE20 截止 | c/a | 1D FD 本征取第二模（w[-2]） | 由 B12/B22 已证 |
| B40 | 矩形波导 TE11 截止 | c/(2π)√((π/a)²+(π/b)²) | 2D Dirichlet 盒 FD 本征取最弱模（w[-1]） | 由 B12/B22 已证 |
| B41 | FP 1D 腔谐振波长 | 2nL/m | 1D Dirichlet 腔 FD 本征取第 m 腔模 | 由 B12/B22 已证 |

**共用铁律**：候选绝不调 golden；残差 = 近似/离散固有误差（持久、随参数变化、可证伪），非代数恒等、非噪声地板。B36/B37/B40/B41 复用 B12/B22 已验证 FD 本征核（`scipy.linalg.eigh`，`w[-mode]` 取最靠近 0 的最小模，非最高模 —— 这是首轮标定踩过的坑）。纯 numpy/scipy，C 级自主，零商业依赖。

## 2. 标定数据（接线前已实测，确保 CI 不红）

| 锚 | 默认参数 | 基线残差 | tol | d/tol 余量 | 反向 10% 信号 |
|----|----------|----------|-----|-----------|---------------|
| B34 | n_f=3.48, n_c=1.44, t=0.5, wl=1.55 | 2.46e-3 | 0.01 | ~4× | t×1.1 → 0.031 ≫ tol |
| B36 | a=0.02286, b=0.01016 | 1.7e-5 GHz | 0.01 GHz | ~590× | a×1.1 → 0.60 GHz ≫ tol |
| B37 | a=0.02286, b=0.01016 | 1.3e-4 GHz | 0.1 GHz | ~770× | a×1.1 → 1.19 GHz ≫ tol |
| B40 | a=0.02286, b=0.01016 | 1.6e-3 GHz | 0.1 GHz | ~62× | a×1.1 → 0.24 GHz ≫ tol |
| B41 | n=3.48, L=0.01, m=1 | 1.8e-7 m | 1e-3 m | ~5500× | L×1.1 → 6.96e-3 m ≫ tol |

全部残差 ≫ 1e-12 噪声地板，反向 10% 扰动全部远超 tol ⇒ 可证伪。tol 均**按实测残差留足余量、未放水**（红线纪律）。

## 3. 接线与护栏同步（已落地）

- `benchmarks.py`：新增 import + `BENCHMARK_DEFS["B34/B36/B37/B40/B41"]`（含 `candidate` 键指向注册候选、`golden_fn` 指向 `_batch_b_numeric.golden_bXX`、`default_params`、`note`）+ `BENCHMARK_ORDER` 追加。
- `golden.py`：`_GOLDEN_DISPATCH` 与 `_PHYSICAL_LAW` 登记 B34/B36/B37/B40/B41。
- `verification_adapters.py`：末尾追加 `_get_batch_b()` 双路兜底导入 + 5 个 `@_register_candidate`（键：`slab_te0_neff_exact` / `rect_wg_te10_fd` / `rect_wg_te20_fd` / `rect_wg_te11_fd` / `fp_cavity_fd`）。
- 账本三处硬编码同步 → (36/3/22/和61)：README（当前账本段 + 双路径口径披露）、CONTRIBUTING（顶部账本块 + 真值块）、ledger smoke docstring。
- `run_count_consistency_smoke`：B 题 33→**38**、末位 B33→**B41**、"B1-B33"→"B1-B41"。
- `run_statistical_anchor_smoke`：硬断言 `expected_b` 由 `range(1,34)` 扩展为 `B1-B33 + [B34,B36,B37,B40,B41]`（**唯一会崩的硬断言，已修**）。
- `run_benchmark_falsifiability_smoke`：`PERTURB_SPEC` 加 5 条反向测试（B34 t / B36 a / B37 a / B40 a / B41 L）、`MIN_INDEPENDENT` 31→**36**。
- 描述性 docstring 同步：`run_l1_agent_smoke` / `run_system_budget_smoke` / `run_empirical_anchor_smoke` / `run_count_consistency_smoke`。

## 4. 验证结果（实跑）

- `run_p0_count_guard_sync_smoke`：**6/6 OK**（README/ledger/CONTRIBUTING 三分类 ≡ 动态真值 36/3/22；`degraded_explicitly_three`=3；反向篡改自检会响）。
- `run_count_consistency_smoke`：**11/11 OK**（B 题 38、末位 B41、"B1-B41" 全部命中）。
- `run_statistical_anchor_smoke`：**34 PASS / 0 FAIL**。
- `run_benchmark_falsifiability_smoke`：**13/13 PASS** · 严格独立 **36** · 降级 3 · 自证桩 22/61 · 全量 61 锚无回归 · `/api/verification_ledger` 三分类 独立36/降级3/自证22 · CLI verified=36/36 · 5 新锚灵敏度均 ≤10%。
- `run_harness.py`：全量回归（见末尾运行记录）。

## 5. 后续批次建议（达 70% 还需 ~23 道）

路径 B 的本质是「用新物理锚堆量」。候选方向（均已确认可落双方法独立、复用已验证 FD 本征/闭式核、避开电容类网格陷阱）：

1. **更多本征模族**：矩形波导 TE01/TE02/TE30/TE21/TE31（闭式 vs 2D FD）、圆柱波导 TE11/TM01（解析 vs 2D FD）。
2. **谐振腔族**：半球/圆柱腔 TE/TM 模式（解析 vs 3D FD）、光子晶体缺陷腔（闭式 vs 2D FDTD，注意判据 D）。
3. **传输线/电路闭式族**：λ/2、λ/4 谐振器、定向耦合器奇偶模（闭式 vs 矩量法/TL 本征）。
4. **量子侧扩展**：更多本征频率/耦合的解析-数值对拍（避免与现有 B9–B27 重复物理）。

⚠️ 诚实边界：每道新锚须满足（a）候选方法学不同源、（b）基线残差 ≫ 1e-12 且 < tol 留余量、（c）反向 10% 必 FAIL、（d）判据 D 适用者真数值收敛。电容类（同轴/双线）已实测因圆形边界网格阶梯误差不可恢复，**放弃**。

## 6. 累计账本（含本批）

- 锚总数：56 → **61**（B1–B41 物理定律 + E1–E10 实证 + S1–S13 系统）
- 三分类：严格独立 31→**36** · 降级量级参考 3 · 自证桩 22（三类和 61）
- 独立率：55.4% → **59.0%**
- 代码位置：`lda/lda_harness/_batch_b_numeric.py`（纯 numpy/scipy 数值核）
