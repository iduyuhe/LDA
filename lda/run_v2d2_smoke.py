# -*- coding: utf-8 -*-
"""蓝图 v2 · **D2 QEC 码族 · M0 常驻门禁**（锚 **B525** 退极化信道 hashing 界）
+ **三类「不可锚」负结果机器化**（见 `lda_harness/d2_registries.py`）。

判据分节（**判据数实跑现数** · A4 + B2 + C2 + D1 + E3 + F1 + G1 + **H3 组 3** + **I 反向 2** = **19**）：
  A 接线 4：B525 ∈ DEFS ∧ ORDER ∧ specs ∧ candidates · golden ≡ 能力层闭式 ·
    candidate ≡ 数值核 · **params 键集 ≡ golden 形参集**（防「喂了不用」的假独立性）
  B 闭式⇄数值 2：`err ≤ tol` · `resid ≤ tol/1e6`（余量 ≥1e6×）
  C 收敛 2：残差随 n 严格单调降 · 相邻比**趋近 16=2⁴**（不写死方向）
  D 反自证桩 1：默认档 `resid > 1e-13` ∧ `resid/ulp(|g|) ≥ 1e4`（非代数恒等 ∧ 非跨平台脆弱）
  E 反向探针 3：非法 p 必抛 · `p=0 ⇒ I_c=1`（无噪）· `p=3/4 ⇒ I_c=−1`（完全退极化，**不是 0**）
  F 自入 CORE 1
  G 能力层自检 1：`qec_code_family.selfcheck` 全 PASS（≥12 项）
  H 负结果 3：**哨兵指标名未被偷登记** · 裁决面完整（自检全 PASS ∧ verdict 存在）·
    三类各 ≥2 条证据 ∧ reason ≥30 字
  I 反向探针 2：注入哨兵名 ⇒ H1 必红 · 截断 reason ⇒ H3 必红（先证能红）

🔴 本门禁源码**不写非本版锚的锚号/指标名**：D2 的哨兵名与裁决理由只在非门禁模块
  `lda_harness/d2_registries.py` 里，防 K4 文本代理把「提了一句」算成「有专属判据」。
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

_CI = os.path.join(_HERE, "run_ci_regression.py")


def _scan_sentinels(defs, sentinels):
    """返回把「不可锚」指标名偷登记成锚的 id 列表（纯函数，便于反向探针）。"""
    sents = {s.lower() for s in sentinels}
    out = []
    for bid, d in defs.items():
        blob = ((d.get("metric") or "") + " " + (d.get("title") or "")).lower()
        if any(s in blob for s in sents):
            out.append(bid)
    return out


def _adjudication_ok(adj):
    """裁决面完整性（纯函数，便于反向探针喂坏数据）。"""
    cls = (adj or {}).get("unanchorable_classes") or {}
    if len(cls) < 3:
        return False
    for v in cls.values():
        if not (isinstance(v.get("reason"), str) and len(v["reason"]) >= 30):
            return False
        if not (isinstance(v.get("evidence"), list) and len(v["evidence"]) >= 2):
            return False
        if not (isinstance(v.get("sentinel_metrics"), list) and len(v["sentinel_metrics"]) >= 1):
            return False
    return True


def main() -> int:
    print("=" * 78)
    print("蓝图 v2 · D2 门禁（B525 退极化信道 hashing 界 · 三类不可锚 H/I 组）")
    print("=" * 78)

    import inspect

    from lda_harness import verification_adapters as va
    from lda_harness import _batch_v2d2_numeric as V
    from lda_harness import d2_registries as D2
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    from lda_l2 import qec_code_family as Q

    specs, cands = va.build_harness_specs()
    by = {x.spec_id: x for x in specs}
    s = by.get("B525")
    check("A1 B525 ∈ DEFS ∧ ORDER ∧ specs ∧ candidates",
          s is not None and "B525" in BENCHMARK_DEFS and "B525" in BENCHMARK_ORDER
          and "B525" in cands,
          "spec=%s defs=%s order=%s cand=%s"
          % (s is not None, "B525" in BENCHMARK_DEFS, "B525" in BENCHMARK_ORDER,
             "B525" in cands))

    g = float(s.oracle_fn(s.params))
    c = float(cands["B525"](s, g))
    err = float(s.compare_fn(c, g))
    tol = float(s.tol)

    rel_mod = abs(g - Q.hashing_bound(float(s.params["p"]))) / max(abs(g), 1e-300)
    check("A2 golden ≡ 能力层闭式（rel < 1e-12）", rel_mod < 1e-12, "rel=%.3e" % rel_mod)

    d_cand = abs(c - V.cand_b525(float(s.params["p"])))
    check("A3 candidate ≡ 数值核默认档（逐位）", d_cand < 1e-15, "|Δ|=%.3e" % d_cand)

    # 🔴 params 键集必须与 golden 形参集一致（B372/B373 的「喂了不用」教训）
    sig = inspect.signature(V.golden_b525)
    want = sorted(p for p in sig.parameters)
    got = sorted(s.params)
    check("A4 params 键集 ≡ golden 形参集（防「喂了不用」）", want == got,
          "params=%s golden_args=%s" % (got, want))

    check("B1 err ≤ tol（闭式 ⇄ 数值一致）", err <= tol, "err=%.3e tol=%.4f" % (err, tol))
    check("B2 resid ≤ tol/1e6（余量 ≥1e6× · 防候选精度偷偷退化）", err <= tol / 1e6,
          "resid=%.3e tol/1e6=%.1e ⇒ %.2e×" % (err, tol / 1e6, tol / max(err, 1e-300)))

    chain = list(V._N_CHAIN["B525"])
    res = [abs(V.cand_b525(float(s.params["p"]), n=n) - g) for n in chain]
    mono = all(res[i] > res[i + 1] for i in range(len(res) - 1))
    check("C1 残差随 n 严格单调降", mono,
          "n=%s resid=%s" % (chain, ["%.3e" % r for r in res]))

    ratios = [res[i] / res[i + 1] for i in range(len(res) - 1)]
    # 复合 Simpson 标称 O(h⁴) ⇒ 相邻比趋近 16（不写死方向；带浮点容差防末位抖动假红）
    check("C2 相邻比趋近 16=2⁴（O(h⁴) · 不写死方向）",
          abs(ratios[-1] - 16.0) <= max(abs(ratios[0] - 16.0), 0.05),
          "链比=%s（标称 16）" % ["%.2f" % x for x in ratios])

    ulp = 2 ** -52 * abs(g)
    check("D1 反自证桩：resid > 1e-13 ∧ resid/ulp ≥ 1e4（非代数恒等 ∧ 非跨平台脆弱）",
          err > 1e-13 and (err / ulp) >= 1e4,
          "resid=%.3e ulp=%.2e ⇒ %.1e×" % (err, ulp, err / ulp))

    def _raises(fn, *a):
        try:
            fn(*a)
        except ValueError:
            return True
        return False

    check("E1 反向探针：非法 p 必抛（-0.1 与 0.8）",
          _raises(V.cand_b525, -0.1) and _raises(V.cand_b525, 0.8),
          "neg=%s over=%s" % (_raises(V.cand_b525, -0.1), _raises(V.cand_b525, 0.8)))

    v0 = abs(V.cand_b525(0.0) - 1.0)
    check("E2 极限：p=0 ⇒ I_c=1（无噪信道 · 数值与闭式同）",
          v0 < 1e-12 and abs(V.golden_b525(0.0) - 1.0) < 1e-15, "|Δ|=%.2e" % v0)

    # 🔴 端点纠错：p=3/4 是完全退极化 ⇒ I_c = −1（**不是 0**；穿零点在 p*≈0.1893）
    v75 = V.cand_b525(0.75)
    check("E3 极限：p=3/4 ⇒ I_c=−1（完全退极化 · **不是 0**）",
          abs(v75 + 1.0) < 1e-6 and abs(V.golden_b525(0.75) + 1.0) < 1e-12,
          "cand=%.9f golden=%.9f" % (v75, V.golden_b525(0.75)))

    with open(_CI, encoding="utf-8") as f:
        in_core = "run_v2d2_smoke.py" in f.read()
    check("F1 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    sc = Q.selfcheck_qec_code_family()
    bad = [k for k, v in sc.items() if not v]
    check("G1 能力层 qec_code_family 自检全 PASS（%d 项）" % len(sc), not bad,
          "FAIL=%s" % bad[:5])

    # ── H 三类「不可锚」负结果机器化 ─────────────────────────────────────
    hit = _scan_sentinels(BENCHMARK_DEFS, D2.d2_sentinel_metrics())
    check("H1 哨兵指标名未被偷登记（『不可锚』的物理量不得换名立锚）",
          not hit, "命中=%s" % hit[:6])

    scd = D2.selfcheck_d2_adjudication()
    bad_d = [k for k, v in scd.items() if not v]
    check("H2 裁决面自洽（自检 %d 项全 PASS ∧ verdict ∈ PARTIALLY_ANCHORABLE）" % len(scd),
          not bad_d and D2.D2_ADJUDICATION.get("verdict") == "PARTIALLY_ANCHORABLE",
          "FAIL=%s" % bad_d[:5])

    check("H3 三类不可锚各 ≥2 条证据 ∧ reason ≥30 字（负结果须带书面理由）",
          _adjudication_ok(D2.D2_ADJUDICATION),
          "类数=%d" % len(D2.D2_ADJUDICATION["unanchorable_classes"]))

    # ── I 反向探针（先证能红）────────────────────────────────────────────
    fake = {"B_ZZD2": {"metric": D2.d2_sentinel_metrics()[0], "title": "偷登记探针"}}
    check("I1 反向探针：注入哨兵指标名 ⇒ H1 必红",
          bool(_scan_sentinels(fake, D2.d2_sentinel_metrics())),
          "命中=%s" % _scan_sentinels(fake, D2.d2_sentinel_metrics()))

    import copy
    bad_adj = copy.deepcopy(D2.D2_ADJUDICATION)
    first = sorted(bad_adj["unanchorable_classes"])[0]
    bad_adj["unanchorable_classes"][first]["reason"] = "太短"
    check("I2 反向探针：截断某类理由 ⇒ H3 必红（非假绿）",
          not _adjudication_ok(bad_adj),
          "被截断类=%s" % first)

    n_bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("D2-M0 门禁：%s（FAIL=%d）· golden=%.15f · resid=%.3e（%.2e×）· |g|/tol=%.2f"
          % ("ALL PASS" if n_bad == 0 else "有红色", n_bad, g, err,
             tol / max(err, 1e-300), abs(g) / tol))
    print("=" * 78)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
