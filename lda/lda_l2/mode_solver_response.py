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
