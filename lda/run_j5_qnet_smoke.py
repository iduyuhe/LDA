# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **常驻门禁**（B519 分发保真度 + B520 HOM 可见度 + B521 中继交换产出数 + B522 微波-光换能效率）。

判据分节（**按锚遍历** · 判据数实跑现数）：
  A 锚项（每锚 11 条 · 读自 BENCHMARK_DEFS 不硬编码）：tol 内 / 残差 >0 非代数恒等 /
    判据 D（严格单调 + 比值形态与算法一致）/ 动态范围 · 反自证桩 · 防回退候选键 /
    🔴 反向探针必须打「离散参数 n」/ 纪律佐证 / n 非法必抛
  B 能力层：`qnet_channel` 14 + `qnet_distribution` 10 + `qnet_source` 8 + `qnet_repeater` 20 +
    `qnet_transducer` 20 + `qnet_classical` 14 + `qnet_system` 17
  C 跨模块同源（逐位）：分发 ≡ B519 golden · 信道 ≡ B519 golden · 源 ≡ B520 golden · 中继 ≡ B521 golden ·
    换能 ≡ B522 golden · 经典接口 ≡ `qs_m2.cpmg_filter`（复用对拍）· 总装六段 ≡ 六能力层
  D 三表一致：`_TOL_BY_BID` ≡ DEFS tol（四锚）· `_M_BY_BID` = 扫描格末端（四锚）· 默认档 ≡ DEFS
  E 红线：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）
  F M4 净增 0 登记核验：避让表 3 条 · 负结果取证 3 条 · 总装报告净增 0 与理由可查

🔴 `main()` 返回「真值」而非恒 0（J4 血案：恒 `return 0` = 假绿）。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3）。
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness import _batch_j5_numeric as J5  # noqa: E402
from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3：禁自定义检查函数）
from lda_l2 import qnet_channel as CH  # noqa: E402
from lda_l2 import qnet_classical as CL  # noqa: E402
from lda_l2 import qnet_distribution as DS  # noqa: E402
from lda_l2 import qnet_repeater as RP  # noqa: E402
from lda_l2 import qnet_source as SR  # noqa: E402
from lda_l2 import qnet_swap as SW  # noqa: E402
from lda_l2 import qnet_system as QS  # noqa: E402
from lda_l2 import qnet_transducer as TR  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_BIDS = ("B519", "B520", "B521", "B522")

#: 期望的候选键（防「回退自证桩」：DEFS 必须指向本征程专用候选）
_EXPECT_CAND = {
    "B519": "b519_entanglement_distribution_fidelity_cand",
    "B520": "b520_hom_visibility_cand",
    "B521": "b521_repeater_yield_cand",
    "B522": "b522_transducer_efficiency_cand",
}

#: 数值核里各锚的默认参数常量（D3 用）
_DEFPARAMS = {"B519": getattr(J5, "B519_DEFAULT_PARAMS"),
              "B520": getattr(J5, "B520_DEFAULT_PARAMS"),
              "B521": getattr(J5, "B521_DEFAULT_PARAMS"),
              "B522": getattr(J5, "B522_DEFAULT_PARAMS")}


def _anchor_checks(bid: str) -> None:
    d = BENCHMARK_DEFS[bid]
    p = dict(d.get("default_params") or {})
    tol = float(d["tol"])
    gold = float(d["golden_fn"](**p))
    print("\n[A·%s] 锚项（golden=%.15e · tol=%.1e）" % (bid, gold, tol))

    n_end = int(J5._M_BY_BID[bid])
    grid = list(J5._GRID_BY_BID[bid])
    cand_fn = J5._CAND_BY_BID[bid]
    d_res = abs(cand_fn(**p) - gold)

    check("A1·%s 默认档残差 > 0（非代数恒等）" % bid, d_res > 0.0, "resid=%.4e" % d_res)
    check("A2·%s 默认档残差 < tol（判决通过）" % bid, d_res < tol,
          "resid=%.4e < tol=%.1e" % (d_res, tol))
    check("A3·%s 基线残差 > 1e-12（不沉双精度地板）" % bid, d_res > 1e-12,
          "resid=%.4e" % d_res)

    chain = [(n, abs(cand_fn(n=n, **p) - gold)) for n in grid]
    mono = all(chain[i][1] > chain[i + 1][1] for i in range(len(chain) - 1))
    check("A4·%s 判据 D：残差链严格单调递减" % bid, mono,
          " → ".join("%d:%.2e" % (n, x) for n, x in chain))
    ratios = [chain[i - 1][1] / chain[i][1] if chain[i][1] > 0 else float("inf")
              for i in range(1, len(chain))]
    # B519 = RK4 ⇒ O(h⁴)，比值从上方逼近 16；B521 = 复合 Simpson ⇒ O(h⁴)，从下方逼近 16；
    # B520 = 复合梯形 ⇒ 超几何收敛（比值单调递增）。判据 = 「趋近标称阶 16」（不限方向）。
    if bid == "B520":
        shape_ok = all(ratios[i] < ratios[i + 1] for i in range(len(ratios) - 1))
    else:
        shape_ok = (4.0 <= ratios[-1] <= 22.0
                    and abs(ratios[-1] - 16.0) <= abs(ratios[0] - 16.0))
    check("A5·%s 判据 D：比值形态与算法一致（趋近标称阶）" % bid, shape_ok,
          " / ".join("%.2f" % r for r in ratios))
    dyn = (chain[0][1] / chain[-1][1]) if chain[-1][1] > 0 else float("nan")
    check("A6·%s 动态范围 ≥ 1e4×（末档残差须 > 0）" % bid, bool(dyn >= 1e4),
          "dyn=%.3g×" % dyn)

    cand_end = cand_fn(n=n_end, **p)
    check("A7·%s 反自证桩：候选 ≠ golden（非恒等）" % bid, abs(cand_end - gold) > 0.0,
          "cand=%.15e" % cand_end)
    check("A8·%s 防回退候选键：DEFS 指向本征程专用候选" % bid,
          d.get("candidate") == _EXPECT_CAND[bid], "key=%s" % d.get("candidate"))

    coarse = abs(cand_fn(n=grid[0], **p) - gold)
    check("A9·%s 反向探针（离散参数 n）：粗档残差 ≫ 默认档残差" % bid,
          coarse > d_res * 1e3, "coarse=%.3e vs fine=%.3e" % (coarse, d_res))
    key0 = sorted(p)[0]
    p_pert = {**p, key0: p[key0] * 1.1}
    pert_resid = abs(cand_fn(n=n_end, **p_pert) - d["golden_fn"](**p_pert))
    check("A10·%s 纪律佐证：物理参数扰动（两侧同扰动）后残差仍 < tol" % bid,
          pert_resid < tol, "pert_resid=%.3e < tol=%.1e" % (pert_resid, tol))

    raised = False
    try:
        cand_fn(n=0, **p)
    except ValueError:
        raised = True
    check("A11·%s 反向：n=0 必抛 ValueError" % bid, raised)


def main() -> int:  # noqa: C901
    print("=" * 78)
    print("J5 门禁（B519 分发保真度 + B520 HOM 可见度 + B521 中继产出数 + B522 换能效率）")
    print("=" * 78)

    for bid in _BIDS:
        _anchor_checks(bid)

    print("\n[B] 能力层自检")
    sc_ch = CH.selfcheck_qnet_channel()
    check("B1 qnet_channel 全部自检通过", not [k for k, v in sc_ch.items() if not v],
          "%d 项" % len(sc_ch))
    sc_ds = DS.selfcheck_qnet_distribution()
    check("B2 qnet_distribution 全部自检通过", not [k for k, v in sc_ds.items() if not v],
          "%d 项" % len(sc_ds))
    sc_sr = SR.selfcheck_qnet_source()
    check("B3 qnet_source 全部自检通过", not [k for k, v in sc_sr.items() if not v],
          "%d 项" % len(sc_sr))
    sc_rp = RP.selfcheck_qnet_repeater()
    check("B4 qnet_repeater 全部自检通过", not [k for k, v in sc_rp.items() if not v],
          "%d 项" % len(sc_rp))
    sc_tr = TR.selfcheck_qnet_transducer()
    check("B5 qnet_transducer 全部自检通过", not [k for k, v in sc_tr.items() if not v],
          "%d 项" % len(sc_tr))
    sc_cl = CL.selfcheck_qnet_classical()
    check("B6 qnet_classical 全部自检通过", not [k for k, v in sc_cl.items() if not v],
          "%d 项" % len(sc_cl))
    sc_sys = QS.selfcheck_qnet_system()
    check("B7 qnet_system 全部自检通过", not [k for k, v in sc_sys.items() if not v],
          "%d 项" % len(sc_sys))

    print("\n[C] 跨模块同源（逐位）")
    g519 = float(BENCHMARK_DEFS["B519"]["golden_fn"](
        **BENCHMARK_DEFS["B519"]["default_params"]))
    g520 = float(BENCHMARK_DEFS["B520"]["golden_fn"](
        **BENCHMARK_DEFS["B520"]["default_params"]))
    g521 = float(BENCHMARK_DEFS["B521"]["golden_fn"](
        **BENCHMARK_DEFS["B521"]["default_params"]))
    check("C1 qnet_distribution.distribution_fidelity ≡ B519 golden（逐位）",
          abs(DS.distribution_fidelity(1.0e5, 2.2e4) - g519) < 1e-15)
    check("C2 qnet_channel.link_fidelity ≡ B519 golden（逐位）",
          abs(CH.link_fidelity(1.0e5, 2.2e4) - g519) < 1e-15)
    check("C3 qnet_source.hom_visibility ≡ B520 golden（逐位）",
          abs(SR.hom_visibility() - g520) < 1e-15)
    check("C4 qnet_source.overlap_magnitude_sq ≡ 数值核同律",
          abs(SR.overlap_magnitude_sq() - J5.hom_visibility_golden()) < 1e-15)
    check("C5 qnet_repeater.repeater_yield ≡ B521 golden（逐位）",
          abs(RP.repeater_yield() - g521) < 1e-15)
    g522 = float(BENCHMARK_DEFS["B522"]["golden_fn"](
        **BENCHMARK_DEFS["B522"]["default_params"]))
    check("C6 qnet_transducer.transducer_efficiency ≡ B522 golden（相对 < 1e-12）",
          abs(TR.transducer_efficiency() - g522) / max(abs(g522), 1e-300) < 1e-12)
    check("C7 qnet_classical 复用 `qs_m2.cpmg_filter`（逐点对拍）",
          bool(sc_cl.get("matches_qs_m2_cpmg_filter", False)))
    _rows = QS.link_segments()
    check("C8 qnet_system 六段 ≡ 六能力层（逐位）",
          all(r["verdict"] in ("PASS", "REVIEW") for r in _rows) and len(_rows) == 6
          and abs(_rows[5]["value"] - CL.jitter_infidelity()) < 1e-15)

    print("\n[D] 三表 / 默认档一致")
    check("D1 _TOL_BY_BID ≡ BENCHMARK_DEFS tol（四锚）",
          all(float(J5._TOL_BY_BID[b]) == float(BENCHMARK_DEFS[b]["tol"]) for b in _BIDS))
    check("D2 _M_BY_BID = 扫描格末端（四锚）",
          all(int(J5._M_BY_BID[b]) == int(J5._GRID_BY_BID[b][-1]) for b in _BIDS))
    check("D3 默认档 ≡ DEFS default_params（四锚）",
          all(dict(_DEFPARAMS[b]) == dict(BENCHMARK_DEFS[b]["default_params"])
              for b in _BIDS))

    print("\n[E] 红线")
    src = ""
    for fn in ("lda_l2/qnet_channel.py", "lda_l2/qnet_distribution.py",
               "lda_l2/qnet_source.py", "lda_l2/qnet_repeater.py",
               "lda_l2/qnet_transducer.py", "lda_l2/qnet_classical.py",
               "lda_l2/qnet_system.py",
               "lda_l2/qnet_swap.py",
               "lda_harness/_batch_j5_numeric.py"):
        p = os.path.join(_HERE, fn)
        if os.path.exists(p):
            src += open(p, encoding="utf-8").read()
    sdk = [s for s in ("qiskit", "cirq", "pennylane", "qutip", "qiskit_aer")
           if ("import " + s) in src]
    check("E1 主权边界：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）",
          not sdk, "命中=%s" % (sdk or "无"))

    print("\n[F] M4 净增 0 登记核验（章程 R8：无物理律者归 smoke）")
    av = CL.avoidance_table()
    check("F1 避让表 3 条齐备（B475 / qs_m2.coherent_chi / B522）",
          set(av) == {"B475", "qs_m2.coherent_chi", "B522"},
          "keys=%s" % sorted(av))
    ev = CL.negative_evidence()
    check("F2 负结果取证 3 条齐备（洛伦兹尾部 / 高斯精确 / Simpson 振荡）",
          len(ev) == 3 and all(ev.values()), "n=%d" % len(ev))
    _rep = QS.full_qnet_report()
    check("F3 总装报告净增 0 且有可查理由",
          _rep["net_new_anchors_M4"] == 0 and "negative_evidence" in _rep["net_new_reason"],
          "reason=%s" % _rep["net_new_reason"][:40])

    print("\n[G] 纠缠交换递推与纯化（v0.9.292 · 订正组合律）")
    # 🔴 改前：`end_to_end_fidelity` 把 N 段链保真度写成 **F_seg^N**（对保真度取幂），
    #    并称其为「朴素上界」。两处错：① 理想交换组合的是 **Werner 参数**（p_out=p₁p₂），
    #    不是保真度；② F_seg^N 恒**小于**正确值 ⇒ 是**下界**，方向说反。
    sc_sw = SW.selfcheck_qnet_swap()
    check("G1 qnet_swap 全部自检通过（对照支路 + 恒等式 + 解析根）",
          not [k for k, v in sc_sw.items() if not v],
          "fail=%s" % [k for k, v in sc_sw.items() if not v])
    _sweep = SW.segments_sweep()
    _fs = [x["fidelity"] for x in _sweep]
    check("G2 🔴 **分段不改保真**：N=1…100 七档端到端 F 逐位相同（相对 1e-15）",
          all(abs(f - _fs[0]) <= 1e-15 for f in _fs),
          "F=%.12f 全同" % _fs[0] if all(abs(f - _fs[0]) <= 1e-15 for f in _fs)
          else str(["%.10f" % f for f in _fs]))
    _bud = QS.end_to_end_fidelity()
    _seg_len = QS.DEFAULT_LINK_LENGTH_M / QS.DEFAULT_SEGMENTS
    _expect = SW.swap_chain_fidelity(DS.werner_parameter(_seg_len), QS.DEFAULT_SEGMENTS)
    check("G3 卡/总装同源：relay_chain_fidelity ≡ qnet_swap.swap_chain_fidelity（逐位）",
          abs(_bud["relay_chain_fidelity"] - _expect) <= 1e-15,
          "got=%.12f want=%.12f" % (_bud["relay_chain_fidelity"], _expect))
    check("G4 旧口径是**下界**（naive < werner）∧ 比值 == 解析预测 F_seg^N / F(p^N)",
          _bud["relay_chain_fidelity_naive"] < _bud["relay_chain_fidelity"]
          and abs(_bud["relay_chain_fidelity_naive"] / _bud["relay_chain_fidelity"]
                  - (CH.link_fidelity(_seg_len) ** QS.DEFAULT_SEGMENTS)
                  / _bud["relay_chain_fidelity"]) <= 1e-15,
          "naive/werner=%.6f（≈1/7.05）"
          % (_bud["relay_chain_fidelity_naive"] / _bud["relay_chain_fidelity"]))
    check("G5 对照支路三条：n=1 恒等 ∧ p=1 ⇒ 1（任意 N）∧ p=0 ⇒ 0（不能无中生有）",
          abs(SW.werner_swap_chain(0.7, 1) - 0.7) <= 1e-18
          and all(abs(SW.werner_swap_chain(1.0, n) - 1.0) <= 1e-18 for n in (1, 2, 5, 20))
          and SW.werner_swap_chain(0.0, 5) == 0.0)
    _d1, _d0 = SW.dejmps_once(1.0), SW.dejmps_once(0.0)
    check("G6 DEJMPS 对照支路：p=1 ⇒ p'=1 且 P_succ=1 ∧ p=0 ⇒ p' **恰为 1/6**（解析）",
          abs(_d1["p_out"] - 1.0) <= 1e-18 and abs(_d1["p_success"] - 1.0) <= 1e-18
          and abs(_d0["p_out"] - 1.0 / 6.0) <= 1e-15,
          "p0_out=%.15f" % _d0["p_out"])
    _lo, _hi = SW.dejmps_thresholds()
    check("G7 纯化临界点：两根代回 9p²−7p+1 == 0 ∧ F(p_high) ≈ 0.6919（文献口径独立校验）",
          abs(9 * _lo * _lo - 7 * _lo + 1) <= 1e-15
          and abs(9 * _hi * _hi - 7 * _hi + 1) <= 1e-15
          and abs(SW.fidelity_from_werner(_hi) - 0.6919) < 5e-4,
          "p_low=%.6f p_high=%.6f F_high=%.5f"
          % (_lo, _hi, SW.fidelity_from_werner(_hi)))
    check("G8 🔴「p'>p」≠「纯化有用」：p=0.3 ⇒ p'<p（降低）；p=0.01 ⇒ p'>p 但 F_out<0.5 ⇒ 二者均判无用",
          SW.dejmps_once(0.3)["p_out"] < 0.3
          and SW.dejmps_once(0.01)["p_out"] > 0.01
          and SW.dejmps_once(0.01)["fidelity_out"] < 0.5
          and not SW.dejmps_is_useful(0.3) and not SW.dejmps_is_useful(0.01),
          "p0.3_out=%.4f p0.01_out=%.4f F_out=%.4f"
          % (SW.dejmps_once(0.3)["p_out"], SW.dejmps_once(0.01)["p_out"],
             SW.dejmps_once(0.01)["fidelity_out"]))
    # G9 反向探针：把 relay_chain_fidelity 换成旧口径值 ⇒ G2 / G3 / G4 三条必红
    _fake = dict(_bud, relay_chain_fidelity=_bud["relay_chain_fidelity_naive"])
    _red2 = not all(abs(f - _fake["relay_chain_fidelity"]) <= 1e-15 for f in _fs)
    _red3 = abs(_fake["relay_chain_fidelity"]
                - SW.swap_chain_fidelity(DS.werner_parameter(
                    QS.DEFAULT_LINK_LENGTH_M / QS.DEFAULT_SEGMENTS),
                    QS.DEFAULT_SEGMENTS)) > 1e-15
    _red4 = not (_fake["relay_chain_fidelity_naive"] < _fake["relay_chain_fidelity"])
    check("G9 反向探针：把 relay_chain_fidelity 退回旧口径 ⇒ G2/G3/G4 三条必红",
          _red2 and _red3 and _red4, "g2=%s g3=%s g4=%s" % (_red2, _red3, _red4))

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("J5 门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
