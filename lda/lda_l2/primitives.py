# -*- coding: utf-8 -*-
"""LDA L2 · 真实版图基元库（D-71，Track B：版图真实化，foundry-ready）。

替代玩具几何（直线 path / 圆环 boundary），提供可流片级真实版图基元的
**纯几何核心**（零依赖，仅标准库 math）——GDS 编码 / SVG 预览 / DRC 复用：

  taper            线性 / 绝热（余弦）taper，宽度 w1→w2 过渡
  euler_bend       Euler 弯（clothoid）：曲率 0→1/R→0 连续变化，无折角
  mmi              MMI 分束器（1×2 对称）：输入 taper + 多模干涉区 + 双输出 taper
  grating_coupler  光栅耦合器（GC）：波导 + 周期部分刻蚀齿
  bragg_grating    布拉格光栅（BraggMirror 的平面实现）：侧壁调制波导，
                   段长 λ0/(4·n_eff)（**n_eff 由 LDA 自有 slab 求解器算出**）

诚实边界：本模块只交付**几何基元**（foundry 可接受的 GDS 版图形状）；
分束比/透射谱等电磁特性属 D-72（真实 2D FDTD 端口 S 参数验收）范畴，
本步不做任何电气性能声称。
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

# 默认典型 SOI 工艺参数（与 drc.DEFAULT_RULES 同窗口；PDK 接入后可覆盖）
DEF_RULES: Dict[str, float] = {
    "min_width_um": 0.35,
    "min_space_um": 0.20,
    "min_bend_R_um": 5.0,
}


# ---------------------------------------------------------------------------
# taper（线性 / 绝热）
# ---------------------------------------------------------------------------
def taper_polygon(w1: float, w2: float, length_um: float,
                  n_seg: int = 32, profile: str = "adiabatic",
                  x0: float = 0.0) -> List[Tuple[float, float]]:
    """宽度 w1→w2 的 taper 闭合多边形。中心线 y=0，输入端在 x=x0。

    profile="linear"：线性过渡；"adiabatic"：余弦渐变（两端斜率 0，
    减小模式失配 / 回波损耗）。n_seg 越大轮廓越光滑。
    """
    h0, h1 = w1 / 2.0, w2 / 2.0
    xs = [x0 + length_um * i / n_seg for i in range(n_seg + 1)]

    def half(x: float) -> float:
        t = (x - x0) / length_um if length_um > 0 else 1.0
        t = max(0.0, min(1.0, t))
        if profile == "linear":
            return h0 + (h1 - h0) * t
        return h0 + (h1 - h0) * (1.0 - math.cos(math.pi * t)) / 2.0

    top = [(x, half(x)) for x in xs]
    bot = [(x, -half(x)) for x in xs[::-1]]
    return top + bot


# ---------------------------------------------------------------------------
# Euler 弯（clothoid：曲率连续）
# ---------------------------------------------------------------------------
def euler_bend_centerline(R: float, theta_deg: float,
                          n: int = 512) -> List[Tuple[float, float]]:
    """Euler 弯中心线：曲率 0→1/R→0 对称线性过渡（两段 clothoid）。

    半径 R（最小曲率半径）、总转角 theta_deg。起点 (0,0)，初始方向 +x。
    曲率连续 ⇒ 无模式转换损耗尖点（对比圆弧弯的曲率阶跃）。
    """
    theta = math.radians(theta_deg)
    Lc = R * theta                       # 每段 clothoid 弧长（升 / 降）
    L_arc = 2.0 * Lc                     # 总弧长
    ds = L_arc / n
    x = y = phi = 0.0
    pts = [(0.0, 0.0)]
    for i in range(1, n + 1):
        sm = i * ds - ds / 2.0           # 段中点弧长
        if sm < Lc:
            kappa = (1.0 / R) * (sm / Lc)
        else:
            kappa = (1.0 / R) * (2.0 - sm / Lc)
        phi += kappa * ds
        x += math.cos(phi) * ds
        y += math.sin(phi) * ds
        pts.append((x, y))
    return pts


def _polyline_offset(points: Sequence[Tuple[float, float]],
                     half_w: float) -> Tuple[List[Tuple[float, float]],
                                             List[Tuple[float, float]]]:
    """中心线 → 两侧偏移 w/2 的左右边界（端点切线法向，端口平齐）。"""
    n = len(points)
    left: List[Tuple[float, float]] = []
    right: List[Tuple[float, float]] = []

    def normal(i: int):
        if i == 0:
            dx, dy = points[1][0] - points[0][0], points[1][1] - points[0][1]
        elif i == n - 1:
            dx, dy = points[-1][0] - points[-2][0], points[-1][1] - points[-2][1]
        else:
            dx, dy = (points[i + 1][0] - points[i - 1][0],
                      points[i + 1][1] - points[i - 1][1])
        L = math.hypot(dx, dy) or 1e-12
        return -dy / L, dx / L           # 法向（左）

    for i, (px, py) in enumerate(points):
        nx, ny = normal(i)
        left.append((px + nx * half_w, py + ny * half_w))
        right.append((px - nx * half_w, py - ny * half_w))
    return left, right


def euler_bend_polygon(R: float, theta_deg: float, width_um: float,
                       n: int = 512) -> List[Tuple[float, float]]:
    """Euler 弯闭合多边形（含宽度 w）。"""
    cl = euler_bend_centerline(R, theta_deg, n=n)
    left, right = _polyline_offset(cl, width_um / 2.0)
    return left + right[::-1]


# ---------------------------------------------------------------------------
# MMI 分束器（1×2 对称）
# ---------------------------------------------------------------------------
def mmi_descs(params: Dict[str, float]) -> List[Dict]:
    """1×2 对称 MMI 分束器几何描述（geometry_desc 风格）。

    params：width(波导宽 w) / W_mmi(多模区宽) / L_mmi(多模区长) /
            L_tap(taper 长) / out_gap(输出波导间距) / L_out(输出波导长)。
    输入在中心（对称激励）；两输出波导中心 y=±(w/2+out_gap/2)，
    经 taper 从多模区边缘展开。分束特性（3dB/耦合比）需 D-72 2D FDTD
    验证，本步只交付几何。
    """
    w = float(params.get("width", 0.5))
    W = float(params.get("W_mmi", 6.0))
    L = float(params.get("L_mmi", 20.0))
    Lt = float(params.get("L_tap", 4.0))
    gap = float(params.get("out_gap", 0.5))
    Lo = float(params.get("L_out", 3.0))
    yo = w / 2.0 + gap / 2.0             # 输出波导中心 y

    descs: List[Dict] = []
    # 输入波导
    descs.append({"kind": "path", "layer": 1, "width_um": w,
                  "points_um": [(-Lt, 0.0), (0.0, 0.0)]})
    # 输入 taper（窄 w → 宽 W）
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [taper_polygon(w, W, Lt, x0=-Lt,
                                             profile="linear")]})
    # 多模干涉区
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [[(0.0, -W / 2.0), (L, -W / 2.0),
                                (L, W / 2.0), (0.0, W / 2.0)]]})
    # 双输出 taper（宽 W → 窄 w，中心 ±yo）
    for sgn in (+1.0, -1.0):
        poly = [(x, y + sgn * yo)
                for x, y in taper_polygon(W, w, Lt, x0=L, profile="linear")]
        descs.append({"kind": "boundary", "layer": 1, "rings_um": [poly]})
        # 输出波导
        descs.append({"kind": "path", "layer": 1, "width_um": w,
                      "points_um": [(L + Lt, sgn * yo),
                                    (L + Lt + Lo, sgn * yo)]})
    return descs


# ---------------------------------------------------------------------------
# 光栅耦合器（GC）：波导 + 周期部分刻蚀齿
# ---------------------------------------------------------------------------
def grating_coupler_descs(params: Dict[str, float]) -> List[Dict]:
    """光栅耦合器几何描述：输入波导 + 周期齿区（齿=保留硅，间隔=刻蚀凹槽）。

    params：width(波导宽 w) / Lambda(周期) / duty(占空比 dc=齿宽/周期) /
            n_tooth(齿数) / L_in(输入波导长)。
    齿贯穿波导全宽（顶部部分刻蚀风格）。耦合效率/方向性需 D-72 FDTD
    验证，本步只交付几何。
    """
    w = float(params.get("width", 0.5))
    Lam = float(params.get("Lambda", 0.68))
    dc = float(params.get("duty", 0.5))
    N = int(params.get("n_tooth", 20))
    Li = float(params.get("L_in", 3.0))
    tooth_w = Lam * dc
    total = N * Lam

    descs: List[Dict] = []
    # 输入波导
    descs.append({"kind": "path", "layer": 1, "width_um": w,
                  "points_um": [(-Li, 0.0), (0.0, 0.0)]})
    # 周期齿（保留硅矩形，间隔=刻蚀凹槽=包层）。
    # D-78 修正：不再加"齿区主体"实心矩形——它与齿同层合并会把凹槽填成硅
    # （GDS 同层多边形为合并填充语义），栅格化后等于直波导，无周期调制。
    for k in range(N):
        x0 = k * Lam
        descs.append({"kind": "boundary", "layer": 1,
                      "rings_um": [[(x0, -w / 2.0), (x0 + tooth_w, -w / 2.0),
                                    (x0 + tooth_w, w / 2.0), (x0, w / 2.0)]]})
    return descs


# ---------------------------------------------------------------------------
# 布拉格光栅（BraggMirror 的平面实现）：侧壁调制波导 + 四分之一波长段
# ---------------------------------------------------------------------------
# EIM 归约链（两级对称 slab），全部由 LDA 自有求解器算，无手工魔法数：
#   竖向 n_core_2d = TE0(n_core, n_clad, d=h_core)      —— mmi_eme.slab_te_neff_analytic
#   横向 n_eff(w)  = TE0(n_core_2d, n_clad, d=w)
#   段长 L_i = λ0 / (4·n_eff(w_i))      ← 与器件库一维 TMM 模型**同构造**
BRAGG_DEFAULTS: Dict[str, float] = {
    "width": 0.5,          # 标称波导宽（也是引线宽）
    "corrugation": 0.12,   # 侧壁调制峰峰值 Δw（宽段 = w+Δw/2，窄段 = w−Δw/2）
    "periods": 6,
    "wl0_um": 1.55,
    "h_core_um": 0.22,     # 220nm SOI
    "n_core": 3.48,
    "n_clad": 1.44,
}

_SOLVER_DIR = None


def _slab_te_neff(n_core: float, n_clad: float, d_um: float,
                  wl_um: float, m: int = 0):
    """取 LDA 自有对称 slab TE_m 解析 n_eff（懒加载求解核，供 EIM 归约）。

    `slab_te_neff_analytic` 本身**零依赖**（超越方程二分解，纯 math），
    位于 lda_solver.mmi_eme；此处懒加载以保持本模块零顶层依赖。
    """
    global _SOLVER_DIR
    import os as _os
    import sys as _sys
    if _SOLVER_DIR is None:
        _SOLVER_DIR = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "lda_solver")
    if _SOLVER_DIR not in _sys.path:
        _sys.path.insert(0, _SOLVER_DIR)
    try:
        from mmi_eme import slab_te_neff_analytic as _f   # type: ignore
    except ImportError:                                    # pragma: no cover
        try:
            from lda_solver.mmi_eme import (               # type: ignore
                slab_te_neff_analytic as _f)
        except ImportError as exc:
            raise ImportError(
                "布拉格光栅需要 lda_solver.mmi_eme.slab_te_neff_analytic "
                "才能导出真实段长（禁止回退到拍脑袋的周期）") from exc
    return _f(n_core, n_clad, d_um, wl_um, m)


def bragg_neff_chain(width: float, corrugation: float = 0.12,
                     wl0_um: float = 1.55, h_core_um: float = 0.22,
                     n_core: float = 3.48, n_clad: float = 1.44):
    """两级 EIM + 四分之一波长段长 → 字典（物理派生结果，非拟合）。

    返回 {w_hi, w_lo, v_neff, n_hi, n_lo, L_hi, L_lo, pitch_um, ...}。
    `v_neff` = 竖向归约折射率，`n_hi/n_lo` = 宽/窄段的横向有效折射率。

    🔴 诚实边界：n_eff 来自 **2D-EIM 对称 slab 抽象**（上下包层同折射率）。
    真实 SOI（上包层空气或不同厚度的氧化层）是非对称 slab，数值会偏移；
    2D-EIM 本身忽略拐角/矢状（corner）修正。本派生是**模型内的自洽**，
    不是实测。
    """
    w = float(width)
    dw = float(corrugation)
    if dw <= 0:
        raise ValueError("corrugation 必须 > 0（无侧壁调制则无布拉格反射）")
    if dw >= w:
        raise ValueError(f"corrugation {dw}µm 过大：窄段 w−Δw/2 会退化（w={w}µm）")
    w_hi, w_lo = w + dw / 2.0, w - dw / 2.0
    v_neff = _slab_te_neff(n_core, n_clad, h_core_um, wl0_um, 0)
    if v_neff is None:
        raise ValueError(
            f"竖向 slab 无导模：h_core={h_core_um}µm @ λ={wl0_um}µm "
            f"（n_core={n_core}/n_clad={n_clad}）")
    n_hi = _slab_te_neff(v_neff, n_clad, w_hi, wl0_um, 0)
    n_lo = _slab_te_neff(v_neff, n_clad, w_lo, wl0_um, 0)
    if n_hi is None or n_lo is None:
        raise ValueError(
            f"横向无导模：宽段 {w_hi:.3f}µm 或窄段 {w_lo:.3f}µm @ λ={wl0_um}µm")
    # 四分之一波长：与器件库一维 TMM（qw = λ/(4n)）**同构造**
    L_hi = wl0_um / (4.0 * n_hi)
    L_lo = wl0_um / (4.0 * n_lo)
    return {"w_hi": w_hi, "w_lo": w_lo, "w_nominal": w, "corrugation": dw,
            "v_neff": v_neff, "n_hi": n_hi, "n_lo": n_lo,
            "L_hi": L_hi, "L_lo": L_lo, "pitch_um": L_hi + L_lo,
            "wl0_um": wl0_um, "h_core_um": h_core_um,
            "n_core": n_core, "n_clad": n_clad}


def bragg_grating_report(params: Dict[str, float]) -> Dict[str, object]:
    """布拉格光栅几何的**物理量报告**（供派生留痕 / 测试断言 / UI 展示）。

    额外键：`n_periods`、`grating_len_um`、`total_len_um`、`n_elements`、
    `honest_note`（写明本版图与器件库一维锚的差异，见下）。

    🔴🔴 **与验证锚的关系（必读，防误用）**：器件库里 BraggMirror 的验收
    契约是**一维四分之一波长堆叠 TMM**（层折射率取**体材料** n_Si=3.48 /
    n_SiO2=1.44）。而平面波导无论怎么调宽都拿不到 3.48:1.44 的折射率比
    （220nm SOI 横向 n_eff 上限 ≈ v_neff ≈ 2.85，下限趋向 n_clad）。
    因此本版图**不是**那个 TMM 模型器件的几何复刻：禁止拿它的 R_min 验收
    结果给这个 GDS 背书，反之亦然。两者共享的只有「逐层堆叠 + 四分之一
    波长」这一**同一构造**。
    """
    p = dict(BRAGG_DEFAULTS)
    p.update({k: v for k, v in params.items() if v is not None})
    n = int(p["periods"])
    if n < 1:
        raise ValueError(f"periods={n} 非法（布拉格光栅至少 1 个周期）")
    chain = bragg_neff_chain(p["width"], p["corrugation"], p["wl0_um"],
                             p["h_core_um"], p["n_core"], p["n_clad"])
    Lt = float(params.get("taper_len", 1.5))
    Li = float(params.get("L_in", 2.0))
    Lo = float(params.get("L_out", 2.0))
    out = dict(chain)
    out.update({
        "n_periods": n,
        "taper_len": Lt, "L_in": Li, "L_out": Lo,
        "grating_len_um": n * chain["pitch_um"],
        "total_len_um": Li + Lt + n * chain["pitch_um"] + Lt + Lo,
        # 2 引线 PATH + 2 taper BOUNDARY + 2n 个周期 BOUNDARY
        "n_elements": 2 + 2 + 2 * n,
        "honest_note": (
            "侧壁调制波导型布拉格光栅：段长由 LDA 自有 slab 求解器按 "
            "λ0/(4·n_eff) 导出，与器件库一维 TMM 锚的体材料折射率 "
            "(3.48/1.44) 不同 —— 220nm SOI 横向 n_eff 上限仅 ≈2.85，无法"
            "复刻该折射率比；两者只共享「四分之一波长堆叠」构造，不可互相背书。"),
    })
    return out


def bragg_grating_descs(params: Dict[str, float]) -> List[Dict]:
    """布拉格光栅（BraggMirror 平面实现）几何描述。

    沿 x：输入引线 PATH → 绝热 taper（引线宽 → 宽段宽）→ N×(宽段+窄段)
    → taper（窄段宽 → 引线宽）→ 输出引线 PATH。

    params：width / corrugation / periods / wl0_um / h_core_um / n_core /
            n_clad / L_in / L_out / taper_len。
    周期段的**段长不是入参**，而是 `bragg_neff_chain` 从模式求解器算出的
    λ0/(4·n_eff) —— 避免「周期」被当成可随意填的自由量（那是造假的入口）。

    ⚠️ 相邻周期段**首尾相接**（连续光栅，同一层合并语义）。几何 DRC 的间距
    规则对此必须按「同层连通域」豁免，否则会假红；见 gds_drc.
    `_CONNECTED_TOUCH_EPS`。
    """
    rep = bragg_grating_report(params)
    n = rep["n_periods"]
    w = rep["w_nominal"]
    w_hi, w_lo = rep["w_hi"], rep["w_lo"]
    L_hi, L_lo = rep["L_hi"], rep["L_lo"]
    Li, Lo, Lt = rep["L_in"], rep["L_out"], rep["taper_len"]

    descs: List[Dict] = []
    # 输入引线（宽=标称值，与 taper 起点同宽 ⇒ 无台阶）
    descs.append({"kind": "path", "layer": 1, "width_um": w,
                  "points_um": [(-Li, 0.0), (0.0, 0.0)]})
    # 输入 taper：引线宽 → 宽段宽
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [taper_polygon(w, w_hi, Lt, profile="adiabatic")]})
    # N 个周期：先宽段后窄段（与 DBR 惯例一致：高低折射率交替，自高起）
    x = Lt
    for _i in range(n):
        for wseg, Lseg in ((w_hi, L_hi), (w_lo, L_lo)):
            descs.append({"kind": "boundary", "layer": 1,
                          "rings_um": [_poly_rect(x, -wseg / 2.0,
                                                  x + Lseg, wseg / 2.0)]})
            x += Lseg
    # 输出 taper：窄段宽 → 引线宽（x 已是光栅末端）
    xe = x
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [taper_polygon(w_lo, w, Lt, x0=xe,
                                             profile="adiabatic")]})
    descs.append({"kind": "path", "layer": 1, "width_um": w,
                  "points_um": [(xe + Lt, 0.0), (xe + Lt + Lo, 0.0)]})
    return descs


# ---------------------------------------------------------------------------
# 统一入口：kind + params → geometry_desc 风格 desc 列表
# ---------------------------------------------------------------------------
def _poly_rect(x0, y0, x1, y1):
    """矩形多边形（逆时针，基元几何工具）。"""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def phase_shifter_descs(params: Dict[str, float]) -> List[Dict]:
    """热光相移器几何（第二梯队-2c 有源基元一）：硅波导 + 顶部加热电阻。

    params：width(波导宽) / L_heat(加热段长) / width_heat(电阻宽) /
            gap_heat(电阻与波导间距)。
    几何表达：主波导条 + 加热电阻矩形（诚实标注：实际工艺加热器在金属层/
    掺杂层，本步先交付几何，工艺层映射归真实 PDK）。
    """
    w = float(params.get("width", 0.5))
    Lh = float(params.get("L_heat", 40.0))
    wh = float(params.get("width_heat", 2.0))
    gh = float(params.get("gap_heat", 1.0))
    y_top = w / 2.0 + gh
    return [
        {"kind": "boundary", "layer": 1,   # 主波导
         "rings_um": [_poly_rect(-Lh / 2.0, -w / 2.0, Lh / 2.0, w / 2.0)]},
        {"kind": "boundary", "layer": 1,   # 加热电阻（顶部，工艺层简化）
         "rings_um": [_poly_rect(-Lh / 2.0, y_top, Lh / 2.0, y_top + wh)]},
    ]


def modulator_descs(params: Dict[str, float]) -> List[Dict]:
    """MZI 电光调制器几何（有源基元二）：双平行臂 + 电极。

    params：width(波导宽) / arm_L(臂长) / arm_gap(臂间距) /
            elec_w(电极宽) / elec_gap(电极与臂间距)。
    """
    w = float(params.get("width", 0.5))
    La = float(params.get("arm_L", 200.0))
    ag = float(params.get("arm_gap", 4.0))
    ew = float(params.get("elec_w", 3.0))
    eg = float(params.get("elec_gap", 1.0))
    y_inner = ag / 2.0 - w / 2.0
    y_outer = ag / 2.0 + w / 2.0
    ye = y_outer + eg
    return [
        {"kind": "boundary", "layer": 1,   # 臂1
         "rings_um": [_poly_rect(-La / 2.0, -y_outer, La / 2.0, -y_inner)]},
        {"kind": "boundary", "layer": 1,   # 臂2
         "rings_um": [_poly_rect(-La / 2.0, y_inner, La / 2.0, y_outer)]},
        {"kind": "boundary", "layer": 1,   # 电极1（工艺层简化）
         "rings_um": [_poly_rect(-La / 2.0, ye, La / 2.0, ye + ew)]},
        {"kind": "boundary", "layer": 1,   # 电极2
         "rings_um": [_poly_rect(-La / 2.0, -ye - ew, La / 2.0, -ye)]},
    ]


def photodetector_descs(params: Dict[str, float]) -> List[Dict]:
    """光电探测器几何（有源基元三）：Ge 吸收区（宽矩形）+ 输入 taper 过渡。

    params：width(输入波导宽) / det_L(吸收区长) / det_w(吸收区宽)。
    诚实标注：实际 Ge 探测器有 n+/p+ 接触与金属互联，本步只交付吸收区几何。
    """
    w = float(params.get("width", 0.5))
    Ld = float(params.get("det_L", 20.0))
    Wd = float(params.get("det_w", 5.0))
    return [
        {"kind": "boundary", "layer": 1,   # 输入波导
         "rings_um": [_poly_rect(-8.0, -w / 2.0, 0.0, w / 2.0)]},
        {"kind": "boundary", "layer": 1,   # Ge 吸收区
         "rings_um": [_poly_rect(0.0, -Wd / 2.0, Ld, Wd / 2.0)]},
    ]


def primitive_descs(kind: str, params: Dict[str, float]) -> List[Dict]:
    """真实版图基元统一几何入口（供 gds_export.geometry_desc 注册）。"""
    kind = kind.lower()
    if kind in ("taper", "taper_linear", "taper_adiabatic"):
        profile = "adiabatic" if "adiabatic" in kind else \
                  ("linear" if "linear" in kind else
                   str(params.get("profile", "adiabatic")))
        w1 = float(params.get("w1", params.get("width_in", 0.5)))
        w2 = float(params.get("w2", params.get("width_out", 1.5)))
        L = float(params.get("length", params.get("L", 20.0)))
        return [{"kind": "boundary", "layer": 1,
                 "rings_um": [taper_polygon(w1, w2, L, profile=profile)]}]
    if kind in ("eulerbend", "euler_bend"):
        R = float(params.get("R", 10.0))
        th = float(params.get("theta_deg", 90.0))
        w = float(params.get("width", 0.5))
        return [{"kind": "boundary", "layer": 1,
                 "rings_um": [euler_bend_polygon(R, th, w)]}]
    if kind == "mmi":
        return mmi_descs(params)
    if kind in ("gratingcoupler", "grating_coupler"):
        return grating_coupler_descs(params)
    if kind in ("phaseshifter", "phase_shifter"):
        return phase_shifter_descs(params)
    if kind in ("modulator", "mzimodulator", "mzi_modulator"):
        return modulator_descs(params)
    if kind in ("photodetector", "photo_detector"):
        return photodetector_descs(params)
    if kind in ("braggmirror", "bragg", "bragggrating", "bragg_grating"):
        return bragg_grating_descs(params)
    raise ValueError(f"真实版图基元暂不支持 kind={kind}")


# ---------------------------------------------------------------------------
# 基元级 DRC 几何量（供 drc.drc_check_device 扩展引用）
# ---------------------------------------------------------------------------
def primitive_geometry(kind: str, params: Dict[str, float]) -> Dict[str, float]:
    """基元的可制造性几何量（min_width/min_space/min_bend_R 检查源）。"""
    kind = kind.lower()
    if kind in ("taper", "taper_linear", "taper_adiabatic"):
        w1 = float(params.get("w1", params.get("width_in", 0.5)))
        w2 = float(params.get("w2", params.get("width_out", 1.5)))
        return {"min_width": min(w1, w2)}
    if kind in ("eulerbend", "euler_bend"):
        return {"min_width": float(params.get("width", 0.5)),
                "min_bend_R": float(params.get("R", 10.0))}
    if kind == "mmi":
        return {"min_width": float(params.get("width", 0.5)),
                "min_space": float(params.get("out_gap", 0.5))}
    if kind in ("gratingcoupler", "grating_coupler"):
        Lam = float(params.get("Lambda", 0.68))
        dc = float(params.get("duty", 0.5))
        return {"min_width": Lam * dc,
                "min_space": Lam * (1.0 - dc)}
    if kind in ("braggmirror", "bragg", "bragggrating", "bragg_grating"):
        # 参数级 DRC 只管**横向宽度**（波导宽的意义）；周期段长是**纵向**
        # 特征，交给几何 DRC（gds_drc 对真实多边形做最小平行带宽度检查）。
        rep = bragg_grating_report(params)
        return {"min_width": min(rep["w_hi"], rep["w_lo"])}
    raise ValueError(f"真实版图基元暂不支持 kind={kind}")
