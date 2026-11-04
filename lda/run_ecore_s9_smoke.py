# -*- coding: utf-8 -*-
"""S9 门禁：**B 系列主链能跑既有 LVS**（适配器，不是第二套实现）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
审计发现（2026-11-04）：`dpnr.route_block` 的 `pins` 是 **4 元组**
`(inst, pin, x, y)`，而 `ddrc_lvs.run_lvs` 期望 `net -> [(x, y)]` ⇒ 直接喂会
`ValueError: too many values to unpack` ⇒ **B 系列主链根本跑不了既有 LVS**。
后果不是「少一个检查」，而是**切换主链时会丢掉「短路」这条最关键的证据**
（旧链 183 条短路条目 / 43 对网）。

本门禁钉三件事：

  S9a **适配器只做形状适配**：4→2 元组，**点值逐位不变**（不取整、不合并、不插值）。
  S9b **适配器是必要的**：把原始 4 元组直接喂 `run_lvs` ⇒ 必 `ValueError`
       （证明它不是「可选的装饰」）。
  S9c **作用域与结论同行**：c17 实测 `nets_checked=4 / total=11`、`uncovered=7`、
       `scope=ROUTED_SUBSET_ONLY`、`ok_is_full_chip=False`。
       🔴 `ok=True` 只是**子集**结论 —— 不许读成「LVS 通过」。
  S9d **不许造出干净 LVS**：复制一条金属改标成异网 ⇒ 必报 `short`。
  S9e **多端点无形状**必报 `net_no_shapes`（这是「没布」在 LVS 层的样子）。
  S9f **断开必报** `net_disconnected`（剔掉一条金属 ⇒ 该网连通性崩）。
  S9g **卡片同源**：`/api/digital_demo` 的 `capacity.dpnr_lvs` == 独立复算。
  S9h **不造第二套实现**：`dpnr` 里不得出现 `def run_lvs`（实现仍只有 `ddrc_lvs` 一份）。

诚实边界
────────
· 本门禁**不要求** `ok_is_full_chip=True` —— 7 条端口网还没建模，要求它等于逼人造假。
· 适配器通过 ≠ c17 的 LVS 通过：4 条已布网干净，**7 条未布网根本没被检验**。
· 这不改善任何几何结果（DRC 87 / LVS 183 条仍在旧链上）。
"""
from __future__ import annotations

import ast
import copy
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dpnr as P                          # noqa: E402
from lda_l2.ecore import ddrc_lvs as RL                     # noqa: E402
from lda_l2.ecore import dverilog as V                      # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 120.0

_HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    print("S9 门禁：B 系列主链跑既有 LVS（适配器 = 形状适配，不是第二套实现）")

    nl = V.parse(V.SAMPLE_VERILOG)
    pl = P.place_real(nl)
    rt = P.route_block(nl, pl)
    shapes = P.all_routing(rt)
    raw = rt["pins"]
    ad = P.pins_for_lvs(rt)
    lv = P.lvs_scoped(rt)

    # ── S9a 适配器只做形状适配，点值逐位不变 ────────────────────────
    same = (sorted(ad) == sorted(raw)
            and all(len(ad[n]) == len(raw[n]) for n in raw)
            and all(ad[n][i] == (p[2], p[3])
                    for n, pts in raw.items() for i, p in enumerate(pts))
            and all(len(t) == 2 for pts in ad.values() for t in pts))
    check("S9a 适配器只做形状适配：%d 条网 / %d 个点，4 元组 → 2 元组且**点值逐位不变**"
          "（不取整、不合并、不插值 —— 改点值等于改 LVS 结论）"
          % (len(ad), sum(len(v) for v in ad.values())),
          same, "nets=%d pts=%d" % (len(ad), sum(len(v) for v in ad.values())))

    # ── S9b 适配器是必要的：原始 4 元组必炸 ──────────────────────────
    raised = ""
    try:
        RL.run_lvs(shapes, raw)
    except ValueError as e:
        raised = str(e)
    check("S9b 适配器是**必要的**：原始 4 元组直接喂 run_lvs ⇒ ValueError"
          "（「%s」）—— 这就是 v0.9.375 之前 B 系列主链跑不了 LVS 的原因" % raised[:46],
          "too many values to unpack" in raised, "raised=%r" % (raised,))

    # ── S9c 作用域必须与结论同行 ────────────────────────────────────
    check("S9c 作用域显式：ok=%s ∧ scope=%s ∧ nets_checked=%d/%d ∧ uncovered=%d ∧ "
          "ok_is_full_chip=%s —— `ok` 只是**子集**结论"
          % (lv["ok"], lv["scope"], lv["nets_checked"], lv["nets_total"],
             len(lv["nets_uncovered"]), lv["ok_is_full_chip"]),
          lv["ok"] is True
          and lv["scope"] == "ROUTED_SUBSET_ONLY"
          and lv["ok_is_full_chip"] is False
          and lv["nets_checked"] + len(lv["nets_uncovered"]) == lv["nets_total"]
          and lv["nets_checked"] == len({s.net for s in shapes if s.net is not None})
          and sum(lv["by_rule"].values()) == lv["n_problems"]
          and lv["unique_pairs"] <= lv["n_problems"],
          "lv=%r" % ({k: v for k, v in lv.items() if k not in ("problems",)},))

    # ── S9d 反向 A：故意短路必报 short ──────────────────────────────
    metal = next(s for s in shapes if s.kind == "metal" and s.net is not None)
    other = next(s for s in shapes
                 if s.kind == "metal" and s.net is not None and s.net != metal.net)
    dup = copy.copy(metal)
    dup.net = other.net
    res_d = RL.run_lvs(list(shapes) + [dup], ad)
    rules_d = {p[0] for p in res_d["problems"]}
    check("S9d 反向 A（不许造干净 LVS）：复制一条 %s 金属改标成 %s ⇒ 必报 `short`"
          "（实测 %s）" % (metal.net, other.net, sorted(rules_d)),
          ("short" in rules_d or "short_via" in rules_d) and res_d["ok"] is False,
          "rules=%r ok=%r" % (sorted(rules_d), res_d["ok"]))

    # ── S9e 反向 B：多端点无形状 ⇒ net_no_shapes ────────────────────
    victim = next(n for n, pts in raw.items() if len(pts) >= 2)
    sh_e = [s for s in shapes if s.net != victim]
    ad_e = dict(ad)
    ad_e[victim] = [ad[victim][0], ad[victim][1]]
    res_e = RL.run_lvs(sh_e, ad_e)
    rules_e = {p[0] for p in res_e["problems"]}
    check("S9e 反向 B（「没布」在 LVS 层的样子）：剔掉网 %s 的全部形状但保留它的 "
          "≥2 个端点 ⇒ 必报 `net_no_shapes`" % victim,
          "net_no_shapes" in rules_e and res_e["ok"] is False,
          "rules=%r" % (sorted(rules_e),))

    # ── S9f 反向 C：断开必报 net_disconnected ───────────────────────
    vm = [s for s in shapes if s.net == victim and s.kind == "metal"]
    res_f = RL.run_lvs([s for s in shapes if s is not vm[0]], ad) if len(vm) > 1 else None
    rules_f = {p[0] for p in res_f["problems"]} if res_f else set()
    check("S9f 反向 C（连得上才算布通）：从网 %s 的 %d 条金属里剔掉 1 条 ⇒ 必报 "
          "`net_disconnected`" % (victim, len(vm)),
          res_f is not None and "net_disconnected" in rules_f and res_f["ok"] is False,
          "n_metal=%d rules=%r" % (len(vm), sorted(rules_f)))

    # ── S9g 卡片同源 ────────────────────────────────────────────────
    from lda_webui import digital_case as DC                    # noqa: E402
    DC.clear_cache()
    card_lv = (DC.case_card().get("capacity") or {}).get("dpnr_lvs") or {}
    ref = {k: v for k, v in lv.items() if k != "problems"}
    check("S9g 卡片 capacity.dpnr_lvs == 独立复算（checked %d/%d · scope %s · "
          "selfcheck 空）"
          % (card_lv.get("nets_checked", -1), card_lv.get("nets_total", -1),
             card_lv.get("scope")),
          card_lv == ref and DC.selfcheck(DC.case_card()) == [],
          "card=%r" % (card_lv,))

    # ── S9h 不造第二套实现 ──────────────────────────────────────────
    with open(os.path.join(_HERE, "lda_l2", "ecore", "dpnr.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    defs = {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    check("S9h **不造第二套 LVS**：dpnr 里没有 `def run_lvs`（实现仍只有 ddrc_lvs "
          "一份 —— 两套必然漂移，本仓已踩过短路口径分叉）",
          "run_lvs" not in defs, "dpnr 自定了 run_lvs")

    # ── S9i 自入 CI core ────────────────────────────────────────────
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("S9i 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s9_smoke.py" in ck)

    # ── S9t 耗时红线 ────────────────────────────────────────────────
    dt = time.time() - T0
    check("S9t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S), dt < AN_ELAPSED_MAX_S)

    print()
    print("  [S9a] 适配器：%d 条网 / %d 个点，点值逐位不变"
          % (len(ad), sum(len(v) for v in ad.values())))
    print("  [S9b] 原始 4 元组 ⇒ ValueError（证明适配器必要）")
    print("  [S9c] LVS 作用域：%s · %d/%d 网 · ok=%s 但 ok_is_full_chip=%s"
          % (lv["scope"], lv["nets_checked"], lv["nets_total"],
             lv["ok"], lv["ok_is_full_chip"]))
    print("  [S9d–f] 反向三向：故意短路 / 多端点无形状 / 断开 ⇒ 各必红")
    print("  [S9g] 卡片与门禁同源（capacity.dpnr_lvs）")
    print("  [S9h] 不造第二套 LVS 实现（AST 查 dpnr 无 def run_lvs）")
    print("  [边界] 适配器通过 ≠ c17 的 LVS 通过：4 条已布网干净，"
          "**7 条未布网根本没被检验**")

    if _FALS:
        print("S9 有红色：%s" % ", ".join(_FALS))
        return 1
    print("S9 全绿 · B 系列主链可跑既有 LVS：适配器只做形状适配，"
          "作用域随结论同行，三个反向探针都能判红")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
