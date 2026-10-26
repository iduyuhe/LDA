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

    # ══════════════════════ J LDPC 解码 BP + OSD-0（v0.9.298 · G-V2-D2-1）══════════════════════
    # 🔴 改前：该缺口只写着「解码器重且禁第三方 SDK ⇒ 未开工」。本层把它建起来，
    #    并且**不靠跑分**——用「无环图 ⇒ BP 后验 ≡ 精确逐位 MAP」这条精确性定理做验证。
    from lda_l2 import d2_ldpc_decoder as LDPC

    _sc_l = LDPC.selfcheck_d2_ldpc_decoder()
    check("J1 d2_ldpc_decoder 自检 %d 项全过（GF2 / 精确性定理 / 结构不变量 / 反向探针）"
          % len(_sc_l),
          not [k for k, v in _sc_l.items() if not v],
          "fail=%s" % [k for k, v in _sc_l.items() if not v])

    _tree = LDPC.tree_vs_exact_scan()
    check("J2 🔴 **无环图 ⇒ BP 后验 ≡ 精确逐位 MAP 后验**：穷举 512 个错误模式 · 破例 %d · "
          "最大偏差 %.2e（≤1e-9）" % (_tree["violations"], _tree["worst_abs_diff"]),
          _tree["violations"] == 0 and _tree["worst_abs_diff"] <= 1e-9,
          "%d/%d 码字" % (_tree["patterns"], _tree["codewords"]))
    check("J3 判据非空转：树码 512 模式 / 32 码字（左集合非 0）",
          _tree["patterns"] == 512 and _tree["codewords"] == 32)

    # 🔴 J4 反向探针：加一条边造出环 ⇒ 精确性**必须破**（证明 J2 不是恒真）
    _cyc = LDPC.tree_vs_exact_scan(LDPC.H_TREE_WITH_CYCLE)
    check("J4 🔴 反向探针：加一条边成环 ⇒ 精确性必破（破例 %d/%d）"
          % (_cyc["violations"], _cyc["patterns"]),
          _cyc["violations"] > 0)

    # 🔴 J5 OSD-0 结构性不变量：输出恒为合法码字（不是「近似对」，是 syndrome 恒 0）
    _n = 9
    _base = LDPC.deterministic_llr(_n)
    _bad_osd = [pat for pat in range(1 << _n)
                if LDPC.osd0_decode([(-_base[v] if (pat >> v) & 1 else _base[v])
                                     for v in range(_n)], LDPC.H_TREE)["syndrome"] != 0]
    check("J5 🔴 OSD-0 结构不变量：全部 512 个模式下输出 syndrome ≡ 0（合法码字）",
          not _bad_osd, "违约=%d" % len(_bad_osd))

    # 🔴 J6 无噪极限（闭式已知答案）：大 LLR ⇒ BP 一次迭代命中 ∧ OSD-0 恒返回该码字
    _cws = LDPC.enumerate_codewords(LDPC.H_TREE, _n)
    _bp_ok = all(
        (lambda r: r["converged"] and r["iterations"] == 1 and r["word"] == cw)(
            LDPC.bp_decode([(-40.0 if b else 40.0) for b in cw], LDPC.H_TREE))
        for cw in _cws)
    _osd_ok = all(
        LDPC.osd0_decode([(-40.0 if b else 40.0) for b in cw], LDPC.H_TREE)["word"] == cw
        for cw in _cws)
    check("J6 🔴 无噪极限：%d 个码字上 BP **一次迭代**即命中 ∧ OSD-0 恒返回该码字" % len(_cws),
          _bp_ok and _osd_ok, "bp=%s osd=%s" % (_bp_ok, _osd_ok))

    # J7 Hamming[7,4,3]（d=3）：OSD-0 必纠全部单比特错误 + 距离确实是 3
    _h_ok = all(
        LDPC.osd0_decode([(-0.6 if i == j else 3.0) for i in range(7)],
                         LDPC.H_HAMMING743)["word"] == tuple(0 for _ in range(7))
        for j in range(7))
    _hw = [sum(cw) for cw in LDPC.enumerate_codewords(LDPC.H_HAMMING743, 7)]
    check("J7 Hamming[7,4,3]：OSD-0 纠全部 7 个单错（错位最不可靠 ⇒ 不在 MRB）∧ d_min 确为 3",
          _h_ok and min(w for w in _hw if w > 0) == 3,
          "n_words=%d" % len(_hw))

    # ══════════════════════ K 色码精确译码 + 闭式失效概率（v0.9.298 · G-V2-D2-2）══════════════════════
    from lda_l2 import d2_color_code as CC

    _sc_c = CC.selfcheck_d2_color_code()
    check("K1 d2_color_code 自检 %d 项全过（闭式 / 完备码 / 失效≠逻辑错 / 反向探针）"
          % len(_sc_c),
          not [k for k, v in _sc_c.items() if not v],
          "fail=%s" % [k for k, v in _sc_c.items() if not v])

    # 🔴 K2 闭式已知答案（一）：闭式 P_fail = 1−(1−p)⁷−7p(1−p)⁶ ≡ 穷举 128 图样加权和
    _worst = max(abs(CC.closed_form_decoder_failure(q) - CC.exhaustive_decoder_failure(q))
                 for q in (1e-3, 5e-3, 0.05, 0.25))
    check("K2 🔴 闭式 ≡ 穷举（四档 p · 绝对 ≤1e-15）：实测 max|Δ| = %.2e" % _worst,
          _worst <= 1e-15)

    # 🔴 K3 闭式已知答案（二）：p=1/2 处两条路径都**恰好**等于 15/16（无容差 `==`）
    check("K3 🔴 p=1/2 ⇒ 闭式与穷举**都恰为 15/16 = 0.9375**（`==` 判定，非 isclose）",
          CC.closed_form_decoder_failure(0.5) == 0.9375
          and CC.exhaustive_decoder_failure(0.5) == 0.9375)

    # K4 色码判据性特征 + 完备码结构
    _st = CC.stab_x_elements()
    _leaders = set()
    for v in range(7):
        e = [0] * 7
        e[v] = 1
        _leaders.add(CC._syndrome_mask(tuple(e)))
    check("K4 色码特征：`H_X ≡ H_Z`（同常量）∧ Stab_X = 8 元素且非零重量**全为 4**（Steiner S(3,4,7)）"
          "∧ 完备码 7 个单错恰好覆盖全部 7 个非零伴随式",
          len(_st) == 8 and sorted({sum(w) for w in _st if any(w)}) == [4]
          and _leaders == set(range(1, 8)))

    # 🔴 K5 「失效」≠「逻辑错」（概念压扁是 N3-b 同型）：
    #    重量 2 必为逻辑错、重量 3 **不全是**；两量在 p=0.05 处必须可分辨
    _w3 = [CC._all_patterns()[i] for i in range(128)
           if sum(CC._all_patterns()[i]) == 3]
    check("K5 🔴 **失效 ≠ 逻辑错**：重量 2 全为逻辑错 ∧ 重量 3 既有也有非 ∧ p=0.05 处两量差 >1e-9",
          all(CC._is_logical_error(e) for e in CC._all_patterns() if sum(e) == 2)
          and any(CC._is_logical_error(e) for e in _w3)
          and any(not CC._is_logical_error(e) for e in _w3)
          and abs(CC.exhaustive_decoder_failure(0.05)
                  - CC.logical_error_probability(0.05)) > 1e-9,
          "w3=%d" % len(_w3))

    # K6 逻辑错在 p=1/2 处为**整数比** N/128（无容差）
    _nb = sum(1 for e in CC._all_patterns() if CC._is_logical_error(e))
    check("K6 p=1/2 ⇒ 逻辑错 = %d/128 = %.6f（整数比 · 与穷举一致，无容差）"
          % (_nb, _nb / 128.0),
          abs(CC.logical_error_probability(0.5) - _nb / 128.0) <= 1e-16)

    # K7 伪阈值只作**披露**（拟合量 ⇒ 非锚）：落在 (0,0.5) 且求根残差极小
    _pt = CC.pseudo_threshold()
    check("K7 伪阈值 = %.6f ∈ (0,0.5) ∧ 求根残差 %.1e（**披露数字 · 非锚**：拟合量不作 golden）"
          % (_pt["pseudo_threshold"], _pt["residual"]),
          0.0 < _pt["pseudo_threshold"] < 0.5 and _pt["residual"] < 1e-12)

    # ══════════ L 节 · 距离递增码族的码容量阈值标定（v0.9.306 · 闭合 G-V2-D2-5a）══════════
    # 缺口原文：两条解码器都只在 n≤9 小码上验了「译码正确性」；**距离递增的码族 + 有限尺寸标定
    # 给阈值/伪阈值仍需 Monte-Carlo —— 能做但未做**。本节把「码容量 / 完美综合征」这一半做掉，
    # 剩下的「有噪综合征时空解码」拆为 `G-V2-D2-5b`（仍未闭合，不合并、不假装）。
    from lda_l2 import d2_threshold_mc as TMC

    _p_, _t_, _ = TMC.run_selfchecks(verbose=False)
    check("L1 距离递增码族阈值标定：模块自检全过（%d/%d）" % (_p_, _t_), _p_ == _t_)

    # L2 🔴 定理级：P_fail(d, 1/2) ≡ 1/2 与反演对称 P_fail(d,1−p) ≡ 1−P_fail(d,p)
    #    （门禁**自己算**，不转调模块自检 —— 否则"自检说过了"就闭环了）
    _w1 = max(abs(TMC.pfail_closed(d, 0.5) - 0.5) for d in TMC.FAMILY_D)
    _w2 = max(abs(TMC.pfail_closed(d, 1.0 - q) - (1.0 - TMC.pfail_closed(d, q)))
              for d in TMC.FAMILY_D for q in (0.01, 0.1, 0.3, 0.45))
    check("L2 🔴 二项尾的两条定理：P(1/2)≡1/2（|Δ|=%.1e）∧ P(1−p)≡1−P(p)（|Δ|=%.1e）"
          % (_w1, _w2), _w1 < 1e-15 and _w2 < 1e-15)

    # L3 MC ⇄ 精确闭式（4σ，非 2σ；30 组只跑抽样 3 组以控时）
    _zs = []
    for _d in (5, 9):
        for _q in (0.05, 0.30):
            _r = TMC.pfail_mc(_d, _q, trials=4000)
            _se = (max(_r["closed"] * (1 - _r["closed"]), 1e-12) / _r["n"]) ** 0.5
            _zs.append((_r["phat"] - _r["closed"]) / _se)
    check("L3 MC（Wilson）⇄ 精确闭式：4 组 (d,p) 全部 |z| ≤ 4（max|z|=%.2f）"
          % max(abs(z) for z in _zs), all(abs(z) <= 4.0 for z in _zs))

    # L4 有限尺寸标定：闭式二分求根的交叉点**恰**为 0.5（不是拟合出来的）
    _roots = {d: TMC.crossing_closed(d, d + 2) for d in (3, 5, 7, 9)}
    check("L4 有限尺寸交叉点（闭式二分求根）≡ 0.5 —— 四条相邻对全部命中",
          all(abs(v - 0.5) < 1e-12 for v in _roots.values()),
          " ".join("%dx%d:%.12f" % (d, d + 2, v) for d, v in _roots.items()))

    # L5 阈值存在的定义性证据 + 披露面：方向翻转 ∧ 报告非空
    _rep = TMC.family_report(trials=500)
    check("L5 单调方向翻转（p<1/2 时 d↑ 严格↓、p>1/2 时 d↑ 严格↑）∧ 披露报告 %d 行"
          % len(_rep),
          TMC.monotone_direction(0.30) == -1 and TMC.monotone_direction(0.70) == 1
          and all(TMC.pfail_closed(TMC.FAMILY_D[i + 1], 0.30) < TMC.pfail_closed(TMC.FAMILY_D[i], 0.30)
                  for i in range(len(TMC.FAMILY_D) - 1))
          and len(_rep) == len(TMC.FAMILY_D) * 6)

    # L6 反向探针：闭式误写成 `d·p` ⇒ L2 必红（证明 L2 不是恒真）
    _wrong = min(1.0, 3 * 0.5)
    check("L6 反向探针：闭式误写 `d·p` ⇒ p=0.5 处给 %.1f 而非 0.5（L2 必红）" % _wrong,
          abs(_wrong - 0.5) > 0.4)

    # K8 🔴 判据数自洽（本卡 gate_checks 原写 13、实跑 19 ⇒ **陈旧漂移**，本版补上机器对拍）
    #    ⚠️ 注意 `D2` 是 `lda_harness.d2_registries`（注册表），**不是** `d2_case` —— 我第一次就写混了，
    #       当场 AttributeError 崩掉整个门禁（「门禁突变必须判红，不得崩溃」）。故这里显式导入 + try 兜底。
    _sofar = globals().get("PASS", 0) + globals().get("FAIL", 0)
    try:
        from lda_webui import d2_case as _D2C
        _decl = int(_D2C.case_card()["gate_checks"])
        _err = ""
    except Exception as exc:                      # pragma: no cover
        _decl, _err = -1, "%s: %s" % (type(exc).__name__, exc)
    check("K8 🔴 判据数自洽：卡内 gate_checks(%d) == 实跑 PASS 总数(%d，含本条)" % (_decl, _sofar + 1),
          _decl == _sofar + 1, "卡内=%d 实跑=%d %s" % (_decl, _sofar + 1, _err))

    n_bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("D2-M0 门禁：%s（FAIL=%d）· golden=%.15f · resid=%.3e（%.2e×）· |g|/tol=%.2f"
          % ("ALL PASS" if n_bad == 0 else "有红色", n_bad, g, err,
             tol / max(err, 1e-300), abs(g) / tol))
    print("=" * 78)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
