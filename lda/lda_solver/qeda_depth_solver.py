"""LDA L2 · QEDA 纵深三件套求解器（D-91）：多能级展开 / 驱动场 / 读出串扰。

与光子栈「闭式解析 ↔ 严格数值」双验证同构，量子侧三条独立物理链：

① **多能级电荷基底展开**（色散读出收敛性）：把 D-88 三能级色散读出推广到
   可配 L 能级 transmon（E_s = s·f_q + s(s-1)/2·α，耦合矩阵元 <s+1|n̂|s>=√(s+1)
   ——标准 transmon 电荷矩阵元），严格对角化验证 χ 随能级数的**收敛性**
   （3→6 能级 χ 变化 < 1% ⇒ 三能级模型自洽、更高能级贡献可忽略）。
   物理锚：χ(L) 序列单调收敛；收敛后与 Blais 修正解析式 χ=g²α/(Δ(Δ+α)) 对拍。

② **驱动场 Rabi / AC Stark**（实验标定核心物理）：二能级旋转波近似（RWA）
   静态哈密顿 H = -(δ_d/2)σz + (Ω/2)σx（δ_d=ω_d-ω_q 驱动失谐）：
   - 共振（δ_d=0）：本征分裂 = Ω ⇒ **Rabi 频率 Ω_R = Ω**（自洽，rel≈0）；
   - 失谐（|δ_d|≫Ω）：能级差 √(δ_d²+Ω²) 相对无驱动 |δ_d| 的偏移/2
     ⇒ **AC Stark 频移 δω = Ω²/(4δ_d)**（解析对拍，弱驱动区 rel ≤ 10%）。
   物理锚：Rabi 自洽 + AC Stark 解析式。

③ **多 qubit 读出串扰（ZZ 耦合）**：两 transmon（不同频率打破简并，频率复用
   真实场景）+ 共享 readout 谐振器联合严格对角化（维度 Lq²×(M+1)）。
   串扰 = **ZZ 耦合 J_zz = (E_ee − E_eg − E_ge + E_gg)/2**（qubit 态能量偏移，
   无需谐振器态标记，谱提取稳健）。物理锚：g=0 时 J_zz=0（自洽）、
   q1↔q2 互换对称（rel≤1%）、媒介耦合量级远弱于直接色散（|J_zz/χ|<1 弱耦合）。

零外部依赖（numpy 小矩阵对角化），LLM 不进判决路径。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

__all__ = ["tls_spectrum_L", "solve_level_convergence",
           "rwa_spectrum", "solve_drive",
           "twoq_resonator_spectrum", "solve_crosstalk",
           "solve_qeda_depth"]


# ---------------------------------------------------------------------------
# ① 多能级电荷基底展开（色散读出收敛性）
# ---------------------------------------------------------------------------
def tls_spectrum_L(f_q: float, alpha: float, f_r: float, g: float,
                   L: int = 3, M: int = 25) -> np.ndarray:
    """L 能级 transmon + Fock 谐振器联合严格对角化（GHz）。

    E_s = s·f_q + s(s-1)/2·α；耦合矩阵元 <s+1|n̂|s> = √(s+1)（n₀₁→1 归一化）。
    维度 L×(M+1)。低能级顺序（弱耦合）|g,0⟩<|e,0⟩<|g,1⟩<|f,0⟩<…。
    """
    dim = L * (M + 1)
    H = np.zeros((dim, dim), dtype=float)
    Es = [s * f_q + s * (s - 1) * alpha / 2.0 for s in range(L)]

    def idx(s: int, n: int) -> int:
        return s * (M + 1) + n

    for s in range(L):
        for n in range(M + 1):
            H[idx(s, n), idx(s, n)] = Es[s] + n * f_r
    for s in range(L - 1):
        ms = math.sqrt(s + 1.0)
        for n in range(M):
            fac = math.sqrt(n + 1.0)
            H[idx(s + 1, n + 1), idx(s, n)] += g * fac * ms
            H[idx(s, n), idx(s + 1, n + 1)] += g * fac * ms
            H[idx(s + 1, n), idx(s, n + 1)] += g * fac * ms
            H[idx(s, n + 1), idx(s + 1, n)] += g * fac * ms
    return np.sort(np.linalg.eigh(H)[0])


def _chi_from_spectrum(E: np.ndarray, f_q: float, f_r: float) -> float:
    """最近能量匹配提取色散频移 χ（弱耦合区态混合小，唯一近邻）。"""
    def near(t: float) -> float:
        return float(E[np.argmin(np.abs(E - t))])

    E_g0 = near(0.0)
    E_e0 = near(f_q)
    E_g1 = near(f_r)
    E_e1 = near(f_q + f_r)
    return float(((E_e1 - E_e0) - (E_g1 - E_g0)) / 2.0)


def solve_level_convergence(f_q: float = 5.0, alpha: float = -0.3,
                            f_r: float = 6.0, g: float = 0.1,
                            L_max: int = 6, M: int = 25,
                            tol_conv: float = 0.01) -> Dict[str, Any]:
    """多能级展开收敛性验证：χ(L) 序列 + 收敛判据 + 与 Blais 修正解析对拍。"""
    chis: List[float] = []
    for L in range(3, L_max + 1):
        E = tls_spectrum_L(f_q, alpha, f_r, g, L=L, M=M)
        chis.append(_chi_from_spectrum(E, f_q, f_r))
    chi_3 = chis[0]
    chi_max = chis[-1]
    conv_rel = abs(chi_max - chi_3) / (abs(chi_3) + 1e-12)
    delta = f_q - f_r
    chi_an = g * g * alpha / (delta * (delta + alpha))
    chi_rel_an = abs(chi_max - chi_an) / (abs(chi_an) + 1e-12)
    converged = bool(conv_rel <= tol_conv and chi_rel_an <= 0.10)
    return {
        "chi_by_level": {L: round(float(c), 9)
                         for L, c in zip(range(3, L_max + 1), chis)},
        "chi_3level": round(chi_3, 9),
        "chi_maxlevel": round(chi_max, 9),
        "conv_rel_3_to_max": float(conv_rel),
        "chi_analytic_3level_ghz": round(float(chi_an), 9),
        "chi_analytic_rel_err": float(chi_rel_an),
        "converged": converged,
        "acceptance": {
            "passed": converged,
            "checks": {
                "convergence_3_to_max_le_1pct": bool(conv_rel <= tol_conv),
                "chi_matches_blais_3level_le_10pct": bool(chi_rel_an <= 0.10),
            },
        },
    }


# ---------------------------------------------------------------------------
# ② 驱动场 Rabi / AC Stark（RWA）
# ---------------------------------------------------------------------------
def rwa_spectrum(delta_d: float, Omega: float) -> np.ndarray:
    """RWA 静态哈密顿 H=−(δ/2)σz+(Ω/2)σx 的本征值（GHz）。"""
    return np.linalg.eigvalsh(
        np.array([[-delta_d / 2.0, Omega / 2.0],
                  [Omega / 2.0, delta_d / 2.0]], dtype=float))


def solve_drive(f_q: float = 5.0, Omega: float = 0.05,
                delta_d: float = 0.4, tol_rabi: float = 0.01,
                tol_ac: float = 0.10) -> Dict[str, Any]:
    """驱动场求解：共振 Rabi 自洽 + 失谐 AC Stark 解析对拍。"""
    # 共振：δ_d=0 → 本征分裂 = Ω（Rabi 频率）
    E_res = rwa_spectrum(0.0, Omega)
    rabi_num = float(E_res[1] - E_res[0])
    rabi_rel = abs(rabi_num - Omega) / (Omega + 1e-12)
    # 失谐：AC Stark 频移（能级差相对无驱动 |δ_d| 的偏移 / 2）
    E_off = rwa_spectrum(delta_d, Omega)
    dw_num = (E_off[1] - E_off[0] - abs(delta_d)) / 2.0
    dw_an = Omega * Omega / (4.0 * abs(delta_d))
    ac_rel = abs(dw_num - dw_an) / (abs(dw_an) + 1e-12)
    passed = bool(rabi_rel <= tol_rabi and ac_rel <= tol_ac)
    return {
        "rabi_freq_ghz": round(float(rabi_num), 9),
        "omega_ghz": round(float(Omega), 9),
        "rabi_self_rel_err": float(rabi_rel),
        "ac_stark_num_ghz": round(float(dw_num), 9),
        "ac_stark_analytic_ghz": round(float(dw_an), 9),
        "ac_stark_rel_err": float(ac_rel),
        "delta_d_ghz": float(delta_d),
        "omega_over_delta": float(Omega / abs(delta_d)),
        "passed": passed,
        "acceptance": {
            "passed": passed,
            "checks": {
                "rabi_self_consistency_le_1pct": bool(rabi_rel <= tol_rabi),
                "ac_stark_analytic_le_10pct": bool(ac_rel <= tol_ac),
            },
        },
    }


# ---------------------------------------------------------------------------
# ③ 多 qubit 读出串扰（ZZ 耦合）
# ---------------------------------------------------------------------------
def twoq_resonator_spectrum(f_q1: float, f_q2: float, alpha: float,
                            f_r: float, g1: float, g2: float,
                            Lq: int = 3, M: int = 12) -> np.ndarray:
    """2 transmon（不同频率打破简并）+ 共享 readout 谐振器严格对角化。

    维度 Lq²×(M+1)。耦合 g1·n̂1(a+a†) + g2·n̂2(a+a†)。
    """
    dim = Lq * Lq * (M + 1)
    H = np.zeros((dim, dim), dtype=float)
    E1 = [s * f_q1 + s * (s - 1) * alpha / 2.0 for s in range(Lq)]
    E2 = [s * f_q2 + s * (s - 1) * alpha / 2.0 for s in range(Lq)]

    def idx(s1: int, s2: int, n: int) -> int:
        return (s1 * Lq + s2) * (M + 1) + n

    for s1 in range(Lq):
        for s2 in range(Lq):
            for n in range(M + 1):
                H[idx(s1, s2, n), idx(s1, s2, n)] = E1[s1] + E2[s2] + n * f_r
    for s in range(Lq - 1):
        ms = math.sqrt(s + 1.0)
        for n in range(M):
            fac = math.sqrt(n + 1.0)
            for s2 in range(Lq):
                H[idx(s + 1, s2, n + 1), idx(s, s2, n)] += g1 * fac * ms
                H[idx(s, s2, n), idx(s + 1, s2, n + 1)] += g1 * fac * ms
                H[idx(s + 1, s2, n), idx(s, s2, n + 1)] += g1 * fac * ms
                H[idx(s, s2, n + 1), idx(s + 1, s2, n)] += g1 * fac * ms
            for s1 in range(Lq):
                H[idx(s1, s + 1, n + 1), idx(s1, s, n)] += g2 * fac * ms
                H[idx(s1, s, n), idx(s1, s + 1, n + 1)] += g2 * fac * ms
                H[idx(s1, s + 1, n), idx(s1, s, n + 1)] += g2 * fac * ms
                H[idx(s1, s, n + 1), idx(s1, s + 1, n)] += g2 * fac * ms
    return np.sort(np.linalg.eigh(H)[0])


def _jzz_from_spectrum(E: np.ndarray, f_q1: float, f_q2: float) -> float:
    """ZZ 耦合提取：J_zz=(E_ee−E_eg−E_ge+E_gg)/2（qubit 态能量偏移，稳健）。"""
    def near(t: float) -> float:
        return float(E[np.argmin(np.abs(E - t))])

    E_gg = near(0.0)
    E_ge = near(f_q1)
    E_eg = near(f_q2)
    E_ee = near(f_q1 + f_q2)
    return float((E_ee - E_eg - E_ge + E_gg) / 2.0)


def solve_crosstalk(f_q1: float = 5.0, f_q2: float = 5.2,
                    alpha: float = -0.3, f_r: float = 6.0,
                    g1: float = 0.1, g2: float = 0.08,
                    Lq: int = 3, M: int = 12,
                    tol_sym: float = 0.01) -> Dict[str, Any]:
    """多 qubit 读出串扰：共享谐振器媒介 ZZ 耦合（自洽 + 对称 + 量级）。"""
    E0 = twoq_resonator_spectrum(f_q1, f_q2, alpha, f_r, 0.0, 0.0, Lq, M)
    jzz_zero = _jzz_from_spectrum(E0, f_q1, f_q2)
    E1 = twoq_resonator_spectrum(f_q1, f_q2, alpha, f_r, g1, g2, Lq, M)
    jzz = _jzz_from_spectrum(E1, f_q1, f_q2)
    E2 = twoq_resonator_spectrum(f_q2, f_q1, alpha, f_r, g2, g1, Lq, M)
    jzz_swap = _jzz_from_spectrum(E2, f_q2, f_q1)
    sym_rel = abs(jzz - jzz_swap) / (abs(jzz) + 1e-12)
    # 量级：媒介耦合 vs 直接色散（弱耦合自洽）
    E_ref = tls_spectrum_L(f_q1, alpha, f_r, g1, L=3, M=M)
    chi_ref = abs(_chi_from_spectrum(E_ref, f_q1, f_r))
    ratio = abs(jzz) / (chi_ref + 1e-12)
    self_ok = abs(jzz_zero) < 1e-9
    sym_ok = bool(sym_rel <= tol_sym)
    scale_ok = bool(ratio < 1.0)
    passed = bool(self_ok and sym_ok and scale_ok)
    return {
        "jzz_coupling_ghz": round(float(jzz), 9),
        "jzz_zero_coupling": round(float(jzz_zero), 12),
        "symmetry_swap_rel_err": float(sym_rel),
        "ratio_jzz_over_chi": float(ratio),
        "chi_ref_ghz": round(float(chi_ref), 9),
        "f_q1": float(f_q1), "f_q2": float(f_q2), "f_r": float(f_r),
        "g1": float(g1), "g2": float(g2),
        "passed": passed,
        "acceptance": {
            "passed": passed,
            "checks": {
                "self_consistency_g0_jzz0": bool(self_ok),
                "swap_symmetry_le_1pct": sym_ok,
                "mediator_weaker_than_direct": scale_ok,
            },
        },
    }


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------
def solve_qeda_depth(f_q: float = 5.0, alpha: float = -0.3,
                     f_r: float = 6.0, g: float = 0.1,
                     Omega: float = 0.05, delta_d: float = 0.4,
                     f_q2: float = 5.2, g2: float = 0.08,
                     L_max: int = 6, M: int = 25) -> Dict[str, Any]:
    """D-91 QEDA 纵深三件套统一求解（多能级收敛 + 驱动场 + 读出串扰）。"""
    conv = solve_level_convergence(f_q=f_q, alpha=alpha, f_r=f_r, g=g,
                                   L_max=L_max, M=M)
    drive = solve_drive(f_q=f_q, Omega=Omega, delta_d=delta_d)
    xtalk = solve_crosstalk(f_q1=f_q, f_q2=f_q2, alpha=alpha, f_r=f_r,
                            g1=g, g2=g2, M=min(M, 12))
    passed = bool(conv["converged"] and drive["passed"] and xtalk["passed"])
    return {
        "convergence": conv,
        "drive": drive,
        "crosstalk": xtalk,
        "passed": passed,
        "acceptance": {
            "passed": passed,
            "checks": {
                "level_convergence_3_to_max_le_1pct":
                    bool(conv["acceptance"]["checks"]
                         ["convergence_3_to_max_le_1pct"]),
                "rabi_self_consistency":
                    bool(drive["acceptance"]["checks"]
                         ["rabi_self_consistency_le_1pct"]),
                "ac_stark_analytic":
                    bool(drive["acceptance"]["checks"]
                         ["ac_stark_analytic_le_10pct"]),
                "crosstalk_self_consistency":
                    bool(xtalk["acceptance"]["checks"]
                         ["self_consistency_g0_jzz0"]),
                "crosstalk_swap_symmetry":
                    bool(xtalk["acceptance"]["checks"]
                         ["swap_symmetry_le_1pct"]),
                "crosstalk_mediator_weaker_than_direct":
                    bool(xtalk["acceptance"]["checks"]
                         ["mediator_weaker_than_direct"]),
            },
        },
        "verdict": ("QEDA 纵深三件套全过：多能级展开收敛 + Rabi/AC Stark 解析锚 "
                    "+ 读出串扰 ZZ 耦合自洽" if passed else "未达标"),
    }


if __name__ == "__main__":
    import json
    r = solve_qeda_depth()
    print(json.dumps({"passed": r["passed"], "acceptance": r["acceptance"],
                      "verdict": r["verdict"]}, ensure_ascii=False, indent=2))
