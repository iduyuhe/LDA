# -*- coding: utf-8 -*-
"""S8 门禁：**网覆盖完备**（每条网必须有归类 —— 布了 / 端口未布 / 布失败）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
审计发现（2026-11-04）：`dpnr.route_block` 在 c17 上只布了 **4/11** 条网 ——
7 条接 primary I/O 的网（`n1/n10/n2/n22/n23/n6/n7`）在 `len(pts) < 2` 处被**静默跳过**，
而 `unrouted` 返回**空** ⇒ 读者会以为「全布完了」，于是 `DRC = 0` 被误读成「c17 已清零」。

本门禁只钉一件事：**每条网都要有归类，且「没布」必须大声说出来**。

  S8a **四分类自洽**：`routed + skipped_port + failed == total`，且 `total == 网表网数`
        （total 由 `dsynth.Netlist` **独立算出**，不信路由结果自述）。
  S8b **跳过的必须明说**：`skipped_port` 恰为「只有 1 个端点」的网；且 `all_routed=False`
        （当前 4/11，若有人把它报成 True ⇒ 红）。
  S8c **反向 A（谎报全布）**：把一条 skipped 塞进 routed ⇒ `accounted > total`，
        `complete` 必须变 False。
  S8d **反向 B（静默丢弃）**：清空 skipped ⇒ `accounted < total`，`missing` 必须非空。
  S8e **卡片同源**：`/api/digital_demo` 的 `capacity.dpnr_coverage` == 独立复算。
  S8f **complete ≠ all_routed**：两个布尔必须能分开（把「有归类」读成「全布」是本项目头号失真）。

诚实边界
────────
· 本门禁**不**要求 `all_routed=True` —— 端口未建模是当前事实，要求它反而会逼人造假。
· 它只保证「没布的要被看见」；把 7 条端口网真正布出来，是后续端口建模那一步的事。
"""
from __future__ import annotations

import json
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


def _net_names(nl) -> set:
    """网表里出现过的全部网名（输出 + 输入），**独立于**路由模块。"""
    s = set()
    for g in nl.gates:
        s.add(g.out)
        s.update(g.ins)
    return s


def main() -> int:
    print("S8 门禁：网覆盖完备（布了 / 端口未布 / 布失败 —— 每条网必须有归类）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)
    rt = P.route_block(nl, pl)
    cov = rt["coverage"]
    ref = P.net_coverage(rt)                       # 独立复算

    # ── S8a 四分类自洽（total 用网表独立算）──────────────────────────
    nets = _net_names(nl)
    check("S8a 四分类自洽：routed(%d) + skipped_port(%d) + failed(%d) == total(%d)，"
          "且 total == 网表网数(%d)"
          % (cov["routed"], cov["skipped_port"], cov["failed"], cov["total"], len(nets)),
          cov["routed"] + cov["skipped_port"] + cov["failed"] == cov["total"]
          and cov["total"] == len(nets) and cov["complete"]
          and not cov["missing"] and not cov["unknown"] and not cov["overlap"],
          "cov=%r nets=%d" % (cov, len(nets)))

    # ── S8b 被跳过的网必须明说 ───────────────────────────────────────
    single = sorted(n for n, pts in rt["pins"].items() if len(pts) < 2)
    check("S8b 单端点网全部进 skipped_port（%d 条：%s）∧ all_routed=False"
          " —— 现在就是没全布，不许报成 True"
          % (len(single), ",".join(single)),
          sorted(rt["skipped_port_nets"]) == single
          and len(single) == cov["skipped_port"]
          and cov["all_routed"] is False,
          "skipped=%r single=%r all_routed=%r"
          % (rt["skipped_port_nets"], single, cov["all_routed"]))

    # ── S8c 反向 A：谎报全布 ⇒ 归类数超过总数 ────────────────────────
    fake = dict(rt)
    fake["routed"] = list(rt["routed"]) + [single[0]]
    c1 = P.net_coverage(fake)
    check("S8c 反向 A（谎报全布）：把「%s」同时塞进 routed 与 skipped ⇒ overlap=%r ∧ "
          "complete 必为 False（**四分类必须互斥**，并集相等不足以证明记账正确）"
          % (single[0], c1["overlap"]),
          c1["overlap"] == [single[0]] and c1["complete"] is False,
          "c1=%r" % (c1,))

    # ── S8d 反向 B：静默丢弃 ⇒ 漏记 ──────────────────────────────────
    fake2 = dict(rt)
    fake2["skipped_port_nets"] = []
    c2 = P.net_coverage(fake2)
    check("S8d 反向 B（静默丢弃）：清空 skipped_port ⇒ accounted %d < total %d ∧ "
          "missing 非空（这就是改动前的老行为）"
          % (c2["accounted"], c2["total"]),
          c2["accounted"] < c2["total"] and bool(c2["missing"])
          and c2["complete"] is False,
          "c2=%r" % (c2,))

    # ── S8e 卡片同源 ────────────────────────────────────────────────
    from lda_webui import digital_case as DC                    # noqa: E402
    DC.clear_cache()
    card_cov = (DC.case_card().get("capacity") or {}).get("dpnr_coverage") or {}
    check("S8e 卡片 capacity.dpnr_coverage == 独立复算（%d 布 / %d 端口 / total %d）"
          % (card_cov.get("routed", -1), card_cov.get("skipped_port", -1),
             card_cov.get("total", -1)),
          card_cov == ref, "card=%r ref=%r" % (card_cov, ref))

    # ── S8f complete 与 all_routed 必须可分 ─────────────────────────
    check("S8f `complete`（有归类）≠ `all_routed`（真的全布）：当前 complete=%s ∧ "
          "all_routed=%s —— 两个布尔混用是本项目头号失真"
          % (cov["complete"], cov["all_routed"]),
          cov["complete"] is True and cov["all_routed"] is False)

    # ── S8g 自入 CI core ────────────────────────────────────────────
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("S8g 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s8_smoke.py" in ck)

    # ── S8h 耗时红线 ────────────────────────────────────────────────
    dt = time.time() - T0
    check("S8h 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S8a] 四分类：routed %d + skipped %d + failed %d = total %d（网表 %d）"
          % (cov["routed"], cov["skipped_port"], cov["failed"], cov["total"], len(nets)))
    print("  [S8b] 端口未布网显式记账：%s" % ",".join(rt["skipped_port_nets"]))
    print("  [S8c–d] 反向：谎报全布 / 静默丢弃 ⇒ 覆盖度必失配")
    print("  [S8e] 卡片与门禁同源（capacity.dpnr_coverage）")
    print("  [边界] 本门禁**不要求** all_routed=True：端口未建模是当前事实，"
          "要求它等于逼人造假")

    if _FALS:
        print("S8 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S8 全绿 · 网覆盖完备：每条网都有归类，且「没布」大声说出来"
          "（c17 实测 4 布 / 7 端口未布 / 0 失败）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
