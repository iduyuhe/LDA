# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E4 · 规模对标（诚实边界）门禁 + 突变探针（D-153）。

============================================================================
E4（吃狗粮：把 E3 数据通路推到大规模，并与公开模拟加速器 landmark 诚实对标）
----------------------------------------------------------------------------
验收（与 CI core 同口径，死标量 + 突变探针）：
  ① 规模扫描 32→256：相对误差有界（< 0.1）；
  ② 规模律：绝对误差随 N 单调增长（固定位数 ADC 固有律 ∝N）+ 相对误差不随 N 爆炸；
  ③ 大规模正确性：N=256（65536 突触）相对误差 < 0.05；
  ④ landmark 登记完整（每项含 source + tier）；
  ⑤ 诚实边界护栏：LDA 能力不含任何 TOPS/TOPS/W 等硬件性能主张；
  ⑥ 诚实对标口径完整（同族可比维度 + 非主张维度 + 层级不同）。

🔴 突变探针（防常数假绿 / 防死断言）：
  ⑦ 破坏数字 golden → 规模扫描 ① 必红；
  ⑧ 向 LDA 能力注入 fabricated 指标（TOPS/W）→ 诚实护栏 ⑤ 必红；
  ⑨ 破坏 landmark 登记（去 source）→ ④ 必红；
  ⑩ 还原后重跑①/③，确无残留漂移（探针反向完备：仍绿(死断言!) 必须为空）。

主权纪律（与全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；
LDA 是设计&验证工具链（非流片芯片）⇒ 不报 fabricated 能效；T1 电路级。
"""
import sys

import numpy as np
from unittest.mock import patch

from lda_l2.ecore import scale_bench
from lda_l2.ecore.mvm_datapath import MvmDatapath
from lda_l2.ecore.scale_bench import (
    LANDMARKS,
    honest_boundary_ok,
    honest_comparison,
    scale_bench_self_check,
    scale_sweep,
)

_SIZES = (32, 64, 128, 256)


# ---------------------------------------------------------------------------
# 绿色检查
# ---------------------------------------------------------------------------
def chk_scale_scan():
    rows = scale_sweep(_SIZES)
    rel = [r["rel_err"] for r in rows]
    ok = all(r < 0.1 for r in rel)
    return ok, "rel_err=" + "/".join(f"{v:.4f}" for v in rel)


def chk_scale_law():
    rows = scale_sweep(_SIZES)
    abs_ = [r["abs_err"] for r in rows]
    rel = [r["rel_err"] for r in rows]
    # 绝对误差随 N 单调增长；相对误差不随 N 爆炸（max/min < 5×）
    mono = all(abs_[i + 1] > abs_[i] for i in range(len(abs_) - 1))
    bounded_ratio = (max(rel) / max(min(rel), 1e-9)) < 5.0
    return (mono and bounded_ratio), f"abs={['%.3f'%v for v in abs_]} rel_ratio={max(rel)/max(min(rel),1e-9):.2f}"


def chk_large_scale():
    rows = scale_sweep((256,))
    ok = rows[0]["rel_err"] < 0.05
    return ok, f"N=256 syn={rows[0]['synapses']} rel={rows[0]['rel_err']:.5f}"


def chk_landmark_registry():
    lm = scale_bench.LANDMARKS
    ok = len(lm) >= 1 and all(("source" in e and e["source"]) and
                              ("tier" in e and e["tier"]) for e in lm)
    return ok, f"landmarks={len(lm)}"


def chk_honest_boundary():
    ok = honest_boundary_ok()
    return ok, f"LDA_CAPABILITIES 无 TOPS/TOPS-W 主张 = {ok}"


def chk_honest_comparison():
    c = honest_comparison()
    ok = (len(c["matched_dimensions"]) >= 1 and len(c["non_claimed"]) >= 1
          and bool(c["different_layer"]) and len(c["landmarks"]) >= 1)
    return ok, (f"matched={len(c['matched_dimensions'])} "
                f"non_claimed={len(c['non_claimed'])}")


# ---------------------------------------------------------------------------
# 突变探针
# ---------------------------------------------------------------------------
def probe_golden_corrupt():
    def bad_golden(self, x):
        return self._chain(x, lambda u, a: u.W @ a) * 2.0
    with patch.object(MvmDatapath, "golden", bad_golden):
        ok, _ = chk_scale_scan()
    return not ok


def probe_inject_fabricated_metric():
    bad = list(scale_bench.LDA_CAPABILITIES) + ["LDA 达到 76 TOPS/W（造假示例）"]
    with patch.object(scale_bench, "LDA_CAPABILITIES", bad):
        ok, _ = chk_honest_boundary()
    return not ok


def probe_landmark_registry_corrupt():
    bad = [{"name": "ghost", "org": "x", "arch": "y"}]     # 缺 source/tier
    with patch.object(scale_bench, "LANDMARKS", bad):
        ok, _ = chk_landmark_registry()
    return not ok


def main():
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 电子计算征程 E4 · 规模对标（诚实边界）门禁（D-153）===")
    print("SCALE_BENCH_DISCLOSURE:", scale_bench.SCALE_BENCH_DISCLOSURE["route"])
    sc = scale_bench_self_check()
    print(f"自证桩: maxN={sc['max_scale_tested']} syn={sc['max_synapses_tested']} "
          f"rel_max={sc['rel_err_max']:.4f} rel_bounded={sc['rel_err_bounded']} "
          f"abs_growing={sc['abs_err_growing_with_N']} landmarks={sc['landmark_count']}")

    # —— 绿：规模 + 诚实对标 ——
    ok, det = chk_scale_scan()
    check("① 规模扫描 32→256: 相对误差有界(<0.1)", ok, det)
    ok, det = chk_scale_law()
    check("② 规模律: 绝对误差∝N 增长 · 相对误差不爆炸", ok, det)
    ok, det = chk_large_scale()
    check("③ 大规模正确性: N=256(65536 突触) 相对误差<0.05", ok, det)
    ok, det = chk_landmark_registry()
    check("④ landmark 登记完整(含 source+tier)", ok, det)
    ok, det = chk_honest_boundary()
    check("⑤ 诚实边界护栏: 无 TOPS/TOPS-W 主张", ok, det)
    ok, det = chk_honest_comparison()
    check("⑥ 诚实对标口径完整(同族维度+非主张维度)", ok, det)

    # —— 红：突变探针（必变红，否则为死断言）——
    check("🔴 ⑦ 突变探针: 破坏数字 golden → 规模扫描必红", probe_golden_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑧ 突变探针: 注入 fabricated 指标(TOPS/W) → 诚实护栏必红",
          probe_inject_fabricated_metric(), "未变红（死断言!）")
    check("🔴 ⑨ 突变探针: 破坏 landmark 登记(去 source) 必红",
          probe_landmark_registry_corrupt(), "未变红（死断言!）")

    # —— 还原完整性 ——
    ok, det = chk_scale_scan()
    check("⑩ 还原重跑: 规模扫描无残留漂移", ok, det)
    ok, det = chk_honest_boundary()
    check("⑩ 还原重跑: 诚实护栏无残留漂移", ok, det)

    if fails:
        print(f"\nE4 门禁: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nE4 门禁: ALL GREEN（含 3 道突变探针 + 还原完整性）")


if __name__ == "__main__":
    main()
