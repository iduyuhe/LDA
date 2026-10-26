# -*- coding: utf-8 -*-
"""模式求解器「响应性」审计与 E1 抬升预算（v0.9.314）。

═══ 这个模块为什么存在 ═══
「抬那 6 道自证桩（E1/E3–E7）」这句话背后藏着一个默认假设：
**只要把 golden 与某个求解器的输出一比，就是在验证。**
本模块证明这个假设是错的，并给出一个可机核的补丁判据。

三道实测（全部可在本机复算，不依赖任何外部数据）：

  ① **E1 抬得动**：全矢量 staggered FV-FDM 解 500×220 SOI 直波导，
     `n_g = 4.179230`，实测 golden `4.18` ⇒ 残差 **7.7e-4**，tol 0.10 的 **1/130**。
     材料色散必须开（关掉得 4.0434，差 0.137 > tol）—— 这不是调参，是物理。
  ② **B2 是假绿**：它的候选 `b2_fvfdm_neff` 把 shift-invert 的**种子**
     `sigma=(2.65·k0)²` 写死，而选模取「返回簇里 n_eff 最小的那个」
     ⇒ 返回值的下限就是种子。实测：σ=2.65 ⇒ 2.645，σ=3.40 ⇒ 3.397；
     给一块 **5×2 µm 的硅**（真值必趋 n_core=3.48）它答 **2.6445**。
  ③ **B2 的 golden 也是错的**：EIM 两步法在高对比度窄条上系统性高估，
     w=0.4/0.5/0.6/1.0/2.0 ⇒ 与全矢量的差 −0.332/−0.198/−0.128/−0.038/−0.009，
     w→∞ 收敛到同一平板极限（2.8529 精确解）。**tol=0.05 却去比对 0.198 的偏差**。

⇒ 两条结论各自独立，但必须一起读：
  · 候选「不能失败」（种子钉死）⇒ 它的 PASS 不构成任何证据；
  · golden「本身偏了 3.9×tol」⇒ 就算候选没坏，这条锚验的也不是真值。

═══ 新立判据：响应率 ρ ═══
     ρ ≡ |Δ候选| / |Δ参考|   同一组参数扰动下
「在 tol 内」只说明没偏；**能不能偏**要靠 ρ。ρ≈0 = 常数函数 ⇒ 恒 PASS 的假绿；
ρ≈1 且符号一致 = 候选真的跟着物理走。ρ 与「可证伪性」互补：
后者问「扰动后会不会 FAIL」，前者问「扰动后会不会动」——**常数候选在后者上反而
更安全**（golden 一动，差就变大，看起来像"抓到了错"），这正是它骗过 8 项判据的原因。

对外一律如实：本模块只做数值一致性，不宣称任何制造/性能指标；LLM 永不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

#: SOI 平台折射率（与 `full_vector_mode_solver` 的自校锚同一取值，λ=1.55 µm）
N_SI = 3.4777
N_SIO2 = 1.4441


def _solver(name: str):
    """双路导入（项目铁律：不得只依赖单一路径 —— 包路径 / 裸目录）。"""
    try:                                                        # 仓库根在 sys.path
        mod = __import__("lda.lda_solver.%s" % name, fromlist=[name])
        return mod
    except ImportError:                                         # 直接跑本文件
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "lda_solver")
        if path not in sys.path:
            sys.path.insert(0, path)
        return __import__(name)


# ---------------------------------------------------------------------------
# 1. 精确可解的对照支路：对称平板 TE0
# ---------------------------------------------------------------------------
def _slab_neff(thickness_um: float, n_core: float, n_clad: float,
               wl_um: float, pol: str = "TE") -> float:
    """对称平板基模 n_eff（精确超越方程，二分求解）。

    🔴 本函数与 `lda_harness.golden._slab_neff` **逐位同构**（同一方程、同一
    二分区间、同一 300 次迭代）。这不是抄——是**故意的两处表示**：专属门禁
    拿两处逐位对拍，任一处被改动都会红。「两个实现各自算、从不互核」正是
    B2/E1 归因错误的温床。
    """
    d = thickness_um / 2.0
    arg = n_core ** 2 - n_clad ** 2
    if arg <= 0:
        return n_clad
    V = (2.0 * math.pi / wl_um) * d * math.sqrt(arg)
    if V < 1e-9:
        return n_clad
    umax = min(V, math.pi / 2.0 - 1e-9)
    lo, hi = 0.0, umax
    for _ in range(300):
        u = 0.5 * (lo + hi)
        v = math.sqrt(max(V * V - u * u, 0.0))
        if pol == "TE":
            f = u * math.tan(u) - v
        else:
            f = u * math.tan(u) - (n_core ** 2 / n_clad ** 2) * v
        if f > 0:
            hi = u
        else:
            lo = u
    u = 0.5 * (lo + hi)
    return math.sqrt(max(n_core ** 2 - (u * wl_um / (2.0 * math.pi * d)) ** 2, 0.0))


def slab_te0_neff(n_core: float, n_clad: float, h_um: float, wl_um: float) -> float:
    """厚度 h_um 的对称平板 TE0 模 n_eff（精确解）。"""
    return _slab_neff(h_um, n_core, n_clad, wl_um, "TE")


def slab_limits(n_core: float = N_SI, n_clad: float = N_SIO2,
                wl_um: float = 1.5476) -> Dict[str, object]:
    """两条**已知答案**的极限（对照支路）。

    h→0：模式几乎全在包层 ⇒ n_eff → n_clad；
    h→∞：模式几乎全在芯层 ⇒ n_eff → n_core。
    🔴 任何"波导求解器"都必须先过这两关，否则它在中间尺寸上的数没有意义。
    """
    thin = slab_te0_neff(n_core, n_clad, 5e-3, wl_um)
    thick = slab_te0_neff(n_core, n_clad, 3.0, wl_um)
    return {
        "thin_h_um": 5e-3, "thin_neff": thin,
        "thin_gap_to_clad": thin - n_clad,
        "thick_h_um": 3.0, "thick_neff": thick,
        "thick_gap_to_core": n_core - thick,
    }


# ---------------------------------------------------------------------------
# 2. EIM 两步法（B2 的 golden 族）与全矢量的系统偏差
# ---------------------------------------------------------------------------
def eim_two_step(w_um: float, h_um: float, n_core: float, n_clad: float,
                 wl_um: float, pol: str = "TE") -> float:
    """两步有效折射率法（先横向 slab → 再纵向 slab）。

    与 `golden.b2_soi_waveguide_neff` 逐位一致（同一顺序：先 width 后 height）。
    🔴 顺序不能换：先高后宽会给出 2.624 而非 2.651 —— 换序即换答案，
    说明这套"两步降维"本身没有唯一口径，这已是它的第一个危险信号。
    """
    n_x = _slab_neff(w_um, n_core, n_clad, wl_um, pol)
    return _slab_neff(h_um, n_x, n_clad, wl_um, pol)


def eim_order_sensitivity(w_um: float, h_um: float, n_core: float, n_clad: float,
                          wl_um: float) -> Dict[str, float]:
    """同一 EIM 在两种降维顺序下的差 —— 一个不该存在的自由度。"""
    fwd = eim_two_step(w_um, h_um, n_core, n_clad, wl_um)
    rev = _slab_neff(h_um, n_core, n_clad, wl_um, "TE")
    rev = _slab_neff(w_um, rev, n_clad, wl_um, "TE")
    return {"width_first": fwd, "height_first": rev, "gap": fwd - rev}


def vector_neff(w_um: float, h_um: float, wl_um: float = 1.5476,
                n_core: float = N_SI, n_clad: float = N_SIO2,
                h_grid: Optional[float] = None,
                pol: str = "TE") -> float:
    """全矢量 staggered FV-FDM 的基模 n_eff（Fallahkhair 2008，Yee 交错）。

    该实现与一篇公开论文的**独立实现**逐位对拍过（600×220 TE0：2.570410 vs
    2.570409755），并与商用 FDE 差 0.004 —— 是本仓唯一有外部标量背书的模式核。
    """
    fvm = _solver("full_vector_mode_solver")
    kw = {}
    if h_grid is not None:
        kw["h_grid"] = h_grid
    return fvm.neff_strip(w_um, h_um, wl_um, n_core=n_core, n_clad=n_clad, pol=pol, **kw)


def eim_error_curve(widths: Sequence[float] = (0.5, 1.0, 2.0),
                    h_um: float = 0.22, wl_um: float = 1.5476,
                    h_grid: Optional[float] = None,
                    n_core: float = N_SI, n_clad: float = N_SIO2) -> List[Dict[str, float]]:
    """EIM − 全矢量 的偏差曲线（宽度扫描）。

    物理内容：EIM 把二维约束拆成两次一维约束，**忽略角区**，在窄条高对比度下
    系统性高估；宽度变大 ⇒ 两次降维都趋于精确 ⇒ 偏差单调收缩到 0。
    ⇒ 这条曲线同时是「EIM 偏差是系统性的、不是随机噪声」的证据，
      也是「B2 的 tol 与 golden 不可能同时在 500×220 上成立」的证据。
    """
    out = []
    for w in widths:
        e = eim_two_step(w, h_um, n_core, n_clad, wl_um)
        v = vector_neff(w, h_um, wl_um, n_core, n_clad, h_grid=h_grid)
        out.append({"w_um": w, "eim": e, "vector": v, "gap": e - v})
    return out


# ---------------------------------------------------------------------------
# 3. E1 的合法候选：全矢量 + 材料色散 → n_g
# ---------------------------------------------------------------------------
def e1_group_index(w_um: float = 0.5, h_um: float = 0.22,
                   wl_um: float = 1.5476, d_wl: float = 0.02,
                   n_core: float = N_SI, n_clad: float = N_SIO2) -> float:
    """E1 候选：SOI 直波导群折射率（全矢量 + Si/SiO2 Sellmeier）。

    🔴 **材料色散必须开**：关掉（n 取常数）得 4.0434，与实测 4.18 差 0.137 > tol；
    开 Sellmeier 得 4.1792，差 7.7e-4。这不叫"把参数调到能过"——常数折射率是
    **错的物理**（1.54–1.56 µm 上 Si 的 n 变化 ~1e-3，但 n_g 是它的导数放大器）。
    """
    fvm = _solver("full_vector_mode_solver")
    return fvm.group_index(w_um, h_um, wl_um, n_core=n_core, n_clad=n_clad,
                           core_material="Si", clad_material="SiO2", d_wl=d_wl)


def e1_group_index_no_dispersion(w_um: float = 0.5, h_um: float = 0.22,
                                 wl_um: float = 1.5476, d_wl: float = 0.02,
                                 n_core: float = N_SI, n_clad: float = N_SIO2) -> float:
    """反向对照：常数折射率（无材料色散）下的同一候选 —— 必须**明显更差**。

    若哪天有人图快把 material 参数去掉，这条会把「残差 7.7e-4」变成「0.137」，
    专属门禁立刻红。
    """
    fvm = _solver("full_vector_mode_solver")
    return fvm.group_index(w_um, h_um, wl_um, n_core=n_core, n_clad=n_clad, d_wl=d_wl)


# ---------------------------------------------------------------------------
# 4. 弯曲效应：那个被写错过两次的数
# ---------------------------------------------------------------------------
def bend_delta_ng(R_um: float, w_um: float = 0.5, h_um: float = 0.22,
                  wl_um: float = 1.5476, window_um: float = 3.6) -> Dict[str, float]:
    """弯曲比直波导把 n_g 抬高多少（共形变换 n² → n²·(1+x/R)²）。

    实测（R=10.63 µm，即 E1 golden 那只 L=66.8 µm 环的半径）：**+0.0033**。
    半矢量同一几何下直波导 4.0228、弯曲 4.0261 ⇒ 差 0.0033，且 30→10 µm 时
    差扩大 9.0×（= (30/10)²，1/R² 律自洽）。
    """
    bm = _solver("bend_mode")
    g0, ne0 = bm.bend_waveguide_ng(w_um, h_um, wl_um, R_um=None, window_um=window_um)
    g1, ne1 = bm.bend_waveguide_ng(w_um, h_um, wl_um, R_um=R_um, window_um=window_um)
    return {"R_um": R_um, "ng_straight": g0, "ng_bend": g1,
            "delta_ng": g1 - g0, "delta_neff": ne1 - ne0}


# ---------------------------------------------------------------------------
# 4b. 层堆任意截面：默认种子一进层堆就静默选不到模（v0.9.315）
# ---------------------------------------------------------------------------
def stacked_section(wl_um: float, w_um: float, h_um: float, box_um: float,
                    clad: str = "air", h_grid: float = 0.025,
                    width_um: float = 4.0,
                    sub_um: float = 0.8, top_um: float = 0.8,
                    n_si: float = N_SI, n_sio2: float = N_SIO2) -> Dict[str, object]:
    """薄埋氧 SOI 的三层截面（Si 衬底 / BOX / Si 芯）→ ε 场 + 顶点掩码。

    为什么需要它：`full_vector_mode_solver.solve_modes_eps` 早就支持"任意 2D 截面"，
    但**没有任何调用方构造过层堆**（14 处调用全是单芯）。E3 的薄 BOX 一直卡在这里。

    🔴 掩码必须**只含波导芯**。若用缺省的 `core_vertex_mask(eps)`，它会用
    (min+max)/2 判"芯"，而 Si 衬底比芯还宽 ⇒ 衬底模被算成"芯内模"，
    选模立刻被衬底模污染。这是层堆特有的坑，单芯结构永远不会遇到。
    """
    import numpy as np
    nxc = int(round(width_um / h_grid))
    y_lo = -box_um - h_um / 2.0 - sub_um
    y_hi = h_um / 2.0 + top_um
    nyc = int(round((y_hi - y_lo) / h_grid))
    xv = np.linspace(-width_um / 2.0, width_um / 2.0, nxc + 1)
    yv = np.linspace(y_lo, y_hi, nyc + 1)
    xc = 0.5 * (xv[:-1] + xv[1:])
    yc = 0.5 * (yv[:-1] + yv[1:])
    n_clad = 1.0 if clad == "air" else n_sio2
    eps = np.full((nyc, nxc), n_clad ** 2)
    eps[yc < -box_um - h_um / 2.0, :] = n_si ** 2               # Si 衬底
    m_box = (yc >= -box_um - h_um / 2.0) & (yc < -h_um / 2.0)
    eps[m_box, :] = n_sio2 ** 2                                  # 400 nm BOX
    m_core = ((np.abs(xc) <= w_um / 2.0 + 1e-12)[None, :]
              & ((yc >= -h_um / 2.0 - 1e-12) & (yc <= h_um / 2.0 + 1e-12))[:, None])
    eps = np.where(m_core, n_si ** 2, eps)
    xvg = np.abs(xv) <= w_um / 2.0 + 1e-12
    yvg = (yv >= -h_um / 2.0 - 1e-12) & (yv <= h_um / 2.0 + 1e-12)
    return {"eps": eps, "xv": xv, "yv": yv, "mask": yvg[:, None] & xvg[None, :],
            "n_hi": n_si, "n_lo": n_clad, "h_grid": h_grid,
            "on_grid": {"w_half_over_h": (w_um / 2.0) / h_grid,
                        "h_half_over_h": (h_um / 2.0) / h_grid}}


def default_seed_blind_spot(wl_um: float = 1.5476, w_um: float = 0.45,
                            h_um: float = 0.25, box_um: float = 0.4,
                            clad: str = "air") -> Dict[str, object]:
    """**实测**：同一层堆截面，用 solver 的**缺省种子**得 0 个模（静默空列表），
    扫一片 σ 才找到 2 个模。

    缺省种子是 `σ = k0·(n_lo + 0.85·(n_hi − n_lo))` —— 它假设「只有一个高折射率芯，
    基模靠近折射率上限」。层堆里 `n_hi` 是 Si 衬底，σ 落在**衬底模簇**，被
    `conf_min` 全部剔除 ⇒ 返回 `[]`。调用方看到的是「这结构没有导模」，
    而真相是「搜索中心放错了地方」。**静默的空列表比报错更危险。**
    """
    import math
    import numpy as np
    fvm = _solver("full_vector_mode_solver")
    sec = stacked_section(wl_um, w_um, h_um, box_um, clad)
    k0 = 2.0 * math.pi / wl_um
    kw = dict(k=8, n_lo=sec["n_lo"], n_hi=sec["n_hi"],
              core_vmask=sec["mask"], conf_min=0.30)
    by_default = fvm.solve_modes_eps(sec["eps"], sec["xv"], sec["yv"], k0, **kw)
    scanned = spectrum_scan(wl_um, w_um, h_um, box_um, clad)
    return {"n_default": len(by_default),
            "n_scanned": len(scanned),
            "modes": [(round(r["neff"], 4), r["pol"], round(r["conf"], 3))
                      for r in scanned]}


def spectrum_scan(wl_um: float = 1.5476, w_um: float = 0.45, h_um: float = 0.25,
                  box_um: float = 0.4, clad: str = "air",
                  sigma_lo: float = 1.6, sigma_hi: float = 3.45,
                  step: float = 0.15, conf_min: float = 0.10,
                  sub_um: float = 0.8, h_grid: float = 0.025) -> List[Dict[str, object]]:
    """把 σ 扫一片再合并去重 —— **层堆/多芯几何的正确用法**。

    🔴 这不是"调参找答案"：σ 只是 ARPACK 的搜索中心，扫一片的代价是 k·N 次求解，
    换来的是**不漏模**。单点 σ 在层堆下会漏（见 `default_seed_blind_spot`），
    而漏掉的模不会被任何断言发现 —— 它只会让结果安静地变成 nan。
    """
    import math
    import numpy as np
    fvm = _solver("full_vector_mode_solver")
    sec = stacked_section(wl_um, w_um, h_um, box_um, clad,
                          sub_um=sub_um, h_grid=h_grid)
    k0 = 2.0 * math.pi / wl_um
    found: Dict[float, object] = {}
    for sg in np.arange(sigma_lo, sigma_hi, step):
        rs = fvm.solve_modes_eps(sec["eps"], sec["xv"], sec["yv"], k0, k=6,
                                 sigma=(float(sg) * k0) ** 2,
                                 n_lo=sec["n_lo"], n_hi=sec["n_hi"],
                                 core_vmask=sec["mask"], conf_min=conf_min)
        for r in rs:
            key = round(r.neff, 3)
            if key not in found or r.conf_core > found[key].conf_core:
                found[key] = r
    out = []
    for r in sorted(found.values(), key=lambda q: -q.neff):
        out.append({"neff": r.neff, "conf": r.conf_core,
                    "pol": "TE" if r.frac_hy_core > 0.5 else "TM"})
    return out


def stacked_group_index(pol: str = "TM", w_um: float = 0.45, h_um: float = 0.25,
                        box_um: float = 0.4, clad: str = "air",
                        wl_um: float = 1.5476, d_wl: float = 0.02) -> Dict[str, object]:
    """薄 BOX 层堆的群折射率（三点差分，三点同网格同窗口）。

    ⚠️ 这是**实算子 + Dirichlet 盒**给出的**实** n_eff。薄 BOX 下的 TM 模向 Si 衬底
    泄漏（leaky），真实 n_eff 是复数；这里的值只能当"上界型估计"，不能当精密真值。
    """
    want = pol.upper()
    vals = []
    for wl in (wl_um - d_wl, wl_um, wl_um + d_wl):
        sp = spectrum_scan(wl, w_um, h_um, box_um, clad)
        pick = [m for m in sp if m["pol"] == want]
        vals.append(pick[0]["neff"] if pick else float("nan"))
    ng = vals[1] - wl_um * (vals[2] - vals[0]) / (2.0 * d_wl)
    return {"pol": want, "neff_mid": vals[1],
            "neff_lo": vals[0], "neff_hi": vals[2], "n_g": ng,
            "neffs": vals}


def window_sensitivity(pol: str = "TM", wl_um: float = 1.5476,
                       w_um: float = 0.45, h_um: float = 0.25,
                       box_um: float = 0.4, clad: str = "air",
                       subs: Sequence[float] = (0.8, 1.4, 2.0)) -> Dict[str, object]:
    """改求解窗口，答案动多少？——**「导模 vs 漏模」的单点判据**。

    真导模：场在包层指数衰减 ⇒ 窗口加大，n_eff 逐位不变。
    漏模（薄 BOX 的 TM）：场持续向 Si 衬底辐射 ⇒ 实算子只能靠 Dirichlet 盒截断，
    窗口就是人为边界 ⇒ **窗口一动答案就动**。

    ⇒ 窗口敏感度 > 1e-2 就该判定「这不是可判的实模」，而不是把它当成求解器噪声。
    """
    vals = []
    for sub in subs:
        sp = spectrum_scan(wl_um, w_um, h_um, box_um, clad, sub_um=sub)
        pick = [m for m in sp if m["pol"] == pol.upper()]
        vals.append(pick[0]["neff"] if pick else float("nan"))
    finite = [v for v in vals if v == v]
    spread = (max(finite) - min(finite)) if len(finite) > 1 else float("nan")
    # 🔴 阈值 1e-3 不是拍的：同仓半矢量对**真导模**的窗口散射实测 **<1e-5**
    #    （见 E2 note），比它大两个数量级就不是"数值噪声"。
    #    「任一窗口丢模」也算 LEAKY —— 导模不会因为盒子加大就消失。
    lost = len(finite) < len(vals)
    verdict = ("GUIDED" if (spread == spread and spread < 1e-3 and not lost)
               else "LEAKY")
    return {"pol": pol.upper(), "windows": list(subs), "neffs": vals,
            "spread": spread, "lost_window": lost, "verdict": verdict}


def e3_budget(n_g_ref: float = 4.92, n_g_cand: Optional[float] = None,
              fsr_meas: float = 10.44, tol_fsr: float = 0.10,
              R_um: float = 7.5, wl_um: float = 1.5576) -> Dict[str, float]:
    """E3 的 tol 预算：要判到 FSR 0.1 nm，n_g 需要准到多少？

    FSR = λ²/(n_g·2πR) ⇒ dFSR/FSR = −dn_g/n_g ⇒ 相对容差 ≡ tol_fsr/FSR。
    """
    if n_g_cand is None:
        n_g_cand = float(stacked_group_index("TM", wl_um=wl_um)["n_g"])
    # λ、R 都是 µm ⇒ FSR 先得 µm，×1000 转 nm 才能与实测 10.44 nm 比
    fsr = lambda ng: (wl_um ** 2) / (ng * 2.0 * math.pi * R_um) * 1000.0   # noqa: E731
    fsr_c = fsr(n_g_cand)
    rel_tol = tol_fsr / fsr_meas
    return {
        "n_g_ref": n_g_ref, "n_g_cand": n_g_cand,
        "n_g_abs_tol": rel_tol * n_g_ref,
        "n_g_rel_err": abs(n_g_cand - n_g_ref) / n_g_ref,
        "fsr_meas": fsr_meas, "fsr_cand": fsr_c,
        "fsr_err": abs(fsr_c - fsr_meas),
        "margin_x": (tol_fsr / abs(fsr_c - fsr_meas)) if abs(fsr_c - fsr_meas) > 0 else float("inf"),
        "verdict": ("PASS" if abs(fsr_c - fsr_meas) <= tol_fsr else "FAIL"),
    }


# ---------------------------------------------------------------------------
# 5. 新立判据：响应率 ρ 与符号一致率
# ---------------------------------------------------------------------------
def response_ratio(pairs: Sequence[Tuple[float, float]],
                   refs: Sequence[Tuple[float, float]]) -> Dict[str, object]:
    """候选的响应率 ρ ≡ |Δ候选| / |Δ参考|（逐扰动取最小）与符号一致率。

    Args:
        pairs: [(未扰动候选, 扰动后候选), ...]，同一组扰动
        refs:  同一组扰动的 [(未扰动参考, 扰动后参考), ...]

    Returns:
        dict(min_ratio, ratios, sign_consistency, n)

    🔴 **符号一致率**单列：坏的候选不止"不响应"这一种，还有"反向响应"。
    `b2_fvfdm_neff` 在 n_si −10% 时给出**更高**的 n_eff（2.6526 > 2.6479），
    这是莫尔效应级的错误，但它仍然落在 tol 内 ⇒ 只有符号能抓到它。
    """
    ratios = []
    signs = 0
    for (c0, c1), (r0, r1) in zip(pairs, refs):
        dc, dr = c1 - c0, r1 - r0
        if abs(dr) < 1e-15:
            continue
        ratios.append(abs(dc) / abs(dr))
        if dc * dr > 0:
            signs += 1
    n = len(ratios)
    return {
        "min_ratio": min(ratios) if ratios else 0.0,
        "ratios": ratios,
        "sign_consistency": (signs / n) if n else 0.0,
        "n": n,
    }


def verdict_from_rho(min_ratio: float, sign_consistency: float,
                     rho_floor: float = 0.5) -> str:
    """把 ρ 翻成三值判决（判据本身只有这三档，不允许"大概可以"）。"""
    if min_ratio < 1e-6:
        return "DEAD_CONSTANT"          # 常数函数：恒 PASS，零证据
    if min_ratio < rho_floor or sign_consistency < 0.99:
        return "NOT_RESPONSIVE"         # 有动但不跟物理走
    return "RESPONSIVE"


# ---------------------------------------------------------------------------
# 6. tol 预算（E1）
# ---------------------------------------------------------------------------
def e1_budget(golden: float = 4.18, tol: float = 0.10,
              cand: Optional[float] = None) -> Dict[str, float]:
    """E1 的残差/余量/可证伪信号三条一起报 —— 单一计算处。"""
    if cand is None:
        cand = e1_group_index()
    residual = abs(cand - golden)
    return {
        "cand": cand, "golden": golden, "tol": tol,
        "residual": residual,
        "margin_x": (tol / residual) if residual > 0 else float("inf"),
        "residual_over_tol": residual / tol,
    }


def falsifiability_signal(w_um: float = 0.5, h_um: float = 0.22,
                          wl_um: float = 1.5476, rel: float = 0.10,
                          n_core: float = N_SI) -> Dict[str, float]:
    """E1 候选的「10% 扰动信号」：判据窗口 tol 必须落在 baseline 与 signal 之间。

    实测：n_core ±10% ⇒ n_g 4.5868 / 3.6744，单侧幅度 **≈0.46**，是 tol 的 4.6×。
    """
    base = e1_group_index(w_um, h_um, wl_um, n_core=n_core)
    up = e1_group_index(w_um, h_um, wl_um, n_core=n_core * (1.0 + rel))
    dn = e1_group_index(w_um, h_um, wl_um, n_core=n_core * (1.0 - rel))
    return {"base": base, "up": up, "down": dn,
            "signal": min(abs(up - base), abs(dn - base))}


# ---------------------------------------------------------------------------
# 7. 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> List[Tuple[str, bool, str]]:
    """自检（快：只含精确解与两次全矢量解，~5 s）。

    重型实测（E1 候选三点差分、弯曲共形变换、种子扫描）放在
    `run_empirical_anchor_smoke.py` 与 `run_benchmark_falsifiability_smoke.py`，
    那里本来就是"跑真数"的地方。
    """
    out: List[Tuple[str, bool, str]] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    # ① 两条极限（对照支路）
    lim = slab_limits()
    chk("① h→0 平板解趋包层（gap < 1e-2）", lim["thin_gap_to_clad"] < 1e-2,
        "gap=%.2e" % lim["thin_gap_to_clad"])
    chk("② h→3µm 平板解趋芯层（gap < 2e-2）", lim["thick_gap_to_core"] < 2e-2,
        "gap=%.2e" % lim["thick_gap_to_core"])

    # ③ EIM 与自身逐位一致（两次调用）—— 防"每次算都不一样"的非确定性
    a = eim_two_step(0.5, 0.22, 3.48, 1.44, 1.55)
    b = eim_two_step(0.5, 0.22, 3.48, 1.44, 1.55)
    chk("③ EIM 幂等（逐位相同）", a == b, "%.12f" % a)

    # ④ 降维顺序敏感：换序即换答案 ⇒ 这套降维无唯一口径
    s = eim_order_sensitivity(0.5, 0.22, 3.48, 1.44, 1.55)
    chk("④ EIM 换序差 > 0.01（同一近似法的自由度）", abs(s["gap"]) > 0.01,
        "width_first=%.4f height_first=%.4f gap=%+.4f"
        % (s["width_first"], s["height_first"], s["gap"]))

    # ⑤ EIM 偏差随宽度单调收缩（这是"系统性"而非"随机噪声"的判据）
    curve = eim_error_curve(widths=(0.5, 0.6))
    gaps = [c["gap"] for c in curve]
    chk("⑤ EIM 偏差随宽度收缩（0.5→0.6 变窄 36%）",
        gaps[0] > gaps[1] and abs(gaps[1]) < 0.15,
        "gap(0.5)=%+.4f gap(0.6)=%+.4f" % (gaps[0], gaps[1]))
    chk("⑥ 500×220 处 |EIM−全矢量| > 3×tol_B2",
        abs(gaps[0]) > 3 * 0.05, "|gap|=%.4f vs 3*0.05" % abs(gaps[0]))

    # ⑦ EIM 在宽条极限回到精确平板（⇒ 它的偏差是"窄条高对比度"效应，非实现 bug）
    eim_wide = eim_two_step(3.0, 0.22, 3.48, 1.44, 1.5464)
    slab_ex = slab_te0_neff(3.48, 1.44, 0.22, 1.5464)
    chk("⑦ EIM 在 3µm 宽极限 ≈ 平板精确解（1.5e-2 内，残留=第一步降维）",
        abs(eim_wide - slab_ex) < 1.5e-2,
        "eim=%.6f slab=%.6f d=%.1e" % (eim_wide, slab_ex, abs(eim_wide - slab_ex)))

    # ⑧ ρ 判据的自洽（喂两个已知答案）
    r = response_ratio([(1.0, 1.4)], [(1.0, 2.0)])
    chk("⑧ ρ=0.4 ⇒ NOT_RESPONSIVE（低于 0.5 档）",
        verdict_from_rho(r["min_ratio"], r["sign_consistency"]) == "NOT_RESPONSIVE",
        "rho=%.3f" % r["min_ratio"])
    r2 = response_ratio([(1.0, 2.0)], [(1.0, 2.0)])
    chk("⑨ ρ=1 且同号 ⇒ RESPONSIVE",
        verdict_from_rho(r2["min_ratio"], r2["sign_consistency"]) == "RESPONSIVE",
        "rho=%.3f" % r2["min_ratio"])
    r3 = response_ratio([(1.0, 0.9)], [(1.0, 2.0)])
    chk("⑩ ρ 够大但反向 ⇒ NOT_RESPONSIVE（符号能把「动错方向」抓出来）",
        verdict_from_rho(r3["min_ratio"], r3["sign_consistency"]) == "NOT_RESPONSIVE",
        "rho=%.3f sign=%.2f" % (r3["min_ratio"], r3["sign_consistency"]))

    # ⑪ 层堆截面：默认种子静默返回 0 模，扫 σ 才能拿到（v0.9.315）
    _bs = default_seed_blind_spot()
    chk("⑪ 层堆截面：缺省种子返回 0 模（静默空列表）而扫描 σ 得 ≥2 模",
        _bs["n_default"] == 0 and _bs["n_scanned"] >= 2,
        "default=%d scanned=%d modes=%s" % (_bs["n_default"], _bs["n_scanned"],
                                            _bs["modes"]))
    # ⑫ 掩码只含波导芯（衬底不得被算成"芯内"）
    _sec = stacked_section(1.5476, 0.45, 0.25, 0.4)
    _mask_cells = int(_sec["mask"].sum())
    _core_cells = int(round(0.45 / 0.025 + 1) * round(0.25 / 0.025 + 1))
    chk("⑫ 层堆掩码只圈波导芯（顶点数 ≤ 芯格数，不含 4µm 宽衬底）",
        _mask_cells <= _core_cells + 8,
        "mask=%d core≈%d（若用缺省 core_vertex_mask 会把衬底算进去）"
        % (_mask_cells, _core_cells))

    # ⑬ E3 预算的**双向**：喂实测 n_g 必须 PASS，喂现算 n_g 必须 FAIL
    _pass = e3_budget(n_g_cand=4.92)
    _fail = e3_budget(n_g_cand=4.5403)
    chk("⑬ E3 预算双向（n_g=4.92⇒PASS / 4.5403⇒FAIL，差 9.0× tol）",
        _pass["verdict"] == "PASS" and _fail["verdict"] == "FAIL"
        and _fail["margin_x"] < 0.2,
        "PASS@4.92 FSR=%.3f / FAIL@4.5403 FSR=%.3f 差=%.3f nm 余量=%.3f×"
        % (_pass["fsr_cand"], _fail["fsr_cand"], _fail["fsr_err"], _fail["margin_x"]))

    for name, ok, detail in out:
        if verbose:
            print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, ("| " + detail) if detail else ""))
    return out


def main() -> int:
    res = run_selfchecks(verbose=True)
    bad = [r for r in res if not r[1]]
    print("\n%d/%d PASS" % (len(res) - len(bad), len(res)))
    return 0 if not bad else 1


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(main())
