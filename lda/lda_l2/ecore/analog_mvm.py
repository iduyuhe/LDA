# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E1 · 最小模拟计算单元（反向求和 MAC = MVM 基本砖）。

============================================================================
设计定位（电子版的「光子 MZI 网格」起点）
----------------------------------------------------------------------------
一个**反相求和运放** Vout = −Σ (Rf/Ri)·Vi 就是模拟矩阵-向量乘的最基本砖
（对 2 输入，即 2×1 的 W = [−Rf/R1, −Rf/R2]）。电子计算芯片征程（E1）先用
理想运放（超大增益 VCVS）把「计算」跑通；E2 再用晶体管级 OTA 替换理想运放、
扩成 N×N 交叉阵列。

同时提供 NMOS 饱和偏置检查：端到端验证 `mna` + `mosfet` 的「晶体管级仿真」链路
（平台此前完全没有）。

主权纪律（全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；%
golden 须闭式物理律。
"""
from __future__ import annotations

import numpy as np

from .mna import Circuit
from .mosfet import NmosParams, id_gm_gds


# ---------------------------------------------------------------------------
# ① 反向求和 MAC（理想运放建模为超大增益 VCVS）
# ---------------------------------------------------------------------------
def inverting_summer_golden(vin1: float, vin2: float, r1: float, r2: float,
                            rf: float) -> float:
    """闭式 golden：Vout = −Rf·(Vin1/R1 + Vin2/R2)。"""
    return -rf * (vin1 / r1 + vin2 / r2)


def inverting_summer(vin1: float, vin2: float, r1: float, r2: float, rf: float,
                     gain: float = 1e6) -> dict:
    """用 MNA 仿真一个 2 输入反相求和器，返回 Vout 与中间节点电压。

    节点：0=地，1=输出(Vout)，2=反相输入(V−)，3=Vin1 源正端，4=Vin2 源正端。
    V+ = 0（接地）；VCVS：V(1)−V(0) = gain·(V(0)−V(2)) ⇒ Vout = −gain·V2。
    """
    ckt = Circuit("inverting_summer")
    ckt.vsource(3, 0, vin1, "Vin1")
    ckt.vsource(4, 0, vin2, "Vin2")
    ckt.resistor(3, 2, r1, "R1")
    ckt.resistor(4, 2, r2, "R2")
    ckt.resistor(1, 2, rf, "Rf")
    ckt.vcvs(1, 0, 0, 2, gain, "opamp")     # Vout = gain·(V+ − V−) = −gain·V2
    x = ckt.solve_dc()
    nv = ckt.node_voltages(x)
    return {
        "vout": nv[1],
        "v_minus": nv[2],          # 虚地 ≈ 0
        "vin1_node": nv[3],
        "vin2_node": nv[4],
        "gain": gain,
        "golden": inverting_summer_golden(vin1, vin2, r1, r2, rf),
    }


# ---------------------------------------------------------------------------
# ② NMOS 饱和偏置（端到端验证 MNA + MOSFET 链路）
# ---------------------------------------------------------------------------
def mosfet_saturation_golden(vdd: float, r: float, p: NmosParams) -> dict:
    """闭式求解 NMOS 饱和偏置交点（含 λ），返回 Vd / Id。

    方程：Id = (Vdd − Vd)/R = ½·KP·(W/L)·(Vgs−Vth)²·(1+λ·Vd)，Vgs = Vdd（栅=Vdd）。
    令 Vov = Vdd − Vth，a = ½·KP·(W/L)·Vov²：
      a·(1 + λ·Vd) = (Vdd − Vd)/R
      ⇒ Vd = (Vdd/R − a) / (a·λ + 1/R)
    要求 Vd ≥ Vov（确在饱和区），否则 golden 不适用（调用方应保证）。
    """
    k = p.kp * p.w_over_l
    vov = vdd - p.vth0
    a = 0.5 * k * vov * vov
    vd = (vdd / r - a) / (a * p.lam + 1.0 / r)
    id_ = (vdd - vd) / r
    return {"vd": vd, "id": id_, "vov": vov, "in_saturation": bool(vd >= vov)}


def mosfet_saturation_bias(vdd: float, r: float, p: NmosParams) -> dict:
    """用 MNA 仿真一个二极管接法偏置的 NMOS（栅=漏=Vdd 经电阻），返回 Vd / Id。

    节点：0=地，1=漏(Vd)，2=栅，3=Vdd 源正端。栅经电阻接 Vdd（栅电流 0 ⇒ 栅=Vdd）。
    漏经电阻 R 接 Vdd。源=地。在饱和区 Vgs=Vdd, Vds=Vd，Id=(Vdd−Vd)/R。
    初值：栅=Vdd、漏=Vdd/2（确保设备导通，避免牛顿卡在截止零解）。
    """
    ckt = Circuit("nmos_bias")
    ckt.vsource(3, 0, vdd, "Vdd")
    ckt.resistor(3, 2, 1e6, "Rg")          # 栅偏置电阻（栅电流≈0 ⇒ 栅=Vdd）
    ckt.resistor(3, 1, r, "Rd")            # 漏负载
    ckt.nmos(1, 2, 0, p, "M1")
    x = ckt.solve_dc(v0={2: vdd, 1: vdd / 2.0})
    nv = ckt.node_voltages(x)
    vd, vg = nv[1], nv[2]
    id_mna = (vdd - vd) / r                 # 负载电流 = 漏电流
    id_model, _, _ = id_gm_gds(vg - 0.0, vd - 0.0, p)
    return {
        "vd": vd, "vg": vg, "id_from_load": id_mna, "id_from_model": id_model,
        "golden": mosfet_saturation_golden(vdd, r, p),
    }
