# -*- coding: utf-8 -*-
"""EIC 行为级模型（P6 · T6.4 · U11）· per-MZI 驱动 + TIA 阵列。

背景：`lda_design/cpo_engines.py:33` 把 **EIC/驱动器/激光器按黑箱**（"有源不物理级建模，
负面清单"）。本模块把 EIC 从**黑箱**推进到**行为级** —— 只建**一阶 RC 驱动**与**单极点 TIA**
的时域/频域响应，用于驱动**上升沿预算**与**接收带宽预算**。

🔴 诚实边界（禁止事后补票）：
  · **只到行为级**：一阶 RC 充放电 + 单极点跨阻；**不碰晶体管级**
    （DAC/ADC/SerDes/DSP/BER 全部在红线外，见计划 §8「不做清单」）。
  · 参数（τ / R_f / C_f / VπL）是**设计预算常数**，**不是实测值**；本模块**没有实测锚**
    ⇒ 结论只可用于**预算与斜率**，**不得**作性能宣称。
  · 🔴 **零能效数字**：不输出 pJ/bit、不输出驱动功耗 —— 沿用 `cpo_engines.py:26`
    与 `golden_product_benchmarks.py:941` 的既有拒绝（电域主导、LDA 无电域锚，
    拿光域量去比会低数个数量级导致恒过）。本模块只给**电压 / 相位 / 时延 / 带宽**。
  · 线性 ODE 的 RK4 收敛阶 O(h⁴) 是**数值格式**属性，**不是器件物理**；不得据此宣称器件精度。
  · 无噪声、无非线性、无温度、无失配 ⇒ **不含**任何保真度/BER 结论。

复用（不重复造已证数学）：`lda_l2.loss_aware_compile.RAIL_PITCH_DEFAULT` 等同族常数族；
`VπL` 口径与 `mesh_pnr.build_mesh_pnr(vpi_l_v_mm=...)`、`wdm_shared_mesh_pnr` 同源（7.5 V·mm 默认）。
"""
from __future__ import annotations

import math
from typing import Any, Dict

# ---------------------------------------------------------------------------
# 设计预算常数（**非实测**；改这些值即改预算，不构成能力宣称）
# ---------------------------------------------------------------------------
TAU_DRIVER_S_DEFAULT = 20e-12        # 驱动器一阶时间常数 τ（20 ps）
V_DD_DEFAULT = 2.0                   # 驱动满摆幅（V）
VPI_L_V_MM_DEFAULT = 7.5             # Vπ·L（V·mm）—— 与 mesh_pnr / wdm_shared_mesh_pnr 默认同源
PS_ARM_UM_DEFAULT = 1000.0           # 相移臂长（µm）
R_F_OHM_DEFAULT = 2.0e3              # TIA 反馈电阻（Ω）
C_F_F_DEFAULT = 20e-15               # TIA 反馈电容（F）
DAC_BITS_DEFAULT = 6                 # 驱动 DAC 位深（相位量化档）

EIC_DISCLOSURE: Dict[str, str] = {
    "level": "只到**行为级**（一阶 RC 驱动 + 单极点 TIA）；**不碰晶体管级**（DAC/ADC/SerDes/DSP/BER 全在红线外）。",
    "params_are_budget": "τ / V_dd / VπL / R_f / C_f / DAC 位深均为**设计预算常数**，**非实测**；本模块**无实测锚**。",
    "not_energy": "🔴 **零能效数字**：不输出 pJ/bit、不输出驱动功耗（沿用 cpo_engines:26 / "
                  "golden_product_benchmarks:941 的既有拒绝 —— 电域主导、LDA 无电域锚）。"
                  "本模块只给**电压 / 相位 / 时延 / 带宽**。",
    "order_is_numeric": "线性 ODE 的 RK4 收敛阶 O(h⁴) 是**数值格式**属性，**不是器件物理**；不得据此宣称器件精度。",
    "no_noise": "无噪声 / 无非线性 / 无温度 / 无失配 ⇒ **不含**任何保真度或 BER 结论。",
    "use": "结论仅可用于**驱动上升沿预算**与**接收带宽预算**；对外引用须同时引用本披露。",
    "vpi_source": "VπL 默认 7.5 V·mm，与 `build_mesh_pnr(vpi_l_v_mm=...)` / "
                  "`build_wdm_shared_mesh_pnr` 同源（口径一致，非新常量）。",
}


class EicBehavioralError(Exception):
    """本模块的输入/不变量违规。"""


# ---------------------------------------------------------------------------
# 1) per-MZI 驱动器：一阶 RC 阶跃响应（闭式 ↔ 数值积分）
# ---------------------------------------------------------------------------
def driver_step_closed_form(t_s: float, tau_s: float = TAU_DRIVER_S_DEFAULT,
                            v_dd: float = V_DD_DEFAULT) -> float:
    """闭式：v(t) = V_dd·(1 − e^{−t/τ})（零初值一阶 RC 充电）。"""
    if tau_s <= 0.0:
        raise EicBehavioralError("tau_s=%.6g 非法（须 > 0）" % tau_s)
    if t_s < 0.0:
        raise EicBehavioralError("t_s=%.6g 非法（须 >= 0）" % t_s)
    return float(v_dd * (1.0 - math.exp(-t_s / tau_s)))


def driver_step_rk4(t_s: float, tau_s: float = TAU_DRIVER_S_DEFAULT,
                    v_dd: float = V_DD_DEFAULT, n_steps: int = 256) -> float:
    """数值积分 ODE `dv/dt = (V_dd − v)/τ`，**经典 RK4**，n_steps 步（自 v(0)=0）。

    **候选实现**（与闭式不同源）：不解析求解，只用四阶 Runge–Kutta 推进。
    残差 = RK4 截断误差 O(h⁴)。
    """
    if tau_s <= 0.0:
        raise EicBehavioralError("tau_s=%.6g 非法（须 > 0）" % tau_s)
    if t_s < 0.0:
        raise EicBehavioralError("t_s=%.6g 非法（须 >= 0）" % t_s)
    if not isinstance(n_steps, int) or n_steps < 1:
        raise EicBehavioralError("n_steps=%r 非法（须为 >=1 的 int）" % (n_steps,))

    def f(v: float) -> float:
        return (v_dd - v) / tau_s

    h = t_s / n_steps
    v = 0.0
    for _ in range(n_steps):
        k1 = f(v)
        k2 = f(v + 0.5 * h * k1)
        k3 = f(v + 0.5 * h * k2)
        k4 = f(v + h * k3)
        v += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(v)


# ---------------------------------------------------------------------------
# 2) 电压 → 相位（VπL 口径与 mesh_pnr 同源）
# ---------------------------------------------------------------------------
def vpi_from_vpi_l(vpi_l_v_mm: float = VPI_L_V_MM_DEFAULT,
                   arm_um: float = PS_ARM_UM_DEFAULT) -> float:
    """由 Vπ·L（V·mm）与臂长（µm）算 Vπ（V）：Vπ = VπL / L_mm，L_mm = arm_um/1000。"""
    if vpi_l_v_mm <= 0.0:
        raise EicBehavioralError("vpi_l_v_mm=%.6g 非法（须 > 0）" % vpi_l_v_mm)
    if arm_um <= 0.0:
        raise EicBehavioralError("arm_um=%.6g 非法（须 > 0）" % arm_um)
    return float(vpi_l_v_mm / (arm_um / 1000.0))


def mzi_phase_from_voltage(v: float, vpi_l_v_mm: float = VPI_L_V_MM_DEFAULT,
                           arm_um: float = PS_ARM_UM_DEFAULT) -> float:
    """推挽 MZI 相位（rad）：φ = π·v / Vπ（Vπ 由 `vpi_from_vpi_l` 给出）。"""
    return float(math.pi * float(v) / vpi_from_vpi_l(vpi_l_v_mm, arm_um))


def phase_resolution_rad(dac_bits: int = DAC_BITS_DEFAULT,
                         v_dd: float = V_DD_DEFAULT,
                         vpi_l_v_mm: float = VPI_L_V_MM_DEFAULT,
                         arm_um: float = PS_ARM_UM_DEFAULT) -> float:
    """驱动 DAC 量化下的**最小相位步进**（rad/步）：Δφ = π·(V_dd/2^bits)/Vπ。"""
    if not isinstance(dac_bits, int) or dac_bits < 1:
        raise EicBehavioralError("dac_bits=%r 非法（须为 >=1 的 int）" % (dac_bits,))
    v_step = float(v_dd) / float(2 ** dac_bits)
    return float(abs(mzi_phase_from_voltage(v_step, vpi_l_v_mm, arm_um)))


# ---------------------------------------------------------------------------
# 3) TIA 阵列：单极点跨阻（行为级频响）
# ---------------------------------------------------------------------------
def tia_transimpedance_ohm(f_hz: float, r_f_ohm: float = R_F_OHM_DEFAULT,
                           c_f_f: float = C_F_F_DEFAULT) -> complex:
    """单极点 TIA 跨阻 Z(f) = R_f / (1 + j·2πf·R_f·C_f)（行为级，无噪声）。"""
    if r_f_ohm <= 0.0 or c_f_f <= 0.0:
        raise EicBehavioralError("r_f_ohm/c_f_f 非法（须 > 0）")
    if f_hz < 0.0:
        raise EicBehavioralError("f_hz=%.6g 非法（须 >= 0）" % f_hz)
    return complex(r_f_ohm) / complex(1.0, 2.0 * math.pi * f_hz * r_f_ohm * c_f_f)


def tia_bandwidth_hz(r_f_ohm: float = R_F_OHM_DEFAULT,
                     c_f_f: float = C_F_F_DEFAULT) -> float:
    """单极点 −3 dB 带宽 f_3dB = 1/(2π R_f C_f)。"""
    if r_f_ohm <= 0.0 or c_f_f <= 0.0:
        raise EicBehavioralError("r_f_ohm/c_f_f 非法（须 > 0）")
    return float(1.0 / (2.0 * math.pi * r_f_ohm * c_f_f))


# ---------------------------------------------------------------------------
# 4) 行为级预算（**零能效数字**，只给电压/相位/时延/带宽）
# ---------------------------------------------------------------------------
def eic_budget(n_mzi: int, tau_s: float = TAU_DRIVER_S_DEFAULT,
               v_dd: float = V_DD_DEFAULT, dac_bits: int = DAC_BITS_DEFAULT,
               vpi_l_v_mm: float = VPI_L_V_MM_DEFAULT,
               arm_um: float = PS_ARM_UM_DEFAULT,
               r_f_ohm: float = R_F_OHM_DEFAULT, c_f_f: float = C_F_F_DEFAULT,
               rise_frac: float = 0.9, n_steps: int = 256) -> Dict[str, Any]:
    """per-MZI 驱动 + TIA 阵列的**行为级**预算。

    · `rise_time_s`：驱动到达 `rise_frac`·V_dd 的 10%→90% 型时延 —— **数值积分**给出（RK4），
      与闭式解同场对照（残差 = 数值截断误差，见 smoke）。
    · `phase_full_swing_rad` / `phase_resolution_rad`：满摆幅相位与 DAC 量化步进。
    · `tia_bandwidth_hz`：单极点 −3 dB 带宽。
    🔴 **不含**任何功耗/能效量（见 `EIC_DISCLOSURE['not_energy']`）。
    """
    if not isinstance(n_mzi, int) or n_mzi < 1:
        raise EicBehavioralError("n_mzi=%r 非法（须为 >=1 的 int）" % (n_mzi,))
    if not (0.0 < rise_frac < 1.0):
        raise EicBehavioralError("rise_frac=%.6g 非法（须 ∈ (0,1)）" % rise_frac)

    # 到达 rise_frac·V_dd 的时刻（闭式）（起于 0，故 0→rise_frac 的「上升时延」）
    t_closed = -tau_s * math.log(1.0 - rise_frac)

    # 数值求 t：在 [0, 4τ] 上按 n_steps 细扫，取 RK4 首次越过阈值的时刻（线性插值细化）
    thr = rise_frac * v_dd
    t_rk = None
    n_scan = max(int(n_steps), 2)
    dt = 4.0 * tau_s / n_scan
    t_prev, v_prev = 0.0, 0.0
    for i in range(1, n_scan + 1):
        t_i = i * dt
        v_i = driver_step_rk4(t_i, tau_s=tau_s, v_dd=v_dd, n_steps=max(1, i))
        if v_i >= thr:
            if v_i > v_prev:
                t_rk = t_prev + (thr - v_prev) / (v_i - v_prev) * (t_i - t_prev)
            else:
                t_rk = t_i
            break
        t_prev, v_prev = t_i, v_i

    out = {
        "n_mzi": n_mzi,
        "n_tia": n_mzi,
        "tau_s": float(tau_s),
        "v_dd": float(v_dd),
        "vpi_v": vpi_from_vpi_l(vpi_l_v_mm, arm_um),
        "phase_full_swing_rad": float(mzi_phase_from_voltage(v_dd, vpi_l_v_mm, arm_um)),
        "phase_resolution_rad": phase_resolution_rad(dac_bits, v_dd, vpi_l_v_mm, arm_um),
        "rise_time_closed_form_s": float(t_closed),
        "rise_time_rk4_s": (float(t_rk) if t_rk is not None else None),
        "rise_frac": float(rise_frac),
        "tia_bandwidth_hz": tia_bandwidth_hz(r_f_ohm, c_f_f),
        "dac_bits": int(dac_bits),
        "disclosure_keys": sorted(EIC_DISCLOSURE.keys()),
    }
    assert_no_energy_metrics(out)
    return out


# ---------------------------------------------------------------------------
# 5) 能效越界守卫 —— **单一真值来源**
# ---------------------------------------------------------------------------
# 🔴 不在本模块复制一份：`optical_pareto` 已实现同一准入条件（键名扫描 + 令牌表）。
#    U10 血案：「同一准入条件不得两处各写一份」—— 两处各写会让突变探针**抓不住**
#    （只改其中一处 ⇒ 仍全绿）。故此处**import 复用**，保持单一来源。
from lda_l2.optical_pareto import assert_no_energy_metrics  # noqa: E402  (单一真值来源)


if __name__ == "__main__":
    print("=== EIC 行为级自检 ===")
    for n in (16, 256, 1024, 4096):
        cf = driver_step_closed_form(4e-11)
        rk = driver_step_rk4(4e-11, n_steps=n)
        print("  N=%-5d v(4τ): closed=%.15f  rk4=%.15f  |Δ|=%.3e" % (n, cf, rk, abs(cf - rk)))
    b = eic_budget(64)
    for k in ("vpi_v", "phase_full_swing_rad", "phase_resolution_rad",
              "rise_time_closed_form_s", "rise_time_rk4_s", "tia_bandwidth_hz"):
        print("  %-26s %s" % (k, b[k]))
