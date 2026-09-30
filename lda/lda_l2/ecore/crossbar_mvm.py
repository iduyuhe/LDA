# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E2 · 参数化 MVM 交叉阵列生成器（D-151）。

============================================================================
设计定位（吃狗粮：电子版的「光子 MZI 网格」—— 用晶体管级模拟单元做矩阵-向量乘）
----------------------------------------------------------------------------
本模块把 E1 的「反相求和 MAC」扩成 **N（输入）× M（输出）的模拟 MVM 交叉阵列**，
直接对标模拟 AI 加速器（Mythic 类）的可编程权重阵列。

两条验证路径（同一 CrossbarMVM 类，`amp` 切换）：
  · amp='ideal'      —— 交叉点电导 + 理想运放(超大增益 VCVS)作 TIA（虚地）。
                        golden = -rf · W @ x，干净、无列间增益差，规模可扩到 8×8+。
  · amp='transistor' —— 交叉点 = NMOS 三极管区作**压控电阻**（栅压=权重 → 电导），
                        列节点用电阻负载做电流-电压转换。真正吃 E1 的 MOSFET 模型，
                        是「晶体管级 MAC 替换理想运放」的诚实落地（权重由晶体管担任）。
                        golden = 列向闭式（含电阻负载的列增益因子，已计入）。

另含 `ota_open_loop_gain`：用 E1 的 NMOS 差分对 + 电阻负载 + 尾电流源表征一个**晶体管级
OTA**的开环增益（增益 ∝ Rd），证明平台能仿真真实放大器；并诚实注明：基础 OTA 要在完整
MVM 摆幅内闭合 TIA 环路需多级缓冲设计，本征程验证路径以理想 TIA / 晶体管权重为准。

主权纪律（全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；golden 俱为闭式物理律；
T1 电路级（不碰 Foundry TCAD/流片）。参数为公开典型量级占位，不宣称器件性能。
"""
from __future__ import annotations

import numpy as np

from .mna import Circuit
from .mosfet import NmosParams


# ---------------------------------------------------------------------------
# 参数化 MVM 交叉阵列
# ---------------------------------------------------------------------------
class CrossbarMVM:
    """参数化 N(输入) × M(输出) 模拟 MVM 交叉阵列。

    约定：weights 形状 (M, N)，weights[o, i] 的物理意义随 amp 而变：
      · amp='ideal'      → 电导 g (Siemens)；golden = -rf · W @ x（vref=0 虚地）。
      · amp='transistor' → 栅压 Wg (V)；线性三极管电导 g_ij = kp·(W/L)·(Wg_ij − Vth)。
    求解后 `outputs` 为长度 M 的电压向量；`golden_outputs()` 为对应闭式。

    🔴 诚实边界：amp='transistor' 的每一列增益 = rload/(1 + rload·Σg_j)，随该列总电导
    变化（电阻负载固有特性，非 TIA 虚地统一增益）；golden 已逐列计入该因子。
    """

    def __init__(self, weights: np.ndarray, inputs: np.ndarray, rf: float = 10e3,
                 amp: str = "ideal", vref: float = 0.0, vdd: float = 10.0,
                 p: NmosParams = None, name: str = "crossbar_mvm"):
        self.weights = np.asarray(weights, dtype=float)
        self.inputs = np.asarray(inputs, dtype=float).reshape(-1)
        if self.weights.shape[1] != self.inputs.shape[0]:
            raise ValueError("weights 列数须等于 inputs 长度")
        self.M, self.N = self.weights.shape
        self.rf = float(rf)
        self.amp = amp
        self.vref = float(vref)
        self.vdd = float(vdd)
        self.p = p or NmosParams()
        self.name = name
        if amp not in ("ideal", "transistor"):
            raise ValueError("amp 仅支持 'ideal' / 'transistor'")

    # —— 构建并返回 MNA 电路（含收敛用初值 v0）——
    def _build(self):
        ckt = Circuit(self.name)
        N, M = self.N, self.M
        rown = {i: i + 1 for i in range(N)}
        coln = {o: N + 1 + o for o in range(M)}
        # 行电压源
        for i in range(N):
            ckt.vsource(rown[i], 0, float(self.inputs[i]), f"Vin{i}")
        if self.amp == "ideal":
            outn = {o: N + M + 1 + o for o in range(M)}
            for o in range(M):
                for i in range(N):
                    g = float(self.weights[o, i])
                    if g <= 0:
                        raise ValueError("ideal 电导须 > 0")
                    ckt.resistor(rown[i], coln[o], 1.0 / g, f"g{o}_{i}")
                ckt.resistor(outn[o], coln[o], self.rf, f"Rf{o}")
                ckt.vcvs(outn[o], 0, 0, coln[o], 1e6, f"OA{o}")
            return ckt, outn, {}
        else:  # transistor：NMOS 三极管区作压控电阻 + 列电阻负载
            p = self.p
            v0 = {}
            gbase = 1_000_000
            for o in range(M):
                v0[coln[o]] = 0.0
                for i in range(N):
                    gnode = gbase + o * 1000 + i
                    wg = float(self.weights[o, i])
                    if wg <= p.vth0:
                        raise ValueError("transistor 栅压须 > Vth0 以进入三极管区")
                    ckt.vsource(gnode, 0, wg, f"Wg{o}_{i}")
                    ckt.nmos(rown[i], gnode, coln[o], p, f"M{o}_{i}")
                ckt.resistor(coln[o], 0, self.rf, f"Rload{o}")
            for i in range(N):
                v0[rown[i]] = float(self.inputs[i])
            return ckt, coln, v0

    def solve(self) -> np.ndarray:
        ckt, outn, v0 = self._build()
        x = ckt.solve_dc(v0=v0 if v0 else None)
        nv = ckt.node_voltages(x)
        return np.array([nv[outn[o]] for o in range(self.M)])

    # —— 闭式 golden（与 amp 对应）——
    def golden_outputs(self) -> np.ndarray:
        if self.amp == "ideal":
            return -self.rf * (self.weights @ self.inputs)
        # transistor：逐列闭式（含电阻负载列增益因子）
        k = self.p.kp * self.p.w_over_l
        out = np.zeros(self.M)
        for o in range(self.M):
            gs = np.array([k * (float(self.weights[o, i]) - self.p.vth0)
                           for i in range(self.N)])
            denom = 1.0 + self.rf * float(np.sum(gs))
            num = self.rf * float(np.sum(gs * self.inputs))
            out[o] = num / denom
        return out

    def max_abs_err(self) -> float:
        return float(np.max(np.abs(self.solve() - self.golden_outputs())))


# ---------------------------------------------------------------------------
# 晶体管级 OTA（NMOS 差分对 + 电阻负载 + 尾电流源）—— 开环增益表征
# ---------------------------------------------------------------------------
def build_ota_circuit(ckt: Circuit, vin: int, vref: int, out_node: int,
                      tail: int, d1: int, vdd: int, Iss: float, Rd: float,
                      Vdd: float, p: NmosParams, tag: str = "") -> None:
    """向已有 Circuit 装入一个 NMOS 差分对 OTA（单端输出 = out_node）。

    结构：M1 栅=Vref(同相), M2 栅=Vin(反相/求和)，源共尾(尾电流源 Iss)，
    漏 d1/out 各经 Rd 上拉 Vdd。开环：V(out) ≈ G_ol·(Vref − Vin)，G_ol = gm·Rd。
    """
    ckt.vsource(vdd, 0, Vdd)
    ckt.isource(tail, 0, Iss)
    ckt.nmos(d1, vref, tail, p, f"OTA_M1_{tag}")
    ckt.nmos(out_node, vin, tail, p, f"OTA_M2_{tag}")
    ckt.resistor(d1, vdd, Rd, f"OTA_Rd1_{tag}")
    ckt.resistor(out_node, vdd, Rd, f"OTA_Rd2_{tag}")


def ota_open_loop_gain(Iss: float = 0.5e-3, Rd: float = 20e3, Vdd: float = 10.0,
                       Vcm: float = 0.9, p: NmosParams = None,
                       dv: float = 1e-4) -> float:
    """表征 OTA 开环增益：在 Vcm 偏置附近做两点微分（Vin=Vcm 与 Vin=Vcm+dv）。

    返回 dVout/dVin（应为负，即反相）。增益绝对值随 Rd 增大而增大（gm·Rd），
    证明该晶体管放大器可作为「理想运放」的晶体管级替身（有限增益）。
    """
    p = p or NmosParams()
    vdd, vref, tail, d1, d2, vin = 100, 101, 102, 103, 104, 105
    v0 = {vref: Vcm, vin: Vcm, d1: Vdd - Iss * Rd / 2.0,
          d2: Vdd - Iss * Rd / 2.0, tail: Vcm - 0.5}
    c = Circuit("ota_gain")
    c.vsource(vref, 0, Vcm)
    build_ota_circuit(c, vin, vref, d2, tail, d1, vdd, Iss, Rd, Vdd, p, "g0")
    c.vsource(vin, 0, Vcm)
    x0 = c.solve_dc(v0=v0)
    n0 = c.node_voltages(x0)
    c1 = Circuit("ota_gain1")
    c1.vsource(vref, 0, Vcm)
    build_ota_circuit(c1, vin, vref, d2, tail, d1, vdd, Iss, Rd, Vdd, p, "g1")
    c1.vsource(vin, 0, Vcm + dv)
    x1 = c1.solve_dc(v0=v0)
    n1 = c1.node_voltages(x1)
    return (n1[d2] - n0[d2]) / dv


CROSSBAR_DISCLOSURE = {
    "route": "电子计算征程 E2 · 参数化 MVM 交叉阵列生成器",
    "e2_scope": "N×M 模拟矩阵-向量乘；amp={'ideal'(VCVS TIA) | 'transistor'(NMOS三极管权重)}",
    "redline": "T1 电路级（不碰 Foundry TCAD / 工艺角 / 流片）；C 级自主（纯 numpy）",
    "sovereignty": "不借任何商业 SPICE 引擎；LLM 不进判决路径",
    "honest_boundary": "参数为公开典型量级占位（非 PDK 标定、无实测锚）；非签核级 SPICE；"
                       "transistor 路径列增益含电阻负载因子（golden 已计入）",
}
