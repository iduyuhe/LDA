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
    step = w + gap                       # 输出波导中心间距（= 2·yo）
    yo = w / 2.0 + gap / 2.0             # 输出波导中心 y（n_out=2 时）
    # v0.9.141（G4/M4）：n_out>2 的 1×N 扇出。此前 `placement.port_anchor`
    # 已支持 n_out>2（v0.9.95 WDM 网格）而**几何仍只画 2 路** ⇒ 声明与版图
    # 静默背离。此处补上（与 port_anchor 同一线性阵列公式，居中排布）；
    # 🔴 n_out<=2 时输出顺序与坐标与旧版**逐字节一致**（保持 [yo, -yo]）。
    n_out = int(params.get("n_out", 2))
    if n_out <= 2:
        ys_out = [yo, -yo]
    else:
        ys_out = [(j - (n_out + 1) / 2.0) * step for j in range(1, n_out + 1)]

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
    # 输出 taper（宽 W → 窄 w，中心 yc）+ 输出波导
    for yc in ys_out:
        poly = [(x, y + yc)
                for x, y in taper_polygon(W, w, Lt, x0=L, profile="linear")]
        descs.append({"kind": "boundary", "layer": 1, "rings_um": [poly]})
        descs.append({"kind": "path", "layer": 1, "width_um": w,
                      "points_um": [(L + Lt, yc), (L + Lt + Lo, yc)]})
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

    🔴 **IR 词汇回退（v0.9.141 · G4/M4）**：链路 IR（`LinkModel`）里
    `PhaseShifter` 的声明参数是 **`L` / `wg`**（见 `mesh_pnr` 的输出相移器），
    不是基元的 `L_heat` / `width`。二者**同一个几何量**，故此处按
    「基元名优先、IR 名回退」解析 —— 使**声明值真正决定几何**（否则几何恒用
    默认 40µm，与声明的 4µm 对不上，几何回提必然误报）。
    """
    w = float(params.get("width", params.get("wg", 0.5)))
    Lh = float(params.get("L_heat", params.get("L", 40.0)))
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
    🔴 IR 词汇回退（v0.9.141 · G4/M4）：IR 侧按 `L` / `W` / `wg` 声明 ⇒
    按「基元名优先、IR 名回退」解析（同 PhaseShifter/MziModulator）。
    """
    w = float(params.get("width", params.get("wg", 0.5)))
    Ld = float(params.get("det_L", params.get("L", 20.0)))
    Wd = float(params.get("det_w", params.get("W", 5.0)))
    return [
        {"kind": "boundary", "layer": 1,   # 输入波导
         "rings_um": [_poly_rect(-8.0, -w / 2.0, 0.0, w / 2.0)]},
        {"kind": "boundary", "layer": 1,   # Ge 吸收区
         "rings_um": [_poly_rect(0.0, -Wd / 2.0, Ld, Wd / 2.0)]},
    ]


# ---------------------------------------------------------------------------
# 光子存储单元（PM 征程 · PCMCell）· v0.9.191
# ---------------------------------------------------------------------------
# 🔴 层号**单一真源在 `gds_export`**：这里只做「同号引用」并由门禁
#    `run_pm_m3_smoke` 的跨源判据断言 `_gds.LIB_LAYER_PCM == _LAYER_PCM`
#    （防止「几何画在 5 层、DRC/解码找 6 层」这类静默失配）。
_LAYER_SI = 1          # 与 gds_export.LIB_LAYER_SI 同号
_LAYER_PCM = 5         # GST 相变层（本征程新增；避开已有 1/2/3/4 与 10–14/20–26）
_LAYER_HEATER = 6      # 加热器/电极金属（设计规则层，非 foundry PDK 映射）

#: PCM 单元默认参数（**单一真源**：descs / geometry / pads 三处同源引用）。
#: 🔴 `heat_gap` 取 0.35 而非更紧的 0.2，是为让电极端口 y_h=1.10 µm **有意超过**
#: LVS 端口归属容差（`run_lvs(tol=1.0)`）—— 保证「波导端点最近端口 = in/out」这一
#: 归属在容差下无歧义（否则 p 端点距两个端口都在容差内，靠「更近」勉强取胜）。
PCM_CELL_DEFAULTS: Dict[str, float] = {
    "width": 0.5,          # 波导宽
    "length": 11.0,        # 单元光程长（PM-M1 设计点量级）
    "gst_overhang": 0.20,  # GST 横向超出波导单边
    "heat_gap": 0.35,      # GST 边缘 → 加热线间隙
    "heat_w": 0.60,        # 加热线宽
    "pad": 4.0,            # 电极 pad 边长
}


def _pcm_p(params: Dict[str, float]) -> Dict[str, float]:
    """PCM 单元参数解析（缺项回落到 `PCM_CELL_DEFAULTS`，单一真源）。"""
    return {k: float(params.get(k, v)) for k, v in PCM_CELL_DEFAULTS.items()}


def pcm_cell_geometry(params: Dict[str, float]) -> Dict[str, float]:
    """PCM 存储单元的**可制造性几何量**（DRC 检查源 · 单一真源）。

    单元结构（局部坐标 µm，器件原点 = 光输入端口 in）：

        y = +y_h  ────── 加热线（上）
        y = +y_gst ┌──── GST 相变段（覆盖波导）────┐
        y = 0      ────── Si 波导（光通路）──────
        y = -y_gst └──── GST 相变段 ────┘
        y = -y_h  ────── 加热线（下）

    派生关系（**不许手写重复值**，全部由主参数算出）：
      y_gst = width/2 + gst_overhang           （GST 横向半高）
      y_h   = y_gst + heat_gap + heat_w/2      （加热线中心线 y）
    """
    p = _pcm_p(params)
    w, go, hg, hw, ps = (p["width"], p["gst_overhang"], p["heat_gap"],
                         p["heat_w"], p["pad"])
    y_gst = w / 2.0 + go
    y_h = y_gst + hg + hw / 2.0
    return {
        "min_width": min(w, 2.0 * y_gst, hw),      # 三处最小横向特征
        "min_space": min(hg, go),                  # GST↔加热线 / GST 相对波导
        "min_pad": ps,
        "y_gst_um": y_gst, "y_heater_um": y_h,
        "gst_width_um": 2.0 * y_gst,
    }


def pcm_cell_descs(params: Dict[str, float]) -> List[Dict]:
    """光子存储单元版图几何（PM 征程 · 光通路 + 相变段 + 双侧微加热器 + 电极 pad）。

    params（µm）：
      length        单元光程长（默认 11.0 = PM-M1 设计点量级）
      width         波导宽（默认 0.5）
      gst_overhang  GST 横向超出波导单边（默认 0.20）
      heat_gap      GST 边缘 → 加热线间隙（默认 0.20）
      heat_w        加热线宽（默认 0.60）
      pad           电极 pad 边长（默认 4.0）

    🔴 几何与端口锚（`lda_layout.placement.port_anchor`）**必须同源**：
    in=(0,0) / out=(length,0) / h1..h4 = 四个 pad 中心。
    """
    p = _pcm_p(params)
    w, L, hw, ps = p["width"], p["length"], p["heat_w"], p["pad"]
    g = pcm_cell_geometry(params)
    y_gst, y_h = g["y_gst_um"], g["y_heater_um"]

    descs: List[Dict] = [
        {"kind": "path", "layer": _LAYER_SI, "width_um": w,
         "points_um": [(0.0, 0.0), (L, 0.0)]},                      # Si 波导
        {"kind": "boundary", "layer": _LAYER_PCM,
         "rings_um": [_poly_rect(0.0, -y_gst, L, y_gst)]},          # GST 段
        {"kind": "path", "layer": _LAYER_HEATER, "width_um": hw,
         "points_um": [(0.0, y_h), (L, y_h)]},                      # 加热线（上）
        {"kind": "path", "layer": _LAYER_HEATER, "width_um": hw,
         "points_um": [(0.0, -y_h), (L, -y_h)]},                    # 加热线（下）
    ]
    for cx, cy in pcm_cell_pads(params).values():
        descs.append({"kind": "boundary", "layer": _LAYER_HEATER,
                      "rings_um": [_poly_rect(cx - ps / 2.0, cy - ps / 2.0,
                                              cx + ps / 2.0, cy + ps / 2.0)]})
    return descs


def pcm_cell_pads(params: Dict[str, float]) -> Dict[str, Tuple[float, float]]:
    """四个电极 pad 中心坐标（局部 µm）——**端口锚点的唯一真源**。

    上加热线两端 ⇒ h1（左）/ h2（右）；下加热线两端 ⇒ h3（左）/ h4（右）。
    `placement.port_anchor` 与 `pcm_cell_descs` 都从这里取值 ⇒ 不可能漂移。
    """
    p = _pcm_p(params)
    y_h = pcm_cell_geometry(params)["y_heater_um"]
    return {"h1": (0.0, y_h), "h2": (p["length"], y_h),
            "h3": (0.0, -y_h), "h4": (p["length"], -y_h)}


# ---------------------------------------------------------------------------
# 传感窗口开窗器件（PS 征程 M1 / G4 · SensingRing / SensingMZI）· v0.9.210
# ---------------------------------------------------------------------------
# 🔴 层号**单一真源在 `gds_export`**（与 PCM 同纪律）：此处只做「同号引用」，
#    并由门禁 `run_ps_m1_smoke` 的跨源判据断言
#    `gds_export.LIB_LAYER_WINDOW == _LAYER_WINDOW`（防「几何画在 7 层、
#    DRC/解码找 8 层」这类静默失配）。
_LAYER_WINDOW = 7      # 传感窗口（局部去上包层开口）工艺层

#: 传感窗口默认参数（**单一真源**：`sensing_window_geometry` / `sensing_window_descs`
#: 两处同源引用，不许各自写一份默认值）。
SENSING_WINDOW_DEFAULTS: Dict[str, float] = {
    "R": 10.0,             # 环形半径（SensingRing）
    "Lu": 20.0,            # 单元长度（SensingMZI）
    "dy": 4.0,             # 双臂轨间距（SensingMZI）
    "wg_width": 0.45,      # 波导芯宽
    "gap": 0.30,           # 耦合间隙（SensingRing：bus ↔ ring）
    "window_w": 3.00,      # 窗口横向（径向）宽度
    "window_len": 8.00,    # 窗口沿光程长度
}


def _sens_p(kind: str, params: Dict[str, float]) -> Dict[str, float]:
    """传感窗口参数解析（缺项回落 `SENSING_WINDOW_DEFAULTS`，单一真源）。"""
    out = dict(SENSING_WINDOW_DEFAULTS)
    for k in list(out):
        if params and k in params:
            out[k] = float(params[k])
    return out


def _sensing_path_extent(kind: str, p: Dict[str, float]) -> float:
    """传感光程总长（窗口端留白的判据基准）。
    SensingRing = 环周长 2πR；SensingMZI = 单元长 Lu。"""
    if kind == "SensingRing":
        return 2.0 * math.pi * p["R"]
    if kind == "SensingMZI":
        return p["Lu"]
    raise ValueError(f"传感窗口不支持的 kind={kind}")


def sensing_window_geometry(kind: str, params: Dict[str, float]) -> Dict[str, float]:
    """传感窗口的**可制造性几何量**（DRC 检查源 · 单一真源）。

    结构（局部坐标 µm，器件原点 = 环心 / MZI 左下角）：

        SensingRing  环心线 PATH（半径 R）+ 下 bus；窗口 = 覆盖环**顶部**弧段的
                     矩形，居中于 (0, R)，弦长近似 window_len
                     （window_len ≪ R 时弧长误差 O(window_len²/R)，本档 window_len=8 /
                     R=10 ⇒ 约 0.7%，设计规则量级可忽略）。
        SensingMZI   双平行臂 PATH（y=0 / y=dy）；窗口 = 覆盖**两臂**的矩形，
                     沿程 window_len、横向 = dy + window_w（每臂各留 window_w/2）。

    派生量（**不许手写重复值**，全部由主参数算出）：
      window_margin  = (window_w − wg_width) / 2   （窗口边 → 波导芯外缘余量）
      window_h       = window_w（Ring）/ dy + window_w（MZI）  （窗口矩形总高）
      window_end_gap = (总光程 − window_len) / 2    （窗口端 → 最近端口/耦合区的留白）
      clad_enclosure = 0.0                          （开窗区包层被人为去除 ⇒ 恒违反通用包封规则，
                                                     由工艺例外 `WINDOW_EXCEPTIONS` 豁免）
    """
    p = _sens_p(kind, params)
    W = _sensing_path_extent(kind, p)
    margin = (p["window_w"] - p["wg_width"]) / 2.0
    out: Dict[str, float] = {
        "window_w": p["window_w"],
        "window_len": p["window_len"],
        "window_margin": margin,
        "window_end_gap": (W - p["window_len"]) / 2.0,
        "clad_enclosure": 0.0,
        "path_extent": W,
    }
    if kind == "SensingRing":
        out["R"] = p["R"]
        out["bus_off"] = p["R"] + p["wg_width"] / 2.0 + p["gap"]
        out["window_h"] = p["window_w"]
        out["window_center_x"] = 0.0
        out["window_center_y"] = p["R"]
        # 🔴 bus 半长是**端口锚与版图共用**的量 ⇒ 在此一次性导出（单一真源），
        #    `sensing_window_descs` 与 `placement.port_anchor` 都取它，
        #    不许各自写 1.4 这个魔数（防「锚点一套、版图一套」漂移）。
        out["bus_half"] = p["R"] * 1.4
    elif kind == "SensingMZI":
        out["Lu"] = p["Lu"]
        out["dy"] = p["dy"]
        out["window_h"] = p["dy"] + p["window_w"]
        out["window_center_x"] = p["Lu"] / 2.0
        out["window_center_y"] = p["dy"] / 2.0
    else:
        raise ValueError(f"传感窗口不支持的 kind={kind}")
    return out


def sensing_window_descs(kind: str, params: Dict[str, float]) -> List[Dict]:
    """传感窗口开窗器件版图几何（PS 征程 M1/G4）。

    = 芯层几何（环 + bus / 双 MZI 臂） + **窗口层**（去上包层开口）矩形。

    🔴 窗口多边形与 `sensing_window_geometry` **同源**（同一函数导出的
    window_center_x/y、window_w/len/h），杜绝「DRC 量算一套、版图画另一套」。
    层号经 lazy import 取 `gds_export.LIB_LAYER_SI`（单一真源）。
    """
    from lda_l2.gds_export import LIB_LAYER_SI, ring_centerline
    p = _sens_p(kind, params)
    g = sensing_window_geometry(kind, params)
    wg = p["wg_width"]
    descs: List[Dict] = []
    if kind == "SensingRing":
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg,
                      "points_um": ring_centerline(p["R"])})
        descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg,
                      "points_um": [(-g["bus_half"], -g["bus_off"]),
                                    (g["bus_half"], -g["bus_off"])]})
    else:
        for y in (0.0, p["dy"]):
            descs.append({"kind": "path", "layer": LIB_LAYER_SI, "width_um": wg,
                          "points_um": [(0.0, y), (p["Lu"], y)]})
    cx, cy = g["window_center_x"], g["window_center_y"]
    descs.append({"kind": "boundary", "layer": _LAYER_WINDOW,
                  "rings_um": [_poly_rect(cx - g["window_len"] / 2.0,
                                          cy - g["window_h"] / 2.0,
                                          cx + g["window_len"] / 2.0,
                                          cy + g["window_h"] / 2.0)]})
    return descs


def splitter_descs(params: Dict[str, float]) -> List[Dict]:
    """MMI 型 1×2 分束器几何（IR kind `Splitter` · v0.9.141 G4/M4）。

    IR 词汇（`lda_ir.photon.Splitter`）：**`length`（多模区长）/ `width`
    （多模区宽）**；基元词汇是 `L_mmi` / `W_mmi` ⇒ 二者同量异名，本函数只做
    **词汇映射 + 委托**（不复制几何代码，杜绝第二份副本）。
    输入波导宽由 `wg` 给（IR 未声明 ⇒ 取 0.5 默认），不影响被回提的
    `length` / `width`（二者只由多模矩形决定）。
    """
    w_mmi = float(params.get("width", 2.0))
    L_mmi = float(params.get("length", 5.0))
    return mmi_descs({
        "width": float(params.get("wg", 0.5)),
        "W_mmi": w_mmi,
        "L_mmi": L_mmi,
        "L_tap": float(params.get("L_tap", 2.0)),
        "out_gap": float(params.get("out_gap", w_mmi / 2.0)),
        "L_out": float(params.get("L_out", 2.0)),
    })


def mmic_descs(params: Dict[str, float]) -> List[Dict]:
    """N×1 合波器几何（IR kind `MMIC` · WDM 网格 P&R 平面输出收口）。

    `MMIC` 是 `MMI` 的**镜像**：N 个输入在左（线性阵列，居中）、单输出在右。
    词汇与 `MMI` 同（`L_mmi` / `L_tap` / `L_out` / `width`（= `W_mmi`）/
    `out_gap`），多一个 **`n_in`**。
    🔴 与 `placement.port_anchor("MMIC")` 逐点一致：out=(L_tap, 0)；
    in{j} 中心 y=(j−(n_in+1)/2)·step、x=−(L_mmi+L_tap+L_out)，step=w+out_gap。
    （**不**用 mmi_descs 镜像：mmi_descs 固定 2 输出，n_in>2 时几何与端口表
    会对不上 —— 那是「静默画错」而不是「少画」。）
    """
    w = float(params.get("width", 0.5))
    W = float(params.get("W_mmi", 6.0))
    L = float(params.get("L_mmi", 20.0))
    Lt = float(params.get("L_tap", 4.0))
    gap = float(params.get("out_gap", 0.5))
    Lo = float(params.get("L_out", 3.0))
    n_in = int(params.get("n_in", 2))
    yo = w / 2.0 + gap / 2.0
    step = yo * 2.0

    descs: List[Dict] = []
    # 合波输出波导（右）
    descs.append({"kind": "path", "layer": 1, "width_um": w,
                  "points_um": [(0.0, 0.0), (Lt, 0.0)]})
    # 输出 taper（多模区宽 W → 输出波导宽 w）
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [taper_polygon(W, w, Lt, profile="linear")]})
    # 多模干涉区（矩形 x∈[−L, 0]，y∈[−W/2, W/2]，逆时针）
    descs.append({"kind": "boundary", "layer": 1,
                  "rings_um": [[(-L, -W / 2.0), (0.0, -W / 2.0),
                                (0.0, W / 2.0), (-L, W / 2.0)]]})
    # N 路输入：taper（窄 w → 宽 W）+ 输入波导
    for j in range(1, n_in + 1):
        yc = (j - (n_in + 1) / 2.0) * step
        poly = [(x, yy + yc)
                for x, yy in taper_polygon(w, W, Lt, x0=-L - Lt,
                                           profile="linear")]
        descs.append({"kind": "boundary", "layer": 1, "rings_um": [poly]})
        descs.append({"kind": "path", "layer": 1, "width_um": w,
                      "points_um": [(-L - Lt - Lo, yc), (-L - Lt, yc)]})
    return descs


def mzi_descs(params: Dict[str, float]) -> List[Dict]:
    """Clements 网格 MZI 单元几何（IR kind `MZI` · v0.9.141 G4/M4）。

    IR 词汇（`mesh_pnr` / `wdm_mesh_pnr` 的 add_device 调用）：**`Lu`（单元
    长度）/ `dy`（上下轨间距）/ `wg`（波导宽）/ `gap`（相邻单元耦合间隙）**。
    几何 = 两条水平臂 PATH，(0,0)→(Lu,0) 与 (0,dy)→(Lu,dy)，与
    `placement.port_anchor("MZI")` 的 in1/out1（下轨 y=0）、in2/out2
    （上轨 y=dy）**逐点一致**。
    🔴 `gap` **不在本单元几何内**：网格里耦合发生在**相邻** MZI 之间
    （单元自身不含定向耦合器几何）⇒ `gap` 属「几何不编码」类，见
    `lvs_geom.PARAM_TAXONOMY`。
    """
    Lu = float(params.get("Lu", 20.0))
    dy = float(params.get("dy", 4.0))
    w = float(params.get("wg", params.get("width", 0.5)))
    return [
        {"kind": "path", "layer": 1, "width_um": w,
         "points_um": [(0.0, 0.0), (Lu, 0.0)]},
        {"kind": "path", "layer": 1, "width_um": w,
         "points_um": [(0.0, dy), (Lu, dy)]},
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
    # v0.9.141（G4/M4）：三件此前无版图几何的链路器件类补几何
    if kind == "splitter":
        return splitter_descs(params)
    if kind == "mmic":
        return mmic_descs(params)
    if kind == "mzi":
        return mzi_descs(params)
    # v0.9.191（PM 征程 M3）：光子存储单元（光通路 + GST 相变段 + 双侧微加热器）。
    if kind in ("pcmcell", "pcm_cell", "pcm"):
        return pcm_cell_descs(params)
    # v0.9.210（PS 征程 M1/G4）：传感窗口开窗器件（环 / 双 MZI 臂 + 窗口层）。
    if kind in ("sensingring", "sensing_ring"):
        return sensing_window_descs("SensingRing", params)
    if kind in ("sensingmzi", "sensing_mzi"):
        return sensing_window_descs("SensingMZI", params)
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
    # ── v0.9.178（M2 · G-OI2）：收发器器件类补可制造性几何量 ────────────────
    # 🔴 此前这 6 类**无 DRC 入口**（`primitive_geometry` 与 `drc_check_device`
    #    双双 `raise ValueError`）⇒ 收发器真 GDS 里这些器件**只能进 GDS、进不了
    #    DRC**（与 wdm_mesh_pnr 只守 MZI 死标量同族）。几何量取自各 `*_descs` 的
    #    实际多边形（单一真源：派生自 descs 用的同名参数）。
    if kind in ("modulator", "mzimodulator", "mzi_modulator"):
        w = float(params.get("width", 0.5))
        ag = float(params.get("arm_gap", 4.0))
        eg = float(params.get("elec_gap", 1.0))
        # 两臂**内缘**间距 = arm_gap − w；电极与臂外缘间距 = elec_gap。
        return {"min_width": w, "min_space": min(ag - w, eg)}
    if kind in ("photodetector", "photo_detector"):
        w = float(params.get("width", params.get("wg", 0.5)))
        Wd = float(params.get("det_w", params.get("W", 5.0)))
        # 吸收区（宽）+ 输入波导（窄）⇒ 最小横向特征取二者较小。
        return {"min_width": min(w, Wd)}
    if kind == "mmic":
        return {"min_width": float(params.get("width", 0.5)),
                "min_space": float(params.get("out_gap", 0.5))}
    if kind == "splitter":
        # IR 词汇：`width`(=W_mmi) / `length`(=L_mmi)；最小横向特征在**波导宽**。
        return {"min_width": float(params.get("wg", 0.5)),
                "min_space": float(params.get("out_gap", 1.0))}
    if kind in ("phaseshifter", "phase_shifter"):
        return {"min_width": float(params.get("width", params.get("wg", 0.5))),
                "min_space": float(params.get("gap_heat", 1.0))}
    if kind == "mzi":
        return {"min_width": float(params.get("wg", params.get("width", 0.5)))}
    # v0.9.191（PM 征程 M3）：光子存储单元——GST 层宽度 / 加热线宽 / 层间间距三闸。
    if kind in ("pcmcell", "pcm_cell", "pcm"):
        g = pcm_cell_geometry(params)
        return {"min_width": g["min_width"], "min_space": g["min_space"],
                "min_pad": g["min_pad"]}
    # v0.9.210（PS 征程 M1/G4）：传感窗口器件——基础几何（宽/间距/弯曲半径）
    # + **窗口工艺规则**（窗口宽 / 窗口边→芯余量 / 窗口端留白）+ 开窗区包封=0。
    if kind in ("sensingring", "sensing_ring", "sensingmzi", "sensing_mzi"):
        K = ("SensingRing" if kind.startswith("sensingr") else "SensingMZI")
        g = sensing_window_geometry(K, params)
        sp = _sens_p(K, params)
        out = {"min_width": sp["wg_width"], "min_space": sp["gap"],
               "min_window": g["window_w"],
               "min_window_margin": g["window_margin"],
               "min_window_end": g["window_end_gap"],
               "min_clad_enclosure": g["clad_enclosure"]}
        if K == "SensingRing":
            out["min_bend_R"] = sp["R"]
        return out
    raise ValueError(f"真实版图基元暂不支持 kind={kind}")
