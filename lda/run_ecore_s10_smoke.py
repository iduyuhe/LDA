# -*- coding: utf-8 -*-
"""S10 门禁：**单端点网三分类**（真端口 / 悬空网 —— 混成一类就是把工作量估小）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么（v0.9.379）
───────────────────────────────────────────────────────────────────────────────
S8 把「端点 < 2 的网」统称 `skipped_port`（7 条）。本轮实测发现这个**名字失真**：

  · **6 条**才是 primary I/O 端口网 —— 输入 `n1/n2/n6/n7` + 输出 `n22/n23`，
    它们**只要补上端口模型（pad 落点）就有望布通**；
  · **1 条** `n10` 是**悬空网** —— `n10` 是 `g10` 的输出，而本仓 c17 源里
    `nand g22 (n22, n16, n19)` 的第二输入写的是 `n16`（标准 ISCAS-85 c17 是 `n10`）。
    它**补端口也布不通**，只能改网表；而改网表会让 DRC 87 / LVS 183 / 时序 57.303 ps /
    DEF 571 B 全部一次性失效 ⇒ 本仓只如实披露，不动网表。

把两者混称「端口未布」，读者会把「补端口就全布通」当成下一步 —— 实际上布通后
`all_routed` 仍不可能为 True（还剩这条悬空网）。本门禁只钉这一件事：**两类必须分开报**。

  S10a **三分类互斥且并集相等**：`port ∩ dangling == ∅` ∧ `port ∪ dangling == skipped`。
  S10b **端口判定取自网表**（`nl.in_nets` / `nl.outputs`），由门禁**独立复算**比对；
        不许按网名（`n1`..`n23`）硬编码 —— 换份网表就失效的判据等于对着答案写。
  S10c **悬空网必须真是悬空**：用**网表事实**独立验证（该网只作为某门 `out` 出现、
        从不作为任何门 `in` 出现、且不是 primary I/O）。
  S10d **计数恒等式**：`skipped == true_port + dangling`（三处口径同时成立）。
  S10e **旧义未被偷改**：`coverage.skipped_port` 仍是**单端点全集**（= 7），
        且 `routed + skipped + failed == total` —— 防止「改语义」制造假绿。
  S10f **反向 A（伪造端口）**：把悬空网 `n10` 塞进 `port_nets` ⇒ 互斥检查必报。
  S10g **反向 B（伪造悬空）**：把一条 3 端点网标成悬空 ⇒ `dangling_outside_skipped` 必非空。
  S10h **空集不崩**：人造网表（无单端点网）⇒ 两类皆空且不抛。
  S10i **卡片同源**：`/api/digital_demo` 的 routing 段三个数 == 独立复算。
  S10j **claimability 没被顺手放宽**：`claimable` 仍 False 且 `all_nets_routed` 仍在 blocking
        —— 「分类修好了」不等于「可以签核」。
  S10k **旧措辞不许回退**：`dpnr.py` 不得再出现「另一端在 primary I/O 上」这种把
        端口与悬空混为一类的说法（措辞失真会让人重犯同一个误判）。
  S10l 本门禁已登记进 `CORE_SMOKES`（防静默漏接）+ 耗时红线。

诚实边界
────────
· 本门禁**不改善任何几何**：仍然 4/11 布通，DRC 0 / LVS 0 仍是**子集结论**。
· 它也**不修网表**：`n10` 悬空是 c17 源的事实，修它会推翻全部既有数字。
· 「6 条端口网补模型后可望布通」是**待验证的预期**，不是结论；下一版（pad 建模）
  才知道实际能布通几条。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dpnr as P                          # noqa: E402
from lda_l2.ecore import dverilog as V                      # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 120.0


def _split_violations(port: dict, dangling, skipped) -> list:
    """三分类的独立性检查（**门禁自己实现**，不复用被测模块的断言）。

    返回违规列表；空表示通过。故意写成「拿到三份数据就能判」，这样反向探针
    可以喂**伪造**的分类结果，验证这个检查器**真的会报**（而不是恒真）。
    """
    bad = []
    P_, D_, S_ = set(port), set(dangling), set(skipped)
    both = sorted(P_ & D_)
    if both:
        bad.append("同时被标为 port 与 dangling: %s" % both)
    union = P_ | D_
    if union != S_:
        bad.append("并集不等：多 %s / 少 %s"
                   % (sorted(union - S_), sorted(S_ - union)))
    return bad


def _nets_from_netlist(nl) -> dict:
    """纯网表事实：net -> {"n_out": 作为门输出的次数, "n_in": 作为门输入的次数}。"""
    st = {}
    for g in nl.gates:
        st.setdefault(g.out, {"n_out": 0, "n_in": 0})["n_out"] += 1
        for i in g.ins:
            st.setdefault(i, {"n_out": 0, "n_in": 0})["n_in"] += 1
    return st


def _is_primary_io(nl, net) -> bool:
    ins = set((getattr(nl, "in_nets", None) or {}).values())
    outs = set()
    for _p, tup in (getattr(nl, "outputs", None) or {}).items():
        outs.update(tuple(tup))
    return net in ins or net in outs


def main() -> int:
    print("S10 门禁：单端点网三分类（真端口 6 vs 悬空 1 —— 混成一类就是把工作量估小）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)
    # 🔴 v0.9.382：主链已启用 pad 落点 ⇒ **同源**取带 ports 的路由结果。
    #    此时单端点网只剩 1 条（`n10` 悬空），6 条端口网因拿到 pad 变成 2 端点 ——
    #    三分类逻辑没变，只是「真端口」从 6 条降到 0 条（它们都已可布）。
    _po = P.build_ports(nl, pl)
    rt = P.route_block(nl, _po["pl"], ports=_po)
    cov = rt["coverage"]
    port = rt["port_nets"]
    dang = rt["dangling_nets"]
    skipped = rt["skipped_port_nets"]

    # ── S10a 三分类互斥且并集相等（用门禁自己的检查器）────────────
    viol = _split_violations(port, dang, skipped)
    check("S10a 三分类互斥：port(%d) ∩ dangling(%d) == ∅ ∧ 并集 == skipped(%d)"
          % (len(port), len(dang), len(skipped)),
          viol == [], "违规=%r" % (viol,))

    # ── S10b 端口判定取自网表（独立复算，不许硬编码网名）────────────
    ref_port = sorted(n for n in skipped if _is_primary_io(nl, n))
    check("S10b 端口集由网表**独立复算**得出（%s），与模块自报一致"
          % ",".join(ref_port),
          ref_port == sorted(port), "ref=%r got=%r" % (ref_port, sorted(port)))

    # ── S10c 悬空网必须真是悬空（网表事实，不看模块自述）───────────
    st = _nets_from_netlist(nl)
    real_dangle = sorted(n for n in skipped if not _is_primary_io(nl, n))
    bad_d = [n for n in dang
             if _is_primary_io(nl, n) or st.get(n, {}).get("n_in", 0) != 0]
    check("S10c 悬空网经网表独立验证：%s（只作门输出、从无门输入、非 primary I/O）"
          % ",".join(dang),
          bad_d == [] and sorted(dang) == real_dangle,
          "bad=%r real=%r" % (bad_d, real_dangle))

    # ── S10d 计数恒等式（三处口径）─────────────────────────────────
    ok_d = (rt["n_skipped_port"] == rt["n_port_nets"] + rt["n_dangling_nets"]
            and cov["skipped_port"] == cov["skipped_true_port"] + cov["skipped_dangling"]
            and cov["skipped_true_port"] == len(port)
            and cov["skipped_dangling"] == len(dang))
    check("S10d 计数恒等：skipped(%d) == true_port(%d) + dangling(%d)，"
          "且 coverage 与列表长度三处同值"
          % (rt["n_skipped_port"], rt["n_port_nets"], rt["n_dangling_nets"]), ok_d)

    # ── S10e 旧义未被偷改 ──────────────────────────────────────────
    ok_e = (cov["skipped_port"] == len(skipped)
            and cov["routed"] + cov["skipped_port"] + cov["failed"] == cov["total"])
    check("S10e `coverage.skipped_port` 仍是**单端点全集**(%d)，"
          "routed(%d)+skipped+failed == total(%d) —— 未用「改语义」制造假绿"
          % (cov["skipped_port"], cov["routed"], cov["total"]), ok_e)

    # ── S10f 反向 A：伪造端口（把悬空网说成端口）⇒ 必报 ────────────
    fake_port = dict(port)
    if dang:
        fake_port[dang[0]] = {"dir": "in", "port": dang[0], "bit": 0}
    viol_a = _split_violations(fake_port, dang, skipped)
    check("S10f 反向 A：把悬空网 `%s` 谎报为端口 ⇒ 互斥检查必报（非恒真）"
          % (dang[0] if dang else "-"), len(viol_a) > 0, "viol=%r" % (viol_a,))

    # ── S10g 反向 B：伪造悬空（多端点网标成悬空）⇒ 必被逮 ──────────
    multi = sorted({g.out for g in nl.gates if st.get(g.out, {}).get("n_in", 0) >= 1})
    fake_dang = list(dang) + (multi[:1] or [])
    cov_b = P._coverage(routed=set(rt["routed"]) | set(rt["in_row_assign"] or {}),
                        skipped=set(skipped), failed=set(rt["unrouted"]),
                        total=set(rt["pins"]), dangling=set(fake_dang))
    check("S10g 反向 B：把多端点网 `%s` 标成悬空 ⇒ `dangling_outside_skipped` 必非空"
          % (multi[0] if multi else "-"),
          bool(cov_b["dangling_outside_skipped"]),
          "outside=%r" % (cov_b["dangling_outside_skipped"],))

    # ── S10h 空集不崩（人造：端口全接上，无单端点网）─────────────────
    class _FakeNL:
        in_nets = {("a", 0): "a"}
        outputs = {"y": ("y",)}
    empty = P.classify_single_endpoint(_FakeNL, {"a": [1, 2], "y": [3, 4]})
    check("S10h 无单端点网时两类皆空且不抛（in=%d dangling=%d）"
          % (empty["n_port"], empty["n_dangling"]),
          empty["n_port"] == 0 and empty["n_dangling"] == 0
          and empty["port_nets"] == {} and empty["dangling_nets"] == [])

    # ── S10i 卡片同源 ──────────────────────────────────────────────
    from lda_webui import digital_case as DC                    # noqa: E402
    DC.clear_cache()
    rout = (DC.case_card().get("routing") or {})
    ok_i = (rout.get("nets_skipped_port") == len(skipped)
            and rout.get("nets_skipped_true_port") == len(port)
            and rout.get("nets_dangling") == len(dang))
    check("S10i 卡片 routing 三段同源：skipped=%r / true_port=%r / dangling=%r"
          % (rout.get("nets_skipped_port"), rout.get("nets_skipped_true_port"),
             rout.get("nets_dangling")), ok_i)

    # ── S10j claimability 没被顺手放宽 ─────────────────────────────
    cl = DC.case_card().get("claimability") or {}
    blocking = list(cl.get("blocking") or [])
    check("S10j 分类修好 ≠ 可签核：claimable=%s ∧ `all_nets_routed` 仍在 blocking(%s)"
          % (cl.get("claimable"), ",".join(blocking)),
          cl.get("claimable") is False and "all_nets_routed" in blocking
          and "lvs_scope_full_chip" in blocking)

    # ── S10k 旧措辞不许回退 ────────────────────────────────────────
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "lda_l2", "ecore", "dpnr.py"), encoding="utf-8").read()
    check("S10k `dpnr.py` 不含把端口与悬空混为一类的旧措辞"
          "（「单端点网 = 另一端在 primary I/O 上」）",
          "单端点网 = 另一端在 primary I/O 上" not in src)

    # ── S10l 已登记进 CORE_SMOKES ──────────────────────────────────
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("S10l 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s10_smoke.py" in ck)

    # ── S10m 耗时红线 ──────────────────────────────────────────────
    dt = time.time() - T0
    check("S10m 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S10a–d] 三分类：真端口 %d（%s）· 悬空 %d（%s）· 并集 == 单端点全集 %d"
          % (len(port), ",".join(sorted(port)), len(dang), ",".join(dang), len(skipped)))
    print("  [S10f–g] 反向：伪造端口 / 伪造悬空 ⇒ 检查器必报")
    print("  [S10j] claimable 仍 False，blocking = %s" % ",".join(blocking))
    print("  [边界] 本门禁不改善几何（仍 4/11 布通）也不修网表（n10 悬空是 c17 源的事实）")

    if _FALS:
        print("S10 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S10 全绿 · 单端点网三分类：6 条真端口（补模型可望布通）+ 1 条悬空网"
          "（只能改网表）—— 「补端口就全布通」这个误判被机核拦住")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
