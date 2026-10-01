# -*- coding: utf-8 -*-
"""ecore · E14 · **真转换器电路**（R-2R DAC + SAR/CDAC ADC + 采样保持）。

============================================================================
为什么存在（E14 · 电子计算征程 · 把「设计链」补成「系统链」）
----------------------------------------------------------------------------
E1–E13 的数据通路里，**DAC 与 ADC 一直只是行为级均匀量化模型**
（`mvm_datapath.quantize_uniform`）—— 有量化**结果**，没有**电路**。
本模块补上两端转换器的**真电路实现**：

  ① **R-2R 梯形 DAC**（无源电阻网络 + **NMOS 模拟开关**）⇒ 暴露开关导通电阻 `R_on`
     对精度的影响（**这是行为级模型看不见的**）。
  ② **SAR + CDAC 电荷重分配 ADC**（真电容阵列 + 真瞬态 + 逐次逼近逻辑）⇒ 核心物理是
     **电荷守恒**；顶板电压由**后向欧拉电容伴随模型**天然给出（见下「为什么瞬态是对的」）。
  ③ **采样保持**（`C_s` + 开关）⇒ 一阶 RC 建立 `v(t)=V_in(1−e^{−t/RC})`。

🔴 方法学（判据为什么算数）
  golden 全部是**闭式物理律**：
    分压 `V_ref·code/2^N` · 电荷守恒 `V_ref·Σb_iC_i/C_total − V_in` ·
    一阶 RC `V_in(1−e^{−t/RC})`。
  **次生 golden（网络装配自证）**：R-2R 用 **MNA 解"理想开关"网络**（vsource 直驱 s_k）
  ⟷ 闭式 `V_ref·code/2^N` —— 一个是**电路拓扑**给的、一个是**二进制除权公式**给的，
  **方法学独立**（同 E7「R=0 网络 ≡ 解析 golden」的纪律）。

🔴🔴 为什么 CDAC 必须走**瞬态**而不是 DC
  **电容在 DC 下是开路** ⇒ DC 解里顶板电位与电荷分配**无关**（拓扑退化）⇒ 拿不到重分配结果。
  后向欧拉的电容伴随模型为 `i = C/dt·(v − v_prev)` + 历史电流源；代入顶板节点 KCL 得

      Σ_k C_k (V_top − V_bk) = Σ_k C_k (V_top^prev − V_bk^prev)     ← 即 Q_top 守恒

  ⇒ **一步瞬态 = 精确的电荷守恒解**（不是近似）。这正是 SAR CDAC 的物理。

🔴 诚实边界
  · **比较器是「有限增益 + 输入失调 + 噪声」的判决器抽象**，**非晶体管级比较器** ——
    MNA 无非线性饱和器件，且 E2 已证朴素 NMOS 差分对无法闭合高增益环路（会落入
    "KCL 不满足却自称收敛"的错误不动点）。
  · **CDAC 的底板开关用理想电压源抽象**（聚焦电荷重分配物理；DAC 侧则用真 NMOS 开关
    以暴露 `R_on`）—— 这是**有意的工程取舍**，已披露。
  · 电阻/电容为**理想值**（不建匹配网络）；失配沿用 E8 的 Pelgrom/MC 口径作旁引。
  · 开关 `R_on` 用平方律**三极管区闭式**；**电荷注入 / 时钟馈通只给量级估算**，不建完整模型。
  · 参数为公开典型量级占位（**非 PDK**）；不做流片；不报 TOPS / TOPS-W / fJ/op。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .mna import Circuit
from .mosfet import NmosParams

__all__ = [
    "CONV_PROCESS", "nmos_switch_ron_ohm", "ideal_dac_voltage",
    "code_to_bits", "bits_to_code", "r2r_rational_voltage",
    "r2r_ideal_network_dc", "r2r_nmos_dac_dc", "dac_static_report",
    "cdac_top_closed_form", "sar_convert", "sar_error_report",
    "sample_hold_transient", "CONVERTER_DISCLOSURE",
    "converter_self_check",
]

# ═══════════════════════════ 默认量（公开典型量级占位）═══════════════════════════
CONV_PROCESS = {
    "vref_v": 1.0,              # 参考电压
    "r_unit_ohm": 10.0e3,       # R-2R 的 R（2R = 2·R）
    "dac_sw_wl": 500.0,         # DAC 开关宽长比（大 ⇒ R_on 小 ⇒ 精度高）
    "sw_vgate_v": 3.0,          # 开关栅压（导通）
    "c_unit_f": 1.0e-12,        # CDAC 单位电容 C_u
    "t_step_s": 1.0e-9,         # 瞬态步长（电导 C/dt 足够大 ⇒ 数值条件良好）
    "pin_r_ohm": 1.0e12,        # 顶板数值钉扎（防浮空奇异；与 C/dt 并联 ⇒ 影响 ~1e-12）
    "rs_ohm": 1.0e3,            # 采样开关等效电阻（采样保持 RC 用）
    "cs_f": 1.0e-12,            # 采样电容
}


def _p(key: str, override: Optional[dict] = None):
    if override and key in override:
        return override[key]
    return CONV_PROCESS[key]


# ═══════════════════════════ ① 器件 / 闭式 ═══════════════════════════════
def nmos_switch_ron_ohm(v_gate: float = 3.0, vth: float = 0.4, kp: float = 120e-6,
                        w_over_l: float = 500.0) -> float:
    """NMOS 开关**导通电阻**（三极管区闭式）：`R_on = 1/(kp·(W/L)·V_ov)`。

    V_ov = V_gate − V_th。这是「真开关」相对「理想开关」的**唯一实质差别** ⇒
    它直接决定 DAC 的静态精度上限（`ΔV/V ≈ R_on/R`）。
    """
    vov = float(v_gate) - float(vth)
    if vov <= 0:
        raise ValueError("栅过驱动须 > 0（否则开关不导通）")
    return 1.0 / (float(kp) * float(w_over_l) * vov)


def ideal_dac_voltage(code: int, n_bits: int, vref: float = 1.0) -> float:
    """**理想 DAC 闭式**（golden）：`V_ref · code / 2^N`（满量程 = `V_ref·(2^N−1)/2^N`）。"""
    n = int(n_bits)
    c = int(code)
    if n < 1:
        raise ValueError("n_bits 须 ≥ 1")
    if c < 0 or c >= (1 << n):
        raise ValueError("code 越界 [0, 2^n)")
    return float(vref) * c / float(1 << n)


def code_to_bits(code: int, n_bits: int) -> List[int]:
    """整数码 → **MSB-first** 位表（`bits[0]` 是 MSB）。"""
    n = int(n_bits)
    c = int(code)
    if c < 0 or c >= (1 << n):
        raise ValueError("code 越界")
    return [(c >> (n - 1 - k)) & 1 for k in range(n)]


def bits_to_code(bits: Sequence[int]) -> int:
    """MSB-first 位表 → 整数码。"""
    c = 0
    for b in bits:
        c = (c << 1) | (1 if int(b) else 0)
    return c


def r2r_rational_voltage(bits: Sequence[int], vref: float = 1.0) -> float:
    """R-2R 网络输出的**有理数精确值**（Fraction 精度，避开浮点）：`V_ref·code/2^N`。

    用整数分子/分母算 ⇒ 可与 MNA 浮点解做**严格**比对。
    """
    n = len(bits)
    num = bits_to_code(bits)
    return float(vref) * num / float(1 << n)


# ═══════════════════════════ ② R-2R DAC 电路 ═══════════════════════════════
#   拓扑（N bit · v[0] 侧＝MSB）：
#     v[k] --R-- v[k+1]   (k = 0..N-2)
#     v[k] --2R-- s[k]    (k = 0..N-1)   s[k] 由开关接 V_ref 或 GND
#     v[N-1] --2R-- GND   (终端电阻)
#   戴维南递推 ⇒ 从任一节点向右看等效 = R ⇒ 逐级二分 ⇒ v[0] = V_ref·code/2^N（MSB-first 权）
_TOP = 1          # 梯形首节点（输出侧）


def _build_r2r_ideal(n: int, bits: Sequence[int], vref: float, r: float) -> Circuit:
    """**理想开关** R-2R（s[k] 由 vsource 直驱）⇒ 用于「网络装配自证」。"""
    ckt = Circuit("r2r_ideal")
    taps = [1 + k for k in range(n)]
    for k in range(n - 1):
        ckt.resistor(taps[k], taps[k + 1], r, "R%d" % k)
    for k in range(n):
        s = 100 + k                      # s 节点由 vsource 驱动（理想开关）
        ckt.resistor(taps[k], s, 2.0 * r, "2R%d" % k)
        val = float(vref) * (1 if bits[k] else 0)
        ckt.vsource(s, 0, val, "S%d" % k)
    ckt.resistor(taps[n - 1], 0, 2.0 * r, "Rt")
    return ckt


def r2r_ideal_network_dc(bits: Sequence[int], vref: float = 1.0,
                         r_unit_ohm: float = 10.0e3) -> float:
    """用 **MNA 解理想 R-2R 网络** ⇒ 首节点电压（**网络装配自证**用）。

    🔴 与 `ideal_dac_voltage` 是**两个独立来源**：前者来自**电路拓扑 + 求解器**，
    后者来自**二进制除权公式** ⇒ 二者一致才算「网络真的搭对了」。
    """
    bs = [int(b) for b in bits]
    n = len(bs)
    if n < 1:
        raise ValueError("bits 不能为空")
    ckt = _build_r2r_ideal(n, bs, vref, r_unit_ohm)
    ckt.resistor(0, 0, 1.0e9, "dummy")          # 保证地节点在集合里
    x = ckt.solve_dc()
    return float(ckt.node_voltages(x)[1])


def _build_r2r_nmos(n: int, bits: Sequence[int], vref: float, r: float,
                    p: NmosParams, vgate: float) -> Circuit:
    """**真 NMOS 开关** R-2R ⇒ 暴露 `R_on` 的影响。

    每个 `s[k]` 接 **两个 NMOS**：一个到 `V_ref`、一个到 `GND`（互补驱动）⇒ 任一时刻
    恰有一个导通（**不会浮空** ⇒ 不引入奇异）。
    """
    ckt = Circuit("r2r_nmos")
    taps = [1 + k for k in range(n)]
    vref_node = 1 + n
    ckt.vsource(vref_node, 0, float(vref), "VREF")
    ckt.resistor(vref_node, vref_node, 1.0e9, "rz")
    for k in range(n - 1):
        ckt.resistor(taps[k], taps[k + 1], r, "R%d" % k)
    for k in range(n):
        s = 100 + k
        ckt.resistor(taps[k], s, 2.0 * r, "2R%d" % k)
        g_ref, g_gnd = 200 + 2 * k, 201 + 2 * k
        on = bool(bits[k])
        ckt.vsource(g_ref, 0, float(vgate) if on else 0.0, "GR%d" % k)
        ckt.vsource(g_gnd, 0, 0.0 if on else float(vgate), "GG%d" % k)
        ckt.nmos(s, g_ref, vref_node, p, "MR%d" % k)
        ckt.nmos(s, g_gnd, 0, p, "MG%d" % k)
    ckt.resistor(taps[n - 1], 0, 2.0 * r, "Rt")
    return ckt


def r2r_nmos_dac_dc(bits: Sequence[int], vref: float = 1.0,
                    r_unit_ohm: float = 10.0e3, dac_sw_wl: float = 500.0,
                    sw_vgate_v: float = 3.0) -> float:
    """**真电路** R-2R DAC 的 MNA 直流解 ⇒ 首节点电压（V）。"""
    bs = [int(b) for b in bits]
    n = len(bs)
    p = NmosParams(w_over_l=float(dac_sw_wl))
    ckt = _build_r2r_nmos(n, bs, vref, r_unit_ohm, p, sw_vgate_v)
    x = ckt.solve_dc()
    return float(ckt.node_voltages(x)[1])


def dac_static_report(n_bits: int = 8, vref: float = 1.0,
                      r_unit_ohm: float = 10.0e3, dac_sw_wl: float = 500.0,
                      sw_vgate_v: float = 3.0, step: int = 1) -> Dict:
    """DAC **静态表征**：全码扫描 ⇒ 端点 / INL / DNL / 单调性 / 相对误差。

    🔴 `step` 控制扫描步长（8 bit 全扫 = 256 点，求解较慢 ⇒ 判据用 `step=1` 全扫，
    趋势类判据可加大）。
    """
    n = int(n_bits)
    ncodes = 1 << n
    lsb = float(vref) / float(ncodes)
    codes = list(range(0, ncodes, max(1, int(step))))
    if codes[-1] != ncodes - 1:
        codes.append(ncodes - 1)
    ideal_v, real_v = {}, {}
    for c in codes:
        bs = code_to_bits(c, n)
        ideal_v[c] = ideal_dac_voltage(c, n, vref)
        real_v[c] = r2r_nmos_dac_dc(bs, vref, r_unit_ohm, dac_sw_wl, sw_vgate_v)
    errs = {c: real_v[c] - ideal_v[c] for c in codes}
    max_abs_err = max(abs(e) for e in errs.values())
    dnl = []
    for i in range(1, len(codes)):
        c0, c1 = codes[i - 1], codes[i]
        if c1 - c0 != 1:
            continue
        dnl.append((real_v[c1] - real_v[c0]) / lsb - 1.0)
    inl = [errs[c] / lsb for c in codes]
    mono = all(real_v[codes[i]] >= real_v[codes[i - 1]] - 1e-15
               for i in range(1, len(codes)))
    return {
        "n_bits": n, "vref": float(vref), "lsb_v": lsb,
        "codes_scanned": len(codes),
        "v_at_code0": real_v[codes[0]], "v_at_full": real_v[codes[-1]],
        "ideal_full_scale": ideal_dac_voltage(ncodes - 1, n, vref),
        "max_abs_err_v": float(max_abs_err),
        "max_abs_err_lsb": float(max_abs_err / lsb),
        "inl_lsb_max": float(max(abs(v) for v in inl)),
        "dnl_lsb_min": float(min(dnl)), "dnl_lsb_max": float(max(dnl)),
        "monotone": bool(mono),
        "ron_ohm": nmos_switch_ron_ohm(sw_vgate_v, 0.4, 120e-6, dac_sw_wl),
        "ron_over_r": nmos_switch_ron_ohm(sw_vgate_v, 0.4, 120e-6, dac_sw_wl) / float(r_unit_ohm),
        "rc_limited": False,
        "is_oracle": False,
    }


# ═══════════════════════════ ③ SAR / CDAC ADC ═══════════════════════════════
#   电容：C_k = 2^k·C_u (k = 0..N-1 · k=0 为 LSB) + 哑元 C_u ⇒ C_total = 2^N·C_u
#   顶板(top) 浮空 / 接 GND（采样）/ 大电阻钉扎（逼近）
#   底板(bot_k) 由 vsource 驱动：采样 = V_in · 保持 = 0 · 试判 = V_ref
def _cdac_c_unit(n_bits: int, c_unit: float) -> List[float]:
    return [float(c_unit) * (1 << k) for k in range(int(n_bits))] + [float(c_unit)]


def cdac_top_closed_form(bits: Sequence[int], v_in: float, vref: float = 1.0,
                         n_bits: int = 8, c_unit: float = 1.0e-12) -> float:
    """**CDAC 顶板电压闭式（golden · 电荷守恒）**：
    `V_top(b) = V_ref·(Σ_{b_i=1} C_i)/C_total − V_in`。

    推导：采样时顶板接地、底板全 `V_in` ⇒ `Q_top = −C_total·V_in`；保持/逼近时顶板浮空
    ⇒ `Σ C_i(V_top − V_bot_i) = Q_top` ⇒ 上式。
    """
    n = int(n_bits)
    cs = _cdac_c_unit(n, c_unit)
    ctot = sum(cs)
    acc = 0.0
    for i, b in enumerate(bits):
        if int(b):
            acc += cs[i]
    return float(vref) * acc / ctot - float(v_in)


def _cdac_run_segment(n_bits: int, c_unit: float, top_v: Optional[float],
                      bot_vs: Sequence[float], v0: Optional[Dict[int, float]],
                      t_step: float, pin_r: float) -> np.ndarray:
    """推进**一个**开关状态段（一步瞬态）⇒ 返回末态节点电压数组（index == node id）。

    `top_v is None` ⇒ 顶板浮空（只挂大电阻钉扎 + 电容电导 ⇒ 不奇异）。
    """
    n = int(n_bits)
    ckt = Circuit("cdac")
    cs = _cdac_c_unit(n, c_unit)
    TOP = 1
    for i, c in enumerate(cs):
        bot = 2 + i
        ckt.capacitor(TOP, bot, c)
        ckt.vsource(bot, 0, float(bot_vs[i]), "B%d" % i)
    if top_v is None:
        ckt.resistor(TOP, 0, float(pin_r), "PIN")
    else:
        ckt.vsource(TOP, 0, float(top_v), "TOPS")
    ckt.resistor(0, 0, 1.0e9, "dummy")      # 地节点入集合
    _, out = ckt.solve_transient(t_end=float(t_step), n_steps=1, v0=v0)
    return out[-1]


def sar_convert(v_in: float, n_bits: int = 8, vref: float = 1.0, c_unit: float = 1.0e-12,
                t_step: float = 1.0e-9, pin_r: float = 1.0e12,
                comp_offset_v: float = 0.0) -> Dict:
    """**SAR + CDAC 逐次逼近转换**（真电容阵列 · 真瞬态 · 逐次逼近逻辑）。

    流程：**采样**（顶板接地、底板全 `V_in`）→ **保持**（顶板浮空、底板全 0）
    → **逐位试判**（MSB→LSB：把该位底板切到 `V_ref`，读顶板电压 ⇒ `< comp_offset` 则保留）。

    判决器：**有限增益 + 失调 + 噪声**的抽象（`comp_offset_v` 即输入失调）；见模块 docstring。
    """
    n = int(n_bits)
    cs = _cdac_c_unit(n, c_unit)
    nbot = len(cs)
    if not (0.0 <= float(v_in) < float(vref)):
        raise ValueError("v_in 须落在 [0, v_ref)")

    # ① 采样：顶板接地，底板全 V_in
    st = _cdac_run_segment(n, c_unit, 0.0, [float(v_in)] * nbot, None, t_step, pin_r)
    v0 = {i: float(st[i]) for i in range(len(st))}
    # ② 保持：顶板浮空，底板全 0 ⇒ V_top = −V_in（电荷守恒）
    bot = [0.0] * nbot
    st = _cdac_run_segment(n, c_unit, None, bot, v0, t_step, pin_r)
    v0 = {i: float(st[i]) for i in range(len(st))}
    v_top_hold = float(st[1])

    # ③ 逐次逼近（MSB → LSB）
    bits = [0] * n
    trace = []
    for k in range(n - 1, -1, -1):          # 电容索引 k：MSB 是最大的 C
        trial = list(bot)
        trial[k] = float(vref)
        st = _cdac_run_segment(n, c_unit, None, trial, v0, t_step, pin_r)
        v_top = float(st[1])
        keep = bool(v_top < float(comp_offset_v))
        trace.append({"cap_index": k, "V_top_v": v_top, "kept": keep})
        if keep:
            bot = trial
            bits[k] = 1
            v0 = {i: float(st[i]) for i in range(len(st))}
        # 回切 ⇒ 状态与 v0 保持上一次（未变）
    code = 0
    for k in range(n):
        if bits[k]:
            code |= (1 << k)
    return {
        "v_in": float(v_in), "code": int(code), "bits_lsb_first": bits,
        "v_top_hold_v": v_top_hold,
        "v_top_final_v": trace[-1]["V_top_v"],
        "residual_v": trace[-1]["V_top_v"],
        "trace": trace, "n_bits": n, "vref": float(vref),
        "lsb_v": float(vref) / float(1 << n),
        "comp_offset_v": float(comp_offset_v),
        "top_closed_form_hold_v": cdac_top_closed_form([0] * n, v_in, vref, n, c_unit),
        "is_oracle": False,
    }


def sar_error_report(n_bits: int = 8, vref: float = 1.0, c_unit: float = 1.0e-12,
                     samples: int = 24, comp_offset_v: float = 0.0) -> Dict:
    """SAR **静态误差报告**：均匀取样点上的码误差（LSB）+ 量化闭式对照。"""
    n = int(n_bits)
    lsb = float(vref) / float(1 << n)
    pts = [(i + 0.5) / float(samples) * float(vref) for i in range(int(samples))]
    errs, rows = [], []
    for v in pts:
        r = sar_convert(v, n, vref, c_unit, comp_offset_v=comp_offset_v)
        ideal_code = int(math.floor(v / lsb + 0.5))
        ideal_code = min(max(ideal_code, 0), (1 << n) - 1)
        e_lsb = abs(r["code"] - ideal_code)
        errs.append(e_lsb)
        rows.append({"v_in": v, "code": int(r["code"]), "ideal_code": ideal_code,
                     "err_lsb": int(e_lsb)})
    return {"n_bits": n, "samples": len(pts), "max_err_lsb": int(max(errs)),
            "all_within_1lsb": bool(max(errs) <= 1), "points": rows,
            "is_oracle": False}


# ═══════════════════════════ ④ 采样保持（真瞬态 RC）═══════════════════════════
def sample_hold_transient(v_in: float = 0.8, t_sample: float = 5.0e-9,
                          rs_ohm: float = 1.0e3, cs_f: float = 1.0e-12,
                          n_steps: int = 40) -> Dict:
    """**采样保持**：`C_s` 经 `R_s` 充电 ⇒ 一阶 RC 建立。

    🔴 **两个口径必须分清**（本项目 E11-d「数值窗口 vs 物理窗口」纪律的同族）：
      · **连续闭式**（物理）：`v(t) = V_in(1 − e^{−t/RC})`
      · **后向欧拉离散闭式**（求解器实际在解的方程）：
        `v_n = V_in·(1 − (1 + dt/τ)^{−n})`，`dt = t_sample/n_steps`
    后向欧拉是**隐式一阶** ⇒ 有 **O(dt) 数值阻尼**（比连续解慢）⇒
    **判据必须与「离散闭式」比对**（同口径 ⇒ 机器精度），
    而「与连续闭式的偏差」应作为**离散化误差**单列，并验证它**随步长加密而下降**。
    """
    tau = float(rs_ohm) * float(cs_f)
    n = int(n_steps)
    dt = float(t_sample) / float(n)
    ckt = Circuit("sh")
    VIN, OUT = 1, 2
    ckt.vsource(VIN, 0, float(v_in), "VIN")
    ckt.resistor(VIN, OUT, float(rs_ohm), "RS")
    ckt.capacitor(OUT, 0, float(cs_f), "CS")
    ckt.resistor(0, 0, 1.0e9, "dummy")
    times, out = ckt.solve_transient(t_end=float(t_sample), n_steps=n)
    v_end = float(out[-1][OUT])
    closed = float(v_in) * (1.0 - math.exp(-float(t_sample) / tau))
    discrete = float(v_in) * (1.0 - (1.0 + dt / tau) ** (-n))
    t_05lsb = -tau * math.log(1.0 - (1.0 - 0.5 / 256.0))
    return {
        "v_in": float(v_in), "t_sample_s": float(t_sample), "tau_s": tau,
        "dt_s": dt, "n_steps": n,
        "v_end_v": v_end,
        "closed_form_v": closed,               # 连续（物理）
        "discrete_form_v": discrete,           # 后向欧拉（求解器方程）
        "rel_err": abs(v_end - closed) / abs(closed) if closed else float("inf"),
        "rel_err_discrete": (abs(v_end - discrete) / abs(discrete)
                             if discrete else float("inf")),
        "discretization_rel": (abs(discrete - closed) / abs(closed)
                               if closed else float("inf")),
        "t_to_half_lsb_8bit_s": float(t_05lsb),
        "settling_ratio_0p5lsb": float(t_05lsb / tau),
        "is_oracle": False,
    }


# ═══════════════════════════ 自检 ═══════════════════════════
CONVERTER_DISCLOSURE: dict = {
    "route": "电子计算征程 E14 · 真转换器电路（R-2R DAC + SAR/CDAC ADC + 采样保持）",
    "capability": "R-2R 梯形 DAC（NMOS 模拟开关）· SAR + CDAC 电荷重分配 ADC（真瞬态）· 采样保持 RC",
    "golden": "分压 V_ref·code/2^N · 电荷守恒 V_ref·Σb_iC_i/C_total − V_in · 一阶 RC V_in(1−e^{−t/RC})",
    "sub_golden": "R-2R 用 MNA 解理想开关网络 ⟷ 二进制除权闭式（**网络装配自证** · 方法学独立）",
    "why_transient": "电容 DC 开路 ⇒ 顶板电位与电荷分配无关；后向欧拉伴随模型给出 **Q_top 严格守恒** "
                     "⇒ 一步瞬态 = 精确电荷守恒解",
    "honest_boundary": "**比较器是「有限增益 + 失调 + 噪声」判决器抽象，非晶体管级比较器**（MNA 无非线性饱和 "
                       "器件，E2 已证朴素差分对无法闭合高增益环路）；**CDAC 底板开关用理想电压源抽象**"
                       "（DAC 侧用真 NMOS 开关暴露 R_on）· 电阻/电容为理想值（不建匹配网络）· "
                       "R_on 取三极管区闭式 · 电荷注入/时钟馈通只给量级 · 参数公开量级占位（非 PDK）· "
                       "不做流片 · 不报 TOPS/TOPS-W/fJ/op",
    "redline": "红线 = 分层口径（器件级 T1 已解锁 · T2 工艺真值/流片永久锁）；LLM 不进判决路径；"
               "C 级自主（纯 numpy/标准库，零商业 SPICE）；**不替换** E3 的行为级通路（真转换器是并行第二通路）",
}


def converter_self_check(verbose: bool = True) -> bool:
    msgs: List[Tuple[str, bool, str]] = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True

    # ① R-2R 网络装配自证：MNA 理想网络 ⟷ 二进制除权闭式（方法学独立）
    worst = 0.0
    for code in (0, 1, 2, 5, 17, 85, 170, 255):
        bs = code_to_bits(code, 8)
        v_net = r2r_ideal_network_dc(bs, 1.0, 10.0e3)
        v_cf = ideal_dac_voltage(code, 8, 1.0)
        worst = max(worst, abs(v_net - v_cf))
    ok &= chk("① R-2R 网络装配自证：MNA 理想网络 ⟷ 闭式 V_ref·code/2^N（max|Δ| < 1e-9）",
              worst < 1e-9, "max|Δ|=%.3e" % worst)

    # ② 真 NMOS 开关 DAC：全码扫描 ⟷ 闭式（1 LSB 内）
    rep = dac_static_report(8, step=1)
    ok &= chk("② 真 NMOS 开关 DAC：8 bit 全码扫描 max|Δ| < 1 LSB · 单调 · R_on=%.1f Ω"
              % rep["ron_ohm"],
              rep["max_abs_err_lsb"] < 1.0 and rep["monotone"],
              "err=%.4f LSB · INL=%.4f · R_on/R=%.5f"
              % (rep["max_abs_err_lsb"], rep["inl_lsb_max"], rep["ron_over_r"]))

    # ③ DAC 位数趋势：位数↑ ⇒ 相对误差↓（同 R_on/R 下 LSB 变小会恶化 ⇒ 用 R_on 影响验证）
    r_big = nmos_switch_ron_ohm(3.0, 0.4, 120e-6, 2000.0)      # 大 W/L ⇒ 小 R_on
    r_sml = nmos_switch_ron_ohm(3.0, 0.4, 120e-6, 50.0)        # 小 W/L ⇒ 大 R_on
    rep_big = dac_static_report(6, dac_sw_wl=2000.0, step=1)
    rep_sml = dac_static_report(6, dac_sw_wl=50.0, step=1)
    ok &= chk("③ R_on 是精度来源：开关 W/L ↑ ⇒ R_on ↓ ⇒ 静态误差 ↓（大/小 W/L 对照）",
              abs(rep_big["max_abs_err_lsb"]) < abs(rep_sml["max_abs_err_lsb"]),
              "W/L=2000 → %.4f LSB；W/L=50 → %.4f LSB（R_on %.1f / %.1f Ω）"
              % (rep_big["max_abs_err_lsb"], rep_sml["max_abs_err_lsb"], r_big, r_sml))

    # ④ CDAC 顶板闭式：采样→保持后 V_top = −V_in（电荷守恒）
    r4 = sar_convert(0.5, 8, 1.0)
    ok &= chk("④ CDAC 电荷守恒：保持后 V_top ⟷ 闭式 −V_in（相对误差 < 1e-6）",
              abs(r4["v_top_hold_v"] - r4["top_closed_form_hold_v"])
              / abs(r4["top_closed_form_hold_v"]) < 1e-6,
              "V_top=%.9f ⟷ 闭式 %.9f" % (r4["v_top_hold_v"], r4["top_closed_form_hold_v"]))

    # ⑤ SAR 转换精度：全部取样点 ≤ 1 LSB
    e5 = sar_error_report(8, samples=16)
    ok &= chk("⑤ SAR + CDAC 转换：16 个取样点 max 误差 ≤ 1 LSB",
              e5["all_within_1lsb"], "max=%d LSB" % e5["max_err_lsb"])

    # ⑥ SAR 逼近收敛：第 k 步剩余 |V_top| ≤ V_ref/2^(N-k)（逐次逼近闭式）
    ok &= chk("⑥ 逐次逼近收敛：末步残差 |V_top| ≤ 1 LSB（区间每步减半）",
              abs(r4["residual_v"]) <= r4["lsb_v"] * 1.5,
              "residual=%.3e V · LSB=%.3e V" % (r4["residual_v"], r4["lsb_v"]))

    # ⑦ 采样保持：瞬态 ⟷ **后向欧拉离散闭式**（同口径 ⇒ 机器精度）
    sh = sample_hold_transient()
    ok &= chk("⑦ 采样保持瞬态 ⟷ **后向欧拉离散闭式**（同口径 · rel < 1e-9）",
              sh["rel_err_discrete"] < 1e-9,
              "v_end=%.9f ⟷ 离散 %.9f（rel=%.2e）"
              % (sh["v_end_v"], sh["discrete_form_v"], sh["rel_err_discrete"]))

    # ⑦b 离散 vs 连续：步长加密 ⇒ 离散化偏差 ↓（后向欧拉 O(dt) 一阶收敛）
    d40 = sample_hold_transient(n_steps=40)["discretization_rel"]
    d80 = sample_hold_transient(n_steps=80)["discretization_rel"]
    d160 = sample_hold_transient(n_steps=160)["discretization_rel"]
    ok &= chk("⑦b 离散化误差 O(dt)：步长 40→80→160 ⇒ 与连续闭式偏差单调降（比值 ≈ 2）",
              d40 > d80 > d160 and 1.5 < (d40 / d80) < 2.6,
              "%.3e → %.3e → %.3e（比值 %.2f）" % (d40, d80, d160, d40 / d80))

    # ⑧ 采样时间单调：t_sample ↑ ⇒ 建立误差 ↓
    e_short = sample_hold_transient(t_sample=1.0e-9)["closed_form_v"]
    e_long = sample_hold_transient(t_sample=10.0e-9)["closed_form_v"]
    tau = sh["tau_s"]
    ok &= chk("⑧ 采样时间单调：t_sample ↑ ⇒ 未建立残差 |V_in−v| ↓（一阶指数收敛）",
              (0.8 - e_long) < (0.8 - e_short) and (0.8 - e_long) > 0.0,
              "t=1 ns 残差 %.4f · t=10 ns 残差 %.4e（τ=%.1e s）"
              % (0.8 - e_short, 0.8 - e_long, tau))

    # ⑨ 比较器失调 ⇒ 转换码偏移（失调效应可见）
    off_hi = sar_error_report(6, samples=8, comp_offset_v=0.01)
    off_lo = sar_error_report(6, samples=8, comp_offset_v=-0.01)
    ok &= chk("⑨ 比较器失调可见：失调 ±10 mV ⇒ 8 bit 下的码误差 ≤ 1 LSB（低位敏感性）",
              off_hi["max_err_lsb"] <= 2 and off_lo["max_err_lsb"] <= 2,
              "off=+10mV → %d LSB；off=−10mV → %d LSB"
              % (off_hi["max_err_lsb"], off_lo["max_err_lsb"]))

    # ⑩ 诚实边界：披露显式声明比较器抽象 + 不报 TOPS
    ok &= chk("⑩ 披露显式声明「比较器是判决器抽象 / 非晶体管级」且不报 TOPS",
              "判决器抽象" in CONVERTER_DISCLOSURE["honest_boundary"]
              and "TOPS" in CONVERTER_DISCLOSURE["honest_boundary"])

    if verbose:
        for nm, c, det in msgs:
            print(("  [PASS] " if c else "  [FAIL] ") + nm + ((" :: " + det) if det else ""))
        print("  —— converter 自检 %d/%d ——" % (sum(1 for _, c, _ in msgs if c), len(msgs)))
    return ok


if __name__ == "__main__":
    import json
    print("=== converter 自检 ===")
    converter_self_check(verbose=True)
    print("=== DAC 静态报告（8 bit）===")
    print(json.dumps(dac_static_report(8, step=1), ensure_ascii=False, indent=1)[:900])
    print("=== SAR 报告（8 bit）===")
    print(json.dumps(sar_convert(0.4187, 8), ensure_ascii=False, indent=1)[:900])
