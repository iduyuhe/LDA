# LDA 独立率冲刺 · 路径 B-6 扩基报告

- **日期**：2026-09-16
- **版本**：v0.9.86（本地；提交 `b8558ee`，已推 gitee + github）
- **批次**：Batch B-6（B105-B120，16 道严格独立锚）
- **冲刺腿**：腿①「扩基加锚」——纯内部确定性扩基，稀释 terminal Tier-1 权重，**缓抬独立率天花板**
- **结论**：独立率 **82.8%（101/122）→ 84.8%（117/138）**；天花板 **90.2% → 91.3%**；零物理判据改动、零 tol 放宽、零判决行为改动、零新增 CI smoke（CI core 仍 178 条）。

---

## 1. 目标与依据

用户指令（2026-09-16）：「**腿①再加锚稀释 terminal：最稳，(122+K−12)/(122+K) 缓抬天花板，纯内部确定性扩基**」。

- terminal Tier-1 = **12 道**（B17/B18/S1-S6/S9-S12），按设计永不升，独立率上限 = (N−12)/N。
- 加锚使 N 增大而 terminal 不变 ⇒ 天花板缓抬：K=16 ⇒ (138−12)/138 = **91.3%**。
- 关键纪律：**only 真 strict 才抬指标**。新锚若落成 `self_certified`，会被棘轮 `MAX_SELF_CERTIFIED=18`（只减不增）直接拦死。故本批 16 道全部按「解析闭式 golden × 方法学不同源真实数值法」范式构造，逐道过 C1–C5 + 判据 D。

---

## 2. 设计范式（同 B-1..B-5）

每道锚 = 一个**确定性解析闭式** 对拍 一个**方法学不同源的真实数值法**：

- 残差 = **离散化误差**（持久、随参数变化、判据 D 响应、反向扰动 FAIL）；
- **不是**代数恒等（B28 血案）、**不是**纯数值误差沉底（B10 血案）；
- 数值核纯 numpy/scipy（C 级自主，零商业依赖）：`lda/lda_harness/_batch_b6_numeric.py`。

---

## 3. 四族物理锚（B105-B120）

| 锚 | 物理对象 | golden（解析闭式） | 候选（数值法） | tol |
|---|---|---|---|---|
| B105–B110 | 刚性转子转动能级 J=1..6 | E_J=ℏ²J(J+1)/(2I) | 关联 Legendre 方程 FD 本征 λ→J(J+1) | 0.01 eV |
| B111–B114 | 二维无限方势阱 (1,1)/(2,1)/(1,2)/(2,2) | E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²) | 2D FD 拉普拉斯本征（Kronecker 和分解） | 0.01 eV |
| B115–B117 | 量子三角势阱 n=1/2/3（V=eFx） | E_n=(ℏ²(eF)²/2m_e)^{1/3}·ζ_n（Airy 零点） | 1D 斜坡势 FD 薛定谔本征 | 0.01 eV |
| B118–B120 | 三维无限球形势阱 (l,n)=(0,1)/(1,1)/(2,1) | E_nl=x_nl²ℏ²/(2mR²)（球 Bessel 零点） | 3D 径向 FD 薛定谔本征 | 0.01 eV |

**接线四件套**（同 B-5）：

1. `lda/lda_harness/benchmarks.py`：import + B105-B120 字典（`golden_fn` 引函数对象、`candidate` 引注册串）+ `BENCHMARK_ORDER` 追加；
2. `lda/lda_harness/golden.py`：import + `_GOLDEN_DISPATCH` + `_PHYSICAL_LAW`（**双表同登铁律**）；
3. `lda/lda_harness/verification_adapters.py`：`_get_batch_b6()` 双路兜底 + 16× `@_register_candidate`；
4. `lda/lda_harness/_batch_b6_numeric.py`：数值核。

---

## 4. 验证证据（真实 harness 路径）

脚本 `_b6_verify.py`（走 `IndependentCandidateRouter` + `golden_value` + `BENCHMARK_CANDIDATES`）逐道核对四项：

| 锚 | strict | \|cand−golden\| | within(tol) | nonzero | 判据 D |
|---|---|---|---|---|---|
| B105 | ✓ | 3.251e-06 | ✓ | ✓ | ✓ |
| B106 | ✓ | 5.419e-06 | ✓ | ✓ | ✓ |
| B107 | ✓ | 7.587e-06 | ✓ | ✓ | ✓ |
| B108 | ✓ | 9.756e-06 | ✓ | ✓ | ✓ |
| B109 | ✓ | 1.192e-05 | ✓ | ✓ | ✓ |
| B110 | ✓ | 1.409e-05 | ✓ | ✓ | ✓ |
| B111 | ✓ | 2.640e-05 | ✓ | ✓ | ✓ |
| B112 | ✓ | 3.432e-04 | ✓ | ✓ | ✓ |
| B113 | ✓ | 1.056e-04 | ✓ | ✓ | ✓ |
| B114 | ✓ | 4.224e-04 | ✓ | ✓ | ✓ |
| B115 | ✓ | 1.778e-06 | ✓ | ✓ | ✓ |
| B116 | ✓ | 5.436e-06 | ✓ | ✓ | ✓ |
| B117 | ✓ | 9.914e-06 | ✓ | ✓ | ✓ |
| B118 | ✓ | 1.834e-08 | ✓ | ✓ | ✓ |
| B119 | ✓ | 4.871e-08 | ✓ | ✓ | ✓ |
| B120 | ✓ | 2.173e-07 | ✓ | ✓ | ✓ |

**16/16 ALL_OK**。worst-case 残差 = B114 的 4.224e-04 eV（占 tol 窗口 ~4%），留 ~20× 余量。

---

## 5. 计数护栏（六道全绿）

| 护栏 | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke.py`（README / CONTRIBUTING / ledger docstring 三面同步） | OK（6 tests） |
| `run_count_consistency_smoke.py`（引擎/包/题库/CI core） | OK（11 tests） |
| `run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点） | 4/4 PASS（117/3/18） |
| `run_self_certified_lock_smoke.py`（棘轮 ≤18 + 锁原因） | 4/4 PASS（`{t2_blocked:6, terminal_tier1:12}`） |
| `run_maturity_baseline_smoke.py`（VMM 底线 6 条） | PASS（M5 口径 117/3/18） |
| `run_webui_verification_ledger_smoke.py`（端点 + 前端接线） | 15 PASS / 0 FAIL |

---

## 6. 诚实边界与血案

1. **`scipy.linalg.eigh(subset_by_index=[1,M])` 在大矩阵上 off-by-one（本会话血案）**：2D 方势阱（Nx=Ny=120 ⇒ 14400×14400 巨阵）与三角势阱（N=2400）用 `subset_by_index` 取低本征，实测**返回第 2 低本征而非最低** ⇒ 候选命中错模（box(1,1) cand=0.751955 实为 (1,2) 模；tri n=1 cand=0.132808 实为 n=2 模），且**静默不报错**。修复：2D 阱改用 **Kronecker 和分解**（1D 全量 eigvalsh 后组合，精确且远小于巨阵）；三角阱/球阱改用**较小网格 N + 全量 `np.linalg.eigvalsh`**（三角 N=900、球 N=2200，全量取升序）。修后 16/16 命中正确模。
2. **三角势阱首次差 1e13 倍**：势能 V=Fx 漏乘基本电荷 e（应为 V=eFx 焦耳），已加 `E_CHARGE` 常量修正。
3. **球形势阱残差极小（~1e-7 eV）**：FD 收敛快属正常；残差非零、判据 D 响应（R×1.1 同步偏移），为真实离散化误差，非代数恒等、非沉底。

---

## 7. 账本变更

| 项 | 变更前 | 变更后 |
|---|---|---|
| 严格独立 | 101 | **117** |
| 降级量级参考 | 3 | 3 |
| 自证桩 | 18 | 18（棘轮 ≤18 保持） |
| 题数 N | 122 | **138** |
| 独立率 | 82.8% | **84.8%** |
| 天花板 | 90.2% | **91.3%** |
| B 题数 | 99（B1-B104） | **115（B1-B120）** |
| CI core | 178 | 178（不变） |

---

## 8. 提交与推送

- commit：`b8558ee872d8ed29c67a34131c1ddda489b26825`（10 files changed, +704 / −21）
- push：gitee `35189be..b8558ee`（exit=0）、github `35189be..b8558ee`（直连 128 → SOCKS5 兜底 exit=0）
- **部署**：本次**未部署**（用户未授权）；部署待明确指令（`remote_deploy.py --expect-head b8558ee`）。
