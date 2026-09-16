# LDA 独立率冲刺 · 路径 B-7 扩基报告

- **日期**：2026-09-17
- **版本**：v0.9.87（本地；提交 `79158d9`，已推 gitee + github）
- **批次**：Batch B-7（B121-B136，16 道严格独立锚）
- **冲刺腿**：腿①「扩基加锚」——纯内部确定性扩基，继续稀释 terminal Tier-1 权重，**缓抬独立率天花板**
- **结论**：独立率 **84.8%（117/138）→ 86.4%（133/154）**；天花板 **91.3% → 92.2%**；零物理判据改动、零 tol 放宽、零判决行为改动、零新增 CI smoke（CI core 仍 178 条）。

---

## 1. 目标与依据

用户指令（2026-09-17）：「**腿①继续加锚（纯内部、最稳）**」。

- terminal Tier-1 = **12 道**（B17/B18/S1-S6/S9-S12），按设计永不升，独立率上限 = (N−12)/N。
- 加锚使 N 增大而 terminal 不变 ⇒ 天花板缓抬：K=16 ⇒ (154−12)/154 = **92.2%**。
- 关键纪律：**only 真 strict 才抬指标**。新锚若落成 `self_certified`，会被棘轮 `MAX_SELF_CERTIFIED=18`（只减不增）直接拦死。故本批 16 道全部按「解析闭式 golden × 方法学不同源真实数值法」范式构造，逐道过 C1–C5 + 判据 D。

---

## 2. 设计范式（同 B-1..B-6）

每道锚 = 一个**确定性解析闭式** 对拍 一个**方法学不同源的真实数值法**：

- 残差 = **离散化误差**（持久、随参数变化、判据 D 响应、反向扰动 FAIL）；
- **不是**代数恒等（B28 血案）、**不是**纯数值误差沉底（B10 血案）；
- 数值核纯 numpy/scipy（C 级自主，零商业依赖）：`lda/lda_harness/_batch_b7_numeric.py`。

🔴 **本批前置纪律（承接 B-6 血案）**：全批**弃用** `scipy.linalg.eigh(subset_by_index=...)`，一律「Kronecker 和分解」或「较小网格 + 全量 `np.linalg.eigvalsh` / 复用 B-5 全量 `eigh` 径向核」，从机制上杜绝子集选择 off-by-one。

---

## 3. 四族物理锚（B121-B136）

| 锚 | 物理对象 | golden（解析闭式） | 候选（数值法） | tol |
|---|---|---|---|---|
| B121–B124 | Morse 势双原子分子振动 n=0..3 | E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e)，ω=a√(2D_e/μ) | 1D FD 薛定谔本征（V=D_e(1−e^{−a(r−r_e)})²） | 0.01 eV |
| B125–B128 | 二维各向异性谐振子 (0,0)/(1,0)/(0,1)/(1,1) | E=ℏω_x(n_x+½)+ℏω_y(n_y+½) | 2D FD 本征（两 1D HO FD 本征值 Kronecker 和） | 0.01 eV |
| B129–B132 | 三维长方体势阱 (1,1,1)/(2,1,1)/(1,2,1)/(1,1,2) | E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²) | 3D FD 拉普拉斯本征（三路 1D Dirichlet Kronecker 和） | 0.01 eV |
| B133–B136 | 类氢激发态 H 4s / He⁺ 4d / Li²⁺ 4f / H 5d | E_n=−RYDBERG·Z²/n² | 径向 FD 薛定谔本征（复用 B-5 核，含高 l 离心项） | 0.01 eV |

**族选择依据**：B-1..B-6 已覆盖 1D/2D/3D 方势阱、1D 谐振子、有限深阱、Pöschl-Teller、势垒/δ/阶跃/Kronig-Penney、氢径向(n≤3)、3D 各向同性 HO、刚性转子、三角阱、球形势阱、矩形/圆波导、Bragg、FP 腔、Marcatili。B-7 选取 **Morse 势（非谐）/2D 各向异性谐振子/3D 长方体势阱** 三个**全新族** + **类氢 n=4/5 高激发态** 一个自然扩展（B-5 止于 n=3），无重复。

**接线四件套**（同 B-5/B-6）：

1. `lda/lda_harness/benchmarks.py`：import + B121-B136 字典（`golden_fn` 引函数对象、`candidate` 引注册串）+ `BENCHMARK_ORDER` 追加；
2. `lda/lda_harness/golden.py`：import + `_GOLDEN_DISPATCH` + `_PHYSICAL_LAW`（**双表同登铁律**）；
3. `lda/lda_harness/verification_adapters.py`：`_get_batch_b7()` 双路兜底 + 16× `@_register_candidate`；
4. `lda/lda_harness/_batch_b7_numeric.py`：数值核。

---

## 4. 验证证据（真实 harness 路径）

脚本 `_b7_verify.py`（走 `build_harness_specs` + `BENCHMARK_CANDIDATES` + `golden_value`/`golden_with_source`，即 `IndependentCandidateRouter` 同源路径）逐道核对四项：

| 锚 | strict | src | \|cand−golden\| | within(tol) | nonzero | 判据 D |
|---|---|---|---|---|---|---|
| B121 | ✓ | physical-law | 2.611e-05 | ✓ | ✓ | ✓ |
| B122 | ✓ | physical-law | 1.279e-04 | ✓ | ✓ | ✓ |
| B123 | ✓ | physical-law | 3.256e-04 | ✓ | ✓ | ✓ |
| B124 | ✓ | physical-law | 6.134e-04 | ✓ | ✓ | ✓ |
| B125 | ✓ | physical-law | 2.832e-05 | ✓ | ✓ | ✓ |
| B126 | ✓ | physical-law | 7.553e-05 | ✓ | ✓ | ✓ |
| B127 | ✓ | physical-law | 9.441e-05 | ✓ | ✓ | ✓ |
| B128 | ✓ | physical-law | 1.416e-04 | ✓ | ✓ | ✓ |
| B129 | ✓ | physical-law | 1.297e-05 | ✓ | ✓ | ✓ |
| B130 | ✓ | physical-law | 1.278e-04 | ✓ | ✓ | ✓ |
| B131 | ✓ | physical-law | 6.400e-05 | ✓ | ✓ | ✓ |
| B132 | ✓ | physical-law | 4.168e-05 | ✓ | ✓ | ✓ |
| B133 | ✓ | physical-law | 5.001e-06 | ✓ | ✓ | ✓ |
| B134 | ✓ | physical-law | 1.486e-05 | ✓ | ✓ | ✓ |
| B135 | ✓ | physical-law | 1.026e-05 | ✓ | ✓ | ✓ |
| B136 | ✓ | physical-law | 2.071e-04 | ✓ | ✓ | ✓ |

**16/16 ALL_PASS**。worst-case 残差 = B124 的 6.134e-04 eV（占 tol 窗口 ~6%），留 ~16× 余量。判据 D 参数：Morse `D_e×1.1`、2D-HO `ω_x×1.1`、3D 盒 `L_x×1.1`、类氢 `Z×1.1` —— golden 与 cand 均同步偏移且仍在 tol 内。

---

## 5. 计数护栏（七道全绿）

| 护栏 | 结果 |
|---|---|
| `run_p0_count_guard_sync_smoke.py`（README / CONTRIBUTING / ledger docstring 三面同步） | OK（6 tests） |
| `run_count_consistency_smoke.py`（引擎/包/题库/CI core） | OK（11 tests） |
| `run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点） | 4/4 PASS（133/3/18） |
| `run_self_certified_lock_smoke.py`（棘轮 ≤18 + 锁原因） | 4/4 PASS（`{t2_blocked:6, terminal_tier1:12}`） |
| `run_maturity_baseline_smoke.py`（VMM 底线 6 条） | PASS（M5 口径 133/3/18，和=154） |
| `run_webui_verification_ledger_smoke.py`（端点 + 前端接线） | 15 PASS / 0 FAIL |
| `run_statistical_anchor_smoke.py`（题库计数 + 统计一致性） | 34 PASS / 0 FAIL |

---

## 6. 诚实边界与血案

1. **类氢族 `default_params` 口径**：`golden_value(bid, params)` 会把 `default_params` 全量 `**` 展开传给 golden 函数，故类氢族 `default_params` 只保留 `{"Z": ...}`（`l`/`n_r` 收在适配器内硬编码，与 B-5 同构）——初版误写 `{"Z","l","n_r"}` 会让 `golden_b133(**params)` 抛 `TypeError`（「标签≠行为」复发路径），已在接线期修正。
2. **Morse 势残差随 n 递增（2.6e-5 → 6.1e-4 eV）**：高激发态波函数更延展、对网格分辨率更敏感，属正常离散化收敛行为；16× 余量充裕，未放宽 tol。
3. **Morse 束缚态数 ~82**：本批仅取最低 4 态（n=0..3），与解析谱一一对应，不存在「取到准连续态」风险（首个准连续态在 E≈D_e=11.2 eV，与 0.13~0.92 eV 区间相距极远）。
4. **类氢 FD 残差极小（5.0e-6 eV）**：复用 B-5 已验证径向核（全量 `eigh`），残差非零、判据 D 响应（Z×1.1 同步偏移），为真实离散化误差，非代数恒等、非沉底。

---

## 7. 账本变更

| 项 | 变更前 | 变更后 |
|---|---|---|
| 版本 | v0.9.86 | **v0.9.87** |
| 严格独立 | 117 | **133** |
| 降级量级参考 | 3 | 3 |
| 自证桩 | 18 | 18（棘轮 ≤18 保持） |
| 题数 N | 138 | **154** |
| 独立率 | 84.8% | **86.4%** |
| 天花板 | 91.3% | **92.2%** |
| B 题数 | 115（B1-B120） | **131（B1-B136）** |
| CI core | 178 | 178（不变） |

---

## 8. 提交与推送

- commit：`79158d905fc41bd0601501f6d85ab287de488557`（12 files changed, +815 / −23）
- push：gitee `05fdcc5..79158d9`（exit=0）、github `05fdcc5..79158d9`（直连 128 → SOCKS5 兜底 exit=0）
- **部署**：本次**未部署**（用户未授权）；部署待明确指令（`remote_deploy.py --expect-head <commit>`）。

---

## 9. 下一步候选

- **腿①续**：仍最稳——继续选新物理族（如二维量子圆盘 Bessel / 有限深球形势阱超越方程 / 非谐振子 x⁴ 微扰 / Landau 能级）扩基，天花板继续缓抬。
- **腿②degraded 3→strict**：纯内部，存量已明确（B21 余量 ~77× 最有望先回）。
- **腿③T2 解锁 6 道**：外部 KPI 阻塞（E1/E3-E7），需 MPW 实测回流。
