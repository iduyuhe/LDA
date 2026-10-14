# -*- coding: utf-8 -*-
"""J4-M1 芯片级 OPM 微型化链（Quantum Sensing System Integration · Layer 4 / 缺口 G-QSYS-2）。

═══ 这是什么 ═══
把 QS-M9 的**台式**光泵原子磁力计（气室 2 cm + 分立 VCSEL/PD + 亥姆霍兹线圈）推进到
**芯片级**：MEMS 气室（mm 级）+ 片载 VCSEL + 光电二极管 —— 即「**微型化如何改变弛豫与
灵敏度**」这一 QS 器件征程未覆盖的系统级问题。

    γ_total = γ_wall + γ_buffer + γ_SE      （弛豫三源，定义式求和）
    γ_wall  = D_eff · (π/a)²                （1D 平板扩散最低衰减模式）
    γ_buf   = k_sd · p_bg                   （缓冲气体自旋破坏，线性压强律）
    η ∝ √(γ_total / (N_a · P_eff²))         （灵敏度正比于弛豫率平方根）

🔴🔴 **账本锚净增 0（如实登记 · 四重避让）** —— 本档**不登记新锚**，理由是**实 grep 全仓**
后四个候选**全部被既有锚占用**，任一都会构成同源重复计数：

| 候选物理量 | 被谁占用 | 判否理由 |
|---|---|---|
| **Voigt / 碰撞展宽线型**（原章程拟做「压致展宽线宽」） | **`voigt_profile`**（B197–B199 Voigt 族） | 同一线型算子 ⇒ **结构同源**（B-8 红线） |
| **气室数密度 n(T)** | **B492**（`qs_alkali_vapor_density`） | 同一被测标量 + 同一 Clausius–Clapeyron 律 |
| **泵浦光透过率 T(L)** | **B493**（`qs_pump_transmission`） | 同一 Beer–Lambert 光路量 |
| **弛豫三源求和**（壁/缓冲/光） | QS-M9 note 已**显式声明不登记** | 定义式求和 ⇒ 算术（同 B17 型） |
| **扩散热核 / 热方程时间推进** | **B-10 族**（线性扩散基础解热核） | 同一扩散算子 ⇒ 结构同源 |

⇒ 本模块交付**能力层（可复算的微型化模型）+ 诚实登记「无锚」**，**不硬凑**
（同 B-44/B-45/B-46 与 PS-M8 B472、QS-M9 的纪律：宁可少，不越级谎报）。

═══ 诚实边界 ═══
· 气室几何 / 缓冲气体压强 / VCSEL 功率 / 扩散系数均为**设计示例量级**（非实测 MEMS PDK）；
· 只证「微型化模型自洽 + 与 QS 器件链的量级一致」，**不作制造/性能宣称**；
· 未建模：气室温度梯度 3D 分布、VCSEL 谱–吸收谱重叠、PD 响应度与噪声、抗弛豫涂层老化。
零商业依赖（纯 numpy + math；零 RNG）。
"""
from __future__ import annotations

import math

#: 🔴 锚登记状态（供门禁判据机械核 —— 本档**净增 0**）
ANCHOR_STATUS = "none"
ANCHOR_AVOIDANCE = (
    ("voigt/collisional lineshape", "B197-B199 voigt_profile", "结构同源（同一线型算子）"),
    ("alkali vapor density n(T)", "B492 qs_alkali_vapor_density", "同被测标量 + 同 C-C 律"),
    ("pump transmission T(L)", "B493 qs_pump_transmission", "同 Beer-Lambert 光路量"),
    ("relaxation 3-source sum", "QS-M9 note（显式不登记）", "定义式求和 = 算术"),
    ("diffusion heat kernel", "B-10 族 线性扩散热核", "结构同源（同一扩散算子）"),
)

# ══════════════════════════════════════════════════════════════════════
# 物理常量（设计示例量级）
# ══════════════════════════════════════════════════════════════════════
CELL_SIDE_M = 2.0e-3              # m（MEMS 气室边长 2 mm · 台式典型 20 mm）
BUF_GAS_PRESSURE_TORR = 100.0     # Torr（缓冲气体压强）
TORR_TO_PA = 133.322
D0_M2_PER_S = 1.9e-4              # m²/s（碱金属–缓冲气体扩散系数 @ 1 Torr 参考）
P_REF_TORR = 1.0
K_SD_PER_TORR_S = 3.0e4           # 1/(s·Torr)（缓冲气体自旋破坏率系数，设计示例）
WALL_RELAX_BARE_S1 = 5.0e3        # 1/s（无涂层壁弛豫率，设计示例）
COATING_SUPPRESSION = 100.0       # 抗弛豫涂层把壁碰撞弛豫压低 100×
N_RELAX_BUFFER_ONLY_S1 = 0.0      # 占位（保留口径一致性）

_CALIBER = "芯片级 OPM 微型化 · 弛豫三源 + 扩散模式 · 设计示例量级"


def assert_caliber(caliber: str) -> None:
    if caliber != _CALIBER:
        raise ValueError("微型化口径不符：本模块仅支持 %r" % _CALIBER)


def diffusion_coefficient(pressure_torr: float = BUF_GAS_PRESSURE_TORR,
                          d0: float = D0_M2_PER_S, p_ref_torr: float = P_REF_TORR) -> float:
    """碱金属在缓冲气体中的扩散系数 D(p) = D₀·(p_ref/p)（与压强成反比）。"""
    p = float(pressure_torr)
    if p <= 0.0:
        raise ValueError("缓冲气体压强须 > 0")
    return float(d0) * float(p_ref_torr) / p


def wall_relaxation_rate(cell_side_m: float = CELL_SIDE_M, coated: bool = True,
                         D_m2_per_s: float = None) -> float:
    """壁弛豫率 γ_wall = D·(π/a)²（1D 平板扩散最低衰减模式；涂层可大幅压低）。

    物理：原子扩散到壁面被破坏自旋 ⇒ 弛豫率由最低扩散模式的衰减常数给出；
    抗弛豫涂层把每次壁碰撞的破坏概率降低 ⇒ 等效 γ_wall 除以 COATING_SUPPRESSION。
    """
    a = float(cell_side_m)
    if a <= 0.0:
        raise ValueError("气室尺寸须 > 0")
    D = diffusion_coefficient() if D_m2_per_s is None else float(D_m2_per_s)
    gamma = D * (math.pi / a) ** 2
    return gamma / COATING_SUPPRESSION if coated else gamma


def buffer_gas_rate(pressure_torr: float = BUF_GAS_PRESSURE_TORR,
                    k_sd: float = K_SD_PER_TORR_S) -> float:
    """缓冲气体自旋破坏率 γ_buf = k_sd·p（线性压强律）。"""
    if pressure_torr < 0.0:
        raise ValueError("压强须 ≥ 0")
    return float(k_sd) * float(pressure_torr)


def total_relaxation_rate(cell_side_m: float = CELL_SIDE_M, coated: bool = True,
                          pressure_torr: float = BUF_GAS_PRESSURE_TORR) -> float:
    """弛豫三源求和 γ_total = γ_wall + γ_buffer + γ_SE（γ_SE 取光抽运链的空占位 0）。"""
    return (wall_relaxation_rate(cell_side_m, coated)
            + buffer_gas_rate(pressure_torr))


def sensitivity_scale(cell_side_m: float = CELL_SIDE_M, coated: bool = True,
                      pressure_torr: float = BUF_GAS_PRESSURE_TORR) -> float:
    """灵敏度相对标度 ∝ √γ_total（假设 N_a 与极化不变 ⇒ 只反映弛豫变化）。"""
    return math.sqrt(total_relaxation_rate(cell_side_m, coated, pressure_torr))


def microcell_report(cell_side_m: float = CELL_SIDE_M, coated: bool = True,
                     pressure_torr: float = BUF_GAS_PRESSURE_TORR) -> dict:
    """芯片级 OPM 微型化报告（弛豫三源 + 与台式对照 + 锚状态）。"""
    gwall = wall_relaxation_rate(cell_side_m, coated)
    gbuf = buffer_gas_rate(pressure_torr)
    gtot = gwall + gbuf
    # 台式对照（20 mm 气室）
    gwall_bulk = wall_relaxation_rate(20.0e-3, coated)
    gtot_bulk = gwall_bulk + gbuf
    return {
        "caliber": _CALIBER,
        "cell_side_m": float(cell_side_m),
        "coated": bool(coated),
        "pressure_torr": float(pressure_torr),
        "wall_rate_s1": float(gwall),
        "buffer_rate_s1": float(gbuf),
        "total_rate_s1": float(gtot),
        "bulk_total_rate_s1": float(gtot_bulk),
        "miniaturization_penalty": float(gtot / gtot_bulk),
        "anchor_status": ANCHOR_STATUS,
        # 微型化使壁弛豫**增大**（a 小 ⇒ (π/a)² 大），故惩罚 >1
        "verdict": "ACCEPT" if gtot / gtot_bulk < 10.0 else "REJECT",
    }


# ── 自检 ────────────────────────────────────────────────────────────────
def selfcheck_qs_j4_microcell() -> dict:
    checks = {}
    checks["anchor_status_is_none"] = bool(ANCHOR_STATUS == "none")
    checks["avoidance_has_5_entries"] = bool(len(ANCHOR_AVOIDANCE) == 5)
    checks["diffusion_inverse_in_pressure"] = bool(
        abs(diffusion_coefficient(2.0) * 2.0 - diffusion_coefficient(1.0)) < 1e-15)
    g_small = wall_relaxation_rate(1.0e-3)
    g_large = wall_relaxation_rate(10.0e-3)
    checks["wall_rate_increases_as_cell_shrinks"] = bool(g_small > g_large)
    checks["wall_rate_quadratic_in_1_over_a"] = bool(
        abs(g_small / g_large - 100.0) < 1e-9)
    checks["coating_suppresses_wall"] = bool(
        wall_relaxation_rate(2.0e-3, coated=True)
        < wall_relaxation_rate(2.0e-3, coated=False))
    checks["buffer_linear_in_pressure"] = bool(
        abs(buffer_gas_rate(200.0) - 2.0 * buffer_gas_rate(100.0)) < 1e-9)
    checks["total_is_sum_of_sources"] = bool(
        abs(total_relaxation_rate() - (wall_relaxation_rate() + buffer_gas_rate())) < 1e-12)
    rep = microcell_report()
    checks["report_anchor_status_none"] = bool(rep["anchor_status"] == "none")
    checks["report_penalty_gt_one"] = bool(rep["miniaturization_penalty"] > 1.0)
    checks["report_sensitivity_scale_positive"] = bool(sensitivity_scale() > 0.0)
    checks["reverse_bad_cell_raises"] = _raises(lambda: wall_relaxation_rate(0.0))
    checks["reverse_bad_pressure_raises"] = _raises(lambda: diffusion_coefficient(0.0))
    checks["reverse_bad_caliber_raises"] = _raises(lambda: assert_caliber("x"))
    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    sc = selfcheck_qs_j4_microcell()
    bad = 0
    print("=" * 64)
    print("J4-M1 芯片级 OPM 微型化自检（锚净增 0 · 如实登记）：")
    for k, v in sc.items():
        ok = bool(v)
        bad += 0 if ok else 1
        print("  [%s] %s" % ("PASS" if ok else "FAIL", k))
    print("=" * 64)
    print("ALL PASS" if bad == 0 else "%d FAIL" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
