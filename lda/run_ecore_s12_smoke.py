# -*- coding: utf-8 -*-
"""S12 门禁：**M1 出口判据改口径**（已布网干净 + 未布网逐条归因 + 布通率披露）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么（v0.9.381）
───────────────────────────────────────────────────────────────────────────────
旧判据（审计文档 §5 M1 出口第 4 条）=「c17 **全芯片** DRC 干净 ∧ LVS 干净」。
本轮实测它**不可达**：6 条端口网无 pad 模型（S10/S11 已证补 pad 也是负收益）+ 1 条悬空网
（`n10`，网表缺陷）。要求它 = **逼人把子集结论写成全芯片结论** —— 那才是本项目头号失真。

新判据把「不可达」换成「**必须归因**」：每条未布网都要落到枚举原因上。
**这不是放松**：放松是「不布就跳过」，新判据是「不布可以，但必须说清为什么，且原因受限」。
归因不出来 ⇒ 判红；原因不在枚举里 ⇒ 判红。

  M1a 四条判据在 c17 上全成立（已布网 DRC 0 / 已布网 LVS 0 / 归因完备 / 布通率披露）。
  M1b 归因**覆盖全部未布网**（`skipped ∪ failed`），`unattributed` 必须为空。
  M1c 归因数**不重复计数**：`len(attribution) == skipped + failed`（同一网不得两条原因）。
  M1d 归因**语义正确**：`n10` 必须 `DANGLING`；6 条端口网必须 `PORT_UNMODELED`。
  M1e 布通率 `7/11` 且 `is_full_chip_routing` **由 routed==total 派生**（不是手填 False）。
  M1f 反向 A（抹掉一条归因）：该网变「未布且无归因」⇒ `ok=False` ∧ `unattributed` 非空。
  M1g 反向 B（枚举收紧）：只允许 `DANGLING` ⇒ `PORT_UNMODELED` 成 `bad_reason` ⇒ `ok=False`。
  M1h 反向 C（谎报全布）：`routed==total` ⇒ `is_full_chip_routing=True` ∧ ratio `11/11`
        —— 证明它是派生量，不是常量。
  M1i 缺数据按不成立：`drc=None` ⇒ `drc_clean=False`（「没测」≠「通过」）。
  M1j **`claimable` 没被顺手放宽**：仍 False，blocking 四条（含 `lvs_zero` —— 未布网
        带来 3 条 `net_no_shapes`/`pin_not_reached`，签核当然要 0）。
  M1k 卡片同源：`m1_exit` 在卡片里、与 `routing` 段同值、`selfcheck` 返回空。
  M1l 自登记 CORE_SMOKES + 耗时红线。

诚实边界
────────
· 本门禁证明的是「**这个阶段的数字可信**」，**不是**「c17 已签核」：
  `claimable` 仍 False（M1j 守），签核仍要六条全满足（含 `all_nets_routed`）。
· 判据本身**不改善几何**；布通 4/11 → **7/11** 是 v0.9.382 改拓扑（pad 走 M2 引出）的功劳，
  不是判据的功劳 —— 两者必须分开记。DRC 0 仍是 `ROUTED_SUBSET_ONLY`。
· 「改拓扑后能不能布通」仍未知 —— 本判据只是把「不可达」这件事**说清楚**，不是解决它。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import db3_trunk as B3                       # noqa: E402
from lda_l2.ecore import dpnr as P                            # noqa: E402
from lda_l2.ecore import dverilog as V                        # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL                       # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 180.0


def main() -> int:
    print("S12 门禁：M1 出口判据改口径（已布网干净 + 未布网逐条归因 + 布通率披露）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)
    # 🔴 v0.9.382：主链已启用 pad 落点 ⇒ 本门禁必须**同源**取带 ports 的结果，
    #    否则会拿旧路径的 4/11 去比主链的 7/11（M1e 就是这样把自己逮住的）。
    _po = P.build_ports(nl, pl)
    rt = P.route_block(nl, _po["pl"], ports=_po)
    drc = DL.run_drc(P.all_routing(rt))
    lvs = P.lvs_scoped(rt)
    m1 = P.m1_exit_assessment(rt, drc, lvs)

    # ── M1a 四条判据全成立 ────────────────────────────────────────
    check("M1a 四条判据在 c17 全成立：%s（DRC %d / LVS 已布网 %d·总 %d / 布通 %s）"
          % ("·".join("%s=%s" % (k, v) for k, v in m1["criteria"].items()),
             len(drc["violations"]), m1["lvs_problems_on_routed"],
             m1["lvs_problems_total"], m1["routed_ratio"]),
          m1["ok"] is True and m1["n_criteria"] == 4)

    # ── M1b 归因覆盖全部未布网 ────────────────────────────────────
    unrouted_all = set(rt["skipped_port_nets"]) | set(rt["unrouted"]) | set(rt["in_row_m3_fail"])
    check("M1b 归因覆盖**全部**未布网：%d 条（skipped %d ∪ failed %d ∪ in_row %d）· 未归因 %r"
          % (len(unrouted_all), len(rt["skipped_port_nets"]), len(rt["unrouted"]),
             len(rt["in_row_m3_fail"]), m1["unattributed"]),
          set(m1["attribution"]) == unrouted_all and m1["unattributed"] == [])

    # ── M1c 不重复计数 ───────────────────────────────────────────
    check("M1c 归因数不重复：len(attribution)=%d == skipped+failed=%d（同网不得两条原因）"
          % (len(m1["attribution"]),
             len(set(rt["skipped_port_nets"]) | set(rt["unrouted"]) | set(rt["in_row_m3_fail"]))),
          len(m1["attribution"]) == len(unrouted_all))

    # ── M1d 归因语义正确（n10 = 悬空，端口网 = 未建模）────────────
    dang = m1["attribution"].get("n10")
    port_attr = sorted(n for n, r in m1["attribution"].items() if r == "PORT_UNMODELED")
    check("M1d 归因语义：`n10`→%r（须 DANGLING）· 端口网 %d 条须 PORT_UNMODELED（%s）"
          % (dang, len(port_attr), ",".join(port_attr)),
          dang == "DANGLING" and port_attr == sorted(rt["port_nets"]))

    # ── M1e 布通率 + 派生 not 手填 ────────────────────────────────
    fake_full = dict(rt)
    fake_full["coverage"] = dict(rt["coverage"], routed=rt["coverage"]["total"])
    r_full = P.m1_exit_assessment(fake_full, drc, lvs)
    check("M1e 布通率 %s ∧ `is_full_chip_routing=%s`（**由 routed==total 派生**："
          "把 routed 改成 total ⇒ %s/%s ∧ True）"
          % (m1["routed_ratio"], m1["is_full_chip_routing"],
             r_full["routed_ratio"], r_full["is_full_chip_routing"]),
          m1["routed_ratio"] == "7/11" and m1["is_full_chip_routing"] is False
          and r_full["is_full_chip_routing"] is True)

    # ── M1f 反向 A：抹掉一条归因 ⇒ 必红 ───────────────────────────
    fake_a = dict(rt)
    fake_a["unrouted"] = [n for n in rt["unrouted"] if n != "n2"]
    ra = P.m1_exit_assessment(fake_a, drc, lvs)
    check("M1f 反向 A（少一条归因）：抹掉 `n2` 的“布失败”记录 ⇒ ok=%s ∧ unattributed=%r"
          % (ra["ok"], ra["unattributed"]),
          ra["ok"] is False and ra["unattributed"] == ["n2"])

    # ── M1g 反向 B：枚举收紧 ⇒ PORT_UNMODELED 成 bad_reason ───────
    rb = P.m1_exit_assessment(rt, drc, lvs, reasons=("DANGLING",))
    _n_non_dang = len([n for n, r in m1["attribution"].items() if r != "DANGLING"])
    check("M1g 反向 B（枚举收紧到只剩 DANGLING）：ok=%s ∧ bad_reason %d 条（须 = 非悬空的未布网 %d 条）"
          % (rb["ok"], len(rb["bad_reason"]), _n_non_dang),
          rb["ok"] is False and len(rb["bad_reason"]) == _n_non_dang and _n_non_dang >= 1)

    # ── M1i 缺数据按不成立 ───────────────────────────────────────
    r_nodrc = P.m1_exit_assessment(rt, None, lvs)
    check("M1i 缺数据按不成立：drc=None ⇒ drc_clean=%s（「没测」≠「通过」）"
          % r_nodrc["criteria"]["drc_clean"],
          r_nodrc["criteria"]["drc_clean"] is False and r_nodrc["ok"] is False)

    # ── M1j claimable 没被放宽 ───────────────────────────────────
    rep = B3.run_trunk(nl)
    cl = rep.get("claimability") or {}
    check("M1j `claimable` 未放宽：claimable=%s ∧ blocking=%s（四条，含 lvs_zero）"
          % (cl.get("claimable"), ",".join(cl.get("blocking") or [])),
          cl.get("claimable") is False
          and sorted(cl.get("blocking") or []) ==
          ["all_nets_routed", "hold_checked", "lvs_scope_full_chip", "lvs_zero"])

    # ── M1k 卡片同源 + selfcheck 空 ──────────────────────────────
    from lda_webui import digital_case as DC                    # noqa: E402
    DC.clear_cache()
    card = DC.case_card()
    cm1 = card.get("m1_exit") or {}
    bad = DC.selfcheck(card)
    check("M1k 卡片同源：m1_exit.ok=%s ∧ routed 与 routing 段同为 %r ∧ selfcheck %d 条问题"
          % (cm1.get("ok"), cm1.get("routed"), len(bad)),
          cm1.get("ok") is True
          and cm1.get("routed") == (card.get("routing") or {}).get("nets_with_segments")
          and bad == [],
          "bad=%r" % (bad[:3],))

    # ── M1l 自登记 ───────────────────────────────────────────────
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("M1l 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s12_smoke.py" in ck)

    dt = time.time() - T0
    check("M1m 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [M1a–c] 已布网 DRC %d / LVS %d · 未布 %d 条全部归因（不重复）"
          % (len(drc["violations"]), lvs["n_problems"], len(m1["attribution"])))
    print("  [M1d] 归因：%s"
          % " · ".join("%s=%s" % (n, r) for n, r in sorted(m1["attribution"].items())))
    print("  [M1e] 布通率 %s（is_full_chip_routing=%s，派生量）"
          % (m1["routed_ratio"], m1["is_full_chip_routing"]))
    print("  [M1j] claimable 仍 %s —— **阶段出口 ≠ 签核资格**" % cl.get("claimable"))
    print("  [边界] 布通 7/11 来自 v0.9.382 的拓扑改动（pad 走 M2），不是判据功劳；DRC 0 仍是子集结论")

    if _FALS:
        print("S12 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S12 全绿 · M1 出口判据已改口径：已布网干净 + 未布网逐条枚举归因（6 端口 + 1 悬空）"
          " + 布通率 7/11 显式披露；claimable 未放宽")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
