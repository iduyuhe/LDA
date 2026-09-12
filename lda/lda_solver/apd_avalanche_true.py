"""LDA · T1-C-W6 APD 雪崩载流子输运 **B 档真求解**（经 T1 电学内核）· C 级自主。

🔴 主权边界（T1 分层解锁 · 研发规划 §3 T1-C-W5/W6 · 锚题契约评审 §B33 裁定）：
- 本模块为 T1-C-W6 交付物：契约评审 §B33 明文「APD 雪崩载流子输运真求解（碰撞
  电离率积分、载流子倍增、过剩噪声系数真算）属 T1-B 内核可做项，留待第3阶段
  W5/W6（经 T1-B）」——本模块即该项落地。
- 物理：反偏耗尽区三角场 E(x)（Sze 闭式 W(V)，与 T1-B 电学内核同源）上，
  ① **确定性电离积分**（精确 1D 局部模型，e 注入）：
      M = 2 / (1 + e^{−2D_W} − 2∫s·e^{−2D}dx)，D(x)=∫₀ˣd，d=(αe−αh)/2，s=(αe+αh)/2
     两个解析极限机器精度可退化为 e^{∫αdx}（αh=0）与 1/(1−αW)（αe=αp）。
  ② **固定种子蒙特卡洛雪崩链**（母载流子存活 + 每次电离产生一个新 e-h 对，
     网格累积危险率反演采样自由程）：M = ⟨N⟩、F = ⟨N²⟩/⟨N⟩²（N=1+E）。
- **零外部依赖**（仅 numpy + 标准库 random）；不 import 任何 A 级/DEVSIM。
- 🔴 **T1 输出不作 ORACLE（红线）**：M(V)/V_br/F 仅为**候选**，判决由物理
  定律闭式（Miller M=1/(1−V/V_br)^n / McIntyre F=k·M+(2−1/M)(1−k)）/ 文献定。
  `T1_OUTPUT_IS_ORACLE=False` 铁律；`guard_t1_not_oracle()` 反向守卫。
- 🔴 **EAR 744.23 成熟节点用途声明**：仅成熟节点 / 非先进用途器件设计仿真。

电离系数（Si，van Overstraeten–de Man 1970，公开文献值，cm→SI 换算，非拟合）：
    α_e = 7.03e7·exp(−1.231e8/E)  (1/m)
    α_h = 1.582e8·exp(−2.036e8/E) (1/m)，E 以 V/m；有效域 E≥1.75e7 V/m 截断。

诚实边界（误差公开）：
- 局部模型（无死区/非局域效应）⇒ M(V) 随偏压的陡度低于实测：本模块在自身 V_br
  上的 Miller 等效指数 n_eff≈0.7–0.9，**低于文献 Miller 带 n≈1.5–4**——这是
  局部模型已知局限（死区效应使实测更陡），如实标注不作 ORACLE。
- 无温度依赖 / 无隧穿分量 / 无载流子存储效应；雪崩自持判断用 M=50 阈值约定。
LLM 不进判决路径。
"""
from __future__ import annotations

import math
import random

import numpy as np

try:  # 包内导入
    from .drift_diffusion_1d import Q_E, EPS_SI, V_T, N_I, N_A_DEFAULT, N_D_DEFAULT
except ImportError:  # 脚本直跑自检
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from lda_solver.drift_diffusion_1d import (  # type: ignore
        Q_E, EPS_SI, V_T, N_I, N_A_DEFAULT, N_D_DEFAULT)

# 🔴 红线开关
T1_OUTPUT_IS_ORACLE = False

# ---- Si 电离系数（van Overstraeten–de Man，文献值，cm→SI）----
A_E, B_E = 7.03e7, 1.231e8     # 电子 (1/m, V/m)
A_H, B_H = 1.582e8, 2.036e8    # 空穴
E_VALID_MIN = 1.75e7           # 有效域下限 (V/m, =1.75e5 V/cm)

M_BREAKDOWN_THRESHOLD = 50.0   # V_br 约定：M=50
N_X_DEFAULT = 600


def alpha_electron(E: float) -> float:
    """电子碰撞电离系数 α_e(E)（1/m，van Overstraeten–de Man，E∈V/m）。"""
    return A_E * math.exp(-B_E / max(E, E_VALID_MIN))


def alpha_hole(E: float) -> float:
    """空穴碰撞电离系数 α_h(E)（1/m）。"""
    return A_H * math.exp(-B_H / max(E, E_VALID_MIN))


def avalanche_profiles(V: float, N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                       n_x: int = N_X_DEFAULT) -> dict:
    """反偏耗尽区三角场 + 电离系数剖面（候选层，golden 耗尽闭式同 T1-B）。

    W(V)=√(2ε(V_bi+V)/q·(N_A+N_D)/(N_A·N_D))（Sze 突变结，与 T1-B 电学内核
    同源闭式）；E(x)=E_max·(1−x/W)，E_max=2·(V_bi+V)/W（三角面积=电压）。
    """
    if V < 0.0:
        raise ValueError("avalanche_profiles: 需反偏 V≥0")
    V_bi = V_T * math.log(N_A * N_D / (N_I * N_I))
    V_tot = V_bi + V
    W = math.sqrt(2.0 * EPS_SI * V_tot / Q_E * (N_A + N_D) / (N_A * N_D))
    E_max = 2.0 * V_tot / W
    xs = np.linspace(0.0, W, n_x)
    Es = E_max * (1.0 - xs / W)
    ae = np.array([alpha_electron(e) for e in Es])
    ah = np.array([alpha_hole(e) for e in Es])
    dx = xs[1] - xs[0]
    cum_e = np.concatenate([[0.0], np.cumsum((ae[1:] + ae[:-1]) * 0.5 * dx)])
    cum_h = np.concatenate([[0.0], np.cumsum((ah[1:] + ah[:-1]) * 0.5 * dx)])
    return {"W": W, "E_max": E_max, "x": xs, "E": Es, "alpha_e": ae, "alpha_h": ah,
            "cum_e": cum_e, "cum_h": cum_h, "V_bi": V_bi, "V_tot": V_tot,
            "N_A": N_A, "N_D": N_D, "n_x": n_x,
            "provenance": "self_authored_t1c_w6_true_solve", "is_oracle": False}


def multiplication_exact(V: float, N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                         n_x: int = N_X_DEFAULT) -> float:
    """精确 1D 局部电离模型倍增因子 M(V)（e 注入，确定性积分）。

    M = 2 / (1 + e^{−2D_W} − 2J)，D(x)=∫₀ˣ(αe−αh)/2·dx'，J=∫(αe+αh)/2·e^{−2D}dx。
    极限校验：αh=0 → e^{αe·W}；αe=αh → 1/(1−αW)（机器精度，见 smoke/自检）。
    M→∞（分母≤0）返回 inf = 雪崩击穿。
    """
    p = avalanche_profiles(V, N_A, N_D, n_x)
    xs, ae, ah = p["x"], p["alpha_e"], p["alpha_h"]
    dx = xs[1] - xs[0]
    d = 0.5 * (ae - ah)
    s = 0.5 * (ae + ah)
    D = np.concatenate([[0.0], np.cumsum((d[1:] + d[:-1]) * 0.5 * dx)])
    J = float(np.trapezoid(s * np.exp(-2.0 * D), xs))
    den = 1.0 + math.exp(-2.0 * float(D[-1])) - 2.0 * J
    if den <= 1e-12:
        return float("inf")
    return 2.0 / den


def breakdown_voltage(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                      n_x: int = N_X_DEFAULT, M_thresh: float = M_BREAKDOWN_THRESHOLD,
                      lo: float = 1.0, hi: float = 500.0) -> float:
    """雪崩击穿电压 V_br（数值，M(V)=M_thresh 二分；确定性候选）。"""
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if multiplication_exact(mid, N_A, N_D, n_x) > M_thresh:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def mc_avalanche_gain_noise(V: float, n_pairs: int = 2000, seed: int = 7,
                            N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                            n_x: int = N_X_DEFAULT,
                            max_events: int = 1_000_000) -> tuple:
    """固定种子蒙特卡洛雪崩链 → (M, F)。

    物理：每次碰撞电离 = **母载流子存活** + 产生一个新 e-h 对（1→3 载流子；
    死亡-分支 1→2 会系统性低估 M 且偏差随场放大——本项目实测坑）。自由程由
    网格累积危险率反演（单调，无发散）：电子 +u 沿 cum_e，空穴 −u 沿 cum_h。
    统计口径：N = 1 + E（E=每初始电子的电离事件数）⇒ M=⟨N⟩，F=⟨N²⟩/⟨N⟩²。
    失败（事件数超限=击穿 runaway）抛 RuntimeError，绝不静默。
    """
    if n_pairs < 2:
        raise ValueError("mc_avalanche_gain_noise: n_pairs≥2")
    p = avalanche_profiles(V, N_A, N_D, n_x)
    cum_e, cum_h = p["cum_e"], p["cum_h"]
    nx = n_x
    rng = random.Random(seed)
    events_list = []
    for _ in range(n_pairs):
        stack = [("e", 0)]
        ev = 0
        while stack:
            carr, i0 = stack.pop()
            u = -math.log(1.0 - rng.random())
            if carr == "e":
                target = cum_e[i0] + u
                if target > cum_e[-1]:
                    continue                      # 越过 W 端收集
                j = int(np.searchsorted(cum_e, target))
                if j >= nx - 1:
                    continue
                stack += [("e", j), ("e", j), ("h", j)]
                ev += 1
            else:
                if i0 < 1:
                    continue
                target = cum_h[i0] - u
                if target < cum_h[1]:
                    continue                      # 越过 0 端收集
                j = int(np.searchsorted(cum_h, target, side="right")) - 1
                if j < 1:
                    continue
                stack += [("h", j), ("e", j), ("h", j)]
                ev += 1
            if ev > max_events:
                raise RuntimeError("mc_avalanche_gain_noise: 雪崩 runaway（事件数超限）")
        events_list.append(ev)
    arr = np.array(events_list, dtype=float)
    N = 1.0 + arr
    M = float(N.mean())
    F = float((N ** 2).mean() / (M * M))
    return M, F


# ============================================================
# golden 闭式（Miller / McIntyre，确定性物理定律锚）
# ============================================================
def miller_gain_closed(V: float, V_br: float, n_miller: float = 3.0) -> float:
    """golden：Miller 倍增闭式 M=1/(1−V/V_br)^n（与 B33/active_models 同式）。"""
    if V >= V_br or n_miller <= 0.0:
        raise ValueError("Miller: 须 V<V_br 且 n>0")
    return 1.0 / (1.0 - V / V_br) ** n_miller


def mcintyre_excess_noise_closed(M: float, k_eff: float) -> float:
    """golden：McIntyre 过剩噪声闭式 F = k·M + (2−1/M)(1−k)（e 注入，k=αh/αe）。"""
    if M <= 0.0 or not (0.0 <= k_eff <= 1.0):
        raise ValueError("McIntyre: M>0 且 0≤k≤1")
    return k_eff * M + (2.0 - 1.0 / M) * (1.0 - k_eff)


def effective_ionization_ratio(V: float, N_A: float = N_A_DEFAULT,
                               N_D: float = N_D_DEFAULT,
                               n_x: int = N_X_DEFAULT) -> float:
    """有效电离比 k_eff = ∫αh·dx / ∫αe·dx（McIntyre F 的输入）。"""
    p = avalanche_profiles(V, N_A, N_D, n_x)
    num = float(np.trapezoid(p["alpha_h"], p["x"]))
    den = float(np.trapezoid(p["alpha_e"], p["x"]))
    if den <= 0.0:
        raise RuntimeError("k_eff: ∫αe≤0（剖面异常）")
    return num / den


def miller_n_effective(V: float, V_br: float, M: float) -> float:
    """Miller 等效指数 n_eff = ln(M)/ln(1/(1−V/V_br))（误差公开载体）。"""
    x = 1.0 - V / V_br
    if x <= 0.0 or x >= 1.0 or M <= 1.0:
        raise ValueError("n_eff: 须 0<V/V_br<1 且 M>1")
    return math.log(M) / math.log(1.0 / x)


def apd_avalanche_true_solve(V: float, n_pairs: int = 2000, seed: int = 7,
                             N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                             n_x: int = N_X_DEFAULT) -> dict:
    """T1-C-W6 APD 雪崩输运 B 档真求解主入口（RC + 雪崩，误差公开）。

    返回 dict（候选，is_oracle=False）：M_exact / M_mc / F_mc / F_mcintyre /
    k_eff / n_eff_vs_own_vbr（误差公开：局部模型 n_eff 低于文献 Miller 带
    1.5–4，死区/非局域效应所致，如实标注）/ W / E_max / provenance。
    """
    M_ex = multiplication_exact(V, N_A, N_D, n_x)
    if math.isinf(M_ex):
        raise RuntimeError("apd_avalanche_true_solve: 已击穿（M_exact=inf）")
    M_mc, F_mc = mc_avalanche_gain_noise(V, n_pairs, seed, N_A, N_D, n_x)
    V_br = breakdown_voltage(N_A, N_D, n_x)
    k_eff = effective_ionization_ratio(V, N_A, N_D, n_x)
    F_mcint = mcintyre_excess_noise_closed(M_ex, k_eff)
    p = avalanche_profiles(V, N_A, N_D, n_x)
    n_eff = miller_n_effective(V, V_br, M_ex) if V < V_br and M_ex > 1.0 else float("nan")
    return {
        "metric": "apd_avalanche_M_F",
        "M_exact": M_ex, "M_mc": M_mc, "M_mc_over_exact": M_mc / M_ex,
        "F_mc": F_mc, "F_mcintyre_closed": F_mcint,
        "k_eff": k_eff, "n_eff_vs_own_vbr": n_eff,
        "V": V, "V_br": V_br, "W": p["W"], "E_max": p["E_max"],
        "n_pairs": n_pairs, "seed": seed,
        "honest_note": ("局部模型（无死区/非局域）n_eff 低于文献 Miller 带 1.5–4；"
                        "M/F 仅为候选，不作 ORACLE。"),
        "provenance": "self_authored_t1c_w6_true_solve",
        "is_oracle": False,
    }


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫（同 W2/W4/W5 语义）。"""
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 M/V_br/F 仅作候选，"
            "死标量判决须由物理定律闭式/文献/foundry 实测定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    # 解析极限自检（机器精度）
    def _lim(ae, ah, W):
        dW = 0.5 * (ae - ah) * W
        if abs(ae - ah) < 1e-30:
            J = ae * W
        else:
            J = 0.5 * (ae + ah) * (1.0 - math.exp(-(ae - ah) * W)) / (ae - ah)
        return 2.0 / (1.0 + math.exp(-2.0 * dW) - 2.0 * J)
    assert abs(_lim(1e5, 0.0, 3e-6) - math.exp(0.3)) < 1e-12
    assert abs(_lim(1e5, 1e5, 3e-6) - 1.0 / (1.0 - 0.3)) < 1e-12
    print("=== 解析极限自检：αh=0→e^{αW}、αe=αh→1/(1−αW) 机器精度一致 ===")
    V_br = breakdown_voltage()
    print(f"V_br(M=50) = {V_br:.3f} V")
    print(f"{'V':>6} {'M_ode':>8} {'M_mc':>8} {'ratio':>7} {'F_mc':>7} {'F_McI':>7} {'n_eff':>6}")
    for frac in (0.5, 0.7, 0.9):
        V = frac * V_br
        r = apd_avalanche_true_solve(V, n_pairs=1500, seed=7)
        print(f"{V:>6.1f} {r['M_exact']:>8.3f} {r['M_mc']:>8.3f} "
              f"{r['M_mc_over_exact']:>7.4f} {r['F_mc']:>7.3f} "
              f"{r['F_mcintyre_closed']:>7.3f} {r['n_eff_vs_own_vbr']:>6.3f}")
    guard_t1_not_oracle(apd_avalanche_true_solve(0.5 * V_br, n_pairs=100))
    print("=== T1 不作 ORACLE 守卫：正常通过 ===")
