# -*- coding: utf-8 -*-
"""E26 ADC 能耗四项预算 + 可校核性门禁（D-201 · v0.9.322）。

═══════════════════════════════════════════════════════════════════════════
本段把 E25 的建议「补建模」做完，结论是：**建议的前提不成立**
═══════════════════════════════════════════════════════════════════════════
E25 说「把比较器/参考缓冲/数字逻辑建成可计算模型，模型⟷实测误差 <20% 才算可信」。
本段建成四项物理模型（闭式齐全）后实测：

① 覆盖率只有 **18.2% / 21.9% / 89.0%**（跨设计 **4.90×**）—— 不是精度问题，是**无跨设计一致性**。
② 各锚所需的电路尺度 `s_i` = **1.13 / 5.46 / 5.63**（离散 4.98×）。
   🔴 其中 40nm 与 28nm 只差 **3.2%** ⇒ 常规档有约 **5.46×** 系统性缺口（= 那 80% 不可建模的设计策略），
   而 65nm 超低功耗档偏离 **4.83×**（亚阈值/低偏置，不能共用标定）。
③ 校核自由度 **dof = 3 − 4 − 2 = −3**（无同工艺锚对）⇒ 任何「误差 <20%」都是**反解再正算 = 循环自证**。
④ ⇒ **「从头算」路线上限已封顶**，ADC 必须走「实测标定 + 区间」：地板 **14.9 ~ 66.2 fJ/op（4.4×）**，
   对 Mythic 8.3 的差距是 **1.80× ~ 7.98×**（E25 单点 33.7 fJ/op ⇒ 4.1× 落在区间内，但**单点报法不成立**）。

判什么
  A 模块自检（`adc_budget.adc_budget_self_check` **17 项**）
  B 关键事实（10 条）：覆盖率三锚 · s_i 与离散度 · 组内一致性 · 离群比 · dof=−3 ·
    区间地板与 vs-Mythic 区间 · E25 单点在区间内 · 未解释项构成 · 四项守恒 · t_regen 与 f_s 无关
  C 反向可证伪：**6 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import adc_budget as B      # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# 现算锚值（v0.9.322）
AN_COV = [18.16, 21.91, 89.01]      # 三锚覆盖率（%）
AN_S_LO = 1.13                       # 65nm 超低功耗档所需尺度
AN_S_MID = 5.46                      # 40nm
AN_S_HI = 5.63                       # 28nm
AN_S_SPREAD = 4.98
AN_INNER_PCT = 3.2                   # 常规两档差（%）
AN_OUTLIER = 4.83                    # 离群比
AN_DOF = -3
AN_INTERVAL = (14.9, 66.2)           # fJ/op 区间
AN_GAP = (1.80, 7.98)                # vs Mythic 8.3
AN_E25_POINT = 33.7
AN_MYTHIC = 8.3


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


# ---------------------------------------------------------------------------
# B 关键事实
# ---------------------------------------------------------------------------
def _cov_ok() -> bool:
    """B1 · 三锚覆盖率必须现算复现（防参数漂移静默改结论）。"""
    rows = B.coverage_table()
    return all(_rel(r["coverage"] * 100, a) < 0.02 for r, a in zip(rows, AN_COV))


def _cov_below_100() -> bool:
    """B2 · 覆盖率必须 <100%（>100% = 参数集过度，模型不可用 · 开发时曾 343%~1640%）。"""
    return all(r["coverage"] < 1.0 for r in B.coverage_table())


def _spread_reported() -> bool:
    """B3 · 覆盖率离散度必须**如实报出**（不得人为凑小）。"""
    sp = B.coverage_spread()
    return sp["spread"] > 1.5 and _rel(sp["spread"], AN_COV[2] / AN_COV[0]) < 0.05


def _s_ok() -> bool:
    """B4 · 各锚所需电路尺度 s_i 必须现算复现。"""
    sa = B.scalability_analysis()
    lo, mid, hi = sa["s_values"]
    return (_rel(lo, AN_S_LO) < 0.02 and _rel(mid, AN_S_MID) < 0.02
            and _rel(hi, AN_S_HI) < 0.02 and _rel(sa["spread"], AN_S_SPREAD) < 0.02)


def _group_ok() -> bool:
    """B5 · 组内一致性 + 离群比（"偏离来自策略差异"这个解释必须站得住）。"""
    sa = B.scalability_analysis()
    return (abs(sa["inner_consistency"] - 1) * 100 < 10.0
            and _rel(sa["outlier_ratio"], AN_OUTLIER) < 0.05)


def _dof_ok() -> bool:
    """B6 · 🔴 dof 必须 ≤0 且 certifiable=False（守「不得宣称可校核」）。"""
    d = B.dof_analysis()
    return d["dof"] == AN_DOF and d["certifiable"] is False


def _interval_ok() -> bool:
    """B7 · 区间地板必须三锚齐报 + spread>1（守「不得报单点」）。"""
    fi = B.floor_interval()
    lo, hi = fi["interval_fj"]
    return (len(fi["rows"]) == 3 and fi["spread"] > 1.0
            and _rel(lo, AN_INTERVAL[0]) < 0.03 and _rel(hi, AN_INTERVAL[1]) < 0.03)


def _gap_ok() -> bool:
    """B8 · 对 Mythic 的差距必须是区间（1.80×~7.98×），不是单点。"""
    g = B.floor_interval()["gap_vs_mythic"]
    return _rel(g[0], AN_GAP[0]) < 0.03 and _rel(g[1], AN_GAP[1]) < 0.03


def _e25_point_inside() -> bool:
    """B9 · E25 单点必须落在区间内（口径相容 ⇒ 本段是"细化"不是"推翻"）。"""
    lo, hi = B.floor_interval()["interval_fj"]
    return lo <= AN_E25_POINT <= hi


def _unexplained_ok() -> bool:
    """B10 · 未解释项里"不可从公开参数建模"必须占多数（守「不得把设计策略说成可建模」）。"""
    nm = sum(1 for u in B.UNEXPLAINED_SOURCES if not u["modelable"])
    return nm >= len(B.UNEXPLAINED_SOURCES) // 2 and len(B.UNEXPLAINED_SOURCES) >= 6


def main() -> int:
    print("=" * 74)
    print("E26 ADC 四项预算 + 可校核性门禁（D-201）")
    print("=" * 74)

    # A 模块自检
    print("\n[A] 模块自检（adc_budget.adc_budget_self_check）")
    ok_mod = B.adc_budget_self_check(verbose=True)
    check("A1 模块自检 17/17 全绿", ok_mod)

    # B 关键事实
    print("\n[B] 关键事实")
    check("B1 三锚覆盖率现算复现：%.1f%% / %.1f%% / %.1f%%" % tuple(AN_COV), _cov_ok())
    check("B2 三锚覆盖率全部 <100%（参数集不过度）", _cov_below_100())
    check("B3 覆盖率离散度 %.2f× **如实报出**（未被人为凑小）"
          % B.coverage_spread()["spread"], _spread_reported())
    check("B4 各锚所需电路尺度 s_i = %.2f/%.2f/%.2f · 离散 %.2f×"
          % (AN_S_LO, AN_S_MID, AN_S_HI, AN_S_SPREAD), _s_ok())
    check("B5 组内一致性 %.1f%% + 离群比 %.2f× ⇒ 偏离来自**设计策略**"
          % (AN_INNER_PCT, AN_OUTLIER), _group_ok())
    check("B6 🔴 校核自由度 dof = %d ≤ 0 ⇒ **不可校核**（无同工艺锚对）" % AN_DOF, _dof_ok())
    check("B7 区间地板 %.1f ~ %.1f fJ/op（%.2f× · 三锚齐报）"
          % (AN_INTERVAL[0], AN_INTERVAL[1], AN_INTERVAL[1] / AN_INTERVAL[0]),
          _interval_ok())
    check("B8 对 Mythic %.1f 的差距是**区间** %.2f× ~ %.2f×（非单点）"
          % (AN_MYTHIC, AN_GAP[0], AN_GAP[1]), _gap_ok())
    check("B9 E25 单点 %.1f fJ/op 落在区间内（细化口径 · 非推翻）" % AN_E25_POINT,
          _e25_point_inside())
    check("B10 未解释项 %d 条中不可建模者占多数（守「不得把设计策略说成可建模」）"
          % len(B.UNEXPLAINED_SOURCES), _unexplained_ok())

    # ------------------------------------------------------------------
    # C 突变探针（每条都必须变红 —— 否则判据是假的）
    # ------------------------------------------------------------------
    print("\n[C] 反向可证伪探针")

    # C1：比较器通电时间回到 T_conv/(2b) 的旧错 ⇒ 覆盖率爆炸 ⇒ B2 必红
    saved = [dict(p) for p in B.PROCESS_NODES]
    bad = [dict(p) for p in saved]
    bad[2]["t_regen_s"] = 41.7e-6      # 65nm 1MS/s·8b 的 T_conv/(2b)
    with mock.patch.object(B, "PROCESS_NODES", bad):
        c1 = not _cov_below_100()
    with mock.patch.object(B, "PROCESS_NODES", saved):
        c1_restored = _cov_below_100()
    check("C1 探针：t_regen 回到 T_conv/(2b)（旧错）⇒ 覆盖率 >100% ⇒ B2 必红；还原后全绿",
          c1 and c1_restored)

    # C2：人为把覆盖率离散度凑成 1.0 ⇒ B3 必红
    with mock.patch.object(B, "coverage_spread",
                           lambda scale=1.0: {"spread": 1.0, "coverages": [1, 1, 1],
                                              "min": 1, "max": 1, "verdict": "凑的",
                                              "tier": "MODEL_ESTIMATE"}):
        c2 = not _spread_reported()
    check("C2 探针：把覆盖率离散度人为凑成 1.0× ⇒ B3 必红（守「必须如实报出」）", c2)

    # C3：宣称"可校核" ⇒ B6 必红
    with mock.patch.object(B, "dof_analysis",
                           lambda: {"dof": 1, "certifiable": True, "free_params": 4,
                                    "anchors": 3, "distinct_nodes": 3, "scaling_params": 2,
                                    "same_node_pairs": 0, "verdict": "可校核",
                                    "tier": "MODEL_ESTIMATE"}):
        c3 = not _dof_ok()
    check("C3 探针：把 dof 改成 +1 并宣称可校核 ⇒ B6 必红（守「不得宣称可校核」）", c3)

    # C4：退回 E25 的单点报法（只报一个锚）⇒ B7 必红
    _real_fi = B.floor_interval
    with mock.patch.object(B, "floor_interval",
                           lambda **k: {**_real_fi(**k),
                                        "rows": _real_fi(**k)["rows"][:1],
                                        "interval_fj": (_real_fi(**k)["rows"][0]["e_op_fj"],) * 2,
                                        "spread": 1.0}):
        c4 = not _interval_ok()
    check("C4 探针：退回单点报法（只报 28nm 一个锚）⇒ B7 必红（守「不得报单点」）", c4)

    # C5：把未解释项全部标成"可建模" ⇒ B10 必红
    with mock.patch.object(B, "UNEXPLAINED_SOURCES",
                           [{**u, "modelable": True} for u in B.UNEXPLAINED_SOURCES]):
        c5 = not _unexplained_ok()
    check("C5 探针：把设计策略全说成「可建模」 ⇒ B10 必红", c5)

    # C6：假装可标定（spread 1.05）⇒ B4/B5 必红
    with mock.patch.object(B, "scalability_analysis",
                           lambda: {"rows": [], "s_values": [1.0, 1.02, 1.05],
                                    "spread": 1.05, "inner_consistency": 1.029,
                                    "outlier_ratio": 1.02, "lowest_anchor": "x",
                                    "outlier_anchors": [], "regular_pair": ["a", "b"],
                                    "calibratable": True, "verdict": "可标定",
                                    "tier": "MODEL_ESTIMATE"}):
        c6 = (not _s_ok()) and (not _group_ok())
    check("C6 探针：假装可标定（s_i 凑成 1.0/1.02/1.05）⇒ B4 与 B5 必红", c6)

    # 还原后重跑（证明探针只改局部、不改模块本身）
    check("C7 全部探针还原后，模块自检与关键事实仍全绿",
          B.adc_budget_self_check() and _cov_ok() and _s_ok() and _dof_ok())

    # ------------------------------------------------------------------
    # K 自入 CI
    # ------------------------------------------------------------------
    print("\n[K] CI 登记")
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e26_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E26 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
