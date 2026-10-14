# -*- coding: utf-8 -*-
"""J4-M3 封装与低温布线热负载（Quantum Sensing System Integration · Layer 4 / 缺口 G-QSYS-4）。

═══ 这是什么 ═══
把「器件级灵敏度」补齐到「**系统级成本项**」：超导腿（SQUID，4 K）与低温 OPM 都必须把
室温机架（300 K）的**线束热负载**压到稀释制冷机的冷量预算之内 —— 这是「设计得出来」与
「**用得起来**」之间的分水岭，QS 器件征程（M0–M9）**完全未覆盖**（其 24 锚全在器件物理）。

    Q = (A/L)·∫_{T_c}^{T_h} k(T) dT        （无源稳态一维传导 · 沿线温度积分）

**热导模型（Wiedemann–Franz）**：金属线束的电子热导 `k_el(T) = L₀·T/ρ(T)`，
其中 `L₀ = π²k_B²/(3e²) = 2.44e-8 W·Ω/K²` 为 Lorenz 数（**物理常数**）、
`ρ(T) = ρ₀ + β·T` 为铜的两区简化电阻率（低温杂质散射残差 ρ₀ + 电子–声子线性项 β）。
⇒ `Q = (A/L)·L₀/β²·{[(ρ₀+βT) − ρ₀ln(ρ₀+βT)]}_{T_c}^{T_h}`（**初等闭式**）。

🔴 账本锚 **B518**（`benchmark_defs/part7`）用**同一物理律**：闭式 ⇄ **RK4 积分定义 ODE**
`dQ/dT = (A/L)·k_el(T)`（本模块提供闭式侧，门禁做跨模块同律判据）。

═══ 诚实边界 ═══
· ρ₀ / β / A / L / T 均为**设计示例量级**（铜的简化两区电阻率模型；非实测线束 PDK）；
· 只证「闭式 ⇄ 数值积分」一致 + 系统级热负载链自洽，**不作制造/性能宣称**；
· 未建模：辐射热负载（同轴线黑体传播）、超导线的非线性热导、接头热阻、多级冷台分配。
零商业依赖（纯 numpy + math；零 RNG）。
"""
from __future__ import annotations

import math

# ══════════════════════════════════════════════════════════════════════
# 物理常量（设计示例量级）
# ══════════════════════════════════════════════════════════════════════
LORENZ_NUMBER = 2.44e-8            # W·Ω/K²（L₀ = π²k_B²/(3e²)）
CU_RESIDUAL_RHO = 1.0e-10          # Ω·m（铜低温杂质散射残差电阻率 ρ₀）
CU_BETA = 5.6e-11                  # Ω·m/K（电子–声子线性斜率 β）
WIRE_AREA_M2 = 1.0e-7              # m²（单根 0.1 mm² 有效传导截面）
WIRE_LENGTH_M = 0.5                # m（300 K 冷台 → 4 K 冷台）
T_HOT_K = 300.0
T_COLD_K = 4.0

_CALIBER = "低温线束热负载 · Wiedemann–Franz 电子热导 + 两区电阻率 · 设计示例量级"


def assert_caliber(caliber: str) -> None:
    """口径守卫：只接受本模块的统一口径串。"""
    if caliber != _CALIBER:
        raise ValueError("热负载口径不符：本模块仅支持 %r" % _CALIBER)


def rho_copper(T: float, rho0: float = CU_RESIDUAL_RHO,
               beta: float = CU_BETA) -> float:
    """铜的两区简化电阻率 ρ(T) = ρ₀ + β·T（Ω·m）。"""
    if rho0 <= 0.0 or beta < 0.0:
        raise ValueError("须 ρ₀ > 0 且 β ≥ 0")
    return float(rho0) + float(beta) * float(T)


def k_electronic(T: float, rho0: float = CU_RESIDUAL_RHO,
                 beta: float = CU_BETA) -> float:
    """Wiedemann–Franz 电子热导 k_el(T) = L₀·T/ρ(T)（W/(m·K)）。"""
    return LORENZ_NUMBER * float(T) / rho_copper(T, rho0, beta)


def cryo_wiring_heat_load(rho0: float = CU_RESIDUAL_RHO, beta: float = CU_BETA,
                          A_m2: float = WIRE_AREA_M2, L_m: float = WIRE_LENGTH_M,
                          T_hot_K: float = T_HOT_K, T_cold_K: float = T_COLD_K) -> float:
    """单根线束的低温热负载 Q（W）—— 闭式（与账本锚 B518 golden 同律）。

        Q = (A/L)·L₀/β² · {[(ρ₀+βT) − ρ₀·ln(ρ₀+βT)]}_{T_c}^{T_h}
    β = 0 ⇒ 退化纯 WF 极限 (A/L)·L₀(T_h²−T_c²)/(2ρ₀)。
    """
    rho0, beta = float(rho0), float(beta)
    if rho0 <= 0.0 or beta < 0.0:
        raise ValueError("须 ρ₀ > 0 且 β ≥ 0")
    if T_hot_K <= T_cold_K:
        raise ValueError("须 T_hot > T_cold")
    scale = float(A_m2) / float(L_m)
    if beta == 0.0:
        return scale * LORENZ_NUMBER * (float(T_hot_K) ** 2 - float(T_cold_K) ** 2) / (2.0 * rho0)

    def _anti(T):
        u = rho0 + beta * T
        return (u - rho0 * math.log(u)) / (beta * beta)

    return scale * LORENZ_NUMBER * (_anti(float(T_hot_K)) - _anti(float(T_cold_K)))


def multiwire_heat_load(n_wires: int, **kwargs) -> float:
    """n 根**完全相同**线束的总热负载 = n · Q_single（线性叠加）。"""
    n = int(n_wires)
    if n < 1:
        raise ValueError("线数 n_wires 须 ≥ 1")
    return n * cryo_wiring_heat_load(**kwargs)


def cooling_budget_fraction(load_w: float, budget_w: float) -> float:
    """热负载占冷量预算的比例（0–1；>1 ⇒ 超预算 ⇒ 系统不可用）。"""
    if budget_w <= 0.0:
        raise ValueError("冷量预算须 > 0")
    return float(load_w) / float(budget_w)


def package_report(n_wires: int = 20, budget_w: float = 1.0, **kwargs) -> dict:
    """封装/低温布线热负载总装报告（单线 / 总线 / 预算占比 / 签核）。"""
    q1 = cryo_wiring_heat_load(**kwargs)
    qtot = multiwire_heat_load(n_wires, **kwargs)
    frac = cooling_budget_fraction(qtot, budget_w)
    return {
        "caliber": _CALIBER,
        "single_wire_load_w": float(q1),
        "n_wires": int(n_wires),
        "total_load_w": float(qtot),
        "budget_w": float(budget_w),
        "budget_fraction": float(frac),
        "k_at_300K_w_per_mk": float(k_electronic(300.0)),
        "verdict": "ACCEPT" if frac < 1.0 else "REJECT",
    }


# ── 自检 ────────────────────────────────────────────────────────────────
def selfcheck_qs_j4_pkg() -> dict:
    checks = {}
    q = cryo_wiring_heat_load()
    checks["load_positive_finite"] = bool(math.isfinite(q) and q > 0.0)
    # β=0 退化纯 WF 极限（独立式）
    q_wf = cryo_wiring_heat_load(beta=0.0)
    q_wf_ref = (WIRE_AREA_M2 / WIRE_LENGTH_M) * LORENZ_NUMBER \
        * (T_HOT_K ** 2 - T_COLD_K ** 2) / (2.0 * CU_RESIDUAL_RHO)
    checks["beta_zero_reduces_to_wf_limit"] = bool(abs(q_wf - q_wf_ref) < 1e-15)
    # 温度依赖使负载**低于**纯 WF（β>0 ⇒ ρ 增大 ⇒ k 减小 ⇒ Q 减小）
    checks["beta_reduces_load"] = bool(q < q_wf)
    # 线性标度
    checks["linear_in_area"] = bool(
        abs(cryo_wiring_heat_load(A_m2=2.0 * WIRE_AREA_M2) - 2.0 * q) < 1e-15)
    checks["inverse_in_length"] = bool(
        abs(cryo_wiring_heat_load(L_m=2.0 * WIRE_LENGTH_M) - 0.5 * q) < 1e-15)
    checks["linear_in_n_wires"] = bool(abs(multiwire_heat_load(3) - 3.0 * q) < 1e-15)
    # 单调于温差
    checks["monotone_in_delta_T"] = bool(
        cryo_wiring_heat_load(T_hot_K=400.0) > q)
    # ρ₀ ↑ ⇒ Q ↓（电阻大 ⇒ 热导小）
    checks["monotone_decreasing_in_rho0"] = bool(
        cryo_wiring_heat_load(rho0=2.0 * CU_RESIDUAL_RHO) < q)
    # 预算占比 / 签核
    rep = package_report()
    checks["report_accept"] = bool(rep["verdict"] == "ACCEPT")
    checks["budget_fraction_consistent"] = bool(
        abs(rep["budget_fraction"] - rep["total_load_w"] / rep["budget_w"]) < 1e-15)
    # 反向探针
    checks["reverse_bad_rho_raises"] = _raises(lambda: cryo_wiring_heat_load(rho0=0.0))
    checks["reverse_bad_T_raises"] = _raises(lambda: cryo_wiring_heat_load(T_hot_K=3.0))
    checks["reverse_bad_caliber_raises"] = _raises(lambda: assert_caliber("x"))
    checks["reverse_budget_raises"] = _raises(lambda: cooling_budget_fraction(1.0, 0.0))
    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    sc = selfcheck_qs_j4_pkg()
    bad = 0
    print("=" * 64)
    print("J4-M3 封装热负载自检：")
    for k, v in sc.items():
        ok = bool(v)
        bad += 0 if ok else 1
        print("  [%s] %s" % ("PASS" if ok else "FAIL", k))
    print("=" * 64)
    print("ALL PASS" if bad == 0 else "%d FAIL" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
