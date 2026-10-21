# -*- coding: utf-8 -*-
"""蓝图 v2 · D1 光-量异质集成 · **常驻门禁**（锚 **B523** M0 阵列孔径截断 + **B524** M3 Kapitza 界面热导）
+ **M1 负结果机器化**（裁决「不立新锚」· 见 `D1_M1_ADJUDICATION`）。

判据分节（**判据数实跑现数** · A3 + B2 + C2 + D1 + E3 + F1 + G1 + **H3 组 3** + **I 反向 2**
+ **J10 组 10** + **K3 组 3** + **L 反向 1** = **32**）：
  A 接线 3：B523 ∈ DEFS ∧ ORDER ∧ specs ∧ candidates · golden ≡ 能力层闭式 · candidate ≡ 数值核
  B 闭式⇄数值 2：`err ≤ tol` · `resid ≤ tol/100`（余量 ≥100×）
  C 收敛 2：残差随 n 严格单调降 · 相邻比**趋近 16=2⁴**（不写死方向）
  D 反自证桩 1：默认档 resid ≫ 1e-13（非代数恒等）
  E 反向探针 3：非法参数必抛 · 宽孔径 ⇒ γ→1 · 零孔径 ⇒ γ→0
  F 自入 CORE 1
  G 能力层自检 1：`qnet_hetero_array.selfcheck` 全 PASS
  H M1 负结果 3（v0.9.259）：覆盖锚**仍在且方法未漂移** · **哨兵指标名未被偷登记** ·
    裁决面完整（≥3 理由 ∧ 每条 ≥12 字 ∧ 覆盖锚 ≥2 ∧ 各有方法规格）
  I 反向探针 2：篡改覆盖锚 metric ⇒ H1 必红 · 注入哨兵名 ⇒ H2 必红
  J B524 10（v0.9.260 · M3）：接线 · golden ≡ 能力层 · candidate ≡ 数值核 · err ≤ tol ·
    resid ≤ tol/100 · 残差随 ε 单调降 · 比趋近 **4=2²**（O(ε²)）· **跨平台稳健**（resid/ulp ≫ 1e4）·
    非法参数必抛 · 能力层 `hetero_thermal` 自检
  K M2 裁决 3（v0.9.260）：**统计包装哨兵未被偷登记** · 裁决面完整（≥4 理由 ∧ ≥4 哨兵）·
    **负证据在册**（闭式 ∧ 设计点 ∧ MC 跨种子 ∧ Simpson 收敛链）
  L 反向探针 1：注入 M2 哨兵名 ⇒ K1 必红

🔴 本门禁源码**不写非本版锚的锚号字面量**：M1 覆盖锚号只在非门禁模块
  `lda_harness/d1_registries.py` 里，防 K4 文本代理把「提了一句」算成「有专属判据」。
🔴 `main()` 返回真值而非恒 0。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def main() -> int:
    print("=" * 78)
    print("蓝图 v2 · D1 门禁（B523 阵列孔径截断 · B524 Kapitza 界面热导 · M1 负结果 H/I 组）")
    print("=" * 78)

    from lda_harness import verification_adapters as va
    from lda_harness import _batch_v2d1_numeric as V
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    from lda_l2 import qnet_hetero_array as M
    from lda_l2 import hetero_thermal as T

    specs, cands = va.build_harness_specs()
    by = {s.spec_id: s for s in specs}
    s = by.get("B523")
    check("A1 B523 ∈ DEFS ∧ ORDER ∧ specs ∧ candidates",
          s is not None and "B523" in BENCHMARK_DEFS and "B523" in BENCHMARK_ORDER
          and "B523" in cands,
          "spec=%s defs=%s order=%s cand=%s"
          % (s is not None, "B523" in BENCHMARK_DEFS, "B523" in BENCHMARK_ORDER,
             "B523" in cands))

    g = float(s.oracle_fn(s.params))
    c = float(cands["B523"](s, g))
    err = float(s.compare_fn(c, g))
    tol = float(s.tol)

    rel_mod = abs(g - M.array_average_clip()) / max(abs(g), 1e-300)
    check("A2 golden ≡ 能力层闭式（rel < 1e-12）", rel_mod < 1e-12, "rel=%.3e" % rel_mod)
    d_cand = abs(c - V.cand_b523())
    check("A3 candidate ≡ 数值核默认档（逐位）", d_cand < 1e-15, "|Δ|=%.3e" % d_cand)

    check("B1 err ≤ tol（闭式 ⇄ 数值一致）", err <= tol,
          "err=%.3e tol=%.1e" % (err, tol))
    check("B2 resid ≤ tol/100（余量 ≥100× · 防候选精度偷偷退化）", err <= tol / 100.0,
          "resid=%.3e tol/100=%.1e ⇒ %.0f×" % (err, tol / 100.0, tol / max(err, 1e-300)))

    chain = [16, 32, 64, 128, 256]
    res = [abs(V.cand_b523(n=n) - g) for n in chain]
    mono = all(res[i] > res[i + 1] for i in range(len(res) - 1))
    check("C1 残差随 n 严格单调降（真截断阶 · 非恒等）", mono,
          "链=%s" % ["%.3e" % x for x in res])
    ratios = [res[i] / res[i + 1] for i in range(len(res) - 1)]
    # 🔴 相邻比趋近的是 16 = 2⁴，不是 4；不写死方向（|r_last−16| ≤ |r_first−16|）
    check("C2 相邻比趋近 16=2⁴（O(h⁴) · 不写死方向）",
          abs(ratios[-1] - 16.0) <= abs(ratios[0] - 16.0),
          "链比=%s（标称 16）" % ["%.2f" % x for x in ratios])

    check("D1 默认档 resid ≫ 1e-13（非代数恒等 / 非自证桩）", err > 1e-13,
          "resid=%.3e（地板 1e-13）" % err)

    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    check("E1 反向探针：非法参数必抛（waist/aperture/n_modes）",
          _raises(lambda: V.cand_b523(waist_m=0.0))
          and _raises(lambda: V.golden_b523(aperture_half_m=0.0))
          and _raises(lambda: V.golden_b523(n_modes=0)),
          "")
    check("E2 反向探针：宽孔径 ⇒ γ→1（极限口径）",
          abs(M.aperture_clip_efficiency(0.0, M.DEFAULT_WAIST_M,
                                         M.DEFAULT_WAIST_M * 100.0) - 1.0) < 1e-12,
          "")
    check("E3 反向探针：零孔径 ⇒ γ→0（极限口径）",
          M.aperture_clip_efficiency(0.0, M.DEFAULT_WAIST_M,
                                     M.DEFAULT_WAIST_M * 1e-6) < 1e-6,
          "")

    ci = os.path.join(_HERE, "run_ci_regression.py")
    with open(ci, encoding="utf-8") as f:
        in_core = "run_v2d1_smoke.py" in f.read()
    check("F1 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    sc = M.selfcheck_qnet_hetero_array()
    bad = [k for k, v in sc.items() if not v]
    check("G1 能力层自检全 PASS（%d 项）" % len(sc), not bad, "FAIL=%s" % bad[:5])

    # ── H M1 负结果机器化（裁决：不立新锚）────────────────────────────
    from lda_harness import d1_registries as D1
    adj = D1.D1_M1_ADJUDICATION

    def _scan_cover_drift(defs):
        """返回 (缺, 漂移) —— 覆盖锚是否仍在且方法未变。抽成纯函数以便反向探针。"""
        miss, dr = [], []
        for aid in D1.d1_covering_anchor_ids():
            spec = adj["covering_anchors"][aid]
            d = defs.get(aid) or {}
            if not d:
                miss.append(aid)
                continue
            ok_metric = (d.get("metric") or "") == spec["metric"]
            ok_oracle = spec["oracle_must_contain"].lower() in (d.get("oracle") or "").lower()
            ok_cand = spec["candidate_must_contain"].lower() in (d.get("candidate_desc") or "").lower()
            if not (ok_metric and ok_oracle and ok_cand):
                dr.append("%s(metric=%s oracle=%s cand=%s)"
                          % (aid, ok_metric, ok_oracle, ok_cand))
        return miss, dr

    def _scan_sentinels(defs, sentinels=None):
        """返回把「不可锚」指标名偷登记成锚的 id 列表（哨兵集可指定，默认 M1）。"""
        src = D1.d1_m1_sentinel_metrics() if sentinels is None else sentinels
        sent = {s.lower() for s in src}
        return [bid for bid, d in defs.items()
                if any(s in ((d.get("metric") or "") + " " + (d.get("title") or "")).lower()
                       for s in sent)]

    miss, drift = _scan_cover_drift(BENCHMARK_DEFS)
    order_bad = [aid for aid in D1.d1_covering_anchor_ids() if aid not in BENCHMARK_ORDER]
    check("H1 覆盖锚仍在且方法未漂移（metric ∧ golden ∧ candidate ∧ ORDER）",
          not miss and not drift and not order_bad,
          "缺=%s 漂移=%s 不在ORDER=%s" % (miss, drift, order_bad))

    hit = _scan_sentinels(BENCHMARK_DEFS)
    check("H2 哨兵指标名未被偷登记（判定『不可锚』的物理量不得换名立锚）",
          not hit, "命中=%s" % hit[:6])

    scd = D1.d1_selfcheck()
    bad_d = [k for k, v in scd.items() if not v]
    check("H3 M1 裁决面完整（verdict ∧ ≥3 理由 ∧ 每条 ≥12 字 ∧ 覆盖锚 ≥2 且带方法规格）",
          not bad_d and adj.get("verdict") == "NOT_ANCHORABLE",
          "FAIL=%s" % bad_d[:5])

    # ── I 反向探针（**先证能变红**：不能变红的判据=假绿）─────────────────
    _fake_bad_metric = {aid: dict(BENCHMARK_DEFS[aid]) for aid in D1.d1_covering_anchor_ids()}
    _first = D1.d1_covering_anchor_ids()[0]
    _fake_bad_metric[_first]["metric"] = "somethingelse_metric"
    _, _dr = _scan_cover_drift(_fake_bad_metric)
    check("I1 反向探针：篡改覆盖锚 metric ⇒ H1 必红", bool(_dr), "红项=%s" % _dr[:2])

    _fake_sentinel = {"B_ZZTEST": {"metric": D1.d1_m1_sentinel_metrics()[0],
                                   "title": "偷登记探针"}}
    check("I2 反向探针：注入哨兵指标名 ⇒ H2 必红",
          bool(_scan_sentinels(_fake_sentinel)), "命中=%s" % _scan_sentinels(_fake_sentinel))

    # ── J B524（M3 Kapitza 界面热导）─────────────────────────────────
    s4 = by.get("B524")
    check("J1 B524 ∈ DEFS ∧ ORDER ∧ specs ∧ candidates",
          s4 is not None and "B524" in BENCHMARK_DEFS and "B524" in BENCHMARK_ORDER
          and "B524" in cands,
          "spec=%s defs=%s order=%s cand=%s"
          % (s4 is not None, "B524" in BENCHMARK_DEFS, "B524" in BENCHMARK_ORDER,
             "B524" in cands))

    g4 = float(s4.oracle_fn(s4.params))
    c4 = float(cands["B524"](s4, g4))
    err4 = float(s4.compare_fn(c4, g4))
    tol4 = float(s4.tol)

    rel_mod4 = abs(g4 - T.kapitza_conductance(float(s4.params.get("T_K", 4.0)))) / max(abs(g4), 1e-300)
    check("J2 B524 golden ≡ 能力层闭式（rel < 1e-12）", rel_mod4 < 1e-12,
          "rel=%.3e" % rel_mod4)
    d4 = abs(c4 - V.cand_b524())
    check("J3 B524 candidate ≡ 数值核默认档（逐位）", d4 < 1e-9, "|Δ|=%.3e" % d4)

    check("J4 B524 err ≤ tol（闭式 ⇄ 数值微分一致）", err4 <= tol4,
          "err=%.3e tol=%.2f" % (err4, tol4))
    check("J5 B524 resid ≤ tol/100（余量 ≥100×）", err4 <= tol4 / 100.0,
          "resid=%.3e tol/100=%.3e ⇒ %.0f×" % (err4, tol4 / 100.0, tol4 / max(err4, 1e-300)))

    eps_chain = list(V._EPS_CHAIN["B524"])
    res4 = [abs(V.cand_b524(eps=e) - g4) for e in eps_chain]
    mono4 = all(res4[i] > res4[i + 1] for i in range(len(res4) - 1))
    check("J6 B524 残差随 ε 严格单调降（真截断阶 · 非恒等）", mono4,
          "链=%s" % ["%.3e" % x for x in res4])
    ratios4 = [res4[i] / res4[i + 1] for i in range(len(res4) - 1)]
    # 中心差商标称 O(ε²) ⇒ 相邻比趋近 4（不写死方向 · 容差 0.02 防「两端都≈4」的浮点末位抖动假红）
    check("J7 B524 相邻比趋近 4=2²（O(ε²) · 不写死方向）",
          abs(ratios4[-1] - 4.0) <= max(abs(ratios4[0] - 4.0), 0.02),
          "链比=%s（标称 4）" % ["%.4f" % x for x in ratios4])

    # 🔴 跨平台稳健（BL-M2c 教训）：resid 必须远高于 ulp 级别，否则平台舍入差会放大成假红/假绿
    ulp4 = 2.0 ** -52 * abs(g4)
    check("J8 B524 非自证桩且跨平台稳健（resid>1e-13 ∧ resid/ulp ≫ 1e4）",
          err4 > 1e-13 and (err4 / ulp4) > 1e4,
          "resid=%.3e ulp=%.2e 比=%.1e" % (err4, ulp4, err4 / ulp4))

    check("J9 B524 反向探针：非法参数必抛（T=0 / eps 越界 / θ=0）",
          _raises(lambda: V.golden_b524(T_K=0.0))
          and _raises(lambda: V.cand_b524(eps=0.6))
          and _raises(lambda: V.golden_b524(theta1_K=0.0)),
          "")

    scT = T.selfcheck_hetero_thermal()
    badT = [k for k, v in scT.items() if not v]
    check("J10 能力层 hetero_thermal 自检全 PASS（%d 项）" % len(scT), not badT,
          "FAIL=%s" % badT[:5])

    # ── K M2 裁决（「良率=既有耦合律的统计包装」· 不立新锚）────────────
    hitM2 = _scan_sentinels(BENCHMARK_DEFS, D1.d1_m2_sentinel_metrics())
    check("K1 M2 哨兵指标名未被偷登记（统计包装不得单独立锚）",
          not hitM2, "命中=%s" % hitM2[:6])

    sc2 = D1.d1_m2_selfcheck()
    bad2 = [k for k, v in sc2.items() if not v]
    check("K2 M2 裁决面完整（verdict ∧ ≥4 理由 ∧ 每条 ≥12 字 ∧ ≥4 哨兵 ∧ 章程原定项在册）",
          not bad2 and D1.D1_M2_ADJUDICATION.get("verdict") == "NOT_ANCHORABLE",
          "FAIL=%s" % bad2[:5])

    emp = D1.D1_M2_ADJUDICATION.get("empirical") or {}
    check("K3 M2 负证据在册（闭式 ∧ 设计点 ∧ MC 跨种子 ∧ Simpson 收敛链）",
          bool(emp.get("yield_closed_form")) and bool(emp.get("design_point"))
          and len(emp.get("mc_worst_of_8_seeds") or {}) >= 2
          and bool(emp.get("density_simpson_chain")),
          "证据键=%s" % sorted(emp))

    # ── L 反向探针（M2 面）────────────────────────────────────────────
    _fake_m2 = {"B_ZZM2": {"metric": D1.d1_m2_sentinel_metrics()[0],
                           "title": "统计包装偷登记探针"}}
    check("L1 反向探针：注入 M2 哨兵指标名 ⇒ K1 必红",
          bool(_scan_sentinels(_fake_m2, D1.d1_m2_sentinel_metrics())),
          "命中=%s" % _scan_sentinels(_fake_m2, D1.d1_m2_sentinel_metrics()))

    n_bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("D1 门禁：%s（FAIL=%d）· B523 golden=%.15e resid=%.3e（%.0f×）· "
          "B524 golden=%.12f resid=%.3e（%.0f×）"
          % ("ALL PASS" if n_bad == 0 else "有红色", n_bad, g, err, tol / max(err, 1e-300),
             g4, err4, tol4 / max(err4, 1e-300)))
    print("=" * 78)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
