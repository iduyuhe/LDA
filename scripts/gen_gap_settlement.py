# -*- coding: utf-8 -*-
"""缺口台账并账生成器（N4 · v0.9.283）。

把 18 张案例卡的 `case_card()["gaps"]` 并成**一张可机核的表**：

    docs/GAP_SETTLEMENT.md    人读（markdown 表）
    docs/gap_settlement.json  机读（含棘轮）

═══ 为什么需要它（N4 的核心发现）═══
审计 v3 写「94 条缺口」，现算 **112** —— 漏了 **18 条**：
`j1`(2) / `j3`(4) / `oi`(7) / `accel`(5)。前两者模块级无 `GAPS` 常量，后两者只在
`case_card()` 里返回；而审计只扫了模块级常量 ⇒ 结构性漏计。

🔴 **更严重的是第二个发现**：112 条里 **58 条根本没有闭合状态标记**
（超导 5 + 电子 20 + 光子 14 + 量子 19 全无状态）。原因不是"没人标"，
是**台账有 6 种形态**：

    gaps_closed 字段 / 元素 closed 键 / 元素 status 键 / 元素 state 键 /
    纯字符串（无状态） / 元素无状态字段

⇒ **任何单一的「已闭合 X 条」数字都取决于口径。** 本生成器**不猜**：
无可靠状态源的一律计入 `unmarked`，并**逐卡登记它的状态来源**。

═══ 纪律 ===═
· 纯 stdlib、无时间戳、无随机 ⇒ 两次运行逐字节相同
· `--check` 只比对不写盘（供门禁守「文档与代码同源」）
· 不改任何卡、不产生任何新物理量
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "lda"))

#: 卡 → 域。d1/d2/d4 是**量子域蓝图 v2**（光-量异质集成 / QEC 码族 / 域扩展），
#: 🔴 审计 v3 把它们算进"光子 36 条" ⇒ 域归属错误，本表修正。
DOMAIN = {
    "pchip": "光子", "pm": "光子", "soc": "光子", "oi": "光子",
    "accel": "光子", "sensor": "光子",
    "qchip": "量子", "qs": "量子", "j1": "量子", "j2": "量子", "j3": "量子",
    "j4": "量子", "j5": "量子", "d1": "量子", "d2": "量子", "d4": "量子",
    "schip": "超导", "ecore": "电子",
}
#: 模块名不规整者单列
MODULE = {"d4": "d4case"}
#: qchip 的 case_card 默认 n_modes=216（flagship），这里统一用 12 保持快且稳定
ARGS = {"qchip": (12,)}

#: 棘轮（**只降不升**）：待补状态的缺口数。要求逐步给每卡补状态源。
UNMARKED_MIN = 58
#: 棘轮（**只升不降**）：有据已闭合的缺口数。
CLOSED_MIN = 28


def _classify(card):
    """返回 (缺口数, 状态来源, 已闭 or None)。None = 无可信状态源。"""
    g = card.get("gaps") or []
    n = len(g)
    gc, gt = card.get("gaps_closed"), card.get("gaps_total")
    if isinstance(gc, int) and isinstance(gt, int) and gt == n:
        return n, "gaps_closed 字段", gc
    if not g:
        return n, "无缺口", 0
    if isinstance(g[0], dict):
        head = g[0]
        if "closed" in head:
            return n, "元素 closed 键", sum(1 for x in g if x.get("closed") is True)
        for key in ("status", "state"):
            if key in head:
                return (n, "元素 %s 键" % key,
                        sum(1 for x in g
                            if "闭合" in str(x.get(key)) and "未" not in str(x.get(key))))
        return n, "元素无状态字段", None
    return n, "纯字符串（无状态）", None


def collect():
    """现算全表（确定性）。"""
    cards = {}
    for k in sorted(DOMAIN):
        mod = MODULE.get(k, k + "_case")
        M = importlib.import_module("lda_webui." + mod)
        card = M.case_card(*ARGS.get(k, ()))
        n, src, closed = _classify(card)
        cards[k] = {
            "domain": DOMAIN[k],
            "gaps": n,
            "status_source": src,
            "closed": closed,
            "open": None if closed is None else n - closed,
            "unmarked": n if closed is None else 0,
        }
    agg = {}
    for k in sorted(cards):
        d = cards[k]["domain"]
        a = agg.setdefault(d, {"gaps": 0, "closed": 0, "open": 0, "unmarked": 0})
        a["gaps"] += cards[k]["gaps"]
        if cards[k]["closed"] is None:
            a["unmarked"] += cards[k]["gaps"]
        else:
            a["closed"] += cards[k]["closed"]
            a["open"] += cards[k]["open"]
    total = {x: sum(agg[d][x] for d in agg) for x in ("gaps", "closed", "open", "unmarked")}
    return {"schema": "lda_gap_settlement_v1", "cards": cards,
            "by_domain": agg, "total": total,
            "ratchet": {"unmarked_min": UNMARKED_MIN, "closed_min": CLOSED_MIN}}


def render_md(ref) -> str:
    """渲染 markdown（确定性；仅由 ref 决定）。"""
    c, agg, tot = ref["cards"], ref["by_domain"], ref["total"]
    out = [
        "# 缺口台账并账（N4）",
        "",
        "> **本文件由 `scripts/gen_gap_settlement.py` 生成，请勿手改** ——",
        "> 门禁 `run_p2_usability_smoke` 会重跑生成器比对，零漂移才通过。",
        "> 数据源：18 张案例卡的 `case_card()[\"gaps\"]` 现算（纯 stdlib · 无时间戳）。",
        "",
        "## 1. 逐卡并账",
        "",
        "| 域 | 卡 | 缺口数 | 状态来源 | 已闭 | 未闭 | 未标 |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in sorted(c):
        r = c[k]
        if r["closed"] is None:
            out.append("| %s | `%s` | %d | %s | — | — | **%d** |"
                       % (r["domain"], k, r["gaps"], r["status_source"], r["gaps"]))
        else:
            out.append("| %s | `%s` | %d | %s | %d | %d | 0 |"
                       % (r["domain"], k, r["gaps"], r["status_source"],
                          r["closed"], r["open"]))
    out += [
        "",
        "## 2. 按域汇总",
        "",
        "| 域 | 缺口 | 已闭(有据) | 未闭(有据) | 未标状态 |",
        "|---|---|---|---|---|",
    ]
    for d in ("光子", "量子", "超导", "电子"):
        if d in agg:
            a = agg[d]
            out.append("| %s | %d | %d | %d | **%d** |"
                       % (d, a["gaps"], a["closed"], a["open"], a["unmarked"]))
    out += [
        "| **合计** | **%d** | **%d** | **%d** | **%d** |"
        % (tot["gaps"], tot["closed"], tot["open"], tot["unmarked"]),
        "",
        "## 3. 三条结论（比数字更重要）",
        "",
        "1. 🔴 **总数是 %d，不是 94**。审计 v3 漏了 **18 条**：`j1`(2) / `j3`(4) /"
        " `oi`(7) / `accel`(5) —— 前两者模块级无 `GAPS` 常量、后两者只在 `case_card()`"
        " 里返回，而审计只扫了模块级常量。" % tot["gaps"],
        "2. 🔴 **%d / %d（%.1f%%）根本没有闭合状态标记**。这不是「没人标」，是台账有"
        " **6 种形态** ⇒ 任何单一「已闭合 X 条」都取决于口径。本表**不猜**，"
        "无可靠状态源一律计入「未标」。" % (tot["unmarked"], tot["gaps"],
                                        tot["unmarked"] * 100.0 / tot["gaps"]),
        "3. 🔴 **域归属修正**：`d1`/`d2`/`d4` 是**量子域蓝图 v2**，审计 v3 把它们算进"
        "「光子 36 条」⇒ 光子/量子的真实构成与旧表**不同数**（旧光子 36 = pchip+sensor"
        "+pm+soc+d1+d2+d4；新光子 36 = pchip+pm+soc+oi+accel+sensor）。"
        "**同数不同构成 —— 聚合数字又一次掩盖了结构。**",
        "",
        "## 4. 棘轮",
        "",
        "| 指标 | 当前 | 方向 | 含义 |",
        "|---|---|---|---|",
        "| `unmarked` | **%d** | 只降不升 | 待补状态源的缺口数 |" % tot["unmarked"],
        "| `closed`（有据） | **%d** | 只升不降 | 有明确状态源且已闭合 |" % tot["closed"],
        "",
        "> `unmarked` 只降，意味着**新加缺口必须带状态源**；否则棘轮当场红。",
        "",
    ]
    return "\n".join(out)


def _atomic_write(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="缺口台账并账（N4）")
    ap.add_argument("--check", action="store_true", help="只比对不写盘（供门禁）")
    a = ap.parse_args(argv)

    ref = collect()
    md = render_md(ref)
    js = json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    pm = os.path.join(ROOT, "docs", "GAP_SETTLEMENT.md")
    pj = os.path.join(ROOT, "docs", "gap_settlement.json")

    if a.check:
        bad = []
        for path, want in ((pm, md), (pj, js)):
            if not os.path.isfile(path):
                bad.append("%s 缺" % os.path.basename(path))
                continue
            with open(path, "rb") as f:
                got = f.read().decode("utf-8")
            if got != want:
                bad.append("%s 漂移" % os.path.basename(path))
        if bad:
            print("FAIL: " + " / ".join(bad), file=sys.stderr)
            return 1
        t = ref["total"]
        print("OK: 并账与代码一致（%d 缺口 · 已闭 %d / 未闭 %d / 未标 %d）"
              % (t["gaps"], t["closed"], t["open"], t["unmarked"]))
        return 0

    _atomic_write(pm, md)
    _atomic_write(pj, js)
    t = ref["total"]
    print("已生成 docs/GAP_SETTLEMENT.md / docs/gap_settlement.json")
    print("  缺口 %d（光子 %d / 量子 %d / 超导 %d / 电子 %d）· 已闭 %d · 未闭 %d · 未标 %d"
          % (t["gaps"], ref["by_domain"]["光子"]["gaps"], ref["by_domain"]["量子"]["gaps"],
             ref["by_domain"]["超导"]["gaps"], ref["by_domain"]["电子"]["gaps"],
             t["closed"], t["open"], t["unmarked"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
