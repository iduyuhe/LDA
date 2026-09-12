# LDA 自证桩换锚路线细化（≥5 桩 · T2 第3阶段交付物 · 2026-09-13）

> 依据：`docs/self_certified_anchor_inventory.md`（性质分层台账）+ 当前 23 桩现状
> （B2、B11 已先后升 strict）+ T1 内核新能力（W2 1D DD / W4 2D DD / W5 探测器带宽真求解 /
> W6 APD 雪崩输运真求解，v0.9.70–0.9.72）。
> 路线图要求（研发规划 §第3阶段）：「≥5 自证桩换锚路线细化」——本文件即该项交付物。

## 0. 现状与目标

| 分类 | 桩数 | 性质 |
|---|---|---|
| Ⅴ·本就不升（terminal Tier-1） | 12 | 定义/算术/合成校验，永不升，**不列入换锚** |
| Ⅵ·设计规则锚（外部行业共识） | 3 | B5/B6/B7 有外部背书，无需重测，**不列入换锚** |
| Ⅰ·曾错已修 | 1 | B16：待 rib-MMI 严格求解器 |
| Ⅱ·缺外部 ORACLE/数据集 | 7 | B21 + E1/E3-E7：待 ORACLE 通道/实测扩样 |
| Ⅲ/Ⅳ·已升 | 2 | B2（v0.9.66）、B11（v0.9.68）已升 strict，作为范式样本 |

**可换锚候选池 = Ⅰ(1) + Ⅱ(7) = 8 桩**。本路线细化其中 **6 桩**（含 1 桩降级替代），
按「独立性价值 × 工程可行性 × 红线合规」排序，另有 2 桩明确挂起理由。

## 1. 路线总表（6 桩）

| # | 桩 | 物理对象 | 现状 golden | 换锚路线（独立候选） | 判据D 载体 | 工作量 | 风险 | 目标 tier |
|---|---|---|---|---|---|---|---|---|
| U1 | **B16** | MMI 1×2 自映像长度 | Soldano & Pennings 抛物线色散闭式（因子已修 3→9/4） | **复用 v0.9.56 双引擎**：`mmi_eme.py`（EIM+EME 解析传播）与 `fdtd2d_mmi.py`（Yee 时域全场）已知 L 处输出重叠 ⇒ 数值自映像长度（fidelity 峰值位置）；golden 仍是闭式 | EME 模数加密 / FDTD 网格加密 → 峰位收敛单调 | 中（引擎已建，需接 harness 候选 + 峰位提取） | ①峰位提取噪声（sponge 反射）②两引擎共享 2D-EIM 抽象（同源偏差，与 golden 闭式比才算三方独立） | strict（三方：闭式 vs EME vs FDTD） |
| U2 | **E-MMI-1X2-EL（E5）** | MMI 1×2 过量损耗 | 实测 0.05 dB ±0.05（SOI 2.8×27 µm²） | **双引擎交叉验证已建未判**（mmi_eme vs fdtd2d_mmi，v0.9.56 结论「暂不足以判决」）→ 细化：判据改为**双引擎一致性区间**（两法差 < tol 且均落在实测 ±2σ 内 ⇒ 升 external-empirical-verified） | FDTD 网格加密 → excess loss 收敛；EME 模数加密 | 中（需重新跑收敛扫描，峰位 tol 细化） | 数值缺陷与抽象缺陷混杂（须先 U1 定峰位再判损耗） | strict（实证+双引擎） |
| U3 | **E-RING-FSR** | add-drop racetrack FSR | 实测 8.6 nm ±0.1（L=66.8 µm SOI） | **复用 B4/B11 同族谱拟合**：`fdtd2d_ring.py`（v0.9.56 已有）扫 add 口透射谱 → 峰周期拟合 FSR；golden=闭式 FSR=c/(n_g·L_r)；实证=8.6nm | 环 FDTD 网格/时步加密 → 峰周期拟合收敛 | 中大（环形 FDTD 跑谱慢，需参数化 L 扫描） | racetrack 直波段+弯段 n_g 不同 ⇒ golden 需两段加权（文献公式） | strict（实证+数值谱拟合） |
| U4 | **E-GE-PD-RESP** | Ge p-i-n 探测器响应度 | 实测 1.1 A/W ±0.05 | **T1-W5 内核直接换锚**：`detector_bandwidth_true.py` 同族——响应度 R=η·qλ/hc 的 η 由**载流子收集效率数值解**替代标称 η=0.8：耗尽区场剖面 E(x)（T1 电学内核）+ 光生载流子输运（W5 漂移模块）⇒ 收集效率 η_col；R_cand = η_col·qλ/hc | 载流子数/时步加密 → η_col 收敛 | 小中（W5 模块复用，几何参数化） | Ge 材料参数（文献值）；探测区几何假设 | strict（实证+T1 内核） |
| U5 | **E-MZM-VPI-18 / E-MRM-VPI-098** | MZM/MRM 载流子耗尽 Vπ·L | 实测 1.8 V·cm ±0.2（MZM） | **T1-W4 2D DD 内核换锚**：p-n 结耗尽电荷 Q_dep(V)（2D Gummel 数值）⇒ dQ/dV ⇒ C_j(V) ⇒ Vπ·L = ...·C_j/(d n_eff/dN)（Soref-Bennett B31 系数，文献）⇒ 与实测 1.8 比对 | 2D 网格加密 → Q_dep/C_j 收敛（W4 smoke 已有） | 中（W4 内核复用，需接 B31 系数与实测锚） | Soref-Bennett 系数适用域（1e17-1e20）；MZM 掺杂剖面未公开（须文献典型值，诚实标注） | strict（实证+T1 内核+文献系数） |
| U6 | **E1/E3/E4（量子 T1·Q 系列）→ 降级替代：E-Q-TTRANS-T1** | 2D Ta transmon T1=300µs | 实测 300 µs ±50 | **不改锚，改判据**：量子 T1 属 T2 工艺真值禁区边沿（介质损耗 tanδ 是工艺参数）→ 判据从「数值解出 T1」降级为「能量弛豫时间量级带判定」（1σ 带内 = PASS），诚实标注 honest_tier=order-of-magnitude；**换锚推迟到 QEDA 数值核（T1 量子区）立项后** | 无判据D（量级带无收敛性） | 小（改 harness 判据字段） | 不虚报 strict；公开降级理由 | degraded-empirical（诚实降级） |

## 2. 逐桩细化（关键工程细节）

### U1 · B16 MMI 自映像长度（最高优先：Ⅰ 类唯一「曾错」桩）
- **三方独立结构**：golden=Soldano 闭式（抛物线色散普适拍长）；候选A=EME（EIM+模展开，代数本征值）；候选B=FDTD（Yee 时域）。三方方法学互斥（解析近似 / 频域代数 / 时域步进）。
- **判据C（正向）**：数值自映像长度 L_self（fidelity 峰位）与 golden L=3·L_π/…（9/4 因子版）差 <5%。
- **判据D（收敛）**：EME 模数 5→40；FDTD 网格 dl 40→10 nm，峰位单调收敛（峰位提取用抛物线插值三点定峰，抗 sponge 噪声）。
- **判据E（反向）**：W_mmi ±5% ⇒ L_self 同向移动（自映像长度 ∝ W_mmi²/n_eff，闭式可预测方向）。
- **红线**：纯 numpy FDTD/EME，C 级自有引擎；不 import Meep/Tidy3D。
- **工作量**：~2-3 天（引擎已有，接 harness + 峰位提取 + smoke）。

### U2 · E5 MMI 过量损耗（依赖 U1 定峰位）
- 判据：在 U1 收敛峰位 L* 处，EME 与 FDTD 的 excess loss 差 <0.05 dB 且 |loss−0.05|<0.10 dB（实测 tol）⇒ 三角验证 PASS。
- 若双引擎一致但偏离实测 >2σ ⇒ **诚实记录抽象缺陷**（2D-EIM 未含侧壁粗糙等），不硬凑——桩升级为 strict-with-noted-deviation 或维持现状，红队审议定。

### U4 · E-GE-PD-RESP（T1-W5 直接受益，最快可做）
- W5 的 `transit_impulse_response` 已输出收集载流子比例；对 Ge 换材料参数（v_sat≈6.24e7 cm/s? 文献值须查——Ge 电子 v_sat≈6.24e7 m/s? 须核实为 6.24e4 m/s 量级）⇒ η_col=收集/光生。
- 风险：η=0.8 标称与 η_col 数值差可能 > tol（0.05/1.1≈4.5%）——若超差，**不硬凑**，把 tol 内的残差公开为「几何/材料假设差」，红队定夺是否升。
- ⚠️ 实现前必须 WebSearch 核实 Ge 电子饱和速度文献值（避免 v_sat 单位血案重演）。

### U5 · E-MZM-VPI（T1-W4 直接受益）
- 链条：2D DD 解 Q_dep(V)（W4 已输出）→ C_j(V)=dQ/dV（数值差分）→ Vπ·L = (g·L_i·C_j)/(2·d n_eff/dN·W? ) —— 须用标准耗尽型 MZM Vπ 公式（文献闭式）与 Soref-Bennett dn/dN（B31 已有）。
- 掺杂剖面用文献典型 interleaved p-n（E-MRM-VPI-098 同源器件），诚实标 assumed-profile。
- 判据D：2D 网格 40→80（W4 smoke 已有范式）→ C_j 收敛 ⇒ Vπ 收敛。

### U6 · 量子 T1 降级判据（诚实降级路线）
- 不新增数值求解（QEDA T1 内核未立项，强行「解出」T1=300µs 会破「不虚报」红线）。
- 改为：harness 判据字段化 honest_tier=order-of-magnitude-band；红队 fuzz 该桩改为「带外必 FAIL」。

## 3. 明确挂起的 2 桩（不列入换锚）

| 桩 | 挂起理由 |
|---|---|
| B21 PhC 腔共振 | 弱调制布拉格 FP 一阶近似 + 已有 2D FDTD 内验 2%——升 Tier-3 需**特定结构外部 ORACLE**（B 级借今踢后：等 MPW 实测或社区投喂），当前投入产出比低于 U1-U5 |
| E4/E6/E7 等 Q/损耗实测桩 | 与 E1/E3 同为「待 T2 实测扩样」——换锚本质是**外部数据依赖**，非库内可解；路线=扩 corpus（社区/退休专家/晶圆厂投喂），挂 T2 专题 sprint |

## 4. 排序与里程碑建议

```
第3阶段（当前）          第4阶段（T2 后）
U4 E-GE-PD-RESP ──┐
U5 E-MZM-VPI ─────┼─ 小中工作量，T1 内核直接受益，先做
U6 量子T1降级 ────┘
U1 B16 三方独立 ─────── 中工作量，Ⅰ类唯一曾错桩，最高独立性价值
U2 E5 双引擎损耗 ─────── 依赖 U1
U3 E-RING-FSR ────────── 中大工作量（谱扫描）
                        E4/E6/E7 + B21 → 挂 T2 实测/ORACLE 通道
```

- **建议节奏**：U4+U5+U6 一个 sprint（全复用 T1 内核）；U1+U2 一个 sprint（MMI 三方独立）；U3 视 CI 时长预算。
- 全部完成后 strict 预期 29→**35**（+U1 +U2 +U3 +U4 +U5；U6 为降级不计入），可外部验货比例 35/58。
```
