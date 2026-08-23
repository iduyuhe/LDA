# -*- coding: utf-8 -*-
"""LDA L2 · 真实版图基元库（D-71，Track B：版图真实化，foundry-ready）。

替代玩具几何（直线 path / 圆环 boundary），提供可流片级真实版图基元的
**纯几何核心**（零依赖，仅标准库 math）——GDS 编码 / SVG 预览 / DRC 复用：

  taper            线性 / 绝热（余弦）taper，宽度 w1→w2 过渡
  euler_bend       Euler 弯（clothoid）：曲率 0→1/R→0 连续变化，无折角
  mmi              MMI 分束器（1×2 对称）：输入 taper + 多模干涉区 + 双输出 taper
  grating_coupler  光栅耦合器（GC）：波导 + 周期部分刻蚀齿

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
# 统一入口：kind + params → geometry_desc 风格 desc 列表
# ---------------------------------------------------------------------------
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
    raise ValueError(f"真实版图基元暂不支持 kind={kind}")
