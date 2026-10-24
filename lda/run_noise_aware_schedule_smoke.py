#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""编译后噪声感知资源核算 门禁 smoke（D-226 · 净增 0 锚 · 能力层）。

═══ 判什么（分六节 · 19 条）═══
A 自检 1 · C 跨模块对拍 4 · D 错误预算可证界 4 · P 并行化 3 · Q 纠错轮数 4 · R 负结果与红线 3。

🔴 **本门禁只判「可证不等式 / 整数恒等 / 集合」**（承 D-218 纪律）：
  · **双侧可证界** `p_max ≤ p_exact ≤ Σp_i` —— 后者是 **Weierstrass 不等式**
    `∏(1−x_i) ≥ 1−Σx_i` 的直接推论，前者是 `1−∏(1−x_i) ≥ x_max`。**理论可证，不需 golden**；
  · **纠错轮数用定义式复算** `1−(1−p_L)^{r−1} < p_c ≤ 1−(1−p_L)^r` ——
    返回值可被独立检查，不依赖"参考实现"；
  · **并行化是整数比** `n_ops / depth`，两端点 `gain == n_ops` / `gain == 1` 是**严格整数等式**；
  · 跨模块 `n_cx` / `n_slots` 必须与 `ft_compiler.resource_report` **逐字相同**。

🔴 **本门禁要守住的一条"不许越界"**：这套核算**不是仿真器**。R3 断言
   `not_a_simulator is True` 且 caliber 明写"非线路级仿真" —— 防日后面板/文档把它
   读成"LDA 能预测线路保真度"（D3 已证浮点保真不可锚）。

🔴 命名纪律：节标签 A/C/D/P/Q/R —— **避开 B/E/S**（账本锚号前缀），防 K4 文本代理虚高覆盖。
"""

from __future__ import annotations

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check          # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _read(rel):
    fp = os.path.join(_HERE, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def _compiled():
    """真实编译结果：grid 3×4 上含远距 CX（强制路由 SWAP）+ T + 测量。"""
    from lda_qeda import ft_compiler as FT
    from lda_qeda import sc_topology_core as TC

    adj = TC.grid_topology(3, 4)["adjacency"]
    circ = FT.make_circuit([("H", 0), ("CX", 0, 2), ("T", 2), ("CX", 1, 3),
                            ("T", 3), ("CX", 0, 3), ("M", 3)])
    return FT.compile_circuit(circ, adj), adj


def main():
    from lda_qeda import ft_compiler as FT
    from lda_qeda import noise_aware_schedule as NS

    result, _adj = _compiled()

    # ═══════════════ A 自检 ═══════════════
    check("A1 模块自检 8/8 PASS", NS.run_selfchecks(verbose=False),
          "双侧界·严格单调·单门·兜底可见·并行端点·定义式·r=0·负结果")

    # ═══════════════ C 跨模块对拍（与 ft_compiler 同口径）═══════════════
    rep = FT.resource_report(result, d=3)
    pg = NS.parallel_gain(result)
    n_cx_ns = sum(1 for o in result["ops"] if o.get("kind") == "CX")

    check("C1 n_cx ≡ ft_compiler.resource_report.n_cx（同一份 op 序列数出来）",
          n_cx_ns == rep["n_cx"] and n_cx_ns > 0,
          "ns=%d rep=%d" % (n_cx_ns, rep["n_cx"]))

    check("C2 n_slots ≡ resource_report.n_slots ≡ len(layers) ≡ depth",
          pg["depth"] == rep["n_slots"] == len(result["layers"]) == result["depth"],
          "depth=%d slots=%d" % (pg["depth"], rep["n_slots"]))

    check("C3 覆盖守恒：各层 op 数之和 ≡ n_ops（每 op 恰出现一次）",
          sum(len(l) for l in result["layers"]) == pg["n_ops"] == len(result["ops"]),
          "sum_layers=%d n_ops=%d" % (sum(len(l) for l in result["layers"]), pg["n_ops"]))

    def _disjoint_layers(res):
        for layer in res["layers"]:
            seen = set()
            for o in layer:
                b = set(o.get("phys") or ())
                if seen & b:
                    return False
                seen |= b
        return True

    check("C4 同层物理比特两两不交（集合口径 · 复核 ft_compiler 的 I4）",
          _disjoint_layers(result))

    # ═══════════════ D 错误预算的可证界 ═══════════════
    eb = NS.error_budget(result["ops"])
    check("D1 🔴 双侧可证界：p_max ≤ p_exact ≤ Σp（Weierstrass 推论，无 golden）",
          eb["bound_ok"]
          and eb["p_max"] <= eb["p_exact"] + 1e-15
          and eb["p_exact"] <= eb["p_first_order"] + 1e-15,
          "pmax=%.6e exact=%.6e Σp=%.6e" % (eb["p_max"], eb["p_exact"],
                                            eb["p_first_order"]))

    mono, prev = True, 0.0
    for k in range(1, len(result["ops"]) + 1):
        cur = NS.error_budget(result["ops"][:k])["p_exact"]
        if not cur > prev:
            mono = False
            break
        prev = cur
    check("D2 严格单调：真实编译序列逐 op 累加，p_exact 每步严格增",
          mono, "n=%d 末值=%.6e" % (len(result["ops"]), prev))

    one = NS.error_budget([{"kind": "CX"}])
    check("D3 单门边界：p_exact ≡ p(CX)（残差<1e-15）",
          abs(one["p_exact"] - NS.DEFAULT_GATE_ERROR["CX"]) < 1e-15,
          "%.3e" % one["p_exact"])

    unk = NS.error_budget([{"kind": "not_registered_anywhere"}])
    check("D4 未登记门走兜底且**可见**（进 fallback_kinds，不静默当 0）",
          unk["fallback_kinds"] == ["not_registered_anywhere"]
          and unk["p_exact"] > 0.0,
          "p=%.3e fallback=%s" % (unk["p_exact"], unk["fallback_kinds"]))

    # ═══════════════ P 并行化（整数比）═══════════════
    check("P1 并行化收益落在整数边界内：1 ≤ gain ≤ n_ops",
          pg["gain_in_range"] and 1.0 - 1e-15 <= pg["gain"] <= pg["n_ops"] + 1e-15,
          "gain=%.4f n_ops=%d depth=%d" % (pg["gain"], pg["n_ops"], pg["depth"]))

    # 双向：all_disjoint ⇔ gain == n_ops
    dis = [{"kind": "CX", "phys": (i, i + 1), "logical": (i, i + 1)}
           for i in range(0, 8, 2)]
    r_dis = {"ops": dis, "layers": [dis], "depth": 1}
    g_dis = NS.parallel_gain(r_dis)
    g_real = pg
    check("P2 🔴 双向：全不冲突 ⇒ gain == n_ops；真实线路（有共享比特）⇒ all_disjoint=False ∧ gain<n_ops",
          g_dis["all_disjoint"] is True
          and abs(g_dis["gain"] - g_dis["n_ops"]) < 1e-12
          and g_real["all_disjoint"] is False
          and g_real["gain"] < g_real["n_ops"],
          "dis: gain=%.0f n=%d · real: gain=%.3f n=%d"
          % (g_dis["gain"], g_dis["n_ops"], g_real["gain"], g_real["n_ops"]))

    ser = [{"kind": "CX", "phys": (0, 1), "logical": (0, 1)} for _ in range(4)]
    g_ser = NS.parallel_gain({"ops": ser, "layers": [[o] for o in ser], "depth": 4})
    check("P3 全串行 ⇒ gain == 1（整数等式，不是近似）",
          g_ser["all_serial"] is True and abs(g_ser["gain"] - 1.0) < 1e-12,
          "gain=%.15f depth=%d" % (g_ser["gain"], g_ser["depth"]))

    # ═══════════════ Q 纠错轮数（定义式复算）═══════════════
    pl = 1.0e-6
    r_need = NS.syndrome_rounds(eb["p_exact"], pl)
    lhs = NS.syndrome_rounds_acc(r_need - 1, pl) if r_need >= 1 else 0.0
    rhs = NS.syndrome_rounds_acc(r_need, pl)
    check("Q1 🔴 定义式复算：1−(1−p_L)^{r−1} < p_c ≤ 1−(1−p_L)^r",
          r_need >= 1 and lhs < eb["p_exact"] <= rhs,
          "r=%d lhs=%.6e p_c=%.6e rhs=%.6e" % (r_need, lhs, eb["p_exact"], rhs))

    # 单调：预算收紧 ⇒ 轮数不减
    rs = [NS.syndrome_rounds(pc, pl) for pc in (1e-6, 1e-4, 1e-2, 0.5)]
    check("Q2 单调：预算越大所需轮数不减（4 档）",
          all(b >= a for a, b in zip(rs, rs[1:])) and rs[-1] > rs[0],
          "rounds=%s" % rs)

    check("Q3 零预算 ⇒ 0 轮（不虚报需要纠错）", NS.syndrome_rounds(0.0, pl) == 0)

    # 独立口径：逐轮累乘循环（不用闭式）找最小 r，必须与返回值相等
    def _loop_min_rounds(pc, pL, r_max=500000):
        if pc == 0.0:
            return 0
        acc = 0.0
        for k in range(1, r_max + 1):
            acc = 1.0 - (1.0 - acc) * (1.0 - pL)
            if acc >= pc:
                return k
        return r_max

    pairs = [(eb["p_exact"], pl), (1e-4, 1e-6), (1e-2, 1e-5), (0.25, 1e-3)]
    eq = all(_loop_min_rounds(pc, pL) == NS.syndrome_rounds(pc, pL) for pc, pL in pairs)
    check("Q4 独立口径：逐轮累乘循环求得的最小 r ≡ 返回值（4 组，非闭式）", eq,
          "rounds=%s" % [NS.syndrome_rounds(pc, pL) for pc, pL in pairs])

    # ═══════════════ R 负结果与红线 ═══════════════
    w = NS.why_not_anchored()
    check("R1 负结果机器化：anchorable=False ∧ ≥4 理由 ∧ ≥4 替代判据 ∧ 重评条件",
          w["anchorable"] is False and len(w["reasons"]) >= 4
          and len(w["substitute_criteria"]) >= 4 and bool(w["revisit_condition"]),
          "reasons=%d" % len(w["reasons"]))

    src = _read(os.path.join("lda_qeda", "noise_aware_schedule.py")).lower()
    banned = ("qiskit", "cirq", "pennylane", "qutip", "braket", "requests",
              "urllib", "socket", "openai", "anthropic", "numpy", "scipy")
    hit = [b for b in banned if ("import %s" % b) in src or ("from %s" % b) in src]
    check("R2 零第三方 / 零网络 / 零 LLM / 零 numpy（纯 stdlib 静态扫描）",
          not hit and "open(" not in src, "hit=%s" % hit)

    br = NS.budget_report(result, p_logical=pl)
    check("R3 🔴 不许越界：not_a_simulator=True ∧ caliber 明写「非线路级仿真」"
          "∧ 无 statevector/fidelity 字样",
          br["not_a_simulator"] is True
          and "非线路级仿真" in br["caliber"]
          and "statevector" not in src and "fidelity" not in src,
          "caliber=%s" % br["caliber"][:34])

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("噪声感知资源核算 门禁 smoke（D-226）：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
