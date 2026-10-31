#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E47 门禁：**多角（PVT）互连线延迟窗口** —— 把主链的「单角单点」升级为 min/typ/max。

## 本门禁守什么
E45 的主链只报**单角 tt** 的一个 Elmore 值。signoff 要的是**窗口**，不是单点。
但「多角 = 乘系数」这句话本身有个陷阱，本门禁的前四条就是围着它转的：

> **定理**：纯 RC 树 + 统一缩放（所有 R × kr、所有 C × kc）时，
> `τ_corner = kr·kc·τ_tt` **精确成立**。⇒ 只有片电阻的模型，多角窗口退化成一个标量，
> 所有网宽度一模一样 —— 那种「多角」是空转的。

所以真要做多角，必须有**不跟片电阻同角**的量。本模型里是**通孔电阻** `R_via`：
它的工艺灵敏度与片电阻不同源（界面/填充 vs 掺杂/线厚）。于是

    τ_k = kr_k·kc_k·τ_metal + kv_k·kc_k·τ_via

两项之比随网自身构成变化 ⇒ 每网窗口不同。**这条可证伪**：把 kv 设成与 kr 相同，
窗口差异必须**精确消失**（D4），而默认参数下必须**确实存在**（D5）。

| # | 守护 | 金标 |
|---|---|---|
| D1 | 拆分加法闭合 | 逐网 `τ == τ_metal + τ_via`（≤1e-9 fs），拓扑不动只改阻值 |
| D2 | **语义对照组** | 无通孔的直导线必须 `τ_via ≡ 0 ∧ τ_metal == τ`（钉死「哪一类是哪一类」） |
| D3 | 纯增量 | tt 角（kr=kc=kv=1）与 v0.9.349 的 `elmore_network` 逐位一致（≤1e-12） |
| D4 | **定理退化** | `kv:=kr` ⇒ `τ_k == kr·kc·τ_tt` 精确（≤1e-9）∧ 各网 spread 均匀（比 == 1） |
| D5 | **非平凡** | 默认 `kv≠kr` ⇒ 各网窗口宽度**不同**（hi/lo > 1.01） |
| D6 | 通孔主导 + 量级 | `via_share ≥ 0.5`（实测 0.79–0.94）∧ 延迟落在正的 fs 量级 |
| D7 | 三角单调 | 每网 `min ≤ typ ≤ max` |
| D8 | 窗口落在闭式界内 | 每网 spread ∈ `[kr_ss·kc_ss/(kr_ff·kc_ff), kv_ss·kc_ss/(kv_ff·kc_ff)]`（全金属界 … 全通孔界） |
| D9 | 反向探针 | 交换 ff/ss 的通孔因子 ⇒ 单调性必**破**（`τ_ss < τ_ff`） |
| D10 | 同源 | `dpvt.CORNERS is dsignoff.CORNERS`（引用，不是副本） |
| D11 | 确定性 | 两次 `block_window` 逐位一致 |
| D0 | 耗时 | < 阈值 |

## 诚实口径（不许省）
- 🔴 **只做互连线**：不含标准单元/器件角 ⇒ **不是**「路径延迟窗口」。真实 signoff 还要
  `.lib` 多角时序 + derating/OCV + clock，本仓都没有。
- 🔴 **不是 OCV/AOCV/POCV**：这是「角缩放」，没有统计变异与 derating 系数。
- 🔴 **角因子是演示假设**（含 `VIA_CORNERS` 比片电阻更宽这一点）；非任何 foundry PVT 数据。
- 🔴 净增 **0 锚**（浮点组合，resid≡0）⇒ 门禁形态。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dpnr as PN          # noqa: E402
from lda_l2.ecore import dctrl as CT         # noqa: E402
from lda_l2.ecore import dsignoff as SG      # noqa: E402
from lda_l2.ecore import dspef as SP         # noqa: E402
from lda_l2.ecore import dpvt as PV          # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 120.0
AN_TOL_FS = 1e-9            # 拆分/定理的绝对容差（fs）
AN_TOL_TT = 1e-12           # tt 角与既有实现的逐位一致（fs）
AN_TRIVIAL_MIN_X = 1.01     # 各网窗口宽度的「确有差异」门限
AN_VIA_SHARE_MIN = 0.5      # 通孔主导门限（实测 0.79–0.94）

CASE_N = 12
CASE_COLS = 4

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def build_block():
    """跑一遍主链（布局 → 路由 → 提取），拿到 E45 那条链的真实网络。"""
    nl = CT.build()["netlist"]
    pl = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS)
    rt = PN.route_block(nl, pl)
    nw = SP.extract_network([s for s in rt["shapes_route"] if s.net],
                            design="LDA_PVT_BLOCK", seg_um=0.5, with_coupling=False)
    return pl, rt, nw["nets"]


def main():
    t0 = time.time()
    print("=" * 78)
    print("E47 · 多角（PVT）互连线延迟窗口（角缩放，不是 OCV）")
    print("=" * 78)

    pl, rt, nets = build_block()
    bw = PV.block_window(nets)

    # ── D1 拆分加法闭合 ────────────────────────────────────────
    worst_add = bw["additivity_worst_fs"]
    check("D1 拆分加法闭合：逐网 τ == τ_metal + τ_via（拓扑不动，只把一类边的 R 置 0）",
          worst_add <= AN_TOL_FS,
          "%d 网 · 最差残差 %.3e fs（容差 %.0e）" % (bw["n_nets"], worst_add, AN_TOL_FS))

    # ── D2 语义对照组（无通孔导线 ⇒ τ_via ≡ 0）──────────────────
    wire = SP.build_wire_network(20.0, 0.24, 8, net="w0")["nets"]["w0"]
    pw = PV.split_tau(wire)
    check("D2 语义对照组：无通孔的直导线 τ_via 必须恰好 0 ∧ τ_metal == τ（防「金属/通孔」写反）",
          pw["n_via"] == 0 and abs(pw["tau_via_fs"]) <= AN_TOL_FS
          and abs(pw["tau_metal_fs"] - pw["tau_fs"]) <= AN_TOL_FS,
          "tau=%.6f · metal=%.6f · via=%.3e · n_via=%d"
          % (pw["tau_fs"], pw["tau_metal_fs"], pw["tau_via_fs"], pw["n_via"]))

    # ── D3 纯增量：tt 角 == v0.9.349 的 elmore_network ───────────
    worst_tt = 0.0
    for name in sorted(nets):
        d = SP.elmore_network(nets[name])["max_fs"]
        worst_tt = max(worst_tt, abs(bw["nets"][name]["tau_fs"]["tt"] - d))
    check("D3 纯增量：tt 角（kr=kc=kv=1）与 v0.9.349 的既有 elmore_network 逐位一致",
          worst_tt <= AN_TOL_TT, "最差 |Δ| %.3e fs（容差 %.0e）" % (worst_tt, AN_TOL_TT))

    # ── D4 定理退化（kv := kr ⇒ 精确标量积）─────────────────────
    tc = PV.theorem_check(nets)
    check("D4 定理退化：把通孔角设成与片电阻角相同 ⇒ τ_k 精确 == kr·kc·τ_tt ∧ 各网 spread 均匀",
          tc["max_abs_err_fs"] <= AN_TOL_FS
          and tc["spread_uniformity"] is not None
          and abs(tc["spread_uniformity"] - 1.0) <= 1e-12,
          "max|τ−kr·kc·τ_tt|=%.2e fs · 均匀比 %.12f" % (tc["max_abs_err_fs"], tc["spread_uniformity"]))

    # ── D5 非平凡（各网窗口宽度必须不同）────────────────────────
    lo_s, hi_s = bw["spread_range"]
    check("D5 非平凡：默认 kv≠kr 时各网窗口宽度**因网而异**（否则多角退化成单一标量）",
          lo_s is not None and hi_s / lo_s > AN_TRIVIAL_MIN_X,
          "spread %.4f× .. %.4f×（比 %.4f > 门限 %.2f）"
          % (lo_s, hi_s, hi_s / lo_s, AN_TRIVIAL_MIN_X))

    # ── D6 通孔主导 + 延迟量级锚 ────────────────────────────────
    vlo, vhi = bw["via_share_range"]
    tau_ok = all(0.0 < v["tau_fs"]["tt"] < 100.0 for v in bw["nets"].values())
    check("D6 通孔主导 + 量级：via_share ≥ %.1f ∧ 全部 τ 落在正的 fs 量级（<100fs）"
          % AN_VIA_SHARE_MIN,
          vlo >= AN_VIA_SHARE_MIN and tau_ok,
          "via 占比 %.1f%%..%.1f%% · τ_tt %.4f..%.4f fs"
          % (vlo * 100, vhi * 100, min(v["tau_fs"]["tt"] for v in bw["nets"].values()),
             max(v["tau_fs"]["tt"] for v in bw["nets"].values())))

    # ── D7 三角单调 ───────────────────────────────────────────
    bad_mono = [n for n, v in bw["nets"].items()
                if not (v["min_fs"] <= v["typ_fs"] <= v["max_fs"] - 0.0 + 1e-12)]
    check("D7 三角单调：每网 min ≤ typ ≤ max（ff 快、tt 中、ss 慢）",
          not bad_mono, "网 %d · 破坏 %s" % (bw["n_nets"], bad_mono or "无"))

    # ── D8 窗口落在**闭式界**内（全金属界 … 全通孔界）────────────
    kff_r, kff_c = PV.CORNERS["ff"]
    kss_r, kss_c = PV.CORNERS["ss"]
    kff_v, kss_v = PV.VIA_CORNERS["ff"], PV.VIA_CORNERS["ss"]
    lo_b, hi_b = (kss_r * kss_c) / (kff_r * kff_c), (kss_v * kss_c) / (kff_v * kff_c)
    out_band = [(n, round(v["spread_x"], 6)) for n, v in bw["nets"].items()
                if not (lo_b - 1e-9 <= v["spread_x"] <= hi_b + 1e-9)]
    check("D8 窗口落在闭式界内：[全金属界 %.4f, 全通孔界 %.4f]（由角因子直接推出，不是拍脑袋带宽）"
          % (lo_b, hi_b),
          not out_band, "实测 %.4f..%.4f · 越界 %s" % (lo_s, hi_s, out_band or "无"))

    # ── D9 反向探针：交换 ff/ss 通孔因子 ⇒ 单调性必破 ─────────────
    bad_via = {"ff": PV.VIA_CORNERS["ss"], "tt": 1.00, "ss": PV.VIA_CORNERS["ff"]}
    bw_bad = PV.block_window(nets, via_corners=bad_via)
    broken = [n for n, v in bw_bad["nets"].items() if v["tau_fs"]["ss"] < v["tau_fs"]["ff"]]
    check("D9 反向探针：把 ff/ss 的通孔因子对调 ⇒ 慢角必须反而更快（单调性判据确有牙）",
          len(broken) == bw_bad["n_nets"],
          "对调后 ss<ff 的网数 %d/%d（ss=%.4f < ff=%.4f 于最坏网 %s）"
          % (len(broken), bw_bad["n_nets"],
             bw_bad["nets"][bw_bad["worst_net"]]["tau_fs"]["ss"],
             bw_bad["nets"][bw_bad["worst_net"]]["tau_fs"]["ff"], bw_bad["worst_net"]))

    # ── D10 同源（角定义只有一份）──────────────────────────────
    check("D10 同源：dpvt.CORNERS 与 dsignoff.CORNERS **是同一个对象**（引用而非副本）",
          PV.CORNERS is SG.CORNERS and PV.CORNERS["tt"] == (1.00, 1.00),
          "角 %s · 通孔角 %s" % (dict(PV.CORNERS), dict(PV.VIA_CORNERS)))

    # ── D11 确定性 ───────────────────────────────────────────
    bw2 = PV.block_window(nets)
    same = ([(n, round(v["tau_fs"]["ff"], 12), round(v["tau_fs"]["ss"], 12))
             for n, v in sorted(bw["nets"].items())] ==
            [(n, round(v["tau_fs"]["ff"], 12), round(v["tau_fs"]["ss"], 12))
             for n, v in sorted(bw2["nets"].items())])
    check("D11 确定性：两次 block_window 的三角延迟逐位一致", same,
          "网 %d · 块 spread %.4f×" % (bw["n_nets"], bw["block_spread_x"]))

    # ── D0 耗时 ─────────────────────────────────────────────
    dt = time.time() - t0
    check("D0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("  [块窗口] %d 网 · 延迟 %.4f..%.4f fs（网间 %.2f×）· 各网角窗口 %.4f..%.4f×"
          % (bw["n_nets"], bw["block_min_fs"], bw["block_max_fs"], bw["block_spread_x"], lo_s, hi_s))
    print("  [最坏网] %s · ff=%.4f tt=%.4f ss=%.4f fs · via 占比 %.0f%%"
          % (bw["worst_net"], bw["nets"][bw["worst_net"]]["tau_fs"]["ff"],
             bw["nets"][bw["worst_net"]]["tau_fs"]["tt"],
             bw["nets"][bw["worst_net"]]["tau_fs"]["ss"],
             bw["nets"][bw["worst_net"]]["parts"]["via_share"] * 100))
    print("  [诚实边界] %s" % "；".join(PV.DPVT_DISCLOSURE["scope"]))
    print("-" * 78)
    print("E47 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E47 有红色：见上方 [FAIL] 行")
        return 1
    print("E47 全绿 · 多角延迟窗口：τ 拆金属/通孔两段各带各的角 · 每网窗口 %.4f..%.4f× · "
          "定理退化精确 · **只做互连线，不是路径延迟窗口**" % (lo_s, hi_s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
