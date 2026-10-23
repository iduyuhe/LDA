"""量子传感器案例卡（WebUI 只读端点数据源）· QS-M8。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
量子传感器芯片征程（吃狗粮第三征程 · QS-M0…QS-M7）的**只读对外窗口**：让客户
一眼看完「用 LDA 从零设计一枚量子传感器芯片」的**两条腿**——

  · **腿 A · NV 色心磁力计**（光-自旋-磁耦合 · 室温）：自旋哈密顿量 → Ramsey/ODMR →
    散粒极限灵敏度 → 退相干 + 四源噪声 → 几何/腔增强优化 → 2×N 阵列 + 串扰 + mux +
    梯度计 → 闭环标定 + 动态范围；器件本体 = NV 柱 / 光子晶体腔 / 微波天线（含 DRC）。
  · **腿 B · 超导 SQUID 磁力计**（电-磁通耦合 · 4 K）：约瑟夫森 RCSJ + SQUID 磁通调制 +
    磁通噪声 → 灵敏度 → 磁通聚焦变压器 + 亚微米结**性能冲刺**。

与 `/api/sensor_demo`（**光子**传感器 PS-M7）**并列**：两者都叫「传感器」但物理不同域
（折射率换能 vs 自旋/磁通换能）；本卡是 **量子传感**（QEDA 的第二支柱），PS 卡是
**光子传感**（PDA）。本卡**不带旋钮**（纯只读案例），与 PS 卡的「设计向导」体例不同。

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不跑求解器、
不 import numpy/scipy/lda_l2、不解析 GDS** —— 全部数字取自
  ① **闭式算术**（散粒极限灵敏度 / Zeeman 分裂 / 优化收益比 —— 与 `qs_m0`/`qs_m7`
     的闭式**镜像**，由门禁 B 节逐位对拍）；
  ② **参考常量快照**（各档建模值，由门禁 B 节对 `qs_m3`/`qs_m4`/`qs_m5`/`qs_m6`/`qs_m7`
     的**现算值**逐位校验 —— 漂移即红）；
  ③ 对已提交产出物只 `os.path.exists` / 目录 `listdir` 的元信息。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/qchip_demo`、
`/api/schip_demo`、`/api/sensor_demo`、`/api/verification_ledger` 同属「公开只读验货」类。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），返回体自带
`honest_note`；本卡是**建模值 / 设计预算**，不是流片实测签核。

🔴 **LLM 不进判决路径**：本模块不含任何模型/网络调用（门禁以 `ast` 遍历真实 import 断言）。

═══ 跨源一致性 ═══
`NV_LEG` / `SQUID_LEG` / `GEOM_REF` / `ARRAY_REF` / `CALIB_REF` / `OPT_REF` 均为
**参考快照**，由门禁 `run_qs_panel_smoke` 的 B 节对 `lda_l2.qs_m0…qs_m7` 的现算值
逐位校验（漂移即红）。
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "QS_HONEST_NOTE", "SENSITIVITY_CALIBER",
    "GAMMA_E_HZ_T", "D_ZFS_HZ", "G_LANDE", "MU_B", "HBAR",
    "NV_LEG", "SQUID_LEG", "GEOM_REF", "ARRAY_REF", "CALIB_REF", "OPT_REF",
    "MILESTONES", "FINDINGS", "GAPS", "SOTA_STARS", "POSITIONING",
    "zeeman_split_hz", "shot_limit_eta_pT", "area_gain_from_areas",
    "optimization_gain_ratio", "case_card", "run_selfchecks",
]

# ═══════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-QS · 量子传感器芯片（NV 色心 + 超导 SQUID 双腿 · 建模设计预算）"

#: 灵敏度统一口径（与 `qs_m0`…`qs_m7` 同源：白噪声幅度谱密度 T/√Hz）
SENSITIVITY_CALIBER = "eta_dB_sqrtT__amplitude_spectral_density__T_per_sqrtHz"

#: 物理常数（与 `qs_m0` 逐位同源 —— 门禁 B 节对拍）
H_PLANCK = 6.62607015e-34          # J·s
HBAR = 1.054571817e-34             # J·s
G_LANDE = 2.0023                   # 电子 g 因子
MU_B = 9.2740100783e-24            # J/T
GAMMA_E_HZ_T = 28.024e9            # Hz/T（NV 电子自旋旋磁比）
D_ZFS_HZ = 2.87e9                  # Hz（NV 基态零场劈裂）

QS_HONEST_NOTE = (
    "① 本卡为**设计预算 / 建模值**（DESIGN_BUDGET），**非**流片实测签核 —— "
    "无低温实测、无金刚石色心实测、无 foundry 回片；"
    "② 灵敏度口径统一为 `η = δB·√T`（白噪声幅度谱密度，T/√Hz），"
    "**禁与线宽受限 LOD / 单次测量不确定度混比**；室温（NV 腿）/ 4 K（SQUID 腿）、"
    "DC/AC、单点/阵列逐项标注；"
    "③ 蓝图 §3 的国际 SOTA 数字（NV 芯片级 26 nT/√Hz、SQUID 集成 1–5 fT/√Hz）"
    "系**公开文献值**，只作**对标准星**引用 —— LDA **不冒充实测**、"
    "**不宣称「已达国际水平」**、不与他方同台比较数值；"
    "④ 物理量分两类：**闭式 ↔ 数值双路径互验**（Zeeman 分裂、Ramsey 相位、散粒极限、"
    "RCSJ 相位、磁通调制、变压器有效面积）为方法学可复核；"
    "**器件几何 / 噪声参数 / 阵列节距 / 环增益 / 结 R_n / 温 / 聚焦因子**为"
    "**设计示例量级**（NV 取室温典型、SQUID 取 4 K 超导典型），**非任何 foundry 的 PDK**；"
    "⑤ 两条腿均**不含**流片/封装/低温布线实现，**不含**量子纠错码层，"
    "**不报** fabricated 能效，**不宣称量子优势**；"
    "⑥ **零量子 SDK**：全程不依赖 Qiskit / Cirq / PennyLane / QuTiP / Strawberry Fields，"
    "物理内核为平台自研（闭式 + numpy）。"
    "LLM 不进判决路径（本模块无任何模型/网络调用）。"
)

# ═══════════════════════ 腿 A · NV 色心磁力计（快照 · 门禁对拍）═══════════════════════
#: 单位：pT/√Hz（幅度谱密度）；五个情景取自 `qs_m0`/`qs_m1`/`qs_m2` 的默认/引用/退化档
NV_LEG: Dict[str, float] = {
    "eta_baseline_pT_per_sqrtHz": 846.5901146206905,
    "eta_cited_pT_per_sqrtHz": 25.39770343862071,
    "eta_degraded_pT_per_sqrtHz": 25429.430750726937,
    "eta_realistic_pT_per_sqrtHz": 847.8819655853509,
    "eta_dd_enhanced_pT_per_sqrtHz": 267.91282722095343,
    "optimal_depth_nm": 45.88517984037517,
    "eta_collection_baseline": 0.12126201835745934,
    "eta_collection_cavity": 0.3081179613854437,
    "purcell_rate_ratio": 451.0,
    "array_channels": 8.0,
    "max_crosstalk_total": 0.02827056514319488,
    "cmrr_db": 40.0,
    "mux_tones_per_feedline": 4.0,
    "dynamic_range_db": 105.02879760052765,
    "ac_sensitivity_nT": 44.721359549995796,
    "lock_residual_rel_linewidth": 3.763327598571777e-08,
    "sota_chip_nT_per_sqrtHz": 26.0,
    "sota_cavity_nT_per_sqrtHz": 52.0,
}

# ═══════════════════════ 腿 B · 超导 SQUID（快照 · 门禁对拍）═══════════════════════
#: `b_n_*` 单位 fT/√Hz；`loop_area_m2` / `a_eff_m2` 单位 m²
SQUID_LEG: Dict[str, float] = {
    "b_n_baseline_fT_per_sqrtHz": 79.25050863210218,
    "ic0_a": 2.0e-06,
    "rn_ohm": 20.0,
    "temp_k": 4.2,
    "loop_area_m2": 1.0e-08,
    "beta_c": 0.9860685408419064,
    "plasma_freq_ghz": 19.61721031280024,
    "a_eff_m2": 1.5000000000000002e-07,
    "area_gain": 15.000000000000002,
    "rn_opt_ohm": 142.5,
    "rn_gain": 7.125,
    "b_n_opt_fT_per_sqrtHz": 1.7299984833764408,
    "optimization_gain": 45.80928871413092,
    "sota_ratio": 0.5766661611254803,
    "sota_band_low_fT": 1.0,
    "sota_band_high_fT": 5.0,
}

#: 几何优化（QS-M3 / QS-M3b）· 与 `qs_m3` / `qs_m3b` 现算逐位对拍
GEOM_REF: Dict[str, float] = {
    "d_star_nm": 45.88517984037517,
    "eta_na": 0.1525327831746235,
    "pillar_height_um": 0.16588517984037515,
    "cavity_web_um": 0.14,
    "antenna_loop_r_um": 20.0,
    "n_device_kinds": 3.0,
    "drc_checks_total": 11.0,
    "drc_violations_total": 0.0,
}

#: 阵列 / 集成（QS-M4）· 与 `qs_m4` 现算逐位对拍
ARRAY_REF: Dict[str, float] = {
    "n_channels": 8.0,
    "max_pair": 0.01562500000000001,
    "max_total": 0.02827056514319488,
    "eta_eff_nT_per_sqrtHz": 1.000399532613603,
    "cmrr_db": 40.0,
    "mux_rows": 2.0,
    "mux_cols": 4.0,
    "mux_tones_per_feedline": 4.0,
    "mux_min_tone_spacing_mhz": 29.999999999999805,
}

#: 闭环标定 / 动态范围（QS-M5）· 与 `qs_m5` 现算逐位对拍
CALIB_REF: Dict[str, float] = {
    "linewidth_mhz": 10.0,
    "dynamic_range_db": 105.02879760052765,
    "ac_sensitivity_nT": 44.721359549995796,
    "lock_n_iter": 6.0,
    "lock_residual_rel_linewidth": 3.763327598571777e-08,
    "field_scale_mismatch": 0.0,
    "b_max_nT": 178418.49842991724,
}

#: 性能冲刺（QS-M7）· 与 `qs_m7` 现算逐位对拍
OPT_REF: Dict[str, float] = {
    "a_eff_m2": 1.5000000000000002e-07,
    "area_gain": 15.000000000000002,
    "rn_gain": 7.125,
    "rn_opt_ohm": 142.5,
    "b_n_opt_fT_per_sqrtHz": 1.7299984833764408,
    "optimization_gain": 45.80928871413092,
    "sota_ratio": 0.5766661611254803,
    "baseline_b_n_fT_per_sqrtHz": 79.25,
}


# ═══════════════════════ 九档征程（静态事实 · 可回溯门禁）═══════════════════════
#: `selfchecks` = 该档**模块自检项数**（由门禁 B 节对 `selfcheck_qs_m*` 现算对拍，
#: 🔴 非手写：任何一侧增删自检项都会当场红了 —— 不登记 smoke 级判据数以避「手写数字」）。
MILESTONES: List[Dict[str, Any]] = [
    {"id": "QS-M0", "code": "v0.9.216", "title": "NV 色心磁力计最小闭环",
     "gate": "run_qs_m0_smoke", "selfchecks": 8,
     "result": "自旋哈密顿量 H=D·Sz²+γe·B·Sz 精确对角化 ⇔ 闭式 Δf=2γeB（rel 0）；"
               "Ramsey 相位 φ=2πγeBτ；散粒极限 η=ħ/(gμB)·√2/(C·√(n_ph·T2*))；"
               "建模基线 η=0.847 nT/√Hz（对标准星 26 / 52 nT/√Hz）"},
    {"id": "QS-M1", "code": "v0.9.217", "title": "灵敏度 FOM 体系 + 四情景",
     "gate": "run_qs_m1_smoke", "selfchecks": 12,
     "result": "统一口径 η=δB·√T（T/√Hz）+ 线宽路径 ⇔ T2* 路径双口径互验；"
               "四情景 baseline 846.59 / cited 25.40 / degraded 25429.43 / bench 846.59 pT/√Hz"},
    {"id": "QS-M2", "code": "v0.9.218", "title": "退相干 + 多源噪声",
     "gate": "run_qs_m2_smoke", "selfchecks": 14,
     "result": "FID 相位方差 ⟨Φ²⟩=2(1−cos ωt) ⇔ Hahn 回波 2(1−cos(ωt/2))²（DC 二阶↔四阶）；"
               "CPMG-n 滤波函数 DC 归零；四源正交合成 → realistic 847.88 / dd_enhanced 267.91 pT/√Hz"},
    {"id": "QS-M3", "code": "v0.9.219", "title": "灵敏度几何优化",
     "gate": "run_qs_m3_smoke", "selfchecks": 15,
     "result": "NA 立体角收集效率 η_NA=0.15253；最优色心深度闭式根方程 d*=45.885 nm；"
               "腔增强 Purcell 计数率比 451× → η_coll 0.1213 → 0.3081（bulk 12.1% → 30.8%）"},
    {"id": "QS-M3b", "code": "v0.9.220", "title": "G5 器件本体（柱/腔/天线 + DRC）",
     "gate": "run_qs_m3b_smoke", "selfchecks": 22,
     "result": "NV 柱 / 光子晶体腔 / 微波天线三类真实几何（柱高 ≡ qs_m3 最优深度现算派生）；"
               "9 条专用可制造性 DRC 规则 + 11 项检查 0 违规；PDK 器件本体登记（params 恒空）"},
    {"id": "QS-M4", "code": "v0.9.221", "title": "2×N 阵列 + 串扰 + 读出 mux + 梯度计",
     "gate": "run_qs_m4_smoke", "selfchecks": 28,
     "result": "磁偶极近场串扰 X=(d_crit/r)³ 闭式 ⇔ 数值点偶极场；8 通道 max_total 0.02827 → "
               "η_eff 1.0004 nT/√Hz；2 行 × 4 列 FDM mux（音间隔 30 MHz）；CMRR 40 dB"},
    {"id": "QS-M5", "code": "v0.9.222", "title": "闭环标定 + 动态范围 + AC 灵敏度",
     "gate": "run_qs_m5_smoke", "selfchecks": 33,
     "result": "ODMR 频率锁定（gain=1 一步收敛 / 残差 3.76e-08 线宽）；磁场标度自标定；"
               "动态范围 105.03 dB；AC 灵敏度 η·√(2Δf)=44.72 nT"},
    {"id": "QS-M6", "code": "v0.9.223", "title": "第二腿 · 超导 SQUID 磁力计",
     "gate": "run_qs_m6_smoke", "selfchecks": 42,
     "result": "约瑟夫森 RCSJ + Ambegaokar–Baratoff；SQUID 磁通调制 I_c(Φ)=2I_c0|cos(πΦ/Φ0)| ⇔ "
               "相位空间扫描；Johnson 噪声 → 基线 B_N=79.25 fT/√Hz（β_c=0.986 / ω_p=19.62 GHz）"},
    {"id": "QS-M7", "code": "v0.9.224", "title": "SQUID 性能冲刺（噪声优化）",
     "gate": "run_qs_m7_smoke", "selfchecks": 13,
     "result": "磁通聚焦变压器 A_eff=1.5e-07 m²（15×）⇔ 离散 Neumann 互感双和；"
               "亚微米结 R_n 20→142.5 Ω（7.125×）；B_N,opt=1.73 fT/√Hz（45.81× 增益，"
               "sota_ratio 0.577 ⇒ 进入公开集成带 1–5 fT/√Hz）"},
]


# ═══════════════════════ 关键结论（物理 + 方法学）═══════════════════════
FINDINGS: List[Dict[str, Any]] = [
    {"title": "物理内核方法学独立（非自证）",
     "detail": "每道锚都是「闭式物理律 ⇔ 独立数值路径」双验证：Zeeman 分裂（精确对角化）、"
               "Ramsey 相位（时间演化）、散粒极限（逐步积分）、RCSJ 相位（RK4）、"
               "SQUID 磁通调制（相位空间扫描）、变压器有效面积（离散 Neumann 互感双和）。"
               "判决为**死标量比对**，LLM 不进判决路径。"},
    {"title": "反自证桩纪律：线性系统上的「聪明解」残差恒 0",
     "detail": "变压器有效面积的首次数值候选（不动点迭代 / 直接线性解 / 线性核中点积分）"
               "在**线性方程上一步精确收敛** ⇒ 闭式 ⇔ 数值残差恰为 0（代数恒等）⇒ 会被"
               "判自证桩。改用**离散 Neumann 互感双和**（∝1/n_seg 截断残差）方得真残差 "
               "rel 1.64e-3；守卫以「粗网格 ⇒ 残差放大 64×/128×」反向钉死。"},
    {"title": "「下界 ≠ 可达」不适用于本卡，但「口径」适用",
     "detail": "本卡所有灵敏度一律为 `η = δB·√T`（白噪声幅度谱密度 T/√Hz），"
               "室温/低温、DC/AC、单点/阵列逐项标注；**禁与线宽受限 LOD 混比** —— "
               "PS 征程的口径混比陷阱在此被显式排除。"},
    {"title": "两条腿是不同物理机制，不是同一能力的两次实现",
     "detail": "腿 A（NV）是**光-自旋-磁**耦合（自旋能级 / ODMR / Ramsey，室温）；"
               "腿 B（SQUID）是**电-磁通**耦合（宏观量子相位 / I_c(Φ)，4 K）。"
               "两者灵敏度天然相差一个量级（nT vs fT），正是「分步达国际水平」的阶梯。"},
    {"title": "性能冲刺的物理杠杆：面积 × 电阻 × 温",
     "detail": "SQUID 腿从 79.25 → 1.73 fT/√Hz（45.81×）由三重叠加兑现："
               "**磁通聚焦变压器**放大有效拾取面积（15×）、**亚微米结**抬高 R_n 压低"
               "Johnson 噪声（7.125×）、**温降**（√T）。每一环都有闭式 ⇔ 数值双验。"},
]


# ═══════════════════════ 缺口登记（G1–G11 · 逐档闭合）═══════════════════════
GAPS: List[Dict[str, Any]] = [
    {"id": "G1", "title": "量子传感通用框架（IR kind）", "status": "已闭合",
     "detail": "QS-M0 起 `QuantumSensorDevice` 语义（自旋/磁通换能）落地。"},
    {"id": "G2", "title": "自旋-磁场转导物理", "status": "已闭合",
     "detail": "Zeeman 分裂 + Ramsey 相位 + 散粒极限灵敏度（QS-M0/M1）。"},
    {"id": "G3", "title": "量子传感指标体系", "status": "已闭合",
     "detail": "统一口径 η=δB·√T + 四情景 FOM 报告（QS-M1）。"},
    {"id": "G4", "title": "自旋相干时间建模", "status": "已闭合",
     "detail": "T2* → T2（DD 回波 / CPMG）+ 四源噪声合成（QS-M2）。"},
    {"id": "G5", "title": "量子传感专用 PDK 器件", "status": "已闭合",
     "detail": "NV 柱 / 光子晶体腔 / 微波天线几何 + DRC + PDK 登记（QS-M3 / QS-M3b）。"},
    {"id": "G6", "title": "量子传感器阵列 / 集成", "status": "已闭合",
     "detail": "2×N 阵列 + 串扰 + 多通道读出 mux + 梯度计（QS-M4）。"},
    {"id": "G7", "title": "量子传感器标定 / 读出闭环", "status": "已闭合",
     "detail": "微波频率锁定 + 磁场标度自标定 + 动态范围 + AC 灵敏度（QS-M5）。"},
    {"id": "G8", "title": "超导量子器件物理（约瑟夫森 / 磁通）", "status": "已闭合",
     "detail": "RCSJ 结 + SQUID 磁通调制 + 磁通噪声 → 灵敏度（QS-M6）。"},
    {"id": "G9", "title": "超导量子传感优化", "status": "已闭合",
     "detail": "磁通聚焦变压器 + 亚微米结 + 温降（QS-M7）。"},
    {"id": "G10", "title": "WebUI 量子传感面板", "status": "本档闭合",
     "detail": "本卡 + `/api/qsensor_demo` + `sec-qsensor` 面板 + 三入口面（抽屉 / "
               "hash 深链 / 首屏案例条）—— QS-M8 交付。"},
    {"id": "G11", "title": "多物理场量子传感整合（OPM / 原子磁力计）",
     "status": "已闭合（QS-M9 · B491–B493）",
     "detail": "光泵自旋进动 + 气室/线圈多物理场整合 → SERF 区灵敏度对照 —— QS-M9 已交付，"
               "落 3 道锚（B491 OPM 自旋进动 / B492 SERF 区灵敏度 / B493 气室-线圈多物理场"
               "耦合），门禁 `run_qs_m9_smoke` 39 判据全绿。"
               "（v0.9.276 台账同步：此前本行长期标「未闭合」，与实现不符 —— F-6。）"},
]


# ═══════════════════════ 对标准星（公开文献值 · 仅背景坐标）═══════════════════════
SOTA_STARS: List[Dict[str, Any]] = [
    {"metric": "NV 色心磁灵敏度（芯片级）", "intl": "26 nT/√Hz",
     "caliber": "2×2 单片集成 QLED 阵列 · 室温 · DC",
     "lda_target": "本卡 NV 腿建模值 846.59 pT/√Hz（baseline 情景）"},
    {"metric": "NV 光学腔最优", "intl": "52 nT/√Hz",
     "caliber": "nanofabricated cavity · 光子散粒受限",
     "lda_target": "腔增强情景 η_coll 0.1213 → 0.3081（R/R₀ = 451×）"},
    {"metric": "SQUID 磁灵敏度（集成 MEG）", "intl": "1–5 fT/√Hz",
     "caliber": "集成芯片 · >80% 器件 <5 fT/√Hz · 4 K",
     "lda_target": "本卡 SQUID 腿优化后建模值 1.73 fT/√Hz（sota_ratio 0.577）"},
    {"metric": "SQUID 极限", "intl": "~0.1 fT/√Hz",
     "caliber": "实验室最优（天花板靶）",
     "lda_target": "未追（> 本卡优化档；只作天花板坐标）"},
    {"metric": "NV 相干时间 T₂", "intl": "~ ms（体材料 · DD 可延 2 个数量级）",
     "caliber": "动力学去耦下的相干时间",
     "lda_target": "本卡 dd_enhanced 情景 T2*=1→10 µs（建模档，非体材料最优）"},
]


POSITIONING: Dict[str, Any] = {
    "disclaimer": "下列为 2025–2026 **公开发表/报道**的产业界与学术界数字，仅作**背景坐标**；"
                  "本卡全部为**建模值 / 设计预算**，两者**不同台比较**、**不构成任何性能宣称**。",
    "what_is_different": [
        "交付物：产业界交付**已制备器件 / 实测谱密度**；LDA 交付**可复现、可审计的设计预算**"
        "（闭式 ⇔ 数值双验证 + 门禁常驻）。",
        "工具链：产业界用各自闭源 CAD/PDK + 量子 SDK；LDA **开源（MIT）· Agent-native · "
        "零量子 SDK**（不依赖 Qiskit / Cirq / PennyLane / QuTiP）。",
        "判决路径：产业界为实验标定 + 数值仿真混合；LDA **LLM 不进判决路径**，"
        "判决为死标量比对，红线为物理定律锚。",
        "覆盖范围：本卡覆盖**从物理反解到器件本体到阵列/标定/噪声优化**的全链"
        "（两条腿），而非单点指标。",
    ],
    "honest_limits": [
        "不做数值同台比较：LDA 不宣称在灵敏度、相干时间或噪声底上优于任何团队/厂商。",
        "不宣称「已达国际水平」：建模值进入公开带仅为**坐标重合**，非实测达成。",
        "不报 fabricated 能效；不宣称量子优势；不涉及任何量子计算优势主张。",
    ],
}


# ═══════════════════════ 闭式（镜像平台模块 · 可反向测试）═══════════════════════
def zeeman_split_hz(B_t: float, gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """闭式 Zeeman 分裂 Δf = 2·γe·B（Hz）—— 镜像 `qs_m0.zeeman_split_closed_form`。"""
    return 2.0 * gamma_hz_t * B_t


def shot_limit_eta_pT(T2star_s: float, n_ph_per_s: float, contrast: float,
                      gamma_hz_t: float = GAMMA_E_HZ_T) -> float:
    """散粒噪声极限磁灵敏度 η（pT/√Hz）—— 镜像 `qs_m0.sensitivity_shot_limit_closed`。

    闭式：η = ħ/(g·µB) · √2 / (C · √(n_ph · T2*))   [T/√Hz]；此处 ×1e12 转 pT/√Hz。
    🔴 与 `qs_m0` 同式同参 ⇒ 门禁 B 节逐位对拍（漂移即红）。
    """
    if T2star_s <= 0.0 or n_ph_per_s <= 0.0 or contrast <= 0.0:
        raise ValueError("T2* / n_ph / contrast 必须 > 0")
    g_muB_over_hbar = G_LANDE * MU_B / HBAR
    eta_t = (math.sqrt(2.0) / (contrast * math.sqrt(n_ph_per_s * T2star_s))
             / g_muB_over_hbar)
    return eta_t * 1e12


def area_gain_from_areas(a_eff_m2: float, bare_loop_area_m2: float) -> float:
    """有效面积增益 = A_eff / A_bare（无量纲）。"""
    if bare_loop_area_m2 <= 0.0:
        raise ValueError("bare_loop_area_m2 必须 > 0")
    return float(a_eff_m2 / bare_loop_area_m2)


def optimization_gain_ratio(base_b_n: float, opt_b_n: float) -> float:
    """优化收益倍率 = 基线灵敏度 / 优化后灵敏度（>1 ⇒ 改善）。"""
    if base_b_n <= 0.0 or opt_b_n <= 0.0:
        raise ValueError("灵敏度必须 > 0")
    return float(base_b_n / opt_b_n)


# ═══════════════════════════ 产出物探测（只读元信息）═══════════════════════════
_ARTIFACT_DIRS = ("examples", "lda/examples")


def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 QS 征程产出物（`outputs/qs_m*` 目录）**元信息**（存在性 + 文件数）。

    🔴 只 `listdir`，不读内容 ⇒ 微秒级；目录不存在（生产只装 `lda/`）则优雅降级。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    hits: List[str] = []
    n_files = 0
    for d in _ARTIFACT_DIRS:
        for m in ("qs_m0", "qs_m1", "qs_m2", "qs_m3", "qs_m3b",
                  "qs_m4", "qs_m5", "qs_m6", "qs_m7"):
            p = os.path.join(root, "outputs", m)
            if os.path.isdir(p):
                rel = os.path.join("outputs", m)
                if rel not in hits:
                    hits.append(rel)
                try:
                    n_files += len([f for f in os.listdir(p)
                                    if os.path.isfile(os.path.join(p, f))])
                except OSError:
                    continue
        break
    if not hits:
        return {"available": False, "n_dirs": 0, "n_files": 0, "dirs": [],
                "note": "产出物目录不在本部署内（由 CI 门禁在源码仓运行生成）"}
    return {"available": True, "n_dirs": len(hits), "n_files": n_files,
            "dirs": hits,
            "note": "只读元信息（目录存在性 + 文件数）；在线复现请跑源码仓的 "
                    "`lda/run_qs_m*_smoke.py`"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装量子传感器案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_BUDGET` —— **明标「设计预算 / 建模值」而非实测**。
    """
    nv = dict(NV_LEG)
    sq = dict(SQUID_LEG)
    # 现算派生（非转录）：面积增益 / 优化收益 由快照常量重算，供门禁对拍真源
    # 🔴 优化收益比按 **QS-M7 定义口径**（基线取 79.25 fT/√Hz，即 QS-M7 定稿的对照基线，
    #    非 QS-M6 的全精度 79.2505…）—— 与 `qs_m7.physics.sensitivity_gain` 逐位一致。
    sq["area_gain"] = area_gain_from_areas(sq["a_eff_m2"], sq["loop_area_m2"])
    sq["optimization_gain"] = optimization_gain_ratio(
        OPT_REF["baseline_b_n_fT_per_sqrtHz"], OPT_REF["b_n_opt_fT_per_sqrtHz"])
    nv["shot_limit_check_pT_per_sqrtHz"] = shot_limit_eta_pT(1.0e-6, 1.0e5, 0.03)

    return {
        "endpoint": "/api/qsensor_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一枚量子传感器芯片（两条腿）：NV 色心磁力计（光-自旋-磁 · "
                 "室温）与超导 SQUID 磁力计（电-磁通 · 4 K）—— 从自旋/约瑟夫森物理反解到"
                 "器件本体、阵列、闭环标定与噪声优化，全链机器校验。",
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算 / 建模值（非流片实测）",
        "identity": {
            "physics": "量子传感（两能级自旋 ⇄ 磁场 / 宏观量子相位 ⇄ 磁通）",
            "device": "NV 色心（纳米柱 / 光子晶体腔 / 微波天线）+ 超导 SQUID"
                      "（约瑟夫森结 + 磁通聚焦变压器 + 拾取环）",
            "unit": "换能单元 = 自旋能级（NV）或 SQUID 环路（磁通→临界电流）",
            "legs": ["腿 A · NV 色心（光-自旋-磁 · 室温）",
                     "腿 B · 超导 SQUID（电-磁通 · 4 K）"],
            "route_note": "量子传感是 QEDA 的第二支柱（第一支柱为量子计算，"
                          "见 /api/qchip_demo 与 /api/schip_demo）；三条路线选型中"
                          "A（NV）+ B（SQUID）双腿已落地，C（OPM）留待 QS-M9。",
            "caliber": SENSITIVITY_CALIBER,
            "zero_quantum_sdk": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gates": len(MILESTONES),
            "module_selfchecks": sum(m["selfchecks"] for m in MILESTONES),
        },
        "milestones": [dict(m) for m in MILESTONES],
        "findings": [dict(f) for f in FINDINGS],
        "gaps": [dict(g) for g in GAPS],
        "gaps_total": len(GAPS),
        "gaps_closed": len([g for g in GAPS if g["status"] != "未闭合"]),
        "nv_leg": nv,
        "squid_leg": sq,
        "geometry": dict(GEOM_REF),
        "array": dict(ARRAY_REF),
        "calibration": dict(CALIB_REF),
        "optimization": dict(OPT_REF),
        "sota_stars": [dict(s) for s in SOTA_STARS],
        "positioning": {
            "disclaimer": POSITIONING["disclaimer"],
            "what_is_different": list(POSITIONING["what_is_different"]),
            "honest_limits": list(POSITIONING["honest_limits"]),
        },
        "artifacts": _artifact_manifest(repo_root),
        "honest_note": QS_HONEST_NOTE,
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器 / numpy）。"""
    import ast

    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    # ① 零外部框架 / 无模型调用（ast 遍历真实 import —— 不用源码字符串 in，见血案）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    banned = {"numpy", "scipy", "torch", "sklearn", "requests", "urllib",
              "socket", "http", "transformers", "openai", "lda_l2"}
    chk("① 零外部框架：本模块不 import numpy/scipy/求解器/网络/lda_l2", not (mods & banned))

    # ② verdict 不伪装实测
    card = case_card(repo_root="__nonexistent_root__")
    chk("② 不伪装实测：verdict 为 DESIGN_BUDGET（非 ACCEPT/PASS/OK）",
        card["verdict"] == "DESIGN_BUDGET"
        and card["verdict"] not in ("PASS", "ACCEPT", "OK"))

    # ③ 诚实边界齐备
    chk("③ 诚实边界齐备（设计预算 / 口径统一 / 非实测 / 不宣称已达国际水平 / "
        "零量子 SDK / LLM 不进判决路径）",
        all(kw in QS_HONEST_NOTE for kw in
            ("设计预算", "白噪声幅度谱密度", "非", "不宣称「已达国际水平」",
             "零量子 SDK", "LLM 不进判决路径")))

    # ④ 九档征程齐备 + 门禁名合法
    chk("④ 九档征程齐备（QS-M0…QS-M7 + QS-M3b）· 门禁名 run_qs_*",
        len(MILESTONES) == 9
        and [m["id"] for m in MILESTONES][0] == "QS-M0"
        and all(m["gate"].startswith("run_qs_") for m in MILESTONES))

    # ⑤ 闭式镜像正确（散粒极限 baseline 情景 ≈ 846.59 pT/√Hz）
    eta = shot_limit_eta_pT(1.0e-6, 1.0e5, 0.03)
    chk("⑤ 闭式镜像：散粒极限 η(1µs, 1e5/s, C=0.03) ≈ 846.5901 pT/√Hz",
        abs(eta - 846.5901146206905) / 846.5901146206905 < 1e-12)

    # ⑥ Zeeman 分裂闭式（1 µT ⇒ 2·28.024e9·1e-6 = 56 048 Hz）· 且 ∝ B、B=0 ⇒ 0
    chk("⑥ Zeeman 分裂闭式：Δf(1µT)=56048 Hz · 线性 ∝ B · Δf(0)=0",
        abs(zeeman_split_hz(1e-6) - 56048.0) < 1e-6
        and abs(zeeman_split_hz(2e-6) - 2.0 * zeeman_split_hz(1e-6)) < 1e-12
        and zeeman_split_hz(0.0) == 0.0)

    # ⑦ 面积增益/优化收益由快照重算（非转录）
    chk("⑦ 面积增益 = A_eff/A_bare = 15× · 优化收益 = 79.25/1.73 = 45.81×",
        abs(SQUID_LEG["area_gain"]
            - area_gain_from_areas(SQUID_LEG["a_eff_m2"],
                                   SQUID_LEG["loop_area_m2"])) < 1e-9
        and abs(OPT_REF["optimization_gain"]
                - optimization_gain_ratio(OPT_REF["baseline_b_n_fT_per_sqrtHz"],
                                          OPT_REF["b_n_opt_fT_per_sqrtHz"])) < 1e-9)

    # ⑧ 物理合理：两腿灵敏度为正且 SQUID 优于 NV（fT < pT）· 优化后进入公开带
    chk("⑧ 物理合理：两腿 η 有限为正 · SQUID 优化后 (1.73 fT) 优于基线 (79.25 fT) · "
        "sota_ratio ∈ (0,1)",
        all(math.isfinite(v) and v > 0 for v in
            (NV_LEG["eta_baseline_pT_per_sqrtHz"],
             SQUID_LEG["b_n_baseline_fT_per_sqrtHz"],
             SQUID_LEG["b_n_opt_fT_per_sqrtHz"]))
        and SQUID_LEG["b_n_opt_fT_per_sqrtHz"] < SQUID_LEG["b_n_baseline_fT_per_sqrtHz"]
        and 0.0 < SQUID_LEG["sota_ratio"] < 1.0)

    # ⑨ 缺口表：11 项 · G10 本档闭合 · G11 **已闭合**（v0.9.276 修 F-6：台账原长期与实现不符）
    # 🔴 本模块是「零重计算」展示卡（E2/E3 硬约束：真实 import ⊆ math/os/typing/json/ast），
    #    故此处**只做结构断言**。G11「已闭合」的**跨真源对拍**（B491–B493 必须在册且 strict）
    #    放在门禁 `run_qs_panel_smoke` 的 B4b —— 台账不得自封，但校验必须发生在
    #    **能 import 账本的那一侧**，不能为此破坏本卡的零依赖约束。
    _g11 = next(g for g in GAPS if g["id"] == "G11")
    chk("⑨ 缺口表 11 项 · G10 标「本档闭合」· G11 标已闭合且写明闭合依据（QS-M9）",
        len(GAPS) == 11
        and next(g for g in GAPS if g["id"] == "G10")["status"] == "本档闭合"
        and "闭合" in _g11["status"] and "未闭合" not in _g11["status"]
        and "QS-M9" in _g11["detail"])

    # ⑩ 对标准星须显式「公开值 / 仅背景」且含诚实限制三条
    chk("⑩ 对标准星：含公开值背景声明 + 3 条诚实限制 + ≥5 条对标准星",
        "公开" in POSITIONING["disclaimer"] and "不同台比较" in POSITIONING["disclaimer"]
        and len(POSITIONING["honest_limits"]) == 3 and len(SOTA_STARS) >= 5)

    # ⑪ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    chk("⑪ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)

    # ⑫ 护栏：非法输入抛错
    guard = 0
    for bad in (lambda: shot_limit_eta_pT(0.0, 1e5, 0.03),
                lambda: shot_limit_eta_pT(1e-6, 0.0, 0.03),
                lambda: shot_limit_eta_pT(1e-6, 1e5, 0.0),
                lambda: area_gain_from_areas(1e-7, 0.0),
                lambda: optimization_gain_ratio(0.0, 1.0)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑫ 护栏：零 T2*/n_ph/contrast · 零面积 · 零灵敏度 均抛 ValueError", guard == 5)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    import json
    print(json.dumps(case_card(), indent=2, ensure_ascii=False))
    print("\nselfcheck:", run_selfchecks(verbose=True))
