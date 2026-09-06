# -*- coding: utf-8 -*-
"""CPO 硅光 I/O 共封装引擎（D 赛道 · v0.9.41 新增）。

零新物理（三项判据全部由已锚定基元 + 公开标准几何算术推出）：
  ① per_channel_il_dB   每通道插入损耗 = GP-* 已锚定基元 dB 级联
     （与 link / sensor_frontend / GC-CPO-8CH 同源，S1 同构）
  ② bandwidth_density_gbps_mm  海岸线带宽密度 = 单通道速率 / 通道间距（纯几何算术）
  ③ link_margin_db      链路功率余量 = P_tx − IL − 探测器灵敏度（S1 同式）

两道物理护栏（对称夹逼，防「方向性 metric 假绿」——D-67 血案纪律的推广）：
  🔴 **D-67 能量守恒下界**（既有纪律，本引擎直接复用）：
     含 1×2 分束器时 IL ≥ n_yb × 3.0103 dB。方向为 `le`（越小越 PASS）的插损
     若无下界，「算漏了损耗」会被伪装成「设计做得更好」（v0.9.10 血案）。
  🔴 **P-CPO 间距几何下界**（本轮新增，对称防「ge 方向虚报」）：
     通道间距 pitch ≥ 耦合方式决定的物理下界：
       · fau（光纤阵列耦合）      → 125.0 µm（ITU-T G.652 单模光纤**包层直径**
                                     125.0±1.0 µm —— 两根光纤不能重叠，几何必然）
       · grating_array（片间光栅阵列直连，无光纤）
                                → 10.3 µm（ITU-T G.652 **模场直径** MFD@1550nm
                                     10.3±0.4 µm —— 模场重叠即串扰，几何必然）
     ⇒ 密度上界 density ≤ lane_rate×1000/pitch_floor（Gbps/mm）。
       方向为 `ge`（越大越 PASS）的密度若无上界，「把间距写小」会被伪装成
       「密度做得更高」——与 D-67 完全对称的假绿通道，必须堵死。

🔴 诚实边界（本引擎**不**做的事，禁止事后补票）：
  · **不判决能效 pJ/bit**。该量由**电域** SerDes/TIA/DSP 主导（OIF 公开表：
    CPO ≈3 pJ/b vs OSFP ≈19 pJ/b，oiforum.com OIF_EEI_Panel_OFC26.pdf），
    而 LDA 无电域锚 —— 若拿光域激光器功率去比 3 pJ/b，复现值会低 4 个数量级
    导致**恒过**（必假绿，等同自证桩）。故能效只作规格标注，不进判决。
  · **密度口径**为「单排 1D 海岸线」= lane_rate / pitch，与 OIF/UCIe 的 **2D
    凸点阵列**口径（如 UCIe 32G@95 µm pitch 记为 2.0 Tbps/mm）**不可直接比较**。
    公开量级引用时一律标注口径。
  · EIC/驱动器/激光器按黑箱（有源不物理级建模，负面清单）。

公开溯源（golden 与物理常数）：
  · ITU-T G.652（2024 第 10 版）：包层直径 125.0 µm；MFD@1550nm 10.3 µm。
  · Semiconductor Engineering：光纤间距「fiber pitches often exceed 100 microns」；
    当前最先进 CPO ≈0.5 Tbps/mm，AI chiplet（UCIe/OIF）≈3 Tbps/mm。
  · OIF EEI Panel OFC26 官方表：CPO 3 pJ/b @ 2.0 Tbps/mm；OSFP 19 pJ/b @ 0.2 T/mm。
  · OIF-Co-Packaging-3.2T-Module-01.0：3.2T 引擎 = 32×112G-XSR 电 + 8×400G 光口。
"""
from __future__ import annotations

import math
from typing import Any, Dict

from lda_design.loss_engines import ENGINE_FUNCS, SPLIT_LOSS_3DB

# ---------------------------------------------------------------------------
# 物理常数（公开标准几何，非经验拟合）
# ---------------------------------------------------------------------------
# ITU-T G.652 单模光纤包层直径（两根光纤不能重叠 ⇒ 光纤阵列 pitch 的几何下界）
FIBER_CLADDING_UM = 125.0
# ITU-T G.652 模场直径 @1550 nm（模场重叠即串扰 ⇒ 光栅阵列 pitch 的几何下界）
FIBER_MFD_1550_UM = 10.3

# 耦合方式 → 通道间距物理下界（µm）
PITCH_FLOOR_UM: Dict[str, float] = {
    "fau": FIBER_CLADDING_UM,        # 光纤阵列（V 槽 FAU）耦合
    "grating_array": FIBER_MFD_1550_UM,  # 片间光栅阵列直连（无光纤）
}

# 标准基元几何（与 GP-* / GC-* 标杆一致，保证级联复现值同源）
# ⚠️ 与 proposal_compiler._design_sensor_frontend 内联常量同源重复，
#    保持逐字一致；后续应收敛到单一定义处（重构属独立任务，此处不动）。
_G_GEOM = {"ff": 0.5, "theta_deg": 8.0, "tilt_sigma_deg": 15.0}
_SIN_GEOM = {"w_core_um": 0.8, "h_core_um": 0.8, "roughness_nm": 0.3}
_YB_GEOM = {"theta_deg": 5.0, "excess_coef": 0.004}
_CR_GEOM = {"w_core_um": 0.5, "taper_w_ratio": 2.5}

# 默认几何（8×200G CPO 光引擎，标准 250 µm FAU pitch）
DEFAULT_GEOM: Dict[str, Any] = {
    "couple_mode": "fau",
    "n_channels": 8,
    "lane_rate_gbps": 200.0,
    "pitch_um": 250.0,
    "n_gratings": 2,
    "wg_length_cm": 1.0,
    "n_ybranch": 1,
    "n_crossing": 1,
    "p_tx_dbm": 0.0,
    "detector_sens_dbm": -20.0,
}


def cpo_optical_io_metrics(geom: Dict[str, Any]) -> Dict[str, Any]:
    """CPO 硅光 I/O 三死标量 + 两道物理护栏。

    geom：
      couple_mode        "fau"（光纤阵列，默认）/ "grating_array"（片间光栅直连）
      n_channels         通道数（默认 8）
      lane_rate_gbps     单通道速率 Gbps（默认 200）
      pitch_um           通道间距 µm（默认 250；须 ≥ 耦合方式物理下界）
      n_gratings/wg_length_cm/n_ybranch/n_crossing  级联组成（GP-* 同源）
      p_tx_dbm           发射光功率 dBm（默认 0）
      detector_sens_dbm  探测器灵敏度 dBm（默认 −20）

    返回：per_channel_il_dB / bandwidth_density_gbps_mm / link_margin_db
          + 护栏证据（pitch_floor_um / density_ceiling_gbps_mm / energy_floor_dB）
          + 几何摘要（shoreline_width_mm / total_bandwidth_tbps / couple_mode）
    """
    g = {**DEFAULT_GEOM, **(geom or {})}

    couple_mode = str(g.get("couple_mode", "fau")).lower()
    if couple_mode not in PITCH_FLOOR_UM:
        raise AssertionError(
            f"[CPO] 未知耦合方式 {couple_mode!r}；可用：{sorted(PITCH_FLOOR_UM)}"
            f"——未知耦合方式无物理下界可守，按『宁红不假绿』直接判不可运行")

    n_ch = int(g["n_channels"])
    lane = float(g["lane_rate_gbps"])
    pitch = float(g["pitch_um"])
    n_g = int(g["n_gratings"])
    L = float(g["wg_length_cm"])
    n_yb = int(g["n_ybranch"])
    n_cr = int(g["n_crossing"])

    # ---- ① 每通道插入损耗（GP-* 已锚定基元 dB 级联，与 GC-CPO-8CH 同源） ----
    grating_il = -10.0 * math.log10(
        ENGINE_FUNCS["engine_grating_eff"](_G_GEOM)["value"])
    sil = ENGINE_FUNCS["engine_sin_pl"](_SIN_GEOM)["value"]
    yb = ENGINE_FUNCS["engine_ybranch_split"](_YB_GEOM)["value"]
    cr = ENGINE_FUNCS["engine_crossing"](_CR_GEOM)["value"]
    total = n_g * grating_il + sil * L + n_yb * yb + n_cr * cr

    # 🔴 护栏一：D-67 能量守恒下界（分束器每级 ≥ 3.0103 dB，逐项守底）
    if n_yb > 0 and yb < SPLIT_LOSS_3DB - 1e-9:
        raise AssertionError(
            f"[CPO] 分束器单级插损 {yb:.4f} dB 低于能量守恒下界 "
            f"{SPLIT_LOSS_3DB:.4f} dB（1×2 功率均分的几何必然）——"
            f"疑似漏算分光损耗（见 D-67 回归）")
    energy_floor = n_yb * SPLIT_LOSS_3DB
    if total < energy_floor - 1e-9:
        raise AssertionError(
            f"[CPO] 链路插损 {total:.4f} dB 低于能量守恒下界 "
            f"{energy_floor:.4f} dB（{n_yb} 级 1×2 分光 × 3.0103 dB）——"
            f"疑似漏算分光损耗（见 D-67 回归）")

    # ---- ② 海岸线带宽密度（纯几何算术 + P-CPO 间距物理下界） ----
    pitch_floor = PITCH_FLOOR_UM[couple_mode]
    if pitch < pitch_floor - 1e-9:
        _why = ("单模光纤包层直径（ITU-T G.652）——两根光纤不能重叠"
                if couple_mode == "fau" else
                "模场直径 MFD@1550nm（ITU-T G.652）——模场重叠即串扰")
        raise AssertionError(
            f"[CPO:{couple_mode}] 通道间距 {pitch:.4f} µm 低于几何下界 "
            f"{pitch_floor:.4f} µm（{_why}，几何必然）——"
            f"疑似虚报带宽密度（见 P-CPO 回归）")
    # 1D 单排海岸线口径：每通道占 pitch 宽度 ⇒ 密度 = lane_rate / pitch
    density = lane * 1000.0 / pitch                    # Gbps/mm
    density_ceiling = lane * 1000.0 / pitch_floor      # Gbps/mm（物理上界）
    if density > density_ceiling + 1e-9:
        raise AssertionError(
            f"[CPO:{couple_mode}] 带宽密度 {density:.4f} Gbps/mm 超过物理上界 "
            f"{density_ceiling:.4f} Gbps/mm（间距不可小于 {pitch_floor:.4f} µm）——"
            f"疑似绕过间距下界虚报密度（见 P-CPO 回归）")

    # ---- ③ 链路功率余量（S1 同式：P_tx − IL − P_sens） ----
    p_tx = float(g["p_tx_dbm"])
    p_sens = float(g["detector_sens_dbm"])
    margin = p_tx - total - p_sens

    shoreline_mm = n_ch * pitch / 1000.0
    total_bw_tbps = n_ch * lane / 1000.0

    return {
        # 三死标量（判决用）
        "per_channel_il_dB": round(total, 4),
        "bandwidth_density_gbps_mm": round(density, 4),
        "link_margin_db": round(margin, 4),
        # 护栏证据（人审用：物理下界/上界当场披露）
        "energy_floor_dB": round(energy_floor, 4),
        "pitch_floor_um": round(pitch_floor, 4),
        "density_ceiling_gbps_mm": round(density_ceiling, 4),
        # 几何摘要
        "couple_mode": couple_mode,
        "n_channels": n_ch,
        "lane_rate_gbps": lane,
        "pitch_um": round(pitch, 4),
        "shoreline_width_mm": round(shoreline_mm, 4),
        "total_bandwidth_tbps": round(total_bw_tbps, 4),
        "model": "CPO 光 I/O（GP-* 级联 + 几何密度 + S1 预算）",
    }


__all__ = [
    "FIBER_CLADDING_UM", "FIBER_MFD_1550_UM", "PITCH_FLOOR_UM", "DEFAULT_GEOM",
    "cpo_optical_io_metrics",
]
