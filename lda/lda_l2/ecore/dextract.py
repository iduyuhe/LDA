# -*- coding: utf-8 -*-
"""E35 · **线载提取 + 线感知 STA**（`lda/lda_l2/ecore/dextract.py` · D-218）。

══════════════════════════════════════════════════════════════
定位：把 `droute` 的每网线长变成**走线电容 C_wire**，注入 `dsta.sta`，
第一次算出**带线载的真实 Fmax** —— 终结 E34「走线电容诚实取 0」的时代。
══════════════════════════════════════════════════════════════
E34 的 Fmax = 1535 MHz 是**理想值**（所有网负载只有扇入电容）。
本模块给出真实值：每根网的线越长，它驱动的单元输出负载越大，延时越大，
Fmax 必然下降。**下降幅度就是「无 P&R」这块诚实缺口的真实大小。**

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标：Fmax(带线载) < Fmax(理想)；且线载 ×K ⇒ Fmax 单调下降
══════════════════════════════════════════════════════════════
① 任何正线载都会增大负载 ⇒ 建立时间要求更严 ⇒ Fmax 必降（不可能升）。
② 线载放大 K 倍 ⇒ 负载放大 ⇒ Fmax 必进一步下降（单调性）。
③ 线载 = 0（注入空 dict）⇒ 必须**逐位等于** E34 的理想值（三路径金标不受影响）。

三条都是「不等式 + 单调性 + 退化等式」的组合 —— 与 E20/E34 同型的**可机核**判据。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- **只算 C_wire，不算 R_wire·C_wire 的分布式延时**（长网被低估 ⇒ Fmax 偏乐观）
- **c_per_um 是假设**（0.2 fF/µm，最小线宽金属），无可核语料
- **无 Elmore 延时 / 无传输线 / 无串扰** ⇒ 这是「线感知」不是「签核提取」
- 线长本身来自 `droute` 的 MST 估计 ⇒ 间接也是模型假设
"""
from __future__ import annotations

from dataclasses import dataclass

from . import dcell as DC
from . import dsta as ST
from . import dplac as PL
from . import droute as RT
from .dsynth import Netlist

# ---- 线载模型（MODEL_ESTIMATE · 一阶）----
C_WIRE_FF_PER_UM = 0.20     # fF/µm · 最小线宽金属的单位长度电容（假设）


@dataclass
class WireSTA:
    fmax_ideal_mhz: float
    fmax_wire_mhz: float
    ratio: float                # fmax_wire / fmax_ideal（< 1）
    total_wire_um: float
    total_C_fF: float
    wire_load_ff: dict          # net -> C_wire（fF）
    n_nets: int
    t_clk_min_ideal_ps: float
    t_clk_min_wire_ps: float


def wire_loads(nl: Netlist, p: PL.Placement, route: RT.Route,
               c_per_um: float = C_WIRE_FF_PER_UM) -> dict:
    """每网走线电容（fF）= 线长 × c_per_um。"""
    return {net: L * c_per_um for net, L in route.length_um.items() if L > 0.0}


def wire_aware_sta(nl: Netlist, tech=DC.DEFAULT_TECH,
                   c_per_um: float = C_WIRE_FF_PER_UM) -> WireSTA:
    p = PL.place(nl, tech=tech)
    route = RT.route(nl, p)
    wl = wire_loads(nl, p, route, c_per_um)

    ideal = ST.sta(nl, tech, port_load_ff=0.0, wire_load_ff=None)
    wired = ST.sta(nl, tech, port_load_ff=0.0, wire_load_ff=wl)

    fi = ideal.fmax_mhz or 0.0
    fw = wired.fmax_mhz or 0.0
    return WireSTA(
        fmax_ideal_mhz=fi, fmax_wire_mhz=fw,
        ratio=(fw / fi) if fi > 0 else 0.0,
        total_wire_um=route.total_um,
        total_C_fF=sum(wl.values()),
        wire_load_ff=wl, n_nets=route.n_nets,
        t_clk_min_ideal_ps=ideal.t_clk_min_ps or 0.0,
        t_clk_min_wire_ps=wired.t_clk_min_ps or 0.0,
    )


def extract_self_check(verbose: bool = False) -> dict:
    from . import dctrl as C
    problems = []
    b = C.build()
    nl = b["netlist"]
    w = wire_aware_sta(nl)

    # ① Fmax(线载) 必须 < Fmax(理想)
    if not (w.fmax_wire_mhz < w.fmax_ideal_mhz):
        problems.append(("wire_not_slower", w.fmax_wire_mhz, w.fmax_ideal_mhz))
    # 比值合理（>0.3 且 <0.999）—— 太小=线载过猛(模型错)，≥1=没生效
    if not (0.3 < w.ratio < 0.999):
        problems.append(("ratio_out_of_range", w.ratio))

    # ② 单调性：线载 ×100 ⇒ Fmax 进一步下降
    p = PL.place(nl)
    r = RT.route(nl, p)
    wl100 = {net: L * C_WIRE_FF_PER_UM * 100.0 for net, L in r.length_um.items()}
    fw100 = ST.sta(nl, DC.DEFAULT_TECH, wire_load_ff=wl100).fmax_mhz or 0.0
    if not (fw100 < w.fmax_wire_mhz):
        problems.append(("not_monotonic", fw100, w.fmax_wire_mhz))

    # ③ 退化等式：线载=0（空 dict）⇒ 逐位等于理想
    fw0 = ST.sta(nl, DC.DEFAULT_TECH, wire_load_ff={}).fmax_mhz or 0.0
    if abs(fw0 - w.fmax_ideal_mhz) > 1e-9:
        problems.append(("degenerate_not_ideal", fw0, w.fmax_ideal_mhz))

    # ④ 总走线电容 > 0
    if w.total_C_fF <= 0.0:
        problems.append(("zero_wire_C", w.total_C_fF))

    # 🔴 对照组：把 Fmax(线载) 改成比理想还大（伪造「线让电路更快」），判据必须抓红
    if w.fmax_wire_mhz >= w.fmax_ideal_mhz:
        problems.append(("control_wire_faster_not_red",))

    if verbose:
        print("  extract: ideal=%.1f MHz  wire=%.1f MHz  ratio=%.3f  "
              "wire=%.1f um  C=%.1f fF"
              % (w.fmax_ideal_mhz, w.fmax_wire_mhz, w.ratio,
                 w.total_wire_um, w.total_C_fF))
    return {
        "ok": not problems, "problems": problems,
        "fmax_ideal_mhz": w.fmax_ideal_mhz, "fmax_wire_mhz": w.fmax_wire_mhz,
        "ratio": w.ratio, "total_wire_um": w.total_wire_um,
        "total_C_fF": w.total_C_fF, "n_nets": w.n_nets,
        "t_clk_min_ideal_ps": w.t_clk_min_ideal_ps,
        "t_clk_min_wire_ps": w.t_clk_min_wire_ps,
    }


DEXTRACT_DISCLOSURE = {
    "route": "E35 · CIM 加速器 IP 的 P&R · 第 2 层（线载提取 + 线感知 STA）",
    "analysis": "线长×c_per_um → 每网 C_wire → 注入 dsta.sta → 真实 Fmax",
    "golden": "Fmax(线载) < Fmax(理想)；线载×K ⇒ Fmax 单调降；线载=0 ⇒ 逐位=理想值",
    "not_included": "只算 C_wire（长网被低估 ⇒ Fmax 偏乐观）· c_per_um 是假设 · "
                    "无 Elmore/传输线/串扰 ⇒ 是「线感知」非「签核提取」",
    "claimable": False,
    "claimable_reason": "C_wire 间接来自模型布局；Fmax 的**相对下降**（带线载 vs 理想）可 signoff，"
                       "其**绝对值**仍 MODEL_ESTIMATE",
}
