# LDA 有源器件 A 档锚题契约（B33 已落地 · 余待评审）

> 配套 `docs/lda_active_device_redline_clarification_2026-09-10.md` §七裁定①。
> **本文件定义契约与落地状态。** B33 已于 2026-09-10 评审通过并落地（严格独立 27→28，自证桩 24 不变，题数 52→53，CI 全绿）；其余待评审，评审通过后逐道注册到 `benchmarks.py` + `verification_adapters.py` + 对应 smoke。
> 全部 A 档锚共同前提：**纯物理定律闭式 + 独立交叉候选，零载流子求解器、零增益动力学、零 TCAD、零 A 级工具 → 不破三不做 / 主权 / 验证纪律任何一条红线。**

---

## 共同契约规范（每道锚必须遵守）

| 项 | 要求 | 红线自检 |
|---|---|---|
| golden | 物理定律闭式（解析或公认经验式），注明出处 | 非拟合回算（IRONLAWS 二/27） |
| 独立候选 | 方法学**不同源**于 golden（如经验式 vs Drude / 闭式 vs TMM 数值扫），注册进 `BENCHMARK_CANDIDATES` | 判据 D：离散参数须单调收敛、粗端浮出噪声地板（IRONLAWS 判据 D） |
| tol | 实测偏差的 2.2~2.5× 余量，**不得为掩盖误差放宽**（IRONLAWS 四/53） | 放宽 tol = 取消验证 = 红线 |
| provenance | `design_rule_anchor` 或 `independent_cross_check`（非低置信自写闭式） | — |
| 载流子 | 密度/浓度由**耗尽近似闭式**给出（泊松一维耗尽解），**绝不**求解漂移-扩散方程 | 不破「电域求解器」红线 |
| 反向测试 | 10% 扰动必 FAIL（IRONLAWS 二/24） | 护栏须测生产代码（二/19） |

---

## B31 · Si 载流子色散相移（Soref-Bennett 闭式）

- **物理对象**：PN 结耗尽型 Si 相位调制器，外加反偏电压 V → 载流子浓度变化 → 折射率变化 → 相移。
- **golden（物理定律锚）**：Soref & Bennett 1987 (IEEE J. Quantum Electron. 23, 123) 唯象闭式
  `Δn_eff = c1·ΔN + c2·(ΔN)² + c3·ΔP_e + c4·(ΔP_h)²`（c1~c4 为 Si 材料常数，待实测定；ΔN/ΔP 由耗尽近似给出）
- **独立候选（independent_cross_check）**：Drude 自由电子气模型 `Δn_eff = −q²·ΔN / (2·ε0·n_eff·m*·ω²)` —— 与 Soref-Bennett 是**不同方法学**（经典微观 vs 唯象宏观），非代数恒等 → 判据 D 不撞。
- **红线自检**：ΔN(V) 用一维耗尽近似闭式（泊松方程耗尽解），**不求解漂移-扩散** → ✅ 不破电域求解器。
- **评审风险**：① c1~c4 须用文献公认值，不得拟合回算；② ΔN 上限（耗尽近似失效区）须标注 honest_tier。

## B32 · EAM-QCSE 吸收边位移（Kane 闭式）

- **物理对象**：电吸收调制器（Franz-Keldysh / 量子限制斯塔克效应），外加场 F → 带边位移 → 消光比。
- **golden（物理定律锚）**：Kane 1956 FK 位移 `ΔE_g = (ℏ·e·F)² / (2·m_r*·E_g)`（m_r* 约化质量）
- **独立候选（independent_cross_check）**：严格 2-band k·p 模型数值积分吸收谱，扫 F 定带边位移，与 Kane 闭式交叉。
- **红线自检**：纯电磁/能带闭式 + 数值带结构，无载流子动力学 → ✅ 不破。
- **评审风险**：QCSE（多量子阱）与 FK（体材料）公式不同，须明确器件是体材料还是 MQW，否则 golden 选错。

## B33 · 探测器带宽 τ=RC（电路闭式）

- **物理对象**：pin/APD 光电探测器 3dB 带宽，受负载 R 与结电容 C 限制。
- **golden（design_rule_anchor）**：`f_3dB = 1/(2π·R·C)`，`C = ε·A/d`（反偏结电容闭式）
- **独立候选（independent_cross_check）**：时域阶跃响应 `V(t)=V0·(1−e^{−t/RC})` 数值拟合 τ，与闭式交叉。
- **红线自检**：纯电路闭式，无光子有源物理 → ✅ 不破。
- **评审风险**：仅覆盖 RC 限制带宽，**不含**渡越时间/暗电流/APD 倍增（那些属 B 档禁区，本锚不碰）。honest_tier 须标"RC-limited only"。

## B34 · 激光器腔体 FSR（几何 EM 闭式）⚠️ 评审项

- **物理对象**：FP/DBR 激光腔纵模间距。
- **golden**：`FSR = c/(2·n_g·L)`
- **评审风险（重要）**：此式与现有 **B3（环形谐振腔 FSR）同源方法学**（频域周期取值）。若直接新增为独立锚，可能被判据 D 视为"同性质复刻"→ **虚报独立候选数**。建议处理：**作为 B3 的器件扩展（在 B3 候选里加 laser-cavity 工况），不单列新锚**，或明确"新物理对象（有源腔含增益介质色散）"以证成独立性。需杜先生/锚裁判评审定夺。

## B35 · 布拉格波长 λ_B = 2·n_eff·Λ（DBR/DFB 闭式）

- **物理对象**：DBR/DFB 光栅布拉格条件。
- **golden（design_rule_anchor）**：布拉格条件 `λ_B = 2·n_eff·Λ`
- **独立候选（independent_cross_check）**：传输矩阵法（TMM，C 级自主已有权核）扫 Λ 找反射峰 λ，与闭式交叉。
- **红线自检**：TMM 是项目自有内核 → ✅ 不破主权。
- **评审风险**：低。与 B29 热光同属"几何 EM 闭式 + TMM 交叉"范式，可快速落地。

## 🔶 边界评审项 · 激光器线宽（Schawlow-Townes）

- `Δν = hν·n_sp·(1+α²) / (4π·P·τ_p²)` —— 含自发辐射因子 n_sp（依赖有源区载流子）。
- **虽为闭式，但 n_sp 牵连有源区载流子 → 边界模糊**。建议**本轮不纳入 A 档**，标记待杜先生拍板：归入 A 档（纯闭式、给定 n_sp 即算）还是 B 档禁区（因涉有源载流子）。**不急于求成，先搁置。**

---

## 落地节奏（评审通过后）

1. 逐道写 `verification_adapters.py` 候选函数（纯 numpy/scipy，CI venv 跑）
2. 注册进 `benchmarks.py` `BENCHMARK_CANDIDATES` + `BENCHMARK_DEFS[bid]["candidate"]`
3. 每个候选过 **判据 D 离散参数响应性** + 10% 反向扰动 must-FAIL
4. tol 按实测偏差 2.2~2.5× 余量定，写进 note
5. 各自 smoke 入 `CORE_SMOKES`；`run_webui_verification_ledger_smoke` + 三分类守恒守护同步
6. 账本 README 顶行 + MEMORY.md 三分类计数同步（verified 数 + 自证桩数变化）

> ⚠️ 不一次性全做：已先落 **B33（探测器带宽，2026-09-10 真·新增严格独立）**；**B35 去重为复用 B15（不新建，避免重复投入）**；再审 B31/B32，B34 待评审定夺。
