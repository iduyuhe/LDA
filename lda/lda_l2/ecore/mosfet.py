# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E1 · NMOS 长沟道紧凑模型（Level-1 / Shichman–Hodges 平方律）。

============================================================================
设计定位（吃狗粮：平台此前**没有晶体管级模型**，电子域只到行为级）
----------------------------------------------------------------------------
本模块是电子计算芯片征程的第一块基石：把「晶体管」从「黑箱」推进到**可仿真**的
长沟道平方律模型。它给出 MOSFET 的本构关系 Id(Vgs, Vds, Vsb) 与**小信号参数**
gm / gds，供 `ecore.mna` 的牛顿迭代当伴随模型使用。

主权纪律（与全平台同源）：
  · C 级自主（纯 numpy），不借任何商业 SPICE 引擎（HSPICE/Spectre）；
  · LLM 不进判决路径；
  · 本包**主动限定在电路级**（设计取舍，非红线要求）：本模块是**电路级晶体管模型**。
    平台红线为**分层口径**（2026-09-11 §八§九 · 2026-09-23 逐步解锁）：**器件级 T1 内核已解锁**
    （`lda_solver/drift_diffusion_1d/2d`）；**T2 工艺真值 / 工艺角 / 流片永久锁**。

模型（长沟道平方律，含沟道长度调制 λ，源=体 Vsb=0 简化）：
  Vgs < Vth                  → 截止：Id = 0
  Vgs ≥ Vth 且 Vds < Vov     → 三极管：Id = KP·(W/L)·(Vov·Vds − Vds²/2)·(1+λ·Vds)
  Vgs ≥ Vth 且 Vds ≥ Vov     → 饱和：Id = ½·KP·(W/L)·Vov²·(1+λ·Vds)
  其中 Vov = Vgs − Vth（过驱动电压）。

导数（伴随模型供牛顿线性化，均为解析闭式）：
  gm  = ∂Id/∂Vgs ， gds = ∂Id/∂Vds ， gmb = ∂Id/∂Vsb（本简化 Vsb=0 ⇒ gmb 另算，暂不耦合体）。

🔴 诚实边界：这是**设计层长沟道教学级模型**，不是 PDK 物理模型；参数（KP/Vth/λ）
是**公开典型量级占位**，非真实工艺标定。本模块**没有实测锚** ⇒ 结论只可用于
模型自洽与电路仿真能力验证，**不得**作器件性能宣称。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple


# ---------------------------------------------------------------------------
# NMOS 参数规格（占位典型量级，非 PDK）
# ---------------------------------------------------------------------------
@dataclass
class NmosParams:
    """长沟道 NMOS 参数（占位）。

    KP   = µ·Cox 跨导参数 (A/V²)；Vth0 = 零偏阈值电压 (V)；
    LAMBDA = 沟道长度调制系数 (1/V)；W/L = 宽长比。
    """

    kp: float = 120e-6          # µCox ≈ 120 µA/V²（长沟道 Si 典型量级）
    vth0: float = 0.4           # 阈值电压 (V)
    lam: float = 0.02           # 沟道长度调制 (1/V)
    w_over_l: float = 10.0      # 宽长比 W/L

    def with_wl(self, wl: float) -> "NmosParams":
        """返回宽长比改为 wl 的副本（不改自身）。"""
        c = NmosParams(kp=self.kp, vth0=self.vth0, lam=self.lam, w_over_l=wl)
        return c


# ---------------------------------------------------------------------------
# 本构关系 + 小信号（解析闭式）
# ---------------------------------------------------------------------------
def id_gm_gds(vgs: float, vds: float, p: NmosParams) -> Tuple[float, float, float]:
    """NMOS 长沟道平方律：返回 (Id, gm, gds)，给定 Vgs/Vds（源=体=0 参考）。

    三区解析：截止 / 三极管 / 饱和；导数均为闭式，供牛顿伴随模型与 AC 小信号。
    """
    vth = p.vth0
    k = p.kp * p.w_over_l
    vov = vgs - vth
    if vov <= 0.0:
        return 0.0, 0.0, 0.0                     # 截止
    if vds < vov:                                 # 三极管
        id_ = k * (vov * vds - 0.5 * vds * vds) * (1.0 + p.lam * vds)
        gm = k * vds * (1.0 + p.lam * vds)
        gds = (k * (vov - vds) * (1.0 + p.lam * vds)
               + k * (vov * vds - 0.5 * vds * vds) * p.lam)
        return id_, gm, gds
    # 饱和
    id_ = 0.5 * k * vov * vov * (1.0 + p.lam * vds)
    gm = k * vov * (1.0 + p.lam * vds)
    gds = 0.5 * k * vov * vov * p.lam
    return id_, gm, gds


def id_saturation_closed(vgs: float, p: NmosParams) -> float:
    """饱和区漏极电流闭式（golden 反证用）：Id = ½·KP·(W/L)·(Vgs−Vth)²。

    取 λ=0 的**纯平方律**口径（与 `id_gm_gds` 在 λ=0 时逐位一致），用于
    突变探针与闭式 golden 对照——避免把 λ 当成误差源。
    """
    vov = vgs - p.vth0
    if vov <= 0.0:
        return 0.0
    return 0.5 * p.kp * p.w_over_l * vov * vov


def vdsat(vgs: float, p: NmosParams) -> float:
    """饱和电压 Vdsat = max(0, Vgs − Vth)（长沟道）。"""
    return max(0.0, vgs - p.vth0)


# ---------------------------------------------------------------------------
# 模型层自证（与全平台「golden 须闭式物理律」同源）
# ---------------------------------------------------------------------------
def mosfet_self_check(seed: int = 20260930) -> dict:
    """模型层自证：平方律三区 + 与闭式 golden 对拍 + 导数边界。

    不引入任何外部 ORACLE——golden 即上方闭式 `id_saturation_closed`，同源于
    长沟道平方律；本自检证明**本模块与自身闭式一致**（自证桩，成熟度 self_certified，
    不冒充方法学独立/实证锚）。
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    p = NmosParams()
    worst_sat = 0.0
    n_ok = 0
    for _ in range(64):
        vgs = p.vth0 + rng.uniform(0.05, 1.0)
        vds = vgs - p.vth0 + 0.2                  # 保证在饱和区
        idv, gm, gds = id_gm_gds(vgs, vds, p)
        gold = id_saturation_closed(vgs, p) * (1.0 + p.lam * vds)
        worst_sat = max(worst_sat, abs(idv - gold))
        if abs(idv - gold) < 1e-12:
            n_ok += 1
    # 截止区：Vgs < Vth ⇒ Id=0
    id_off, _, _ = id_gm_gds(p.vth0 - 0.1, 1.0, p)
    # 三极管→饱和边界连续：Vds=Vov 处三极管与饱和 Id 一致
    vgs = 1.0
    vov = vgs - p.vth0
    id_tri, _, _ = id_gm_gds(vgs, vov - 1e-9, p)   # 三极管侧极限
    id_sat_b, _, _ = id_gm_gds(vgs, vov + 1e-9, p)  # 饱和侧极限
    return {
        "params": {"kp": p.kp, "vth0": p.vth0, "lam": p.lam, "w_over_l": p.w_over_l},
        "saturation_vs_closed_form_max_abs_err": float(worst_sat),
        "saturation_points_in_agreement": n_ok,
        "cutoff_id": float(id_off),
        "triode_sat_boundary_continuity_abs_err": float(abs(id_tri - id_sat_b)),
        "note": "自证桩：本模块与自身闭式平方律一致（非外部 ORACLE），成熟度 self_certified。",
    }


# 模块级披露（对外引用须携此诚实边界）
MOSFET_DISCLOSURE: dict = {
    "level": "电路级（**本包主动限定**）长沟道平方律晶体管模型；**不碰 Foundry TCAD / 工艺角 / 流片**"
             "（属 T2 真值，永久锁）。平台红线为分层口径（器件级 T1 内核已解锁）。",
    "params_are_typical": "KP/Vth0/λ 是**公开典型量级占位**，非真实 PDK 标定；本模块**无实测锚**。",
    "no_capability_claim": "🔴 不做器件性能宣称：结论只用于模型自洽与电路仿真能力验证。",
    "square_law_scope": "长沟道平方律（含 λ 沟道长度调制）覆盖截止/三极管/饱和三区；不含短沟道效应"
                        "（速度饱和/迁移率退化/DIBL 等）——那是 T2 物理，不在本模块。",
}
