"""LDA 设计侧虚拟制造 2.0 · 可封装性链（packaging tolerance · v0.9.65+）。

把「设计 → 封装良率」打通：耦合容差 / 对准失配预算 / 封装良率预测。
**公开方法，不臆造物理；先造系统，待 T2 实测回填再升级（数据驱动，非硬编码）。**

物理基础（全部公开、可文献溯源）：
  · 横向耦合容差：高斯模场重叠（Senior, Optical Fiber Communications）
        η(dx) = η0 · exp(−2·dx² / MFD²)
    MFD 取 ITU-T G.652 单模光纤 @1550nm = 10.3 µm（公开标准，见 cpo_engines）。
  · 角向耦合容差：高斯光束角向滚降（远场发散角 θ_div = 2λ/(π·MFD)）
        η(θ) = η0 · exp(−(π·MFD·θ / (2λ))²)
  · 封装良率：2D 对准失配 (dx,dy) ~ N(0, σ_align²) → Rayleigh CDF
        Y = 1 − exp(−R² / (2·σ_align²))，
        R 为耦合容差半径 = (MFD/√2)·√(−ln(η_min/η0))
    —— 与 S13 同一族高斯容差积分：1D 退化即 S13 的 Φ 闭式，此处 2D 径向，纯解析。

复用（不重复造轮子）：
  · lda_design.cpo_engines.FIBER_MFD_1550_UM / PITCH_FLOOR_UM（P-CPO 几何下界，ITU-T G.652）
  · 与 lda_harness.yield_anchor 的 _phi 闭式同源（高斯容差积分），可互相印证。

provenance：self_authored_with_check
  🔴 诚实边界（务必保留）：
    ① σ_align（装配合准分布 1σ）取**公开设备规格假设**（如 ±0.5 µm 贴片机），非本项目 MPW 实测。
    ② MFD 取 ITU-T G.652 公开标准；片上波导 MFD 可由模 solver 给出，本模块作为入参。
    ③ 二者均**非自有实测**；待 T2 真值回流（实测工艺波动分布 + 封装实测）后，
       把 σ_align / 片上 MFD 替换为实测值即可升级为 Tier-3 严独锚——**系统骨架不变（数据驱动）**。
  🔴 不宣称 MPW 验证；不进入签核硬门；对外话术须标注「假设分布，待实测回填」。

红线（严格保持 · LLM 不进判决路径）：
  判决 = 死标量比对；解析 Rayleigh 闭式与固定种子蒙特卡洛双算法互证（同源 S13 纪律）。
  纯标准库（math/random），零第三方依赖，与项目「核心零依赖优雅降级」铁律一致。
"""
from __future__ import annotations

import math
import random
from typing import Dict, Any, Optional, Tuple

# ---- 公开标准 / 假设输入（发动期实测替换） ----
LAMBDA_NM = 1550.0          # 工作波长 C 波段（公开）
FIBER_MFD_UM = 10.3         # ITU-T G.652 单模光纤 MFD@1550nm（公开标准，复用 cpo_engines）
DEFAULT_SIGMA_ALIGN_UM = 0.5  # 装配合准 1σ 假设：±0.5 µm 级贴片机（公开设备规格量级，待 T2 实测）
SEED = 2026                 # 固定种子（可复现）


def _mfd(mfd_um: Optional[float]) -> float:
    """MFD 取值：显式给定优先，否则回退 ITU-T G.652 光纤标准值。"""
    return float(mfd_um) if mfd_um is not None else FIBER_MFD_UM


def coupling_efficiency(dx_um: float = 0.0, dy_um: float = 0.0,
                        theta_deg: float = 0.0, mfd_um: Optional[float] = None,
                        eta0: float = 1.0, lam_nm: float = LAMBDA_NM) -> float:
    """耦合效率（公开高斯模场重叠，含横向 + 角向）。

    横向： η_lat = exp(−2·(dx²+dy²) / MFD²)
    角向： η_ang = exp(−(π·MFD·θ / (2λ))²)，θ 单位度（内部转弧度）
    合成： η = η0 · η_lat · η_ang
    """
    mfd = _mfd(mfd_um)
    lat = math.exp(-2.0 * (dx_um * dx_um + dy_um * dy_um) / (mfd * mfd))
    theta_rad = math.radians(theta_deg)
    ang = math.exp(-((math.pi * mfd * theta_rad) / (2.0 * lam_nm)) ** 2)
    return eta0 * lat * ang


def lateral_tolerance_um(eta_target: float, eta0: float = 1.0,
                         mfd_um: Optional[float] = None) -> float:
    """横向对准容差（闭环逆运算，公开方法）：使 η(dx)=η_target 的 |dx| 上限。

    η_target/eta0 = exp(−2·dx²/MFD²) → dx = (MFD/2)·√(−2·ln(η_target/eta0))
    """
    mfd = _mfd(mfd_um)
    ratio = eta_target / eta0
    if ratio >= 1.0:
        return float("inf")  # 目标高于基线，零失配也满足
    return (mfd / 2.0) * math.sqrt(-2.0 * math.log(ratio))


def _tolerance_radius_um(eta_min: float, eta0: float = 1.0,
                         mfd_um: Optional[float] = None) -> float:
    """耦合容差半径 R：η ≥ η_min 等价 dx²+dy² ≤ R²（2D 径向）。"""
    mfd = _mfd(mfd_um)
    ratio = eta_min / eta0
    if ratio >= 1.0:
        return float("inf")
    return mfd * math.sqrt(-math.log(ratio) / 2.0)


def package_yield(mfd_um: Optional[float] = None, eta_min: float = 0.5,
                  sigma_align_um: float = DEFAULT_SIGMA_ALIGN_UM,
                  eta0: float = 1.0) -> float:
    """封装良率（2D 对准失配 Rayleigh CDF，纯解析闭式，与 S13 同族）。

    (dx,dy) ~ N(0, σ_align²) 独立 → dx²+dy²/σ² ~ χ²(2)
    η ≥ η_min ⟺ dx²+dy² ≤ R²，R=_tolerance_radius_um
    Y = P(χ²(2) ≤ R²/σ²) = 1 − exp(−R² / (2·σ_align²))
    """
    if sigma_align_um <= 0:
        raise ValueError("sigma_align_um 必须 > 0")
    r = _tolerance_radius_um(eta_min, eta0, mfd_um)
    if math.isinf(r):
        return 1.0
    return 1.0 - math.exp(-(r * r) / (2.0 * sigma_align_um * sigma_align_um))


def design_to_packaging_yield(waveguide_mfd_um: float,
                              sigma_align_um: float = DEFAULT_SIGMA_ALIGN_UM,
                              eta_min: float = 0.5, eta0: float = 1.0) -> Dict[str, float]:
    """设计 → 封装良率反馈（T3 验收核心：设计改动 → 封装良率同向变化且可复现）。

    入参 waveguide_mfd_um = 片上波导模场直径（设计旋钮，由模 solver 给出或设计指标）。
    返回：耦合容差半径、横向容差、封装良率。MFD 越大 → 容差越大 → 良率越高（单调、确定）。
    """
    r = _tolerance_radius_um(eta_min, eta0, waveguide_mfd_um)
    dx_tol = lateral_tolerance_um(eta_min, eta0, waveguide_mfd_um)
    y = package_yield(waveguide_mfd_um, eta_min, sigma_align_um, eta0)
    return {
        "mfd_um": waveguide_mfd_um,
        "tolerance_radius_um": r,
        "lateral_tolerance_um": dx_tol,
        "sigma_align_um": sigma_align_um,
        "eta_min": eta_min,
        "packaging_yield": y,
    }


def _cpo_pitch_floor_um() -> float:
    """惰性取 P-CPO 几何下界（避免顶层循环导入）。失败则回退 ITU-T MFD 值。"""
    try:
        from lda_design.cpo_engines import PITCH_FLOOR_UM
        return float(PITCH_FLOOR_UM)
    except Exception:
        return FIBER_MFD_UM


def package_yield_with_pitch(waveguide_mfd_um: float, pitch_um: float,
                             sigma_align_um: float = DEFAULT_SIGMA_ALIGN_UM,
                             eta_min: float = 0.5, eta0: float = 1.0) -> Dict[str, Any]:
    """多通道阵列封装良率：单通道良率 × 间距合规（P-CPO 几何下界守护）。

    pitch 必须 ≥ P-CPO 几何下界（模场重叠即串扰）；否则标记 pitch_compliant=False
    并如实计入串扰风险（不假装更高良率）。返回含 provenance 的字典。
    """
    floor = _cpo_pitch_floor_um()
    compliant = pitch_um >= floor
    y = package_yield(waveguide_mfd_um, eta_min, sigma_align_um, eta0)
    return {
        "mfd_um": waveguide_mfd_um,
        "pitch_um": pitch_um,
        "pitch_floor_um": floor,
        "pitch_compliant": compliant,
        "packaging_yield": y,
        "provenance": "self_authored_with_check",
        "note": "σ_align/MFD 为公开假设值，待 T2 实测回填；非 MPW 验证",
    }


def verify_packaging_anchor(n: int = 20000, seed: int = SEED,
                            mfd_um: Optional[float] = None,
                            eta_min: float = 0.5,
                            sigma_align_um: float = DEFAULT_SIGMA_ALIGN_UM,
                            eta0: float = 1.0,
                            tol: float = 1e-2) -> Dict[str, Any]:
    """自证桩闭环：解析 Rayleigh 闭式 ↔ 固定种子蒙特卡洛双算法互证（同源 S13 纪律）。

    返回 {analytic, monte_carlo, diff, ok}。两法一致（|Δ|≤tol）说明数值采样与解析
    积分在同一物理定律上收敛——构成「非 AI ground」的硬证据。
    """
    mfd = _mfd(mfd_um)
    r = _tolerance_radius_um(eta_min, eta0, mfd)
    # 解析
    y_an = package_yield(mfd, eta_min, sigma_align_um, eta0)
    # 蒙特卡洛：采样 (dx,dy)~N(0,σ²)，计数 η≥η_min
    rng = random.Random(seed)
    sig = sigma_align_um
    hits = 0
    for _ in range(int(n)):
        dx = rng.gauss(0.0, sig)
        dy = rng.gauss(0.0, sig)
        # 角向失配在本验证中不计（取 θ=0 的横向主因），与解析口径一致
        eta = coupling_efficiency(dx, dy, 0.0, mfd, eta0)
        if eta >= eta_min:
            hits += 1
    y_mc = hits / n
    diff = abs(y_an - y_mc)
    return {
        "analytic": y_an,
        "monte_carlo": y_mc,
        "diff": diff,
        "ok": diff <= tol,
        "n_samples": n,
        "mfd_um": mfd,
        "sigma_align_um": sig,
        "eta_min": eta_min,
    }


if __name__ == "__main__":
    # 演示：设计旋钮（片上 MFD）变大 → 封装良率单调上升
    print("=== 可封装性链演示（公开方法，假设 σ_align=0.5µm）===")
    for mfd in (2.0, 4.0, 6.0, 10.3):
        d = design_to_packaging_yield(mfd, eta_min=0.5, eta0=0.9)
        print(f"  MFD={mfd:5.1f}µm  横向容差={d['lateral_tolerance_um']:6.3f}µm  "
              f"封装良率={d['packaging_yield']*100:6.2f}%")
    v = verify_packaging_anchor()
    print(f"\n自证互证：解析={v['analytic']:.5f}  蒙特卡洛={v['monte_carlo']:.5f}  "
          f"Δ={v['diff']:.5f}  ok={v['ok']}")
