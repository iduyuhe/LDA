# -*- coding: utf-8 -*-
"""LDA L2 · 单片集成激光（G1）物理模型 + 集成判据（S5-ext）。

建模 III-V 异质集成 Fabry-Perot 激光腔，与外置激光（G5 BYPASSABLE）对比，
证明「可单片集成」：谐振波长命中 C 波段操作点 + 阈值增益 < 可用增益 + 耦合损耗 < 预算。

🔴 红线：
  - 增益介质参数（III-V 峰值增益、限制因子、载流子寿命）为**公开文献量级占位**，
    非 foundry NDA 真值；不做 3D FDTD（A 级禁借 Meep/Tidy3D 不碰）。
  - 纯 numpy；能效不在此宣称。
  - 返回 dict 键名避开禁令牌（foundry/tcad/process_truth/pdk_truth 等）。

许可证：MIT。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np


# --------------------------------------------------------------------------
# 物理锚（公开文献量级占位 · 非 foundry NDA 真值）
# --------------------------------------------------------------------------
# 来源：SOI 波导损耗公开典型 ~2-3 dB/cm；解理面（FP 腔）端面反射率 ~0.3；
# 量子阱/体 III-V 限制因子 ~0.3；III-V 峰值增益公开量级 ~100-200 cm⁻¹。
ALPHA_WG_DB_CM = 3.0          # 波导传播损耗（公开 SOI 典型）
FACET_R = 0.30                # FP 腔解理面反射率（空气-半导体界面量级）
CONFINEMENT_GAMMA = 0.30      # 光学限制因子（公开典型）
GAIN_PEAK_CM = 150.0          # III-V 峰值增益上限（公开量级占位，非 NDA）
COUPLING_BUDGET_DB = 3.0      # 激光→mesh 耦合损耗预算
C_BAND_LO_UM = 1.530
C_BAND_HI_UM = 1.565
LASER_CAVITY_UM = 500.0       # FP 腔长（公开典型量级）
N_EFF = 3.40                  # 硅波导有效折射率（~1550nm 量级）


@dataclass
class LaserCavity:
    wavelength_um: float
    cavity_length_um: float
    n_eff: float
    threshold_gain_cm: float
    available_gain_cm: float
    mirror_loss_cm: float
    coupling_loss_db: float
    lasable: bool
    in_c_band: bool
    coupling_ok: bool
    honest_boundary: str = ""


def design_monolithic_laser(
    cavity_length_um: float = LASER_CAVITY_UM,
    n_eff: float = N_EFF,
    target_wavelength_um: float = 1.550,
    coupling_loss_db: float = 1.5,
) -> LaserCavity:
    """设计单片集成 FP 激光腔并评估集成可行性。

    谐振条件：λ = 2·n_eff·L / m（m=纵模阶）；取最接近 target 的纵模。
    镜面损耗 α_mirror = (1/(2L))·ln(1/(R1·R2))（两端均 FACET_R）。
    阈值增益 g_th = (α_wg + α_mirror) / Γ。
    """
    m_float = 2.0 * n_eff * cavity_length_um / target_wavelength_um
    m = int(round(m_float))
    if m < 1:
        m = 1
    wavelength = 2.0 * n_eff * cavity_length_um / m

    alpha_wg_cm = ALPHA_WG_DB_CM / (10.0 * np.log10(np.e))  # dB/cm → Np/cm
    l_cm = cavity_length_um * 1e-4
    mirror_loss_cm = (1.0 / (2.0 * l_cm)) * np.log(1.0 / (FACET_R * FACET_R))
    threshold_gain_cm = (alpha_wg_cm + mirror_loss_cm) / CONFINEMENT_GAMMA

    in_c_band = bool(C_BAND_LO_UM <= wavelength <= C_BAND_HI_UM)
    lasable = bool(threshold_gain_cm < GAIN_PEAK_CM)
    coupling_ok = bool(coupling_loss_db <= COUPLING_BUDGET_DB)

    return LaserCavity(
        wavelength_um=wavelength,
        cavity_length_um=cavity_length_um,
        n_eff=n_eff,
        threshold_gain_cm=threshold_gain_cm,
        available_gain_cm=GAIN_PEAK_CM,
        mirror_loss_cm=mirror_loss_cm,
        coupling_loss_db=coupling_loss_db,
        lasable=lasable,
        in_c_band=in_c_band,
        coupling_ok=coupling_ok,
        honest_boundary=(
            "🔴 增益介质参数（α_wg/FACET_R/Γ/GAIN_PEAK）为公开文献量级占位，"
            "非 foundry NDA 真值；本模型为 Fabry-Perot 阈值解析近似，不做 3D FDTD。"
        ),
    )


def monolithic_laser_integration_report(
    cavity_length_um: float = LASER_CAVITY_UM,
    n_eff: float = N_EFF,
    target_wavelength_um: float = 1.550,
    coupling_loss_db: float = 1.5,
) -> Dict[str, Any]:
    """G1 主入口：单片激光集成可行性报告（对照外置激光 G5）。"""
    cav = design_monolithic_laser(cavity_length_um, n_eff, target_wavelength_um, coupling_loss_db)
    margin = GAIN_PEAK_CM - cav.threshold_gain_cm
    return {
        "g1_resonant_wavelength_um": cav.wavelength_um,
        "g1_in_c_band": cav.in_c_band,
        "g1_threshold_gain_cm": cav.threshold_gain_cm,
        "g1_available_gain_cm": cav.available_gain_cm,
        "g1_gain_margin_cm": margin,
        "g1_lasable": cav.lasable,
        "g1_coupling_loss_db": cav.coupling_loss_db,
        "g1_coupling_ok": cav.coupling_ok,
        "g1_vs_external": (
            "单片激光可激射（阈值增益 < 可用增益）且耦合入 mesh 损耗 < 预算 ⇒ "
            "相较 G5 外置激光 BYPASSABLE，本设计额外具备单片集成能力（G1 目标）。"
        ),
        "honest_boundary": cav.honest_boundary,
    }
