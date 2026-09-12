"""LDA · T1-C-W5 探测器带宽 **B 档真求解**（经 T1 电学内核）· C 级自主。

🔴 主权边界（T1 分层解锁 · 研发规划 §3 T1-C-W5/W6）：
- 本模块为 T1-C-W5 交付物：**探测器 3dB 带宽的真物理求解**——在 B33 闭式
  （RC 限制 f=1/(2πRC)，A 档行为层）之上，补上 **渡越时间限制**（B 档真物理）：
  用 T1 电学内核（`drift_diffusion_1d` 自洽泊松-玻尔兹曼）解出的**真实耗尽区场
  剖面 E(x)**，对光生载流子做**逐时步漂移输运**（含速度饱和 v(E)=v_sat·(E/Es)/
  (1+E/Es)），感应电流按 Ramo-Shockley i(t)=Σv(x_k)/W，FFT 得真实渡越频率响应，
  再与 RC 一阶低通级联 ⇒ 真实 3dB 带宽 f_total ≤ f_rc。
- **零外部依赖**（仅 numpy）；**不 import 任何 A 级美系商业求解器 / DEVSIM**。
- 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 f_total / f_tr 仅为**候选**，
  判决由物理定律闭式（Sze/Lucovsky 渡越闭式 0.44·v_sat/W、B33 RC 闭式）/
  文献定。`T1_OUTPUT_IS_ORACLE=False` 铁律；`guard_t1_not_oracle()` 反向守卫。
- 🔴 **EAR 744.23 成熟节点用途声明**：仅用于成熟节点 / 非先进用途器件设计仿真。

物理（Sze《Physics of Semiconductor Devices》§13 光电探测器带宽；Lucovsky 1964）：
- 探测器带宽由 **RC 时间常数** 与 **载流子渡越时间** 共同限制：
    f_rc = 1/(2π R C)，C = ε·A/W（W=耗尽宽度，反偏结电容）；
    f_tr = 渡越时间限制 3dB（均匀饱和速度下闭式 f ≈ 0.44·v_sat/W）。
- 真实器件：两机制级联 ⇒ f_total = |H_tr(f)·H_rc(f)| 的 3dB 点 ≤ min(f_rc, f_tr)。

与闭式 golden 的方法学独立性：
- golden = 闭式（RC 解析 + 均匀饱和速度渡越解析 0.44·v_sat/W，假定载流子全程饱和）；
- cand   = 数值（真实场剖面 v(E(x)) 逐时步漂移 + FFT 频响，**允许亚饱和**）。
⇒ cand ≤ golden（亚饱和使载流子更慢 ⇒ 渡越更慢 ⇒ 带宽更低），比值随场强单调升向 1。

诚实边界：
- 单载流子型（电子）渡越，不含空穴双载流子分布 / 雪崩倍增 / 暗电流 / 过剩噪声
  （雪崩动力学与增益介质仍属禁区）。provenance 标 `self_authored_t1c_w5_true_solve`。
- 场剖面来自 1D T1 电学内核（同一物理族；2D 扩面见 T1-B-W4）。半导体输运参数
  （μ_n、v_sat）为**公开文献值**，非拟合，非 foundry 专有。
LLM 不进判决路径。
"""
from __future__ import annotations

import math

import numpy as np

try:  # 包内导入（smoke / 生产路径）
    from .drift_diffusion_1d import (
        solve_pn_junction_1d,
        Q_E,
        EPS_SI,
        V_T,
        N_I,
        N_A_DEFAULT,
        N_D_DEFAULT,
    )
except ImportError:  # 允许 `python lda_solver/detector_bandwidth_true.py` 直接自检
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from lda_solver.drift_diffusion_1d import (  # type: ignore
        solve_pn_junction_1d,
        Q_E,
        EPS_SI,
        V_T,
        N_I,
        N_A_DEFAULT,
        N_D_DEFAULT,
    )

# 🔴 红线开关：T1 输出永不作 ORACLE
T1_OUTPUT_IS_ORACLE = False

# ---- 输运常数（Si，公开文献值，非拟合） ----
MU_N_SI = 0.135          # 电子迁移率 (m^2/V/s, ~1350 cm^2/Vs)
V_SAT_E_SI = 1.0e5       # 电子饱和漂移速度 (m/s, Si ~1.0e5，文献值)
TRANSIT_COEFF = 0.44     # 均匀饱和速度渡越 3dB 系数（Sze/Lucovsky textbook）
# 频响 FFT 补零长度：渡越窗 ~4·τ_sat（~1e-11 s）对应的原始频率步 ~ 数十 GHz，
# 不足以分辨 RC 拐点（~GHz）⇒ 零填充到长窗，得细频率栅格（步 ~0.3 GHz）再求级联 3dB。
FFT_N_DEFAULT = 1 << 17

# ---- 探测器默认几何（B33 同源电容参数 + 高速小面积） ----
R_LOAD_DEFAULT = 50.0          # 负载电阻 (Ω)
EPS_CAP_DEFAULT = 1.036e-10    # 半导体介电 ε（B33 同源，F/m）
A_DET_DEFAULT = 1.0e-9         # 探测器面积 (m^2, ~32µm×32µm 高速器件)


# ============================================================
# 1) T1 电学内核 → 耗尽区真实场剖面 E(x)
# ============================================================
def t1_depletion_field(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                       Lx: float = 8.0e-6, n_grid: int = 1200,
                       field_frac: float = 0.05) -> dict:
    """用 T1 电学内核（1D 自洽泊松-玻尔兹曼）解出耗尽区电场剖面 E(x)。

    耗尽区边界由数值场阈值 |E| ≥ field_frac·E_max **稳健提取**（不依赖易失效的
    `N_D/e` 阈值——后者在宽耗尽 / p-i-n 型剖面下会给出 inf）。

    返回 dict：x_dep / E_dep（耗尽区内坐标 + 有符号电场）/ W / x_p / x_n /
              E_max / V_bi / N_A / N_D / provenance / is_oracle(False) / converged。
    """
    if N_A <= 0 or N_D <= 0 or Lx <= 0 or n_grid < 50:
        raise ValueError("t1_depletion_field: 非法参数（N_A/N_D>0, Lx>0, n_grid≥50）")
    sol = solve_pn_junction_1d(N_A=N_A, N_D=N_D, L=Lx, n_grid=n_grid)
    x = sol["x"]
    E = -np.gradient(sol["phi"], sol["dx"])      # 有符号电场 E_x = −dφ/dx
    Eabs = np.abs(E)
    E_max = float(Eabs.max())
    if E_max <= 0.0:
        raise RuntimeError("t1_depletion_field: 峰值电场 ≤ 0（求解异常）")
    idx = np.where(Eabs >= field_frac * E_max)[0]
    if len(idx) < 2:
        raise RuntimeError("t1_depletion_field: 无超过阈值的耗尽区（ doping 越界）")
    i0, i1 = idx[0], idx[-1]
    x_dep = x[i0:i1 + 1].copy()
    E_dep = E[i0:i1 + 1].copy()
    W = float(x_dep[-1] - x_dep[0])
    return {
        "x_dep": x_dep, "E_dep": E_dep, "W": W,
        "x_p": float(x_dep[0]), "x_n": float(x_dep[-1]),
        "E_max": E_max, "V_bi": float(sol["V_bi"]),
        "N_A": float(N_A), "N_D": float(N_D),
        "provenance": "t1_electrical_kernel_1d_field",
        "is_oracle": False, "converged": bool(sol["converged"]),
    }


# ============================================================
# 2) 速度饱和模型 + 数值渡越冲激响应（Ramo-Shockley）
# ============================================================
def velocity_saturation(E: np.ndarray, mu: float = MU_N_SI,
                        v_sat: float = V_SAT_E_SI) -> np.ndarray:
    """速度饱和模型 v(E) = v_sat·(E/E_s)/(1+E/E_s)，E_s=v_sat/μ（Caughey-Thomas 单参）。

    低场 v→μE（线性）；高场 v→v_sat（饱和）。确定性物理，不引入拟合。
    """
    E = np.asarray(E, dtype=float)
    Es = v_sat / mu
    a = np.abs(E) / Es
    return v_sat * a / (1.0 + a)


def transit_impulse_response(x_dep: np.ndarray, E_dep: np.ndarray,
                             mu: float = MU_N_SI, v_sat: float = V_SAT_E_SI,
                             n_carriers: int = 2000, n_t: int = 600) -> tuple:
    """数值渡越冲激响应（Ramo-Shockley，平面探测器）。

    物理：t=0 在耗尽区 [x_p, x_n] 内**均匀**光生 n_carriers 个电子（δ 光脉冲），
    每个以 v(E(x)) 漂移；平面均匀场下位置 x 的载流子感应电流 i_k = q·v(x_k)/W
    ⇒ 归一化总电流 i(t) = Σ_{仍在区内} v(x_k)/W。返回 (t, i)。

    ⚠️ 失败即抛异常上浮，绝不静默回退。
    """
    if n_carriers < 2 or n_t < 8:
        raise ValueError("transit_impulse_response: n_carriers≥2 且 n_t≥8")
    order = np.argsort(x_dep)
    xd = np.asarray(x_dep, float)[order]
    vd = velocity_saturation(np.asarray(E_dep, float)[order], mu, v_sat)
    x_p, x_n = float(xd[0]), float(xd[-1])
    W = x_n - x_p
    if W <= 0.0:
        raise ValueError("transit_impulse_response: 耗尽宽度 ≤ 0")
    pos = np.linspace(x_p, x_n, n_carriers)
    tau_sat = W / v_sat                      # 饱和速度渡越时间（时间尺度）
    T = 4.0 * tau_sat
    dt = T / n_t
    i = np.zeros(n_t)
    alive = np.ones(n_carriers, dtype=bool)
    for k in range(n_t):
        vv = np.interp(pos, xd, vd, left=vd[0], right=0.0)
        vv = np.where(alive, vv, 0.0)
        i[k] = float(np.sum(vv)) / W
        pos = pos + vv * dt
        alive = alive & (pos < x_n)
        if not alive.any():
            break
    t = (np.arange(1, n_t + 1)) * dt
    return t, i


def _frequency_response(t: np.ndarray, i: np.ndarray,
                        n_fft: int | None = None) -> tuple:
    """由时域冲激响应 i(t) → 归一化幅频 |H(f)|（f=0 归一为 1）。

    关键：i(t) 物理窗很短（载流子渡越完即 0），直接 FFT 的频率步太粗（~数十 GHz），
    无法分辨 RC 拐点（~GHz）。故**零填充**到长窗（n_fft），得细频率栅格后再求级联 3dB。
    """
    n = len(i)
    dt = float(t[1] - t[0])
    i_ = np.asarray(i, dtype=float)
    if n_fft is not None and n_fft > n:
        i_ = np.concatenate([i_, np.zeros(n_fft - n, dtype=float)])
        n = n_fft
    mag = np.abs(np.fft.rfft(i_))
    freqs = np.fft.rfftfreq(n, d=dt)
    if mag[0] <= 0.0:
        mag = mag.copy()
        mag[0] = 1e-300
    return freqs, mag / mag[0]


def _find_3db(freqs: np.ndarray, mag: np.ndarray,
              target: float | None = None) -> float:
    """线性插值求 |H(f)| 首次跌破 −3dB（mag=1/√2）的频率。"""
    if target is None:
        target = 1.0 / math.sqrt(2.0)
    idx = np.where(mag < target)[0]
    if len(idx) == 0:
        return float(freqs[-1])
    j = int(idx[0])
    if j == 0:
        return float(freqs[0])
    f0, f1 = float(freqs[j - 1]), float(freqs[j])
    m0, m1 = float(mag[j - 1]), float(mag[j])
    if m1 == m0:
        return f1
    return f0 + (target - m0) * (f1 - f0) / (m1 - m0)


def transit_bandwidth_numeric(x_dep: np.ndarray, E_dep: np.ndarray,
                              mu: float = MU_N_SI, v_sat: float = V_SAT_E_SI,
                              n_carriers: int = 2000, n_t: int = 600,
                              n_fft: int = FFT_N_DEFAULT) -> float:
    """数值渡越时间限制 3dB 带宽 f_tr（Hz）——真实场剖面 v(E(x)) 逐时步漂移的频响 3dB。"""
    t, i = transit_impulse_response(x_dep, E_dep, mu, v_sat, n_carriers, n_t)
    freqs, mag = _frequency_response(t, i, n_fft)
    return float(_find_3db(freqs, mag))


# ============================================================
# 3) 闭式 golden（RC + 均匀饱和速度渡越）+ 真求解主函数
# ============================================================
def transit_bandwidth_closed_form(W: float, v_sat: float = V_SAT_E_SI) -> float:
    """golden 闭式（design_rule_anchor）：均匀**饱和速度**渡越 3dB f = 0.44·v_sat/W。

    Sze/Lucovsky 教科书结果（载流子全程以 v_sat 漂移，均匀光生）。为**上界**：
    真实场剖面在边缘低场区亚饱和 ⇒ 数值 f_tr ≤ 本闭式。
    """
    if W <= 0.0 or v_sat <= 0.0:
        raise ValueError("transit_bandwidth_closed_form: W>0 且 v_sat>0")
    return TRANSIT_COEFF * v_sat / W


def rc_bandwidth(R: float = R_LOAD_DEFAULT, eps: float = EPS_CAP_DEFAULT,
                 A: float = A_DET_DEFAULT, W: float = 1.0e-6) -> float:
    """RC 限制 3dB 带宽 f_rc = 1/(2π·R·C)，C = ε·A/W（W=耗尽宽度）。"""
    if R <= 0.0 or eps <= 0.0 or A <= 0.0 or W <= 0.0:
        raise ValueError("rc_bandwidth: R/eps/A/W 均须 > 0")
    C = eps * A / W
    return 1.0 / (2.0 * math.pi * R * C)


def detector_bandwidth_true_solve(R: float = R_LOAD_DEFAULT,
                                  eps: float = EPS_CAP_DEFAULT,
                                  A: float = A_DET_DEFAULT,
                                  N_A: float = N_A_DEFAULT,
                                  N_D: float = N_D_DEFAULT,
                                  Lx: float = 8.0e-6, n_grid: int = 1200,
                                  mu: float = MU_N_SI, v_sat: float = V_SAT_E_SI,
                                  n_carriers: int = 2000, n_t: int = 600,
                                  n_fft: int = FFT_N_DEFAULT) -> dict:
    """T1-C-W5 探测器 3dB 带宽 **B 档真求解**（RC + 渡越，经 T1 电学内核）。

    步骤：T1 内核解场剖面 → W、E(x) → 数值渡越 f_tr（FFT 频响）→ 与 RC 一阶低通
    **级联** |H(f)|=|H_tr(f)|·|H_rc(f)| 求真实 3dB（非简单 1/f² 近似）。

    返回 dict（prov＝候选，is_oracle=False）：
      f_total / f_rc / f_tr / f_tr_closed / W / E_max / penalty_pct / ratio_tr ...
    🔴 红线：输出仅候选，判决由闭式 golden 定。
    """
    fld = t1_depletion_field(N_A, N_D, Lx, n_grid)
    W = fld["W"]
    x_dep, E_dep = fld["x_dep"], fld["E_dep"]

    # 数值渡越频响
    t, i = transit_impulse_response(x_dep, E_dep, mu, v_sat, n_carriers, n_t)
    freqs, mag_tr = _frequency_response(t, i, n_fft)
    f_tr = float(_find_3db(freqs, mag_tr))

    # RC 一阶低通幅频
    f_rc = rc_bandwidth(R, eps, A, W)
    tau_rc = 1.0 / (2.0 * math.pi * f_rc)
    mag_rc = 1.0 / np.sqrt(1.0 + (2.0 * math.pi * freqs * tau_rc) ** 2)
    f_total = float(_find_3db(freqs, mag_tr * mag_rc))

    f_tr_cf = transit_bandwidth_closed_form(W, v_sat)
    penalty = (f_rc - f_total) / f_rc if f_rc > 0 else 0.0
    return {
        "metric": "f3dB_Hz_true_solve",
        "f_total": f_total,
        "f_rc": f_rc,
        "f_tr": f_tr,
        "f_tr_closed": f_tr_cf,
        "ratio_tr": f_tr / f_tr_cf if f_tr_cf > 0 else float("nan"),
        "penalty_pct": penalty * 100.0,
        "W": W, "E_max": fld["E_max"], "V_bi": fld["V_bi"],
        "N_A": float(N_A), "N_D": float(N_D),
        "mu": mu, "v_sat": v_sat, "R": R, "eps": eps, "A": A,
        "provenance": "self_authored_t1c_w5_true_solve",
        "is_oracle": False,
    }


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫（同 W2/W4 语义）。"""
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 f_total/f_tr 仅作候选，"
            "死标量判决须由物理定律闭式/文献/foundry 实测定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    print("=== T1-C-W5 探测器带宽真求解（经 T1 电学内核） ===")
    print(f"{'N_D':>10} {'W(nm)':>9} {'E_max':>8} {'f_tr_cf':>10} {'f_tr_num':>11} "
          f"{'ratio':>7} {'f_rc(GHz)':>10} {'f_tot(GHz)':>11} {'penalty%':>9}")
    for N_D in (1e22, 1e21, 5e20, 3e20):
        r = detector_bandwidth_true_solve(N_D=N_D)
        print(f"{N_D:>10.1e} {r['W']*1e9:>9.1f} {r['E_max']/1e5:>8.1f} "
              f"{r['f_tr_closed']/1e9:>10.3f} {r['f_tr']/1e9:>11.3f} "
              f"{r['ratio_tr']:>7.3f} {r['f_rc']/1e9:>10.3f} "
              f"{r['f_total']/1e9:>11.3f} {r['penalty_pct']:>9.2f}")
    guard_t1_not_oracle(detector_bandwidth_true_solve())
    print("=== T1 不作 ORACLE 守卫：正常通过 ===")
