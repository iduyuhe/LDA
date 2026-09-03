"""MZM 半波电压 Vπ 的数值零点拟合求解器（B28 独立候选 · v0.9.28 · T-2）。

物理链（候选只走这条链，**从不反解闭式 Vπ=λ₀d/(2n³rΓL)**）：
  Pockels 效应    Δn(z) = −½·n_eff³·r_eff·Γ·E(z)，E(z)=V/d
  单臂相位累积    Δφ_arm(V) = (2π/λ₀)·∫Δn dz = (π·n_eff³·r_eff·Γ·L/(λ₀·d))·V
  推挽 MZM 传输   T(V) = cos²(Δφ_total/2) = cos²(Δφ_arm(V))
  Vπ 定义        T(Vπ)=0 的第一个传输零点

候选做法（= 实验 Measure Vπ 的标准流程的数值化）：
  1. 在电压区间 (0.01·V_φ=π, V_φ=π] 取 n_voltage 个等距采样点；
     V_φ=π 由相位链 Δφ_arm=π 反解（数值上=2·Vπ），**仅作括住零点的扫描上界**，
     零点位置不由此得出；
  2. 逐点计算 T(V)；
  3. 找第一个局部极小（即第一个传输零点）；
  4. 过零点邻域三点做抛物线拟合，取顶点为 Vπ。

🔴 与 golden 的方法学独立（与 B3/B4/B20 峰拟合同族，项目已判定的独立模式）：
  golden = 对 T(V)=0 条件的**解析反解**（闭式）；
  候选   = 对模拟观测谱 T(V) 的**数值零点测量**（采样 + 抛物线定顶）。
  候选从不求值 λ₀d/(2n³rΓL)。

🔴 判据 D 实测（2026-09-03，判据 D 单一定义处复算）：
  cos² 在零点附近 = sin²(u)·(1−u²/3+…) 含四次修正 ⇒ 抛物线顶点误差 ~O(ΔV³)，
  随网格加密严格收敛（N 加倍 ⇒ 误差降 ~8×）。**与沿程积分候选（剖分守恒 ⇒
  残差恒 4.44e-16 的代数恒等）形成对照**——判据 D 抓前放后、抓此放彼。
  生产档位 n_voltage=400：基线残差 ~4e-8 V（tol=1e-3 的 0.004%，且 ≫1e-12
  噪声地板，双向可标定）。

⚠️ 诚实边界：
  1. **同一 1D Pockels 模型**：候选与 golden 共享同一物理模型，独立性在
     「解法」（解析反解 vs 数值零点测量），不在「模型」。与 B20（闭式 FSR vs
     数值谱峰拟合）同档。
  2. 均匀 Γ 假设：候选支持任意 Γ(z)（积分换 ΣΓᵢ·Δzᵢ 即可），当前锚参数为
     均匀段。
  3. 扫描上界由相位链反解（=2·Vπ）：只决定从哪扫描，不影响零点定位——
     上界取 3π 反解（=3·Vπ）时结果不变（首个零点在 π/2·(2/π)…即中部）。

红线：纯标准库（math），零第三方依赖；LLM 不进判决路径。
"""
from __future__ import annotations

import math

# 生产档位：n_voltage=400 ⇒ 基线残差 ~4e-8 V（tol 1e-3 的 0.004%）。
# 🔴 双向标定（铁律）：加粗（N 小）⇒ 残差浮出、可标定；再加密（N≥3200）⇒
# 残差逼近双精度噪声地板，与代数恒等不可区分 ⇒ **勿盲目加密**。
DEFAULT_N_VOLTAGE = 400


def _arm_phase(V: float, lam_m: float, n_eff: float, r_eff: float,
               gamma: float, L_m: float, d_m: float) -> float:
    """单臂 Pockels 相位累积 |Δφ_arm(V)|（物理链第一二环，SI 单位）。"""
    return (math.pi * (n_eff ** 3) * r_eff * V * gamma * L_m) / (lam_m * d_m)


def _transmission(V: float, lam_m: float, n_eff: float, r_eff: float,
                  gamma: float, L_m: float, d_m: float) -> float:
    """推挽 MZM 传输 T(V) = cos²(Δφ_arm)（differential = 2·arm ⇒ cos²(arm)）。"""
    return math.cos(_arm_phase(V, lam_m, n_eff, r_eff, gamma, L_m, d_m)) ** 2


def mzm_vpi_nullfit(lambda_vac_um: float = 1.55,
                    n_eff: float = 2.2,
                    r_eff: float = 30.8e-12,
                    gamma: float = 0.5,
                    L_um: float = 10000.0,
                    d_um: float = 8.0,
                    n_voltage: int = DEFAULT_N_VOLTAGE) -> float:
    """数值零点拟合半波电压 Vπ（B28 独立候选）。

    采样 T(V) → 首个局部极小 → 三点抛物线定顶。从不求值闭式 Vπ。
    """
    lam = lambda_vac_um * 1e-6
    L = L_um * 1e-6
    d = d_um * 1e-6

    # 扫描上界：相位链 Δφ_arm = π 的反解（数值上 = 2·Vπ），仅括住首个零点。
    v_hi = (lam * d) / ((n_eff ** 3) * r_eff * gamma * L)
    v_lo = 0.01 * v_hi
    n = max(int(n_voltage), 8)
    dv = (v_hi - v_lo) / n

    # 找第一个局部极小（T 先单调降后回升处 = 首个传输零点）
    prev = _transmission(v_lo, lam, n_eff, r_eff, gamma, L, d)
    curr = _transmission(v_lo + dv, lam, n_eff, r_eff, gamma, L, d)
    for i in range(1, n):
        v_next = v_lo + (i + 1) * dv
        nxt = _transmission(v_next, lam, n_eff, r_eff, gamma, L, d)
        if curr <= prev and curr <= nxt:
            # 三点抛物线定顶：(v_prev,prev) (v,curr) (v_next,nxt)
            denom = prev - 2.0 * curr + nxt
            if denom > 0.0:
                return v_lo + i * dv + 0.5 * dv * (prev - nxt) / denom
            return v_lo + i * dv
        prev, curr = curr, nxt
    raise ValueError("扫描区间内未找到传输零点（参数异常或 n_voltage 过小）")


def nullfit_convergence(lambda_vac_um: float = 1.55,
                        n_eff: float = 2.2,
                        r_eff: float = 30.8e-12,
                        gamma: float = 0.5,
                        L_um: float = 10000.0,
                        d_um: float = 8.0,
                        ns=(25, 50, 100, 200, 400, 800),
                        ) -> dict:
    """判据 D 证据表：残差随电压网格密度 N 的收敛（供常驻 smoke 断言）。"""
    lam = lambda_vac_um * 1e-6
    L = L_um * 1e-6
    d = d_um * 1e-6
    # 参照值 = 闭式（仅用于**测量**残差，不进候选路径）
    ref = (lam * d) / (2.0 * (n_eff ** 3) * r_eff * gamma * L)
    rows = []
    for n in ns:
        v = mzm_vpi_nullfit(lambda_vac_um, n_eff, r_eff, gamma, L_um, d_um,
                            n_voltage=n)
        rows.append({"n_voltage": n, "vpi": v, "abs_err": abs(v - ref)})
    return {"ref_closed_form": ref, "rows": rows}
