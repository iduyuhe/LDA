# -*- coding: utf-8 -*-
"""E19 列侧共享的动态代价（`lda/lda_l2/ecore/col_share_dynamic.py` · D-194）。

═══════════════════════════════════════════════════════════════════════════
定位：**E18 静态面积/吞吐口径的「动态补齐」**（面积/时间维度上的 E15/E17 动态尾）
═══════════════════════════════════════════════════════════════════════════
E18 补上了「面积」维度，但**自点名**（G-S 诚实边界）留了一个缺口：
「共享的**动态代价**（多路开关电荷注入 / 串扰 / 采样孔径抖动 / 复用开关建立时间）未建模」。

本段把 E18 的「**静态面积**」口径闭合成「**静态 + 动态**」：
· ① 复用开关**电荷注入 + 时钟馈通** = 确定性 pedestal（可单次校准消）+ Pelgrom 随机残差 σ（接 E8）
· ② **采样孔径抖动** σ_v = slope·σ_t · 地板仍是 E18 的 kT/C
· ③ 多路开关**建立时间对吞吐的侵蚀**（复用 E14 R_on·E17 建立律，叠加到 E18 每列周期）

═══════════════════════════════════════════════════════════════════════════
🔴🔴 诚实结论（接续 E18「诚实拒绝造腿」）
═══════════════════════════════════════════════════════════════════════════
在可达共享度内，三项动态代价**都不是精度墙**：
① 电荷注入的确定性 pedestal 虽大（~12% FS 量级）但**可单点校准消除** ⇒ 不进精度预算；
   其 Pelgrom 随机残差 ~29 µV ≪ kT/C/LSB ⇒ 不是墙；**真成本 = 校准负担（N 列需 N 次失调校准）**。
② 孔径抖动在低/中带宽被 kT/C 与 LSB 埋住，仅当输入带宽 >~20 MHz 才越过热噪地板、>~1.2 GHz 才越 LSB
   （保吞吐共享因抬高 kT/C 地板而更早触发）；**条件性，非墙**。
③ 多路开关建立是**固定绝对开销**（采样电容 C_s 固定）：plain 共享下平坦 ~0.04%（可忽略）；
   **保吞吐共享下随 K 回升**，在 K*≈160 处达 ~7% 每列周期 —— 这是 E18 静态模型**此前未计**
   的真实动态代价，且**反相关于 E18 的面积收益**（与抖动同族）。
⇒ 共享的真实、新代价 = 「保吞吐共享的开关建立开销」+「高带宽孔径抖动」，二者都反相关于 E18 静态收益，
  但**都不造新墙**（不硬造精度腿 / 不报 TOPS）。

═══════════════════════════════════════════════════════════════════════════
保护性约束
═══════════════════════════════════════════════════════════════════════════
**只读消费** E14/E17/E18/E8/E15 —— **不改** `CONV_PROCESS`/`TIMING_PROCESS`/`COL_SHARE_PROCESS`/任何既有默认值；
`keep_throughput` 默认 **False** ⇒ **E15/E16/E17/E18 已发布数字逐位不变**；
本段**只新增**动态代价项与吞吐侵蚀，**不覆盖** E18 的 `converter_period_s`/`col_throughput_sps` 返回值。

═══════════════════════════════════════════════════════════════════════════
诚实边界
═══════════════════════════════════════════════════════════════════════════
开关尺寸/重叠/抖动/信号频率均为**公开量级占位（非 PDK）**；电荷注入用对称分配 α=0.5 经典模型；
时钟馈通用栅漏重叠 C_gd 一阶模型；孔径抖动取满量程正弦最陡斜率 π·f·V_ref（最坏口径）；
复用开关 R_on 与 E18 CDAC 开关**同一器件**（W/L=500 ⇒ 6.41 Ω）；**不做功耗估算 ⇒ 不谈能效**；
🔴 **绝不报 TOPS / TOPS-W / fJ/op**。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from . import converter as CV
from . import timing as T
from . import col_share as CS
from . import mismatch as MM
from . import budget as BG

KB = 1.380649e-23

# ═══════════════════════════════════════════════════════════════════════════
# 工艺 / 默认参数（**公开典型量级占位 · 非 PDK**）
# ═══════════════════════════════════════════════════════════════════════════
COL_SHARE_DYN_PROCESS: Dict[str, float] = {
    "mux_w_um": 50.0,              # 开关绘制宽度（与 E18 `switch_wl=500` 同口径 ⇒ L=0.1µm）
    "mux_l_um": 0.1,               # 开关绘制长度（W/L = 500）
    "mux_vgate_v": 3.0,            # 开关栅压（导通）
    "mux_vth_v": 0.4,              # 开关阈值（与 E14 `vth` 默认同口径）
    "charge_inj_alpha": 0.5,        # 沟道电荷对称分配系数（经典模型）
    "clk_feedthrough_overlap_um": 0.05,  # 栅漏重叠 L_ov（µm）
    "clk_swing_v": 3.0,            # 时钟摆幅 ΔV_clk（V）
    "sample_cap_f": 1.0e-12,        # 采样电容 C_s（复用 E14 `CONV_PROCESS['cs_f']`）
    "clock_jitter_sigma_s": 1.0e-12,  # 时钟抖动 σ_t（1 ps rms，公开量级）
    "signal_freq_hz": 100.0e6,      # 被采样信号带宽参考（100 MHz）
    "temperature_k": 300.0,
    "ref_v": 1.0,
    "k_sigma": 3.0,
}

COL_SHARE_DYN_DISCLOSURE: Dict[str, str] = {
    "role": "E19 = 列侧共享的**动态代价** —— 闭合 E18 G-S 自点名的缺口"
            "（多路开关电荷注入 / 采样孔径抖动 / 复用开关建立时间）",
    "charge_injection": "🔴 复用开关电荷注入 + 时钟馈通 = 确定性 pedestal（~12% FS 量级）**可单点校准消除**"
                        "⇒ 不进精度预算；Pelgrom 随机残差 ~29 µV ≪ kT/C/LSB ⇒ 不是墙；"
                        "**真成本 = 校准负担（N 列需 N 次失调校准）**",
    "aperture_jitter": "🔴 采样孔径抖动 σ_v = π·f·V_ref·σ_t（满量程正弦最陡斜率最坏口径）；"
                       "低/中带宽被 kT/C 与 LSB 埋住：越 kT/C ≈ 20.5 MHz、越 LSB ≈ 1.24 GHz"
                       "（保吞吐共享抬高 kT/C 地板 ⇒ 更早触发）；**条件性，非墙**",
    "mux_settling": "🔴 多路开关建立 τ_mux = R_on·C_s（C_s 固定绝对开销）；plain 共享侵蚀恒定 ~0.04%（可忽略），"
                    "**保吞吐共享下随 K 回升、K*≈160 处 ≈7% 每列周期** —— E18 静态模型此前未计的真实动态代价",
    "upstream_anchor": "复用 E14 `nmos_switch_ron_ohm`（与 E18 CDAC 开关同一器件 W/L=500 ⇒ 6.41Ω）"
                        "· E17 `settle_half_lsb`（建立律）· E18 `converter_period_s`/`thermal_noise_rms_v`"
                        "· E8 `pelgrom_sigma_vth_mv` · E15 `make_term`",
    "area_model": "开关尺寸/重叠/抖动/信号频率均为**公开量级占位（非 PDK）**；电荷注入用 α=0.5 经典模型；"
                  "时钟馈通用栅漏重叠 C_gd 一阶模型",
    "protect": "🔴 **只读消费** E14/E17/E18/E8/E15 —— 不改任何既有默认值；`keep_throughput` 默认 **False**"
               "⇒ E15/E16/E17/E18 已发布数字**逐位不变**；**不覆盖** E18 的 `converter_period_s`/`col_throughput_sps`",
    "no_power": "🔴 **不做功耗估算 ⇒ 不谈能效**；**绝不报 TOPS / TOPS-W / fJ/op**",
    "red_line": "纯标准库（复用 E14/E17/E18/E8/E15）· LLM 不进判决路径 · 零商业 EDA 依赖 · **非签核级 SPICE**",
}

__all__ = [
    "KB", "COL_SHARE_DYN_PROCESS", "COL_SHARE_DYN_DISCLOSURE",
    # ① 电荷注入 + 时钟馈通
    "charge_injection_pedestal_v", "charge_injection_residual_sigma_v",
    # ② 孔径抖动
    "aperture_jitter_sigma_v", "jitter_bandwidth_limits",
    # ③ 多路开关建立侵蚀
    "mux_settling_tau", "mux_settling_erosion",
    # ④ 预算项 / 报告 / 自检
    "dynamic_budget_terms", "dynamic_cost_report", "col_share_dynamic_self_check",
]


def _p(key: str, override: Optional[dict] = None):
    if override and key in override:
        return override[key]
    return COL_SHARE_DYN_PROCESS[key]


# ═══════════════════════════════════════════════════════════════════════════
# ① 复用开关电荷注入 + 时钟馈通
# ═══════════════════════════════════════════════════════════════════════════
def charge_injection_pedestal_v(override: Optional[dict] = None) -> Dict:
    """**确定性 pedestal**（电荷注入 + 时钟馈通）—— 关断瞬间沟道电荷注入 + 时钟经栅漏重叠耦合。

    🔴 这是**确定性**偏移（给定工艺定值），可由**每列/每开关的单点失调校准消除**
    ⇒ **不进精度预算**（与 E16「共模漂移可被单次全局校准消除」同口径）。
    其**随机残差**见 `charge_injection_residual_sigma_v`（接 E8 Pelgrom）。
    """
    w = float(_p("mux_w_um", override))
    l = float(_p("mux_l_um", override))
    vg = float(_p("mux_vgate_v", override))
    vth = float(_p("mux_vth_v", override))
    alpha = float(_p("charge_inj_alpha", override))
    lov = float(_p("clk_feedthrough_overlap_um", override))
    dclk = float(_p("clk_swing_v", override))
    cs = float(_p("sample_cap_f", override))
    vref = float(_p("ref_v", override))
    cox = float(MM.MISMATCH_PROCESS["cox_f_per_um2"])        # F/µm²

    vov = vg - vth
    if vov <= 0.0:
        raise ValueError("开关过驱动须 > 0")
    c_ox_dev = cox * w * l                                 # 开关总栅氧电容
    q_inj = alpha * c_ox_dev * vov
    dv_inj = q_inj / cs
    c_gd = w * cox * lov                                    # 栅漏重叠电容
    dv_ft = (c_gd / (c_gd + cs)) * dclk
    pedestal = dv_inj + dv_ft
    return {
        "w_um": w, "l_um": l, "v_ov_v": vov, "c_ox_dev_f": c_ox_dev,
        "c_gd_f": c_gd, "sample_cap_f": cs,
        "delta_v_injection_v": dv_inj, "delta_v_feedthrough_v": dv_ft,
        "pedestal_v": pedestal, "pedestal_rel_pct": pedestal / vref * 100.0,
        "is_deterministic": True, "is_calibratable": True,
        "calibratable_note": "🔴 确定性偏移 ⇒ 可单点失调校准消除 ⇒ 不进精度预算",
        "is_oracle": False,
    }


def charge_injection_residual_sigma_v(override: Optional[dict] = None) -> Dict:
    """**校准后幸存的随机残差**（Pelgrom 口径）—— 各开关 W·L 与 V_th 失配 ⇒ pedestal 散布 1σ。

    `σ_ped = α·(C_ox·W·L)/C_s · σ_ΔVth`，`σ_ΔVth = A_VT/√(W·L)`（接 E8）。
    🔴 这是**唯一进精度预算**的电荷注入项（RANDOM / kσ）；量级 ≪ kT/C 与 LSB ⇒ 不是墙。
    """
    w = float(_p("mux_w_um", override))
    l = float(_p("mux_l_um", override))
    alpha = float(_p("charge_inj_alpha", override))
    cs = float(_p("sample_cap_f", override))
    vref = float(_p("ref_v", override))
    cox = float(MM.MISMATCH_PROCESS["cox_f_per_um2"])
    c_ox_dev = cox * w * l
    sig_dvth = MM.pelgrom_sigma_vth_mv(w, l) / 1000.0         # mV → V
    sig_ped = alpha * c_ox_dev / cs * sig_dvth
    ktc = CS.thermal_noise_rms_v(cs)
    lsb = vref / (1 << 8)
    return {
        "sigma_delta_vth_v": sig_dvth,
        "sigma_pedestal_v": sig_ped, "sigma_pedestal_rel_pct": sig_ped / vref * 100.0,
        "vs_ktc_ratio": (sig_ped / ktc) if ktc > 0 else float("inf"),
        "vs_lsb_ratio": sig_ped / lsb,
        "below_ktc": bool(sig_ped < ktc), "below_lsb": bool(sig_ped < lsb),
        "note": "🔴 仅此随机残差进精度预算；确定性 pedestal 已校准剔除",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ② 采样孔径抖动（地板 = E18 kT/C）
# ═══════════════════════════════════════════════════════════════════════════
def aperture_jitter_sigma_v(signal_freq_hz: Optional[float] = None,
                            override: Optional[dict] = None) -> Dict:
    """**孔径抖动电压误差** = `π·f·V_ref·σ_t`（满量程正弦最陡斜率，最坏口径）。

    `σ_t` 来自时钟抖动；`f` 为被采样信号带宽。地板仍是 E18 的 `σ=√(kT/C_s)`。
    """
    f = float(_p("signal_freq_hz", override) if signal_freq_hz is None else signal_freq_hz)
    sig_t = float(_p("clock_jitter_sigma_s", override))
    vref = float(_p("ref_v", override))
    cs = float(_p("sample_cap_f", override))
    if f < 0.0:
        raise ValueError("信号频率须 >= 0")
    sig_v = math.pi * f * vref * sig_t
    ktc = CS.thermal_noise_rms_v(cs)
    lsb = vref / (1 << 8)
    return {
        "signal_freq_hz": f, "clock_jitter_sigma_s": sig_t, "ref_v": vref,
        "sigma_v": sig_v, "sigma_rel_pct": sig_v / vref * 100.0,
        "ktc_floor_v": ktc, "lsb_v": lsb,
        "above_ktc": bool(sig_v > ktc), "below_lsb": bool(sig_v < lsb),
        "is_oracle": False,
    }


def jitter_bandwidth_limits(bits: int = 8, override: Optional[dict] = None) -> Dict:
    """**抖动何时越界**：越过 kT/C 与越过 LSB 的信号带宽交点。

    `f_ktc = σ_kTC / (π·V_ref·σ_t)`，`f_lsb = (V_ref/2^bits) / (π·V_ref·σ_t) = 1/(π·2^bits·σ_t)`。
    🔴 `f_ktc < f_lsb` ⇒ 抖动先在 >f_ktc 成为主导噪声（仍非精度限），在 >f_lsb 才越 LSB。
    """
    b = int(bits)
    sig_t = float(_p("clock_jitter_sigma_s", override))
    vref = float(_p("ref_v", override))
    cs = float(_p("sample_cap_f", override))
    ktc = CS.thermal_noise_rms_v(cs)
    lsb = vref / (1 << b)
    f_ktc = (ktc / (math.pi * vref * sig_t)) if sig_t > 0 else float("inf")
    f_lsb = (lsb / (math.pi * vref * sig_t)) if sig_t > 0 else float("inf")
    return {
        "bits": b, "ktc_floor_v": ktc, "lsb_v": lsb,
        "f_cross_ktc_hz": f_ktc, "f_cross_lsb_hz": f_lsb,
        "jitter_dominant_after_ktc": f_ktc > 0,
        "is_accuracy_limit_after_lsb": f_lsb > 0,
        "note": "🔴 f_ktc < f_lsb ⇒ 抖动先越 kT/C 成主导噪声、后越 LSB 成精度限；"
                "保吞吐共享抬高 kT/C 地板 ⇒ f_ktc 更早触发",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ③ 多路开关建立时间对吞吐的侵蚀（复用 E14 R_on · E17 建立律）
# ═══════════════════════════════════════════════════════════════════════════
def mux_settling_tau(bits: Optional[int] = None, override: Optional[dict] = None) -> Dict:
    """**多路开关建立时间常数 τ_mux = R_on_mux·C_s**（C_s 为固定绝对采样电容，与 CDAC 共享无关）。

    `R_on_mux` 复用 E14 `nmos_switch_ron_ohm`（与 E18 CDAC 开关同一器件 W/L=500 ⇒ 6.41 Ω）。
    `t_mux = settle_half_lsb(τ_mux, bits)`（复用 E17 G-2）。
    """
    w = float(_p("mux_w_um", override))
    l = float(_p("mux_l_um", override))
    vg = float(_p("mux_vgate_v", override))
    vth = float(_p("mux_vth_v", override))
    cs = float(_p("sample_cap_f", override))
    wl = w / l
    r_on = CV.nmos_switch_ron_ohm(v_gate=vg, vth=vth, w_over_l=wl)
    tau = r_on * cs
    b = int(T.TIMING_PROCESS["bits"] if bits is None else bits)
    t_settle = T.settle_half_lsb(tau, b)
    return {
        "w_over_l": wl, "r_on_ohm": r_on, "sample_cap_f": cs, "tau_s": tau,
        "bits": b, "t_settle_s": t_settle,
        "same_device_as_e18": bool(abs(r_on - T.cdac_settle_tau(b)["r_on_ohm"]) < 1e-15),
        "is_oracle": False,
    }


def mux_settling_erosion(n_cols: int, k_adc: int = 1, bits: Optional[int] = None,
                         keep_throughput: bool = False, override: Optional[dict] = None) -> Dict:
    """🔴 **多路开关建立对吞吐的侵蚀** —— 叠加在 E18 每列周期之上（**不覆盖** E18 返回值）。

    `C_s` 固定绝对 ⇒ `t_mux` 不随 K 缩小：
    · **plain 共享**（不保吞吐）：每列周期 `K·(T_conv(1)+t_mux)` vs E18 基线 `K·T_conv(1)`
      ⇒ 侵蚀 **恒定 = t_mux/T_conv(1)**（可忽略）。
    · **保吞吐共享**（C_tot 同比降 K ⇒ 吞吐保住）：每列周期 `K·(T_conv(1)/K+t_mux)=T_conv(1)+K·t_mux`
      vs E18 基线 `T_conv(1)` ⇒ 侵蚀 **∝ K**（K*=160 处 ≈ 7%）。
    """
    n = int(n_cols)
    k = max(1, int(k_adc))
    if n < 1:
        raise ValueError("列数须 >= 1")
    b = int(T.TIMING_PROCESS["bits"] if bits is None else bits)
    t_mux = mux_settling_tau(b, override)["t_settle_s"]
    t_conv1 = CS.converter_period_s(b)                       # 未共享转换周期（E18）
    if keep_throughput:
        baseline = t_conv1                                   # E18 keep_throughput 每列周期 = T_conv(1)
        per_col = k * (t_conv1 / float(k) + t_mux)           # = T_conv(1) + K·t_mux
        e18_throughput = CS.col_throughput_sps(k, b, keep_throughput=True)
    else:
        baseline = k * t_conv1                               # E18 plain 每列周期
        per_col = k * (t_conv1 + t_mux)
        e18_throughput = CS.col_throughput_sps(k, b, keep_throughput=False)
    overhead_rel = (per_col - baseline) / baseline if baseline > 0 else 0.0
    eff = 1.0 / per_col
    return {
        "n_cols": n, "k_adc": k, "bits": b, "keep_throughput": bool(keep_throughput),
        "t_mux_settle_s": t_mux, "t_conv1_s": t_conv1,
        "baseline_per_col_period_s": baseline, "per_col_period_s": per_col,
        "overhead_rel_pct": overhead_rel * 100.0,
        "e18_throughput_sps": e18_throughput, "effective_throughput_sps": eff,
        "erosion_factor": (eff / e18_throughput) if e18_throughput > 0 else 0.0,
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ④ 预算项（接 E15 make_term）
# ═══════════════════════════════════════════════════════════════════════════
def dynamic_budget_terms(n_cols: int = 8, m: int = 8, bits: int = 8,
                         override: Optional[dict] = None) -> List[Dict]:
    """**动态代价误差项**（E15 `make_term` 格式 · 相对满量程百分比 · 1σ）。

    🔴 仅含**进预算**的两项 RANDOM（kσ）：① 电荷注入 Pelgrom 随机残差（确定性 pedestal 已校准剔除）
    ② 孔径抖动（在参考带宽 `signal_freq_hz` 下）。两者地板均为 E18 kT/C。
    确定性 pedestal（可校准）/ 多路开关建立（吞吐代价非 %FS 误差）**不入预算**。

    🔴 `n_cols`/`m` 保留在签名里（与 E15 `make_term` 调用方口径一致、且 `dynamic_cost_report`
    原样透传），但**本函数的预算项与阵列规模无关**（σ 均为单位 cell 级量），
    故这里不得出现 `n = int(n_cols)` 之类的尺寸派生——那是死代码，pyflakes 棘轮会拦（F841）。
    """
    b = int(bits)
    res = charge_injection_residual_sigma_v(override)
    jit = aperture_jitter_sigma_v(None, override)
    terms = [
        BG.make_term(
            "colshare_charge_injection_residual", BG.RANDOM,
            float(res["sigma_pedestal_rel_pct"]), "E19/E8",
            "复用开关电荷注入 Pelgrom 随机残差（确定性 pedestal 已单点校准剔除）；"
            "σ≈%.3e V ≪ kT/C/LSB ⇒ 非墙" % res["sigma_pedestal_v"]),
        BG.make_term(
            "colshare_aperture_jitter", BG.RANDOM,
            float(jit["sigma_rel_pct"]), "E19",
            "采样孔径抖动 σ_v=π·f·V_ref·σ_t（f=%.0f Hz）；越 kT/C=%.1f MHz · 越 LSB=%.0f MHz"
            % (jit["signal_freq_hz"], jitter_bandwidth_limits(b, override)["f_cross_ktc_hz"] / 1e6,
               jitter_bandwidth_limits(b, override)["f_cross_lsb_hz"] / 1e6)),
    ]
    return terms


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 汇总报告
# ═══════════════════════════════════════════════════════════════════════════
def dynamic_cost_report(n_cols: int = 8, m: int = 8, bits: int = 8,
                        ks: Sequence[int] = (1, 2, 4, 8, 16, 32, 64, 128, 160),
                        override: Optional[dict] = None) -> Dict:
    """**三项动态代价的汇总**（含保吞吐/不保吞吐两路 mux 侵蚀对照表）。"""
    b = int(bits)
    ped = charge_injection_pedestal_v(override)
    res = charge_injection_residual_sigma_v(override)
    jit = aperture_jitter_sigma_v(None, override)
    jlim = jitter_bandwidth_limits(b, override)
    t_mux = mux_settling_tau(b, override)
    ero_rows = []
    for k in ks:
        k = int(k)
        e_plain = mux_settling_erosion(n_cols, k, b, False, override)
        e_keep = mux_settling_erosion(n_cols, k, b, True, override)
        ero_rows.append({
            "k_adc": k,
            "overhead_plain_pct": e_plain["overhead_rel_pct"],
            "overhead_keep_pct": e_keep["overhead_rel_pct"],
            "effective_throughput_keep_sps": e_keep["effective_throughput_sps"],
        })
    terms = dynamic_budget_terms(n_cols, m, b, override)
    combined = BG.combine(terms)
    return {
        "bits": b, "n_cols": int(n_cols),
        "charge_injection": {
            "pedestal_v": ped["pedestal_v"], "pedestal_rel_pct": ped["pedestal_rel_pct"],
            "is_calibratable": ped["is_calibratable"],
            "residual_sigma_v": res["sigma_pedestal_v"],
            "residual_rel_pct": res["sigma_pedestal_rel_pct"],
            "residual_below_ktc": res["below_ktc"], "residual_below_lsb": res["below_lsb"],
        },
        "aperture_jitter": {
            "signal_freq_hz": jit["signal_freq_hz"], "sigma_v": jit["sigma_v"],
            "sigma_rel_pct": jit["sigma_rel_pct"],
            "f_cross_ktc_hz": jlim["f_cross_ktc_hz"],
            "f_cross_lsb_hz": jlim["f_cross_lsb_hz"],
            "below_lsb_at_ref": jit["below_lsb"],
        },
        "mux_settling": {
            "r_on_ohm": t_mux["r_on_ohm"], "tau_s": t_mux["tau_s"],
            "t_settle_s": t_mux["t_settle_s"],
            "erosion_table": ero_rows,
        },
        "budget_terms": terms,
        "budget_combined": combined,
        "conclusion": "🔴 三项动态代价在可达共享度内**都不是精度墙**：① 电荷注入确定性 pedestal 可校准"
                      "（真成本=校准负担）· 残差可忽略；② 孔径抖动仅高带宽越 kT/C/LSB（条件性）；"
                      "③ 多路开关建立在保吞吐共享下随 K 回升、K*≈160 处 ≈7% 每列周期（E18 漏计的真实代价，"
                      "反相关于 E18 面积收益）。⇒ 共享真实新代价=保吞吐开关建立开销+高带宽抖动，都不造新墙",
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 自检（13 项）
# ═══════════════════════════════════════════════════════════════════════════
def col_share_dynamic_self_check(verbose: bool = True) -> bool:
    """模块自检 **13 项**（电荷注入 + 孔径抖动 + mux 建立侵蚀 + 跨模块交叉 + 保护性约束）。"""
    res = True

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        nonlocal res
        if verbose:
            print(("PASS | " if cond else "FAIL | ") + name
                  + (("  :: " + detail) if detail else ""))
        res = res and bool(cond)
        return bool(cond)

    # ① 电荷注入 pedestal > 0、确定性、可校准；且随机残差 ≪ pedestal
    ped = charge_injection_pedestal_v()
    resd = charge_injection_residual_sigma_v()
    chk("① 电荷注入：pedestal=%.1f mV（%.1f%%FS）确定性可校准 · 随机残差 %.2f µV ≪ pedestal"
        % (ped["pedestal_v"] * 1e3, ped["pedestal_rel_pct"], resd["sigma_pedestal_v"] * 1e6),
        ped["pedestal_v"] > 0.05 and ped["is_calibratable"] is True
        and resd["sigma_pedestal_v"] < ped["pedestal_v"] / 100.0,
        "ped=%.4e V · σ_res=%.3e V" % (ped["pedestal_v"], resd["sigma_pedestal_v"]))

    # ② 电荷注入随机残差 ≪ kT/C 与 LSB（不是墙）
    ktc_cs = CS.thermal_noise_rms_v(ped["sample_cap_f"])
    lsb_v = ped["ref_v"] / (1 << 8) if "ref_v" in ped else 1.0 / (1 << 8)
    chk("② 电荷注入随机残差 ≪ kT/C(%.2e V) 与 LSB(%.2e V)：σ_res=%.2e V"
        % (ktc_cs, lsb_v, resd["sigma_pedestal_v"]),
        resd["below_ktc"] and resd["below_lsb"],
        "vs_ktc=%.4f · vs_lsb=%.5f" % (resd["vs_ktc_ratio"], resd["vs_lsb_ratio"]))

    # ③ 孔径抖动在参考带宽（100 MHz）下低于 LSB（条件性，非墙）
    jit = aperture_jitter_sigma_v()
    chk("③ 孔径抖动 @ %.0f MHz：σ_v=%.1f µV（%.4f%%FS）< LSB=%.1f µV（条件性）"
        % (jit["signal_freq_hz"] / 1e6, jit["sigma_v"] * 1e6, jit["sigma_rel_pct"],
           jit["lsb_v"] * 1e6),
        jit["sigma_v"] > 0 and jit["below_lsb"] is True,
        "σ_v=%.4e V" % jit["sigma_v"])

    # ④ 抖动越界频率单调：f_ktc < f_lsb，且均 > 0
    jlim = jitter_bandwidth_limits(8)
    chk("④ 抖动越界频率：f_ktc=%.1f MHz < f_lsb=%.0f MHz（先越 kT/C 再越 LSB）"
        % (jlim["f_cross_ktc_hz"] / 1e6, jlim["f_cross_lsb_hz"] / 1e6),
        0 < jlim["f_cross_ktc_hz"] < jlim["f_cross_lsb_hz"],
        "f_ktc=%.4e · f_lsb=%.4e Hz" % (jlim["f_cross_ktc_hz"], jlim["f_cross_lsb_hz"]))

    # ⑤ mux R_on == E18 CDAC 开关 R_on（同一器件 W/L=500）；t_mux 远小于 T_conv(1)
    t_mux = mux_settling_tau(8)
    tconv1 = CS.converter_period_s(8)
    chk("⑤ 多路开关 R_on=%.4f Ω（同一器件 W/L=500）· t_mux=%.2f ps ≪ T_conv(1)=%.1f ns（×%.0f）"
        % (t_mux["r_on_ohm"], t_mux["t_settle_s"] * 1e12, tconv1 * 1e9,
           tconv1 / t_mux["t_settle_s"]),
        t_mux["same_device_as_e18"] and abs(t_mux["r_on_ohm"] - T.cdac_settle_tau(8)["r_on_ohm"]) < 1e-15
        and t_mux["t_settle_s"] < tconv1 / 1000.0,
        "τ_mux=%.3e s" % t_mux["tau_s"])

    # ⑥ plain mux 侵蚀恒定 = t_mux/T_conv(1)，与 K 无关
    e_plain_1 = mux_settling_erosion(64, 1, 8, False)
    e_plain_4 = mux_settling_erosion(64, 4, 8, False)
    chk("⑥ plain 共享 mux 侵蚀恒定（∝ t_mux/T_conv，与 K 无关）：K=1 → %.4f%% · K=4 → %.4f%%"
        % (e_plain_1["overhead_rel_pct"], e_plain_4["overhead_rel_pct"]),
        abs(e_plain_1["overhead_rel_pct"] - e_plain_4["overhead_rel_pct"]) < 1e-9
        and abs(e_plain_1["overhead_rel_pct"] - t_mux["t_settle_s"] / tconv1 * 100.0) < 1e-9,
        "恒定侵蚀 %.4f%%" % e_plain_1["overhead_rel_pct"])

    # ⑦ keep mux 侵蚀 ∝ K：K=160 约为 K=1 的 160 倍，且 K*=160 处 ≈7%
    e_keep_1 = mux_settling_erosion(64, 1, 8, True)
    e_keep_160 = mux_settling_erosion(64, 160, 8, True)
    chk("⑦ 保吞吐共享 mux 侵蚀 ∝ K：K=1 → %.4f%% · K=160 → %.2f%%（≈K 倍 · K* 处 ~7%%）"
        % (e_keep_1["overhead_rel_pct"], e_keep_160["overhead_rel_pct"]),
        abs(e_keep_160["overhead_rel_pct"] / e_keep_1["overhead_rel_pct"] - 160.0) < 1e-9
        and 5.0 < e_keep_160["overhead_rel_pct"] < 9.0,
        "K=160 侵蚀 %.3f%%" % e_keep_160["overhead_rel_pct"])

    # ⑧ keep 侵蚀 >> plain 侵蚀（K=160 时约 K 倍）
    e_plain_160 = mux_settling_erosion(64, 160, 8, False)
    chk("⑧ 保吞吐共享侵蚀(K=160, %.2f%%) ≫ plain 共享侵蚀(K=160, %.4f%%)（反相关于 E18 面积收益）"
        % (e_keep_160["overhead_rel_pct"], e_plain_160["overhead_rel_pct"]),
        e_keep_160["overhead_rel_pct"] > 100.0 * e_plain_160["overhead_rel_pct"],
        "比值 ≈ %.1f×" % (e_keep_160["overhead_rel_pct"] / e_plain_160["overhead_rel_pct"]))

    # ⑨ 预算项格式合规（类别∈CATEGORIES、非负）+ 合成律可跑
    terms = dynamic_budget_terms(8, 8, 8)
    ok_fmt = all(t["category"] in BG.CATEGORIES and t["rel_pct"] >= 0.0 for t in terms)
    cmb = BG.combine(terms)
    chk("⑨ 动态预算项格式合规（RANDOM·非负）且 E15 合成律可跑：worst=%.4f%% ⇒ %.3f 位"
        % (cmb["worst_pct"], cmb["worst_bits"]),
        ok_fmt and len(terms) == 2 and cmb["n_terms"] == 2 and cmb["worst_bits"] > 7.0,
        "项=%d · worst_bits=%.4f" % (cmb["n_terms"], cmb["worst_bits"]))

    # ⑩ 保护性：E18 已发布数字逐位不变（converter_period_s / col_throughput_sps 不受 E19 影响）
    tconv8 = CS.converter_period_s(8)
    sps4 = CS.col_throughput_sps(4, 8, keep_throughput=False)
    chk("⑩ 🔴 保护性：E18 `converter_period_s(8)` 逐位不变 · `col_throughput_sps(4,keep=False)==1/(4·T_conv)` · "
        "CONV/TIMING/COL_SHARE_PROCESS 键值未改",
        abs(tconv8 - 9.213525600058347e-08) < 1e-21
        and abs(sps4 - 1.0 / (4.0 * tconv8)) < 1e-30
        and CV.CONV_PROCESS["c_unit_f"] == 1.0e-12
        and T.TIMING_PROCESS["bits"] == 8
        and CS.COL_SHARE_PROCESS["switch_wl"] == 500.0,
        "T_conv(8)=%.6e ns · rate(4)=%.4f MSa/s" % (tconv8 * 1e9, sps4 / 1e6))

    # ⑪ 跨模块交叉：mux R_on 与 E18 `cdac_settle_tau` 同器件；kT/C 地板复用 E18
    chk("⑪ 跨模块交叉：mux R_on ⟷ E18 `cdac_settle_tau` 同器件（6.41 Ω）· kT/C 地板 ⟷ E18 `thermal_noise_rms_v`",
        abs(mux_settling_tau(8)["r_on_ohm"] - T.cdac_settle_tau(8)["r_on_ohm"]) < 1e-15
        and abs(CS.thermal_noise_rms_v(1.0e-12) - math.sqrt(KB * 300.0 / 1.0e-12)) < 1e-24,
        "R_on=%.6f Ω" % mux_settling_tau(8)["r_on_ohm"])

    # ⑫ 🔴 诚实披露含「不报 TOPS」「可校准」「非 PDK」「确定性 pedestal」
    chk("⑫ 🔴 诚实披露：含「不报 TOPS」「确定性 pedestal 可校准」「非 PDK」",
        ("不报 TOPS" in COL_SHARE_DYN_DISCLOSURE["no_power"])
        and ("可单点失调校准消除" in COL_SHARE_DYN_DISCLOSURE["charge_injection"]
             or "校准" in COL_SHARE_DYN_DISCLOSURE["charge_injection"])
        and ("非 PDK" in COL_SHARE_DYN_DISCLOSURE["area_model"]),
        "披露 %d 键" % len(COL_SHARE_DYN_DISCLOSURE))

    # ⑬ 汇总报告可跑且返回 is_oracle=False
    rep = dynamic_cost_report(64, 64, 8)
    chk("⑬ 汇总报告 `dynamic_cost_report` 可跑 · 三项动态代价齐备 · is_oracle=False",
        isinstance(rep, dict) and rep["is_oracle"] is False
        and "charge_injection" in rep and "aperture_jitter" in rep and "mux_settling" in rep
        and len(rep["mux_settling"]["erosion_table"]) >= 9,
        "结论键=%d" % len(rep["conclusion"]))

    if verbose:
        print("\n" + ("ALL PASS" if res else "SOME FAILED") + " · col_share_dynamic_self_check")
    return res


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(0 if col_share_dynamic_self_check(verbose=True) else 1)
