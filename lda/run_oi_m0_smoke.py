# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M0 基线门禁（含突变探针 + 引擎回归）。

验证项：
  C1 装配合法（IR.validate == []）
  C2 无缺失器件模型
  C3 B19 无源无增益 |T|≤1
  C4 链路预算 闭式≡级联（≤0.05dB，证明装配接线正确）
  C5 信道隔离 ≥ 15 dB（M0·L0 基线下限；<30dB 见 design_notes 调优目标）
  C6 基线 IL ∈ [3,20] dB
  C7 引擎回归：≥3 端口星型网不得重复计数路径（光联接 M0 暴露的平台 bug）
突变探针（须造真实分歧，证明门禁非恒绿）：
  P1 窄信道间隔 → C5 隔离崩溃（变红）
  P2 光纤 span 50dB → C6 IL 超界（变红）
  P3 gc_tx 改无模型 kind → C2 缺失 + C4 闭式≠级联（变红）
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2.oi_module import (  # noqa: E402
    build_transceiver_m0, transceiver_m0_budget)

CHANNELS = [1550.0, 1551.6]


def _get(link, cid):
    return [c for c in link.ir.components if c.id == cid][0]


def _star_doublecount_regression() -> float:
    """引擎级回归：≥3 端口星型网不得重复计数路径（光联接 M0 暴露的平台 bug）。

    构造与 tx_mux 同构的最小例：3 端口星型网 {src0.out, src1.out, gc.wg} +
    单向 GratingCoupler(wg→fib, η=0.5)。信号 src0.in→src0→src0.out 抵达星型网后，
    gc.wg 既可由「直连边」也可经「src0.out→src1.out→gc.wg」到达 → 旧 all-pairs
    实现会把同一条路径求和两次（传递翻倍为 1.0）；hub 模型修复后应为单路径 0.5。
    """
    from lda_chain.link_model import LinkModel
    from lda_chain.engine import simulate
    link = LinkModel(domain="photon", name="star-regress")
    link.add_device("src0", "MziModulator", params={"V": 0.0, "V_pi": 4.0})
    link.add_device("src1", "MziModulator", params={"V": 0.0, "V_pi": 4.0})
    link.mark_source("src0", "in")
    link.mark_source("src1", "in")
    link.ir.connect("tx_mux", "src0.out", "src1.out", "gc.wg")  # 3 端口星型
    link.add_device("gc", "GratingCoupler", params={"coupling": 0.5})
    link.external_io("gc_out", "gc", "fib")  # sink
    sim = simulate(link, [1.55])
    return sim["transfers"].get("src0.in->gc.fib", [0.0])[0]


def _eval(link):
    """评估门禁条件（不计入全局 FAIL；供基线门禁与突变探针共用）。"""
    rep = transceiver_m0_budget(link, CHANNELS)
    conds = {
        "missing": all(not pc["missing_models"] for pc in rep["per_channel"]),
        "b19": rep["b19_passivity"],
        "ab": all(pc["il_ab_diff_db"] <= 0.05 for pc in rep["per_channel"]),
        "iso": all(pc["isolation_db"] >= 15.0 for pc in rep["per_channel"]),
        "il": all(3.0 <= pc["il_b_db"] <= 20.0 for pc in rep["per_channel"]),
    }
    return conds, rep


def run_checks(link, label):
    """基线门禁：逐条计入全局 PASS/FAIL。"""
    conds, rep = _eval(link)
    check(f"{label}: 无缺失器件模型", conds["missing"])
    check(f"{label}: B19 无源无增益 |T|≤1", conds["b19"])
    check(f"{label}: 预算闭式≡级联(≤0.05dB)", conds["ab"])
    check(f"{label}: 信道隔离≥15dB(M0·L0下限)", conds["iso"])
    check(f"{label}: 基线IL∈[3,20]dB", conds["il"])
    return conds, rep


def main() -> int:
    # —— C7：引擎回归（星型网重复计数）先于业务门禁 ——
    star_val = _star_doublecount_regression()
    check("C7 引擎回归: 3端口星型网单路径(=0.5,非翻倍1.0)",
          abs(star_val - 0.5) < 1e-6 and star_val < 0.75)

    # —— 正常态（应全绿）——
    link = build_transceiver_m0(n_lanes=2, channels_nm=CHANNELS)
    assert link.validate() == [], f"IR.validate 应无错误：{link.validate()}"
    check("M0: 装配合法 IR.validate==[]", link.validate() == [])
    _, rep = run_checks(link, "M0")
    for pc in rep["per_channel"]:
        print(f"  通道{pc['lane']} {pc['channel_nm']}nm: "
              f"IL={pc['il_b_db']:.2f}dB 隔离={pc['isolation_db']:.1f}dB "
              f"闭式≡级联差={pc['il_ab_diff_db']:.4f}dB")
    for note in rep.get("design_notes", []):
        print(f"  · 设计洞察: {note}")

    # —— P1：隔离探针（窄信道间隔 → 前置环 drop 旁瓣抬升 → 隔离崩溃）——
    #   门禁 C5 须在突变态变红（c1["iso"]=False），探针断言此分歧真实存在。
    lp1 = build_transceiver_m0(n_lanes=2, channels_nm=[1550.0, 1550.4])
    c1, rep1 = _eval(lp1)
    iso1 = min(pc["isolation_db"] for pc in rep1["per_channel"])
    check("P1 探针须造分歧(窄间隔→C5 变红)", (not c1["iso"]) and iso1 < 15.0)

    # —— P2：IL 探针（光纤 span 50dB → IL 超界）——
    lp2 = build_transceiver_m0(n_lanes=2, channels_nm=CHANNELS,
                               fiber_span_db=50.0)
    c2, rep2 = _eval(lp2)
    il2 = max(pc["il_b_db"] for pc in rep2["per_channel"])
    check("P2 探针须造分歧(IL>20dB→C6 变红)", (not c2["il"]) and il2 > 20.0)

    # —— P3：缺模型探针（gc_tx 改无模型 kind）——
    lp3 = build_transceiver_m0(n_lanes=2, channels_nm=CHANNELS)
    _get(lp3, "gc_tx").kind = "BogusGC"
    c3, rep3 = _eval(lp3)
    miss3 = any(pc["missing_models"] for pc in rep3["per_channel"])
    diff3 = max(pc["il_ab_diff_db"] for pc in rep3["per_channel"])
    check("P3a 探针须造分歧(缺失非空→C2 变红)", (not c3["missing"]) and miss3)
    check("P3b 探针须造分歧(闭式≠级联→C4 变红)", (not c3["ab"]) and diff3 > 0.05)

    return 0 if (globals().get("PASS", 0) and not globals().get("FAIL", 0)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
