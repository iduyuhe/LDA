# -*- coding: utf-8 -*-
"""VMM 分级覆盖表（F-08 拆分自 `benchmarks.py` · 逐字节搬移 · v0.9.117）。

键 = benchmark id；值 = (provenance, upgrade_path)。由 `benchmarks._vmm_provenance` /
`_vmm_upgrade_path` 读取；`_VMM_FINAL_VERDICT`（终审锁）仍留在 `benchmarks.py`。
"""
_VMM_OVERRIDES = {
    # id: (provenance, upgrade_path)
    "B2":  ("independent_cross_check",
            "🔒 终审锁定升 Tier-3 严格独立（2026-09-10 多智能体终审）：FV-FDM 全矢量（纯物理选模 2.644，Δ=0.0069）+ PWE 平面波展开（2.614，Δ=0.0369）两个方法学独立全波数值均在 tol=0.05 内复现 EIM golden 2.6509，golden 居二者之间，判据 C5 成立。推翻早间『半矢量 FDM=2.53 证伪』误判（该实现索引 bug，已废弃）。详见 _VMM_FINAL_VERDICT['B2']。勿反复审议。"),
    "B5":  ("independent_cross_check",
            "🔒 v0.9.81 升 Tier-3 严格独立（P1-1 B567）：候选 `ybranch_eme` 双芯超模 EME"
            "（EIM 降维 + 锥区逐片解完整横向 Helmholtz 本征问题 + 模式重叠矩阵级联），"
            "末片导模功率和 T ⇒ 分束损耗 = 3.0103 − 10log10(T)；实测 3.0321 dB vs golden "
            "3.4（|diff|=0.368 < tol 1.0），残差 = golden 唯象拟合式 0.4·(θ/10)² 的固有"
            "粗糙度（严格 EME 给出 excess 仅 0.008–0.061 dB，θ 5–20°，θ 依赖形状与拟合式"
            "完全不同源）。⚠️ tol=1.0 远宽于候选参数响应幅度（±10% 仅 ~0.005 dB）⇒ 本锚"
            "**无参数判别力**（同 B8 型），只回答「是否接近理想均分下限」，故不进 "
            "PERTURB_SPEC。（原 design_rule_anchor 升级路径已打通）"),
    "B6":  ("independent_cross_check",
            "🔒 v0.9.81 升 Tier-3 严格独立（P1-1 B567）：候选 `grating_fp` 首原理四因子"
            "分解 η = η_dir·η_ov·F(ff)·M ——η_dir=1/2（上下包层对称 ⇒ 一阶衍射上/下功率"
            "相等，由对称性推出）、η_ov=0.7846（指数辐射场⊗高斯光纤模 MFD=10.4µm 的"
            "归一化模场重叠，对 α 取设计最优）、F=sin(π·ff)（方波一阶傅里叶强度）、"
            "M=exp(−(Δβ·L_g/2)²)（光栅方程相位匹配，L_g=20 周期）。实测 0.3909 vs golden "
            "0.5（|diff|=0.109 < tol 0.15）：残差=设计守则把 η_ov 理想化为 1 的乐观偏差"
            "（无镜面光栅理论天花板）；不引用 E8 的 σ=15° 唯象倾斜散布系数。"
            "（原 design_rule_anchor 升级路径已打通）"),
    "B7":  ("independent_cross_check",
            "🔒 v0.9.82 升 Tier-3 严格独立：golden 语义订正为设计守则锚 −40 dB"
            "（独立实证背书 E7 同几何实测 −41±2 dB）；已证失真的 2D 离线 FDTD"
            "（裸十字 vs 锚定 taper 交叉差 20~30 dB、源位 ±3 dB 不收敛）撤出 "
            "golden 调度、降级为机理诊断量。候选=双芯超模/CMT 本征解"
            "（方法学独立于场级 FDTD），|diff|=4.64 < tol 5.0 —— 残差占窗口 "
            "93%，属边缘通过；彻底闭合需 3D 全波 + 真实版图"),
    "B11": ("independent_cross_check",
            "🔒 v0.9.68 升 Tier-3 严格独立：数值 add-drop 环 drop 口传递函数峰周期拟合"
            "FSR（同 B4 谱拟合族），再算 |FSR−target|/target 与 golden 同一标量。"
            "方法学独立于闭式 FSR；基线残差 ~1e-9 << tol=0.03，余量 >>1000×，判据 D 不触发。"
            "（原 self_authored_closed_form 升级路径已打通）"),
    "B16": ("independent_cross_check",
            "🔒 v0.9.80 升 Tier-3 严格独立（P1-1 B16 重审）：rib-MMI 全场模态重构候选 "
            "`rib_mmi_recon`——① 反演 core 折射率使平板基模 ≡ 器件 n_eff（对象一致，正面"
            "修正 mmi_eme 的 slab≠rib 错配）；② 精确解 tan/cot 本征方程得全部导模；"
            "③ 输入场按全部导模展开沿 z 精确传播，双度量联合定位 1×2 首像（**不套 (9/8) "
            "成像因子**）。方法学独立于 golden 抛物线闭式。实测 |cand−golden|：W=2.0→0.26µm、"
            "2.4→0.25、2.8→0.54、3.2→0.92、3.6→1.48、4.0→2.21（全 < tol 3.0µm，覆盖 "
            "2.0–4.0µm 全宽度域）；残差=抛物线近似固有误差（非零、有界、物理，非假绿）。"
            "（原 self_authored_closed_form 升级路径已打通；golden 因子 3→9/4 已修）"),
    "B17": ("self_authored_closed_form",
            "本就不升：定义同义反复（terminal Tier-1）"),
    "B18": ("self_authored_closed_form",
            "本就不升：regime 越界（terminal Tier-1）"),
    "B21": ("self_authored_closed_form_with_check",
            "v0.9.78 诚实升 degraded_ordinal（用户授权「B 路径」）：自研 2D FDTD 全波"
            "（fdtd2d_dbr_cavity.py，纯 numpy·C 级自主·不借 Meep/Tidy3D）作方法学独立候选，"
            "6 点扫描实证实残差 0.04%–8.06% 随几何变化（判据 D 满足，非伪绿）。默认"
            "λ_fdtd=2214.87nm vs golden 2214.0nm，rel=0.039%（余量 ~77×，低于严格 100×"
            "故保守归 degraded，不进死标量判决列）；tol=66.0nm=3%×golden(2214nm) 绝对带。"
            "跨域偏差主成分为一阶 FP 模型近似粗糙度，待放宽红线（借 A 级/补波导几何）方升 strict。"),
    "E1":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E3":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E4":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E5":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E6":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E7":  ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
    "E9":  ("external_empirical", "用真实 PDK 标定 c1 工艺系数后升 Tier-3"),
    "S1":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S2":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S3":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S4":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S5":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S6":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S9":  ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S10": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S11": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
    "S12": ("self_authored_closed_form", "本就不升：系统/算术合成校验（terminal Tier-1，非物理锚）"),
}
