# LDA · 反向偏压简化模型局限（已知缺口 · 诚实边界）

> **结论一句话**：本库 2D 漂移-扩散电流内核 `solve_pn_junction_2d_bias`（T1-B-W4）**仅在正偏 / 近平衡（V ≥ 0）经实测验证可用**；**反偏（V < 0）下非物理、不可用**，输出带 `reverse_bias_unvalidated=True` 诚实标记，**绝不参与任何方法学比对或死标量判决**。

---

## 1. 受影响代码

| 项 | 位置 |
|---|---|
| 偏压输运主入口（含 Dirichlet BC 设定与 Gummel 迭代） | `lda/lda_solver/drift_diffusion_2d.py` → `solve_pn_junction_2d_bias` |
| 稳态连续性求解（**无复合-产生项 G=R=0**） | `drift_diffusion_2d.py` → `_solve_continuity_sg` |
| 接触少数载流子 **Dirichlet BC**（低注入理想二极管律 `n_i²/N_A·exp(V/V_T)`） | `solve_pn_junction_2d_bias` 第 460–467 行 |
| 每轮由 n/p **反推准费米势**再解泊松（反偏下正反馈发散点） | `solve_pn_junction_2d_bias` 第 482–483 行 |
| 运行时诚实标记 | 返回 dict 字段 `reverse_bias_unvalidated`（V<0 时 `True`） |

---

## 2. 症状（实测，SI，默认突变结 N_A=1e23 / N_D=1e22 m⁻³，nx=ny=50）

| 偏压 V | 模型 I(V) | 理想二极管饱和电流 I_s | 判读 |
|---|---|---|---|
| +0.0 V | 2.6e-13 A | 0 | 平衡 ✓ |
| +0.3 V | 6.6e-07 A | 短二极管闭式 6.4e-07 A | **正偏吻合 ✓（已验证）** |
| +0.6 V | 7.4e-02 A | 短二极管闭式 7.0e-02 A | **正偏吻合 ✓（已验证）** |
| −0.5 V | **−1.4e-03 A** | −5.8e-12 A | **反偏：约 2.4×10⁹ 倍饱和电流、且完全不饱和 ✗** |
| −1.0 V | **−3.5e+02 A** | −5.8e-12 A | 非物理巨流 ✗ |
| −2.0 V | −3.6e+03 A | −5.8e-12 A | conv=False（Gummel 发散）✗ |
| −3.0 V | −6.5e+03 A | −5.8e-12 A | conv=False（Gummel 发散）✗ |

> 物理上二极管反偏电流应**迅速饱和**于 I_s（≈ nA 量级）；本模型在反偏下给出**随 |V| 单调放大的非物理巨流**，且在 |V|≳1V 时迭代不收敛（`converged=False`，空穴密度越界 `p_max>N_A`）。

---

## 3. 根因（物理 + 数值两层）

### 3.1 物理层：模型缺失反向电流的物理来源
- 稳态连续性方程取 **G = R = 0（无复合、无产生）**。
- 真实二极管的**反向饱和电流**由**耗尽区内的载流子产生（generation）**与少数载流子向耗尽边扩散共同提供。本模型**完全没有 R-G 项**，在耗尽区没有"电流源"，反向电流无物理来路。
- 接触少数载流子被 **Dirichlet BC 钉在低注入理想二极管律** `n_i²/N_A·exp(V/V_T)`。反偏时 `exp(V/V_T) → 0`，接触少数载流子密度**坍塌至 0**——这正是错误边界条件：物理上反偏饱和电流由**准中性区少数载流子扩散到耗尽边**决定（一固定饱和值，与 V 无关），而非由接触处密度趋近于 0 决定。

### 3.2 数值层：Gummel 反偏正反馈发散
- 每轮外迭代由当前 n/p **反推准费米势** `φ_n = φ − V_T·ln(n/n_i)`、`φ_p = φ + V_T·ln(p/n_i)`（第 482–483 行），再解非线性泊松。
- 反偏下接触 n/p → 近 0 ⇒ `ln(n/n_i)` 趋于 −∞ ⇒ `φ_n/φ_p` 剧烈外推 ⇒ 泊松解出的电荷分布非物理（`p_max>N_A`）⇒ 下一轮 n/p 更畸变 ⇒ **正反馈不收敛**。
- 不收敛时终端电流由畸变剖面算出，量级失控（数百~数千安）。

> 两层叠加：**即使迭代收敛，反偏电流也不饱和（缺 R-G 源）；不收敛时直接非物理**。这是简化模型的固有局限，不是 bug 可"修一行"解决。

---

## 4. 已验证可用区间（诚实边界）

| 区间 | 状态 | 说明 |
|---|---|---|
| **V ≥ 0（正偏 / 平衡）** | ✅ 已验证 | V=+0.3/+0.6 与短二极管闭式 I_s·(exp(V/V_T)−1) 吻合（误差 < 2×，量级正确）；W4 的 2D 平衡收敛、W5 探测器带宽、W6 APD 均建立在此基础上 |
| **V < 0（反偏）** | ❌ 不可用 | 非物理巨流 / 不收敛；见 §2、§3 |

---

## 5. 本项目如何规避（已落地的正确做法）

所有**已验证的反偏分析都刻意绕开本 2D 电流求解器的反偏路径**：

- **MZM Vπ 耗尽（W5/U5）**：用 **1D 平衡/耗尽内核 + n_i 等价缩放**（`mzm_vpi_depletion_true.py` 的 `t1_biased_depletion_profile`）只取**耗尽场剖面 n(x,V)/p(x,V)**，再接 Soref-Bennett 幂律 → 模式重叠 → Vπ·L 闭式；**从不在此 2D 求解器上施反偏求电流**。
- **APD 雪崩（W6）**：反偏三角场用 Sze 闭式 W(V)（与 T1 电学内核同源），电离积分走 van Overstraeten–de Man 解析系数，**独立于本 2D 电流求解器**。
- **探测器带宽（W5）**：耗尽场由 1D 内核取，渡越/RC 用闭式 + 数值 v(E) 漂移，**不含反偏电流求解**。

⇒ 反向偏压局限**不影响任何已发布锚题的诚实性**：那些锚题要么在正偏验证区间，要么从设计上不依赖本 2D 反偏电流解。

---

## 6. 升级路径（若要支持反偏，须做之一）

> 🔴 **2026-09-23 排序（杜先生裁定 ③）**：以下四条**不是并列选项**，而是**带优先级的施工序**
> —— **② 修反偏边界条件 → ① 加 SRH / 产生-复合项 → ④ 外部 ORACLE 标定（仅作最后手段）**。
> 理由：② 是**外科级**修复（反偏电流「无物理来路」的根因正是 BC 把接触少数载流子钉在
> `n_i²/N_A·exp(V/V_T)`，反偏时该式 → 0）；① 是**补物理源**（耗尽区载流子产生）；
> ④ 依赖外部真值、须走**已签字标定窗口**，成本最高而可证伪性最弱 ⇒ 只在 ①② 都做不成时才用。

1. **加 SRH / 产生-复合项**（第 ①步）：连续性方程改 `∇·J_n = q(R−G)`、`∇·J_p = −q(R−G)`，耗尽区引入载流子产生率 G（与电场相关的隧道/雪崩阈值以上才开启），为反向电流提供物理源。
2. **修正反偏边界条件**（第 ②步 · **优先**）：耗尽边少数载流子取**零边界（耗尽近似）**而非接触处 `exp(V/V_T)` 钉值；准中性区用扩散方程解饱和电流，使 I 在反偏下自然饱和于 I_s。
3. **限制使用区间**（现状兜底）：在 `solve_pn_junction_2d_bias` 入口对 `V < 0` 直接 `raise` 或返回 `converged=False` + 明确错误，从调用层面禁止反偏误用（当前选择**仅标记** `reverse_bias_unvalidated=True`，保留调用方知情权）。
4. **改用经反向标定的外部 ORACLE**（第 ④步 · **仅最后手段**；DEVSIM / Sentaurus，B 级）：同几何同边界双向标定，**仅在已签字标定窗口内借真值**——窗口契约见 §7 与
   `lda/lda_harness/real_machine_oracle.py`（`CalibrationWindow` + `honest_tier`），仍须遵守「LLM 不进判决路径 / T1 输出不作 ORACLE」红线。

---

## 7. 机器可发现的护栏

- `solve_pn_junction_2d_bias(V)` 对 **V < 0** 返回 `"reverse_bias_unvalidated": True`。任何消费方**必须**检查该标志；为 `True` 时 I(V) 视为未验证、不得进入判决回路。
- 模块顶部 docstring 含 🔴 反向偏压局限横幅，指向本文档。
- 护栏 smoke：`lda/run_t1_reverse_bias_limitation_smoke.py` 断言 ① 正偏 V=+0.6 收敛且电流符号/量级正确；② 反偏 V=−1.0/−2.0 必带 `reverse_bias_unvalidated=True`（防止未来重构静默移除诚实标记）。
- 🔴 **反偏路径 ④（外部 ORACLE 标定）的窗口契约已机器化（2026-09-23 · 裁定 ②）**：`lda/lda_harness/real_machine_oracle.py` 的 `CalibrationWindow`（含**人类签字人** `signer` / `signed_date` / `source_ref`）与 `SIGNED_CALIBRATION_WINDOWS`（**当前空表** ⇒ 一律视作未标定）。凡在 `honest_tier` 声称 `oracle-calibrated[...]` 的注册，必须落在**已签字**窗口内，否则按 W1/W2/W3/W4/**W5 超窗** raise；护栏 = `lda/run_real_machine_oracle_contract_smoke.py`（14 组判据，含 7 条反例）。
- 🔴 **仿真值不作 golden（2026-09-23 · 裁定 ①）**：`OracleKind` 区分「实测事实」（foundry / 流片 / A 级公开实测）与「仿真值」（**商业求解器场级解** / 自研内核解）；后者**注册即 raise**，且「二级 golden」机制整体禁用。这条直接约束任何「拿 Sentaurus / DEVSIM 场级解当反偏 golden」的捷径。

---

## 8. 参考

- Sze, *Physics of Semiconductor Devices*, §2.2（突变 p-n 结耗尽近似 / 理想二极管律）。
- Selberherr, *Analysis and Simulation of Semiconductor Devices*（Scharfetter–Gummel 离散、Gummel 迭代、R-G 项）。
- 逐日日志 `D:\agent_LDA\.workbuddy\memory\2026-09-13.md`（W6 APD 段记录 2D 内核反偏 |V|>1V 发散实测）。
