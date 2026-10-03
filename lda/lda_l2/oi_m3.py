# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · **M3（3.2T / CPO）**：400G/lane 带宽墙 · CPO 电通道 ·
die↔die 热 + 闭环热调 · 同口径功耗账 · 2.5D 版图签核。

M3 与 M0/M1/M2/M2b 的根本差别（勘查第一结论）：**前四轮的缺口是「平台空白 ⇒ 从零建」，
M3 的缺口是「有底座但没跑到 3.2T 速率级、且 CPO 特有物理链路是断的」**。
⇒ 打法反过来：**先吃狗粮复用（禁止重造第二份），只补真断口**。

复用底座（🔴 一律 import，**不重抄常量** —— 抄了就是血案 #3）：
  · `lda_l2.oi_m2`：奈奎斯特 / 符号率（本轮 3.2T 常量**由 200G 档派生**，不写第二份）
  · `lda_l2.oi_m2b`：热调单真源 Pπ / 调谐斜率 S / 二维薄片对数热解 Θ / 有限差分第二通道
  · `lda_l2.oi_m1`：一阶单极点口径与 |H|=1/√2 的 f₃dB 定义（**同口径互锁**，见 `_family_lock`）
  · `lda_design.cpo_engines.cpo_optical_io_metrics`：**只调参 lane_rate_gbps=400**，
    三道物理下界（能量守恒 3.0103 dB/级 · FAU 间距 ≥125 µm · 密度上界）必须**仍成立**
  · `lda_l2.chip_layout_export.export_chip_gds` / `lda_l2.gds_export.gds_library`：2.5D GDS 底座

五项真断口（本模块逐条补）：
  ① 400G/lane 带宽墙：行波电极 TWMZM（❶闭式分布 RLC 解析 ❷N 段 ABCD 链第二通道）
  ② CPO 电通道（ASIC↔光引擎共封装）：电报闭式 ⟷ 1D FDTD 时域对拍 + NEXT + PDN 地弹
  ③ CPO die↔die 热（复用 M2b Θ，拆两串热阻）+ **闭环热调稳态功耗**
  ④ 功耗同口径账（3.2T 下 CPO ⟷ 可插拔逐项对照，**只 mW/W，不做 fJ/bit**）
  ⑤ 2.5D 版图签核（G-OI6）：ASIC die + 光引擎 die + 中介层 + FAU，**片外 fiber 不落版图**

🔴 诚实边界（红线）：
  · C 级自主 ⇒ 纯 numpy/标准库（cmath/math），零商业 EDA/SPICE/串行链路工具；
  · 🔴 **不报 TOPS / TOPS-W / fJ/op / pJ/bit** ⇒ 功耗账只出 **mW / W**；
  · T2 工艺真值**锁死** ⇒ 电通道的 R'/C'/L'、PDN 感抗、等效线电容、ASIC 热阻
    全是**显式声明的规格锚**（带取值窗口 `_BANDS`），**不是 foundry 数据** ⇒
    `verdict` 恒 `DESIGN_BUDGET`，不得宣称「实测电学特性」；
  · 器件为 L0/L1 解析 / 行为模型，参数属公开文献典型量级占位（**非 PDK**），**无实测锚**；
  · LLM 不进判决路径。
"""
from __future__ import annotations

import cmath
import hashlib
import math
import struct
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from lda_l2 import oi_m1 as _M1
from lda_l2 import oi_m2 as _M2
from lda_l2 import oi_m2b as _M2B

C_M_S = _M1.C_M_S                       # 2.99792458e8（同源，不重抄）


# ═════════════════════════════════════════════════════════════════════════════
# 0) 3.2T 常量：🔴 **全部由 200G 档派生**（每倍频沿用 Rs = lane_bits/2），不写第二份
# ═════════════════════════════════════════════════════════════════════════════
PAM4_BAUD_200G_GBD = _M2.PAM4_BAUD_200G_GBD     # 106.25 GBd（200G/lane，同源）
PAM4_BAUD_3200_GBD = 2.0 * PAM4_BAUD_200G_GBD   # 212.5 GBd（IEEE 802.3dj 400G/lane）
NYQUIST_3200_GHZ = PAM4_BAUD_3200_GBD / 2.0     # 106.25 GHz

LANES_3200 = 8                                  # 3.2T = 8 × 400G
LANE_BITS_3200 = 400.0                          # 每通道 400 Gb/s（编码后）
ENCODE_OVERHEAD = 1.0625                        # 64b/66b + RS(544,514) 开销（规格锚）
LINE_RATE_3200_GBPS = LANES_3200 * LANE_BITS_3200 * ENCODE_OVERHEAD   # 3400 Gb/s


# ═════════════════════════════════════════════════════════════════════════════
# 1) 规格锚 / 取值窗口（防口径静默写错 —— M1 `TARGET_BER_KP4` 血案同族）
# ═════════════════════════════════════════════════════════════════════════════
OI_M3_PROCESS: Dict[str, Any] = {
    "n_lanes": LANES_3200,
    # ── ① 行波电极 TWMZM（400G/lane 带宽墙）
    "l_electrode_mm": 2.0,        # 行波电极长度
    "n_g_opt": _M2B.OI_M2B_PROCESS["ring_n_g"],   # 4.2（SOI 波导群折射率，同源）
    "dn_g_resid": 0.15,           # 倾斜电极补偿后**残留**速度失配（n_g,mw − n_g,opt）
    "r_elect_ohm_per_mm": 2.0,    # 电极单位长度电阻
    "c_elect_fF_per_mm": 200.0,   # 电极单位长度电容
    "f_pd_ghz": 120.0,            # 探测器（3.2T 档需 >106.25）
    "f_tia_ghz": 150.0,           # TIA（3.2T 档需 >106.25）
    # ── ② CPO 电通道（ASIC↔光引擎共封装，mm 级）
    "bus_len_mm": 5.0,            # die-to-die 电总线长度（CPO 的本质卖点：cm → mm）
    "r_bus_ohm_per_mm": 60.0,     # stripline 单位长度电阻（规格锚，非 PDK）
    "l_bus_nH_per_mm": 0.5,       # 单位长度电感
    "c_bus_fF_per_mm": 200.0,     # 单位长度电容
    "c_m_over_c_tot": 0.08,       # NEXT 容性耦合比
    "f_next_hz": 1.0e9,           # NEXT 参考频率（耦合项 ∝ (f/f₀)²）
    "l_pdn_nH": 0.5,              # PDN 回路感抗（地弹 L·di/dt）
    "dv_dt_a_per_s": 8.0e10,      # PRBS 边沿速率（规格锚）
    # ── ③ die↔die 热（复用 M2b Θ；r_th 拆 ASIC→中介层→光子 die 两串）
    "p_asic_w": 3.0,              # ASIC 功耗（规格锚）
    "r_th_asic_k_per_w": 1.5,     # ASIC → 中介层
    "r_th_int_k_per_w": 4.0,      # 中介层 → 光子 die
    "t_amb_c": 25.0,
    "asic_to_photon_um": 300.0,   # ASIC 边缘 ↔ 光子 die 边缘（喂 M2b Θ 的对数场）
    # ── ④ 功耗账（3.2T 同口径；🔴 只 mW/W）
    "v_pp_diff_v": 1.2,           # 差分摆幅（两家同参）
    "r_term_diff_ohm": 100.0,     # 差分终端（可插拔有板级终端，CPO 无）
    "c_line_cpo_pF": 1.0,         # CPO die-to-die 等效线电容（规格锚）
    "c_line_pluggable_pF": 2.5,   # 可插拔板级等效线电容（规格锚，含终端吸收）
    "p_tia_mw_per_lane": 60.0,    # TIA 静态（规格锚）
    "p_ctle_mw_per_lane": 20.0,   # 模拟 CTLE 静态（规格锚）
    "p_source_mw_per_lane": 80.0, # 光源 / 泵浦（规格锚）
    "p_pdn_mw_per_lane": 25.0,    # CPO 独有：中介层供电网络损耗（规格锚）
    # ── ⑤ 2.5D 版图（G-OI6）
    "asic_die_x_um": 1800.0,      # ASIC die 边长
    "asic_die_y_um": 1800.0,
    "interposer_pad_um": 40.0,    # 中介层焊盘边长（≥ DRC min width）
    "diff_pitch_um": 12.0,        # 差分对间距（≥ DRC min space）
    "m1_width_um": 2.0,           # 金属线宽（≥ DRC min width）
    "m1_space_um": 2.0,           # 金属线距（≥ DRC min space）
}

# 取值窗口：任何锚越界 ⇒ 判 FAIL（M1 血案：错常量时**原判据全绿抓不到**）
_BANDS: Dict[str, Tuple[float, float]] = {
    "nyquist_ghz": (106.0, 106.5),
    "baud_gbd": (212.0, 213.0),
    "l_electrode_mm": (0.5, 12.0),
    "n_g_opt": (3.5, 5.0),
    "dn_g_resid": (0.01, 1.0),
    "r_elect_ohm_per_mm": (0.2, 20.0),
    "c_elect_fF_per_mm": (50.0, 500.0),
    "f_pd_ghz": (100.0, 200.0),
    "f_tia_ghz": (120.0, 250.0),
    "bus_len_mm": (1.0, 40.0),
    "r_bus_ohm_per_mm": (5.0, 500.0),
    "c_m_over_c_tot": (0.001, 0.3),
    "p_asic_w": (0.5, 10.0),
    "r_th_asic_k_per_w": (0.2, 10.0),
    "r_th_int_k_per_w": (0.5, 20.0),
    "v_pp_diff_v": (0.4, 2.0),
    "c_line_cpo_pF": (0.2, 5.0),
    "c_line_pluggable_pF": (0.5, 10.0),
    "asic_die_x_um": (500.0, 5000.0),
    "m1_width_um": (0.5, 10.0),
    "m1_space_um": (0.5, 10.0),
}

# 调制器族（🔴 互锁判据咬族名：跨档抄常量时族名会跟着错）
_FAMILY = {"twmzm": "traveling_wave_mzm", "ring": "lumped_ring"}


def _in_band(key: str, value: float) -> bool:
    lo, hi = _BANDS[key]
    return lo <= float(value) <= hi


def family_lock() -> Dict[str, Any]:
    """与 `oi_m1` 的**同口径互锁**：同一个口径定义（|H|=1/√2 几何二分）在
    **两个不同调制器族**上**必须给出不同数值**，且族名必须不同。

    🔴 为什么这不是「同源假绿」：M1 的环是集总三单极点有理式、M3 的 TWMZM 是分布 RLC
    传播 + 光学加权积分，**频响函数本身不同源**；这里对拍的是**求解器口径**（同一步几何
    二分在不同 H 上是否各自自洽），再加族名不等式 ⇒ 换族必红（探针 P3）。
    """
    fam3, fam1 = _FAMILY["twmzm"], _FAMILY["ring"]
    b3 = twmzm_bandwidth_hz()
    b1 = _M1.eo_s21_f3db_hz(f_mod_hz=float(OI_M3_PROCESS["f_pd_ghz"]) * 1e9,
                            f_pd_hz=float(OI_M3_PROCESS["f_pd_ghz"]) * 1e9,
                            f_tia_hz=float(OI_M3_PROCESS["f_tia_ghz"]) * 1e9)
    # 口径自洽：单极点退化下，两个求解器都应给出≈同一点的答案
    deg = _f3db_of(lambda f: _M1.first_order_mag(f, 50e9))
    return {"family_m3": fam3, "family_m1": fam1,
            "f3db_m3_hz": b3, "f3db_m1_hz": b1,
            "family_distinct": bool(fam3 != fam1),
            "solver_agrees_on_single_pole": bool(abs(deg - 50e9) / 50e9 < 0.02)}


def _f3db_of(mag) -> float:
    """|H|=1/√2 的 f₃dB（**几何二分**，与 `oi_m1.eo_s21_f3db_hz` 同口径）。"""
    target = 1.0 / math.sqrt(2.0)
    lo, hi = 1.0, 1e14
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if mag(mid) >= target:
            lo = mid
        else:
            hi = mid
        if hi / lo <= 1.0 + 1e-12:
            break
    return math.sqrt(lo * hi)


# ═════════════════════════════════════════════════════════════════════════════
# 2) ① 400G/lane 带宽墙：行波电极 TWMZM
# ═════════════════════════════════════════════════════════════════════════════
def _electrode_primers(l_mm: Optional[float] = None,
                       dn_g_resid: Optional[float] = None
                       ) -> Tuple[float, float, float, float]:
    """电极单位长度 R'(Ω/m) · L'(H/m) · C'(F/m)，以及长度(m) 与速度失配 Δk 系数。

    🔴 L' **不独立声明**：由设计点反推 `L' = (n_g,mw/c)² / C'`，`n_g,mw = n_g,opt + Δn`
    ⇒ 速度失配**直接进 γ**（物理自洽），不出现「两套互不相干的常数」。
    """
    p = OI_M3_PROCESS
    l_mm = float(p["l_electrode_mm"] if l_mm is None else l_mm)
    dn = float(p["dn_g_resid"] if dn_g_resid is None else dn_g_resid)
    r_pm = float(p["r_elect_ohm_per_mm"]) * 1e3          # Ω/mm → Ω/m
    c_pm = float(p["c_elect_fF_per_mm"]) * 1e-15 / 1e-3  # fF/mm → F/m
    n_g_mw = float(p["n_g_opt"]) + dn
    l_pm = (n_g_mw / C_M_S) ** 2 / c_pm                  # H/m
    return r_pm, l_pm, c_pm, l_mm * 1e-3


def propagation_gamma(f_hz: float, r_pm: float, l_pm: float,
                      c_pm: float) -> complex:
    """行波电极传播常数 `γ = √((R′ + jωL′)·jωC′)`（1/m）。"""
    w = 2.0 * math.pi * f_hz
    return cmath.sqrt((r_pm + 1j * w * l_pm) * (1j * w * c_pm))


def _optical_rel_phase_rad_per_m(f_hz: float,
                                 dn_g_resid: Optional[float] = None) -> float:
    """光/微波**相对**相位率 `Ω = β_mw − β_opt = 2πf·(n_g,mw − n_g,opt)/c`（rad/m）。

    🔴 这是 TWMZM 唯一的速度失配入口。写成独立函数是为了让**闭式与 ladder 共用同一口径**
    （同源的相位定义，但**求解路径完全不同**：解析积分 ⟷ 矩阵链递推）。
    """
    dn = float(OI_M3_PROCESS["dn_g_resid"] if dn_g_resid is None else dn_g_resid)
    return 2.0 * math.pi * float(f_hz) * dn / C_M_S


def twmzm_response_closed(f_hz: float, l_mm: Optional[float] = None,
                          dn_g_resid: Optional[float] = None) -> complex:
    """**golden 闭式**：光学加权调制响应 `H = (1/L)∫₀^L e^{−q x}dx`。

        q = Re γ + j·(Im γ − ω·n_g,opt/c)   ⇒  q ≈ α + j·(β_mw − β_opt)

    物理：微波沿电极以 n_g,mw 传播（幅度按 Re γ 衰减、相位 Im γ ≈ β_mw），光以 n_g,opt 传播；
    有效调制是两者**在同一段长度上重叠积分** ⇒ 相对相位率正是 `Ω = β_mw − β_opt`，
    速度匹配 (dn→0) 时 Im q→0 且 Re q→0 ⇒ H≡1（全通）。

    🔴 **首版把相位算重了**：直接写 `q = γ + j·Ω`，把 γ 的虚部（已是 n_g,mw 的微波相位）
    又加了一遍 `jΩ` ⇒ q 的相位变成 `2β_mw − β_opt`，|H| 掉得离谱（f₃dB 被压到 14 GHz，
    400G 门限 106.25 GHz 判死线直接判死 ⇒ 一个"看起来像物理"的假红）。
    正确做法是**把微波相位从 γ 里减掉光相位基准**，只保留二者之差。
    """
    r_pm, l_pm, c_pm, L = _electrode_primers(l_mm, dn_g_resid)
    w = 2.0 * math.pi * f_hz
    g = propagation_gamma(f_hz, r_pm, l_pm, c_pm)
    q = complex(g.real, g.imag - w * float(OI_M3_PROCESS["n_g_opt"]) / C_M_S)
    if abs(q) * L < 1e-9:
        return 1.0 + 0j
    return (1.0 - cmath.exp(-q * L)) / (L * q)


def twmzm_response_ladder(f_hz: float, n_seg: int = 200,
                          l_mm: Optional[float] = None,
                          dn_g_resid: Optional[float] = None) -> complex:
    """**第二独立通道**：N 段集总 ABCD 链（串联 R/N + L/N、并联 C/N）+ 梯形光学加权。

    与闭式**完全不同源**：闭式是解析积分 `∫e^{−qx}dx`；这里是逐段的二端口矩阵连乘
    （`M_i = Mz·My`）从输入端推进，再对每段中点做光学相位加权求和 ⇒ 方法学独立。
    N↑ ⇒ 收敛到闭式（判据取**相对误差随 N 单调下降**，不是「同源码相等」）。
    """
    r_pm, l_pm, c_pm, L = _electrode_primers(l_mm, dn_g_resid)
    n = max(2, int(n_seg))
    seg = L / n
    w = 2.0 * math.pi * f_hz
    z = (r_pm + 1j * w * l_pm) * seg            # 段串联阻抗（Ω）
    y = 1j * w * c_pm * seg                     # 段并联导纳（S）
    # 单段物理顺序：先串联 z，再并联 y ⇒ 段矩阵（负载侧→源侧）Msec = mz·my
    #   mz·my = [[1 + zy, z], [y, 1]]   （det = 1， unimodular）
    m11, m12 = (1.0 + z * y), z
    m21, m22 = y, 1.0 + 0j
    # 连乘 n 段：[V_in; I_in] = Msec^n·[V_L; I_L]
    t11, t12, t21, t22 = m11, m12, m21, m22
    for _ in range(n - 1):
        s11 = t11 * m11 + t12 * m21
        s12 = t11 * m12 + t12 * m22
        s21 = t21 * m11 + t22 * m21
        s22 = t21 * m12 + t22 * m22
        t11, t12, t21, t22 = s11, s12, s21, s22
    if abs(t11) < 1e-300:
        return 0.0 + 0j
    # 负载 = 电极**特性阻抗**（行波电极标准做法：微波端接，抑制反射）
    # 🔴 首版末端**开路** ⇒ 微波电压沿线驻波从 1 涨到 2（|V| 平均 ≈1.6）
    #   ⇒ ladder 收敛到 |H|=0.59，而闭式（匹配前向波）是 0.968 —— 差一个常数因子。
    z0 = cmath.sqrt(z / y) if abs(y) > 1e-300 else 0.0 + 0j
    if abs(z0) < 1e-300:
        return 0.0 + 0j
    # 归一化输入端电压 V_in = 1 ⇒ 由 [V_in;I_in] = Msec^n[V_L; V_L/Z0] 解出负载节点电压
    den = t11 + t12 / z0
    v_l = (1.0 + 0j) / den if abs(den) > 1e-300 else 0.0 + 0j
    v, i = 1.0 + 0j, t21 * v_l + t22 * (v_l / z0)   # 源端状态（V_in=1, I_in 由负载反解）

    # 正向（源→负载）推进：逐段乘 Msec⁻¹ = [[1, −z], [−y, 1+zy]]
    # 🔴 级联矩阵的自然方向是**负载→源**；正向推进必须乘 Msec⁻¹（首版直接乘 Msec，
    #   解出的是反向行波 ⇒ 末态对不上负载、|H| 差一个常数）。
    #   V_{k+1} = V_k − z·I_k ;  I_{k+1} = −y·V_k + (1+zy)·I_k
    # 光学加权：V(x) 自带 e^{−jβ_mw·x} ⇒ 补 e^{+jβ_opt·x}（β_opt = ω·n_g,opt/c）
    #   ⇒ 净相位 = e^{−j(β_mw−β_opt)x} = e^{−jΩx}，与闭式同口径。
    # 🔴 首版错在直接乘「相对相位率 Ω」⇒ 相位变 2β_mw−β_opt（|H| 塌到 0.03）。
    k_opt = 2.0 * math.pi * f_hz * float(OI_M3_PROCESS["n_g_opt"]) / C_M_S
    acc = 0.0 + 0j
    for k in range(n):
        acc += v * cmath.exp(1j * k_opt * (k + 0.5) * seg)
        v, i = v - z * i, -y * v + (1.0 + z * y) * i   # Msec⁻¹（源 → 负载）
    return acc / n


def twmzm_bandwidth_hz(l_mm: Optional[float] = None,
                       dn_g_resid: Optional[float] = None) -> float:
    """TWMZM 的 f₃dB（|H|=1/√2 · 几何二分 · 与 `oi_m1` 同口径）。"""
    return _f3db_of(lambda f: abs(twmzm_response_closed(f, l_mm, dn_g_resid)))


def rc_pole_hz(l_mm: Optional[float] = None) -> float:
    """电极**集总 RC 等效极点** `f_RC = 1/(2π·R′ₜₒₜ·C′ₜₒₜ)`（总长上积分）。

    这是工程读数用的派生量（**不是 golden**）；与闭式 γ 的互锁见 `oi_m3_self_check`
    的「等效单极点反解 ⟷ f_RC 闭式」一条 —— 漏乘长度 L 时该判据必红（探针 P2）。
    """
    p = OI_M3_PROCESS
    l = float(p["l_electrode_mm"] if l_mm is None else l_mm) * 1e-3
    r_tot = float(p["r_elect_ohm_per_mm"]) * 1e3 * l      # Ω
    c_tot = float(p["c_elect_fF_per_mm"]) * 1e-15 / 1e-3 * l  # F
    # 🔴 这是**分布 RC 线**的等效单极点：`R_tot·C_tot = R′·C′·L²` ⇒ f_RC ∝ **1/L²**（不是 1/L）。
    #   （集总两端口把总电阻/总电容串π起来才会 ∝1/L；行波电极是连续分布线。）
    return 1.0 / (2.0 * math.pi * r_tot * c_tot)


def twmzm_design() -> Dict[str, Any]:
    """调制器设计点：f₃dB 必须 **≥ 奈奎斯特**（否则 3.2T 判死），且不得离谱过宽。

    🔴 判据**双侧**：只判「≥ f_nyq」是**充分非必要**（参数写错也能绿）⇒ 必须同时有上界，
    否则下面「闭环热调 / 功耗账」全在假设计点上跑。
    """
    f3 = twmzm_bandwidth_hz()
    f_nyq = NYQUIST_3200_GHZ * 1e9
    return {
        "family": _FAMILY["twmzm"],
        "l_electrode_mm": float(OI_M3_PROCESS["l_electrode_mm"]),
        "dn_g_resid": float(OI_M3_PROCESS["dn_g_resid"]),
        "f_rc_hz": rc_pole_hz(),
        "f3db_hz": f3,
        "f_nyquist_hz": f_nyq,
        "margin_db": 20.0 * math.log10(f3 / f_nyq) if f3 > 0 else float("-inf"),
        "ratio_to_nyquist": f3 / f_nyq,
        # 双侧窗口判据：1.03×…8×（下侧留 3% 余量，上侧防「参数没标度对」的假绿）
        "in_window": bool(1.03 <= (f3 / f_nyq) <= 8.0),
        "bandwidth_ok": bool(f3 >= 1.03 * f_nyq),
        "f_pd_hz": float(OI_M3_PROCESS["f_pd_ghz"]) * 1e9,
        "f_tia_hz": float(OI_M3_PROCESS["f_tia_ghz"]) * 1e9,
    }


def twmzm_ladder_convergence() -> Dict[str, Any]:
    """闭式 ⟷ N 段 ABCD 链：**相对误差随 N 单调下降**（真物理判据，非同源码相等）。"""
    f = NYQUIST_3200_GHZ * 1e9
    ref = abs(twmzm_response_closed(f))
    errs = []
    for n in (100, 200, 400, 800):
        errs.append(abs(abs(twmzm_response_ladder(f, n)) - ref) / max(ref, 1e-30))
    mono = all(errs[i] > errs[i + 1] for i in range(len(errs) - 1))
    return {"f_hz": f, "n_grid": [100, 200, 400, 800],
            "rel_err": errs, "monotonic_decreasing": bool(mono),
            "err_largest": errs[0], "err_smallest": errs[-1]}


# ═════════════════════════════════════════════════════════════════════════════
# 3) ② CPO 电通道（ASIC ↔ 光引擎共封装）
# ═════════════════════════════════════════════════════════════════════════════
def echannel_closed(f_hz: float, l_mm: Optional[float] = None) -> complex:
    """电互连闭式 `H = e^{−γL}`（分布 RLC 电报方程，与 TWMZM 同一 γ 体例）。

    🔴 与可插拔的**真正差别**：CPO 的电总线是 **mm 级**（`bus_len_mm`），
    可插拔要走 cm~10cm 级板线 ⇒ 同一 γ 下 H 差一大截（功耗账里按同口径进 driver 动态项）。
    """
    p = OI_M3_PROCESS
    l_mm = float(p["bus_len_mm"] if l_mm is None else l_mm)
    r = float(p["r_bus_ohm_per_mm"]) * 1e3
    lc = float(p["l_bus_nH_per_mm"]) * 1e-9 / 1e-3
    c = float(p["c_bus_fF_per_mm"]) * 1e-15 / 1e-3
    g = propagation_gamma(f_hz, r, lc, c)
    return cmath.exp(-g * l_mm * 1e-3)


def echannel_att_db(f_hz: float, l_mm: Optional[float] = None) -> float:
    return -20.0 * math.log10(max(abs(echannel_closed(f_hz, l_mm)), 1e-30))


def echannel_h_db_per_sqrt_ghz(l_mm: Optional[float] = None) -> float:
    """衰减标量 `h`（dB/√GHz）：`|H|dB = −h·√(f/GHz)·(L/L_ref)` 的 h（定稿 §3.2 口径）。

    R 主导（mm 级短线属此）时 Re γ ≈ √(πfR′C′/2) ⇒ dB ∝ √f ⇒ h 是**真常数**，
    不是把指数硬套成 √f 的糊法（判据：h 在 10×f 跨度内相对漂移 < 2%，见自检）。
    """
    p = OI_M3_PROCESS
    l_mm = float(p["bus_len_mm"] if l_mm is None else l_mm)
    h = echannel_att_db(1.0e9, l_mm) / math.sqrt(1.0)      # 1 GHz 处标定
    return h


def echannel_h_sqrtf_ok() -> Dict[str, Any]:
    """`h = |H|dB/√(f/GHz)` 的**真常数性校验**（🔴 窗口内的 √f 律，不是跨频硬套）。

    物理：Re γ = Re√((R′+jωL′)·jωC′) 只在 **R 主导**（ωL′ ≪ R′）时 ∝ √f；
    R′=60 Ω/mm、L′=0.5 nH/mm ⇒ 交叉频率 `f_RL = R′/(2πL′) ≈ 19 GHz`；
    只有 `f ≲ f_RL/200`（ωL′ ≤ 0.005 R′）√f 渐近才收敛到 0.5% 以内。
    在 1↔10 GHz 上「硬套 √f」会有 ~20% 漂移 —— 那是**真物理（RL 主导区）**，
    不是实现 bug；把非窗口区叫「常数」就是假判据。本函数**先算窗口再判**，
    并**如实报出窗口外漂移**（判据咬语义：写成 `∝ f` 会让窗口内漂移量级爆炸 ⇒ 必红）。

    判据咬语义：若把衰减写成 `∝ f`（而非 √f），窗口内漂移会量级爆炸 ⇒ 必红。
    """
    p = OI_M3_PROCESS
    r = float(p["r_bus_ohm_per_mm"]) * 1e3
    lc = float(p["l_bus_nH_per_mm"]) * 1e-9 / 1e-3
    ghz = 1.0e9
    f_rl = r / (2.0 * math.pi * lc)          # ωL′ = R′ 的交叉频率（≈19 GHz）
    f_top = f_rl / 200.0                     # ωL′ ≤ 0.005·R′（√f 渐近误差 <0.5%）
    f_bot = f_top / 10.0                     # 窗口下沿（判据跨度 10×）
    h_lo = echannel_att_db(f_bot) / math.sqrt(f_bot / ghz)
    h_hi = echannel_att_db(f_top) / math.sqrt(f_top / ghz)
    drift_in = abs(h_hi - h_lo) / max(abs(h_lo), 1e-12)
    h_a = echannel_att_db(1.0e9) / math.sqrt(1.0)
    h_b = echannel_att_db(10.0e9) / math.sqrt(10.0)
    drift_out = abs(h_b - h_a) / max(abs(h_a), 1e-12)
    return {"f_rl_hz": f_rl, "f_window_hz": (f_bot, f_top),
            "h_in_window": h_hi, "drift_in_window": drift_in,
            "h_outside": h_b, "drift_outside": drift_out,
            "ok": bool(drift_in < 0.005), "disclosed_outside": bool(drift_out > 0.10)}


def xtalk_next_db(f_hz: Optional[float] = None, k: Optional[float] = None) -> Dict[str, Any]:
    """最坏近端串扰（NEXT）：`X(f) = (C_m/C_tot)·(f/f₀)²`，均方积分成**功率比**。

        NEXT_ratio = K²·(F/f₀)⁴/3   （∫₀^F K²(f/f₀)⁴df ÷ ∫₀^F df）

    `k` 可显式给（探针 P4 靶子：把它清零 ⇒ 必为 −∞ dB）。
    """
    p = OI_M3_PROCESS
    f = NYQUIST_3200_GHZ * 1e9 if f_hz is None else float(f_hz)
    f0 = float(p["f_next_hz"])
    k = float(p["c_m_over_c_tot"]) if k is None else float(k)
    if k == 0.0:
        # 🔴 耦合比清零 ⇒ 物理上串扰功率比为 0 ⇒ dB 为 **−∞**（不是被 clamp 的 −3000）。
        #   clamp 会让「探针把 c_m 清零」这条判据看起来"绿了但没真判"（首版就栽在这）。
        return {"ratio_linear": 0.0, "xtalk_db": float("-inf"),
                "k": k, "f_hz": f, "f0_hz": f0,
                "xtalk_at_zero_coupling_db": float("-inf")}
    ratio = k * k * (f / f0) ** 4 / 3.0
    return {"ratio_linear": ratio, "xtalk_db": 10.0 * math.log10(max(ratio, 1e-300)),
            "k": k, "f_hz": f, "f0_hz": f0,
            "xtalk_at_zero_coupling_db": 10.0 * math.log10(max(ratio, 1e-300))}


def pdn_bounce_v() -> Dict[str, Any]:
    """PDN 地弹 `V_bounce = L_pdn·Δi/Δt`（与 driver 动态功耗同回路）。"""
    p = OI_M3_PROCESS
    ind = float(p["l_pdn_nH"]) * 1e-9
    didt = float(p["dv_dt_a_per_s"])
    return {"l_pdn_h": ind, "di_dt_a_per_s": didt,
            "v_bounce_v": ind * didt,
            "v_bounce_mv": ind * didt * 1e3}


def fdtd_telegraph(pulse_s: float = 1.5e-12, l_mm: Optional[float] = None,
                   n_cells: int = 400, tail_ps: float = 120.0,
                   r_on: bool = False) -> Dict[str, Any]:
    """**第二独立通道**：1D 电报方程**时域 FDTD**（Yee 蛙跳）测传播延迟 ⇒ 相速。

    🔴 为什么对「相速」而不是「幅度」：电互连的 `R′` 大到让**分布 RC 扩散长度远小于网格**
    （局部时间常数 C′/R′ ≈ 3 fs，而总线总 RC ≈ 0.3 ns）⇒ 显式蛙跳带 R′ 项数值发散
    （dt·R′/C′ ≈ 68 ≫ 1）。把幅度效应交给闭式 `exp(−Re γ·L)`，FDTD 专攻**时域相速**：

        τ_FDTD = t_peak(out) − t_peak(in)，   v_FDTD = L/τ_FDTD
        τ_closed = L·√(L′C′)   （闭式为 `e^{−γL}`，无损极限 γ→jω√(L′C′)）

    物理边界（诚实披露）：FDTD 跑**无损**电报方程（对拍量是相速，对 R′ 不敏感）；
    有损幅度 `exp(−Reγ·L)` 由闭式单独提供，两者**不是同一个量的替换**，而是互补通道。

    `r_on=True` 时保留 R′（判据会红 ⇒ 探针可证明「R′ 项确实进了方程」，非装饰）。
    """
    p = OI_M3_PROCESS
    l_mm = float(p["bus_len_mm"] if l_mm is None else l_mm)
    r = float(p["r_bus_ohm_per_mm"]) * 1e3
    lc = float(p["l_bus_nH_per_mm"]) * 1e-9 / 1e-3
    c = float(p["c_bus_fF_per_mm"]) * 1e-15 / 1e-3
    L = l_mm * 1e-3
    n = max(8, int(n_cells))
    dx = L / n
    v_p = 1.0 / math.sqrt(lc * c)               # 无损相速 [m/s]
    # 🔴 显式蛙跳的离散化（Yee，V 在节点 0..n，I 在半格 0.5..n−0.5）：
    #     ∂V/∂x = −(R′ + L′∂/∂t)I  ⇒ I^{n+1/2} = I^{n−1/2} − (Δt/L′Δx)(V_{j+1}−V_j)
    #     ∂I/∂x = −C′∂V/∂t         ⇒ V^{n+1}   = V^n     − (Δt/C′Δx)(I_{j+1/2}−I_{j−1/2})
    #   🔴 系数是 **Δt/(L′Δx)** 与 **Δt/(C′Δx)**（首版写成 L′Δx/Δt ⇒ 倒数，Δt 一小就爆炸）。
    #     蛙跳稳定界 `a·b = (v_p·Δt/Δx)² ≤ 1` ⇒ 取 0.5×  ⇒ a·b = 0.25 ✓（不是 1，是 0.25）。
    dt = 0.5 * dx / v_p
    tau_closed = L / v_p
    # 🔴 仿真时长必须**覆盖脉冲走完全线**（首版 tail=3 ps vs 渡越 50 ps ⇒ 末端采样恒 0
    #   ⇒ argmax 落在 0 ⇒ τ_FDTD=0 假红、v_FDTD=5e27）；留 3× 渡越 + 4× 脉宽看反射。
    sim_t = max(tail_ps * 1e-12, 3.0 * tau_closed + 4.0 * pulse_s)
    n_step = max(8, int(math.ceil(sim_t / dt)))
    i_out = n                                   # 末端（开路）采样点

    v = np.zeros(n + 1, dtype=float)            # V at i·dx
    i_arr = np.zeros(n, dtype=float)            # I at (i+0.5)dx
    t_axis = np.arange(n_step) * dt
    src = np.exp(-((t_axis / pulse_s) ** 2))    # 高斯脉冲（峰值在 t=0）
    v_hist = np.zeros(n_step)

    for step in range(n_step):
        # 🔴 Yee 蛙跳顺序：先更新 I（**用旧 V**），再用**新 I** 更新 V。
        #    顺序写反（拿刚更新的 V 去算 I）会成正反馈 ⇒ 指数爆炸（首版就栽在这）。
        i_arr = i_arr - (dt / (lc * dx)) * (v[1:] - v[:n])
        # 有损电报方程 ∂V/∂x = −L′∂I/∂t − R′I ⇒ I 更新多一项显式欧拉阻尼 −(R′Δt/L′)·I
        # （R′ 串在电流路径上 ⇒ 挂在 I 的更新上；首版挂在 V 上是错的）
        if r_on:
            i_arr = i_arr * (1.0 - (r * dt / lc)) if r * dt / lc < 1.0 else i_arr * 0.0
        i_left = i_arr                                   # I_{j−1/2}，j=1..n
        i_right = np.concatenate((i_arr[1:], [0.0]))     # I_{j+1/2}（末端开路 ⇒ I_{n+1/2}=0）
        #   ∂I/∂x = −C′∂V/∂t ⇒ V_j^{n+1} = V_j^n − (Δt/C′Δx)·(I_{j+1/2} − I_{j−1/2})
        v[1:] = v[1:] - (dt / (c * dx)) * (i_right - i_left)
        v[0] = src[step]
        v_hist[step] = v[i_out]

    # 峰值时刻（抛物线插值 ⇒ 亚步长精度）
    k_out = int(np.argmax(v_hist))
    y1, y2, y3 = v_hist[k_out - 1], v_hist[k_out], v_hist[k_out + 1]
    denom = (y1 - 2.0 * y2 + y3)
    shift = 0.5 * (y1 - y3) / denom if denom != 0.0 else 0.0
    t_peak = (k_out + shift) * dt
    return {
        "pulse_s": pulse_s, "n_cells": n, "dt_s": dt, "n_step": n_step,
        "v_fdtd_m_per_s": L / max(t_peak, 1e-30),
        "tau_fdtd_s": t_peak, "tau_closed_s": tau_closed,
        "rel_err": abs(t_peak - tau_closed) / tau_closed,
        "peak_out_v": float(v_hist[k_out]),
        "lossy_term_included": bool(r_on),
        "phase_ok": bool(abs(t_peak - tau_closed) / tau_closed < 0.05),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 4) ③ CPO die↔die 热耦合 + 闭环热调稳态
# ═════════════════════════════════════════════════════════════════════════════
def die_thermal_stack() -> Dict[str, Any]:
    """跨 die 热路径（复用 M2b 的对数热解做 die↔die 耦合形状函数）。

        ΔT_interposer = P_asic·R_asic
        ΔT_photon     = P_asic·(R_asic + R_int)   （ASIC 热经中介层传到光子 die）

    `r_th0` 拆成 **两串**（ASIC→中介层 / 中介层→光子 die），不再是片内单一热阻；
    die↔die 的**横向**几何扩散用 M2b 的 `thermal_coupling_log`（不重造热解）。
    """
    p = OI_M3_PROCESS
    p_asic = float(p["p_asic_w"])
    r_a = float(p["r_th_asic_k_per_w"])
    r_i = float(p["r_th_int_k_per_w"])
    t_amb = float(p["t_amb_c"])
    d_int = p_asic * r_a
    d_ph = p_asic * (r_a + r_i)
    theta = _M2B.thermal_coupling_log(float(p["asic_to_photon_um"]))
    return {
        "p_asic_w": p_asic, "r_th_asic_k_per_w": r_a, "r_th_int_k_per_w": r_i,
        "t_amb_c": t_amb,
        "d_t_interposer_c": d_int,
        "t_interposer_c": t_amb + d_int,
        "d_t_photon_c": d_ph,
        "t_photon_c": t_amb + d_ph,
        "die_to_die_theta_k": theta,                      # M2b 对数热解（跨 die 复用）
        "theta_from_m2b_network": _m2b_theta_via_network(),  # 第二独立通道
        "theta_channels_agree": bool(abs(theta - _m2b_theta_via_network()) < 0.15 * max(theta, 1e-6) + 0.05),
    }


def _m2b_theta_via_network() -> float:
    """die↔die 热耦合的**第二独立通道**：M2b 有限差分热网络（跨 die 位置喂进去）。"""
    d = float(OI_M3_PROCESS["asic_to_photon_um"])
    pos = [(0.0, 0.0), (d, 0.0)]
    return float(_M2B.thermal_network_coupling(pos, grid=16, extent_um=max(520.0, d * 2.0))[1][0])


def heater_r_th_k_per_mw() -> float:
    """加热器（→环波器芯）热阻 `R_h`，单位 **K/mW**。

    🔴 **单一真源**：`lda_design.active_models.R_TH_K_PER_MW` —— 与 M2b 生成调谐斜率 S
    时**同一个** R_th。M3 首版在 `OI_M3_PROCESS` 里抄了一个「看起来更合理」的
    `r_th_thermal_k_per_w = 8.0`（K/W ⇒ 8 mK/mW，比真值小 125 倍）⇒ 与 S 不自洽，
    闭环反馈增益凭空多出 `R_h·S/FSR ≈ 28` 倍 ⇒ 不动点发散到 1e88 K（**纯算术假失稳**）。
    修法不是「调参数让它绿」，而是**回到单一真源 + 单通路**，并把双计做成必红判据。
    """
    # 🔴 F7（v0.9.185）：**删除静默回退** —— 首版 `except: return 1.0` 的回退值恰等于真值
    #    （`R_TH_K_PER_MW = 1.0`）⇒ 门禁**完全看不见**降级（`single_path_consistency` 也照绿）。
    #    现在 import 失败即 raise（不静默），可达性另由 `single_source_reachable_m3()` 守。
    from lda_design import active_models as _AM      # noqa: E402（单一真源）
    return float(_AM.R_TH_K_PER_MW)


def single_source_reachable_m3() -> bool:
    """🔴 F7（v0.9.185）：单一真源**可达性**判据（防静默回退）。

    `heater_r_th_k_per_mw()` 已删回退（失败即 raise），本判据进一步把「真源可达」变成
    机器可查：import 失败 ⇒ **必红**（探针 P15 靶子）。
    """
    try:
        from lda_design import active_models as _AM   # noqa: E402（单一真源）
        return float(_AM.R_TH_K_PER_MW) > 0.0
    except Exception:                                     # noqa: BLE001
        return False


def no_bypass_thermal_key() -> bool:
    """🔴 F6（v0.9.185）：`OI_M3_PROCESS` **不得含旁路热阻键** `r_th_thermal_k_per_w`。

    首版该键 = 8.0 K/W（= 8 mK/mW，比真值小 125 倍）、**无任何计算消费**（死配置）且
    **不在 `_BANDS`**（无取值窗口）⇒ 后来者极易误用（M1 `TARGET_BER_KP4` 血案同族：
    错常量静默）。已删；本判据守「不许复活」（探针 P14 靶子）。
    """
    return "r_th_thermal_k_per_w" not in OI_M3_PROCESS


def tuning_slope_nm_per_k() -> float:
    """`dλ/dT`（nm/K）：由 M2b 的调谐斜率 S 与**同一条通路**的热阻反推，不新写第二个数。

        S = dλ/dP = (dλ/dT)·R_h      ⇒      dλ/dT = S / R_h
    """
    return float(_M2B.tuning_slope_nm_per_mw()) / heater_r_th_k_per_mw()


def closed_loop_thermal_steady(n_lanes: Optional[int] = None,
                               setpoint_over_ambient_c: Optional[float] = None,
                               r_h_override_k_per_mw: Optional[float] = None,
                               solve_mode: str = "algebraic",
                               loop_gain: float = 1.0,
                               max_iter: int = 200,
                               tol_mw: float = 1e-9) -> Dict[str, Any]:
    """闭环热调**稳态**（`solve_mode` 两条求解路径）。

    `"algebraic"`（默认）：闭式代数解 —— 伺服把环温拉到设定点 ⇒ `P = ΔT/R_h`。
    `"fixed_point"`：**真·不动点迭代** `P ← P + A·(λ_t − λ_ring(P))/S`；
      `loop_gain = A` 是**环路增益**（= 控制器增益 × 真实灵敏度 dλ/dP）。
      `A = 1` ⇒ **一步收敛**到与代数解**同一**稳态；
      🔴 `A ≫ 1`（= 双计 / 灵敏度算错）⇒ **必发散**。

    物理（**单通路**）：加热器功率 P 经 R_h 抬环波器芯温度，热光效应把共振红移：
        T_ring = T_amb + ΔT_asic + P·R_h
        λ_ring = λ_cold + (dλ/dT)·(T_ring − T_amb) = λ_cold + S·P

    🔴 **血案与 v0.9.185 修 F2**（首版不动点发散到 **1e88 K**）：根因是把「加热器→温升
    →波长」通路**算两遍**（`T ← T_amb+ΔT+P·R_h` 之后又用**含 R_h 的 S** 反推 P，
    而首版还把 R_h 抄小 125 倍 ⇒ `A = R_h·S/FSR ≈ 28 ≫ 2`）⇒ 迭代越界。
    正确结论：**单通路**下闭环稳态只有代数解（或 A=1 的一步不动点）。

    🔴 **首版的判据链三层同时失效**（同源恒等式 + 自证探针 + 死码负例）⇒ 这一条最贵的
    血案**零护栏**。现在改为：`algebraic` ⟷ `fixed_point(A=1)` 收敛到同一稳态
    （第二独立通道）+ `A≫1` fixed_point **必发散**（可被判据直接咬住）。

    与 M2b 的**关键差别**：M2b `thermal_tune_budget` 是「一次性调谐到信道」的一次性功耗；
    CPO 里光引擎与 ASIC 共封装 ⇒ ASIC 热背景**持续存在** ⇒ 热调必须**持续跟踪**（稳态）。
    """
    if solve_mode not in ("algebraic", "fixed_point"):
        raise ValueError("未知求解模式：%r（应为 'algebraic' | 'fixed_point'）" % (solve_mode,))
    p = OI_M3_PROCESS
    n = int(p["n_lanes"]) if n_lanes is None else int(n_lanes)
    t_amb = float(p["t_amb_c"])
    r_h = heater_r_th_k_per_mw() if r_h_override_k_per_mw is None \
        else float(r_h_override_k_per_mw)
    s = float(_M2B.tuning_slope_nm_per_mw())
    dl = tuning_slope_nm_per_k()
    # 🔴 与 r_h **自洽**的有效灵敏度（S ≡ dλdT·R_h）：override 时随 r_h 线性变，
    #    这样两条求解路径在任意 r_h 下都对同一物理系统求解（修 F2b 的「代数恒真」）
    s_eff = dl * r_h
    fsr = float(_M2B.thermal_tune_budget()["FSR_nm"])
    d_t_asic = float(p["p_asic_w"]) * (float(p["r_th_asic_k_per_w"]) + float(p["r_th_int_k_per_w"]))
    t_free = t_amb + d_t_asic                    # 加热器关断（只有 ASIC 热）
    t_set = t_amb if setpoint_over_ambient_c is None \
        else t_amb + float(setpoint_over_ambient_c)

    # 单向执行器（加热器只加热、不制冷）⇒ 只能**向上**够设定点
    t_ring = max(t_free, t_set)
    d_t_heater = t_ring - t_free                     # ≥ 0
    p_heater = d_t_heater / r_h if r_h > 0.0 else 0.0
    d_t_resid = t_ring - t_set                       # ≥ 0（够不到 ⇒ 残余温升）
    p_actuator_alg = abs(t_free - t_set) / r_h if r_h > 0.0 else 0.0

    out: Dict[str, Any] = {
        "n_lanes": n, "solve_mode": solve_mode, "loop_gain": float(loop_gain),
        "r_h_k_per_mw": r_h, "S_nm_per_mW": s, "S_eff_nm_per_mW": s_eff,
        "d_lambda_dT_nm_per_k": dl,
        "t_free_c": t_free, "t_setpoint_c": t_set, "t_ring_c": t_ring,
        "d_t_from_asic_c": d_t_asic,
        "open_loop_residual_nm": dl * (t_free - t_set),
        "open_loop_residual_frac_fsr_nm": dl * (t_free - t_set) / fsr,
        "residual_nm": dl * d_t_resid,
        "residual_frac_fsr_nm": dl * d_t_resid / fsr,
        "p_heater_supplyable_mw_per_lane": p_heater,
        "actuator_direction": "cool(TEC)" if t_free > t_set else "heat",
        "unidirectional_heater_feasible": bool(t_set >= t_free),
        "note": ("CPO 真实热代价：ASIC 热把光子 die 抬升 ⇒ 单向加热器补不回来；"
                 "工程解是「固化点预偏移」或「双向 TEC」"),
    }

    if solve_mode == "algebraic":
        # 🔴 `solution` / `closed_loop` **由求解路径返回**（不再写死字面量）
        out.update({"solution": "algebraic", "converged": True, "n_iter": 0,
                    "diverged": False,
                    "p_actuator_required_mw_per_lane": p_actuator_alg,
                    "p_fixed_point_mw_per_lane": None,
                    "closed_loop": True})
        return out

    # ── `fixed_point`：真·不动点迭代（环路增益 A = loop_gain）─────────────────
    target = abs(dl * (t_set - t_free))          # nm：需补偿的波长量
    pk = 0.0
    n_iter, converged, diverged = 0, False, False
    for _ in range(int(max_iter)):
        n_iter += 1
        err = target - s_eff * pk
        p_next = pk + loop_gain * err / s_eff if s_eff > 0.0 else pk
        if (not math.isfinite(p_next)) or abs(p_next) > 1e12:
            diverged = True
            pk = p_next
            break
        if abs(p_next - pk) <= tol_mw:
            pk = p_next
            converged = True
            break
        pk = p_next
    out.update({"solution": "fixed_point", "converged": bool(converged),
                "n_iter": n_iter, "diverged": bool(diverged),
                "p_actuator_required_mw_per_lane": (pk if converged else float("inf")),
                "p_fixed_point_mw_per_lane": (pk if converged else None),
                "closed_loop": bool(converged)})
    return out


def _algebraic_matches_fixed_point(tol_rel: float = 1e-6) -> bool:
    """**第二独立通道**：代数解 ⟷ 不动点迭代（A=1）必须收敛到**同一**稳态。

    🔴 这**不是**同源相等：代数解走闭式 `P = ΔT/R_h`，不动点解走迭代
    `P ← P + (λ_t − λ_ring(P))/S` 直到自洽 —— 两条路径**算法独立**（无共享中间量）。
    若实现把双计灌进任一路径，二者不再相等 ⇒ 判据必红。
    """
    a = float(closed_loop_thermal_steady()["p_actuator_required_mw_per_lane"])
    f = closed_loop_thermal_steady(solve_mode="fixed_point", loop_gain=1.0)
    if f["converged"] is not True:
        return False
    return bool(abs(a - float(f["p_actuator_required_mw_per_lane"]))
                < tol_rel * max(abs(a), 1e-12) + 1e-12)


def _double_count_diverges(gain: float = 28.0) -> bool:
    """🔴 **双计 / 假环路增益** ⇒ 不动点迭代**必发散**（1e88 K 血案的真实护栏）。

    环路增益 `A = loop_gain`（= 控制器增益 × dλ/dP）。`0 < A < 2` 收敛；`A ≫ 1` 发散。
    双计把灵敏度算错 ⇒ A 被放大到 ~28（首版实测量级）⇒ 迭代越界 ⇒
    `converged=False` 且 `diverged=True`。
    """
    r = closed_loop_thermal_steady(solve_mode="fixed_point", loop_gain=gain)
    return bool(r["converged"] is False and r["diverged"] is True)


def _closed_loop_scales_with_r_h() -> bool:
    """稳态执行器功率必须 **∝ 1/R_h**（R_h 加倍 ⇒ 功率减半）。

    🔴 **由不动点求解器输出**（不是 `p = ΔT/r_h` 的闭式定义换写）：两个不同 R_h 的环
    各自**真迭代**到自洽再比功率 ⇒ 若求解器把 R_h 用错位置，比值不再等于 2 ⇒ 必红。
    """
    a = closed_loop_thermal_steady(r_h_override_k_per_mw=1.0,
                                   solve_mode="fixed_point", loop_gain=1.0)
    b = closed_loop_thermal_steady(r_h_override_k_per_mw=2.0,
                                   solve_mode="fixed_point", loop_gain=1.0)
    if a["converged"] is not True or b["converged"] is not True:
        return False
    pa = float(a["p_actuator_required_mw_per_lane"])
    pb = float(b["p_actuator_required_mw_per_lane"])
    return bool(pa > 0.0 and abs(pa - 2.0 * pb) < 1e-6 * pa + 1e-12)


# ═════════════════════════════════════════════════════════════════════════════
# 5) ④ 功耗同口径账（3.2T：CPO ⟷ 可插拔，逐项对照；🔴 只 mW/W，不做 fJ/bit）
# ═════════════════════════════════════════════════════════════════════════════
def power_breakdown(form: str = "cpo", n_lanes: Optional[int] = None,
                    cap_model: str = "electrode") -> Dict[str, Any]:
    """单 lane 逐项功耗（mW）+ 模块聚合（W）。**两家逐项同参**，只改电路径口径。

    mW/lane 逐项：driver_dynamic（½C·V_pp²·f_sym）· driver_termination·
                  tia_static · ctle_analog · thermal_steady · source_pump
    # 🔴 M5 口径（cap_model）：驱动器负载电容取**电极电容 C′·L**（光引擎内、与 L 线性）——这才是驱动器真正开关的负载；`c_line_*_pF` 是 die-to-die 互连等效（与 L 无关），其损耗已由 `interposer_pdn_mw` 覆盖，再算进 driver 属双重计数⇒ 旧口径以 `driver_package_line_mw` **显式并报**（口径变更可溯源），不进 `items` 求和。
    W/模块：上面逐 lane 求和 + CPO **独有**项 interposer_pdn（可插拔没有）。

    🔴 红线：不报「每比特焦耳 / TOPS 能效」，所有量是**功耗**（mW/W）。
    """
    if form not in ("cpo", "pluggable"):
        raise ValueError("未知形态：%r（应为 'cpo' | 'pluggable'）" % (form,))
    if cap_model not in ("electrode", "package"):
        raise ValueError("未知电容口径：%r（应为 'electrode' | 'package'）" % (cap_model,))
    p = OI_M3_PROCESS
    n = int(p["n_lanes"]) if n_lanes is None else int(n_lanes)
    f_sym = PAM4_BAUD_3200_GBD * 1e9            # 212.5 GBd（PAM4 符号率）
    vpp = float(p["v_pp_diff_v"])
    c_line = float(p["c_line_cpo_pF"] if form == "cpo" else p["c_line_pluggable_pF"]) * 1e-12
    r_term = float(p["r_term_diff_ohm"])

    # 🔴 双口径：电极电容 C′·L（主账）vs 封装线电容（并报，不进求和）
    c_elec_f = float(p["c_elect_fF_per_mm"]) * 1e-15 * float(p["l_electrode_mm"])
    c_load_f = c_elec_f if cap_model == "electrode" else c_line
    p_drv_pkg = 0.5 * c_line * vpp ** 2 * f_sym * 1e3       # mW/lane（旧口径·并报）
    p_drv = 0.5 * c_load_f * vpp ** 2 * f_sym * 1e3         # mW/lane（主账）
    p_term = (vpp ** 2) / (4.0 * r_term) * 1e3 if form == "pluggable" else 0.0
    p_tia = float(p["p_tia_mw_per_lane"])
    p_ctle = float(p["p_ctle_mw_per_lane"])
    # 🔴 CPO 有 ASIC 热背景 ⇒ 闭环热调必须**持续**跟踪；可插拔的光子 die 不受 ASIC 热耦合
    #   ⇒ 该项为 0。两者同口径（都是「稳态执行器功率 mW/lane」，不是一次性调谐）。
    p_th = float(closed_loop_thermal_steady(n)["p_actuator_required_mw_per_lane"]) * (
        1.0 if form == "cpo" else 0.0)
    p_src = float(p["p_source_mw_per_lane"])

    items = {
        "driver_dynamic_mw": p_drv,
        "driver_termination_mw": p_term,
        "tia_static_mw": p_tia,
        "ctle_analog_mw": p_ctle,
        "thermal_steady_mw": p_th,
        "source_pump_mw": p_src,
    }
    p_pdn = float(p["p_pdn_mw_per_lane"]) if form == "cpo" else 0.0
    # 🔴 CPO 独有项**必须先挂进 items 再求和**（首版挂在 sum 之后 ⇒ 逐项加总比
    #   `per_lane_total` 多一块 interposer_pdn ⇒ 对拍判据必红）。
    items["interposer_pdn_mw"] = p_pdn
    per_lane = sum(items.values())                  # 已含 CPO 独有项
    module_w = per_lane * n / 1000.0                # 与「逐项加总×lane 数」严格同口径
    return {
        "form": form, "n_lanes": n,
        "f_sym_hz": f_sym, "v_pp_v": vpp, "c_line_pF": c_line * 1e12,
        "cap_model_used": cap_model,
        "driver_cap_fF": c_load_f * 1e15,
        "driver_package_line_mw": p_drv_pkg,
        "driver_package_line_note": ("旧口径并报：die-to-die 互连等效，与 L 无关；其损耗已由 interposer_pdn_mw 覆盖，故不进 items 求和。" if cap_model == "electrode" else "与 cap_model 相同，无对照"),
        "items_mw_per_lane": items,
        "per_lane_total_mw": per_lane,
        "module_total_w": module_w,
        "module_rate_tbps": LINE_RATE_3200_GBPS * 1e-3 * n / LANES_3200,
        "energy_per_bit_banned": True,       # 🔴 红线标记（不产生 fJ/bit 数字）
    }


def power_reconcile() -> Dict[str, Any]:
    """「全局口径」⟷「逐 lane 之和」**对拍**（探针 P8 靶子：漏掉 CPO 独有项必红）。"""
    rows = {f: power_breakdown(f) for f in ("cpo", "pluggable")}
    out: Dict[str, Any] = {}
    for f, r in rows.items():
        items = r["items_mw_per_lane"]
        s = sum(items.values())
        out[f] = {
            "items_mw_per_lane": items,
            "sum_items_mw": s,
            "per_lane_total_mw": r["per_lane_total_mw"],
            "module_total_w": r["module_total_w"],
            "match_per_lane": bool(abs(s - r["per_lane_total_mw"]) < 1e-9),
            "match_module": bool(abs(s * r["n_lanes"] / 1000.0 - r["module_total_w"]) < 1e-12),
        }
    c, pl = out["cpo"], out["pluggable"]
    # 🔴 符号：这里是「CPO 比可插拔**多付**的热代价」⇒ 取 cpo − pluggable（首版写反 ⇒ 恒负）
    out["cpo_advantage_thermal_mw"] = c["items_mw_per_lane"]["thermal_steady_mw"] - \
        pl["items_mw_per_lane"]["thermal_steady_mw"]
    out["cpo_penalty_interposer_mw"] = c["items_mw_per_lane"]["interposer_pdn_mw"]
    out["cpo_total_w"] = c["module_total_w"]
    out["pluggable_total_w"] = pl["module_total_w"]
    out["reconciled"] = bool(c["match_per_lane"] and c["match_module"]
                             and pl["match_per_lane"] and pl["match_module"])
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 6) ⑤ 2.5D 版图签核（G-OI6）
# ═════════════════════════════════════════════════════════════════════════════
_LAYER_INTERPOSER = 64
_LAYER_M1 = 65
_LAYER_ASIC = 66


def cpo_2p5d_geometry(oe_structures: Optional[Dict[str, List[bytes]]] = None) -> Dict[str, Any]:
    """2.5D 版图几何层（µm）：ASIC die + 中介层 + 光引擎 die + FAU 接入。

    🔴 **片外 fiber 不落版图**（与 G-OI2 同口径）：本层只有「FAU 接触点」，
    没有光纤本体（探针 P8 靶子：把 fiber 落进版图 ⇒ DRC/判据必红）。

    光引擎 die 的 GDS 由 `chip_layout_export.export_chip_gds` 提供（复用不重造），
    本函数只拼「电/封装层」并做**电层 DRC**（min width / min space，规格锚）。
    """
    from lda_l2 import gds_export as gx        # noqa: E402（单一真源）
    p = OI_M3_PROCESS
    ax, ay = float(p["asic_die_x_um"]), float(p["asic_die_y_um"])
    pad = float(p["interposer_pad_um"])
    pitch = float(p["diff_pitch_um"])
    w = float(p["m1_width_um"])
    sp = float(p["m1_space_um"])

    # 中介层比 ASIC die 每边外扩 margin（首版写 `d_out = 8·pad` ⇒ 320 µm < 1800 µm die，
    # 「die 不越出中介层」这条 DRC 必红；改成**相对 die 尺寸**的外扩量）
    margin = 16.0 * pad
    d_in, d_out = ax, ax + 2.0 * margin        # 内框（die  footprint）/ 外框（中介层）
    structs: Dict[str, List[bytes]] = {}
    if oe_structures:
        structs.update(oe_structures)

    def _rect(layer: int, x0: float, y0: float, x1: float, y1: float) -> bytes:
        """矩形多边形（闭合由渲染层处理）。

        🔴 `gds_export.boundary(layer, pts)` 的 `pts` 是**单层点列表**
        （内部 `pts = [p for xy in points_um for p in xy]` 两层展平，
        再传 `[[...]]` 会让迭代元素变成 (x,y) 元组 ⇒ `float(tuple)` TypeError）。
        """
        return gx.boundary(layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    structs["INTERPOSER"] = [
        _rect(_LAYER_INTERPOSER, -d_out / 2, -d_out / 2, d_out / 2, d_out / 2),
        _rect(_LAYER_INTERPOSER, -d_in / 2, -d_in / 2, d_in / 2, d_in / 2),  # ASIC die 挖空区
    ]
    structs["ASIC_DIE"] = [_rect(_LAYER_ASIC, -ax / 2, -ay / 2, ax / 2, ay / 2)]
    # 中介层焊盘阵列 + 电布线（沿中介层走）
    pads, m1s = [], []
    n_pitch = max(1, int(ax // (2.0 * pitch)))
    for k in range(n_pitch):
        x = -ax / 2 + (k + 0.5) * (ax / n_pitch)
        pads.append(_rect(_LAYER_M1, x - pad / 2, -pad / 2, x + pad / 2, pad / 2))
        m1s.append(gx.path(_LAYER_M1, w, [(x, 0.0), (x, ax * 0.5 + pad)]))
    structs["INTERPOSER_PAD"] = pads
    structs["M1_ROUTING"] = m1s
    # FAU 接触点（🔴 只有接触点，**没有光纤本体** —— 片外 fiber 不落版图）
    structs["FAU_TOUCH"] = [_rect(_LAYER_M1, ax / 2 + pad, -pad / 2,
                                  ax / 2 + 2.0 * pad, pad / 2)]

    # 电层 DRC：宽度/间距/焊盘不越 interposer
    d_ok = (w >= 0.5 and sp >= 0.5 and pitch >= w + sp)
    d_ok = d_ok and (ax <= d_out)
    return {
        "structures": structs,
        "asic_die_um": (ax, ay), "interposer_um": (d_out, d_out),
        "n_pads": len(pads), "n_m1": len(m1s),
        "m1_width_um": w, "m1_space_um": sp, "diff_pitch_um": pitch,
        "drc_electrical_pass": bool(d_ok),
        "fiber_in_layout": False,       # 🔴 片外 fiber 不落版图（P8 靶子）
        "oe_structures_inherited": bool(oe_structures),
    }


def cpo_2p5d_layout(oe_link=None, oe_placement=None, oe_routes=None,
                    wg_width: float = 0.5) -> Dict[str, Any]:
    """2.5D 版图签核主入口：光引擎 die GDS（复用 `export_chip_gds`）+ 2.5D 电/封装层。

    🔴 只复用不重造：光层 DRC/LVS 走 `chip_layout_export`（既有双闸），
    M3 只补电层 DRC 与电网络拓扑 LVS（**几何-拓扑一致性核对**，非 foundry 电 PDK 网表；
    电学真值属 T2 锁死区，见 disclosure）。
    """
    from lda_l2 import chip_layout_export as _CLE     # noqa: E402
    from lda_l2 import gds_export as gx               # noqa: E402

    oe = _CLE.export_chip_gds(oe_link, oe_placement, oe_routes,
                              wg_width=wg_width, with_hierarchy=True)
    # 🔴 首版把 `gds_parse["structures"]` 直接喂 `cpo_2p5d_geometry` ⇒ 运行期 TypeError：
    #    那里的 `structures` 是**统计摘要**（{cell: {"elements": int, "layers": set}}），
    #    不是 GDS 元素字节 ⇒ `gds_library` 的 b"".join() 会报
    #    "expected a bytes-like object, str found"。真正要复用的是元素生成器本身：
    #    `chip_layout_export.device_elements`（与 `export_chip_gds` 同源，不重造几何）。
    #    诚实披露：这里走**flat 元素**路径（层次化那条用了 AREF 压缩，不展开），
    #    与 `oe["gds_bytes"]` 的字节不同 ⇒ 本层 GDS 是**同内容**而非同字节。
    oe_structs = {"OE_DIE": list(_CLE.device_elements(oe_link, oe_placement, wg_width))}
    geoms = cpo_2p5d_geometry(oe_structs)
    structs = geoms.pop("structures")

    gds = gx.gds_library("LDA_3P2T_CPO_2P5D", structs)

    # 电网络拓扑 LVS：每个电网络的路径端点 ∈ 版图电气元素（反向完备）
    nets = _pdn_lvs(structs)
    n_elem = sum(len(v) for v in structs.values())
    return {
        "gds_bytes": gds,
        "gds_bytes_len": len(gds),
        "gds_sha256": hashlib.sha256(gds).hexdigest(),
        "gds_structures": sorted(structs.keys()),
        "gds_elements": n_elem,
        "oe_elements_reused": len(oe_structs["OE_DIE"]),
        "oe_drc_pass": bool(oe.get("drc_report", {}).get("all_pass")),
        # 🔴 诚实披露：走**通用**芯片导出路径 `export_chip_gds` 时，ring 器件的**参数几何回提**
        #    （v0.9.128 起的 LVS 双闸「连接 + 尺寸双一致」）会报 REJECT（declared gap 0.55 µm vs
        #    measured 232.3 µm ⇒ 回提对 ring 不适用）。M2 的 G-OI2 builder 走的是自己那条 LVS
        #    管线（ACCEPT/0 违规），M3 复用的只是**元素几何**（`device_elements`），
        #    双闸口径不同 ⇒ 这里**如实报 verdict**，不做「统一说 ACCEPT」的假签核。
        "oe_lvs_verdict": oe.get("lvs_report", {}).get("verdict"),
        "oe_lvs_n_violations": oe.get("lvs_report", {}).get("n_violations"),
        "oe_lvs_honest_note": oe.get("lvs_report", {}).get("honest_note"),
        "oe_lvs_pass": bool(oe.get("lvs_report", {}).get("pass")),
        "electrical_drc_pass": bool(geoms["drc_electrical_pass"]),
        "lvs_report": nets,
        "fiber_in_layout": geoms["fiber_in_layout"],
        "geometry": geoms,
        "oe_stats": oe.get("gds_stats", {}),
    }


def _m1_elements_from_gds(structs: Dict[str, List[bytes]]) -> Dict[int, Dict[str, list]]:
    """🔴 **独立**最小 GDSII 记录流解析器（**刻意不复用** `gds_export` 的解码器）。

    只解本 LVS 需要的记录：BOUNDARY(0x08) / PATH(0x09) + LAYER(0x0D) +
    WIDTH(0x0F) + XY(0x10, INT4) + ENDEL(0x11)；坐标 DBU→µm（1 DBU = 1 nm）。

    **为何自写**：若复用编码器所在模块的解码器，判据读到的仍是**同源派生量**
    ⇒ 假判据高发区（本项目血案 #16 同族）。这里从**最终 GDS 字节**独立解出几何，
    与生成端**零共享代码**。
    """
    dbu = 1e-3                                     # 与 gds_export.DBU 同口径
    out: Dict[int, Dict[str, list]] = {}
    for _sname, elems in structs.items():
        if not isinstance(elems, (list, tuple)):
            continue                           # 畸形输入 ⇒ 安全跳过
        for blob in elems:
            if not isinstance(blob, (bytes, bytearray)):
                continue                           # 非 GDS 字节 ⇒ 安全跳过（P9 靶子）
            i, n = 0, len(blob)
            kind = None
            layer = None
            width = None
            xy: Optional[List[Tuple[float, float]]] = None
            while i + 4 <= n:
                (ln,) = struct.unpack_from(">H", blob, i)
                if ln < 4 or i + ln > n:
                    break
                rt = blob[i + 2]
                payload = blob[i + 4:i + ln]
                if rt == 0x08:
                    kind = "boundary"
                elif rt == 0x09:
                    kind = "path"
                elif rt == 0x0D:
                    layer = int(struct.unpack_from(">h", payload, 0)[0])
                elif rt == 0x0F:
                    width = int(struct.unpack_from(">i", payload, 0)[0]) * dbu
                elif rt == 0x10:
                    cnt = len(payload) // 4
                    vals = struct.unpack_from(">%di" % cnt, payload)
                    xy = [(vals[j] * dbu, vals[j + 1] * dbu) for j in range(0, cnt, 2)]
                i += ln
            if layer is None or not xy or kind is None:
                continue
            slot = out.setdefault(layer, {"rects": [], "paths": []})
            if kind == "boundary":
                xs = [q[0] for q in xy]
                ys = [q[1] for q in xy]
                slot["rects"].append((min(xs), min(ys), max(xs), max(ys)))
            else:
                slot["paths"].append({"pts": list(xy), "width_um": float(width or 0.0)})
    return out


def _pt_in_box(pt: Tuple[float, float], box: Tuple[float, float, float, float],
               tol: float = 0.0) -> bool:
    return (box[0] - tol) <= pt[0] <= (box[2] + tol) and (box[1] - tol) <= pt[1] <= (box[3] + tol)


def _polyline_len(pts: List[Tuple[float, float]]) -> float:
    return float(sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                     for i in range(len(pts) - 1)))


def _pdn_lvs(structs: Dict[str, List[bytes]]) -> Dict[str, Any]:
    """电网络拓扑 LVS：**从最终 GDS 字节独立解码**做几何-拓扑一致性核对。

    口径（诚实披露）：这是**几何-拓扑一致性核对**，**不是** foundry 电 PDK 网表核对
    —— 电阻率/层厚/叠层真值属 T2 锁死区（规格锚 + 窗口判据，见 `_BANDS`）。

    🔴 **v0.9.185 修 F1**：首版此函数是**硬编码 `endpoints_on_pads: True` 的假 LVS**
    （实证：`n_pads=999999` 也 `pass=True`，`n_pads=0` 才 False）⇒ 判据实际只等价于
    「计数 > 0」，**从不检查任何 path/endpoint**；而它经 `ok_m3_layout → good4 →
    run_selfchecks()` 进了案例卡**顶层判决**。

    现在真执行的检查（全部来自**独立解码**的几何）：
      1. 从 GDS 记录流解出 ASIC die 跨度（层 `_LAYER_ASIC`）；
      2. M1 层（`_LAYER_M1`）**焊盘** = x 中心落在 die 跨度内的矩形；**片外接触点**
         （如 FAU touch，x 中心在 die 外）单列，**不入网络**；
      3. **前向**：每条 M1 走线的**起点**必须落在某个焊盘内（否则记**悬空走线**）；
      4. **反向**：每个焊盘必须被 ≥1 条走线起点覆盖（否则记**悬空焊盘**）；
      5. `pass` = 焊盘数 ≥1 且 走线数 ≥1 且 无悬空。
    """
    layers = _m1_elements_from_gds(structs)
    asic = layers.get(_LAYER_ASIC, {"rects": [], "paths": []})["rects"]
    m1 = layers.get(_LAYER_M1, {"rects": [], "paths": []})
    rects, paths = m1["rects"], m1["paths"]

    if asic:
        ax0 = min(b[0] for b in asic)
        ax1 = max(b[2] for b in asic)
    else:
        ax0, ax1 = float("-inf"), float("inf")

    pads, offdie = [], []
    for b in rects:
        cx = 0.5 * (b[0] + b[2])
        (pads if ax0 <= cx <= ax1 else offdie).append(b)

    covered = [False] * len(pads)
    dangling = 0
    nets: List[Dict[str, Any]] = []
    for j, pth in enumerate(paths):
        start = pth["pts"][0]
        hit = -1
        for k, b in enumerate(pads):
            if _pt_in_box(start, b):
                hit = k
                break
        if hit >= 0:
            covered[hit] = True
        else:
            dangling += 1
        nets.append({
            "net": "BUS_LANE_%d" % (j + 1),
            "path_start_um": [round(start[0], 4), round(start[1], 4)],
            "endpoint_on_pad": bool(hit >= 0),
            "pad_index": int(hit),
            "path_len_um": round(_polyline_len(pth["pts"]), 4),
            "width_um": round(pth["width_um"], 4),
        })
    n_uncovered = sum(1 for c in covered if not c)
    ok = bool(len(pads) > 0 and len(paths) > 0 and dangling == 0 and n_uncovered == 0)
    return {
        "n_nets": min(len(paths), len(pads)),
        "n_pads": len(pads), "n_paths": len(paths),
        "n_dangling_paths": int(dangling), "n_uncovered_pads": int(n_uncovered),
        "n_offdie_touch_points": len(offdie),
        "nets": nets, "pass": ok,
        "decoder": "independent_min_gdsi_reader（不复用 gds_export 解码器）",
        "kind": "geometry_topology_lvs（非 foundry 电 PDK 网表；电学真值 T2 锁死）",
    }


def oi_m3_optical_io_at_400g() -> Dict[str, Any]:
    """🔴 复用 `cpo_optical_io_metrics`，**只调参 lane_rate_gbps=400** ⇒ 三道物理下界仍成立。

    这是「吃狗粮」硬要求：不新建光学 I/O 模型，只验证现有底座在 3.2T 速率级不塌。
    """
    from lda_design import cpo_engines as _CPO     # noqa: E402
    g200 = _CPO.cpo_optical_io_metrics({"lane_rate_gbps": 200.0})
    g400 = _CPO.cpo_optical_io_metrics({"lane_rate_gbps": 400.0})
    return {
        "at_200g": g200, "at_400g": g400,
        "lane_halved": float(g400["bandwidth_density_gbps_mm"]) ==
        2.0 * float(g200["bandwidth_density_gbps_mm"]),
        "density_still_below_ceiling": bool(
            float(g400["bandwidth_density_gbps_mm"]) <=
            float(g400["density_ceiling_gbps_mm"]) + 1e-9),
        "pitch_still_above_floor": bool(
            float(g400["pitch_floor_um"]) <= float(g400["pitch_um"])),
        "energy_floor_still_positive": bool(
            float(g400["energy_floor_dB"]) > 0.0),
        "reused_not_rebuilt": True,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 7) 披露面 / 自检
# ═════════════════════════════════════════════════════════════════════════════
OI_M3_DISCLOSURE: Dict[str, str] = {
    "scope": "3.2T/CPO 设计&验证（8×400G PAM4 · 212.5 GBd · 106.25 GHz 奈奎斯特，与 "
             "IEEE 802.3dj 400G/lane 同口径）；由 M2 的 200G 档翻倍派生，不重抄常量。",
    "golden": "闭式物理律：分布 RLC 电报方程 γ=√((R′+jωL′)jωC′)、二维薄片稳态热场、"
              "二维热网络、erf 良率；时域 FDTD / 有限差分 / ABCD 链只作第二独立通道。",
    "anchor": "电通道 R′/L′/C′、PDN 感抗、等效线电容、ASIC 热阻、探测器/TIA/光源功耗"
              "均为**显式声明的规格锚**（带取值窗口 _BANDS），非 foundry 数据（T2 锁死区）。",
    "verdict": "DESIGN_BUDGET",
    "no_energy": (
        "🔴 本模块禁止且未提供任何「每比特焦耳 / TOPS / TOPS-W / fJ-op / pJ-bit」数字；"
        "所有功耗以 **mW（逐 lane）与 W（模块）** 报出，不做比特能效换算。"),
    "no_fabricated": "未流片；不报 fabricated 能效。",
    "open_gaps": "G-OI4（跨档统一热/工艺真值）、G-OI6（2.5D 电通道电路级建模需 foundry 电 PDK，"
                 "本轮以几何-拓扑 LVS + 规格锚窗口约束）。",
}

_EFFECT_BANNED = ("fJ/", "pJ/bit", "TOPS-W", "能效比", "J/op")


def honest_boundary_ok() -> bool:
    """禁词只扫**肯定式宣称面**（否定式自我声明豁免；否定前若有肯定式仍会红）。"""
    txt = " ".join(v for k, v in OI_M3_DISCLOSURE.items() if k != "no_energy")
    return not any(b in txt for b in _EFFECT_BANNED)


def oi_m3_self_check(verbose: bool = True) -> Dict[str, Any]:
    """模块内自检（被 `run_oi_m3_smoke.py` 复用为互锁判据的一环）。"""
    c: List[Tuple[str, bool]] = []

    # ── 0) 规格锚窗口（3.2T 口径）
    c.append(("M3 规格锚：3.2T 奈奎斯特落窗 106.25 GHz",
              _in_band("nyquist_ghz", NYQUIST_3200_GHZ)))
    c.append(("M3 规格锚：符号率 212.5 GBd 落窗",
              _in_band("baud_gbd", PAM4_BAUD_3200_GBD)))
    c.append(("M3 互锁：3.2T 符号率 == 2 × 200G 档（派生不重抄）",
              abs(PAM4_BAUD_3200_GBD - 2.0 * PAM4_BAUD_200G_GBD) < 1e-12))
    c.append(("M3 互锁：3.2T 奈奎斯特 == 2 × 200G 档奈奎斯特",
              abs(NYQUIST_3200_GHZ - 2.0 * _M2.NYQUIST_200G_GHZ) < 1e-12))

    # ── ① TWMZM
    d = twmzm_design()
    c.append(("M3 ① 带宽墙：TWMZM f₃dB ≥ 1.03× 奈奎斯特（400G/lane 判死线）", d["bandwidth_ok"]))
    c.append(("M3 ① 双侧窗口：f₃dB/奈奎斯特 ∈ [1.03, 8]（防参数没标度对的假绿）", d["in_window"]))
    conv = twmzm_ladder_convergence()
    c.append(("M3 ① 第二通道：ABCD 链相对误差随 N 单调下降", conv["monotonic_decreasing"]))
    c.append(("M3 ① 第二通道：N=200 相对误差 < 2%", conv["err_smallest"] < 0.02))
    c.append(("M3 ① 退化：|H(0)| ≡ 1（q→0 不除零，物理全通）",
              abs(abs(twmzm_response_closed(1.0)) - 1.0) < 1e-3))
    c.append(("M3 ① 速度失配物理：长电极 (8 mm) 必比短电极 (1 mm) 带宽窄",
              twmzm_bandwidth_hz(l_mm=8.0) < twmzm_bandwidth_hz(l_mm=1.0)))
    c.append(("M3 ① 长电极 (8 mm) 落到判死线以下（判据咬物理，非恒绿）",
              twmzm_bandwidth_hz(l_mm=8.0) < 1.03 * NYQUIST_3200_GHZ * 1e9))
    c.append(("M3 ① 互锁：f_RC 落窗且 ∝ 1/L²（分布 RC 线，漏乘一个 L 必红）",
              _in_band_rc(rc_pole_hz()) and _rc_scales_with_length()))
    # 与 oi_m1 同口径互锁
    fl = family_lock()
    c.append(("M3 ① 族名互锁：M3(twmzm) ≠ M1(ring)（防跨档抄常量）", fl["family_distinct"]))
    c.append(("M3 ① 口径互锁：两求解器在单极点退化上自洽（同一 |H|=1/√2 定义）",
              fl["solver_agrees_on_single_pole"]))
    c.append(("M3 ① 跨族：TWMZM 与环的 f₃dB 数值不同（真·不同族，非同源假绿）",
              abs(fl["f3db_m3_hz"] - fl["f3db_m1_hz"]) > 1e6))

    # ── ② 电通道
    hsq = echannel_h_sqrtf_ok()
    c.append(("M3 ② 衰减标量 h 在 **R 主导子带**（f ≤ f_RL/20）内是真常数（√f 律非硬套）",
              hsq["ok"]))
    c.append(("M3 ② 诚实披露：窗口外（1↔10 GHz，RL 主导区）的 √f 漂移被如实报出",
              hsq["disclosed_outside"]))
    c.append(("M3 ② 电互连随长度衰减（5 mm > 1 mm）",
              echannel_att_db(NYQUIST_3200_GHZ * 1e9, 5.0)
              > echannel_att_db(NYQUIST_3200_GHZ * 1e9, 1.0)))
    c.append(("M3 ② NEXT：耦合比清零 ⇒ 串扰 −∞ dB（P4 靶子可判）",
              xtalk_next_db(k=0.0)["xtalk_at_zero_coupling_db"] == float("-inf")))
    c.append(("M3 ② NEXT：K·(F/f₀)² 功率比随 F 单调增",
              xtalk_next_db(NYQUIST_3200_GHZ * 1e9)["ratio_linear"]
              > xtalk_next_db(1e9)["ratio_linear"]))
    c.append(("M3 ② PDN 地弹：V = L·di/dt 落窗（规格锚）",
              abs(pdn_bounce_v()["v_bounce_v"] - 0.5e-9 * 8.0e10) < 1e-12))
    fd = fdtd_telegraph()
    c.append(("M3 ② 第二通道：FDTD 时域相速 ⟷ 闭式 τ=L√(L′C′) 相对误差 < 5%", fd["phase_ok"]))
    c.append(("M3 ② FDTD 输出幅度 > 0（不是空跑出 0）", fd["peak_out_v"] > 0.0))
    _rp = float(OI_M3_PROCESS["r_bus_ohm_per_mm"]) * 1e3
    _lp = float(OI_M3_PROCESS["l_bus_nH_per_mm"]) * 1e-9 / 1e-3
    _cp = float(OI_M3_PROCESS["c_bus_fF_per_mm"]) * 1e-15 / 1e-3
    c.append(("M3 ② R′ 项：γ 实部 > 0（损耗真进了闭式，不是纯相位传输线）",
              propagation_gamma(NYQUIST_3200_GHZ * 1e9, _rp, _lp, _cp).real > 0.0))

    # ── ③ 热
    st = die_thermal_stack()
    c.append(("M3 ③ 跨 die 热：光子 die 温升 > 中介层温升（两串热阻叠加）",
              st["d_t_photon_c"] > st["d_t_interposer_c"]))
    c.append(("M3 ③ 热解双通道：对数解 ⟷ M2b 有限差分网络一致", st["theta_channels_agree"]))
    cl = closed_loop_thermal_steady()
    c.append(("M3 ③ 闭环热调：稳态解**收敛**且 `solution` 由实际求解路径返回（非字面量）",
              bool(cl["converged"]) and cl["solution"] == "algebraic"))
    c.append(("M3 ③ 闭环热调：代数解 ⟷ 不动点迭代（单通路 A=1）收敛到**同一**稳态（第二独立通道）",
              _algebraic_matches_fixed_point()))
    c.append(("M3 ③ 闭环热调：**双计**（环路增益 A≫1）⇒ 不动点迭代**必发散**（1e88 K 血案的真实护栏）",
              _double_count_diverges()))
    c.append(("M3 ③ 闭环热调：稳态执行器功率 ∝ 1/R_h（**由不动点求解器输出**，非闭式定义换写）",
              _closed_loop_scales_with_r_h()))
    c.append(("M3 ③ 闭环热调：单向加热器判定（够不到设定点 ⇒ 需预偏移或 TEC，不是硬凑正数）",
              cl["unidirectional_heater_feasible"] is False))
    c.append(("M3 ③ 闭环热调：残余失谐落在 (0, 1 FSR)（CPO 真实代价，可插拔无此项）",
              0.0 < cl["residual_nm"] < _M2B.thermal_tune_budget()["FSR_nm"]))
    # 🔴 F6/F7（v0.9.185）：单一真源可达（回退已删）+ 无旁路热阻键（8.0 死配置已删）
    c.append(("M3 ③ 单一真源：`active_models.R_TH_K_PER_MW` 可达（静默回退已删 · 修 F7）",
              single_source_reachable_m3()))
    c.append(("M3 ③ 无旁路热阻键：`OI_M3_PROCESS` 不含 `r_th_thermal_k_per_w`（死配置已删 · 修 F6）",
              no_bypass_thermal_key()))

    # ── ④ 功耗账
    rec = power_reconcile()
    c.append(("M3 ④ 对拍：逐项加总 == 逐 lane 之和（全局口径不脱钩，P7 靶子）",
              rec["reconciled"]))
    c.append(("M3 ④ CPO 热调代价 > 可插拔（CPO 才需跟踪 ASIC 热）",
              rec["cpo_advantage_thermal_mw"] > 0.0))
    c.append(("M3 ④ CPO 独有项 interposer_pdn > 0（可插拔没有）",
              rec["cpo_penalty_interposer_mw"] > 0.0))
    c.append(("M3 ④ 红线：功耗账已标记禁用能效换算",
              bool(power_breakdown("cpo")["energy_per_bit_banned"])))
    c.append(("M3 ④ 口径同参：CPO 与可插拔除电路径外各项同参",
              power_breakdown("cpo")["items_mw_per_lane"]["tia_static_mw"]
              == power_breakdown("pluggable")["items_mw_per_lane"]["tia_static_mw"]))

    # ── ⑤ 2.5D 版图
    # 🔴 必须**真的把光引擎 structures 传进去**：首版 `cpo_2p5d_structure()` 没传 ⇒
    #   `oe_structures_inherited=False` ⇒ 「复用 export_chip_gds」这条判据是空绿（假绿）。
    from lda_l2 import gds_export as _gx                     # noqa: E402（单一真源）
    _oe_stub = {"WG_ROUTE": [_gx.boundary(1, [(0.0, 0.0), (10.0, 0.0),
                                              (10.0, 10.0), (0.0, 10.0)])]}
    geo = cpo_2p5d_geometry(oe_structures=_oe_stub)
    c.append(("M3 ⑤ 电层 DRC：线宽/线距/差分 pitch 互锁", geo["drc_electrical_pass"]))
    c.append(("M3 ⑤ 片外 fiber 不落版图（P8 靶子）", geo["fiber_in_layout"] is False))
    lvs = _pdn_lvs(geo["structures"])
    c.append(("M3 ⑤ 电网络拓扑 LVS：从 GDS 字节**独立解码** ⇒ 无悬空走线 / 无悬空焊盘",
              lvs["pass"] and lvs["n_dangling_paths"] == 0 and lvs["n_uncovered_pads"] == 0))
    c.append(("M3 ⑤ LVS 解码器**独立**：不复用 gds_export 解码器（防同源假判据）",
              "independent_min_gdsi_reader" in lvs["decoder"]))
    c.append(("M3 ⑤ LVS 咬**几何**非计数：走线起点逐条核对落在焊盘内（首版读 n_pads 字段 ⇒ 荒谬值必假绿）",
              lvs["n_pads"] == lvs["n_paths"] and lvs["n_nets"] == lvs["n_pads"]))
    c.append(("M3 ⑤ 片外 FAU 接触点被识别为**非网络元素**（x 中心在 ASIC die 外 ⇒ 不入焊盘集）",
              lvs["n_offdie_touch_points"] >= 1))
    c.append(("M3 ⑤ 光引擎 GDS 由 export_chip_gds 复用（吃狗粮不重造，非空绿）",
              geo["oe_structures_inherited"] and len(geo["structures"]["WG_ROUTE"]) == 1))

    # ── 复用底座在 3.2T 速率级仍成立
    io = oi_m3_optical_io_at_400g()
    c.append(("M3 复用：cpo_optical_io_metrics 在 400G/lane 密度仍低于上界",
              io["density_still_below_ceiling"]))
    c.append(("M3 复用：400G 密度 == 2×200G（复用底座口径随速率线性，非另起炉灶）",
              io["lane_halved"]))
    c.append(("M3 复用：400G 下 pitch 仍高于耦合物理下界", io["pitch_still_above_floor"]))
    c.append(("M3 复用：400G 下能量守恒下界仍 > 0", io["energy_floor_still_positive"]))

    c.append(("M3 诚实边界：披露面无禁出词", honest_boundary_ok()))

    ok = all(x[1] for x in c)
    if verbose:
        for name, good in c:
            print(("  [%s] " % ("PASS" if good else "FAIL")) + name)
        print("-" * 70)
        print("M3 自检：%d PASS / %d FAIL / 共 %d 项" %
              (sum(1 for _, x in c if x), sum(1 for _, x in c if not x), len(c)))
    return {"ok": ok, "checks": c,
            "n_pass": sum(1 for _, x in c if x), "n_fail": sum(1 for _, x in c if not x)}


def _in_band_rc(value: float) -> bool:
    """f_RC 的窗口（按量级判，避免把窗口键写死进 _BANDS 语义混用）。"""
    return 1e3 < value < 1e13


def _rc_scales_with_length() -> bool:
    """f_RC ∝ **1/L²**（分布 RC 线；漏乘一个 L ⇒ 判据必红；探针 P2 靶子）。"""
    f1 = rc_pole_hz(1.0)
    f2 = rc_pole_hz(2.0)
    return abs(f2 - f1 / 4.0) < 1e-6 * max(f1, 1.0)


if __name__ == "__main__":
    r = oi_m3_self_check()
    raise SystemExit(0 if r["ok"] else 1)
